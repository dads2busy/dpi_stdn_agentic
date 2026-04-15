# Naive Component Baseline (Raw)

Evaluation of naive single-shot LLM extraction against gold standard. Component names used as-is from LLM output (no canonical normalization).

- **Date**: 2026-04-15 09:05
- **Extraction model**: `openai:gpt-4.1-mini`
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Runs per technology**: 5
- **Prompt**: `What are the primary manufacturing components of a {technology}? List each component on its own line.`

## Extraction Summary

| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |
| --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 42 | 11.8 | 10 | 13 | 0.139 |
| Rotary tablet press | 41 | 12.6 | 11 | 14 | 0.167 |
| Single-use bioreactor | 38 | 8.8 | 8 | 10 | 0.043 |
| Smartphone | 52 | 18.2 | 14 | 21 | 0.216 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 8 | 42 | 8 | 34 | 5 | 0 | 0.190 | 1.000 | 0.320 |
| Rotary tablet press | 10 | 41 | 10 | 37 | 0 | 0 | 0.213 | 1.000 | 0.351 |
| Single-use bioreactor | 9 | 38 | 9 | 34 | 4 | 0 | 0.209 | 1.000 | 0.346 |
| Smartphone | 20 | 52 | 19 | 48 | 1 | 1 | 0.284 | 0.950 | 0.437 |
| **AGGREGATE** | 47 | 173 | 46 | 153 | 10 | 1 | 0.231 | 0.979 | 0.374 |
