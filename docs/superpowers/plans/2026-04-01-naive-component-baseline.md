# Naive Single-Shot Component Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a script that runs a generic LLM prompt for component extraction on 4 gold-standard technologies (5 runs each), then evaluates against the gold standard with and without canonical normalization.

**Architecture:** Single script (`scripts/naive_component_baseline.py`) that: (1) calls `gpt-4.1-mini` with a deliberately simple prompt, (2) parses free-text output into component lists, (3) runs the existing judge on all components, (4) optionally normalizes through the canonical vocab, (5) computes metrics and writes reports. Reuses judge infrastructure from `validate_judge_against_goldstandard.py`.

**Tech Stack:** Python 3.9+, pydantic-ai, asyncio, existing judge/normalization utilities from the codebase.

---

### Task 1: Script skeleton with CLI and naive LLM extraction

**Files:**
- Create: `scripts/naive_component_baseline.py`

- [ ] **Step 1: Create the script with imports, CLI args, and the naive extraction function**

```python
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

    # 1. Load gold standard and normalize
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
            out_file = output_dir / f"naive_components_{_norm_key(tech).replace(' ', '_')}_{run_idx + 1}.json"
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
        for comp in raw_unions[tech] | gold_standard.get(tech, set()):
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
        gs_comps = gold_standard.get(tech, set())
        naive_comps = raw_unions[tech]
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
        for comp in norm_unions[tech] | gold_standard.get(tech, set()):
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
        gs_comps = gold_standard.get(tech, set())
        naive_comps = norm_unions[tech]
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

    # Aggregate judge metrics
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
```

- [ ] **Step 2: Verify the script parses without errors**

Run: `cd /Users/ads7fg/git/dpi_stdn_agentic && uv run python -c "import ast; ast.parse(open('scripts/naive_component_baseline.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Verify imports resolve**

Run: `cd /Users/ads7fg/git/dpi_stdn_agentic && uv run python -c "import sys; sys.path.insert(0, 'scripts'); from naive_component_baseline import parse_component_list; print('imports OK')"`
Expected: `imports OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/ads7fg/git/dpi_stdn_agentic
git add scripts/naive_component_baseline.py
git commit -m "feat: add naive single-shot component baseline script"
```

---

### Task 2: Test the parser on realistic LLM output

**Files:**
- Modify: `scripts/naive_component_baseline.py` (only if parser needs fixing)

- [ ] **Step 1: Test parse_component_list with realistic inputs**

Run:
```bash
cd /Users/ads7fg/git/dpi_stdn_agentic && uv run python -c "
import sys; sys.path.insert(0, 'scripts')
from naive_component_baseline import parse_component_list

# Numbered list
text1 = '''Here are the primary manufacturing components of a Smartphone:

1. Display Module
2. Battery
3. System-on-Chip (SoC)
4. Camera Module
5. Printed Circuit Board (PCB)
6. Antenna
7. Speaker
8. Microphone
'''
result1 = parse_component_list(text1)
print('Numbered:', result1)
assert len(result1) == 8, f'Expected 8, got {len(result1)}'
assert result1[0] == 'Display Module'

# Bullet list
text2 = '''- Vacuum System
- Shelf System
- Condenser
- Control System
- Refrigeration Unit
'''
result2 = parse_component_list(text2)
print('Bullets:', result2)
assert len(result2) == 5, f'Expected 5, got {len(result2)}'

# Mixed with preamble
text3 = '''The primary manufacturing components of a Rotary Tablet Press include:

* Turret
* Dies
* Punches
* Cam System
* Feeder
* Control Panel
* Motor and Drive System
'''
result3 = parse_component_list(text3)
print('Mixed:', result3)
assert 'Turret' in result3
# The preamble line should be filtered out
assert not any('include' in c.lower() for c in result3)

print('All parser tests passed')
"
```
Expected: `All parser tests passed`

- [ ] **Step 2: Fix any parser issues found, or confirm no changes needed**

If parser tests pass, no changes needed. If a test fails, adjust the `parse_component_list` function and re-test.

---

### Task 3: Run the full baseline

**Files:**
- No file changes (running existing script)

- [ ] **Step 1: Run the naive baseline**

Run:
```bash
cd /Users/ads7fg/git/dpi_stdn_agentic && uv run python scripts/naive_component_baseline.py \
  --extraction-model openai:gpt-4.1-mini \
  --judge-model openai:gpt-4.1 \
  --normalization-model openai:gpt-4.1 \
  --runs 5
```

Expected: Script completes, printing extraction counts per run, judge progress, and final summary table. Creates:
- `output/naive/naive_components_*.json` (20 files: 4 techs x 5 runs)
- `output/analysis/naive_baseline_raw.md`
- `output/analysis/naive_baseline_normalized.md`

- [ ] **Step 2: Verify output files exist**

Run:
```bash
ls -la /Users/ads7fg/git/dpi_stdn_agentic/output/naive/ | head -25
ls -la /Users/ads7fg/git/dpi_stdn_agentic/output/analysis/naive_baseline_*.md
```

Expected: 20 JSON files in `output/naive/`, 2 markdown reports in `output/analysis/`.

- [ ] **Step 3: Spot-check one raw JSON output**

Run: `cat /Users/ads7fg/git/dpi_stdn_agentic/output/naive/naive_components_smartphone_1.json | python -m json.tool | head -20`

Expected: JSON with `technology`, `run`, `model`, `prompt`, `timestamp_utc`, `components` (list of strings).

- [ ] **Step 4: Review the raw report**

Run: `cat /Users/ads7fg/git/dpi_stdn_agentic/output/analysis/naive_baseline_raw.md`

Check that:
- Extraction summary table has all 4 technologies with union sizes, stability
- Judge validation table has TP/FP/TN/FN and aggregate row
- No obvious errors (negative numbers, missing values)

- [ ] **Step 5: Review the normalized report**

Run: `cat /Users/ads7fg/git/dpi_stdn_agentic/output/analysis/naive_baseline_normalized.md`

Check that:
- Union sizes are smaller than raw (normalization should consolidate)
- Jaccard stability should be different from raw
- Judge metrics should differ from raw (normalized names may match different cache entries)

- [ ] **Step 6: Commit results**

```bash
cd /Users/ads7fg/git/dpi_stdn_agentic
git add output/naive/ output/analysis/naive_baseline_raw.md output/analysis/naive_baseline_normalized.md
git commit -m "data: naive component baseline results (4 techs, 5 runs, raw + normalized)"
```
