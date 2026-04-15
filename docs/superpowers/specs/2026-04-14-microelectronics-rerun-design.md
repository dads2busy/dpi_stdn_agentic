# Rerun STDN analyses on 61-tech microelectronics set

**Date:** 2026-04-14
**Purpose:** Replace the technical report's 26-tech results with fresh runs on the 61-tech microelectronics product list. Same experiment protocol, larger and domain-focused technology set.

## Parameters

- **Tech list:** `data/tech_list_microelectronic_products.csv` (61 technologies)
- **Model:** `openai:gpt-4.1-mini`
- **Configs:** v1v1v1, d2v1v1, d3v1v1, d4v1v1, d5v1v1
- **Runs per config:** 5
- **Total runs:** 25

## Phase 1: Config setup

Create 5 config files, one per debate configuration. All share:
- `import_tech_list`: `./data/tech_list_microelectronic_products.csv`
- `model`: `openai:gpt-4.1-mini`
- `output_dir`: `./output`
- `enable_process_consumables`: false (Stage 1 focus)
- `component_debate_top_p`: 0.0001 (deterministic generation within debate)
- `component_debate_temperature`: 0.03

Varying by config:
- `enable_component_debate`: true/false
- `num_agents_component`: 1, 2, 3, 4, 5

Files:
- `config_micro_v1v1v1.json` (debate off, 1 agent)
- `config_micro_d2v1v1.json` (debate on, 2 agents)
- `config_micro_d3v1v1.json` (debate on, 3 agents)
- `config_micro_d4v1v1.json` (debate on, 4 agents)
- `config_micro_d5v1v1.json` (debate on, 5 agents)

## Phase 2: Pipeline execution

Run each config 5 times using `scripts/parallel_runs.py`:

```bash
uv run python scripts/parallel_runs.py --config-type v1v1v1 --num-runs 5 --base-config config_micro_v1v1v1.json
uv run python scripts/parallel_runs.py --config-type d2v1v1 --num-runs 5 --base-config config_micro_d2v1v1.json
uv run python scripts/parallel_runs.py --config-type d3v1v1 --num-runs 5 --base-config config_micro_d3v1v1.json
uv run python scripts/parallel_runs.py --config-type d4v1v1 --num-runs 5 --base-config config_micro_d4v1v1.json
uv run python scripts/parallel_runs.py --config-type d5v1v1 --num-runs 5 --base-config config_micro_d5v1v1.json
```

Sequential across configs. Each batch handles its own parallelism internally.

Raw outputs land in `output/raw/` with timestamps in filenames. No collision with existing data.

## Phase 3: Normalization

Normalize the fresh raw outputs using the current canonical vocabulary:

```bash
uv run python scripts/normalize_outputs_global_granularity.py \
  --pattern "output/raw/stdns_output_*v1v1*.csv" \
  --global-vocab data/component_canonical_vocab_global_primary.json \
  --model openai:gpt-4.1-mini
```

Run once per config pattern or with a glob that catches all new files. Normalized outputs land in `output/normalized/`.

## Phase 4: Analysis

Run the same analysis scripts that produced the technical report's results. Filter to only the fresh runs (by date or config pattern).

### 4a. Component stability (Jaccard by N)

```bash
uv run python scripts/analyze_stage1_component_stability_normalized.py \
  --normalized-dir output/normalized/ \
  --include-config v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1 \
  --out-md output/analysis/micro_stage1_stability.md \
  --out-json output/analysis/micro_stage1_stability.json
```

### 4b. Judge validity (invalid rates by N)

```bash
uv run python scripts/judge_stage1_components_from_normalized_outputs.py \
  --normalized-dir output/normalized/ \
  --configs v1v1v1 d2v1v1 d3v1v1 d4v1v1 d5v1v1 \
  --judge-model openai:gpt-4.1 \
  --out-md output/analysis/micro_stage1_judge.md \
  --out-jsonl output/analysis/micro_stage1_judge.jsonl
```

### 4c. Sweet-spot tradeoffs (stability + validity + convergence + runtime + bootstrap CIs)

```bash
uv run python scripts/analyze_sweet_spot_tradeoffs.py \
  --transcripts-dir output/transcripts/ \
  --normalized-dir output/normalized/ \
  --canonical-vocab data/component_canonical_vocab_global_primary.json \
  --judge-jsonl output/analysis/micro_stage1_judge.jsonl \
  --log-dir output/logs/ \
  --out-md output/analysis/micro_sweet_spot.md \
  --out-techn-csv output/analysis/micro_sweet_spot_by_tech.csv \
  --out-by-n-csv output/analysis/micro_sweet_spot_by_n.csv
```

### 4d. Convergence dynamics

```bash
uv run python scripts/analyze_convergence_by_agent_count.py \
  --transcripts-dir output/transcripts/ \
  --out-csv output/analysis/micro_convergence.csv
```

### 4e. Naive baseline (same 61 techs, no pipeline structure)

```bash
uv run python scripts/naive_component_baseline.py \
  --extraction-model openai:gpt-4.1-mini \
  --runs 5 \
  --goldstandard data/goldstndrd.csv \
  --out-md output/analysis/micro_naive_baseline.md \
  --out-jsonl output/analysis/micro_naive_baseline.jsonl
```

Note: the naive baseline script may need the tech list source adjusted if it currently reads from the gold standard CSV rather than an arbitrary tech list. Verify before running.

### 4f. Figures

```bash
uv run python scripts/plot_sweet_spot_figures.py \
  --by-n-csv output/analysis/micro_sweet_spot_by_n.csv \
  --per-tech-csv output/analysis/micro_sweet_spot_by_tech.csv \
  --out-dir output/analysis/figures/
```

## Filtering old vs. new data

The analysis scripts need to operate on only the fresh microelectronics runs, not the existing 26-tech data. Options:
1. Use `--after` date filters where scripts support them
2. Use glob patterns that match only the new filenames (if config naming is distinct, e.g. `config_micro_*`)
3. Move old data to an archive directory before running

Option 3 is cleanest. Before starting Phase 2, move existing raw/normalized/transcript data:

```bash
mkdir -p output/archive_26tech
mv output/raw/*.csv output/archive_26tech/raw/
mv output/normalized/*.csv output/archive_26tech/normalized/
mv output/normalized/*.json output/archive_26tech/normalized/
```

Keep the canonical vocabulary and analysis reports in place (they are inputs, not outputs of the pipeline).

## Expected outputs

After all phases complete, the `output/analysis/` directory will contain:
- Stability report and JSON (Jaccard by tech and N)
- Judge validity report and JSONL cache
- Sweet-spot tradeoff report, per-tech CSV, and by-N CSV with bootstrap CIs
- Convergence CSV
- Naive baseline report and JSONL
- Paper-ready PNG figures (validity, tradeoff, convergence, heatmap)

These replace the corresponding sections in the technical report.

## Estimated cost

- 25 pipeline runs x 61 techs = 1,525 technology extractions
- Each extraction: ~3-9 LLM calls depending on debate config (more agents = more calls per round, up to 3 rounds)
- Judge evaluation: 1 call per unique (tech, component) pair across all runs
- Naive baseline: 5 runs x 61 techs = 305 simple extractions
- Model: gpt-4.1-mini (cheap) for extraction, gpt-4.1 (more expensive) for judge
