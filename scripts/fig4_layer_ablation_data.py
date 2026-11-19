#!/usr/bin/env python3
"""Per-technology stability values behind Fig. 4 (layer-wise ablation) of the Communications
Sustainability paper, using the paper's stated metric: for each technology, the median Jaccard
similarity over all pairs of its runs (10 pairs for 5 runs).

Panel A: naive single-shot prompt, raw names (output/naive_micro) vs the same output after
         per-technology normalization (pass A, output/naivetest/norm_a).
Panel B: structured single-agent (v1v1v1) vs three-agent debate (d3v1v1), submitted April 2026
         microelectronics runs, raw component names as extracted (output/raw), no normalization.
Both panels: the 60 microelectronics benchmark technologies, each with all available runs (at
least two; seven technologies have four debate runs), as in Table 2.

Writes output/analysis/fig4_layer_ablation_pertech.csv and prints medians with 95% bootstrap CIs
(10,000 resamples, unit = technology, seed 0).

Usage: uv run python scripts/fig4_layer_ablation_data.py
"""
import csv
import glob
import json
from collections import defaultdict
from itertools import combinations
from statistics import median

import numpy as np

BENCH = "data/tech_list_microelectronic_products.csv"
OUT = "output/analysis/fig4_layer_ablation_pertech.csv"


def bench():
    with open(BENCH) as f:
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


def naive_raw():
    out = defaultdict(list)
    for p in glob.glob("output/naive_micro/*.json"):
        d = json.load(open(p))
        out[d["technology"].strip()].append({c.strip() for c in d["components"] if c and c.strip()})
    return out


def med_pairwise(sets):
    js = [len(a & b) / len(a | b) for a, b in combinations(sets, 2) if a | b]
    return median(js) if js else None


def boot_ci(x, n=10_000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    meds = np.median(rng.choice(x, size=(n, len(x)), replace=True), axis=1)
    return np.percentile(meds, [2.5, 97.5])


def main():
    techs = bench()
    conditions = [
        ("A", "naive_raw", naive_raw()),
        ("A", "naive_normalized", runs_from_csvs(glob.glob("output/naivetest/norm_a/stdns_output_*.csv"))),
        ("B", "v1_raw", runs_from_csvs(glob.glob("output/raw/stdns_output_v1v1v1_2026041*.csv"))),
        ("B", "d3_raw", runs_from_csvs(glob.glob("output/raw/stdns_output_d3v1v1_2026041*.csv"))),
    ]
    rows = []
    for panel, cond, data in conditions:
        vals = {t: med_pairwise(data[t]) for t in sorted(techs) if len(data.get(t, [])) >= 2}
        vals = {t: v for t, v in vals.items() if v is not None}
        lo, hi = boot_ci(list(vals.values()))
        print(f"{panel} {cond:17s} n={len(vals):2d} median={median(vals.values()):.3f} "
              f"95% CI {lo:.3f}-{hi:.3f}")
        rows += [(panel, cond, t, f"{v:.6f}") for t, v in vals.items()]
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["panel", "condition", "technology", "median_pairwise_jaccard"])
        w.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
