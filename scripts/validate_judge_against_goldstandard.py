#!/usr/bin/env python3
"""
Validate the LLM judge against a human-curated gold standard.

This script:
1. Loads a gold standard CSV (Technology, Component) with known-valid primary components.
2. Normalizes gold standard component names through the same canonical vocab used by the
   pipeline normalization (to ensure apples-to-apples comparison).
3. Loads normalized pipeline outputs and extracts unique (technology, component) pairs.
4. Runs the LLM judge on all unique pairs.
5. Computes precision, recall, F1 against the gold standard:
   - True Positive:  judge says plausible AND component is in gold standard
   - False Positive: judge says plausible AND component is NOT in gold standard
   - True Negative:  judge says implausible AND component is NOT in gold standard
   - False Negative: judge says implausible AND component IS in gold standard
6. Reports per-technology and aggregate metrics.

Note: The gold standard may not be exhaustive. Components not in the gold standard that
the judge labels plausible may actually be valid — the false positive rate is an upper bound.

Usage:
    uv run python scripts/validate_judge_against_goldstandard.py \
      --goldstandard data/goldstndrd.csv \
      --normalized-dir output/normalized \
      --configs v1v1v1 d3v1v1 \
      --judge-model openai:gpt-4.1 \
      --normalization-model openai:gpt-4.1 \
      --out-md output/analysis/judge_validation_vs_goldstandard.md
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from pydantic_ai import Agent

# ---------------------------------------------------------------------------
# Regex for matching normalized output filenames
# ---------------------------------------------------------------------------

_RX_FILE = re.compile(
    r"^stdns_output_(?P<config>[a-z0-9]+)(?:_run\d+)?_(?P<ts>\d{8}_\d{6})\.csv$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class JudgeVerdict(BaseModel):
    plausible: bool = Field(
        description="True if the component is a plausible primary manufacturing component."
    )
    rationale: str = Field(
        description="Short justification for the plausibility decision (1-3 sentences)."
    )


class ComponentMappingResponse(BaseModel):
    mappings: Dict[str, str] = Field(
        description="Mapping from raw component name to canonical primary-component name."
    )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunFile:
    path: Path
    config: str
    timestamp: str


@dataclass
class JudgedRecord:
    technology: str
    component: str
    plausible: bool
    rationale: str
    judged_at_utc: str
    judge_model: str


# ---------------------------------------------------------------------------
# Gold standard loading and normalization
# ---------------------------------------------------------------------------


def load_goldstandard(csv_path: Path) -> Dict[str, Set[str]]:
    """Load gold standard CSV → {technology: {component, ...}}."""
    tech_to_components: Dict[str, Set[str]] = defaultdict(set)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tech = (row.get("Technology") or "").strip()
            comp = (row.get("Component") or "").strip()
            if tech and comp:
                tech_to_components[tech].add(comp)
    return dict(tech_to_components)


def _norm_key(s: str) -> str:
    """Normalize for dict keying (matches normalize_outputs_global_granularity.py)."""
    t = (s or "").strip()
    t = re.sub(r"[\u2013\u2014]", "-", t)
    t = re.sub(r"\s+", " ", t)
    t = t.strip(" \t\r\n.,;:()[]{}")
    return t.lower()


def load_canonical_vocab(path: Path) -> Dict[str, str]:
    """Load the global canonical vocab mappings."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.get("mappings", {}).items()}


async def normalize_goldstandard_components(
    tech_to_components: Dict[str, Set[str]],
    vocab: Dict[str, str],
    model: str,
    retries: int = 5,
) -> Dict[str, Set[str]]:
    """
    Normalize gold standard component names through the canonical vocab.
    Uses LLM for any names not found in the existing vocab.
    Returns {technology: {normalized_component, ...}}.
    """
    NON_PRIMARY = "__NON_PRIMARY__"
    normalized: Dict[str, Set[str]] = defaultdict(set)
    unknown_by_tech: Dict[str, List[str]] = defaultdict(list)

    # First pass: resolve from technology-scoped vocab ONLY (no global fallback)
    for tech, comps in tech_to_components.items():
        for comp in comps:
            # Only use technology-scoped keys to avoid cross-domain mismatches
            tech_key = f"{_norm_key(tech)}|||{_norm_key(comp)}"

            canonical = vocab.get(tech_key)
            if canonical and canonical != NON_PRIMARY:
                normalized[tech].add(canonical)
            elif canonical == NON_PRIMARY:
                # Gold standard item mapped to non-primary — skip but warn
                print(f"  ⚠ Gold standard component mapped to NON_PRIMARY: {tech} / {comp}")
            else:
                unknown_by_tech[tech].append(comp)

    # Second pass: LLM normalize unknowns per technology
    if unknown_by_tech:
        total_unknown = sum(len(v) for v in unknown_by_tech.values())
        print(f"\nNormalizing {total_unknown} unknown gold standard components via LLM...")

        for tech, unknowns in unknown_by_tech.items():
            existing_canonicals = sorted(normalized.get(tech, set()))
            # Also include pipeline canonicals for this technology from vocab
            prefix = f"{_norm_key(tech)}|||"
            tech_canonicals = [
                v for k, v in vocab.items()
                if k.startswith(prefix) and v != NON_PRIMARY
            ]
            all_canonicals = sorted(set(existing_canonicals + tech_canonicals))

            new_mappings = await _llm_normalize_for_goldstandard(
                names=unknowns,
                technology=tech,
                existing_canonicals=all_canonicals,
                model=model,
                retries=retries,
                non_primary_sentinel=NON_PRIMARY,
            )

            for raw, canonical in new_mappings.items():
                if canonical and canonical != NON_PRIMARY:
                    normalized[tech].add(canonical)
                else:
                    print(f"  ⚠ Gold standard component normalized to NON_PRIMARY: {tech} / {raw}")

    return dict(normalized)


async def _llm_normalize_for_goldstandard(
    names: Sequence[str],
    technology: str,
    existing_canonicals: Sequence[str],
    model: str,
    retries: int,
    non_primary_sentinel: str,
) -> Dict[str, str]:
    """Normalize a batch of gold standard component names via LLM."""
    canonical_examples = ""
    if existing_canonicals:
        sample = existing_canonicals[: min(60, len(existing_canonicals))]
        canonical_examples = (
            "\nEXISTING CANONICAL PRIMARY COMPONENT NAMES (use exact spelling when applicable):\n"
            + ", ".join(sample)
            + "\n"
        )

    numbered = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(names))

    prompt = f"""You are a component normalization system for supply chain dependency mapping.

TARGET TECHNOLOGY: {technology}

Goal: Map each RAW component name to a CANONICAL *PRIMARY MANUFACTURING COMPONENT* name.
Primary components are major modules/subsystems that plausibly have distinct supply chains.

IMPORTANT: These are from a human-curated gold standard, so most should map to valid
primary components. Only mark as {non_primary_sentinel} if truly not a primary component.

- Consolidate synonyms/variants to a single canonical form.
- Use Title Case for canonical names.
- If a raw name is a subassembly, map to the nearest primary component.
- Output MUST be valid JSON with a single top-level key "mappings".

{canonical_examples}

RAW NAMES TO NORMALIZE:
{numbered}

Return JSON:
{{
  "mappings": {{
    "<raw_name_1>": "<canonical_primary_component_or_sentinel>",
    ...
  }}
}}
"""

    agent = Agent(
        model=model,
        output_type=ComponentMappingResponse,
        system_prompt=(
            "You normalize component names to canonical primary manufacturing components. "
            "Always respond with valid JSON conforming to the schema."
        ),
        retries=retries,
        output_retries=retries,
    )

    result = await agent.run(prompt)
    if not result or not getattr(result, "output", None):
        return {}

    mapping = dict(result.output.mappings)
    out: Dict[str, str] = {}
    for raw in names:
        canonical = mapping.get(raw, mapping.get(raw.strip(), raw))
        out[raw] = canonical
    return out


# ---------------------------------------------------------------------------
# Pipeline output loading
# ---------------------------------------------------------------------------


def iter_run_csvs(normalized_dir: Path) -> List[RunFile]:
    out = []
    for p in sorted(normalized_dir.glob("stdns_output_*.csv")):
        m = _RX_FILE.match(p.name)
        if not m:
            continue
        out.append(RunFile(path=p, config=m.group("config").lower(), timestamp=m.group("ts")))
    return out


def load_pipeline_components(
    normalized_dir: Path,
    configs: Set[str],
    technologies: Set[str],
) -> Dict[str, Set[str]]:
    """
    Load unique (technology, component) pairs from normalized pipeline outputs.
    Returns {technology: {component, ...}}.
    """
    run_files = iter_run_csvs(normalized_dir)
    tech_to_components: Dict[str, Set[str]] = defaultdict(set)

    for rf in run_files:
        if configs and rf.config not in configs:
            continue
        with rf.path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                continue
            fields = {name.strip().lower(): name for name in reader.fieldnames}
            tech_col = fields.get("technology")
            comp_col = fields.get("component")
            if not tech_col or not comp_col:
                continue
            for row in reader:
                tech = (row.get(tech_col) or "").strip()
                comp = (row.get(comp_col) or "").strip()
                if not tech or not comp:
                    continue
                if technologies and tech not in technologies:
                    continue
                tech_to_components[tech].add(comp)

    return dict(tech_to_components)


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------


def build_judge_prompt(technology: str, component: str) -> str:
    """Same prompt as the existing judge script for consistency."""
    return f"""You are an expert in technology manufacturing and supply chain analysis.

**CRITICAL: Always respond in English.**

**STEP 1: TECHNOLOGY SPECIFICATION**

First, identify the MOST COMMON, INDUSTRY-STANDARD form of the technology requested.

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
- Subassemblies are valid components when they represent meaningful dependency boundaries.
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


# ---------------------------------------------------------------------------
# Cache (reuse existing judge cache)
# ---------------------------------------------------------------------------


def load_cache_jsonl(cache_path: Path) -> Dict[str, JudgedRecord]:
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
            cache[key] = JudgedRecord(
                technology=obj["technology"],
                component=obj["component"],
                plausible=bool(obj["plausible"]),
                rationale=str(obj.get("rationale", "")),
                judged_at_utc=str(obj.get("judged_at_utc", "")),
                judge_model=str(obj.get("judge_model", "")),
            )
    return cache


def append_cache_jsonl(cache_path: Path, key: str, rec: JudgedRecord) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "key": key,
        "technology": rec.technology,
        "component": rec.component,
        "plausible": rec.plausible,
        "rationale": rec.rationale,
        "judged_at_utc": rec.judged_at_utc,
        "judge_model": rec.judge_model,
    }
    with cache_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _cache_key(tech: str, comp: str) -> str:
    return f"{tech.strip()}|||{comp.strip()}"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class ValidationMetrics:
    technology: str
    gold_standard_count: int
    pipeline_count: int
    judged_count: int
    # Judge vs gold standard
    true_positive: int   # judge=plausible AND in gold standard
    false_positive: int  # judge=plausible AND NOT in gold standard
    true_negative: int   # judge=implausible AND NOT in gold standard
    false_negative: int  # judge=implausible AND in gold standard
    precision: Optional[float]
    recall: Optional[float]
    f1: Optional[float]
    # Pipeline coverage of gold standard
    pipeline_recall: Optional[float]  # what fraction of gold standard does pipeline extract?


def compute_metrics(
    tech: str,
    gold_components: Set[str],
    pipeline_components: Set[str],
    cache: Dict[str, JudgedRecord],
) -> ValidationMetrics:
    """Compute validation metrics for a single technology."""
    # All unique components to judge (union of gold standard + pipeline)
    all_components = gold_components | pipeline_components

    tp = fp = tn = fn = 0

    for comp in all_components:
        key = _cache_key(tech, comp)
        rec = cache.get(key)
        if rec is None:
            continue

        in_gold = comp in gold_components
        judge_plausible = rec.plausible

        if judge_plausible and in_gold:
            tp += 1
        elif judge_plausible and not in_gold:
            fp += 1
        elif not judge_plausible and not in_gold:
            tn += 1
        elif not judge_plausible and in_gold:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = (2 * precision * recall / (precision + recall)) if (precision and recall) else None

    # Pipeline recall: how many gold standard components appear in pipeline output?
    pipeline_hits = gold_components & pipeline_components
    pipeline_recall = len(pipeline_hits) / len(gold_components) if gold_components else None

    return ValidationMetrics(
        technology=tech,
        gold_standard_count=len(gold_components),
        pipeline_count=len(pipeline_components),
        judged_count=tp + fp + tn + fn,
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        pipeline_recall=pipeline_recall,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def fmt(x: Any) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def write_markdown_report(
    out_path: Path,
    metrics: List[ValidationMetrics],
    gold_standard: Dict[str, Set[str]],
    pipeline_components: Dict[str, Set[str]],
    cache: Dict[str, JudgedRecord],
    judge_model: str,
    normalization_model: str,
    configs: List[str],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts: List[str] = []

    parts.append("# LLM Judge Validation Against Gold Standard\n\n")
    parts.append(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    parts.append(f"- **Judge model**: `{judge_model}`\n")
    parts.append(f"- **Normalization model**: `{normalization_model}`\n")
    parts.append(f"- **Pipeline configs**: {', '.join(configs)}\n")
    parts.append(f"- **Technologies**: {', '.join(sorted(gold_standard.keys()))}\n\n")

    parts.append("## Methodology\n\n")
    parts.append(
        "The gold standard lists known-valid primary manufacturing components per technology. "
        "Both gold standard and pipeline component names are normalized through the same canonical "
        "vocabulary. The LLM judge is run on the union of gold standard and pipeline components. "
        "Precision/recall/F1 measure how well the judge's plausibility verdicts align with gold "
        "standard membership.\n\n"
    )
    parts.append(
        "**Caveat**: The gold standard may not be exhaustive. Components NOT in the gold standard "
        "that the judge labels plausible may actually be valid — the false positive count is an "
        "upper bound, and precision is a lower bound.\n\n"
    )

    # Per-technology table
    parts.append("## Per-Technology Results\n\n")
    parts.append(
        "| Technology | Gold Std | Pipeline | TP | FP | TN | FN | Precision | Recall | F1 | Pipeline Recall |\n"
    )
    parts.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    for m in metrics:
        parts.append(
            f"| {m.technology} | {m.gold_standard_count} | {m.pipeline_count} | "
            f"{m.true_positive} | {m.false_positive} | {m.true_negative} | {m.false_negative} | "
            f"{fmt(m.precision)} | {fmt(m.recall)} | {fmt(m.f1)} | {fmt(m.pipeline_recall)} |\n"
        )

    # Aggregate
    total_tp = sum(m.true_positive for m in metrics)
    total_fp = sum(m.false_positive for m in metrics)
    total_tn = sum(m.true_negative for m in metrics)
    total_fn = sum(m.false_negative for m in metrics)
    total_gs = sum(m.gold_standard_count for m in metrics)
    total_pipe = sum(m.pipeline_count for m in metrics)

    agg_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else None
    agg_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else None
    agg_f1 = (2 * agg_prec * agg_rec / (agg_prec + agg_rec)) if (agg_prec and agg_rec) else None

    parts.append(
        f"| **AGGREGATE** | {total_gs} | {total_pipe} | "
        f"{total_tp} | {total_fp} | {total_tn} | {total_fn} | "
        f"{fmt(agg_prec)} | {fmt(agg_rec)} | {fmt(agg_f1)} | — |\n"
    )

    # False negatives detail (gold standard items the judge rejected)
    parts.append("\n## False Negatives (Gold Standard Components Judge Rejected)\n\n")
    parts.append("These are components in the gold standard that the judge labeled implausible.\n\n")
    for m in metrics:
        tech = m.technology
        gs = gold_standard.get(tech, set())
        fn_items = []
        for comp in sorted(gs):
            key = _cache_key(tech, comp)
            rec = cache.get(key)
            if rec and not rec.plausible:
                fn_items.append((comp, rec.rationale))
        if fn_items:
            parts.append(f"### {tech}\n\n")
            for comp, rationale in fn_items:
                parts.append(f"- **{comp}**: {rationale}\n")
            parts.append("\n")

    # False positives detail (pipeline-only items the judge accepted)
    parts.append("## False Positives (Pipeline-Only Components Judge Accepted)\n\n")
    parts.append(
        "These are components NOT in the gold standard that the judge labeled plausible. "
        "Some may actually be valid components missing from the gold standard.\n\n"
    )
    for m in metrics:
        tech = m.technology
        gs = gold_standard.get(tech, set())
        pipe = pipeline_components.get(tech, set())
        fp_items = []
        for comp in sorted(pipe - gs):
            key = _cache_key(tech, comp)
            rec = cache.get(key)
            if rec and rec.plausible:
                fp_items.append((comp, rec.rationale))
        if fp_items:
            parts.append(f"### {tech}\n\n")
            for comp, rationale in fp_items:
                parts.append(f"- **{comp}**: {rationale}\n")
            parts.append("\n")

    out_path.write_text("".join(parts), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate LLM judge against gold standard.")
    p.add_argument(
        "--goldstandard", default="data/goldstndrd.csv",
        help="Path to gold standard CSV (Technology, Component).",
    )
    p.add_argument(
        "--normalized-dir", default="output/normalized",
        help="Directory containing normalized CSV outputs.",
    )
    p.add_argument(
        "--configs", nargs="+", required=True,
        help="Config tags to include (e.g., v1v1v1 d3v1v1).",
    )
    p.add_argument(
        "--judge-model", default="openai:gpt-4.1",
        help="Model for the judge.",
    )
    p.add_argument(
        "--normalization-model", default="openai:gpt-4.1",
        help="Model for normalizing gold standard component names.",
    )
    p.add_argument(
        "--global-vocab", default="data/component_canonical_vocab.json",
        help="Path to canonical vocab JSON.",
    )
    p.add_argument(
        "--cache-jsonl", default="output/analysis/stage1_component_judge_cache.jsonl",
        help="JSONL cache file (shared with judge script).",
    )
    p.add_argument(
        "--retries", type=int, default=5,
        help="Agent retry count.",
    )
    p.add_argument(
        "--out-md", default="output/analysis/judge_validation_vs_goldstandard.md",
        help="Markdown report output path.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Do not call judge; just report counts.",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def async_main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # 1. Load gold standard
    gs_path = Path(args.goldstandard)
    if not gs_path.exists():
        print(f"ERROR: gold standard not found: {gs_path}", file=sys.stderr)
        return 2
    raw_gold = load_goldstandard(gs_path)
    print(f"Gold standard: {sum(len(v) for v in raw_gold.values())} components across {len(raw_gold)} technologies")
    for tech, comps in sorted(raw_gold.items()):
        print(f"  {tech}: {len(comps)} components (before dedup/normalization)")

    # 2. Load canonical vocab and normalize gold standard
    vocab = load_canonical_vocab(Path(args.global_vocab))
    print(f"\nCanonical vocab: {len(vocab)} mappings loaded from {args.global_vocab}")

    gold_standard = await normalize_goldstandard_components(
        raw_gold, vocab, args.normalization_model, args.retries
    )
    print(f"\nNormalized gold standard:")
    for tech, comps in sorted(gold_standard.items()):
        print(f"  {tech}: {len(comps)} unique canonical components")
        for comp in sorted(comps):
            print(f"    - {comp}")

    # 3. Load pipeline components
    configs = set(c.strip().lower() for c in args.configs)
    technologies = set(gold_standard.keys())
    pipeline_components = load_pipeline_components(
        Path(args.normalized_dir), configs, technologies
    )
    print(f"\nPipeline components ({', '.join(sorted(configs))}):")
    for tech, comps in sorted(pipeline_components.items()):
        print(f"  {tech}: {len(comps)} unique components")

    # 4. Build set of all (tech, component) pairs to judge
    all_pairs: List[Tuple[str, str]] = []
    for tech in technologies:
        gs_comps = gold_standard.get(tech, set())
        pipe_comps = pipeline_components.get(tech, set())
        for comp in gs_comps | pipe_comps:
            all_pairs.append((tech, comp))

    print(f"\nTotal unique (technology, component) pairs to judge: {len(all_pairs)}")

    # 5. Load cache and find missing
    cache_path = Path(args.cache_jsonl)
    cache = load_cache_jsonl(cache_path)
    missing = [(t, c) for t, c in all_pairs if _cache_key(t, c) not in cache]
    cached = len(all_pairs) - len(missing)
    print(f"Cached: {cached}, Need judging: {len(missing)}")

    if args.dry_run:
        print("\n=== DRY RUN — exiting ===")
        return 0

    # 6. Judge missing pairs
    if missing:
        agent = make_judge_agent(args.judge_model, retries=args.retries)
        for idx, (tech, comp) in enumerate(missing, start=1):
            prompt = build_judge_prompt(tech, comp)
            try:
                result = await agent.run(prompt)
                verdict = result.output
                rec = JudgedRecord(
                    technology=tech,
                    component=comp,
                    plausible=bool(verdict.plausible),
                    rationale=str(verdict.rationale),
                    judged_at_utc=datetime.now(timezone.utc).isoformat(),
                    judge_model=args.judge_model,
                )
                key = _cache_key(tech, comp)
                append_cache_jsonl(cache_path, key, rec)
                cache[key] = rec
            except Exception as e:
                print(f"WARNING: judge failed for ({tech}, {comp}): {e}", file=sys.stderr)
                continue

            if idx == 1 or idx % 25 == 0 or idx == len(missing):
                print(f"Judged {idx}/{len(missing)} items...")
                sys.stdout.flush()

    # 7. Compute metrics
    metrics = []
    for tech in sorted(technologies):
        gs_comps = gold_standard.get(tech, set())
        pipe_comps = pipeline_components.get(tech, set())
        m = compute_metrics(tech, gs_comps, pipe_comps, cache)
        metrics.append(m)

    # 8. Write report
    write_markdown_report(
        out_path=Path(args.out_md),
        metrics=metrics,
        gold_standard=gold_standard,
        pipeline_components=pipeline_components,
        cache=cache,
        judge_model=args.judge_model,
        normalization_model=args.normalization_model,
        configs=sorted(configs),
    )

    # 9. Print summary
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    for m in metrics:
        print(f"\n{m.technology}:")
        print(f"  Gold standard: {m.gold_standard_count} | Pipeline: {m.pipeline_count}")
        print(f"  TP={m.true_positive} FP={m.false_positive} TN={m.true_negative} FN={m.false_negative}")
        print(f"  Precision={fmt(m.precision)} Recall={fmt(m.recall)} F1={fmt(m.f1)}")
        print(f"  Pipeline recall of gold standard: {fmt(m.pipeline_recall)}")

    total_tp = sum(m.true_positive for m in metrics)
    total_fp = sum(m.false_positive for m in metrics)
    total_tn = sum(m.true_negative for m in metrics)
    total_fn = sum(m.false_negative for m in metrics)
    agg_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else None
    agg_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else None
    agg_f1 = (2 * agg_prec * agg_rec / (agg_prec + agg_rec)) if (agg_prec and agg_rec) else None

    print(f"\nAGGREGATE:")
    print(f"  TP={total_tp} FP={total_fp} TN={total_tn} FN={total_fn}")
    print(f"  Precision={fmt(agg_prec)} Recall={fmt(agg_rec)} F1={fmt(agg_f1)}")

    print(f"\nReport: {args.out_md}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
