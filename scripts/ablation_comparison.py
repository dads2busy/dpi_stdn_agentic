#!/usr/bin/env python3
"""Produce a markdown comparison table showing how each pipeline layer
contributes to output quality.

Layers:
  1. Naive raw
  2. Naive + normalization
  3. Structured raw (v1v1v1)
  4. Structured + normalization (v1v1v1)
  5. Structured + norm + debate (d3v1v1)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Markdown table parser
# ---------------------------------------------------------------------------


def _parse_md_table(text: str) -> list[dict[str, str]]:
    """Return rows from the first markdown table found in *text*."""
    lines = text.strip().splitlines()
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header is not None:
                # Table ended
                break
            continue
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if header is None:
            header = cells
            continue
        # skip separator row
        if all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _find_table_after(text: str, heading_pattern: str) -> list[dict[str, str]]:
    """Find the first markdown table after a heading matching *heading_pattern*."""
    match = re.search(heading_pattern, text, re.IGNORECASE)
    if not match:
        return _parse_md_table(text)
    return _parse_md_table(text[match.start() :])


# ---------------------------------------------------------------------------
# Layer data loaders
# ---------------------------------------------------------------------------


def _load_naive(path: Path) -> dict:
    """Extract median stability and median union component count from a naive
    baseline markdown file."""
    if not path.exists():
        return {}
    text = path.read_text()
    rows = _find_table_after(text, r"## Extraction Summary")
    if not rows:
        return {}
    stabilities = []
    unions = []
    for r in rows:
        jac = r.get("Stability (Jaccard)")
        union = r.get("Union")
        if jac is not None:
            try:
                stabilities.append(float(jac))
            except ValueError:
                pass
        if union is not None:
            try:
                unions.append(float(union))
            except ValueError:
                pass
    result: dict = {}
    if stabilities:
        result["stability"] = statistics.median(stabilities)
    if unions:
        result["components"] = statistics.median(unions)
    return result


def _load_structured_raw_stability(path: Path) -> float | None:
    """Load median Jaccard for v1v1v1 from the raw stability JSON."""
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    # The JSON has macro_by_agent_count: [{agent_count, macro_median_jaccard, ...}]
    for entry in data.get("macro_by_agent_count", []):
        if entry.get("agent_count") == 1:
            return entry.get("macro_median_jaccard")
    return None


def _load_structured_raw_invalid(path: Path) -> float | None:
    """Load invalid_rate_median for v1v1v1 from judge markdown."""
    if not path.exists():
        return None
    text = path.read_text()
    rows = _find_table_after(text, r"variability summary")
    for r in rows:
        if r.get("config", "").strip() == "v1v1v1":
            val = r.get("invalid_rate_median")
            if val is not None:
                return float(val)
    return None


def _load_sweet_spot_csv(path: Path) -> dict[int, dict]:
    """Load micro_sweet_spot_by_n.csv and return {N: row_dict}."""
    if not path.exists():
        return {}
    result = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                n = int(row["n"])
            except (KeyError, ValueError):
                continue
            result[n] = row
    return result


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt(val, decimals: int = 3) -> str:
    if val is None:
        return "\u2014"
    return f"{val:.{decimals}f}"


def _fmt_delta(val) -> str:
    if val is None:
        return "\u2014"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.3f}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Produce ablation comparison table across pipeline layers."
    )
    parser.add_argument(
        "--naive-raw",
        type=Path,
        default=Path("output/analysis/naive_baseline_raw.md"),
        help="Path to naive raw baseline markdown.",
    )
    parser.add_argument(
        "--naive-normalized",
        type=Path,
        default=Path("output/analysis/naive_baseline_normalized.md"),
        help="Path to naive normalized baseline markdown.",
    )
    parser.add_argument(
        "--raw-stability-json",
        type=Path,
        default=Path("output/analysis/ablation_raw_v1v1v1_stability.json"),
        help="Path to structured raw stability JSON.",
    )
    parser.add_argument(
        "--raw-judge-md",
        type=Path,
        default=Path("output/analysis/ablation_raw_v1v1v1_judge.md"),
        help="Path to structured raw judge markdown.",
    )
    parser.add_argument(
        "--sweet-spot-csv",
        type=Path,
        default=Path("output/analysis/micro_sweet_spot_by_n.csv"),
        help="Path to sweet-spot-by-N CSV (layers 4-5).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/analysis/ablation_comparison.md"),
        help="Output markdown file.",
    )
    args = parser.parse_args()

    # -- Load data ----------------------------------------------------------
    naive_raw = _load_naive(args.naive_raw)
    naive_norm = _load_naive(args.naive_normalized)
    raw_stability = _load_structured_raw_stability(args.raw_stability_json)
    raw_invalid = _load_structured_raw_invalid(args.raw_judge_md)
    sweet = _load_sweet_spot_csv(args.sweet_spot_csv)

    # Extract layer 4 (N=1) and layer 5 (N=3) from sweet-spot CSV
    row_n1 = sweet.get(1, {})
    row_n3 = sweet.get(3, {})

    def _csv_float(row: dict, key: str) -> float | None:
        val = row.get(key)
        if val is None or val == "":
            return None
        return float(val)

    layers = [
        {
            "name": "Naive raw",
            "stability": naive_raw.get("stability"),
            "invalid": None,
            "components": naive_raw.get("components"),
        },
        {
            "name": "Naive + normalization",
            "stability": naive_norm.get("stability"),
            "invalid": None,
            "components": naive_norm.get("components"),
        },
        {
            "name": "Structured raw (v1v1v1)",
            "stability": raw_stability,
            "invalid": raw_invalid,
            "components": None,
        },
        {
            "name": "Structured + normalization (v1v1v1)",
            "stability": _csv_float(row_n1, "stability_median"),
            "invalid": _csv_float(row_n1, "not_plausible_occ_median"),
            "components": _csv_float(row_n1, "produced_components_median"),
        },
        {
            "name": "Structured + norm + debate (d3v1v1)",
            "stability": _csv_float(row_n3, "stability_median"),
            "invalid": _csv_float(row_n3, "not_plausible_occ_median"),
            "components": _csv_float(row_n3, "produced_components_median"),
        },
    ]

    # -- Build markdown -----------------------------------------------------
    lines: list[str] = []
    lines.append("# Ablation Comparison: Pipeline Layer Contributions")
    lines.append("")
    lines.append(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- **Naive raw**: `{args.naive_raw}`")
    lines.append(f"- **Naive normalized**: `{args.naive_normalized}`")
    lines.append(f"- **Raw stability JSON**: `{args.raw_stability_json}`")
    lines.append(f"- **Raw judge MD**: `{args.raw_judge_md}`")
    lines.append(f"- **Sweet-spot CSV**: `{args.sweet_spot_csv}`")
    lines.append("")

    # Missing-file warnings
    missing = []
    for label, path in [
        ("naive raw", args.naive_raw),
        ("naive normalized", args.naive_normalized),
        ("raw stability JSON", args.raw_stability_json),
        ("raw judge MD", args.raw_judge_md),
        ("sweet-spot CSV", args.sweet_spot_csv),
    ]:
        if not path.exists():
            missing.append(f"  - `{path}` ({label})")
    if missing:
        lines.append("> **Warning**: the following source files were not found:")
        for m in missing:
            lines.append(f">{m}")
        lines.append("")

    # -- Layer table --------------------------------------------------------
    lines.append("## Layer comparison")
    lines.append("")
    lines.append(
        "| Layer | Stability (median Jaccard) | Invalid rate (median) | Components (median) |"
    )
    lines.append("| --- | --- | --- | --- |")
    for layer in layers:
        lines.append(
            f"| {layer['name']} "
            f"| {_fmt(layer['stability'])} "
            f"| {_fmt(layer['invalid'])} "
            f"| {_fmt(layer['components'], 1)} |"
        )
    lines.append("")

    # -- Marginal contributions ---------------------------------------------
    def _delta(a, b):
        if a is None or b is None:
            return None
        return b - a

    transitions = [
        {
            "name": "Normalization (1\u21922)",
            "d_stab": _delta(layers[0]["stability"], layers[1]["stability"]),
            "d_inv": _delta(layers[0]["invalid"], layers[1]["invalid"]),
        },
        {
            "name": "Structured extraction (2\u21924)",
            "d_stab": _delta(layers[1]["stability"], layers[3]["stability"]),
            "d_inv": _delta(layers[1]["invalid"], layers[3]["invalid"]),
        },
        {
            "name": "Normalization on structured (3\u21924)",
            "d_stab": _delta(layers[2]["stability"], layers[3]["stability"]),
            "d_inv": _delta(layers[2]["invalid"], layers[3]["invalid"]),
        },
        {
            "name": "Debate (4\u21925)",
            "d_stab": _delta(layers[3]["stability"], layers[4]["stability"]),
            "d_inv": _delta(layers[3]["invalid"], layers[4]["invalid"]),
        },
    ]

    lines.append("## Marginal contributions")
    lines.append("")
    lines.append("| Transition | \u0394 Stability | \u0394 Invalid rate |")
    lines.append("| --- | --- | --- |")
    for t in transitions:
        lines.append(
            f"| {t['name']} | {_fmt_delta(t['d_stab'])} | {_fmt_delta(t['d_inv'])} |"
        )
    lines.append("")

    report = "\n".join(lines)

    # -- Write and print ----------------------------------------------------
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(report)
    print(f"\nWritten to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
