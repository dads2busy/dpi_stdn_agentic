#!/bin/bash
# Run 5 d3d3v3 runs followed by 5 v1v1v1 runs
# With resume capability - detects completed runs and skips them

set -e  # Exit on error

cd /Users/ads7fg/git/dpi_stdn_agentic
source .venv/bin/activate

# Configuration
D3D3V3_TARGET=5
V1V1V1_TARGET=5
OUTPUT_DIR="./output/raw"
PROGRESS_FILE="./output/batch_progress.json"

# Function to count completed runs of a specific type
count_completed_runs() {
    local pattern=$1
    local count=$(ls -1 ${OUTPUT_DIR}/stdns_output_${pattern}_*.csv 2>/dev/null | wc -l | tr -d ' ')
    echo $count
}

# Function to check if a CSV file is complete (has more than just header)
is_run_complete() {
    local file=$1
    if [ -f "$file" ]; then
        local lines=$(wc -l < "$file" | tr -d ' ')
        # A complete run should have header + data rows (at least 100 lines for 20 techs)
        if [ "$lines" -gt 100 ]; then
            return 0  # true - complete
        fi
    fi
    return 1  # false - incomplete
}

# Function to find and remove incomplete runs
cleanup_incomplete_runs() {
    local pattern=$1
    echo "Checking for incomplete ${pattern} runs..."
    for file in ${OUTPUT_DIR}/stdns_output_${pattern}_*.csv; do
        if [ -f "$file" ]; then
            if ! is_run_complete "$file"; then
                echo "  Removing incomplete run: $file"
                rm -f "$file"
            fi
        fi
    done
}

# Function to run a single batch
run_single() {
    local run_type=$1  # "d3d3v3" or "v1v1v1"
    local run_num=$2
    local total=$3

    echo ""
    echo "=== ${run_type^^} Run $run_num of $total ==="
    echo "Started at $(date)"

    if [ "$run_type" = "d3d3v3" ]; then
        python -u -m stdn_agentic.main \
            --enable-component-debate true \
            --enable-material-debate true \
            --enable-country-debate true \
            --num-agents-component 3 \
            --num-agents-material 3 \
            --num-agents-country 3
    else
        python -u -m stdn_agentic.main \
            --enable-component-debate false \
            --enable-material-debate false \
            --enable-country-debate false
    fi

    echo "Completed at $(date)"
}

echo "========================================"
echo "STDN Batch Runner with Resume Support"
echo "========================================"
echo "Started at $(date)"
echo ""

# Cleanup any incomplete runs first
cleanup_incomplete_runs "d3d3v3"
cleanup_incomplete_runs "v1v1v1"

# Count existing complete runs
d3d3v3_done=$(count_completed_runs "d3d3v3")
v1v1v1_done=$(count_completed_runs "v1v1v1")

echo "Current status:"
echo "  D3D3V3 runs complete: $d3d3v3_done / $D3D3V3_TARGET"
echo "  V1V1V1 runs complete: $v1v1v1_done / $V1V1V1_TARGET"
echo ""

# Run remaining D3D3V3 runs
d3d3v3_remaining=$((D3D3V3_TARGET - d3d3v3_done))
if [ $d3d3v3_remaining -gt 0 ]; then
    echo "Running $d3d3v3_remaining more D3D3V3 runs..."
    for i in $(seq 1 $d3d3v3_remaining); do
        current_run=$((d3d3v3_done + i))
        run_single "d3d3v3" $current_run $D3D3V3_TARGET
    done
else
    echo "All D3D3V3 runs already complete."
fi

# Recount after D3D3V3 runs
d3d3v3_done=$(count_completed_runs "d3d3v3")

# Run remaining V1V1V1 runs
v1v1v1_remaining=$((V1V1V1_TARGET - v1v1v1_done))
if [ $v1v1v1_remaining -gt 0 ]; then
    echo ""
    echo "Running $v1v1v1_remaining more V1V1V1 runs..."
    for i in $(seq 1 $v1v1v1_remaining); do
        current_run=$((v1v1v1_done + i))
        run_single "v1v1v1" $current_run $V1V1V1_TARGET
    done
else
    echo "All V1V1V1 runs already complete."
fi

# Final status
d3d3v3_done=$(count_completed_runs "d3d3v3")
v1v1v1_done=$(count_completed_runs "v1v1v1")

echo ""
echo "========================================"
echo "Batch Run Complete"
echo "========================================"
echo "Finished at $(date)"
echo ""
echo "Final status:"
echo "  D3D3V3 runs: $d3d3v3_done / $D3D3V3_TARGET"
echo "  V1V1V1 runs: $v1v1v1_done / $V1V1V1_TARGET"
echo ""
echo "Output files in: $OUTPUT_DIR"
ls -la ${OUTPUT_DIR}/*.csv 2>/dev/null | tail -20
