#!/usr/bin/env python3
"""
Compute Stage 1 final-component stability (pairwise Jaccard) from transcripts.

This script supports two related analyses:

A) By technology and config tag (existing behavior)
- Reads transcript TXT files from output/transcripts/
- Filters to specified configuration tags (default: v1v1v1, d2v1v1, d3v1v1, d4v1v1, d5v1v1)
- For specified base technologies, extracts the Stage 1 "FINAL CONSENSUS: Components" numbered list
- Computes pairwise Jaccard similarity across runs within each (technology, config) group
- Prints a Markdown table

B) Agent-count "sweet spot" analysis across the same five target technologies (new)
- Interprets the config tag as a proxy for component agent-count:
    v1v1v1 -> N=1 (single agent for components)
    d2v1v1 -> N=2 (2 debating agents for components)
    d3v1v1 -> N=3, ...
  (materials/country tokens are ignored for Stage 1 stability)
- Aggregates stability by (technology, N), then macro-averages across technologies
- Adds set-size statistics to avoid misreading stability when final list size changes with N

Usage:
  uv run python scripts/analyze_stage1_component_stability.py

Options:
  --transcripts-dir output/transcripts
  --tech "Bioreactor" --tech "Smartphone" ...
  --configs v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1
  --out-md output/analysis/stage1_component_stability.md

Agent-count analysis options:
  --agent-count-analysis
      Print an additional Markdown table grouped by component agent-count N and a macro-average summary.
  --agent-counts 1 2 3 4 5
      Optional explicit N values to include. If omitted, inferred from provided --configs.

Target technology selection:
  --all-tech
      Analyze across all technologies discovered in the transcripts directory (ignores the built-in default list).

Notes:
- "Config tag" is parsed from filename tokens using the project convention:
  a tag is 3 concatenated tokens, each token is 'v' or 'd' followed by 1-2 digits, e.g.:
    v1v1v1, d2v1v1, v1d12d19, d5v1d9
- Stage 1 extraction is bounded to:
    STAGE 1: COMPONENT EXTRACTION
    ...
    END OF COMPONENT EXTRACTION
  and then looks for:
    FINAL CONSENSUS: Components
  followed by numbered items (often indented):
    1. ...
    2. ...
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# Config tag token: 3 tokens, each token is [vd][1-2 digits], concatenated.
_RX_CFG_TOKEN = re.compile(r"(?:^|[_\s])((?:[vd]\d{1,2}){3})(?:$|[_\s])", re.IGNORECASE)

# Stage 1 bounding headers
_RX_STAGE1_HEADER = re.compile(r"^STAGE 1:\s*COMPONENT EXTRACTION\s*$", re.IGNORECASE)
_RX_STAGE1_END = re.compile(
    r"^END OF COMPONENT EXTRACTION\s*$|^END OF COMPONENTS EXTRACTION\s*$", re.IGNORECASE
)

# Final consensus section header and numbered items
# Accept minor variants in transcript formatting (case, optional plural).
_RX_FINAL_HEADER = re.compile(r"^FINAL CONSENSUS:\s*Component(?:s)?\s*$", re.IGNORECASE)
_RX_NUM_ITEM = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_RX_NUM_ITEM_BULLET = re.compile(r"^\s*[-*•]\s+(.+?)\s*$")

# Timestamp suffix in filenames
_RX_TIMESTAMP_SUFFIX = re.compile(r"_\d{8}_\d{6}$")


@dataclass(frozen=True)
class StabilityStats:
    technology: str
    config: str
    runs: int
    avg_jaccard: Optional[float]
    min_jaccard: Optional[float]
    max_jaccard: Optional[float]


@dataclass(frozen=True)
class AgentCountStabilityStats:
    technology: str
    component_agent_count: int
    runs: int
    avg_pairwise_jaccard: Optional[float]
    min_pairwise_jaccard: Optional[float]
    max_pairwise_jaccard: Optional[float]
    avg_set_size: Optional[float]
    min_set_size: Optional[int]
    max_set_size: Optional[int]


@dataclass(frozen=True)
class MacroAgentCountStats:
    component_agent_count: int
    technologies: int
    # Macro-summary across technologies (equal weight per technology)
    macro_avg_jaccard: Optional[float]
    macro_median_jaccard: Optional[float]
    macro_p10_jaccard: Optional[float]
    macro_p90_jaccard: Optional[float]
    macro_min_jaccard: Optional[float]
    macro_max_jaccard: Optional[float]
    macro_avg_set_size: Optional[float]


def iter_transcript_files(transcripts_dir: Path) -> Iterable[Path]:
    yield from sorted(transcripts_dir.glob("*.txt"))


def component_agent_count_from_config_tag(cfg: str) -> Optional[int]:
    """
    Map a config tag to the number of component agents N.

    Conventions:
      - v1v1v1 => N=1
      - d2v1v1 => N=2
      - d3v1v1 => N=3
      - ...

    We interpret ONLY the first token ([vd]\\d{1,2}) as the component-stage agent count.
    - vK -> K agents (single-agent mode encoded as v1 in this project)
    - dK -> K agents (debate mode)
    """
    cfg = (cfg or "").lower().strip()
    m = re.fullmatch(r"([vd])(\d{1,2})([vd]\d{1,2})([vd]\d{1,2})", cfg)
    if not m:
        return None
    prefix = m.group(1)
    n = int(m.group(2))
    if prefix not in ("v", "d"):
        return None
    return n


def parse_config_from_filename(path: Path) -> str:
    m = _RX_CFG_TOKEN.search(path.stem)
    return m.group(1).lower() if m else "unknown"


def parse_base_technology_from_filename(path: Path) -> str:
    """
    Convert a transcript filename stem into a base technology name by:
    - removing trailing timestamp
    - removing config tag token (if present)
    - converting underscores to spaces
    """
    stem = path.stem
    stem = _RX_TIMESTAMP_SUFFIX.sub("", stem)

    m = _RX_CFG_TOKEN.search(stem)
    if m:
        stem = (stem[: m.start(1)] + stem[m.end(1) :]).strip("_ ")

    stem = stem.replace("_", " ").strip()
    stem = re.sub(r"\s+", " ", stem)
    return stem


def extract_stage1_final_components(transcript_text: str) -> set[str]:
    """
    Extract the Stage 1 FINAL CONSENSUS: Components numbered list as a set of component strings.
    """
    lines = transcript_text.splitlines()

    # Bound to Stage 1 block if possible
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    for idx, line in enumerate(lines):
        s = line.strip()
        if start_idx is None and _RX_STAGE1_HEADER.match(s):
            start_idx = idx
            continue
        if start_idx is not None and _RX_STAGE1_END.match(s):
            end_idx = idx
            break

    if start_idx is not None:
        lines = lines[start_idx : (end_idx if end_idx is not None else len(lines))]

    in_final = False
    comps: list[str] = []

    for line in lines:
        s = line.strip()

        if _RX_FINAL_HEADER.match(s):
            in_final = True
            continue

        if not in_final:
            continue

        # Skip blank lines / metadata lines commonly present in the final block
        if not s:
            continue
        if any(
            s.lower().startswith(prefix)
            for prefix in (
                "rounds completed:",
                "final convergence:",
                "components selected:",
            )
        ):
            continue

        # Stop conditions if we drift into another section (or hit the section footer)
        #
        # Note: Many transcripts put a separator line ("=====") immediately after the
        # FINAL CONSENSUS header. We should *not* treat that first separator as an
        # end-of-section marker; instead, we ignore separators and stop on explicit
        # section boundaries.
        if s.upper().startswith("END OF") or s.upper().startswith("STAGE "):
            break

        # Parse numbered items (typical) or bullet items (some transcript variants)
        m = _RX_NUM_ITEM.match(line)
        if not m:
            m = _RX_NUM_ITEM_BULLET.match(line)

        if m:
            comp = m.group(1).strip()
            if comp:
                comps.append(comp)

    return set(comps)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def pairwise_jaccards(sets: list[set[str]]) -> list[float]:
    scores: list[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            scores.append(jaccard(sets[i], sets[j]))
    return scores


def compute_stats(technology: str, config: str, run_sets: list[set[str]]) -> StabilityStats:
    n = len(run_sets)
    if n < 2:
        return StabilityStats(
            technology=technology,
            config=config,
            runs=n,
            avg_jaccard=None,
            min_jaccard=None,
            max_jaccard=None,
        )
    scores = pairwise_jaccards(run_sets)
    if not scores:
        return StabilityStats(
            technology=technology,
            config=config,
            runs=n,
            avg_jaccard=0.0,
            min_jaccard=0.0,
            max_jaccard=0.0,
        )
    avg = sum(scores) / len(scores)
    return StabilityStats(
        technology=technology,
        config=config,
        runs=n,
        avg_jaccard=avg,
        min_jaccard=min(scores),
        max_jaccard=max(scores),
    )


def compute_agent_count_stats(
    technology: str, component_agent_count: int, run_sets: list[set[str]]
) -> AgentCountStabilityStats:
    runs = len(run_sets)

    if runs == 0:
        return AgentCountStabilityStats(
            technology=technology,
            component_agent_count=component_agent_count,
            runs=0,
            avg_pairwise_jaccard=None,
            min_pairwise_jaccard=None,
            max_pairwise_jaccard=None,
            avg_set_size=None,
            min_set_size=None,
            max_set_size=None,
        )

    sizes = [len(s) for s in run_sets]
    avg_set_size = sum(sizes) / len(sizes) if sizes else None
    min_set_size = min(sizes) if sizes else None
    max_set_size = max(sizes) if sizes else None

    if runs < 2:
        return AgentCountStabilityStats(
            technology=technology,
            component_agent_count=component_agent_count,
            runs=runs,
            avg_pairwise_jaccard=None,
            min_pairwise_jaccard=None,
            max_pairwise_jaccard=None,
            avg_set_size=avg_set_size,
            min_set_size=min_set_size,
            max_set_size=max_set_size,
        )

    scores = pairwise_jaccards(run_sets)
    if not scores:
        return AgentCountStabilityStats(
            technology=technology,
            component_agent_count=component_agent_count,
            runs=runs,
            avg_pairwise_jaccard=0.0,
            min_pairwise_jaccard=0.0,
            max_pairwise_jaccard=0.0,
            avg_set_size=avg_set_size,
            min_set_size=min_set_size,
            max_set_size=max_set_size,
        )

    return AgentCountStabilityStats(
        technology=technology,
        component_agent_count=component_agent_count,
        runs=runs,
        avg_pairwise_jaccard=sum(scores) / len(scores),
        min_pairwise_jaccard=min(scores),
        max_pairwise_jaccard=max(scores),
        avg_set_size=avg_set_size,
        min_set_size=min_set_size,
        max_set_size=max_set_size,
    )


def compute_macro_agent_count_stats(
    per_tech: list[AgentCountStabilityStats], component_agent_count: int
) -> MacroAgentCountStats:
    """
    Macro-summary across technologies (equal weight per technology), ignoring technologies
    where we don't have a defined avg_pairwise_jaccard (e.g. runs < 2).

    Notes:
    - "technologies" counts technologies present for this N (even if runs < 2).
    - Stability summaries (avg/median/p10/p90/min/max) are computed only across
      technologies with avg_pairwise_jaccard defined (i.e., runs >= 2).
    """
    eligible = [s for s in per_tech if s.component_agent_count == component_agent_count]

    # Only include technologies with stability defined (>=2 runs) for macro stability numbers.
    eligible_for_stability = [s for s in eligible if s.avg_pairwise_jaccard is not None]
    eligible_for_size = [s for s in eligible if s.avg_set_size is not None]

    if not eligible:
        return MacroAgentCountStats(
            component_agent_count=component_agent_count,
            technologies=0,
            macro_avg_jaccard=None,
            macro_median_jaccard=None,
            macro_p10_jaccard=None,
            macro_p90_jaccard=None,
            macro_min_jaccard=None,
            macro_max_jaccard=None,
            macro_avg_set_size=None,
        )

    if eligible_for_stability:
        values = sorted(s.avg_pairwise_jaccard for s in eligible_for_stability)

        macro_avg = sum(values) / len(values)

        # Median
        mid = len(values) // 2
        if len(values) % 2 == 1:
            macro_median = values[mid]
        else:
            macro_median = (values[mid - 1] + values[mid]) / 2.0

        # p10/p90 using nearest-rank on the sorted list (simple + stable for small n like 5 techs)
        def _nearest_rank(sorted_vals: list[float], p: float) -> float:
            # p in [0,1]; clamp and pick 1-indexed nearest rank
            if not sorted_vals:
                raise ValueError("sorted_vals must be non-empty")
            p = 0.0 if p < 0.0 else (1.0 if p > 1.0 else p)
            k = int((len(sorted_vals) - 1) * p + 0.5)
            return sorted_vals[k]

        macro_p10 = _nearest_rank(values, 0.10)
        macro_p90 = _nearest_rank(values, 0.90)

        # Still keep extrema across *pairwise* ranges, not the avg values.
        macro_min = min(
            s.min_pairwise_jaccard
            for s in eligible_for_stability
            if s.min_pairwise_jaccard is not None
        )
        macro_max = max(
            s.max_pairwise_jaccard
            for s in eligible_for_stability
            if s.max_pairwise_jaccard is not None
        )
    else:
        macro_avg = None
        macro_median = None
        macro_p10 = None
        macro_p90 = None
        macro_min = None
        macro_max = None

    macro_avg_size = (
        sum(s.avg_set_size for s in eligible_for_size) / len(eligible_for_size)
        if eligible_for_size
        else None
    )

    return MacroAgentCountStats(
        component_agent_count=component_agent_count,
        technologies=len(eligible),
        macro_avg_jaccard=macro_avg,
        macro_median_jaccard=macro_median,
        macro_p10_jaccard=macro_p10,
        macro_p90_jaccard=macro_p90,
        macro_min_jaccard=macro_min,
        macro_max_jaccard=macro_max,
        macro_avg_set_size=macro_avg_size,
    )


def format_md_agent_count_tables(
    tech_stats: list[AgentCountStabilityStats],
    macro_stats: list[MacroAgentCountStats],
    tech_order: list[str],
    agent_counts_order: list[int],
) -> str:
    out: list[str] = []

    out.append("\n## Stage 1 stability by component agent-count (N)\n")
    out.append(
        "| Technology | N (component agents) | Runs | Avg pairwise Jaccard | Min | Max | Avg |final_set| | Min | Max |"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    index = {(s.technology, s.component_agent_count): s for s in tech_stats}
    for tech in tech_order:
        for n in agent_counts_order:
            s = index.get((tech, n))
            if s is None:
                out.append(f"| {tech} | {n} | 0 | NA | NA | NA | NA | NA | NA |")
                continue

            if s.avg_pairwise_jaccard is None:
                avg = "NA" if s.runs == 0 else "NA (n=1)"
                out.append(
                    f"| {tech} | {n} | {s.runs} | {avg} | NA | NA | "
                    f"{'NA' if s.avg_set_size is None else f'{s.avg_set_size:.2f}'} | "
                    f"{'NA' if s.min_set_size is None else s.min_set_size} | "
                    f"{'NA' if s.max_set_size is None else s.max_set_size} |"
                )
            else:
                out.append(
                    f"| {tech} | {n} | {s.runs} | {s.avg_pairwise_jaccard:.3f} | "
                    f"{s.min_pairwise_jaccard:.3f} | {s.max_pairwise_jaccard:.3f} | "
                    f"{s.avg_set_size:.2f} | {s.min_set_size} | {s.max_set_size} |"
                )

    out.append("\n### Macro-summary across technologies (equal weight)\n")
    out.append(
        "| N (component agents) | Technologies | Macro avg Jaccard | Macro median | Macro p10 | Macro p90 | Macro min | Macro max | Macro avg |final_set| |"
    )
    out.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    macro_index = {m.component_agent_count: m for m in macro_stats}
    for n in agent_counts_order:
        m = macro_index.get(n)
        if m is None or m.technologies == 0:
            out.append(f"| {n} | 0 | NA | NA | NA | NA |")
            continue

        if m.macro_avg_jaccard is None:
            out.append(
                f"| {n} | {m.technologies} | NA | NA | NA | NA | NA | NA | "
                f"{'NA' if m.macro_avg_set_size is None else f'{m.macro_avg_set_size:.2f}'}"
                " |"
            )
        else:
            out.append(
                f"| {n} | {m.technologies} | {m.macro_avg_jaccard:.3f} | "
                f"{m.macro_median_jaccard:.3f} | {m.macro_p10_jaccard:.3f} | {m.macro_p90_jaccard:.3f} | "
                f"{m.macro_min_jaccard:.3f} | {m.macro_max_jaccard:.3f} | "
                f"{m.macro_avg_set_size:.2f} |"
            )

    return "\n".join(out) + "\n"


def format_md_table(
    stats: list[StabilityStats], configs_order: list[str], tech_order: list[str]
) -> str:
    lines: list[str] = []
    lines.append(
        "| Technology | Config | Runs | Avg pairwise Jaccard (Stage 1 final components) | Min | Max |"
    )
    lines.append("|---|---|---:|---:|---:|---:|")

    # stable ordering: by tech order then config order
    index = {(s.technology, s.config): s for s in stats}
    for tech in tech_order:
        for cfg in configs_order:
            s = index.get((tech, cfg))
            if s is None:
                # Should not happen if we build stats for all pairs
                lines.append(f"| {tech} | `{cfg}` | 0 | NA | NA | NA |")
                continue

            if s.avg_jaccard is None:
                avg = "NA" if s.runs == 0 else "NA (n=1)"
                lines.append(f"| {tech} | `{cfg}` | {s.runs} | {avg} | NA | NA |")
            else:
                lines.append(
                    f"| {tech} | `{cfg}` | {s.runs} | {s.avg_jaccard:.3f} | {s.min_jaccard:.3f} | {s.max_jaccard:.3f} |"
                )

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--transcripts-dir",
        default="output/transcripts",
        help="Directory containing transcript .txt files (default: output/transcripts).",
    )
    ap.add_argument(
        "--tech",
        action="append",
        default=[],
        help="Base technology name to include (repeatable). If omitted, uses a built-in default set.",
    )
    ap.add_argument(
        "--configs",
        nargs="+",
        default=["v1v1v1", "d2v1v1", "d3v1v1", "d4v1v1", "d5v1v1"],
        help="Config tags to include (space-separated).",
    )
    ap.add_argument(
        "--all-tech",
        action="store_true",
        help="Analyze across all technologies discovered in the transcripts directory (overrides the built-in default tech list).",
    )
    ap.add_argument(
        "--agent-count-analysis",
        action="store_true",
        help="Also compute Stage 1 stability by component agent-count (N) and a macro-average across technologies.",
    )
    ap.add_argument(
        "--agent-counts",
        nargs="+",
        type=int,
        default=None,
        help="Optional explicit component agent-count N values to include (space-separated). If omitted, inferred from --configs.",
    )
    ap.add_argument(
        "--out-md",
        default=None,
        help="Optional path to write the markdown table(s) (e.g., output/analysis/stage1_component_stability.md).",
    )
    args = ap.parse_args()

    transcripts_dir = Path(args.transcripts_dir)
    if not transcripts_dir.exists():
        raise SystemExit(f"Transcripts dir not found: {transcripts_dir}")

    default_targets = [
        "Bioreactor",
        "Freeze Dryer (Lyophilizer)",
        "Hydroponic Systems",
        "Smartphone",
        "Tablet Press (Rotary Tablet Press)",
    ]

    if args.all_tech:
        # Discover all technologies present in the transcripts directory (filtered by requested configs).
        discovered: set[str] = set()
        for fp in iter_transcript_files(transcripts_dir):
            cfg = parse_config_from_filename(fp)
            if cfg not in set(c.lower() for c in args.configs):
                continue
            discovered.add(parse_base_technology_from_filename(fp))
        targets: list[str] = sorted(discovered)
    else:
        # Default behavior: use the same five technologies unless the caller overrides with --tech.
        targets = args.tech if args.tech else default_targets

    configs_order: list[str] = [c.lower() for c in args.configs]
    configs_set = set(configs_order)

    # Component agent-counts (N) derived from config tags unless explicitly provided.
    if args.agent_counts is not None:
        agent_counts_order: list[int] = sorted(set(args.agent_counts))
    else:
        inferred = []
        for cfg in configs_order:
            n = component_agent_count_from_config_tag(cfg)
            if n is not None:
                inferred.append(n)
        agent_counts_order = sorted(set(inferred))

    # (tech, cfg) -> list[component_set]
    grouped: dict[tuple[str, str], list[set[str]]] = {}
    for tech in targets:
        for cfg in configs_order:
            grouped[(tech, cfg)] = []

    # (tech, N) -> list[component_set]
    grouped_by_n: dict[tuple[str, int], list[set[str]]] = {}
    for tech in targets:
        for n in agent_counts_order:
            grouped_by_n[(tech, n)] = []

    for fp in iter_transcript_files(transcripts_dir):
        cfg = parse_config_from_filename(fp)
        if cfg not in configs_set:
            continue

        tech = parse_base_technology_from_filename(fp)
        if tech not in targets:
            continue

        txt = fp.read_text(encoding="utf-8", errors="replace")
        comps = extract_stage1_final_components(txt)
        if not comps:
            continue

        grouped[(tech, cfg)].append(comps)

        n = component_agent_count_from_config_tag(cfg)
        if n is not None and n in set(agent_counts_order):
            grouped_by_n[(tech, n)].append(comps)

    # Build stats for all requested pairs, even if 0 runs found.
    stats: list[StabilityStats] = []
    for tech in targets:
        for cfg in configs_order:
            stats.append(compute_stats(tech, cfg, grouped.get((tech, cfg), [])))

    md = format_md_table(stats, configs_order=configs_order, tech_order=targets)

    if args.agent_count_analysis:
        tech_n_stats: list[AgentCountStabilityStats] = []
        for tech in targets:
            for n in agent_counts_order:
                tech_n_stats.append(
                    compute_agent_count_stats(tech, n, grouped_by_n.get((tech, n), []))
                )

        macro_stats: list[MacroAgentCountStats] = [
            compute_macro_agent_count_stats(tech_n_stats, n) for n in agent_counts_order
        ]

        md += format_md_agent_count_tables(
            tech_stats=tech_n_stats,
            macro_stats=macro_stats,
            tech_order=targets,
            agent_counts_order=agent_counts_order,
        )

    print(md, end="")

    if args.out_md:
        out_path = Path(args.out_md)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"\nWrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
