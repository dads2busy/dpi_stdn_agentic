#!/usr/bin/env python3
"""Debate-utility Test 4: judge invalid rate under per-technology normalization.

Pre-registered in docs/prereg/2026-11-18-debate-utility.md (addendum). Uses judge verdicts cached by
scripts/judge_stage1_components_from_normalized_outputs.py over output/normalized_techscope_a
(output/analysis/judge_cache_techscope_a.jsonl). Per technology and configuration: deduped-canonical invalid
rate = share of the canonicals appearing in any of its 5 runs that the judge labels not plausible.
Δ = debate − v1 per domain, paired over technologies; Wilcoxon.

Usage (code repo): uv run --with scipy --with numpy python scripts/debate_invalid_rate_techscope.py \
    > output/analysis/debate_invalid_rate_techscope.md
"""
import csv
import glob
import json
import re
from collections import defaultdict
from statistics import mean, median

from scipy import stats

NORM = "output/normalized_techscope_a"
CACHE = "output/analysis/judge_cache_techscope_a.jsonl"
COMPARISONS = [
    ("post-fix d3 (primary)", "microelectronics", "fxmicro_v1v1v1", "fxmicro_d3v1v1"),
    ("post-fix d3 (primary)", "biotech", "fxbiotech_v1v1v1", "fxbiotech_d3v1v1"),
    ("post-fix d3 (primary)", "pharma", "fxpharma_v1v1v1", "fxpharma_d3v1v1"),
    ("submitted d3", "microelectronics", "v1v1v1_20260414_105", "d3v1v1_20260414_14"),
    ("submitted d3", "biotech", "biotech_v1v1v1", "biotech_d3v1v1"),
    ("submitted d3", "pharma", "pharma_v1v1v1", "pharma_d3v1v1"),
    ("d5", "microelectronics", "v1v1v1_20260414_105", "d5v1v1_20260414_"),
    ("d5", "biotech", "biotech_v1v1v1", "biotech_d5v1v1"),
    ("d5", "pharma", "pharma_v1v1v1", "pharma_d5v1v1"),
]


def ws(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def load_cache():
    verdict = {}
    with open(CACHE) as f:
        for line in f:
            if line.strip():
                o = json.loads(line)
                verdict[(ws(o["technology"]), ws(o["component"]))] = bool(o["plausible"])
    return verdict


def canon_union(stem):
    out = defaultdict(set)
    for path in sorted(glob.glob(f"{NORM}/stdns_output_{stem}*.csv")):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                t, c = ws(r.get("technology")), ws(r.get("component"))
                if t and c:
                    out[t].add(c)
    return out


def rates(stem, verdict):
    out, missing = {}, 0
    for t, comps in canon_union(stem).items():
        judged = [verdict[(t, c)] for c in comps if (t, c) in verdict]
        missing += len(comps) - len(judged)
        if judged:
            out[t] = sum(not v for v in judged) / len(judged)
    return out, missing


def main():
    verdict = load_cache()
    n_invalid = sum(not v for v in verdict.values())
    print("# Debate-utility Test 4: judge invalid rate under per-technology normalization\n")
    print(f"Judge cache: {len(verdict)} (technology, canonical) verdicts, {n_invalid} labelled not plausible "
          f"({n_invalid / len(verdict):.1%}).\n")
    print("| comparison | domain | n techs | mean invalid v1 | mean invalid debate | median Δ | mean Δ | Wilcoxon p | unjudged |")
    print("|---|---|---|---|---|---|---|---|---|")
    for label, dom, s1, s2 in COMPARISONS:
        r1, m1 = rates(s1, verdict)
        r2, m2 = rates(s2, verdict)
        ts = sorted(set(r1) & set(r2))
        d = [r2[t] - r1[t] for t in ts]
        nz = [x for x in d if x != 0]
        p = stats.wilcoxon(nz).pvalue if len(nz) >= 5 else float("nan")
        print(f"| {label} | {dom} | {len(ts)} | {mean(r1[t] for t in ts):.3f} | {mean(r2[t] for t in ts):.3f} | "
              f"{median(d):+.3f} | {mean(d):+.3f} | {p:.2g} | {m1}/{m2} |")


if __name__ == "__main__":
    main()
