# Stage 1 Component Stability (Normalized Outputs)
This report computes run-to-run stability using **normalized** STDN outputs (`output/normalized/stdns_output_<config>_*.csv`). Stability is measured as pairwise **Jaccard similarity** of the per-technology **set of unique canonical component names** (`component` column), aggregated across technologies.
- Normalized dir: `output/raw`
- Selected configs: v1v1v1
- min_runs: 2

## Macro summary by component debate strength (Stage 1 N)

| N | macro_median_jaccard | macro_mean_jaccard | technologies | configs |
| --- | --- | --- | --- | --- |
| 1 | 0.067 | 0.091 | 63 | v1v1v1 |

## Per-configuration summary (Stage 1 components)

| config | N | techs | macro_median_of_tech_medians | macro_mean_of_tech_medians |
| --- | --- | --- | --- | --- |
| v1v1v1 | 1 | 63 | 0.067 | 0.091 |
