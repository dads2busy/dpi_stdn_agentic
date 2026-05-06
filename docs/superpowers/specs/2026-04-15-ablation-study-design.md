# Ablation study: contribution of each pipeline layer

**Date:** 2026-04-15
**Purpose:** Quantify the contribution of each pipeline layer (normalization, structured extraction, debate) to output quality across the 61-tech microelectronics set.

## Layers

| Layer | Description | Data |
|---|---|---|
| 1. Naive raw | Bare LLM extraction, no structure, no normalization | New: extend naive baseline to 61 techs |
| 2. Naive normalized | Naive extraction + canonical normalization | New: normalize naive outputs |
| 3. Structured raw | Pipeline v1v1v1 without normalization | Existing: raw v1v1v1 files, need judge run |
| 4. Structured normalized | Pipeline v1v1v1 + normalization | Existing: from microelectronics rerun |
| 5. Structured + debate normalized | Pipeline d3v1v1 + normalization | Existing: from microelectronics rerun |

## Metrics per layer

- Stability: pairwise Jaccard similarity across 5 runs per technology, macro-median across techs
- Validity: judge-based invalid rate (occurrence-based and dedup-canonical), using openai:gpt-4.1
- Component count: median unique components per technology

## Work required

### 1. Extend naive_component_baseline.py

The script currently reads technologies from the gold standard CSV. Add a `--tech-list` argument that accepts an arbitrary tech list CSV (same format as pipeline input: domain,tech,role columns). When provided, extract the tech column and run naive extraction on those technologies. When not provided, fall back to gold standard behavior.

Judge validation against gold standard is only meaningful for the 4 gold standard techs, so skip gold standard comparison when using `--tech-list`. Instead, just run extraction + judge + stability on whatever techs are provided.

### 2. Run naive extraction on 61 microelectronics techs

```bash
uv run python scripts/naive_component_baseline.py \
  --tech-list data/tech_list_microelectronic_products.csv \
  --extraction-model openai:gpt-4.1-mini \
  --runs 5 \
  --analysis-dir output/analysis
```

5 runs x 61 techs = 305 simple extractions. Output: per-run component lists as JSONL + stability/judge reports.

### 3. Normalize naive outputs

Run the naive outputs through the same normalization pipeline and canonical vocabulary used for the pipeline outputs:

```bash
uv run python scripts/normalize_outputs_global_granularity.py \
  --pattern "output/naive_baseline_micro/*.csv" \
  --global-vocab data/component_canonical_vocab_global_primary.json \
  --model openai:gpt-4.1
```

This requires the naive baseline script to write per-run CSVs in a format the normalization script can consume, or a conversion step.

### 4. Judge raw v1v1v1 files

Run the judge on the un-normalized v1v1v1 raw files:

```bash
uv run python scripts/judge_stage1_components_from_normalized_outputs.py \
  --normalized-dir output/raw/ \
  --configs v1v1v1 \
  --judge-model openai:gpt-4.1 \
  --out-md output/analysis/ablation_raw_v1v1v1_judge.md \
  --out-jsonl output/analysis/ablation_raw_v1v1v1_judge.jsonl
```

Note: the judge script expects "normalized" dir but works on any CSVs with the same column format. Raw pipeline CSVs have the same schema.

### 5. Compute stability for naive raw and naive normalized

Reuse the stability analysis script or compute inline in the extended naive baseline script.

### 6. Produce comparison table

A script or section in the naive baseline script that produces a single table:

| Layer | Stability (median) | Invalid rate occ (median) | Invalid rate dedup (median) | Components (median) |
|---|---|---|---|---|
| Naive raw | ? | ? | ? | ? |
| Naive normalized | ? | ? | ? | ? |
| Structured raw (v1v1v1) | ? | ? | ? | ? |
| Structured normalized (v1v1v1) | ? | ? | ? | ? |
| Structured + debate (d3v1v1) | ? | ? | ? | ? |

## Output

- `output/analysis/ablation_comparison.md` - the comparison table
- `output/analysis/ablation_naive_micro_raw.md` - naive raw results
- `output/analysis/ablation_naive_micro_normalized.md` - naive normalized results
- `output/analysis/ablation_raw_v1v1v1_judge.md` - raw v1v1v1 judge results
