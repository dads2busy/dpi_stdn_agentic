# Naive Component Baseline (Naive, Raw)

Evaluation of single-shot LLM extraction (prompt style: naive) against gold standard. Component names used as-is from LLM output (no canonical normalization).

- **Date**: 2026-05-14 16:13
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
| Pharmaceutical Lyophilizer | 47 | 12.4 | 12 | 13 | 0.106 |
| Rotary tablet press | 38 | 13.0 | 10 | 16 | 0.278 |
| Single-use bioreactor | 38 | 9.0 | 8 | 10 | 0.042 |
| Smartphone | 45 | 17.4 | 15 | 20 | 0.290 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 8 | 47 | 8 | 43 | 2 | 0 | 0.157 | 1.000 | 0.271 |
| Rotary tablet press | 9 | 38 | 9 | 36 | 0 | 0 | 0.200 | 1.000 | 0.333 |
| Single-use bioreactor | 10 | 38 | 9 | 36 | 2 | 1 | 0.200 | 0.900 | 0.327 |
| Smartphone | 17 | 45 | 17 | 41 | 1 | 0 | 0.293 | 1.000 | 0.453 |
| **AGGREGATE** | 44 | 168 | 43 | 156 | 5 | 1 | 0.216 | 0.977 | 0.354 |
