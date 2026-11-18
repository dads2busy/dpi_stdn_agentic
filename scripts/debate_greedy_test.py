#!/usr/bin/env python3
"""Debate-utility Test 3: debate under near-greedy sampling (applied after the 2026-11-18 sampling fix).

Pre-registered in docs/prereg/2026-11-18-debate-utility.md (addendum). 24-tech subset, 5 runs each of v1 and d3
at provider-default sampling (t003v1, fxctl; settings were never sent before the fix) and at near-greedy
component sampling, temperature 0.03 / top_p 0.0001 (g0v1, g0d3), normalized with per-technology vocabs built
over all four batches (data/greedytest/vocab_{a,b}.json). Metric: per-tech median pairwise Jaccard.

Usage (code repo): uv run --with scipy --with numpy python scripts/debate_greedy_test.py \
    > output/analysis/debate_greedy_test.md
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
from normalize_outputs_global_granularity import make_vocab_key  # noqa: E402

SENTINEL = "__NON_PRIMARY__"
BATCHES = {("v1", "default"): "t003v1_v1v1v1", ("d3", "default"): "fxctl_d3v1v1",
           ("v1", "greedy"): "g0v1_v1v1v1", ("d3", "greedy"): "g0d3_d3v1v1"}


def load(stem, vocab):
    raw, canon = defaultdict(list), defaultdict(list)
    for path in sorted(glob.glob(f"output/raw/stdns_output_{stem}_*.csv")):
        r_run, c_run = defaultdict(set), defaultdict(set)
        with open(path) as fh:
            for r in csv.DictReader(fh):
                t, c = (r.get("technology") or "").strip(), (r.get("component") or "").strip()
                if not t or not c:
                    continue
                r_run[t].add(c)
                k = vocab.get(make_vocab_key(c, t, "technology"), c)
                if k != SENTINEL:
                    c_run[t].add(k)
        for t in r_run:
            raw[t].append(r_run[t])
            canon[t].append(c_run[t])
    return raw, canon


def mj(sets):
    js = [len(a & b) / len(a | b) for a, b in combinations(sets, 2) if a | b]
    return median(js) if js else None


def boot(x, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.asarray(x)
    return np.percentile(np.median(rng.choice(x, size=(n, len(x)), replace=True), axis=1), [2.5, 97.5])


def wil(x):
    x = [v for v in x if v != 0]
    return stats.wilcoxon(x).pvalue if len(x) >= 5 else float("nan")


def main():
    print("# Debate-utility Test 3: debate under near-greedy sampling\n")
    print("Pre-registration: docs/prereg/2026-11-18-debate-utility.md. Values are medians over technologies; "
          "CIs bootstrap the median over technologies; p = paired Wilcoxon.\n")
    for rep in ["a", "b"]:
        with open(f"data/greedytest/vocab_{rep}.json") as f:
            vocab = json.load(f)["mappings"]
        stab = {lvl: {} for lvl in ["canonical", "raw"]}
        for key, stem in BATCHES.items():
            raw, canon = load(stem, vocab)
            stab["canonical"][key] = {t: mj(v) for t, v in canon.items() if len(v) == 5}
            stab["raw"][key] = {t: mj(v) for t, v in raw.items() if len(v) == 5}
        print(f"\n## Normalization pass {rep}\n")
        print("| level | v1 @default | d3 @default | v1 @greedy | d3 @greedy | Δ@default (p) | Δ@greedy (p) | interaction [95% CI] |")
        print("|---|---|---|---|---|---|---|---|")
        for lvl, s in stab.items():
            ts = sorted(set.intersection(*(set(d) for d in s.values())))
            g = lambda k: [s[k][t] for t in ts]
            d03 = [b - a for a, b in zip(g(("v1", "default")), g(("d3", "default")))]
            d07 = [b - a for a, b in zip(g(("v1", "greedy")), g(("d3", "greedy")))]
            inter = [y - x for x, y in zip(d03, d07)]
            lo, hi = boot(inter)
            med = lambda k: f"{median(g(k)):.3f}"
            print(f"| {lvl} (n={len(ts)}) | {med(('v1','default'))} | {med(('d3','default'))} | {med(('v1','greedy'))} | "
                  f"{med(('d3','greedy'))} | {median(d03):+.3f} ({wil(d03):.2g}) | {median(d07):+.3f} ({wil(d07):.2g}) | "
                  f"{median(inter):+.3f} [{lo:+.3f}, {hi:+.3f}] (p={wil(inter):.2g}) |")
            if lvl == "canonical":
                v1t = [b - a for a, b in zip(g(("v1", "default")), g(("v1", "greedy")))]
                print(f"\nSecondary: v1 stability change default → greedy (canonical): {median(v1t):+.3f} "
                      f"(p={wil(v1t):.2g}); mean Δ@greedy = {np.mean(d07):+.3f}, mean interaction = "
                      f"{np.mean(inter):+.3f}\n")


if __name__ == "__main__":
    main()
