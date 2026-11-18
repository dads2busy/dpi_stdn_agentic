#!/usr/bin/env python3
"""Debate-utility Test 1: is debate confidence a better uncertainty signal than single-agent confidence?

Pre-registered in docs/prereg/2026-11-18-debate-utility.md. For each configuration, a component's
confidence in a run is scored against whether its canonical recurs (in >= 3 of the 5 runs of that technology
and configuration). Metric: AUC within each technology, averaged over technologies; d3 - v1 per domain with a
bootstrap CI over technologies.

Usage (code repo): uv run --with scipy --with numpy python scripts/debate_confidence_signal.py \
    > output/analysis/debate_confidence_signal.md
"""
import csv
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np
from scipy.stats import rankdata

sys.path.insert(0, os.path.dirname(__file__))
from normalize_outputs_global_granularity import make_vocab_key  # noqa: E402

SENTINEL = "__NON_PRIMARY__"
NRUNS = 5
DATASETS = {
    "post-fix (primary)": {
        "microelectronics": ("fxmicro_v1v1v1", "fxmicro_d3v1v1"),
        "biotech": ("fxbiotech_v1v1v1", "fxbiotech_d3v1v1"),
        "pharma": ("fxpharma_v1v1v1", "fxpharma_d3v1v1"),
    },
    "submitted (replication)": {
        "microelectronics": ("v1v1v1_20260414_105", "d3v1v1_20260414_14"),
        "biotech": ("biotech_v1v1v1", "biotech_d3v1v1"),
        "pharma": ("pharma_v1v1v1", "pharma_d3v1v1"),
    },
    "d5 vs v1, submitted (secondary)": {
        "microelectronics": ("v1v1v1_20260414_105", "d5v1v1_20260414_"),
        "biotech": ("biotech_v1v1v1", "biotech_d5v1v1"),
        "pharma": ("pharma_v1v1v1", "pharma_d5v1v1"),
    },
}
# Submitted micro: the April 60-tech batch only (5 files each); the 19:5x supplement batch covers 3 techs.


def load(stem, vocab):
    """tech -> list (one per run) of {canonical: max confidence}."""
    files = sorted(glob.glob(f"output/raw/stdns_output_{stem}*.csv"))
    per = defaultdict(list)
    for path in files:
        run = defaultdict(dict)
        with open(path) as fh:
            for r in csv.DictReader(fh):
                t, c = (r.get("technology") or "").strip(), (r.get("component") or "").strip()
                if not t or not c:
                    continue
                canon = vocab.get(make_vocab_key(c, t, "technology"), c)
                if canon == SENTINEL:
                    continue
                try:
                    conf = float(r.get("component_confidence") or "nan")
                except ValueError:
                    continue
                if np.isnan(conf):
                    continue
                run[t][canon] = max(conf, run[t].get(canon, -1.0))
        for t, d in run.items():
            per[t].append(d)
    return per, len(files)


def auc(scores, labels):
    labels = np.asarray(labels, bool)
    npos, nneg = labels.sum(), (~labels).sum()
    if npos == 0 or nneg == 0:
        return None
    r = rankdata(scores)
    return (r[labels].sum() - npos * (npos + 1) / 2) / (npos * nneg)


def tech_aucs(per, min_runs):
    out = {}
    for t, runs in per.items():
        if len(runs) != NRUNS:
            continue
        counts = defaultdict(int)
        for d in runs:
            for c in d:
                counts[c] += 1
        s, y = [], []
        for d in runs:
            for c, conf in d.items():
                s.append(conf)
                y.append(counts[c] >= min_runs)
        a = auc(s, y)
        if a is not None:
            out[t] = a
    return out


def boot(diffs, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.asarray(diffs)
    m = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return np.percentile(m, [2.5, 97.5])


def main():
    print("# Debate-utility Test 1: confidence as an uncertainty signal\n")
    print("Pre-registration: docs/prereg/2026-11-18-debate-utility.md. AUC of component confidence vs "
          "'canonical recurs in >= k of 5 runs', within technology, averaged. Δ = debate − v1 over technologies "
          "with AUCs in both; 95% bootstrap CI.\n")
    for vtag in ["techscope_a", "techscope_b"]:
        with open(f"data/component_canonical_vocab_{vtag}.json") as f:
            vocab = json.load(f)["mappings"]
        for k, klabel in [(3, "label: >=3 of 5 (primary)"), (5, "label: all 5 (secondary)")]:
            print(f"\n## Vocab {vtag}, {klabel}\n")
            print("| dataset | domain | files v1/debate | n techs | AUC v1 | AUC debate | Δ [95% CI] |")
            print("|---|---|---|---|---|---|---|")
            for dname, doms in DATASETS.items():
                for dom, (s1, s2) in doms.items():
                    p1, n1 = load(s1, vocab)
                    p2, n2 = load(s2, vocab)
                    a1, a2 = tech_aucs(p1, k), tech_aucs(p2, k)
                    ts = sorted(set(a1) & set(a2))
                    if len(ts) < 5:
                        print(f"| {dname} | {dom} | {n1}/{n2} | {len(ts)} | – | – | too few |")
                        continue
                    d = [a2[t] - a1[t] for t in ts]
                    lo, hi = boot(d)
                    print(f"| {dname} | {dom} | {n1}/{n2} | {len(ts)} | {np.mean([a1[t] for t in ts]):.3f} | "
                          f"{np.mean([a2[t] for t in ts]):.3f} | {np.mean(d):+.3f} [{lo:+.3f}, {hi:+.3f}] |")


if __name__ == "__main__":
    main()
