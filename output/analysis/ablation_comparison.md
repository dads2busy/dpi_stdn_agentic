# Ablation Comparison: Pipeline Layer Contributions

- **Date**: 2026-04-15 11:36
- **Naive raw**: `output/analysis/naive_baseline_raw.md`
- **Naive normalized**: `output/analysis/naive_baseline_normalized.md`
- **Raw stability JSON**: `output/analysis/ablation_raw_v1v1v1_stability.json`
- **Raw judge MD**: `output/analysis/ablation_raw_v1v1v1_judge.md`
- **Sweet-spot CSV**: `output/analysis/micro_sweet_spot_by_n.csv`

## Layer comparison

| Layer | Stability (median Jaccard) | Invalid rate (median) | Components (median) |
| --- | --- | --- | --- |
| Naive raw | 0.146 | — | 39.5 |
| Naive + normalization | 0.756 | — | 12.0 |
| Structured raw (v1v1v1) | 0.067 | 0.000 | — |
| Structured + normalization (v1v1v1) | 0.073 | 0.011 | 5.0 |
| Structured + norm + debate (d3v1v1) | 0.147 | 0.000 | 4.0 |

## Marginal contributions

| Transition | Δ Stability | Δ Invalid rate |
| --- | --- | --- |
| Normalization (1→2) | +0.610 | — |
| Structured extraction (2→4) | -0.683 | — |
| Normalization on structured (3→4) | +0.006 | +0.011 |
| Debate (4→5) | +0.074 | -0.011 |
