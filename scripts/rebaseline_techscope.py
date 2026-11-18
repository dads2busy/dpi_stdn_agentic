#!/usr/bin/env python3
"""Re-baseline every normalization-dependent number in the Results under per-technology normalization.

Adopted 2026-11-18: all normalized numbers in the revision use per-technology vocabularies
(`--vocab-scope technology`); pass A is primary and pass B is the replication. This script is the single source
for:

  Table 1  (tab:ablation-norm)   naive single-shot vs naive + normalization, 60 micro techs
  Table 2  (tab:ablation-debate) v1 vs d3 and v1 vs d5 per domain, paired (R1.2 adds d5 for all domains);
                                 submitted session, with the post-fix session (d3) as replication
  Core ratio                     intersection over 5 runs / median run size, v1 vs d3 vs d5, micro
  Fig 6 data                     per-technology paired values -> output/analysis/rebaseline_fig6_pairs_{a,b}.csv

Not normalization-dependent and therefore not here: runtimes, debate rounds and convergence, the Fig 3B
pre-normalization (transcript-level) Jaccard, and the Nd HHI section. Table 4 is scripts/goldstandard_table4.py.
The invalid rate is scripts/debate_invalid_rate_techscope.py.

Per-technology stability = median pairwise Jaccard over runs (the paper's definition). Table 1 also reports the
mean pairwise Jaccard, which the April naive report used.

Usage (code repo): uv run --with scipy --with numpy python scripts/rebaseline_techscope.py \
    > output/analysis/rebaseline_techscope.md
"""
import csv
import glob
import json
from collections import defaultdict
from itertools import combinations
from statistics import mean, median

import numpy as np
from scipy import stats

PASSES = {"A": "normalized_techscope_a", "B": "normalized_techscope_b"}
NAIVE_NORM = {"A": "output/naivetest/norm_a", "B": "output/naivetest/norm_b"}
LISTS = {
    "microelectronics": "data/tech_list_microelectronic_products.csv",
    "biotech": "data/tech_list_biotechnology_products.csv",
    "pharma": "data/tech_list_pharmaceutical_products.csv",
}
# stems under output/<normalized dir>/stdns_output_<stem>*.csv (same file sets as the paper's analysis scripts)
SESSIONS = {
    "submitted": {
        "microelectronics": {"v1": "v1v1v1_2026041", "d3": "d3v1v1_2026041", "d5": "d5v1v1_2026041"},
        "biotech": {"v1": "biotech_v1v1v1_", "d3": "biotech_d3v1v1_", "d5": "biotech_d5v1v1_"},
        "pharma": {"v1": "pharma_v1v1v1_", "d3": "pharma_d3v1v1_", "d5": "pharma_d5v1v1_"},
    },
    "post-fix": {
        "microelectronics": {"v1": "fxmicro_v1v1v1_", "d3": "fxmicro_d3v1v1_"},
        "biotech": {"v1": "fxbiotech_v1v1v1_", "d3": "fxbiotech_d3v1v1_"},
        "pharma": {"v1": "fxpharma_v1v1v1_", "d3": "fxpharma_d3v1v1_"},
    },
}
BOOT_N, SEED = 10_000, 0


def bench(dom):
    with open(LISTS[dom]) as f:
        return {r["tech"].strip() for r in csv.DictReader(f)}


def runs_from_csvs(paths):
    out = defaultdict(list)
    for p in sorted(paths):
        run = defaultdict(set)
        with open(p) as fh:
            for r in csv.DictReader(fh):
                t, c = (r.get("technology") or "").strip(), (r.get("component") or "").strip()
                if t and c:
                    run[t].add(c)
        for t, s in run.items():
            out[t].append(s)
    return out


def pairwise(sets):
    return [len(a & b) / len(a | b) for a, b in combinations(sets, 2) if a | b]


def med_j(sets):
    js = pairwise(sets)
    return median(js) if len(sets) >= 2 and js else None


def boot_ci(x, stat=np.median):
    rng = np.random.default_rng(SEED)
    x = np.asarray(x, float)
    s = stat(rng.choice(x, size=(BOOT_N, len(x)), replace=True), axis=1)
    return np.percentile(s, [2.5, 97.5])


def fmt_ci(x):
    lo, hi = boot_ci(x)
    return f"{np.median(x):.3f} ({lo:.2f}–{hi:.2f})"


# ---------------- Table 1 ----------------
def table1():
    print("## Table 1 (tab:ablation-norm): naive single-shot vs naive + per-technology normalization\n")
    print("60 microelectronics technologies × 5 runs (`output/naive_micro`). Median over technologies of the "
          "per-technology pairwise Jaccard; 95% bootstrap CI (10,000 resamples, unit = technology). "
          "#components = per-technology union over the 5 runs.\n")
    raw = defaultdict(list)
    for p in glob.glob("output/naive_micro/*.json"):
        d = json.load(open(p))
        raw[d["technology"]].append({c.strip() for c in d["components"] if c and c.strip()})
    rows = [("Naive single-shot (raw names)", raw)]
    for k, d in NAIVE_NORM.items():
        rows.append((f"Naive + normalization (pass {k})", runs_from_csvs(glob.glob(f"{d}/stdns_output_*.csv"))))
    print("| Configuration | n | Median Jaccard (per-tech median pairwise) | Same, per-tech mean pairwise "
          "(April definition) | Median #components (union) |")
    print("|---|---|---|---|---|")
    for name, data in rows:
        ts = [t for t, v in data.items() if len(v) == 5]
        mj = [median(pairwise(data[t])) for t in ts]
        mn = [mean(pairwise(data[t])) for t in ts]
        un = [len(set().union(*data[t])) for t in ts]
        print(f"| {name} | {len(ts)} | {fmt_ci(mj)} | {fmt_ci(mn)} | {fmt_ci(un)} |")
    print()


# ---------------- Table 2 + Fig 6 data ----------------
def paired(ndir, stems, dom, a, b):
    """{tech: (a value, b value)} for benchmark techs with values in both configurations."""
    B = bench(dom)
    da = runs_from_csvs(glob.glob(f"output/{ndir}/stdns_output_{stems[a]}*.csv"))
    db = runs_from_csvs(glob.glob(f"output/{ndir}/stdns_output_{stems[b]}*.csv"))
    out = {}
    for t in sorted(B):
        x, y = med_j(da.get(t, [])), med_j(db.get(t, []))
        if x is not None and y is not None:
            out[t] = (x, y)
    return out


def row(label, pairs):
    x = [v for v, _ in pairs.values()]
    y = [w for _, w in pairs.values()]
    d = [w - v for v, w in pairs.values()]
    imp, wor = sum(v > 0 for v in d), sum(v < 0 for v in d)
    nz = [v for v in d if v != 0]
    p = stats.wilcoxon(nz).pvalue if len(nz) >= 5 else float("nan")
    lo, hi = boot_ci(d)
    return (f"| {label} | {len(d)} | {median(x):.3f} | {median(y):.3f} | {median(d):+.3f} [{lo:+.3f}, {hi:+.3f}] | "
            f"{imp}/{wor}/{len(d) - imp - wor} | {p:.2g} |")


def table2():
    print("## Table 2 (tab:ablation-debate): debate vs single agent, per-technology normalization\n")
    print("Per-technology median pairwise Jaccard; Δ = median of per-technology (debate − v1) with 95% bootstrap "
          "CI; imp/wor/tied counts; Wilcoxon two-sided p on per-technology differences.\n")
    for pname, ndir in PASSES.items():
        for session, doms in SESSIONS.items():
            for cmp in ["d3", "d5"]:
                if not all(cmp in s for s in doms.values()):
                    continue
                print(f"\n### Pass {pname}, {session} session, v1 vs {cmp}\n")
                print(f"| Domain | n | v1 median | {cmp} median | Δ [95% CI] | imp/wor/tied | Wilcoxon p |")
                print("|---|---|---|---|---|---|---|")
                allp = {}
                for dom, stems in doms.items():
                    pr = paired(ndir, stems, dom, "v1", cmp)
                    allp.update({(dom, t): v for t, v in pr.items()})
                    print(row(dom, pr))
                    if session == "submitted" and cmp == "d3":
                        with open(f"output/analysis/rebaseline_fig6_pairs_{pname.lower()}.csv", "a" if dom != "microelectronics" else "w", newline="") as f:
                            w = csv.writer(f)
                            if dom == "microelectronics":
                                w.writerow(["domain", "technology", "v1_jaccard", "d3_jaccard"])
                            for t, (x, y) in pr.items():
                                w.writerow([dom, t, f"{x:.4f}", f"{y:.4f}"])
                print(row("Combined", allp))
    print()


# ---------------- core ratio ----------------
def core_ratio():
    print("## Core ratio (micro): intersection across 5 runs / median run size, macro median over technologies\n")
    print("| Pass | v1 | d3 | d5 | n (v1/d3/d5) |")
    print("|---|---|---|---|---|")
    B = bench("microelectronics")
    for pname, ndir in PASSES.items():
        vals, ns = [], []
        for c in ["v1v1v1_2026041", "d3v1v1_2026041", "d5v1v1_2026041"]:
            data = runs_from_csvs(glob.glob(f"output/{ndir}/stdns_output_{c}*.csv"))
            cr = []
            for t in B:
                s = data.get(t, [])
                if len(s) == 5:
                    m = median(len(x) for x in s)
                    if m:
                        cr.append(len(set.intersection(*s)) / m)
            vals.append(median(cr))
            ns.append(len(cr))
        print(f"| {pname} | {vals[0]:.3f} | {vals[1]:.3f} | {vals[2]:.3f} | {'/'.join(map(str, ns))} |")
    print("\nSubmitted (old global vocab): v1 0.429, d3 0.200.\n")


def main():
    print("# Re-baseline under per-technology normalization (pass A primary, pass B replication)\n")
    table1()
    table2()
    core_ratio()


if __name__ == "__main__":
    main()
