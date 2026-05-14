# Naive Component Baseline (Engineered, Normalized)

Evaluation of single-shot LLM extraction (prompt style: engineered) against gold standard. Component names normalized through canonical vocabulary before evaluation.

- **Date**: 2026-05-14 16:06
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
| Pharmaceutical Lyophilizer | 10 | 9.6 | 9 | 10 | 0.940 |
| Rotary tablet press | 17 | 12.6 | 11 | 14 | 0.629 |
| Single-use bioreactor | 9 | 8.0 | 7 | 9 | 0.863 |
| Smartphone | 20 | 17.2 | 16 | 18 | 0.892 |

## Judge Validation Against Gold Standard

| Technology | Gold Std | Naive | TP | FP | TN | FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pharmaceutical Lyophilizer | 7 | 10 | 7 | 8 | 0 | 0 | 0.467 | 1.000 | 0.636 |
| Rotary tablet press | 10 | 17 | 10 | 14 | 0 | 0 | 0.417 | 1.000 | 0.588 |
| Single-use bioreactor | 10 | 9 | 10 | 6 | 0 | 0 | 0.625 | 1.000 | 0.769 |
| Smartphone | 19 | 20 | 19 | 11 | 2 | 0 | 0.633 | 1.000 | 0.776 |
| **AGGREGATE** | 46 | 56 | 46 | 39 | 2 | 0 | 0.541 | 1.000 | 0.702 |
