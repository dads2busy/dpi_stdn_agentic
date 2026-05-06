# Naive Single-Shot Component Baseline

## Purpose

Provide an external baseline for the KDD paper by measuring the gap between "just ask an LLM" and the full STDN-GEN pipeline for Stage 1 component extraction. Without this baseline, the paper only compares configurations of the same system (v1v1v1 vs d3v1v1), which reviewers will flag as self-referential.

## Script

`scripts/naive_component_baseline.py`

## Design

### Prompt

Deliberately generic. No role conditioning, no confidence scoring, no exclusion rules, no structured output schema:

> "What are the primary manufacturing components of a {technology}? List each component on its own line."

Free-text response, parsed into one component name per line. Strip numbering, bullets, and blank lines.

### Technologies

The 4 gold-standard technologies from `data/goldstndrd.csv`:
- Pharmaceutical Lyophilizer
- Rotary tablet press
- Single-use bioreactor
- Smartphone

### Runs

5 runs per technology (matching existing pipeline validation).

### Models

- Extraction: `openai:gpt-4.1-mini` (matches pipeline extraction model)
- Judge: `openai:gpt-4.1` (matches existing judge)
- Normalization: `openai:gpt-4.1` (matches existing normalization model)

### Two evaluation passes

**Pass 1 -- Raw:** Judge and gold-standard comparison on raw component names. Only minimal string cleanup (strip whitespace, remove bullets/numbering). No canonical vocabulary normalization.

**Pass 2 -- Normalized:** Pass naive output through the canonical vocabulary + LLM normalization (same process as the pipeline uses), then re-evaluate with identical metrics.

### Metrics (same as existing validation)

Per-technology and aggregate:
- TP, FP, TN, FN against gold standard via judge
- Precision (raw), Recall
- Pairwise Jaccard across 5 runs (stability)
- Component count per run (min, mean, max)
- Union size across 5 runs

### Output artifacts

- `output/naive/naive_components_{technology}_{run}.json` -- per-run raw outputs (component list + metadata)
- `output/analysis/naive_baseline_raw.md` -- evaluation report on raw names
- `output/analysis/naive_baseline_normalized.md` -- evaluation report after normalization

### Reuse from existing code

- Judge agent and prompt from `validate_judge_against_goldstandard.py` (same judge, same JSONL cache)
- Canonical vocab normalization logic from `normalize_outputs_global_granularity.py`
- Model routing via pydantic-ai (`openai:` prefix)
- Gold standard loading from `data/goldstndrd.csv`

### Does not reuse

- Component agent prompt (that is what we are testing against)
- Debate/orchestration machinery
- Confidence scoring or structured output schema (ComponentList pydantic model)

## What this proves

If the pipeline outperforms the naive baseline on judge metrics and stability: the pipeline engineering (structured prompts, debate, normalization) adds value beyond what the LLM provides out of the box.

If the normalized naive baseline approaches the pipeline: the value is primarily in normalization, not extraction. Also a publishable finding.
