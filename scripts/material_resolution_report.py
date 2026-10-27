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


def node_shares(resolved_rows, src_level):
    """Share of material nodes (technology, component, material) at element/compound level, before
    resolution (the material as extracted) and after (every constituent element/compound)."""
    nodes = {}
    for r in resolved_rows:
        node = (r["technology"], r["component"], r["material"])
        nodes.setdefault(node, set()).add(r["material_level"])
    if not nodes:
        return 0.0, 0.0
    ok = {"element", "compound"}
    before = sum(src_level.get(m.strip().lower(), "unmapped") in ok for _, _, m in nodes)
    after = sum(lv <= ok for lv in nodes.values())
    return before / len(nodes), after / len(nodes)


def count_block(pattern, src_level):
    before, after, generic_sources, sources = Counter(), Counter(), Counter(), Counter()
    shares = []
    for f in sorted(glob.glob(f"output/resolved/{pattern}")):
        nodes, constituents = set(), set()
        rows = list(csv.DictReader(open(f)))
        shares.append(node_shares(rows, src_level))
        for r in rows:
            if r["resolution_provenance"] == "map" and r["material_resolved"]:
                sources[r["country_source"] or "none"] += 1
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
    nb = sum(s[0] for s in shares) / len(shares) if shares else 0.0
    na = sum(s[1] for s in shares) / len(shares) if shares else 0.0
    return before, after, generic_sources, sources, nb, na


def table(before, after):
    tb, ta = sum(before.values()), sum(after.values())
    lines = [f"| level | before (material nodes, n={tb}) | after (constituents, n={ta}) |", "|---|---|---|"]
    for k in LEVELS:
        lines.append(f"| {k} | {before[k]} ({before[k] / tb:.1%}) | {after[k]} ({after[k] / ta:.1%}) |")
    return "\n".join(lines)


def main():
    src_level = source_levels()
    print("# Material resolution report\n")
    print("Counts are material nodes: distinct (technology, component, material) per run, summed over runs. "
          "*Before* classifies the material as extracted; *after* classifies each constituent it resolves to "
          "via `data/material_resolution_map.csv`. Generic entries that remain generic after resolution are "
          "petrochemical resins, biologicals, and USGS commodities reported as such (including steel).\n\n"
          "The headline is the share of material nodes that are element/compound-level: before = the material "
          "as extracted, after = every constituent it resolves to is element/compound-level (mean over runs). "
          "The level table below counts constituents after resolution, so its totals differ.\n")
    for title, pattern in BLOCKS:
        before, after, gens, sources, nb, na = count_block(pattern, src_level)
        if not before:
            continue
        print(f"## {title}\n")
        print(f"**Element/compound-level material nodes: {nb:.1%} before, {na:.1%} after.**\n")
        print(table(before, after))
        tot = sum(sources.values())
        print("\nCountry shares for resolved constituents (rows): "
              + ", ".join(f"{k} {v} ({v / tot:.1%})" for k, v in sources.most_common()) + "\n")
        print("\nMost frequent generic materials before resolution: "
              + ", ".join(f"{m} ({n})" for m, n in gens.most_common(8)) + "\n")


if __name__ == "__main__":
    main()
