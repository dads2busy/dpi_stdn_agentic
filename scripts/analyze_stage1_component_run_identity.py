#!/usr/bin/env python3
"""
Analyze Stage 1 component run identity and core/union statistics across configurations.

This script is intended to help diagnose cases where:
- A single-agent configuration (e.g., v1v1v1) produces identical component sets across repeated runs
- Multi-agent debate configurations produce more variability
- Apparent robustness differences are driven by a small "tail" of swing components

Inputs
------
Normalized per-run STDN output CSVs produced by the pipeline:

  output/normalized/stdns_output_<config>_<YYYYMMDD>_<HHMMSS>.csv

We use the `technology` and `component` columns and deduplicate components within
each (technology, run) because the CSV is denormalized over materials/countries.

Outputs
-------
- A Markdown report summarizing, per configuration and per technology:
  - number of runs observed
  - number of unique run-sets (after canonical normalization already applied in CSV)
  - count/fraction of technologies with perfectly identical runs (unique_sets == 1)
  - per-technology core/union sizes:
      * intersection size across runs (core)
      * union size across runs
      * core_ratio = |intersection| / median(|set|)
      * jaccard_core_union = |intersection| / |union|

- Optional JSON containing the same structured results.

Usage
-----
uv run python scripts/analyze_stage1_component_run_identity.py \
  --normalized-dir output/normalized \
  --configs v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1 \
  --out-md output/analysis/stage1_component_run_identity.md \
  --out-json output/analysis/stage1_component_run_identity.json

Notes
-----
- This script does not compute pairwise Jaccard directly (that exists elsewhere).
  It focuses on set identity and core/union diagnostics.
- If you are running a global+granularity normalization, run this on the rewritten
  normalized CSVs to understand "post-normalization" consistency.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

_RX_FILE = re.compile(
    r"^stdns_output_(?P<config>[a-z0-9]+)_(?P<ts>\d{8}_\d{6})\.csv$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RunFile:
    path: Path
    config: str
    timestamp: str


@dataclass
class TechConfigStats:
    technology: str
    config: str
    runs: int
    unique_run_sets: int
    identical_runs: bool
    # Set-size diagnostics
    set_sizes: List[int]
    median_set_size: Optional[float]
    min_set_size: Optional[int]
    max_set_size: Optional[int]
    # Core/union diagnostics
    intersection_size: Optional[int]
    union_size: Optional[int]
    core_ratio: Optional[float]  # |∩| / median(|set|)
    jaccard_core_union: Optional[float]  # |∩| / |∪|
    # Swing components: those not always present (union - intersection)
    swing_components_count: Optional[int]


@dataclass
class ConfigSummary:
    config: str
    technologies: int
    runs_total: int
    technologies_all_runs_identical: int
    pct_technologies_all_runs_identical: Optional[float]
    macro_median_core_ratio: Optional[float]
    macro_mean_core_ratio: Optional[float]
    macro_median_jaccard_core_union: Optional[float]
    macro_mean_jaccard_core_union: Optional[float]
    macro_median_unique_run_sets: Optional[float]
    macro_mean_unique_run_sets: Optional[float]


def _fmt(x: Any) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        if math.isnan(x):
            return "NA"
        return f"{x:.3f}"
    return str(x)


def _md_table(headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(_fmt(r.get(h)) for h in headers) + " |")
    return "\n".join(lines) + "\n"


def iter_run_csvs(normalized_dir: Path) -> Iterable[RunFile]:
    for p in sorted(normalized_dir.glob("stdns_output_*.csv")):
        m = _RX_FILE.match(p.name)
        if not m:
            continue
        yield RunFile(path=p, config=m.group("config").lower(), timestamp=m.group("ts"))


def load_run_components(csv_path: Path) -> Dict[str, Set[str]]:
    """
    Return per-technology set of unique components for this run.
    Dedup is inherent because we build a set per technology.

    This assumes columns: technology, component (case-insensitive match).
    """
    tech_to_components: Dict[str, Set[str]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Missing header row: {csv_path}")

        fields = {name.strip().lower(): name for name in reader.fieldnames}
        if "technology" not in fields or "component" not in fields:
            raise ValueError(
                f"CSV missing required columns technology/component: {csv_path} "
                f"(found {reader.fieldnames})"
            )
        tech_col = fields["technology"]
        comp_col = fields["component"]

        for row in reader:
            tech = (row.get(tech_col) or "").strip()
            comp = (row.get(comp_col) or "").strip()
            if not tech or not comp:
                continue
            tech_to_components.setdefault(tech, set()).add(comp)

    return tech_to_components


def stable_set_fingerprint(items: Set[str]) -> str:
    """
    Fingerprint a set of component strings.
    We use a stable hash over sorted UTF-8 bytes.
    """
    joined = "\n".join(sorted(items)).encode("utf-8", errors="replace")
    return hashlib.sha256(joined).hexdigest()


def compute_tech_config_stats(
    technology: str, config: str, run_sets: Sequence[Set[str]]
) -> TechConfigStats:
    runs = len(run_sets)
    set_sizes = [len(s) for s in run_sets]

    if runs == 0:
        return TechConfigStats(
            technology=technology,
            config=config,
            runs=0,
            unique_run_sets=0,
            identical_runs=False,
            set_sizes=[],
            median_set_size=None,
            min_set_size=None,
            max_set_size=None,
            intersection_size=None,
            union_size=None,
            core_ratio=None,
            jaccard_core_union=None,
            swing_components_count=None,
        )

    fingerprints = [stable_set_fingerprint(s) for s in run_sets]
    unique_sets = len(set(fingerprints))
    identical = unique_sets == 1

    inter = set.intersection(*[set(s) for s in run_sets]) if run_sets else set()
    uni = set.union(*[set(s) for s in run_sets]) if run_sets else set()

    med_size = float(median(set_sizes)) if set_sizes else None
    inter_size = len(inter)
    uni_size = len(uni)

    core_ratio = (inter_size / med_size) if (med_size and med_size > 0) else None
    jcu = (inter_size / uni_size) if uni_size > 0 else None
    swing = (uni_size - inter_size) if (uni_size is not None) else None

    return TechConfigStats(
        technology=technology,
        config=config,
        runs=runs,
        unique_run_sets=unique_sets,
        identical_runs=identical,
        set_sizes=set_sizes,
        median_set_size=med_size,
        min_set_size=min(set_sizes) if set_sizes else None,
        max_set_size=max(set_sizes) if set_sizes else None,
        intersection_size=inter_size,
        union_size=uni_size,
        core_ratio=core_ratio,
        jaccard_core_union=jcu,
        swing_components_count=swing,
    )


def summarize_by_config(stats: Sequence[TechConfigStats]) -> List[ConfigSummary]:
    by_cfg: Dict[str, List[TechConfigStats]] = {}
    for s in stats:
        by_cfg.setdefault(s.config, []).append(s)

    summaries: List[ConfigSummary] = []
    for cfg in sorted(by_cfg.keys()):
        items = by_cfg[cfg]
        techs = len(items)
        runs_total = sum(s.runs for s in items)
        identical_techs = sum(1 for s in items if s.identical_runs)

        core_ratios = [s.core_ratio for s in items if s.core_ratio is not None]
        jcus = [s.jaccard_core_union for s in items if s.jaccard_core_union is not None]
        uniqs = [float(s.unique_run_sets) for s in items if s.runs > 0]

        summaries.append(
            ConfigSummary(
                config=cfg,
                technologies=techs,
                runs_total=runs_total,
                technologies_all_runs_identical=identical_techs,
                pct_technologies_all_runs_identical=(
                    (identical_techs / techs) if techs > 0 else None
                ),
                macro_median_core_ratio=float(median(core_ratios)) if core_ratios else None,
                macro_mean_core_ratio=float(mean(core_ratios)) if core_ratios else None,
                macro_median_jaccard_core_union=float(median(jcus)) if jcus else None,
                macro_mean_jaccard_core_union=float(mean(jcus)) if jcus else None,
                macro_median_unique_run_sets=float(median(uniqs)) if uniqs else None,
                macro_mean_unique_run_sets=float(mean(uniqs)) if uniqs else None,
            )
        )

    return summaries


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Report per-technology identical-run counts and core/union stats for Stage 1 component sets."
    )
    p.add_argument(
        "--normalized-dir",
        default="output/normalized",
        help="Directory containing normalized CSV outputs.",
    )
    p.add_argument(
        "--configs",
        nargs="+",
        required=True,
        help="Config tags to include (e.g., v1v1v1 d3v1v1).",
    )
    p.add_argument(
        "--out-md",
        default="",
        help="Optional path to write a Markdown report. If omitted, prints to stdout.",
    )
    p.add_argument(
        "--out-json",
        default="",
        help="Optional path to write JSON with full stats.",
    )
    p.add_argument(
        "--min-runs",
        type=int,
        default=2,
        help="Minimum runs required per technology/config to compute stats (default: 2).",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    normalized_dir = Path(args.normalized_dir)
    if not normalized_dir.exists():
        print(f"ERROR: normalized dir not found: {normalized_dir}", file=sys.stderr)
        return 2

    configs = [c.strip().lower() for c in args.configs if c.strip()]
    cfg_set = set(configs)
    if not cfg_set:
        print("ERROR: at least one config must be provided", file=sys.stderr)
        return 2

    run_files = [rf for rf in iter_run_csvs(normalized_dir) if rf.config in cfg_set]
    if not run_files:
        print(
            f"ERROR: no run CSVs found for configs={configs} under {normalized_dir}",
            file=sys.stderr,
        )
        return 2

    # Build mapping: (config, technology) -> list[set]
    sets_by_cfg_tech: Dict[Tuple[str, str], List[Set[str]]] = defaultdict(list)
    for rf in run_files:
        tech_to_components = load_run_components(rf.path)
        for tech, comps in tech_to_components.items():
            sets_by_cfg_tech[(rf.config, tech)].append(comps)

    # Compute per-tech stats
    all_stats: List[TechConfigStats] = []
    for (cfg, tech), run_sets in sorted(sets_by_cfg_tech.items(), key=lambda x: (x[0][0], x[0][1])):
        if len(run_sets) < args.min_runs:
            continue
        all_stats.append(compute_tech_config_stats(technology=tech, config=cfg, run_sets=run_sets))

    summaries = summarize_by_config(all_stats)

    # Render Markdown
    parts: List[str] = []
    parts.append("# Stage 1 Component Run Identity + Core/Union Diagnostics\n\n")
    parts.append(
        "This report analyzes per-technology Stage 1 component sets across repeated runs to detect:\n"
        "- technologies where all runs are identical (unique_run_sets = 1)\n"
        "- how much of each set is a stable core (intersection across runs)\n"
        "- how large the swing/tail is (union minus intersection)\n\n"
    )
    parts.append(f"- normalized_dir: `{normalized_dir}`\n")
    parts.append(f"- configs: {', '.join(configs)}\n")
    parts.append(f"- min_runs: {args.min_runs}\n\n")

    # Config summaries
    parts.append("## Summary by configuration\n\n")
    parts.append(
        _md_table(
            headers=[
                "config",
                "technologies",
                "runs_total",
                "technologies_all_runs_identical",
                "pct_technologies_all_runs_identical",
                "macro_median_unique_run_sets",
                "macro_mean_unique_run_sets",
                "macro_median_core_ratio",
                "macro_mean_core_ratio",
                "macro_median_jaccard_core_union",
                "macro_mean_jaccard_core_union",
            ],
            rows=[asdict(s) for s in summaries],
        )
    )

    # Per-tech table (sorted by config then tech)
    parts.append("\n## Per-technology stats (per config)\n\n")
    tech_rows: List[Dict[str, Any]] = []
    for s in sorted(all_stats, key=lambda x: (x.config, x.technology)):
        tech_rows.append(
            {
                "config": s.config,
                "technology": s.technology,
                "runs": s.runs,
                "unique_run_sets": s.unique_run_sets,
                "identical_runs": s.identical_runs,
                "median_set_size": s.median_set_size,
                "intersection_size": s.intersection_size,
                "union_size": s.union_size,
                "core_ratio": s.core_ratio,
                "jaccard_core_union": s.jaccard_core_union,
                "swing_components_count": s.swing_components_count,
            }
        )
    parts.append(
        _md_table(
            headers=[
                "config",
                "technology",
                "runs",
                "unique_run_sets",
                "identical_runs",
                "median_set_size",
                "intersection_size",
                "union_size",
                "core_ratio",
                "jaccard_core_union",
                "swing_components_count",
            ],
            rows=tech_rows,
        )
    )

    md = "".join(parts)

    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md, encoding="utf-8")
    else:
        print(md)

    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "normalized_dir": str(normalized_dir),
            "configs": configs,
            "min_runs": args.min_runs,
            "run_files": [
                {
                    **asdict(rf),
                    "path": str(rf.path),
                }
                for rf in run_files
            ],
            "per_tech_stats": [asdict(s) for s in all_stats],
            "config_summaries": [asdict(s) for s in summaries],
        }
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
