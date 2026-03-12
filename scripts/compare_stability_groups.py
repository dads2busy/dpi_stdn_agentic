#!/usr/bin/env python3
"""
Compare Stage 1 component stability between two groups of runs.

Supports two comparison modes:
1. Same config, split by date (original behavior):
       --group-a d3v1v1 --group-b d3v1v1 --cutoff 20260306
2. Different configs, optionally filtered by date:
       --group-a d3v1v1 --group-b v1v1v1
       --group-a d3v1v1 --group-b v1v1v1 --after 20260308

Usage:
    # Compare d3v1v1 vs v1v1v1 (all files)
    python scripts/compare_stability_groups.py --group-a d3v1v1 --group-b v1v1v1

    # Compare d3v1v1 vs v1v1v1, only files from 20260308 onward
    python scripts/compare_stability_groups.py --group-a d3v1v1 --group-b v1v1v1 --after 20260308

    # Same config split by date (like compare_d3v1v1_groups.py)
    python scripts/compare_stability_groups.py --group-a d3v1v1 --group-b d3v1v1 --cutoff 20260306
"""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Set, Tuple

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_stage1_component_stability_normalized import (
    RunFile,
    StabilityStats,
    _RX_FILENAME,
    compute_stability_for_config,
)


def collect_files(
    normalized_dir: Path,
    config: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
) -> List[RunFile]:
    """Collect run files for a config tag, optionally filtered by date range."""
    results: List[RunFile] = []
    for p in sorted(normalized_dir.glob("stdns_output_*.csv")):
        m = _RX_FILENAME.match(p.name)
        if not m:
            continue
        file_config = m.group("config").lower()
        if file_config != config.lower():
            continue
        ts = m.group("ts")
        date_part = ts[:8]
        if after and date_part < after:
            continue
        if before and date_part >= before:
            continue
        results.append(RunFile(path=p, config=file_config, timestamp=ts))
    return results


def per_tech_stats(
    run_files: List[RunFile], min_runs: int = 2
) -> List[StabilityStats]:
    if not run_files:
        return []
    config = run_files[0].config
    return compute_stability_for_config(config, run_files, min_runs=min_runs)


def print_comparison(
    label_a: str,
    label_b: str,
    stats_a: List[StabilityStats],
    stats_b: List[StabilityStats],
    count_a: int,
    count_b: int,
) -> None:
    by_tech_a = {s.technology: s for s in stats_a}
    by_tech_b = {s.technology: s for s in stats_b}
    all_techs = sorted(set(by_tech_a.keys()) | set(by_tech_b.keys()))

    # Truncate labels for column headers
    col_a = label_a[:12]
    col_b = label_b[:12]

    print()
    print("=" * 90)
    print(f"STAGE 1 COMPONENT STABILITY COMPARISON")
    print("=" * 90)
    print(f"  Group A ({label_a}):  {count_a} files")
    print(f"  Group B ({label_b}):  {count_b} files")
    print()

    hdr = f"{'Technology':<45} {col_a:>12} {col_b:>12} {'Delta':>8}"
    print(hdr)
    print("-" * len(hdr))

    medians_a: List[float] = []
    medians_b: List[float] = []

    for tech in all_techs:
        a = by_tech_a.get(tech)
        b = by_tech_b.get(tech)
        a_med = a.median_jaccard if a and a.median_jaccard is not None else None
        b_med = b.median_jaccard if b and b.median_jaccard is not None else None

        a_str = f"{a_med:.3f}" if a_med is not None else "NA"
        b_str = f"{b_med:.3f}" if b_med is not None else "NA"

        if a_med is not None and b_med is not None:
            delta = b_med - a_med
            d_str = f"{delta:+.3f}"
            medians_a.append(a_med)
            medians_b.append(b_med)
        else:
            d_str = "NA"
            if a_med is not None:
                medians_a.append(a_med)
            if b_med is not None:
                medians_b.append(b_med)

        print(f"{tech:<45} {a_str:>12} {b_str:>12} {d_str:>8}")

    print("-" * len(hdr))

    def fmt(v):
        return f"{v:.3f}" if v is not None else "NA"

    a_macro_med = median(medians_a) if medians_a else None
    a_macro_mean = mean(medians_a) if medians_a else None
    b_macro_med = median(medians_b) if medians_b else None
    b_macro_mean = mean(medians_b) if medians_b else None

    def delta_str(va, vb):
        if va is not None and vb is not None:
            return f"{vb - va:>+8.3f}"
        return f"{'NA':>8}"

    print(f"{'MACRO MEDIAN':<45} {fmt(a_macro_med):>12} {fmt(b_macro_med):>12} {delta_str(a_macro_med, b_macro_med)}")
    print(f"{'MACRO MEAN':<45} {fmt(a_macro_mean):>12} {fmt(b_macro_mean):>12} {delta_str(a_macro_mean, b_macro_mean)}")
    print()

    for label, stats_list in [(label_a, stats_a), (label_b, stats_b)]:
        print(f"\n--- {label} per-technology detail ---")
        for s in stats_list:
            if s.median_jaccard is not None:
                print(
                    f"  {s.technology:<43} "
                    f"med={s.median_jaccard:.3f}  "
                    f"min={s.min_jaccard:.3f}  "
                    f"max={s.max_jaccard:.3f}  "
                    f"runs={s.runs}"
                )
            else:
                print(f"  {s.technology:<43} insufficient runs ({s.runs})")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compare Stage 1 component stability between two groups of runs."
    )
    ap.add_argument("--group-a", required=True, help="Config tag for group A (e.g., d3v1v1)")
    ap.add_argument("--group-b", required=True, help="Config tag for group B (e.g., v1v1v1)")
    ap.add_argument(
        "--cutoff",
        type=str,
        default=None,
        help="Date cutoff (YYYYMMDD) for same-config comparison. "
             "Group A = before cutoff, Group B = on/after cutoff.",
    )
    ap.add_argument(
        "--after",
        type=str,
        default=None,
        help="Only include files on/after this date (YYYYMMDD). Applies to both groups.",
    )
    ap.add_argument(
        "--before",
        type=str,
        default=None,
        help="Only include files before this date (YYYYMMDD). Applies to both groups.",
    )
    ap.add_argument(
        "--normalized-dir",
        type=str,
        default="output/normalized",
        help="Directory containing normalized CSV outputs.",
    )
    ap.add_argument("--min-runs", type=int, default=2, help="Minimum runs per technology per group.")
    args = ap.parse_args()

    normalized_dir = Path(args.normalized_dir)
    if not normalized_dir.exists():
        raise SystemExit(f"Normalized directory not found: {normalized_dir}")

    if args.group_a == args.group_b and args.cutoff:
        # Same config, split by date
        files_before = collect_files(normalized_dir, args.group_a, after=args.after, before=args.cutoff)
        files_after = collect_files(normalized_dir, args.group_b, after=args.cutoff, before=args.before)
        label_a = f"{args.group_a} (<{args.cutoff})"
        label_b = f"{args.group_b} (>={args.cutoff})"
        files_a, files_b = files_before, files_after
    else:
        # Different configs
        files_a = collect_files(normalized_dir, args.group_a, after=args.after, before=args.before)
        files_b = collect_files(normalized_dir, args.group_b, after=args.after, before=args.before)
        label_a = args.group_a
        label_b = args.group_b

    if not files_a:
        raise SystemExit(f"No files found for group A ({args.group_a})")
    if not files_b:
        raise SystemExit(f"No files found for group B ({args.group_b})")

    print(f"Group A ({label_a}): {len(files_a)} files")
    print(f"Group B ({label_b}): {len(files_b)} files")

    stats_a = per_tech_stats(files_a, min_runs=args.min_runs)
    stats_b = per_tech_stats(files_b, min_runs=args.min_runs)

    print_comparison(label_a, label_b, stats_a, stats_b, len(files_a), len(files_b))


if __name__ == "__main__":
    main()
