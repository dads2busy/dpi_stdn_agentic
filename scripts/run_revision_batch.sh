#!/usr/bin/env bash
# Communications Sustainability revision round 1: new pipeline runs.
#   R1.2  N=5 for biotechnology and pharmaceuticals (60 techs each)
#   R1.2  N=5 for the 3 non-micro gold-standard techs (judge validity at N=5;
#         Smartphone already has micro d5v1v1 runs)
#   R1.5  tau/R sensitivity on 24 techs: a 20-tech stratified microelectronics
#         subset (seed 20261026) + all 4 gold-standard techs
# Each batch is 5 runs x all techs in its list. Total ~1,100 technology-runs.
#
# Approximate wall clock (from the 2026-04-14 micro rerun: 60 techs x 5 runs took
# ~1h at d3, ~3h at d5):
#   biotech_d5 ~3h   pharma_d5 ~3h   gold_d5 ~10m
#   tau085 ~25m   tau095 ~35m   tau095r5 ~40m   r5 ~30m   normalize ~15m
#
# Usage:
#   bash scripts/run_revision_batch.sh gold_d5 tau085   # selected batches, in order
#   bash scripts/run_revision_batch.sh normalize        # normalization only (run last)
#   bash scripts/run_revision_batch.sh abort tau085     # stop a batch, quarantine partial outputs
#   nohup bash scripts/run_revision_batch.sh gold_d5 tau085 > logs/revision_batch.log 2>&1 &
# Batches: biotech_d5 pharma_d5 gold_d5 tau085 tau095 tau095r5 r5
#
# Safety: the submitted results must not change.
# - --defer-shared-postprocess: parallel_runs.py otherwise re-normalizes EVERY
#   output/raw/stdns_output_<config_type>_*.csv, including the submitted micro
#   files, and grows the shared vocab.
# - After each batch, every new output file containing _<config_type>_ (raw CSVs,
#   transcripts, usage logs) is renamed to _<tag>_<config_type>_, so later globs
#   on _d3v1v1_ / _d5v1v1_ never pick them up.
# - Normalization maps new names with the LLM (as the submitted runs did) against
#   a COPY of the vocab, so data/component_canonical_vocab_global_primary.json is
#   untouched. (--freeze-vocab is not used: it passes unknown names through raw.)
# - Each run checkpoints to output/raw/<output_base>_parallel_checkpoint.json
#   (before 2026-10-27 all runs shared one file, so late-starting replicates
#   skipped technologies other replicates had finished). A stale checkpoint makes
#   the next batch silently skip technologies, so a batch refuses to start if any
#   exists; `abort` quarantines them.

set -e
export PYTHONUNBUFFERED=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

mkdir -p logs

SUBMITTED_VOCAB="data/component_canonical_vocab_global_primary.json"
REVISION_VOCAB="data/component_canonical_vocab_global_primary_revision.json"
CHECKPOINT_GLOB="output/raw/*parallel_checkpoint.json"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# batch_spec <name> -> "tag config_type base_config tau R"
batch_spec() {
    case "$1" in
        biotech_d5) echo "biotech  d5v1v1 config_biotech_d5v1v1.json           0.7  3" ;;
        pharma_d5)  echo "pharma   d5v1v1 config_pharma_d5v1v1.json            0.7  3" ;;
        gold_d5)    echo "gold     d5v1v1 config_goldstandard_supplement.json  0.7  3" ;;
        tau085)     echo "tau085   d3v1v1 config_tau_subset.json               0.85 3" ;;
        tau095)     echo "tau095   d3v1v1 config_tau_subset.json               0.95 3" ;;
        tau095r5)   echo "tau095r5 d3v1v1 config_tau_subset.json               0.95 5" ;;
        r5)         echo "r5       d3v1v1 config_tau_subset.json               0.7  5" ;;
        *) echo "Unknown batch: $1" >&2; return 1 ;;
    esac
}

# Rename files created since the marker: _<config_type>_ -> _<tag>_<config_type>_
tag_new_outputs() {
    local tag="$1" config_type="$2" marker="$3"
    local n=0 f base dir
    while IFS= read -r f; do
        base=$(basename "$f"); dir=$(dirname "$f")
        case "$base" in *"_${tag}_${config_type}_"*) continue ;; esac
        mv "$f" "$dir/${base/_${config_type}_/_${tag}_${config_type}_}"
        n=$((n + 1))
    done < <(find output -type f -newer "$marker" -name "*_${config_type}_*" -not -path "output/logs/*" -not -path "output/aborted/*")
    log "Tagged $n new files as ${tag}_${config_type}"
}

# run_batch <tag> <config_type> <base_config> <tau> <R>
run_batch() {
    local tag="$1" config_type="$2" base_config="$3" tau="$4" rounds="$5"
    local marker="logs/.revision_${tag}_start"

    if compgen -G "$CHECKPOINT_GLOB" > /dev/null; then
        log "ERROR: stale checkpoint(s) $(echo $CHECKPOINT_GLOB) exist (an earlier batch was interrupted)."
        log "       Run 'abort <batch>' for that batch first. Not starting $tag."
        exit 1
    fi

    log "=========================================="
    log "Starting $tag: $config_type, $base_config, tau=$tau, R=$rounds"
    log "=========================================="
    touch "$marker"

    # Set tau and R explicitly for every batch so a stray shell export cannot leak in
    CONVERGENCE_THRESHOLD="$tau" MAX_DEBATE_ROUNDS="$rounds" \
    uv run python scripts/parallel_runs.py \
        --config-type "$config_type" \
        --num-runs 5 \
        --base-config "$base_config" \
        --defer-shared-postprocess

    tag_new_outputs "$tag" "$config_type" "$marker"

    local raw_count
    raw_count=$(ls output/raw/stdns_output_${tag}_${config_type}_*.csv 2>/dev/null | wc -l | tr -d ' ')
    log "Completed $tag: $raw_count raw files"
}

# Stop a running batch and move its partial outputs out of the analysis folders
abort_batch() {
    local tag config_type
    read -r tag config_type _ <<< "$(batch_spec "$1")"
    local marker="logs/.revision_${tag}_start"
    local dest="output/aborted/${tag}_$(date '+%Y%m%d_%H%M%S')"

    log "Aborting $1: stopping processes"
    pkill -f "run_revision_batch.sh" 2>/dev/null || true
    pkill -f "parallel_runs.py --config-type ${config_type}" 2>/dev/null || true
    pkill -f "stdn -i config_${config_type}" 2>/dev/null || true
    sleep 3

    mkdir -p "$dest"
    local n=0 f
    if [ -e "$marker" ]; then
        while IFS= read -r f; do
            mv "$f" "$dest/"; n=$((n + 1))
        done < <(find output -type f -newer "$marker" -name "*_${config_type}_*" -not -name "*_${tag}_${config_type}_*" -not -path "output/logs/*" -not -path "output/aborted/*")
    fi
    for f in $CHECKPOINT_GLOB; do
        [ -e "$f" ] && mv "$f" "$dest/" && n=$((n + 1))
    done
    rm -f data/*_"${config_type}"_run*.db config_"${config_type}"_run*.json
    log "Moved $n partial files to $dest; removed temp DB/config copies"
}

normalize_all() {
    log "Normalizing revision outputs against a copy of the submitted vocab"
    [ -f "$REVISION_VOCAB" ] || cp "$SUBMITTED_VOCAB" "$REVISION_VOCAB"
    local pat
    for pat in biotech_d5v1v1 pharma_d5v1v1 gold_d5v1v1 tau085_d3v1v1 tau095_d3v1v1 tau095r5_d3v1v1 r5_d3v1v1; do
        ls output/raw/stdns_output_${pat}_*.csv >/dev/null 2>&1 || { log "  skip $pat (no raw files)"; continue; }
        log "  $pat"
        uv run python scripts/normalize_outputs_global_granularity.py \
            --pattern "output/raw/stdns_output_${pat}_*.csv" \
            --group-by technology \
            --output-dir output/normalized \
            --manifest-dir output/normalized/manifests_revision \
            --global-vocab "$REVISION_VOCAB" \
            --model openai:gpt-4.1 \
            --chunk-size 120
    done
    log "Normalized revision files: $(ls output/normalized | grep -cE 'biotech_d5|pharma_d5|gold_d5|tau08|tau09|r5_d3')"
}

if [ $# -eq 0 ]; then
    sed -n '2,20p' "$0"; exit 1
fi

if [ "$1" = "abort" ]; then
    abort_batch "$2"; exit 0
fi

# Validate all names before starting anything
for b in "$@"; do
    [ "$b" = "normalize" ] || batch_spec "$b" > /dev/null
done

# Keep the Mac from idle-sleeping while batches run (closing the lid still sleeps it)
if command -v caffeinate > /dev/null; then
    caffeinate -i -w $$ &
fi

for b in "$@"; do
    if [ "$b" = "normalize" ]; then
        normalize_all
    else
        # shellcheck disable=SC2046
        run_batch $(batch_spec "$b")
    fi
done

log "ALL DONE: $*"
