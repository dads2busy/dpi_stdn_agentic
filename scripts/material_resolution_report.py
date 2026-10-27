#!/usr/bin/env python3
"""Before/after material-level shares for the resolution post-pass (Reviewer 2).

Counts material nodes, i.e. distinct (technology, component, material) per run file, so
country rows do not inflate the counts. Before = level of the material as extracted;
after = level of each resolved constituent.

Usage: uv run python scripts/material_resolution_report.py > output/analysis/material_resolution_report.md
"""
import csv
import glob
from collections import Counter

LEVELS = ["element", "compound", "generic", "not_material", "unmapped"]
BLOCKS = [
    ("Microelectronics d5v1v1 (submitted, 5 runs)", "stdns_output_d5v1v1_2026*.csv"),
    ("Biotechnology d5v1v1 (revision, 5 runs)", "stdns_output_biotech_d5v1v1_*.csv"),
    ("Pharmaceuticals d5v1v1 (revision, 5 runs)", "stdns_output_pharma_d5v1v1_*.csv"),
]


def source_levels(map_path="data/material_resolution_map.csv"):
    return {r["source"].strip().lower(): r["level"] for r in csv.DictReader(open(map_path))}


def count_block(pattern, src_level):
    before, after, generic_sources = Counter(), Counter(), Counter()
    for f in sorted(glob.glob(f"output/resolved/{pattern}")):
        nodes, constituents = set(), set()
        for r in csv.DictReader(open(f)):
            node = (r["technology"], r["component"], r["material"])
            nodes.add(node)
            constituents.add(node + (r["material_resolved"], r["material_level"]))
        for t, c, m in nodes:
            lvl = src_level.get(m.strip().lower(), "unmapped")
            before[lvl] += 1
            if lvl == "generic":
                generic_sources[m] += 1
        for *_, lvl in constituents:
            after[lvl] += 1
    return before, after, generic_sources


def table(before, after):
    tb, ta = sum(before.values()), sum(after.values())
    lines = ["| level | before | after |", "|---|---|---|"]
    for k in LEVELS:
        lines.append(f"| {k} | {before[k]} ({before[k] / tb:.1%}) | {after[k]} ({after[k] / ta:.1%}) |")
    lines.append(f"| **element + compound** | {(before['element'] + before['compound']) / tb:.1%} "
                 f"| {(after['element'] + after['compound']) / ta:.1%} |")
    return "\n".join(lines)


def main():
    src_level = source_levels()
    print("# Material resolution report\n")
    print("Counts are material nodes: distinct (technology, component, material) per run, summed over runs. "
          "*Before* classifies the material as extracted; *after* classifies each constituent it resolves to "
          "via `data/material_resolution_map.csv`. Generic entries that remain generic after resolution are "
          "petrochemical resins, biologicals, and USGS mineral commodities reported as such.\n")
    for title, pattern in BLOCKS:
        before, after, gens = count_block(pattern, src_level)
        if not before:
            continue
        print(f"## {title}\n")
        print(table(before, after))
        print("\nMost frequent generic materials before resolution: "
              + ", ".join(f"{m} ({n})" for m, n in gens.most_common(8)) + "\n")


if __name__ == "__main__":
    main()
