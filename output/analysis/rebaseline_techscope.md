# Re-baseline under per-technology normalization (pass A primary, pass B replication)

## Table 1 (tab:ablation-norm): naive single-shot vs naive + per-technology normalization

60 microelectronics technologies × 5 runs (`output/naive_micro`). Median over technologies of the per-technology pairwise Jaccard; 95% bootstrap CI (10,000 resamples, unit = technology). #components = per-technology union over the 5 runs.

| Configuration | n | Median Jaccard (per-tech median pairwise) | Same, per-tech mean pairwise (April definition) | Median #components (union) |
|---|---|---|---|---|
| Naive single-shot (raw names) | 60 | 0.134 (0.11–0.17) | 0.146 (0.12–0.18) | 39.500 (37.00–43.50) |
| Naive + normalization (pass A) | 60 | 0.692 (0.64–0.75) | 0.692 (0.64–0.74) | 15.000 (15.00–16.50) |
| Naive + normalization (pass B) | 60 | 0.667 (0.63–0.71) | 0.666 (0.62–0.71) | 16.000 (15.00–17.00) |

## Table 2 (tab:ablation-debate): debate vs single agent, per-technology normalization

Per-technology median pairwise Jaccard; Δ = median of per-technology (debate − v1) with 95% bootstrap CI; imp/wor/tied counts; Wilcoxon two-sided p on per-technology differences.


### Pass A, submitted session, v1 vs d3

| Domain | n | v1 median | d3 median | Δ [95% CI] | imp/wor/tied | Wilcoxon p |
|---|---|---|---|---|---|---|
| microelectronics | 60 | 0.675 | 0.528 | -0.099 [-0.134, -0.071] | 9/49/2 | 3.8e-08 |
| biotech | 60 | 0.667 | 0.594 | -0.035 [-0.080, +0.000] | 22/36/2 | 0.0061 |
| pharma | 58 | 0.629 | 0.528 | -0.103 [-0.140, -0.010] | 21/37/0 | 0.003 |
| Combined | 178 | 0.658 | 0.550 | -0.076 [-0.106, -0.042] | 52/122/4 | 6.9e-11 |

### Pass A, submitted session, v1 vs d5

| Domain | n | v1 median | d5 median | Δ [95% CI] | imp/wor/tied | Wilcoxon p |
|---|---|---|---|---|---|---|
| microelectronics | 60 | 0.675 | 0.585 | -0.058 [-0.088, -0.021] | 16/42/2 | 0.00025 |
| biotech | 60 | 0.667 | 0.672 | +0.042 [+0.002, +0.105] | 39/21/0 | 0.051 |
| pharma | 58 | 0.629 | 0.610 | -0.016 [-0.051, +0.030] | 25/31/2 | 0.48 |
| Combined | 178 | 0.658 | 0.635 | -0.014 [-0.039, +0.007] | 80/94/4 | 0.2 |

### Pass A, post-fix session, v1 vs d3

| Domain | n | v1 median | d3 median | Δ [95% CI] | imp/wor/tied | Wilcoxon p |
|---|---|---|---|---|---|---|
| microelectronics | 60 | 0.667 | 0.571 | -0.052 [-0.111, +0.000] | 21/36/3 | 0.019 |
| biotech | 60 | 0.683 | 0.598 | -0.101 [-0.125, -0.047] | 14/42/4 | 0.00022 |
| pharma | 60 | 0.656 | 0.567 | -0.058 [-0.111, -0.023] | 18/41/1 | 0.00046 |
| Combined | 180 | 0.667 | 0.581 | -0.069 [-0.105, -0.039] | 53/119/8 | 1.4e-08 |

### Pass B, submitted session, v1 vs d3

| Domain | n | v1 median | d3 median | Δ [95% CI] | imp/wor/tied | Wilcoxon p |
|---|---|---|---|---|---|---|
| microelectronics | 60 | 0.667 | 0.536 | -0.098 [-0.134, -0.064] | 10/49/1 | 7.6e-09 |
| biotech | 60 | 0.600 | 0.567 | -0.012 [-0.068, +0.019] | 26/30/4 | 0.065 |
| pharma | 58 | 0.583 | 0.541 | -0.045 [-0.094, +0.018] | 25/33/0 | 0.027 |
| Combined | 178 | 0.625 | 0.541 | -0.059 [-0.086, -0.035] | 61/112/5 | 1.3e-08 |

### Pass B, submitted session, v1 vs d5

| Domain | n | v1 median | d5 median | Δ [95% CI] | imp/wor/tied | Wilcoxon p |
|---|---|---|---|---|---|---|
| microelectronics | 60 | 0.667 | 0.600 | -0.076 [-0.116, -0.037] | 13/45/2 | 3.6e-05 |
| biotech | 60 | 0.600 | 0.668 | +0.044 [+0.008, +0.102] | 39/20/1 | 0.0053 |
| pharma | 58 | 0.583 | 0.604 | +0.009 [-0.021, +0.060] | 31/27/0 | 0.56 |
| Combined | 178 | 0.625 | 0.633 | -0.014 [-0.024, +0.014] | 83/92/3 | 0.73 |

### Pass B, post-fix session, v1 vs d3

| Domain | n | v1 median | d3 median | Δ [95% CI] | imp/wor/tied | Wilcoxon p |
|---|---|---|---|---|---|---|
| microelectronics | 60 | 0.667 | 0.595 | -0.019 [-0.078, +0.006] | 23/33/4 | 0.086 |
| biotech | 60 | 0.635 | 0.581 | -0.072 [-0.106, -0.028] | 18/39/3 | 0.0014 |
| pharma | 60 | 0.651 | 0.571 | -0.103 [-0.140, -0.039] | 16/43/1 | 2.8e-05 |
| Combined | 180 | 0.652 | 0.582 | -0.071 [-0.089, -0.035] | 57/115/8 | 1e-07 |

## Core ratio (micro): intersection across 5 runs / median run size, macro median over technologies

| Pass | v1 | d3 | d5 | n (v1/d3/d5) |
|---|---|---|---|---|
| A | 0.625 | 0.400 | 0.400 | 60/53/55 |
| B | 0.625 | 0.400 | 0.429 | 60/53/55 |

Submitted (old global vocab): v1 0.429, d3 0.200.

