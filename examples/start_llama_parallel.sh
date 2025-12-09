#!/bin/bash
# Start llama.cpp server configured for parallel agent execution
#
# This script starts llama.cpp with optimal settings for running
# multiple debate agents in parallel.
#
# Usage:
#   ./examples/start_llama_parallel.sh /path/to/model.gguf
#
# Or with defaults:
#   ./examples/start_llama_parallel.sh

set -e

# Configuration
MODEL_PATH="${1:-models/mistral-7b-instruct-v0.2.Q4_K_M.gguf}"
HOST="${LLAMA_HOST:-0.0.0.0}"
PORT="${LLAMA_PORT:-8080}"
PARALLEL_SLOTS="${LLAMA_PARALLEL:-4}"  # Number of concurrent requests
CTX_SIZE="${LLAMA_CTX:-8192}"         # Context window
GPU_LAYERS="${LLAMA_GPU_LAYERS:-35}"  # Number of layers on GPU (-1 for all)
THREADS="${LLAMA_THREADS:-8}"         # CPU threads

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "${GREEN}========================================${NC}"
echo "${GREEN}Starting llama.cpp for Parallel Agents${NC}"
echo "${GREEN}========================================${NC}"
echo ""
echo "Configuration:"
echo "  Model: $MODEL_PATH"
echo "  Host: $HOST:$PORT"
echo "  Parallel slots: $PARALLEL_SLOTS"
echo "  Context size: $CTX_SIZE"
echo "  GPU layers: $GPU_LAYERS"
echo "  CPU threads: $THREADS"
echo ""

# Check if model exists
if [ ! -f "$MODEL_PATH" ]; then
    echo "${YELLOW}Warning: Model not found at $MODEL_PATH${NC}"
    echo "Please provide correct model path as first argument:"
    echo "  ./examples/start_llama_parallel.sh /path/to/your/model.gguf"
    echo ""
    echo "Example models:"
    echo "  - mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    echo "  - llama-2-7b-chat.Q4_K_M.gguf"
    echo "  - mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf"
    exit 1
fi

# Check if llama-server exists
if ! command -v llama-server &> /dev/null; then
    echo "${YELLOW}Error: llama-server not found in PATH${NC}"
    echo ""
    echo "Please install llama.cpp:"
    echo "  git clone https://github.com/ggerganov/llama.cpp"
    echo "  cd llama.cpp"
    echo "  make LLAMA_CUDA=1  # or LLAMA_METAL=1 for Mac"
    echo ""
    echo "Then add to PATH or run from llama.cpp directory:"
    echo "  export PATH=/path/to/llama.cpp:$PATH"
    exit 1
fi

echo "${GREEN}Starting server...${NC}"
echo ""

# Start llama.cpp server with parallel support
llama-server \
    --model "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    --parallel "$PARALLEL_SLOTS" \
    --ctx-size "$CTX_SIZE" \
    --n-gpu-layers "$GPU_LAYERS" \
    --threads "$THREADS" \
    --batch-size 512 \
    --ubatch-size 256 \
    --cont-batching \
    --log-format text \
    --metrics \
    --verbose

# Notes:
# --parallel 4         : Support 4 concurrent requests (adjust based on VRAM)
# --ctx-size 8192      : 8K context window (adjust as needed)
# --batch-size 512     : Larger batch for better parallelism
# --ubatch-size 256    : Micro-batch size for parallel decoding
# --cont-batching      : Enable continuous batching (critical for parallelism)
# --metrics            : Enable Prometheus metrics at /metrics
# --n-gpu-layers 35    : Offload 35 layers to GPU (adjust for your GPU)
#                        Use -1 to offload all layers
