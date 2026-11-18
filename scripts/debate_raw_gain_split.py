#!/usr/bin/env python3
"""How much of debate's raw-agreement gain survives normalization?

Debate (d3, d5) raises run-to-run agreement of raw component names in every domain, but lowers it after
normalization. This script splits the paired debate effect Δ = config - v1 (per technology, median pairwise
Jaccard over runs) across four levels of the same raw rows, so each step isolates one normalization operation:

  L0 exact      raw `component` strings as emitted
  L1 key        the normalizer's _norm_key (case, whitespace, dashes, edge punctuation)
  L2 primary    L1 with names the normalizer maps to the non-primary sentinel removed (no merging yet)
  L3 canonical  L2 names mapped to their canonical (the per-technology vocab, i.e. the normalized output)

Δ(L1)-Δ(L0) = gain absorbed by string cleanup; Δ(L2)-Δ(L1) = by dropping non-primary items;
Δ(L3)-Δ(L2) = by synonym merging. If Δ(L3) <= 0 < Δ(L0), the raw gain does not survive normalization.

Also reports naming consistency: for a pair of runs, among canonicals both runs contain, the share for which
the two runs used at least one identical L1 name. High in d3 but not v1 => debate's raw gain is lexical.

Mappings come from data/component_canonical_vocab_techscope_{a,b}.json (two independent per-technology
normalization passes, 2026-11-03). L3 reconstructed here is checked against output/normalized_techscope_*.

Usage (from the code repo):
  uv run --with scipy --with numpy python scripts/debate_raw_gain_split.py > output/analysis/debate_raw_gain_split.md
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
LEVELS = ["L0 exact", "L1 key", "L2 primary", "L3 canonical"]
PASSES = {"A": "techscope_a", "B": "techscope_b"}

# (label, domain, baseline glob stem, debate glob stem) under output/raw/
COMPARISONS = [
    ("submitted d3", "microelectronics", "stdns_output_v1v1v1_2026041*", "stdns_output_d3v1v1_2026041*"),
    ("submitted d3", "biotech", "stdns_output_biotech_v1v1v1_*", "stdns_output_biotech_d3v1v1_*"),
    ("submitted d3", "pharma", "stdns_output_pharma_v1v1v1_*", "stdns_output_pharma_d3v1v1_*"),
    ("post-fix d3", "microelectronics", "stdns_output_fxmicro_v1v1v1_*", "stdns_output_fxmicro_d3v1v1_*"),
    ("post-fix d3", "biotech", "stdns_output_fxbiotech_v1v1v1_*", "stdns_output_fxbiotech_d3v1v1_*"),
    ("post-fix d3", "pharma", "stdns_output_fxpharma_v1v1v1_*", "stdns_output_fxpharma_d3v1v1_*"),
    ("d5", "microelectronics", "stdns_output_v1v1v1_2026041*", "stdns_output_d5v1v1_2026041*"),
    ("d5", "biotech", "stdns_output_biotech_v1v1v1_*", "stdns_output_biotech_d5v1v1_*"),
    ("d5", "pharma", "stdns_output_pharma_v1v1v1_*", "stdns_output_pharma_d5v1v1_*"),
]


def load_vocab(tag):
    with open(f"data/component_canonical_vocab_{tag}.json") as f:
        return json.load(f)["mappings"]


def run_levels(path, vocab):
    """tech -> {level: set of names} for one run file, plus tech -> {canonical: set of L1 names}."""
    levels = defaultdict(lambda: {lv: set() for lv in LEVELS})
    names_by_canon = defaultdict(lambda: defaultdict(set))
    with open(path) as fh:
        for row in csv.DictReader(fh):
            tech, comp = (row.get("technology") or "").strip(), (row.get("component") or "").strip()
            if not tech or not comp:
                continue
            key = _norm_key(comp)
            canon = vocab.get(make_vocab_key(comp, tech, "technology"), comp)
            lv = levels[tech]
            lv["L0 exact"].add(comp)
            lv["L1 key"].add(key)
            if canon != SENTINEL:
                lv["L2 primary"].add(key)
                lv["L3 canonical"].add(canon)
                names_by_canon[tech][canon].add(key)
    return levels, names_by_canon


def load_config(stem, vocab):
    """tech -> list over runs of (levels dict, names_by_canon dict)."""
    out = defaultdict(list)
    for path in sorted(glob.glob(f"output/raw/{stem}.csv")):
        levels, nbc = run_levels(path, vocab)
        for tech in levels:
            out[tech].append((levels[tech], nbc[tech]))
    return out


def jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else None


def tech_metrics(runs):
    """Median pairwise Jaccard at each level, and median naming consistency, for one tech/config."""
    if len(runs) < 2:
        return None
    per_level = {lv: [] for lv in LEVELS}
    consistency = []
    for (la, na), (lb, nb) in combinations(runs, 2):
        for lv in LEVELS:
            j = jaccard(la[lv], lb[lv])
            if j is not None:
                per_level[lv].append(j)
        shared = set(na) & set(nb)
        if shared:
            consistency.append(sum(bool(na[c] & nb[c]) for c in shared) / len(shared))
    if any(not v for v in per_level.values()):
        return None
    m = {lv: median(v) for lv, v in per_level.items()}
    m["consistency"] = median(consistency) if consistency else None
    return m


def boot_ci(x, n=5000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.asarray(x)
    meds = np.median(rng.choice(x, size=(n, len(x)), replace=True), axis=1)
    return np.percentile(meds, [2.5, 97.5])


def wilcoxon_p(x):
    x = [v for v in x if v != 0]
    return stats.wilcoxon(x).pvalue if len(x) >= 5 else float("nan")


def check_against_normalized(tag, vocab):
    """L3 reconstruction must reproduce the normalized files' component sets."""
    mism = total = 0
    for path in sorted(glob.glob(f"output/normalized_{tag}/stdns_output_*.csv")):
        raw = path.replace(f"normalized_{tag}", "raw")
        if not os.path.exists(raw):
            continue
        levels, _ = run_levels(raw, vocab)
        norm = defaultdict(set)
        with open(path) as fh:
            for row in csv.DictReader(fh):
                if row.get("technology") and row.get("component"):
                    norm[row["technology"].strip()].add(row["component"].strip())
        for tech in set(levels) | set(norm):
            total += 1
            mism += levels[tech]["L3 canonical"] != norm.get(tech, set()) if tech in levels else 1
    return mism, total


def fmt(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.{d}f}" if d == 3 else f"{x:.{d}g}"


def main():
    print("# Debate raw-gain split across normalization steps\n")
    print("Δ = median over paired techs of (debate − v1) per-tech median pairwise Jaccard. "
          "p = Wilcoxon signed-rank on per-tech differences.\n")
    for pname, tag in PASSES.items():
        vocab = load_vocab(tag)
        mism, total = check_against_normalized(tag, vocab)
        print(f"\n## Pass {pname} ({tag})\n")
        print(f"L3 reconstruction check vs output/normalized_{tag}: {mism} of {total} file×tech sets differ.\n")
        cache = {}

        def cfg(stem):
            if stem not in cache:
                cache[stem] = load_config(stem, vocab)
            return cache[stem]

        print("| comparison | domain | n | " + " | ".join(f"Δ {lv}" for lv in LEVELS)
              + " | v1 / debate level at L0 | v1 / debate at L3 | naming consistency v1 / debate |")
        print("|---|---|---|" + "---|" * len(LEVELS) + "---|---|---|")
        for label, domain, base, deb in COMPARISONS:
            b, d = cfg(base), cfg(deb)
            rows = []
            for tech in sorted(set(b) & set(d)):
                mb, md = tech_metrics(b[tech]), tech_metrics(d[tech])
                if mb and md:
                    rows.append((mb, md))
            if not rows:
                continue
            cells = []
            for lv in LEVELS:
                diffs = [md[lv] - mb[lv] for mb, md in rows]
                lo, hi = boot_ci(diffs)
                cells.append(f"{median(diffs):+.3f} [{lo:+.3f}, {hi:+.3f}] p={wilcoxon_p(diffs):.2g}")
            lvl = lambda lv: f"{median(mb[lv] for mb, _ in rows):.3f} / {median(md[lv] for _, md in rows):.3f}"
            cb = [mb["consistency"] for mb, _ in rows if mb["consistency"] is not None]
            cd = [md["consistency"] for _, md in rows if md["consistency"] is not None]
            cons = f"{median(cb):.3f} / {median(cd):.3f}"
            print(f"| {label} | {domain} | {len(rows)} | " + " | ".join(cells)
                  + f" | {lvl('L0 exact')} | {lvl('L3 canonical')} | {cons} |")


if __name__ == "__main__":
    main()
