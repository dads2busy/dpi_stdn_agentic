#!/usr/bin/env python3
"""
Compute Stage 1 (component) run-to-run stability using *normalized* STDN outputs.

Why this script exists
----------------------
The existing stability analysis in `scripts/analyze_stage1_component_stability.py`
computes Jaccard overlap over raw component strings extracted from transcript text.
That is a useful diagnostic for prompt-surface variability, but it can understate
the reproducibility of the *delivered artifact* because it is sensitive to
synonyms, formatting differences, and granularity drift.

This script computes stability using the normalized outputs in:

    output/normalized/stdns_output_<configuration>_*.csv

The normalized CSVs contain canonicalized component names in a `component` column.
We compute per-technology component sets from that column (deduped), then compute
pairwise Jaccard similarities across repeated runs for each configuration.

Outputs
-------
Prints Markdown tables summarizing stability by component-agent count N (parsed from
the configuration tag), plus optional CSV/JSON outputs if requested.

Assumptions
-----------
- Input files are normalized CSVs with a header row including at least:
    - technology
    - component
- Filenames follow the pattern:
    stdns_output_<config>_<timestamp>.csv
  where <config> includes tokens like v1v1v1, d3v1v1, v1d2v1, etc.
- We focus on Stage 1 components, so for configuration parsing we use the *first*
  token:
    - v1 => N = 1
    - dN => N = N

Usage
-----
    python scripts/analyze_stage1_component_stability_normalized.py \
        --normalized-dir output/normalized \
        --include-config 'd*' \
        --include-config 'v1v1v1' \
        --min-runs 2 \
        --out-md output/analysis/stage1_component_stability_normalized.md

Notes
-----
- Jaccard is computed over the set of unique canonical components per technology/run.
- This stability definition is "product-facing": it measures overlap of canonical
  components emitted by the pipeline, after normalization.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Dict, Iterable, List, Optional, Sequence, Set

_RX_FILENAME = re.compile(
    r"^stdns_output_(?P<config>[a-z0-9]+)_(?P<ts>\d{8}_\d{6})(?P<rest>.*)\.csv$",
    re.IGNORECASE,
)
# Match the *first* stage token at the beginning of the config tag (Stage 1 components):
#   v1v1v1  -> v1
#   d3v1v1  -> d3
#   v1d2v1  -> v1
_RX_STAGE1_TOKEN = re.compile(r"^(v1|d\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class RunFile:
    path: Path
    config: str
    timestamp: str


@dataclass
class StabilityStats:
    technology: str
    config: str
    runs: int
    avg_jaccard: Optional[float]
    min_jaccard: Optional[float]
    max_jaccard: Optional[float]
    median_jaccard: Optional[float]


@dataclass
class AgentCountStabilityStats:
    agent_count: int
    configs: List[str]
    technologies: int
    runs_total: int
    macro_median_jaccard: Optional[float]
    macro_mean_jaccard: Optional[float]
    tech_medians: List[float]  # per-technology median jaccard (flattened across configs)


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def pairwise_jaccards(sets: Sequence[Set[str]]) -> List[float]:
    scores: List[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            scores.append(jaccard(sets[i], sets[j]))
    return scores


def component_agent_count_from_config_tag(config: str) -> int:
    """
    Extract Stage 1 (components) agent count N from a config tag.

    We intentionally parse only the *leading* token, since the config tag encodes
    stage decisions positionally:
      - v1v1v1 -> Stage 1 token is v1  -> N = 1
      - d3v1v1 -> Stage 1 token is d3  -> N = 3
      - v1d2v1 -> Stage 1 token is v1  -> N = 1  (materials debate is Stage 2)
    """
    config = config.strip().lower()
    m = _RX_STAGE1_TOKEN.match(config)
    if not m:
        return -1

    token = m.group(1).lower()
    if token == "v1":
        return 1

    if token.startswith("d"):
        try:
            return int(token[1:])
        except ValueError:
            return -1

    return -1


def iter_normalized_csv_files(normalized_dir: Path) -> Iterable[RunFile]:
    for p in sorted(normalized_dir.glob("stdns_output_*.csv")):
        m = _RX_FILENAME.match(p.name)
        if not m:
            # Skip aggregates like *_ALL_dedup.csv or any nonstandard naming.
            continue
        yield RunFile(path=p, config=m.group("config").lower(), timestamp=m.group("ts"))


def load_component_sets_from_csv(path: Path) -> Dict[str, Set[str]]:
    """
    Parse a normalized STDN output CSV and return:
        technology -> set(components)
    The CSV is denormalized at the (technology, component, material, country) level,
    so we deduplicate by technology+component.
    """
    tech_to_components: Dict[str, Set[str]] = {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Missing header row in CSV: {path}")

        # Allow minor header variations by normalizing names.
        fields = {name.strip().lower(): name for name in reader.fieldnames}
        if "technology" not in fields or "component" not in fields:
            raise ValueError(
                f"CSV missing required columns technology/component: {path} "
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


def compute_stability_for_config(
    config: str, run_files: Sequence[RunFile], min_runs: int
) -> List[StabilityStats]:
    """
    For a given config, compute per-technology stability across runs.
    Returns a list of StabilityStats (one per technology).
    """
    # Load all runs: each run yields a mapping technology -> set(components)
    run_maps: List[Dict[str, Set[str]]] = []
    for rf in run_files:
        run_maps.append(load_component_sets_from_csv(rf.path))

    # Union of technologies observed across runs (some runs may miss a tech)
    technologies: Set[str] = set()
    for m in run_maps:
        technologies |= set(m.keys())

    results: List[StabilityStats] = []

    for tech in sorted(technologies):
        # Collect the set from each run where this tech is present
        run_sets: List[Set[str]] = [m[tech] for m in run_maps if tech in m]
        n = len(run_sets)
        if n < min_runs:
            results.append(
                StabilityStats(
                    technology=tech,
                    config=config,
                    runs=n,
                    avg_jaccard=None,
                    min_jaccard=None,
                    max_jaccard=None,
                    median_jaccard=None,
                )
            )
            continue

        scores = pairwise_jaccards(run_sets)
        if not scores:
            results.append(
                StabilityStats(
                    technology=tech,
                    config=config,
                    runs=n,
                    avg_jaccard=1.0,
                    min_jaccard=1.0,
                    max_jaccard=1.0,
                    median_jaccard=1.0,
                )
            )
            continue

        results.append(
            StabilityStats(
                technology=tech,
                config=config,
                runs=n,
                avg_jaccard=float(mean(scores)),
                min_jaccard=float(min(scores)),
                max_jaccard=float(max(scores)),
                median_jaccard=float(median(scores)),
            )
        )

    return results


def macro_aggregate_by_agent_count(
    per_config_stats: Dict[str, List[StabilityStats]],
) -> List[AgentCountStabilityStats]:
    """
    Aggregate per-technology stability into agent-count-level macro summaries.

    We:
    - group configs by Stage 1 agent count N
    - collect per-technology median_jaccard (skipping None)
    - report macro median and macro mean across those per-technology medians
    """
    by_n: Dict[int, Dict[str, List[float]]] = {}
    by_n_configs: Dict[int, List[str]] = {}
    by_n_runs_total: Dict[int, int] = {}
    by_n_techs: Dict[int, Set[str]] = {}

    for cfg, stats_list in per_config_stats.items():
        n = component_agent_count_from_config_tag(cfg)
        if n <= 0:
            continue
        by_n_configs.setdefault(n, []).append(cfg)
        by_n_runs_total.setdefault(n, 0)
        by_n_techs.setdefault(n, set())

        # Count runs total: approximate as the max runs seen per tech for this config
        # (not perfect, but good for a compact report)
        max_runs = 0
        for s in stats_list:
            if s.runs and s.runs > max_runs:
                max_runs = s.runs
        by_n_runs_total[n] += max_runs

        for s in stats_list:
            by_n_techs[n].add(s.technology)
            if s.median_jaccard is None:
                continue
            by_n.setdefault(n, {}).setdefault(s.technology, []).append(s.median_jaccard)

    out: List[AgentCountStabilityStats] = []
    for n in sorted(by_n_configs.keys()):
        tech_medians: List[float] = []
        # If a technology appears under multiple configs for the same N, average its medians.
        for tech, vals in (by_n.get(n, {}) or {}).items():
            if vals:
                tech_medians.append(float(mean(vals)))

        macro_med = float(median(tech_medians)) if tech_medians else None
        macro_mean = float(mean(tech_medians)) if tech_medians else None

        out.append(
            AgentCountStabilityStats(
                agent_count=n,
                configs=sorted(by_n_configs.get(n, [])),
                technologies=len(by_n_techs.get(n, set())),
                runs_total=by_n_runs_total.get(n, 0),
                macro_median_jaccard=macro_med,
                macro_mean_jaccard=macro_mean,
                tech_medians=sorted(tech_medians),
            )
        )
    return out


def format_md_table(rows: List[Dict[str, object]], headers: List[str]) -> str:
    """
    Simple Markdown table formatter with fixed header ordering.
    """

    def fmt(v: object) -> str:
        if v is None:
            return "NA"
        if isinstance(v, float):
            # compact but readable
            if math.isnan(v):
                return "NA"
            return f"{v:.3f}"
        return str(v)

    lines: List[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(fmt(r.get(h)) for h in headers) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compute Stage 1 component stability (Jaccard) using normalized CSV outputs."
    )
    ap.add_argument(
        "--normalized-dir",
        type=str,
        default="output/normalized",
        help="Directory containing stdns_output_<config>_*.csv normalized outputs.",
    )
    ap.add_argument(
        "--include-config",
        action="append",
        default=[],
        help=(
            "Glob-like filter(s) for config tags to include (e.g., 'd*', 'v1v1v1'). "
            "May be repeated. If omitted, includes all detected configs."
        ),
    )
    ap.add_argument(
        "--exclude-config",
        action="append",
        default=[],
        help="Glob-like filter(s) for config tags to exclude. May be repeated.",
    )
    ap.add_argument(
        "--min-runs",
        type=int,
        default=2,
        help="Minimum number of runs required per technology to compute stability.",
    )
    ap.add_argument(
        "--out-md",
        type=str,
        default="",
        help="Optional path to write a Markdown report.",
    )
    ap.add_argument(
        "--out-json",
        type=str,
        default="",
        help="Optional path to write raw per-technology stats as JSON.",
    )
    args = ap.parse_args()

    normalized_dir = Path(args.normalized_dir)
    if not normalized_dir.exists():
        raise SystemExit(f"Normalized directory not found: {normalized_dir}")

    # Gather run files grouped by config.
    configs_to_runs: Dict[str, List[RunFile]] = {}
    for rf in iter_normalized_csv_files(normalized_dir):
        configs_to_runs.setdefault(rf.config, []).append(rf)

    if not configs_to_runs:
        raise SystemExit(f"No normalized run CSVs found in: {normalized_dir}")

    # Apply include/exclude filters.
    def match_any_globs(s: str, globs: Sequence[str]) -> bool:
        if not globs:
            return True
        for g in globs:
            if Path(s).match(g):
                return True
        return False

    def match_excluded(s: str, globs: Sequence[str]) -> bool:
        for g in globs:
            if Path(s).match(g):
                return True
        return False

    selected_configs = [
        c
        for c in sorted(configs_to_runs.keys())
        if match_any_globs(c, args.include_config) and not match_excluded(c, args.exclude_config)
    ]

    if not selected_configs:
        raise SystemExit("No configs selected after applying include/exclude filters.")

    # Compute per-config per-technology stability stats.
    per_config_stats: Dict[str, List[StabilityStats]] = {}
    for cfg in selected_configs:
        run_files = sorted(configs_to_runs[cfg], key=lambda r: r.timestamp)
        per_config_stats[cfg] = compute_stability_for_config(cfg, run_files, min_runs=args.min_runs)

    # Macro aggregation by agent count (Stage 1 N).
    macro = macro_aggregate_by_agent_count(per_config_stats)

    # Build Markdown report.
    md_parts: List[str] = []
    md_parts.append("# Stage 1 Component Stability (Normalized Outputs)\n")
    md_parts.append(
        "This report computes run-to-run stability using **normalized** STDN outputs "
        "(`output/normalized/stdns_output_<config>_*.csv`). Stability is measured as "
        "pairwise **Jaccard similarity** of the per-technology **set of unique canonical component names** "
        "(`component` column), aggregated across technologies.\n"
    )
    md_parts.append(f"- Normalized dir: `{normalized_dir}`\n")
    md_parts.append(f"- Selected configs: {', '.join(selected_configs)}\n")
    md_parts.append(f"- min_runs: {args.min_runs}\n\n")

    # Summary table by agent count.
    rows: List[Dict[str, object]] = []
    for s in macro:
        rows.append(
            {
                "N": s.agent_count,
                "macro_median_jaccard": s.macro_median_jaccard,
                "macro_mean_jaccard": s.macro_mean_jaccard,
                "technologies": s.technologies,
                "configs": ", ".join(s.configs),
            }
        )
    md_parts.append("## Macro summary by component debate strength (Stage 1 N)\n\n")
    md_parts.append(
        format_md_table(
            rows,
            headers=["N", "macro_median_jaccard", "macro_mean_jaccard", "technologies", "configs"],
        )
    )

    # Per-config quick table (macro-median of per-technology medians for each config).
    cfg_rows: List[Dict[str, object]] = []
    for cfg in selected_configs:
        medians = [s.median_jaccard for s in per_config_stats[cfg] if s.median_jaccard is not None]
        cfg_rows.append(
            {
                "config": cfg,
                "N": component_agent_count_from_config_tag(cfg),
                "techs": len({s.technology for s in per_config_stats[cfg]}),
                "macro_median_of_tech_medians": float(median(medians)) if medians else None,
                "macro_mean_of_tech_medians": float(mean(medians)) if medians else None,
            }
        )
    md_parts.append("\n## Per-configuration summary (Stage 1 components)\n\n")
    md_parts.append(
        format_md_table(
            cfg_rows,
            headers=[
                "config",
                "N",
                "techs",
                "macro_median_of_tech_medians",
                "macro_mean_of_tech_medians",
            ],
        )
    )

    report = "".join(md_parts)

    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(report, encoding="utf-8")
    else:
        print(report)

    if args.out_json:
        out_json = Path(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "normalized_dir": str(normalized_dir),
            "selected_configs": selected_configs,
            "min_runs": args.min_runs,
            "per_config_stats": {
                cfg: [asdict(s) for s in stats] for cfg, stats in per_config_stats.items()
            },
            "macro_by_agent_count": [asdict(s) for s in macro],
        }
        out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
