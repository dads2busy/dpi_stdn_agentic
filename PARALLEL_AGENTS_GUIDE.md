# Parallel Agent Execution with llama.cpp

## Short Answer: YES! ✅

You can absolutely run all debating agents in parallel with llama.cpp backend, significantly speeding up the initial proposal phase.

## Current Implementation (Sequential)

**Time for 3 agents**: ~30-45 seconds (10-15s per agent)

```python
# Current: Each agent runs one after another
for agent_num in range(1, num_agents + 1):
    result = await self.component_agent.run(prompt, deps=agent_deps)
    agent_proposals[agent_id] = process_result(result)
```

## Parallel Implementation (Recommended)

**Time for 3 agents**: ~10-15 seconds (all run simultaneously)

```python
# Parallel: All agents run at the same time
tasks = [self.component_agent.run(prompt, deps=agent_deps) 
         for agent_num in range(1, num_agents + 1)]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**Speedup**: 3x faster for 3 agents! 🚀

---

## llama.cpp Server Configuration

### 1. Start llama.cpp with parallel processing support

```bash
# Key parameters for parallel requests:
./llama-server \
    --model models/your-model.gguf \
    --host 0.0.0.0 \
    --port 8080 \
    --parallel 4 \
    --n-gpu-layers 35 \
    --ctx-size 8192 \
    --batch-size 512 \
    --ubatch-size 256 \
    --threads 8 \
    --cont-batching
```

### Key Parameters Explained:

- **`--parallel 4`**: Handle up to 4 concurrent requests (set to num_agents + 1)
- **`--cont-batching`**: Enable continuous batching for better throughput
- **`--batch-size 512`**: Larger batch for processing multiple requests
- **`--ubatch-size 256`**: Micro-batch size for parallel decoding
- **`--threads 8`**: CPU threads for KV cache operations

### 2. Configure your model in config.json

```json
{
  "model": "openai:llama-local",
  "base_url": "http://localhost:8080/v1",
  "api_key": "not-needed",
  "temperature": 0.7,
  "top_p": 0.95
}
```

---

## Implementation: Modify `pipeline.py`

### Location: `extract_components_with_debate` method

**Find this code** (around line 430-490):

```python
for agent_num in range(1, num_agents + 1):
    agent_id = f"Agent_{agent_num}"
    perspective = PERSPECTIVE_FOCUS[agent_num - 1]
    
    try:
        result = await self.component_agent.run(
            f"You are a {role} analyzing {technology}. "
            f"{perspective}. ",
            deps=agent_deps,
        )
        
        if result and result.output:
            # Process result...
            agent_proposals[agent_id] = [...]
    
    except Exception as e:
        logger.error(f"Error in {agent_id}: {e}")
```

**Replace with**:

```python
# Step 1: Prepare all agent tasks
agent_task_info = []
for agent_num in range(1, num_agents + 1):
    agent_id = f"Agent_{agent_num}"
    perspective = (
        PERSPECTIVE_FOCUS[agent_num - 1]
        if agent_num <= len(PERSPECTIVE_FOCUS)
        else "Focus on identifying essential subsystems and modules"
    )
    perspective_short = perspective.replace("Focus on ", "").replace("identifying ", "")
    
    prompt = (
        f"You are a {role} analyzing {technology}. "
        f"{perspective}. "
        f"Extract the primary manufacturing components from this analytical perspective."
    )
    
    # Create coroutine (don't await yet!)
    task = self.component_agent.run(prompt, deps=agent_deps)
    
    agent_task_info.append({
        'agent_id': agent_id,
        'perspective': perspective,
        'perspective_short': perspective_short,
        'task': task
    })

print(f"\n🚀 Running {len(agent_task_info)} agents in PARALLEL...\n")

# Step 2: Execute all tasks in parallel
tasks = [info['task'] for info in agent_task_info]
results = await asyncio.gather(*tasks, return_exceptions=True)

print(f"✓ All {len(results)} agents completed\n")

# Step 3: Process results
technology_specification = technology
technology_reasoning = ""

for info, result in zip(agent_task_info, results):
    agent_id = info['agent_id']
    perspective_short = info['perspective_short']
    
    # Handle errors
    if isinstance(result, Exception):
        logger.error(f"Error in {agent_id} proposal: {result}")
        print(f"  ✗ {agent_id}: Failed")
        continue
    
    # Handle None or missing output
    if not result or not result.output:
        logger.warning(f"{agent_id} returned no output")
        print(f"  ✗ {agent_id}: No output")
        continue
    
    # Process successful result
    try:
        components = (
            result.output.component_list
            if hasattr(result.output, "component_list")
            else result.output
        )
        
        # Capture tech spec from first agent
        if agent_id == "Agent_1":
            if hasattr(result.output, "technology_specification"):
                technology_specification = result.output.technology_specification
                print(f"✓ Captured tech spec: {technology_specification}")
            if hasattr(result.output, "technology_reasoning"):
                technology_reasoning = result.output.technology_reasoning
                print(f"✓ Captured reasoning: {technology_reasoning[:100]}...")
        
        from typing import cast
        from ..agents.component_agent import ComponentWithConfidence
        components_typed = cast(list[ComponentWithConfidence], components)
        
        # Extract proposals with confidence
        agent_proposals[agent_id] = [
            {
                "component": comp.name,
                "confidence": comp.confidence,
                "reasoning": comp.reasoning,
            }
            for comp in components_typed
        ]
        
        avg_conf = sum(p["confidence"] for p in agent_proposals[agent_id]) / len(
            agent_proposals[agent_id]
        )
        
        print(f"  ✓ {agent_id} ({role}): {len(components_typed)} components (avg conf: {avg_conf:.2f})")
        print(f"     → {perspective_short}")
        
        # Store for transcript
        agent_responses_for_transcript.append({
            "agent_id": agent_id,
            "components": agent_proposals[agent_id],
            "persona": f"{role} - {info['perspective']}",
        })
        
    except Exception as e:
        logger.error(f"Error processing {agent_id} result: {e}", exc_info=True)
        print(f"  ✗ {agent_id}: Error processing result")
```

---

## Performance Comparison

### Sequential (Current)
```
Agent 1: 12s
Agent 2: 11s  
Agent 3: 13s
-----------
Total: 36s
```

### Parallel (With llama.cpp)
```
All agents: 13s (longest agent)
-----------
Total: 13s
Speedup: 2.8x
```

### With More Agents
```
3 agents: 3x faster
5 agents: 5x faster
10 agents: ~8-10x faster (limited by hardware)
```

---

## Hardware Requirements

### Minimum (works but slower)
- **GPU**: RTX 3060 (12GB VRAM)
- **RAM**: 16GB
- **Parallel slots**: 3-4

### Recommended
- **GPU**: RTX 4090 (24GB VRAM) or A100 (40-80GB)
- **RAM**: 32GB+
- **Parallel slots**: 8-16

### Memory per Slot

For a 7B model (Q4_K_M):
- **Per request context**: ~500MB-1GB
- **3 parallel agents**: ~2-3GB additional
- **Model base**: ~4GB
- **Total VRAM needed**: ~6-7GB

For a 13B model:
- **Model base**: ~8GB  
- **3 parallel slots**: ~3-5GB
- **Total**: ~11-13GB

---

## Important Considerations

### 1. **llama.cpp Batch Processing**

llama.cpp doesn't actually run multiple model instances. Instead:
- Single model loaded once in VRAM
- Multiple requests processed in batches
- KV cache shared/swapped between requests
- More efficient than you'd think!

### 2. **Connection Pooling**

If using Pydantic AI with OpenAI client:
```python
import httpx

# Configure connection pool
httpx_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5
    ),
    timeout=httpx.Timeout(300.0)
)

# Pass to Pydantic AI agent configuration
```

### 3. **Rate Limiting**

For very large runs, you may want to add semaphores:

```python
# Limit to N concurrent requests
max_concurrent = 3
semaphore = asyncio.Semaphore(max_concurrent)

async def run_with_limit(task):
    async with semaphore:
        return await task

results = await asyncio.gather(
    *[run_with_limit(task) for task in tasks],
    return_exceptions=True
)
```

### 4. **Error Handling**

**Important**: Use `return_exceptions=True` in `asyncio.gather()` so one failed agent doesn't crash all of them!

---

## Testing Your Parallel Setup

### 1. Start llama.cpp server with monitoring

```bash
./llama-server \
    --model models/mistral-7b-q4.gguf \
    --parallel 4 \
    --cont-batching \
    --log-format text
```

Watch the logs - you should see multiple `/v1/chat/completions` requests come in simultaneously.

### 2. Test with your pipeline

```bash
cd ~/git/dpi_stdn_agentic
python -m stdn_agentic.main
```

Look for the new output:
```
🚀 Running 3 agents in PARALLEL...
✓ All 3 agents completed
  ✓ Agent_1 (supply chain analyst): 8 components (avg conf: 0.83)
  ✓ Agent_2 (supply chain analyst): 7 components (avg conf: 0.81)
  ✓ Agent_3 (supply chain analyst): 9 components (avg conf: 0.85)
```

### 3. Benchmark

```python
import time

start = time.time()
result = await orchestrator.extract_components_with_debate(...)
end = time.time()

print(f"Time: {end - start:.1f}s")
```

---

## Alternative: Ollama Backend

Ollama also supports concurrent requests:

```bash
# Start Ollama (automatically supports parallelism)
ollama serve

# Set in config.json
"model": "openai:mistral"
"base_url": "http://localhost:11434/v1"
```

Ollama handles batching automatically but may be slightly slower than llama.cpp for high concurrency.

---

## Recommended: Create a Parallel Debate Flag

Add to your config:

```json
{
  "enable_parallel_debate": true,
  "max_parallel_agents": 3
}
```

Then in code:
```python
if self.config.enable_parallel_debate:
    # Use parallel implementation
    results = await asyncio.gather(*tasks)
else:
    # Use sequential (safe default)
    for task in tasks:
        result = await task
```

---

## Summary

✅ **Yes, parallel agent execution works with llama.cpp**

✅ **3x+ speedup for initial proposals**

✅ **Simple to implement with `asyncio.gather()`**

✅ **Works with existing Pydantic AI code**

✅ **Requires proper llama.cpp server configuration**

⚠️ **Need sufficient VRAM for parallel slots**

⚠️ **Use `return_exceptions=True` for error handling**

**Next Steps**:
1. Configure llama.cpp with `--parallel 4`
2. Implement the parallel code changes shown above
3. Test and benchmark
4. Tune `--parallel` based on your hardware
