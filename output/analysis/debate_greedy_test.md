# Debate-utility Test 3: debate under near-greedy sampling

Pre-registration: docs/prereg/2026-11-18-debate-utility.md. Values are medians over technologies; CIs bootstrap the median over technologies; p = paired Wilcoxon.


## Normalization pass a

| level | v1 @default | d3 @default | v1 @greedy | d3 @greedy | Δ@default (p) | Δ@greedy (p) | interaction [95% CI] |
|---|---|---|---|---|---|---|---|
| canonical (n=24) | 0.646 | 0.646 | 0.798 | 0.762 | -0.051 (0.082) | -0.035 (0.1) | -0.013 [-0.104, +0.099] (p=0.73) |

Secondary: v1 stability change default → greedy (canonical): +0.172 (p=0.00042); mean Δ@greedy = -0.053, mean interaction = -0.014

| raw (n=24) | 0.069 | 0.191 | 0.336 | 0.373 | +0.087 (2.4e-06) | +0.012 (0.68) | -0.054 [-0.226, +0.015] (p=0.028) |

## Normalization pass b

| level | v1 @default | d3 @default | v1 @greedy | d3 @greedy | Δ@default (p) | Δ@greedy (p) | interaction [95% CI] |
|---|---|---|---|---|---|---|---|
| canonical (n=24) | 0.667 | 0.600 | 0.798 | 0.782 | -0.023 (0.4) | -0.035 (0.084) | -0.003 [-0.054, +0.058] (p=0.71) |

Secondary: v1 stability change default → greedy (canonical): +0.163 (p=0.00019); mean Δ@greedy = -0.055, mean interaction = -0.032

| raw (n=24) | 0.069 | 0.191 | 0.336 | 0.373 | +0.087 (2.4e-06) | +0.012 (0.68) | -0.054 [-0.226, +0.015] (p=0.028) |
