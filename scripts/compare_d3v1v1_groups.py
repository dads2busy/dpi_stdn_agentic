#!/usr/bin/env python3
"""
Compare Stage 1 component stability between two groups of d3v1v1 runs.

Splits d3v1v1 normalized outputs into "baseline" (before a cutoff date) and
"experiment" (on or after the cutoff date), then runs the stability analysis
on each group independently and prints a side-by-side comparison.

Usage:
    python scripts/compare_d3v1v1_groups.py --cutoff 20260306

    # Custom normalized dir
    python scripts/compare_d3v1v1_groups.py --cutoff 20260306 --normalized-dir output/normalized
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Set, Tuple

# Reuse the core logic from the existing analysis script
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_stage1_component_stability_normalized import (
    RunFile,
    StabilityStats,
    _RX_FILENAME,
    compute_stability_for_config,
    load_component_sets_from_csv,
    pairwise_jaccards,
)


def split_files_by_cutoff(
    normalized_dir: Path, config: str, cutoff: str
) -> Tuple[List[RunFile], List[RunFile]]:
    """Split run files into baseline (before cutoff) and experiment (>= cutoff)."""
    baseline: List[RunFile] = []
    experiment: List[RunFile] = []

    for p in sorted(normalized_dir.glob("stdns_output_*.csv")):
        m = _RX_FILENAME.match(p.name)
        if not m:
            continue
        file_config = m.group("config").lower()
        if file_config != config.lower():
            continue
        ts = m.group("ts")  # e.g. 20260222_105102
        date_part = ts[:8]  # e.g. 20260222
        rf = RunFile(path=p, config=file_config, timestamp=ts)
        if date_part < cutoff:
            baseline.append(rf)
        else:
            experiment.append(rf)

    return baseline, experiment


def per_tech_stats(
    run_files: List[RunFile], min_runs: int = 2
) -> List[StabilityStats]:
    """Compute stability stats, reusing existing function."""
    if not run_files:
        return []
    config = run_files[0].config
    return compute_stability_for_config(config, run_files, min_runs=min_runs)


def print_comparison(
    baseline_stats: List[StabilityStats],
    experiment_stats: List[StabilityStats],
    baseline_count: int,
    experiment_count: int,
) -> None:
    # Index by technology
    base_by_tech = {s.technology: s for s in baseline_stats}
    exp_by_tech = {s.technology: s for s in experiment_stats}
    all_techs = sorted(set(base_by_tech.keys()) | set(exp_by_tech.keys()))

    print()
    print("=" * 90)
    print("STAGE 1 COMPONENT STABILITY COMPARISON: d3v1v1")
    print("=" * 90)
    print(f"  Baseline runs:    {baseline_count}")
    print(f"  Experiment runs:  {experiment_count}")
    print()

    # Per-technology table
    hdr = f"{'Technology':<45} {'Base Med':>9} {'Exp Med':>9} {'Delta':>8}"
    print(hdr)
    print("-" * len(hdr))

    base_medians: List[float] = []
    exp_medians: List[float] = []

    for tech in all_techs:
        b = base_by_tech.get(tech)
        e = exp_by_tech.get(tech)
        b_med = b.median_jaccard if b and b.median_jaccard is not None else None
        e_med = e.median_jaccard if e and e.median_jaccard is not None else None

        b_str = f"{b_med:.3f}" if b_med is not None else "NA"
        e_str = f"{e_med:.3f}" if e_med is not None else "NA"

        if b_med is not None and e_med is not None:
            delta = e_med - b_med
            d_str = f"{delta:+.3f}"
            base_medians.append(b_med)
            exp_medians.append(e_med)
        else:
            d_str = "NA"
            if b_med is not None:
                base_medians.append(b_med)
            if e_med is not None:
                exp_medians.append(e_med)

        print(f"{tech:<45} {b_str:>9} {e_str:>9} {d_str:>8}")

    print("-" * len(hdr))

    # Macro summary
    if base_medians:
        b_macro_med = median(base_medians)
        b_macro_mean = mean(base_medians)
    else:
        b_macro_med = b_macro_mean = None

    if exp_medians:
        e_macro_med = median(exp_medians)
        e_macro_mean = mean(exp_medians)
    else:
        e_macro_med = e_macro_mean = None

    def fmt(v):
        return f"{v:.3f}" if v is not None else "NA"

    print(f"{'MACRO MEDIAN':<45} {fmt(b_macro_med):>9} {fmt(e_macro_med):>9}", end="")
    if b_macro_med is not None and e_macro_med is not None:
        print(f" {e_macro_med - b_macro_med:>+8.3f}")
    else:
        print(f" {'NA':>8}")

    print(f"{'MACRO MEAN':<45} {fmt(b_macro_mean):>9} {fmt(e_macro_mean):>9}", end="")
    if b_macro_mean is not None and e_macro_mean is not None:
        print(f" {e_macro_mean - b_macro_mean:>+8.3f}")
    else:
        print(f" {'NA':>8}")

    print()

    # Component set details per group
    for label, run_files_list, stats_list in [
        ("BASELINE", "baseline", baseline_stats),
        ("EXPERIMENT", "experiment", experiment_stats),
    ]:
        print(f"\n--- {label} per-technology component sets ---")
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
        description="Compare d3v1v1 component stability between baseline and experiment groups."
    )
    ap.add_argument(
        "--cutoff",
        type=str,
        required=True,
        help="Date cutoff (YYYYMMDD). Files before this date are baseline, on/after are experiment.",
    )
    ap.add_argument(
        "--normalized-dir",
        type=str,
        default="output/normalized",
        help="Directory containing normalized CSV outputs.",
    )
    ap.add_argument(
        "--config",
        type=str,
        default="d3v1v1",
        help="Config tag to filter on (default: d3v1v1).",
    )
    ap.add_argument(
        "--min-runs",
        type=int,
        default=2,
        help="Minimum runs required per technology per group.",
    )
    args = ap.parse_args()

    normalized_dir = Path(args.normalized_dir)
    if not normalized_dir.exists():
        raise SystemExit(f"Normalized directory not found: {normalized_dir}")

    baseline, experiment = split_files_by_cutoff(normalized_dir, args.config, args.cutoff)

    if not baseline:
        raise SystemExit(f"No baseline files found (before {args.cutoff})")
    if not experiment:
        raise SystemExit(f"No experiment files found (on/after {args.cutoff})")

    print(f"Found {len(baseline)} baseline files, {len(experiment)} experiment files")

    baseline_stats = per_tech_stats(baseline, min_runs=args.min_runs)
    experiment_stats = per_tech_stats(experiment, min_runs=args.min_runs)

    print_comparison(baseline_stats, experiment_stats, len(baseline), len(experiment))


if __name__ == "__main__":
    main()
