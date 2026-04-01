# Naive Component Baseline (Raw)

Evaluation of naive single-shot LLM extraction against gold standard. Component names used as-is from LLM output (no canonical normalization).

- **Date**: 2026-04-01 12:29
- **Extraction model**: `openai:gpt-4.1-mini`
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Runs per technology**: 5
- **Prompt**: `What are the primary manufacturing components of a {technology}? List each component on its own line.`

## Extraction Summary

| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |
| --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 46 | 11.4 | 10 | 13 | 0.088 |
| Rotary tablet press | 35 | 12.8 | 12 | 14 | 0.284 |
| Single-use bioreactor | 38 | 9.2 | 8 | 10 | 0.053 |
| Smartphone | 58 | 18.0 | 15 | 20 | 0.171 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 7 | 46 | 7 | 39 | 4 | 0 | 0.152 | 1.000 | 0.264 |
| Rotary tablet press | 10 | 35 | 10 | 32 | 0 | 0 | 0.238 | 1.000 | 0.385 |
| Single-use bioreactor | 11 | 38 | 10 | 37 | 1 | 1 | 0.213 | 0.909 | 0.345 |
| Smartphone | 17 | 58 | 17 | 56 | 1 | 0 | 0.233 | 1.000 | 0.378 |
| **AGGREGATE** | 45 | 177 | 44 | 164 | 6 | 1 | 0.212 | 0.978 | 0.348 |
