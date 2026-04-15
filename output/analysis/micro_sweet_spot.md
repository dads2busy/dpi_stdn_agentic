# Sweet-spot tradeoff summary (Stage 1)

Macro-summary across technologies (equal weight; values are macro-median and macro-mean across (tech,N)).

| N | Techs | Stability (median) | Stability (mean) | Stability mean 95% CI | Δ Stability mean vs N=1 (95% CI) | Δ Stability median vs N=1 (95% CI) | Not-plausible occ (median) | Not-plausible occ (mean) | Not-plausible occ mean 95% CI | Δ Not-plausible occ mean vs N=1 (95% CI) | Δ Not-plausible occ median vs N=1 (95% CI) | % techs improved (occ invalid) | Precision occ (median) | Precision occ (mean) | Not-plausible dedup-canon (median) | Not-plausible dedup-canon (mean) | Not-plausible dedup-canon mean 95% CI | Δ Not-plausible dedup-canon mean vs N=1 (95% CI) | Δ Not-plausible dedup-canon median vs N=1 (95% CI) | % techs improved (dedup invalid) | Precision dedup-canon (median) | Precision dedup-canon (mean) | #Components (median) | #Components (mean) | #Components mean 95% CI | Δ #Components mean vs N=1 (95% CI) | Δ #Components median vs N=1 (95% CI) | Silver recall (median) | Silver recall (mean) | Silver recall mean 95% CI | Δ Silver recall mean vs N=1 (95% CI) | Δ Silver recall median vs N=1 (95% CI) | Final conv (median) | Final conv (mean) | Final conv mean 95% CI | Δ Final conv mean vs N=1 (95% CI) | Δ Final conv median vs N=1 (95% CI) | Rounds (median) | Rounds (mean) | Rounds mean 95% CI | Δ Rounds mean vs N=1 (95% CI) | Δ Rounds median vs N=1 (95% CI) | Runtime (median) | Runtime (mean) | Runtime mean 95% CI | Δ Runtime mean vs N=1 (95% CI) | Δ Runtime median vs N=1 (95% CI) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 66 | 0.073 | 0.107 | [0.079, 0.144] | NA | NA | 0.011 | 0.063 | [0.040, 0.089] | NA | NA | NA | 0.989 | 0.937 | 0.000 | 0.061 | [0.037, 0.089] | NA | NA | NA | 1.000 | 0.939 | 5.00 | 4.72 | [4.38, 5.07] | NA | NA | 0.500 | 0.528 | [0.491, 0.569] | NA | NA | 0.887 | 0.887 | [0.883, 0.891] | NA | NA | 1.00 | 1.00 | [1.00, 1.00] | NA | NA | 57s | 57s | [0.9m, 0.9m] | NA | NA |
| 2 | 66 | 0.113 | 0.151 | [0.119, 0.190] | [0.019, 0.060] | [0.020, 0.064] | 0.040 | 0.073 | [0.052, 0.097] | [-0.010, 0.030] | [-0.017, 0.053] | 23.3% | 0.960 | 0.927 | 0.000 | 0.067 | [0.046, 0.090] | [-0.023, 0.034] | [0.000, 0.083] | 23.3% | 1.000 | 0.933 | 4.00 | 3.97 | [3.64, 4.31] | [-1.19, -0.32] | [-1.00, 0.00] | 0.567 | 0.562 | [0.527, 0.597] | [-0.021, 0.086] | [-0.028, 0.120] | 0.930 | 0.927 | [0.914, 0.940] | [0.026, 0.054] | [0.019, 0.064] | 2.00 | 1.88 | [1.79, 1.96] | [0.78, 0.96] | [0.80, 1.00] | 42.6m | 42.6m | [42.6m, 42.6m] | [41.7m, 41.7m] | [41.7m, 41.7m] |
| 3 | 66 | 0.147 | 0.160 | [0.134, 0.197] | [0.035, 0.071] | [0.054, 0.097] | 0.000 | 0.051 | [0.034, 0.072] | [-0.032, 0.007] | [-0.040, 0.028] | 28.3% | 1.000 | 0.949 | 0.000 | 0.058 | [0.038, 0.081] | [-0.028, 0.023] | [0.000, 0.000] | 21.7% | 1.000 | 0.942 | 4.00 | 4.38 | [4.07, 4.72] | [-0.72, 0.07] | [-1.00, 0.00] | 0.613 | 0.616 | [0.578, 0.655] | [0.041, 0.137] | [0.052, 0.167] | 0.920 | 0.921 | [0.909, 0.933] | [0.021, 0.047] | [0.016, 0.054] | 2.00 | 2.02 | [1.94, 2.10] | [0.94, 1.09] | [1.00, 1.20] | 2.7m | 2.7m | [2.7m, 2.7m] | [1.7m, 1.7m] | [1.7m, 1.7m] |
| 4 | 66 | 0.153 | 0.167 | [0.138, 0.203] | [0.040, 0.073] | [0.046, 0.105] | 0.036 | 0.063 | [0.043, 0.085] | [-0.018, 0.019] | [-0.007, 0.048] | 28.3% | 0.964 | 0.937 | 0.000 | 0.061 | [0.042, 0.081] | [-0.025, 0.025] | [0.000, 0.088] | 21.7% | 1.000 | 0.939 | 5.00 | 5.07 | [4.72, 5.43] | [-0.07, 0.77] | [-0.25, 1.00] | 0.655 | 0.645 | [0.615, 0.675] | [0.072, 0.164] | [0.097, 0.196] | 0.903 | 0.899 | [0.886, 0.911] | [-0.002, 0.024] | [-0.002, 0.035] | 2.10 | 2.09 | [2.00, 2.18] | [0.99, 1.18] | [1.00, 1.20] | 103.2m | 103.2m | [103.2m, 103.2m] | [102.3m, 102.3m] | [102.3m, 102.3m] |
| 5 | 66 | 0.160 | 0.166 | [0.136, 0.203] | [0.041, 0.070] | [0.046, 0.100] | 0.041 | 0.067 | [0.047, 0.090] | [-0.014, 0.020] | [0.000, 0.045] | 30.0% | 0.959 | 0.933 | 0.074 | 0.079 | [0.055, 0.104] | [-0.007, 0.042] | [0.000, 0.101] | 23.3% | 0.926 | 0.921 | 5.00 | 4.81 | [4.47, 5.17] | [-0.29, 0.47] | [-0.75, 1.00] | 0.667 | 0.659 | [0.627, 0.691] | [0.090, 0.169] | [0.117, 0.192] | 0.894 | 0.889 | [0.876, 0.902] | [-0.013, 0.016] | [-0.012, 0.028] | 2.20 | 2.17 | [2.06, 2.26] | [1.06, 1.26] | [1.20, 1.20] | 107.1m | 107.1m | [107.1m, 107.1m] | [106.2m, 106.2m] | [106.2m, 106.2m] |
## Recommendation (heuristic)

Recommended component agent-count: **N=5**

### Why this N was picked

Constraints (macro-median metrics):
- not_plausible_median <= NA (no constraint)
- final_convergence_median >= NA (no constraint)
- runtime_median_seconds <= NA (no constraint)

Near-best stability requirement: stability_median >= best_feasible_stability * 0.98

Feasible Ns: N=1 (stability_median=0.073, not_plausible_occ_median=0.011, not_plausible_dedup_canon_median=0.000, final_conv_median=0.887, runtime_median=57s), N=2 (stability_median=0.113, not_plausible_occ_median=0.040, not_plausible_dedup_canon_median=0.000, final_conv_median=0.930, runtime_median=42.6m), N=3 (stability_median=0.147, not_plausible_occ_median=0.000, not_plausible_dedup_canon_median=0.000, final_conv_median=0.920, runtime_median=2.7m), N=4 (stability_median=0.153, not_plausible_occ_median=0.036, not_plausible_dedup_canon_median=0.000, final_conv_median=0.903, runtime_median=103.2m), N=5 (stability_median=0.160, not_plausible_occ_median=0.041, not_plausible_dedup_canon_median=0.074, final_conv_median=0.894, runtime_median=107.1m).

Best feasible stability_median: 0.160
Stability threshold (near-best): 0.157

Near-best candidates: N=5 (stability_median=0.160, runtime_median=107.1m).

Selected: N=5 (smallest N among near-best candidates; runtime_median=107.1m).
