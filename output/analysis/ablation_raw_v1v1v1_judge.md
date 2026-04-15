# Stage 1 Component Validity (Normalized Outputs; Per-Run)
This report uses an LLM judge to label whether each extracted component is a plausible **primary manufacturing component** for a given technology. Candidates are sourced from **normalized STDN output CSVs** and evaluated per run. A cache keyed by (technology, component) avoids repeated judge calls.

- normalized_dir: `output/raw`
- configs: v1v1v1
- judge_model: `openai:gpt-4.1`
- cache: `output/analysis/stage1_component_judge_cache.jsonl`
- judged_new: 1674
- judged_cached: 242

## Per-configuration variability summary (per-run invalid rate)

| config | runs_entries | invalid_rate_median | invalid_rate_mean | invalid_rate_min | invalid_rate_max | component_count_median | component_count_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1v1v1 | 315 | 0.000 | 0.029 | 0.000 | 0.500 | 8.000 | 7.756 |
