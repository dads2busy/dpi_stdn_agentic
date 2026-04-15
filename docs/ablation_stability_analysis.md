# Ablation: stability tension between debate and normalization

The ablation reveals a tension in how stability should be measured. Before normalization, debate doubles run-to-run stability (0.073 to 0.147 median pairwise Jaccard) because the debate feedback loop pushes agents toward overlapping component sets within each run. After normalization, the picture reverses: single-agent output becomes more stable (0.500) than debate output (0.327).

The explanation is that single-agent runs produce similar components with different surface forms. "Battery Module" in one run becomes "Lithium-ion Battery Pack" in another. Normalization collapses these to the same canonical name, producing high post-normalization overlap. Debate, by contrast, produces genuinely different component selections across runs. The union across 5 debate runs (13 median) is larger than the union across 5 single-agent runs (12.5), while the intersection is smaller (1 vs 3). Debate is exploring a broader component space, not converging on a stable core.

This means debate and normalization are working at cross-purposes for stability. Debate increases the diversity of what gets extracted. Normalization increases the consistency of how it's named. For the single-agent case, naming variation is the dominant source of instability, so normalization provides a massive improvement. For the debate case, semantic variation (genuinely different component selections) is the dominant source, and normalization can't help with that.

The practical question is: which kind of stability matters? If the goal is reproducibility (same output every time), single-agent with normalization wins. If the goal is coverage (finding all relevant components across multiple runs), debate wins, it just finds different subsets each time.

This reframes the technical report from "debate improves stability" to a more nuanced story about what debate actually does: it broadens exploration at the cost of run-to-run convergence, while normalization provides naming consistency regardless. Whether that's a feature or a problem depends on the use case.

## Supporting data (61-tech microelectronics, April 2026)

### Stability comparison

| Metric | v1v1v1 (no debate) | d3v1v1 (3-agent debate) |
|---|---|---|
| Transcript-level Jaccard (pre-normalization) | 0.073 | 0.147 |
| CSV-level Jaccard (post-normalization) | 0.500 | 0.327 |
| Core ratio (intersection / median set size) | 0.429 | 0.200 |
| Median intersection size | 3.0 | 1.0 |
| Median union size | 12.5 | 13.0 |
| Median per-run set size | 7.0 | 6.0 |

### Full ablation table

| Layer | Stability (median Jaccard) | Invalid rate (median) | Components (median) |
|---|---|---|---|
| Naive raw | 0.146 | n/a | 39.5 |
| Naive + normalization | 0.756 | n/a | 12.0 |
| Structured raw (v1v1v1) | 0.067 | 0.000 | n/a |
| Structured + normalization (v1v1v1) | 0.073 | 0.011 | 5.0 |
| Structured + norm + debate (d3v1v1) | 0.147 | 0.000 | 4.0 |

### Data sources

- Sweet-spot analysis: `output/analysis/micro_sweet_spot_by_n.csv` (transcript-derived stability)
- Standalone stability: `output/analysis/micro_stage1_stability.json` (CSV-derived stability)
- Core ratio: `output/analysis/ablation_core_ratio.json`
- Ablation comparison: `output/analysis/ablation_comparison.md`
