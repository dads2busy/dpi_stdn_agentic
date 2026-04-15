# Naive Component Baseline (Normalized)

Evaluation of naive single-shot LLM extraction against gold standard. Component names normalized through canonical vocabulary before evaluation.

- **Date**: 2026-04-15 09:06
- **Extraction model**: `openai:gpt-4.1-mini`
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Runs per technology**: 5
- **Prompt**: `What are the primary manufacturing components of a {technology}? List each component on its own line.`

## Extraction Summary

| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |
| --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 12 | 9.4 | 9 | 11 | 0.817 |
| Rotary tablet press | 17 | 11.8 | 11 | 13 | 0.649 |
| Single-use bioreactor | 10 | 7.8 | 7 | 9 | 0.783 |
| Smartphone | 21 | 17.4 | 14 | 19 | 0.749 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 8 | 12 | 8 | 8 | 0 | 0 | 0.500 | 1.000 | 0.667 |
| Rotary tablet press | 10 | 17 | 10 | 12 | 0 | 0 | 0.455 | 1.000 | 0.625 |
| Single-use bioreactor | 9 | 10 | 9 | 9 | 0 | 0 | 0.500 | 1.000 | 0.667 |
| Smartphone | 20 | 21 | 19 | 13 | 0 | 1 | 0.594 | 0.950 | 0.731 |
| **AGGREGATE** | 47 | 60 | 46 | 42 | 0 | 1 | 0.523 | 0.979 | 0.681 |
