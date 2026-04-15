# Stage 1 Component Stability (Normalized Outputs)
This report computes run-to-run stability using **normalized** STDN outputs (`output/normalized/stdns_output_<config>_*.csv`). Stability is measured as pairwise **Jaccard similarity** of the per-technology **set of unique canonical component names** (`component` column), aggregated across technologies.
- Normalized dir: `output/normalized`
- Selected configs: d2v1v1, d3v1v1, d4v1v1, d5v1v1, v1v1v1
- min_runs: 2

## Macro summary by component debate strength (Stage 1 N)

| N | macro_median_jaccard | macro_mean_jaccard | technologies | configs |
| --- | --- | --- | --- | --- |
| 1 | 0.500 | 0.510 | 60 | v1v1v1 |
| 2 | 0.312 | 0.339 | 60 | d2v1v1 |
| 3 | 0.327 | 0.358 | 60 | d3v1v1 |
| 4 | 0.366 | 0.377 | 60 | d4v1v1 |
| 5 | 0.333 | 0.359 | 60 | d5v1v1 |

## Per-configuration summary (Stage 1 components)

| config | N | techs | macro_median_of_tech_medians | macro_mean_of_tech_medians |
| --- | --- | --- | --- | --- |
| d2v1v1 | 2 | 60 | 0.312 | 0.339 |
| d3v1v1 | 3 | 60 | 0.327 | 0.358 |
| d4v1v1 | 4 | 60 | 0.366 | 0.377 |
| d5v1v1 | 5 | 60 | 0.333 | 0.359 |
| v1v1v1 | 1 | 60 | 0.500 | 0.510 |
