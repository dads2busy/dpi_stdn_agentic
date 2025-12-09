#!/usr/bin/env python3
"""
Example: Parallel Agent Execution for Multi-Agent Debate

This example demonstrates how to run multiple debate agents in parallel
using asyncio.gather() with llama.cpp or other async LLM backends.

Key Benefits:
- 3x faster for 3 agents (sequential: 36s → parallel: 13s)
- Better resource utilization
- Same results as sequential execution

Requirements:
- llama.cpp server running with --parallel 4
- Sufficient VRAM for multiple concurrent requests

Usage:
    python examples/parallel_debate_example.py
"""

import asyncio
import time
from typing import List, Dict, Any


async def run_agent_sequential(agent_id: str, prompt: str, delay: float = 2.0) -> Dict[str, Any]:
    """
    Simulate a single agent making a proposal (sequential).
    
    In real code, this would be:
        result = await self.component_agent.run(prompt, deps=agent_deps)
    """
    print(f"  {agent_id} starting...")
    await asyncio.sleep(delay)  # Simulate LLM inference time
    print(f"  {agent_id} completed")
    return {
        "agent_id": agent_id,
        "components": [f"Component_{agent_id}_1", f"Component_{agent_id}_2"],
        "confidence": 0.85
    }


async def demo_sequential_execution(num_agents: int = 3):
    """
    CURRENT IMPLEMENTATION: Sequential execution
    Each agent runs one after another.
    """
    print("\n" + "="*70)
    print("SEQUENTIAL EXECUTION (Current)")
    print("="*70)
    
    start_time = time.time()
    
    results = []
    for i in range(1, num_agents + 1):
        agent_id = f"Agent_{i}"
        result = await run_agent_sequential(agent_id, f"prompt_{i}")
        results.append(result)
    
    elapsed = time.time() - start_time
    
    print(f"\n✓ Completed {len(results)} agents")
    print(f"⏱  Total time: {elapsed:.1f}s")
    print(f"📊 Average per agent: {elapsed/num_agents:.1f}s")
    
    return results


async def demo_parallel_execution(num_agents: int = 3):
    """
    RECOMMENDED: Parallel execution
    All agents run simultaneously.
    """
    print("\n" + "="*70)
    print("PARALLEL EXECUTION (Recommended)")
    print("="*70)
    
    start_time = time.time()
    
    # Step 1: Create all agent tasks (don't await yet!)
    tasks = []
    for i in range(1, num_agents + 1):
        agent_id = f"Agent_{i}"
        task = run_agent_sequential(agent_id, f"prompt_{i}")
        tasks.append(task)
    
    print(f"\n🚀 Running {len(tasks)} agents in PARALLEL...\n")
    
    # Step 2: Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    
    print(f"\n✓ Completed {len(results)} agents")
    print(f"⏱  Total time: {elapsed:.1f}s")
    print(f"📊 Speedup: {(num_agents * 2.0) / elapsed:.1f}x")
    
    return results


async def demo_parallel_with_error_handling(num_agents: int = 3):
    """
    PRODUCTION EXAMPLE: Parallel execution with proper error handling
    """
    print("\n" + "="*70)
    print("PARALLEL WITH ERROR HANDLING (Production Ready)")
    print("="*70)
    
    async def run_agent_with_error(agent_id: str, should_fail: bool = False):
        """Agent that might fail."""
        print(f"  {agent_id} starting...")
        await asyncio.sleep(1.5)
        
        if should_fail:
            raise RuntimeError(f"{agent_id} failed intentionally")
        
        print(f"  {agent_id} completed")
        return {
            "agent_id": agent_id,
            "components": [f"Component_{agent_id}_1"],
            "confidence": 0.85
        }
    
    start_time = time.time()
    
    # Create tasks (Agent_2 will fail)
    tasks = [
        run_agent_with_error("Agent_1", should_fail=False),
        run_agent_with_error("Agent_2", should_fail=True),  # This will fail
        run_agent_with_error("Agent_3", should_fail=False),
    ]
    
    print(f"\n🚀 Running {len(tasks)} agents (one will fail)...\n")
    
    # Execute with return_exceptions=True (critical!)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    successful = []
    failed = []
    
    for i, result in enumerate(results):
        agent_id = f"Agent_{i+1}"
        if isinstance(result, Exception):
            print(f"  ✗ {agent_id}: {result}")
            failed.append(agent_id)
        else:
            print(f"  ✓ {agent_id}: {len(result['components'])} components")
            successful.append(result)
    
    elapsed = time.time() - start_time
    
    print(f"\n📊 Summary:")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")
    print(f"  Total time: {elapsed:.1f}s")
    print(f"  ⚠️  Pipeline continued despite failure!")
    
    return successful


async def demo_rate_limited_parallel(num_agents: int = 10, max_concurrent: int = 3):
    """
    ADVANCED: Rate-limited parallel execution
    Useful when you have many agents but limited resources.
    """
    print("\n" + "="*70)
    print(f"RATE-LIMITED PARALLEL ({num_agents} agents, max {max_concurrent} concurrent)")
    print("="*70)
    
    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_with_limit(agent_id: str):
        async with semaphore:
            print(f"  {agent_id} acquired slot (running)")
            await asyncio.sleep(1.0)
            print(f"  {agent_id} released slot (done)")
            return {"agent_id": agent_id, "components": [f"Comp_{agent_id}"]}
    
    start_time = time.time()
    
    # Create all tasks
    tasks = [run_with_limit(f"Agent_{i}") for i in range(1, num_agents + 1)]
    
    print(f"\n🚀 Processing {num_agents} agents with max {max_concurrent} concurrent...\n")
    
    # Run with rate limiting
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    
    print(f"\n📊 Summary:")
    print(f"  Total agents: {num_agents}")
    print(f"  Max concurrent: {max_concurrent}")
    print(f"  Total time: {elapsed:.1f}s")
    print(f"  Expected time: {(num_agents / max_concurrent) * 1.0:.1f}s")
    print(f"  Efficiency: {((num_agents / max_concurrent) * 1.0) / elapsed * 100:.0f}%")
    
    return results


async def main():
    """Run all demonstrations."""
    print("\n" + "#"*70)
    print("# Parallel Agent Execution Demo")
    print("#"*70)
    
    # Demo 1: Sequential (current)
    await demo_sequential_execution(num_agents=3)
    
    # Demo 2: Parallel (recommended)
    await demo_parallel_execution(num_agents=3)
    
    # Demo 3: Error handling
    await demo_parallel_with_error_handling(num_agents=3)
    
    # Demo 4: Rate limiting
    await demo_rate_limited_parallel(num_agents=10, max_concurrent=3)
    
    print("\n" + "#"*70)
    print("# Summary")
    print("#"*70)
    print("""
Key Takeaways:
1. ✅ Parallel execution is 3x+ faster than sequential
2. ✅ Use asyncio.gather(*tasks, return_exceptions=True)
3. ✅ Handle exceptions gracefully - don't let one agent crash all
4. ✅ Use Semaphore for rate limiting when needed
5. ✅ Works great with llama.cpp --parallel flag

To implement in your pipeline:
- Modify extract_components_with_debate() in pipeline.py
- Replace the for loop with asyncio.gather()
- Add proper error handling
- Configure llama.cpp with --parallel 4

See PARALLEL_AGENTS_GUIDE.md for full implementation details.
    """)


if __name__ == "__main__":
    asyncio.run(main())
