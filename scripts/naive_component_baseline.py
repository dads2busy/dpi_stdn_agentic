#!/usr/bin/env python3
"""
Naive single-shot component baseline for KDD paper.

Sends a generic prompt to an LLM for each gold-standard technology, 5 runs each.
No role conditioning, no confidence scoring, no exclusion rules.
Evaluates against gold standard with and without canonical normalization.

Usage:
    uv run python scripts/naive_component_baseline.py
    uv run python scripts/naive_component_baseline.py --extraction-model openai:gpt-4.1-mini --runs 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

load_dotenv()

from pydantic_ai import Agent

# Reuse from existing validation script
from validate_judge_against_goldstandard import (
    JudgeVerdict,
    JudgedRecord,
    ValidationMetrics,
    _cache_key,
    append_cache_jsonl,
    build_judge_prompt,
    compute_metrics,
    fmt,
    load_cache_jsonl,
    load_canonical_vocab,
    load_goldstandard,
    make_judge_agent,
    normalize_goldstandard_components,
)

# Reuse normalization utilities from the normalization script
from normalize_outputs_global_granularity import (
    ComponentMappingResponse,
    _norm_key,
    load_global_vocab,
    make_vocab_key,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NAIVE_PROMPT = (
    "What are the primary manufacturing components of a {technology}? "
    "List each component on its own line."
)

DEFAULT_GOLDSTANDARD = "data/goldstndrd.csv"
DEFAULT_VOCAB = "data/component_canonical_vocab.json"
DEFAULT_GLOBAL_VOCAB = "data/component_canonical_vocab_global_primary.json"
DEFAULT_CACHE = "output/analysis/stage1_component_judge_cache.jsonl"
DEFAULT_OUTPUT_DIR = "output/naive"
DEFAULT_ANALYSIS_DIR = "output/analysis"

# ---------------------------------------------------------------------------
# Naive extraction
# ---------------------------------------------------------------------------


def parse_component_list(raw_text: str) -> List[str]:
    """Parse free-text LLM output into a list of component names.

    Handles numbered lists, bullet points, and plain lines.
    """
    components = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip leading bullets, numbers, dashes
        line = re.sub(r"^[\d]+[.):\-]\s*", "", line)
        line = re.sub(r"^[-*•]\s*", "", line)
        line = line.strip()
        if not line:
            continue
        # Skip lines that look like headers or preamble (no component is >100 chars)
        if len(line) > 100:
            continue
        # Skip lines that are clearly prose (contain "the following" etc.)
        if any(phrase in line.lower() for phrase in [
            "the following", "here are", "primary manufacturing", "components of",
            "listed below", "include:",
        ]):
            continue
        components.append(line)
    return components


async def run_naive_extraction(
    technology: str,
    model: str,
    num_runs: int,
    retries: int,
) -> List[List[str]]:
    """Run the naive prompt num_runs times and return parsed component lists."""
    agent = Agent(
        model=model,
        system_prompt="You are a helpful assistant.",
        retries=retries,
    )

    all_runs: List[List[str]] = []
    for run_idx in range(num_runs):
        prompt = NAIVE_PROMPT.format(technology=technology)
        result = await agent.run(prompt)
        raw_text = result.output  # str when no output_type specified
        components = parse_component_list(raw_text)
        all_runs.append(components)
        print(f"  Run {run_idx + 1}: {len(components)} components")
    return all_runs


# ---------------------------------------------------------------------------
# Normalization of naive output through canonical vocab
# ---------------------------------------------------------------------------


async def normalize_naive_components(
    tech: str,
    components: Set[str],
    vocab: Dict[str, str],
    model: str,
    retries: int,
) -> Dict[str, str]:
    """Normalize naive component names through canonical vocab + LLM fallback.

    Returns {raw_name: canonical_name} mapping.
    """
    NON_PRIMARY = "__NON_PRIMARY__"
    mapping: Dict[str, str] = {}
    unknowns: List[str] = []

    # First pass: check technology-scoped vocab
    for comp in components:
        tech_key = f"{_norm_key(tech)}|||{_norm_key(comp)}"
        canonical = vocab.get(tech_key)
        if canonical:
            mapping[comp] = canonical
        else:
            unknowns.append(comp)

    # Second pass: LLM for unknowns
    if unknowns:
        # Gather existing canonicals for this technology
        prefix = f"{_norm_key(tech)}|||"
        tech_canonicals = sorted(set(
            v for k, v in vocab.items()
            if k.startswith(prefix) and v != NON_PRIMARY
        ))

        numbered = "\n".join(f"{i + 1}. {n}" for i, n in enumerate(unknowns))
        canonical_examples = ""
        if tech_canonicals:
            sample = tech_canonicals[:60]
            canonical_examples = (
                "\nEXISTING CANONICAL PRIMARY COMPONENT NAMES (use exact spelling when applicable):\n"
                + ", ".join(sample)
                + "\n"
            )

        prompt = f"""You are a component normalization system for supply chain dependency mapping.

TARGET TECHNOLOGY: {tech}

Goal: Map each RAW component name to a CANONICAL *PRIMARY MANUFACTURING COMPONENT* name.
Primary components are major modules/subsystems that plausibly have distinct supply chains.

- Consolidate synonyms/variants to a single canonical form.
- Use Title Case for canonical names.
- If a raw name is a subassembly, map to the nearest primary component.
- If a raw name is NOT a primary manufacturing component (e.g., a raw material,
  consumable, or overly generic label), map it to {NON_PRIMARY}.
- Output MUST be valid JSON with a single top-level key "mappings".

{canonical_examples}

RAW NAMES TO NORMALIZE:
{numbered}

Return JSON:
{{
  "mappings": {{
    "<raw_name_1>": "<canonical_primary_component_or_{NON_PRIMARY}>",
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
        if result and result.output:
            for raw in unknowns:
                canonical = result.output.mappings.get(raw, raw)
                mapping[raw] = canonical

    return mapping


# ---------------------------------------------------------------------------
# Stability (pairwise Jaccard)
# ---------------------------------------------------------------------------


def pairwise_jaccard(runs: List[Set[str]]) -> float:
    """Compute mean pairwise Jaccard similarity across runs."""
    if len(runs) < 2:
        return 1.0
    jaccards = []
    for a, b in combinations(runs, 2):
        if not a and not b:
            jaccards.append(1.0)
        elif not a or not b:
            jaccards.append(0.0)
        else:
            jaccards.append(len(a & b) / len(a | b))
    return mean(jaccards)


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------


def write_report(
    out_path: Path,
    title: str,
    description: str,
    tech_results: Dict[str, Dict[str, Any]],
    metrics_list: List[ValidationMetrics],
    extraction_model: str,
    judge_model: str,
    normalization_model: str,
    num_runs: int,
) -> None:
    """Write a markdown evaluation report."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts: List[str] = []

    parts.append(f"# {title}\n\n")
    parts.append(f"{description}\n\n")
    parts.append(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    parts.append(f"- **Extraction model**: `{extraction_model}`\n")
    parts.append(f"- **Judge model**: `{judge_model}`\n")
    parts.append(f"- **Normalization model**: `{normalization_model}`\n")
    parts.append(f"- **Runs per technology**: {num_runs}\n")
    parts.append(f"- **Prompt**: `{NAIVE_PROMPT}`\n\n")

    # Extraction summary
    parts.append("## Extraction Summary\n\n")
    parts.append("| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |\n")
    parts.append("| --- | --- | --- | --- | --- | --- |\n")
    for tech in sorted(tech_results.keys()):
        r = tech_results[tech]
        parts.append(
            f"| {tech} | {r['union_size']} | {r['mean_per_run']:.1f} | "
            f"{r['min_per_run']} | {r['max_per_run']} | {r['jaccard']:.3f} |\n"
        )

    # Judge validation
    parts.append("\n## Judge Validation Against Gold Standard\n\n")
    parts.append(
        "| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |\n"
    )
    parts.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )
    for m in metrics_list:
        parts.append(
            f"| {m.technology} | {m.gold_standard_count} | {m.pipeline_count} | "
            f"{m.true_positive} | {m.false_positive} | {m.true_negative} | {m.false_negative} | "
            f"{fmt(m.precision)} | {fmt(m.recall)} | {fmt(m.f1)} |\n"
        )

    # Aggregate
    total_tp = sum(m.true_positive for m in metrics_list)
    total_fp = sum(m.false_positive for m in metrics_list)
    total_tn = sum(m.true_negative for m in metrics_list)
    total_fn = sum(m.false_negative for m in metrics_list)
    total_gs = sum(m.gold_standard_count for m in metrics_list)
    total_naive = sum(m.pipeline_count for m in metrics_list)
    agg_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else None
    agg_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else None
    agg_f1 = (2 * agg_prec * agg_rec / (agg_prec + agg_rec)) if (agg_prec and agg_rec) else None

    parts.append(
        f"| **AGGREGATE** | {total_gs} | {total_naive} | "
        f"{total_tp} | {total_fp} | {total_tn} | {total_fn} | "
        f"{fmt(agg_prec)} | {fmt(agg_rec)} | {fmt(agg_f1)} |\n"
    )

    out_path.write_text("".join(parts), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Naive single-shot component extraction baseline."
    )
    p.add_argument(
        "--extraction-model", default="openai:gpt-4.1-mini",
        help="Model for naive extraction.",
    )
    p.add_argument(
        "--judge-model", default="openai:gpt-4.1",
        help="Model for the judge.",
    )
    p.add_argument(
        "--normalization-model", default="openai:gpt-4.1",
        help="Model for normalizing component names.",
    )
    p.add_argument(
        "--goldstandard", default=DEFAULT_GOLDSTANDARD,
        help="Path to gold standard CSV.",
    )
    p.add_argument(
        "--tech-list", default=None,
        help="Path to tech list CSV (domain,tech,role columns). "
             "When provided, runs on these techs instead of gold standard. "
             "Gold standard comparison is skipped.",
    )
    p.add_argument(
        "--global-vocab", default=DEFAULT_VOCAB,
        help="Path to canonical vocab JSON (for gold standard normalization).",
    )
    p.add_argument(
        "--naive-vocab", default=DEFAULT_GLOBAL_VOCAB,
        help="Path to global primary vocab JSON (for naive output normalization).",
    )
    p.add_argument(
        "--cache-jsonl", default=DEFAULT_CACHE,
        help="JSONL judge cache (shared with other scripts).",
    )
    p.add_argument(
        "--runs", type=int, default=5,
        help="Number of runs per technology.",
    )
    p.add_argument(
        "--retries", type=int, default=5,
        help="Agent retry count.",
    )
    p.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR,
        help="Directory for per-run JSON outputs.",
    )
    p.add_argument(
        "--analysis-dir", default=DEFAULT_ANALYSIS_DIR,
        help="Directory for analysis reports.",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def async_main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # 1. Load technologies (from tech list or gold standard)
    if args.tech_list:
        import csv as csv_mod
        tl_path = Path(args.tech_list)
        if not tl_path.exists():
            print(f"ERROR: tech list not found: {tl_path}", file=sys.stderr)
            return 2
        with open(tl_path, newline="", encoding="utf-8") as fh:
            reader = csv_mod.DictReader(fh)
            technologies = sorted(set(row["tech"].strip() for row in reader if row.get("tech", "").strip()))
        gold_standard = None
        print(f"Tech list: {len(technologies)} technologies (gold standard comparison skipped)")
    else:
        gs_path = Path(args.goldstandard)
        if not gs_path.exists():
            print(f"ERROR: gold standard not found: {gs_path}", file=sys.stderr)
            return 2
        raw_gold = load_goldstandard(gs_path)
        technologies = sorted(raw_gold.keys())
        print(f"Gold standard: {len(technologies)} technologies")

        vocab = load_canonical_vocab(Path(args.global_vocab))
        gold_standard = await normalize_goldstandard_components(
            raw_gold, vocab, args.normalization_model, args.retries
        )
        print(f"Normalized gold standard: {sum(len(v) for v in gold_standard.values())} components")

    # 2. Run naive extraction
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # {tech: [[run1_components], [run2_components], ...]}
    all_extractions: Dict[str, List[List[str]]] = {}

    for tech in technologies:
        print(f"\nExtracting: {tech}")
        runs = await run_naive_extraction(
            technology=tech,
            model=args.extraction_model,
            num_runs=args.runs,
            retries=args.retries,
        )
        all_extractions[tech] = runs

        # Save per-run JSON
        for run_idx, components in enumerate(runs):
            safe_name = _norm_key(tech).replace(' ', '_').replace('/', '_')
            out_file = output_dir / f"naive_components_{safe_name}_{run_idx + 1}.json"
            out_file.write_text(json.dumps({
                "technology": tech,
                "run": run_idx + 1,
                "model": args.extraction_model,
                "prompt": NAIVE_PROMPT.format(technology=tech),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "components": components,
            }, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. Build union sets (raw) per technology
    raw_unions: Dict[str, Set[str]] = {}
    raw_run_sets: Dict[str, List[Set[str]]] = {}
    for tech, runs in all_extractions.items():
        sets = [set(r) for r in runs]
        raw_run_sets[tech] = sets
        raw_unions[tech] = set().union(*sets) if sets else set()

    # 4. Judge all raw components
    cache_path = Path(args.cache_jsonl)
    cache = load_cache_jsonl(cache_path)

    all_raw_pairs: List[Tuple[str, str]] = []
    for tech in technologies:
        gs_comps = gold_standard.get(tech, set()) if gold_standard is not None else set()
        for comp in raw_unions[tech] | gs_comps:
            all_raw_pairs.append((tech, comp))

    missing = [(t, c) for t, c in all_raw_pairs if _cache_key(t, c) not in cache]
    print(f"\nJudging: {len(missing)} new items ({len(all_raw_pairs)} total, {len(all_raw_pairs) - len(missing)} cached)")

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
            if idx == 1 or idx % 25 == 0 or idx == len(missing):
                print(f"  Judged {idx}/{len(missing)}")
                sys.stdout.flush()

    # 5. Compute raw metrics + stability
    raw_tech_results: Dict[str, Dict[str, Any]] = {}
    raw_metrics: List[ValidationMetrics] = []
    for tech in technologies:
        naive_comps = raw_unions[tech]

        if gold_standard is not None:
            gs_comps = gold_standard.get(tech, set())
            m = compute_metrics(tech, gs_comps, naive_comps, cache)
            raw_metrics.append(m)

        run_sizes = [len(s) for s in raw_run_sets[tech]]
        raw_tech_results[tech] = {
            "union_size": len(naive_comps),
            "mean_per_run": mean(run_sizes) if run_sizes else 0,
            "min_per_run": min(run_sizes) if run_sizes else 0,
            "max_per_run": max(run_sizes) if run_sizes else 0,
            "jaccard": pairwise_jaccard(raw_run_sets[tech]),
        }

    # 6. Write raw report
    analysis_dir = Path(args.analysis_dir)
    write_report(
        out_path=analysis_dir / "naive_baseline_raw.md",
        title="Naive Component Baseline (Raw)",
        description=(
            "Evaluation of naive single-shot LLM extraction against gold standard. "
            "Component names used as-is from LLM output (no canonical normalization)."
        ),
        tech_results=raw_tech_results,
        metrics_list=raw_metrics,
        extraction_model=args.extraction_model,
        judge_model=args.judge_model,
        normalization_model=args.normalization_model,
        num_runs=args.runs,
    )
    print(f"\nRaw report: {analysis_dir / 'naive_baseline_raw.md'}")

    # 7. Normalize naive output through canonical vocab
    print("\nNormalizing naive output through canonical vocab...")
    naive_vocab = load_global_vocab(Path(args.naive_vocab))
    print(f"Loaded {len(naive_vocab)} vocab mappings from {args.naive_vocab}")

    NON_PRIMARY = "__NON_PRIMARY__"
    norm_run_sets: Dict[str, List[Set[str]]] = {}
    norm_unions: Dict[str, Set[str]] = {}

    for tech in technologies:
        all_raw = raw_unions[tech]
        mapping = await normalize_naive_components(
            tech=tech,
            components=all_raw,
            vocab=naive_vocab,
            model=args.normalization_model,
            retries=args.retries,
        )

        # Apply mapping to each run
        tech_norm_sets = []
        for run_set in raw_run_sets[tech]:
            normed = set()
            for comp in run_set:
                canonical = mapping.get(comp, comp)
                if canonical and canonical != NON_PRIMARY:
                    normed.add(canonical)
            tech_norm_sets.append(normed)
        norm_run_sets[tech] = tech_norm_sets
        norm_unions[tech] = set().union(*tech_norm_sets) if tech_norm_sets else set()
        print(f"  {tech}: {len(all_raw)} raw -> {len(norm_unions[tech])} normalized")

    # 8. Judge normalized components (some may be new cache keys)
    all_norm_pairs: List[Tuple[str, str]] = []
    for tech in technologies:
        gs_comps = gold_standard.get(tech, set()) if gold_standard is not None else set()
        for comp in norm_unions[tech] | gs_comps:
            all_norm_pairs.append((tech, comp))

    missing_norm = [(t, c) for t, c in all_norm_pairs if _cache_key(t, c) not in cache]
    if missing_norm:
        print(f"\nJudging {len(missing_norm)} newly normalized items...")
        agent = make_judge_agent(args.judge_model, retries=args.retries)
        for idx, (tech, comp) in enumerate(missing_norm, start=1):
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
            if idx == 1 or idx % 25 == 0 or idx == len(missing_norm):
                print(f"  Judged {idx}/{len(missing_norm)}")
                sys.stdout.flush()

    # 9. Compute normalized metrics + stability
    norm_tech_results: Dict[str, Dict[str, Any]] = {}
    norm_metrics: List[ValidationMetrics] = []
    for tech in technologies:
        naive_comps = norm_unions[tech]

        if gold_standard is not None:
            gs_comps = gold_standard.get(tech, set())
            m = compute_metrics(tech, gs_comps, naive_comps, cache)
            norm_metrics.append(m)

        run_sizes = [len(s) for s in norm_run_sets[tech]]
        norm_tech_results[tech] = {
            "union_size": len(naive_comps),
            "mean_per_run": mean(run_sizes) if run_sizes else 0,
            "min_per_run": min(run_sizes) if run_sizes else 0,
            "max_per_run": max(run_sizes) if run_sizes else 0,
            "jaccard": pairwise_jaccard(norm_run_sets[tech]),
        }

    # 10. Write normalized report
    write_report(
        out_path=analysis_dir / "naive_baseline_normalized.md",
        title="Naive Component Baseline (Normalized)",
        description=(
            "Evaluation of naive single-shot LLM extraction against gold standard. "
            "Component names normalized through canonical vocabulary before evaluation."
        ),
        tech_results=norm_tech_results,
        metrics_list=norm_metrics,
        extraction_model=args.extraction_model,
        judge_model=args.judge_model,
        normalization_model=args.normalization_model,
        num_runs=args.runs,
    )
    print(f"Normalized report: {analysis_dir / 'naive_baseline_normalized.md'}")

    # 11. Print summary comparison
    print("\n" + "=" * 70)
    print("SUMMARY: NAIVE BASELINE")
    print("=" * 70)
    print(f"\n{'':30s} {'RAW':>20s} {'NORMALIZED':>20s}")
    print("-" * 70)
    for tech in technologies:
        rr = raw_tech_results[tech]
        nr = norm_tech_results[tech]
        print(f"{tech:30s} union={rr['union_size']:>3d} J={rr['jaccard']:.3f}   union={nr['union_size']:>3d} J={nr['jaccard']:.3f}")

    # Aggregate judge metrics (only when gold standard is available)
    if gold_standard is not None:
        for label, mlist in [("Raw", raw_metrics), ("Normalized", norm_metrics)]:
            tp = sum(m.true_positive for m in mlist)
            fp = sum(m.false_positive for m in mlist)
            tn = sum(m.true_negative for m in mlist)
            fn = sum(m.false_negative for m in mlist)
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0
            print(f"\n{label} aggregate: TP={tp} FP={fp} TN={tn} FN={fn} Prec={prec:.3f} Rec={rec:.3f}")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
