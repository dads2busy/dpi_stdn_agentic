# Naive Component Baseline (Engineered, Raw)

Evaluation of single-shot LLM extraction (prompt style: engineered) against gold standard. Component names used as-is from LLM output (no canonical normalization).

- **Date**: 2026-05-14 16:05
- **Prompt style**: `engineered`
- **Extraction model**: `openai:gpt-4.1-mini`
- **Judge model**: `openai:gpt-4.1`
- **Normalization model**: `openai:gpt-4.1`
- **Runs per technology**: 5
- **System prompt**: `You are an expert in industrial supply chain analysis.`
- **User prompt**: `List the primary physical hardware components of a {technology}, excluding raw materials, software, and services. Return as a JSON array of component names.`

## Extraction Summary

| Technology | Union | Mean/run | Min | Max | Stability (Jaccard) |
| --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 53 | 15.4 | 14 | 17 | 0.162 |
| Rotary tablet press | 54 | 16.2 | 13 | 20 | 0.164 |
| Single-use bioreactor | 48 | 11.6 | 10 | 13 | 0.078 |
| Smartphone | 52 | 20.0 | 18 | 23 | 0.324 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 7 | 53 | 7 | 43 | 8 | 0 | 0.140 | 1.000 | 0.246 |
| Rotary tablet press | 10 | 54 | 10 | 46 | 3 | 0 | 0.179 | 1.000 | 0.303 |
| Single-use bioreactor | 10 | 48 | 10 | 41 | 7 | 0 | 0.196 | 1.000 | 0.328 |
| Smartphone | 19 | 52 | 19 | 44 | 1 | 0 | 0.302 | 1.000 | 0.463 |
| **AGGREGATE** | 46 | 207 | 46 | 174 | 19 | 0 | 0.209 | 1.000 | 0.346 |
