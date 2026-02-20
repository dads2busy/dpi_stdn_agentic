#!/usr/bin/env python3
"""
Judge Stage 1 component validity from *normalized* STDN outputs (per-run), with caching.

Why this script exists
----------------------
The paper's validity analysis uses an independent LLM judge to label whether each extracted
component is a plausible *primary manufacturing component* for a given technology.

After introducing stronger cross-run normalization (including granularity enforcement),
we also want to compare *per-run output variability* across configurations (e.g., v1v1v1 vs d3v1v1),
without paying judge cost repeatedly for the same (technology, component) pair.

This script:
- Reads normalized CSVs: output/normalized/stdns_output_<config>_<timestamp>.csv
- Extracts per-run component sets (deduped within run and technology)
- Judges (technology, component) pairs via an LLM judge
- Caches verdicts by (technology, component) so per-run metrics are cheap to compute
- Reports per-run invalid rates and variability summaries per config
- Optionally emits a JSONL of raw judgments and a Markdown report

Requirements
------------
- Run via the project's environment manager so dependencies are available (recommended).
- Provider API key must be available in env (e.g., OPENAI_API_KEY). This script loads .env if present.

Example usage
-------------
uv run python scripts/judge_stage1_components_from_normalized_outputs.py \\
  --normalized-dir output/normalized \\
  --configs v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1 \\
  --judge-model openai:gpt-4.1 \\
  --out-md output/analysis/stage1_component_judge_normalized.md \\
  --out-jsonl output/analysis/stage1_component_judge_normalized.jsonl

Notes
-----
- This script judges normalized component *names* (canonical primary components) if your normalization
  pipeline has been applied. If not, it will judge whatever is in the CSV.
- Caching is keyed by exact (technology, component) strings after basic whitespace normalization.
  If you further change normalization, clear/rotate the cache file to avoid mixing regimes.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from dotenv import load_dotenv

# Load environment variables from .env (if present) so provider keys like OPENAI_API_KEY are available.
load_dotenv()

from pydantic import BaseModel, Field
from pydantic_ai import Agent

_RX_FILE = re.compile(
    r"^stdns_output_(?P<config>[a-z0-9]+)_(?P<ts>\d{8}_\d{6})\.csv$",
    re.IGNORECASE,
)


# -----------------------------
# Models
# -----------------------------


class JudgeVerdict(BaseModel):
    plausible: bool = Field(
        description="True if the component is a plausible primary manufacturing component."
    )
    rationale: str = Field(
        description="Short justification for the plausibility decision (1-3 sentences)."
    )


@dataclass(frozen=True)
class RunFile:
    path: Path
    config: str
    timestamp: str


@dataclass(frozen=True)
class Candidate:
    technology: str
    component: str
    config: str
    run_timestamp: str
    source_csv: str


@dataclass(frozen=True)
class CacheKey:
    technology: str
    component: str

    def as_str(self) -> str:
        # Stable key for JSONL cache. Avoid separators that may appear in text.
        return f"{self.technology}|||{self.component}"


@dataclass
class JudgedRecord:
    technology: str
    component: str
    plausible: bool
    rationale: str
    judged_at_utc: str
    judge_model: str


@dataclass
class RunMetrics:
    config: str
    run_timestamp: str
    technology: str
    components_total: int
    components_invalid: int
    invalid_rate: Optional[float]


# -----------------------------
# Helpers: parsing + extraction
# -----------------------------


def iter_run_csvs(normalized_dir: Path) -> Iterable[RunFile]:
    for p in sorted(normalized_dir.glob("stdns_output_*.csv")):
        m = _RX_FILE.match(p.name)
        if not m:
            # Skip aggregates like *_ALL_dedup.csv
            continue
        yield RunFile(path=p, config=m.group("config").lower(), timestamp=m.group("ts"))


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def load_run_components(csv_path: Path) -> Dict[str, Set[str]]:
    """
    Return per-technology set of unique components for this run.

    The normalized CSV is denormalized over (technology, component, material, country),
    so we dedupe by (technology, component).
    """
    tech_to_components: Dict[str, Set[str]] = defaultdict(set)

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
            tech = _strip(row.get(tech_col, ""))
            comp = _strip(row.get(comp_col, ""))
            if not tech or not comp:
                continue
            tech_to_components[tech].add(comp)

    return tech_to_components


def build_candidates(
    run_files: Sequence[RunFile],
    configs: Set[str],
    technologies: Optional[Set[str]],
) -> List[Candidate]:
    out: List[Candidate] = []
    for rf in run_files:
        if configs and rf.config not in configs:
            continue
        tech_to_components = load_run_components(rf.path)
        for tech, comps in tech_to_components.items():
            if technologies is not None and tech not in technologies:
                continue
            for comp in sorted(comps):
                out.append(
                    Candidate(
                        technology=tech,
                        component=comp,
                        config=rf.config,
                        run_timestamp=rf.timestamp,
                        source_csv=str(rf.path),
                    )
                )
    return out


# -----------------------------
# Judge prompt + agent
# -----------------------------


def build_judge_prompt(technology: str, component: str) -> str:
    """
    Judge whether `component` is a plausible PRIMARY MANUFACTURING COMPONENT for `technology`.

    This prompt is intentionally aligned with the Stage 1 Component Agent's concept definition:
    major modules/subassemblies with distinct supply chains, excluding raw materials, tools,
    consumables, and packaging. The judge returns only a binary plausibility verdict and a
    short rationale.
    """
    return f"""You are an expert in technology manufacturing and supply chain analysis.

**CRITICAL: Always respond in English.**

**STEP 1: TECHNOLOGY SPECIFICATION**

First, identify the MOST COMMON, INDUSTRY-STANDARD form of the technology requested.
- Use precise industry terminology and technical nomenclature
- Identify the dominant market variant by production volume or market adoption
- Consider current market standards (as of 2024-2025)
- ALWAYS validate the user's term, even if already specific

You do NOT need to output the technology specification, but you MUST use it when judging the candidate component below.

**STEP 2: COMPONENT IDENTIFICATION (VALIDITY CHECK)**

Your task is to determine whether the candidate below is a PRIMARY MANUFACTURING COMPONENT for the SPECIFIED technology product.

PRIMARY COMPONENTS are major subassemblies or modules that:
- Are procured or manufactured separately
- Have distinct supply chains
- Form the core functional or structural architecture
- Are typically purchased as complete units

INCLUDE (plausible primary components):
- Major functional modules (e.g., display, battery, processor, control system)
- Structural assemblies (e.g., chassis, enclosure, vessel body)
- Key subassemblies with separate suppliers
- Electronic boards and subsystems

EXCLUDE (not primary components):
- Raw materials (metals, plastics, chemicals) - these are inputs TO components
- Manufacturing tools and equipment
- Consumables (adhesives, fasteners, solvents, lubricants)
- Generic supplies and packaging materials
- Overly generic labels without function (e.g., "Module", "Unit", "System" without a clear function)

CRITICAL INTERPRETATION NOTE:
- Subassemblies are valid components when they represent meaningful dependency boundaries (i.e., manufactured/assembled as discrete units and integrated into the final product).
- Do NOT reject a candidate simply because it is part of a larger assembly; reject it only if it is a raw material, consumable, packaging, a tool, or an overly generic/non-functional label.

Now evaluate:

Technology: {technology}
Candidate component: {component}

Return JSON with:
- plausible: true/false
- rationale: 1-3 sentences, concise and technical
"""


def make_judge_agent(judge_model: str, retries: int) -> Agent:
    return Agent(
        model=judge_model,
        output_type=JudgeVerdict,
        system_prompt="You judge whether a candidate is a plausible primary manufacturing component. Output valid JSON only.",
        retries=retries,
        output_retries=retries,
    )


# -----------------------------
# Cache
# -----------------------------


def load_cache_jsonl(cache_path: Path) -> Dict[str, JudgedRecord]:
    """
    Cache is JSONL with one object per line.
    Latest record per key wins.
    """
    cache: Dict[str, JudgedRecord] = {}
    if not cache_path.exists():
        return cache

    with cache_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            key = str(obj["key"])
            rec = JudgedRecord(
                technology=obj["technology"],
                component=obj["component"],
                plausible=bool(obj["plausible"]),
                rationale=str(obj.get("rationale", "")),
                judged_at_utc=str(obj.get("judged_at_utc", "")),
                judge_model=str(obj.get("judge_model", "")),
            )
            cache[key] = rec
    return cache


def append_cache_jsonl(cache_path: Path, key: CacheKey, rec: JudgedRecord) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "key": key.as_str(),
        "technology": rec.technology,
        "component": rec.component,
        "plausible": rec.plausible,
        "rationale": rec.rationale,
        "judged_at_utc": rec.judged_at_utc,
        "judge_model": rec.judge_model,
    }
    with cache_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


# -----------------------------
# Metrics + reporting
# -----------------------------


def compute_run_metrics(
    run_files: Sequence[RunFile],
    configs: Set[str],
    technologies: Optional[Set[str]],
    cache: Dict[str, JudgedRecord],
) -> List[RunMetrics]:
    """
    Compute per-run invalid rates, using cached judgments.
    """
    out: List[RunMetrics] = []
    for rf in run_files:
        if configs and rf.config not in configs:
            continue
        tech_to_components = load_run_components(rf.path)
        for tech, comps in tech_to_components.items():
            if technologies is not None and tech not in technologies:
                continue

            total = 0
            invalid = 0
            for comp in comps:
                total += 1
                key = CacheKey(technology=tech, component=comp).as_str()
                rec = cache.get(key)
                if rec is None:
                    # Unknown at metrics time; caller should ensure judging completed.
                    continue
                if not rec.plausible:
                    invalid += 1

            invalid_rate = (invalid / total) if total > 0 else None
            out.append(
                RunMetrics(
                    config=rf.config,
                    run_timestamp=rf.timestamp,
                    technology=tech,
                    components_total=total,
                    components_invalid=invalid,
                    invalid_rate=invalid_rate,
                )
            )
    return out


def fmt(x: Any) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def format_md_table(headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(fmt(r.get(h)) for h in headers) + " |")
    return "\n".join(lines) + "\n"


def summarize_variability(run_metrics: Sequence[RunMetrics]) -> Dict[str, Dict[str, Any]]:
    """
    Summarize variability per config over all (technology, run) entries.
    """
    by_cfg: Dict[str, List[float]] = defaultdict(list)
    by_cfg_counts: Dict[str, List[int]] = defaultdict(list)
    for rm in run_metrics:
        if rm.invalid_rate is not None:
            by_cfg[rm.config].append(float(rm.invalid_rate))
        by_cfg_counts[rm.config].append(int(rm.components_total))

    out: Dict[str, Dict[str, Any]] = {}
    for cfg in sorted(set([rm.config for rm in run_metrics])):
        rates = by_cfg.get(cfg, [])
        counts = by_cfg_counts.get(cfg, [])
        out[cfg] = {
            "config": cfg,
            "runs_entries": len([rm for rm in run_metrics if rm.config == cfg]),
            "invalid_rate_median": float(median(rates)) if rates else None,
            "invalid_rate_mean": float(mean(rates)) if rates else None,
            "invalid_rate_min": float(min(rates)) if rates else None,
            "invalid_rate_max": float(max(rates)) if rates else None,
            "component_count_median": float(median(counts)) if counts else None,
            "component_count_mean": float(mean(counts)) if counts else None,
        }
    return out


def write_markdown_report(
    out_path: Path,
    *,
    normalized_dir: Path,
    configs: List[str],
    technologies: Optional[List[str]],
    judge_model: str,
    cache_path: Path,
    judged_new: int,
    judged_cached: int,
    run_metrics: Sequence[RunMetrics],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts: List[str] = []

    parts.append("# Stage 1 Component Validity (Normalized Outputs; Per-Run)\n")
    parts.append(
        "This report uses an LLM judge to label whether each extracted component is a plausible "
        "**primary manufacturing component** for a given technology. Candidates are sourced from "
        "**normalized STDN output CSVs** and evaluated per run. A cache keyed by (technology, component) "
        "avoids repeated judge calls.\n\n"
    )
    parts.append(f"- normalized_dir: `{normalized_dir}`\n")
    parts.append(f"- configs: {', '.join(configs)}\n")
    if technologies:
        parts.append(f"- technologies filter: {', '.join(technologies)}\n")
    parts.append(f"- judge_model: `{judge_model}`\n")
    parts.append(f"- cache: `{cache_path}`\n")
    parts.append(f"- judged_new: {judged_new}\n")
    parts.append(f"- judged_cached: {judged_cached}\n\n")

    # Variability summary by config
    summary = summarize_variability(run_metrics)
    rows = [summary[cfg] for cfg in configs if cfg in summary]
    parts.append("## Per-configuration variability summary (per-run invalid rate)\n\n")
    parts.append(
        format_md_table(
            headers=[
                "config",
                "runs_entries",
                "invalid_rate_median",
                "invalid_rate_mean",
                "invalid_rate_min",
                "invalid_rate_max",
                "component_count_median",
                "component_count_mean",
            ],
            rows=rows,
        )
    )

    # Optional: per-technology paired summary for v1v1v1 vs d3v1v1 if present
    cfg_a = "v1v1v1"
    cfg_b = "d3v1v1"
    if cfg_a in configs and cfg_b in configs:
        parts.append("\n## Per-technology comparison (median invalid rate across runs)\n\n")
        tech_to_cfg_rates: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for rm in run_metrics:
            if rm.invalid_rate is None:
                continue
            tech_to_cfg_rates[rm.technology][rm.config].append(float(rm.invalid_rate))

        comp_rows: List[Dict[str, Any]] = []
        for tech in sorted(tech_to_cfg_rates.keys()):
            ra = tech_to_cfg_rates[tech].get(cfg_a, [])
            rb = tech_to_cfg_rates[tech].get(cfg_b, [])
            ma = float(median(ra)) if ra else None
            mb = float(median(rb)) if rb else None
            delta = (mb - ma) if (ma is not None and mb is not None) else None
            comp_rows.append(
                {
                    "technology": tech,
                    f"{cfg_a}_median_invalid_rate": ma,
                    f"{cfg_b}_median_invalid_rate": mb,
                    "delta_d3_minus_v1": delta,
                }
            )

        parts.append(
            format_md_table(
                headers=[
                    "technology",
                    f"{cfg_a}_median_invalid_rate",
                    f"{cfg_b}_median_invalid_rate",
                    "delta_d3_minus_v1",
                ],
                rows=comp_rows,
            )
        )

    out_path.write_text("".join(parts), encoding="utf-8")


def write_jsonl_records(out_path: Path, records: Sequence[Dict[str, Any]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# -----------------------------
# CLI
# -----------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Judge Stage 1 components from normalized outputs (per-run), with caching. "
            "Intended for variability analysis across configurations."
        )
    )
    p.add_argument(
        "--normalized-dir",
        default="output/normalized",
        help="Directory containing normalized CSV outputs (stdns_output_<config>_<ts>.csv).",
    )
    p.add_argument(
        "--configs",
        nargs="+",
        required=True,
        help="Config tags to include (e.g., v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1).",
    )
    p.add_argument(
        "--technologies",
        nargs="*",
        default=None,
        help="Optional list of technologies to include. If omitted, all technologies in selected runs are used.",
    )
    p.add_argument(
        "--judge-model",
        default="openai:gpt-4.1",
        help="Judge model identifier.",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("STDN_AGENT_RETRIES", "5") or "5"),
        help="Judge agent retry count (defaults to STDN_AGENT_RETRIES or 5).",
    )
    p.add_argument(
        "--cache-jsonl",
        default="output/analysis/stage1_component_judge_cache.jsonl",
        help="JSONL cache file keyed by (technology, component).",
    )
    p.add_argument(
        "--max-judge-items",
        type=int,
        default=0,
        help="Optional cap on number of NEW (uncached) items to judge (0 = no cap).",
    )
    p.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle new items before selecting max-judge-items.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for --shuffle.",
    )
    p.add_argument(
        "--out-md",
        default="output/analysis/stage1_component_judge_normalized.md",
        help="Markdown report output path.",
    )
    p.add_argument(
        "--out-jsonl",
        default="",
        help="Optional JSONL output containing per-candidate judgments (including cached).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call the judge model; just report counts and exit.",
    )
    return p.parse_args(argv)


# -----------------------------
# Main
# -----------------------------


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    normalized_dir = Path(args.normalized_dir)
    if not normalized_dir.exists():
        print(f"ERROR: normalized dir not found: {normalized_dir}", file=sys.stderr)
        return 2

    configs = [c.strip().lower() for c in args.configs if c.strip()]
    config_set = set(configs)
    if not config_set:
        print("ERROR: at least one config is required", file=sys.stderr)
        return 2

    tech_filter = (
        set(t.strip() for t in (args.technologies or []) if t.strip())
        if args.technologies
        else None
    )

    run_files = [rf for rf in iter_run_csvs(normalized_dir) if rf.config in config_set]
    if not run_files:
        print(
            f"ERROR: no run CSVs found for configs={configs} under {normalized_dir}",
            file=sys.stderr,
        )
        return 2

    # Build per-run candidates
    candidates = build_candidates(run_files, config_set, tech_filter)

    # Collapse to unique cache keys; we still compute per-run metrics later from cache
    unique_keys: Dict[str, CacheKey] = {}
    for c in candidates:
        k = CacheKey(technology=_strip(c.technology), component=_strip(c.component))
        unique_keys[k.as_str()] = k

    cache_path = Path(args.cache_jsonl)
    cache = load_cache_jsonl(cache_path)

    # Identify which keys need judging
    missing: List[CacheKey] = [k for kstr, k in unique_keys.items() if kstr not in cache]
    judged_cached = len(unique_keys) - len(missing)

    if args.shuffle:
        random.seed(args.seed)
        random.shuffle(missing)

    if args.max_judge_items and args.max_judge_items > 0 and len(missing) > args.max_judge_items:
        missing = missing[: args.max_judge_items]

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"normalized_dir: {normalized_dir}")
        print(f"configs: {configs}")
        if tech_filter:
            print(f"technologies: {sorted(tech_filter)}")
        print(f"run_files: {len(run_files)}")
        print(f"candidates (per-run): {len(candidates)}")
        print(f"unique (technology, component) keys: {len(unique_keys)}")
        print(f"cached: {judged_cached}")
        print(f"missing (to judge): {len(missing)}")
        print(f"judge_model: {args.judge_model}")
        print(f"cache: {cache_path}")
        return 0

    agent = make_judge_agent(args.judge_model, retries=args.retries)

    judged_new = 0
    judged_records_out: List[Dict[str, Any]] = []

    # Judge missing keys and append to cache
    for idx, key in enumerate(missing, start=1):
        prompt = build_judge_prompt(key.technology, key.component)
        try:
            result = agent.run_sync(prompt)  # pydantic_ai supports sync runner
            verdict = result.output
            rec = JudgedRecord(
                technology=key.technology,
                component=key.component,
                plausible=bool(verdict.plausible),
                rationale=str(verdict.rationale),
                judged_at_utc=datetime.now(timezone.utc).isoformat(),
                judge_model=args.judge_model,
            )
            append_cache_jsonl(cache_path, key, rec)
            cache[key.as_str()] = rec
            judged_new += 1
            judged_records_out.append(
                {
                    "technology": rec.technology,
                    "component": rec.component,
                    "plausible": rec.plausible,
                    "rationale": rec.rationale,
                    "judged_at_utc": rec.judged_at_utc,
                    "judge_model": rec.judge_model,
                    "cache_key": key.as_str(),
                }
            )
        except Exception as e:
            print(
                f"WARNING: judge failed for ({key.technology}, {key.component}): {e}",
                file=sys.stderr,
            )
            continue

        if idx == 1 or idx % 25 == 0 or idx == len(missing):
            print(f"Judged {idx}/{len(missing)} new items...")
            sys.stdout.flush()

    # Compute per-run metrics using the now-complete cache
    run_metrics = compute_run_metrics(run_files, config_set, tech_filter, cache)

    # Write report
    write_markdown_report(
        out_path=Path(args.out_md),
        normalized_dir=normalized_dir,
        configs=configs,
        technologies=sorted(tech_filter) if tech_filter else None,
        judge_model=args.judge_model,
        cache_path=cache_path,
        judged_new=judged_new,
        judged_cached=judged_cached,
        run_metrics=run_metrics,
    )

    # Optional JSONL export of judgments (including cached + newly judged)
    if args.out_jsonl.strip():
        # Emit a compact, deduped list of all keys used in this run.
        all_out: List[Dict[str, Any]] = []
        for kstr, k in unique_keys.items():
            rec = cache.get(kstr)
            if rec is None:
                continue
            all_out.append(
                {
                    "technology": rec.technology,
                    "component": rec.component,
                    "plausible": rec.plausible,
                    "rationale": rec.rationale,
                    "judged_at_utc": rec.judged_at_utc,
                    "judge_model": rec.judge_model,
                    "cache_key": kstr,
                }
            )
        write_jsonl_records(Path(args.out_jsonl), all_out)

    print("\n=== COMPLETE ===")
    print(f"run_files: {len(run_files)}")
    print(f"candidates (per-run): {len(candidates)}")
    print(f"unique (technology, component): {len(unique_keys)}")
    print(f"judged_new: {judged_new}")
    print(f"judged_cached: {judged_cached}")
    print(f"cache: {cache_path}")
    print(f"report: {args.out_md}")
    if args.out_jsonl.strip():
        print(f"judgments_jsonl: {args.out_jsonl}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
