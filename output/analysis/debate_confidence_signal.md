# Debate-utility Test 1: confidence as an uncertainty signal

Pre-registration: docs/prereg/2026-11-18-debate-utility.md. AUC of component confidence vs 'canonical recurs in >= k of 5 runs', within technology, averaged. Δ = debate − v1 over technologies with AUCs in both; 95% bootstrap CI.


## Vocab techscope_a, label: >=3 of 5 (primary)

| dataset | domain | files v1/debate | n techs | AUC v1 | AUC debate | Δ [95% CI] |
|---|---|---|---|---|---|---|
| post-fix (primary) | microelectronics | 5/5 | 57 | 0.658 | 0.589 | -0.069 [-0.137, +0.004] |
| post-fix (primary) | biotech | 5/5 | 53 | 0.682 | 0.672 | -0.010 [-0.070, +0.050] |
| post-fix (primary) | pharma | 5/5 | 52 | 0.699 | 0.757 | +0.058 [+0.005, +0.110] |
| submitted (replication) | microelectronics | 5/5 | 48 | 0.662 | 0.602 | -0.060 [-0.131, +0.005] |
| submitted (replication) | biotech | 5/5 | 31 | 0.696 | 0.702 | +0.006 [-0.073, +0.078] |
| submitted (replication) | pharma | 5/5 | 27 | 0.739 | 0.700 | -0.039 [-0.106, +0.024] |
| d5 vs v1, submitted (secondary) | microelectronics | 5/5 | 48 | 0.670 | 0.603 | -0.067 [-0.123, -0.008] |
| d5 vs v1, submitted (secondary) | biotech | 5/5 | 37 | 0.689 | 0.652 | -0.037 [-0.107, +0.026] |
| d5 vs v1, submitted (secondary) | pharma | 5/5 | 31 | 0.742 | 0.708 | -0.034 [-0.106, +0.035] |

## Vocab techscope_a, label: all 5 (secondary)

| dataset | domain | files v1/debate | n techs | AUC v1 | AUC debate | Δ [95% CI] |
|---|---|---|---|---|---|---|
| post-fix (primary) | microelectronics | 5/5 | 58 | 0.677 | 0.623 | -0.054 [-0.122, +0.014] |
| post-fix (primary) | biotech | 5/5 | 55 | 0.739 | 0.668 | -0.071 [-0.145, -0.001] |
| post-fix (primary) | pharma | 5/5 | 54 | 0.754 | 0.742 | -0.013 [-0.074, +0.042] |
| submitted (replication) | microelectronics | 5/5 | 48 | 0.683 | 0.583 | -0.100 [-0.180, -0.016] |
| submitted (replication) | biotech | 5/5 | 28 | 0.705 | 0.634 | -0.071 [-0.157, +0.011] |
| submitted (replication) | pharma | 5/5 | 28 | 0.728 | 0.687 | -0.041 [-0.143, +0.050] |
| d5 vs v1, submitted (secondary) | microelectronics | 5/5 | 53 | 0.670 | 0.615 | -0.055 [-0.123, +0.010] |
| d5 vs v1, submitted (secondary) | biotech | 5/5 | 37 | 0.689 | 0.708 | +0.019 [-0.050, +0.085] |
| d5 vs v1, submitted (secondary) | pharma | 5/5 | 31 | 0.739 | 0.707 | -0.032 [-0.109, +0.040] |

## Vocab techscope_b, label: >=3 of 5 (primary)

| dataset | domain | files v1/debate | n techs | AUC v1 | AUC debate | Δ [95% CI] |
|---|---|---|---|---|---|---|
| post-fix (primary) | microelectronics | 5/5 | 56 | 0.648 | 0.611 | -0.037 [-0.100, +0.027] |
| post-fix (primary) | biotech | 5/5 | 57 | 0.687 | 0.670 | -0.017 [-0.082, +0.046] |
| post-fix (primary) | pharma | 5/5 | 53 | 0.696 | 0.764 | +0.067 [+0.014, +0.125] |
| submitted (replication) | microelectronics | 5/5 | 49 | 0.654 | 0.632 | -0.022 [-0.080, +0.035] |
| submitted (replication) | biotech | 5/5 | 28 | 0.697 | 0.687 | -0.010 [-0.091, +0.057] |
| submitted (replication) | pharma | 5/5 | 26 | 0.705 | 0.714 | +0.009 [-0.053, +0.085] |
| d5 vs v1, submitted (secondary) | microelectronics | 5/5 | 51 | 0.655 | 0.617 | -0.038 [-0.107, +0.030] |
| d5 vs v1, submitted (secondary) | biotech | 5/5 | 37 | 0.686 | 0.665 | -0.021 [-0.096, +0.049] |
| d5 vs v1, submitted (secondary) | pharma | 5/5 | 33 | 0.723 | 0.690 | -0.033 [-0.119, +0.054] |

## Vocab techscope_b, label: all 5 (secondary)

| dataset | domain | files v1/debate | n techs | AUC v1 | AUC debate | Δ [95% CI] |
|---|---|---|---|---|---|---|
| post-fix (primary) | microelectronics | 5/5 | 59 | 0.662 | 0.648 | -0.013 [-0.081, +0.055] |
| post-fix (primary) | biotech | 5/5 | 55 | 0.696 | 0.666 | -0.030 [-0.114, +0.050] |
| post-fix (primary) | pharma | 5/5 | 52 | 0.745 | 0.719 | -0.026 [-0.087, +0.035] |
| submitted (replication) | microelectronics | 5/5 | 47 | 0.684 | 0.559 | -0.124 [-0.204, -0.047] |
| submitted (replication) | biotech | 5/5 | 29 | 0.728 | 0.633 | -0.095 [-0.170, -0.030] |
| submitted (replication) | pharma | 5/5 | 29 | 0.727 | 0.672 | -0.056 [-0.166, +0.044] |
| d5 vs v1, submitted (secondary) | microelectronics | 5/5 | 52 | 0.665 | 0.589 | -0.075 [-0.143, -0.008] |
| d5 vs v1, submitted (secondary) | biotech | 5/5 | 38 | 0.702 | 0.687 | -0.015 [-0.081, +0.050] |
| d5 vs v1, submitted (secondary) | pharma | 5/5 | 33 | 0.724 | 0.677 | -0.047 [-0.154, +0.052] |
