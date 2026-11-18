#!/usr/bin/env bash
# Vocabulary seeding test (2026-11-18): does a vocab seeded from debate outputs normalize new runs better
# than one seeded from single-agent outputs?
#   Phase 1: build per-technology vocabs from scratch on the submitted v1 (seedV) or d3 (seedD) raw runs,
#            two independent passes each (a, b).
#   Phase 2: normalize the held-out post-fix runs (fx{micro,biotech,pharma}_{v1,d3}) by EXTENDING a copy of
#            each seed vocab (unknown names mapped against the seed's canonicals), plus an empty-vocab control.
# Inputs are symlinks under output/seedtest/stage_*; nothing outside output/seedtest and data/seedtest is written.
# Analysis: scripts/seeding_test_analysis.py
set -euo pipefail
cd "$(dirname "$0")/.."
S=output/seedtest
V=data/seedtest
LOG=logs/seedtest_$(date +%Y%m%d)
mkdir -p "$LOG"

norm() {  # norm <stage> <vocab> <outdir> <logname>
  uv run python scripts/normalize_outputs_global_granularity.py \
    --pattern "$S/$1/stdns_output_*.csv" --group-by technology --vocab-scope technology \
    --global-vocab "$2" --output-dir "$3" --model openai:gpt-4.1 --chunk-size 120 \
    > "$LOG/$4.log" 2>&1
}

echo "phase 1 start $(date)"
for seed in V D; do for rep in a b; do
  rm -f "$V/vocab_seed${seed}_${rep}.json"
  norm "stage_seed${seed}" "$V/vocab_seed${seed}_${rep}.json" "$S/seed${seed}_${rep}" "seed${seed}_${rep}" &
done; done
wait
echo "phase 1 done $(date)"

for seed in V D; do for rep in a b; do
  cp "$V/vocab_seed${seed}_${rep}.json" "$V/vocab_ext${seed}_${rep}.json"
  norm stage_heldout "$V/vocab_ext${seed}_${rep}.json" "$S/ext${seed}_${rep}" "ext${seed}_${rep}" &
done; done
for rep in a b; do
  rm -f "$V/vocab_extN_${rep}.json"
  norm stage_heldout "$V/vocab_extN_${rep}.json" "$S/extN_${rep}" "extN_${rep}" &
done
wait
echo "phase 2 done $(date)"
