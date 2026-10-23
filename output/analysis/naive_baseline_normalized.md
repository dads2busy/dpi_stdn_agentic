# Naive Component Baseline (Naive, Normalized)

Evaluation of single-shot LLM extraction (prompt style: naive) against gold standard. Component names normalized through canonical vocabulary before evaluation.

- **Date**: 2026-05-14 16:14
- **Prompt style**: `naive`
- **Extraction model**: `openai:gpt-4.1-mini`
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Runs per technology**: 5
- **System prompt**: `You are a helpful assistant.`
- **User prompt**: `What are the primary manufacturing components of a {technology}? List each component on its own line.`

## Extraction Summary

| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |
| --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 10 | 8.8 | 8 | 10 | 0.896 |
| Rotary tablet press | 15 | 12.2 | 10 | 13 | 0.732 |
| Single-use bioreactor | 10 | 8.8 | 8 | 9 | 0.837 |
| Smartphone | 19 | 15.8 | 13 | 18 | 0.756 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 8 | 10 | 8 | 5 | 0 | 0 | 0.615 | 1.000 | 0.762 |
| Rotary tablet press | 9 | 15 | 9 | 11 | 0 | 0 | 0.450 | 1.000 | 0.621 |
| Single-use bioreactor | 10 | 10 | 9 | 9 | 0 | 1 | 0.500 | 0.900 | 0.643 |
| Smartphone | 17 | 19 | 17 | 8 | 2 | 0 | 0.680 | 1.000 | 0.810 |
| **AGGREGATE** | 44 | 54 | 43 | 33 | 2 | 1 | 0.566 | 0.977 | 0.717 |
