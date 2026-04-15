#!/usr/bin/env bash
# Microelectronics 61-tech rerun: 5 configs x 5 runs = 25 total pipeline runs
# Plus gold standard supplement: 2 configs x 5 runs = 10 runs
# Total: 35 runs
#
# Usage:
#   bash scripts/run_micro_rerun.sh
#   nohup bash scripts/run_micro_rerun.sh > logs/micro_rerun.log 2>&1 &

set -e
export PYTHONUNBUFFERED=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

mkdir -p logs

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

run_batch() {
    local config_type="$1"
    local base_config="$2"
    local num_runs="${3:-5}"

    log "=========================================="
    log "Starting $config_type ($num_runs runs) with $base_config"
    log "=========================================="

    uv run python scripts/parallel_runs.py \
        --config-type "$config_type" \
        --num-runs "$num_runs" \
        --base-config "$base_config"

    local raw_count
    raw_count=$(ls output/raw/stdns_output_${config_type}_*.csv 2>/dev/null | wc -l | tr -d ' ')
    log "Completed $config_type: $raw_count raw files"
}

normalize_existing() {
    local config_type="$1"
    local model="$2"

    log "=========================================="
    log "Normalizing existing $config_type raw files with $model"
    log "=========================================="

    uv run python scripts/normalize_outputs_global_granularity.py \
        --pattern "output/raw/stdns_output_${config_type}_*.csv" \
        --group-by technology \
        --output-dir output/normalized \
        --global-vocab data/component_canonical_vocab_global_primary.json \
        --model "$model" \
        --chunk-size 120

    log "Normalization complete for $config_type"
}

log "Microelectronics 61-tech rerun starting"
log "Project dir: $PROJECT_DIR"

# Phase 0: Normalize v1v1v1 raw files (pipeline runs already completed)
normalize_existing v1v1v1 openai:gpt-4.1

# Phase 1: Remaining microelectronics runs (4 configs x 5 runs)
run_batch d2v1v1 config_micro_d2v1v1.json
run_batch d3v1v1 config_micro_d3v1v1.json
run_batch d4v1v1 config_micro_d4v1v1.json
run_batch d5v1v1 config_micro_d5v1v1.json

# Phase 2: Gold standard supplement (3 pharma/biotech techs, v1v1v1 + d3v1v1)
run_batch v1v1v1 config_goldstandard_supplement.json
run_batch d3v1v1 config_goldstandard_supplement.json

log "=========================================="
log "All runs complete"
log "Raw files: $(ls output/raw/*.csv 2>/dev/null | wc -l | tr -d ' ')"
log "Normalized files: $(ls output/normalized/*.csv 2>/dev/null | wc -l | tr -d ' ')"
log "=========================================="
