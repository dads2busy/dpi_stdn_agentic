# Naive Component Baseline (Normalized)

Evaluation of naive single-shot LLM extraction against gold standard. Component names normalized through canonical vocabulary before evaluation.

- **Date**: 2026-04-01 12:30
- **Extraction model**: `openai:gpt-4.1-mini`
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Runs per technology**: 5
- **Prompt**: `What are the primary manufacturing components of a {technology}? List each component on its own line.`

## Extraction Summary

| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |
| --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 12 | 8.8 | 8 | 10 | 0.683 |
| Rotary tablet press | 10 | 8.0 | 7 | 9 | 0.825 |
| Single-use bioreactor | 11 | 8.8 | 8 | 10 | 0.749 |
| Smartphone | 18 | 16.4 | 15 | 17 | 0.897 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 7 | 12 | 7 | 8 | 0 | 0 | 0.467 | 1.000 | 0.636 |
| Rotary tablet press | 10 | 10 | 10 | 7 | 0 | 0 | 0.588 | 1.000 | 0.741 |
| Single-use bioreactor | 11 | 11 | 10 | 9 | 1 | 1 | 0.526 | 0.909 | 0.667 |
| Smartphone | 17 | 18 | 17 | 13 | 1 | 0 | 0.567 | 1.000 | 0.723 |
| **AGGREGATE** | 45 | 51 | 44 | 37 | 2 | 1 | 0.543 | 0.978 | 0.698 |
