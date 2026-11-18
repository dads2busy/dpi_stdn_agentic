#!/usr/bin/env python3
"""Analyse the vocabulary seeding test (scripts/run_seeding_test.sh).

Held-out runs (post-fix fx{micro,biotech,pharma}_{v1v1v1,d3v1v1}) were normalized by extending a per-technology
vocab seeded from submitted single-agent runs (V), submitted 3-agent debate runs (D), or nothing (N, control),
two independent passes each (a, b). For each condition this reports, per domain:

  coverage    share of held-out per-tech names (norm_key) already mapped in the seed vocab
  seed canon  canonicals per tech in the seed vocab (median)
  new canon   canonicals per tech created while extending to the held-out runs (median)
  stab v1/d3  median per-tech median pairwise Jaccard of held-out normalized sets, single-agent / debate runs
  Δ debate    median per-tech (d3 - v1) on the held-out runs
  repro a~b   pair-F1 between passes a and b over "these two raw names share a canonical" (non-primary
              marker counted as its own class), median per tech. Higher = the normalization is more repeatable.

Then paired per-tech Wilcoxon tests of seed D vs seed V (and each vs N) on held-out stability.

Usage (code repo): uv run --with scipy --with numpy python scripts/seeding_test_analysis.py > output/analysis/seeding_test.md
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict
from itertools import combinations
from statistics import median

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
from normalize_outputs_global_granularity import _norm_key, make_vocab_key  # noqa: E402

SENTINEL = "__NON_PRIMARY__"
VDIR = "data/seedtest"
DOMAINS = {"microelectronics": "fxmicro", "biotech": "fxbiotech", "pharma": "fxpharma"}
CONDS = ["V", "D", "N"]
REPS = ["a", "b"]


def vocab(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)["mappings"]


def runs(stem):
    """tech -> list over run files of set of raw names; also tech -> set of all norm keys."""
    out, names = defaultdict(list), defaultdict(set)
    for path in sorted(glob.glob(f"output/raw/stdns_output_{stem}_*.csv")):
        per = defaultdict(set)
        with open(path) as fh:
            for r in csv.DictReader(fh):
                t, c = (r.get("technology") or "").strip(), (r.get("component") or "").strip()
                if t and c:
                    per[t].add(c)
                    names[t].add(c)
        for t, s in per.items():
            out[t].append(s)
    return out, names


def canon_sets(run_list, tech, voc):
    res = []
    for s in run_list:
        cs = {voc.get(make_vocab_key(c, tech, "technology"), c) for c in s}
        res.append(cs - {SENTINEL})
    return res


def med_jacc(sets):
    js = [len(a & b) / len(a | b) for a, b in combinations(sets, 2) if a | b]
    return median(js) if js else None


def pair_f1(names, tech, va, vb):
    """Agreement of two partitions of a tech's raw names (by canonical) over co-assigned pairs."""
    keys = sorted({_norm_key(n) for n in names})
    la = {k: va.get(make_vocab_key(k, tech, "technology")) for k in keys}
    lb = {k: vb.get(make_vocab_key(k, tech, "technology")) for k in keys}
    pa = {(x, y) for x, y in combinations(keys, 2) if la[x] is not None and la[x] == la[y]}
    pb = {(x, y) for x, y in combinations(keys, 2) if lb[x] is not None and lb[x] == lb[y]}
    if not pa and not pb:
        return None
    return 2 * len(pa & pb) / (len(pa) + len(pb))


def canons(voc, tech):
    pre = make_vocab_key("", tech, "technology")
    return {v for k, v in voc.items() if k.startswith(pre) and v != SENTINEL}


def wil(x):
    x = [v for v in x if v != 0]
    return stats.wilcoxon(x).pvalue if len(x) >= 5 else float("nan")


def main():
    seeds = {(c, r): vocab(f"{VDIR}/vocab_seed{c}_{r}.json") for c in "VD" for r in REPS}
    exts = {(c, r): vocab(f"{VDIR}/vocab_ext{c}_{r}.json") for c in CONDS for r in REPS}
    missing = [k for k, v in exts.items() if not v]
    if missing:
        print(f"WARNING: empty/missing extended vocabs: {missing}")

    print("# Vocabulary seeding test\n")
    print("Seed V = submitted single-agent runs; D = submitted 3-agent debate runs; N = no seed. "
          "Held-out = post-fix session runs. Values: pass a / pass b.\n")
    print("| domain | seed | coverage | seed canon/tech | new canon/tech | stab v1 | stab d3 | Δ debate | repro a~b |")
    print("|---|---|---|---|---|---|---|---|---|")
    stab = {}  # (cond, rep, domain, cfg) -> {tech: jaccard}
    for dom, stem in DOMAINS.items():
        v1r, v1n = runs(f"{stem}_v1v1v1")
        d3r, d3n = runs(f"{stem}_d3v1v1")
        techs = sorted(set(v1r) & set(d3r))
        for c in CONDS:
            cells = defaultdict(list)
            for r in REPS:
                ev = exts[(c, r)]
                sv = seeds.get((c, r), {})
                cov, sc, nc, s1, s3, dd = [], [], [], {}, {}, []
                for t in techs:
                    keys = {make_vocab_key(n, t, "technology") for n in v1n[t] | d3n[t]}
                    cov.append(sum(k in sv for k in keys) / len(keys))
                    seed_c = canons(sv, t)
                    sc.append(len(seed_c))
                    nc.append(len(canons(ev, t) - seed_c))
                    a, b = med_jacc(canon_sets(v1r[t], t, ev)), med_jacc(canon_sets(d3r[t], t, ev))
                    if a is not None and b is not None:
                        s1[t], s3[t] = a, b
                        dd.append(b - a)
                stab[(c, r, dom, "v1")], stab[(c, r, dom, "d3")] = s1, s3
                cells["cov"].append(f"{median(cov):.2f}")
                cells["sc"].append(f"{median(sc):.0f}")
                cells["nc"].append(f"{median(nc):.0f}")
                cells["s1"].append(f"{median(s1.values()):.3f}")
                cells["s3"].append(f"{median(s3.values()):.3f}")
                cells["dd"].append(f"{median(dd):+.3f}")
            rep = [pair_f1(v1n[t] | d3n[t], t, exts[(c, "a")], exts[(c, "b")]) for t in techs]
            rep = [x for x in rep if x is not None]
            j = lambda k: " / ".join(cells[k])
            print(f"| {dom} | {c} | {j('cov')} | {j('sc')} | {j('nc')} | {j('s1')} | {j('s3')} | {j('dd')} "
                  f"| {median(rep):.2f} |")

    print("\n## Paired per-tech tests on held-out stability (median of per-tech difference, Wilcoxon p)\n")
    print("| domain | runs | D − V (a) | D − V (b) | V − N (a) | V − N (b) | D − N (a) | D − N (b) |")
    print("|---|---|---|---|---|---|---|---|")
    for dom in DOMAINS:
        for cfg in ["v1", "d3"]:
            cells = []
            for x, y in [("D", "V"), ("V", "N"), ("D", "N")]:
                for r in REPS:
                    A, B = stab[(x, r, dom, cfg)], stab[(y, r, dom, cfg)]
                    diffs = [A[t] - B[t] for t in A if t in B]
                    cells.append(f"{median(diffs):+.3f} p={wil(diffs):.2g}")
            print(f"| {dom} | {cfg} | " + " | ".join(cells) + " |")

    print("\n## Cross-seed agreement on held-out names (pair-F1, median per tech)\n")
    for r in REPS:
        vals = []
        for dom, stem in DOMAINS.items():
            _, v1n = runs(f"{stem}_v1v1v1")
            _, d3n = runs(f"{stem}_d3v1v1")
            for t in sorted(set(v1n) & set(d3n)):
                f = pair_f1(v1n[t] | d3n[t], t, exts[("V", r)], exts[("D", r)])
                if f is not None:
                    vals.append(f)
        print(f"- V vs D, pass {r}: {median(vals):.2f} (n={len(vals)})")


if __name__ == "__main__":
    main()
