# Parallel Technology Processing — Design Spec

## Problem

The STDN-GEN pipeline processes technologies sequentially: for a 60-technology tech list with the d3d3v3 debate config, each technology takes several minutes (Stages 1-3 + 2b), resulting in multi-hour wall-clock time. Technologies are independent until the final normalization step, so there's no fundamental reason they can't run concurrently.

## Decision Summary

| Decision | Choice | Rationale |
|---|---|---|
| Parallelism mechanism | `asyncio.gather` + `Semaphore` | Already async; no new dependencies |
| Concurrency limit | Configurable semaphore (default 10) | Supports different API tiers and local Ollama |
| Output strategy | Collect in memory, write once | Avoids file contention |
| DuckDB | Per-technology connection | Safe concurrent reads |
| Canonical vocab | Sequential post-phase | No contention |
| LLM fallback cache | File lock on write | Same-material writes are rare but possible |
| Checkpointing | Set-based (completed techs) | Index-based doesn't work for parallel |
| Backwards compatibility | Defaults to sequential | Opt-in via config or CLI flag |

## Architecture

### Two-Phase Execution

```
Phase 1 — Parallel (per-technology):
  asyncio.gather with Semaphore(max_concurrent_technologies)
    Technology A: Stage 1 → Stage 2 + 2b → Stage 3 → return rows
    Technology B: Stage 1 → Stage 2 + 2b → Stage 3 → return rows
    Technology C: ...

Phase 2 — Sequential (cross-technology):
  Write combined CSV
  Normalize component names (LLM + vocab)
  Normalize material names (deterministic)
  Write JSON output
```

### Per-Technology Isolation via Context Object

The current `process_technology()` reads shared mutable state from `self.*` sub-objects (extractors, enrichers, reporters). Under concurrency this causes race conditions. The fix is a per-technology context object that isolates mutable state.

**Create a `TechnologyContext` dataclass** that holds per-invocation instances of objects with mutable state:

```python
@dataclass
class TechnologyContext:
    country_repo: CountryDataRepository   # own DuckDB connection + own cache dict
    usage: RunUsage                       # own token counters
    transcript_path: Path | None = None   # own transcript path (was on shared ComponentExtractor)
```

**Changes to `process_technology()`**:
- Accept a `TechnologyContext` instead of shared `self.country_repo`, `self.usage`
- Return transcript path in the result dict (instead of reading `self.component_extractor.last_transcript_path`)
- Component/materials/country extractors remain shared (they are stateless beyond their arguments) **except** for `last_transcript_path` which moves to the context

**Shared objects that are safe** (stateless, read-only, or thread-safe):
- `self.deps` (STDNDependencies) — read-only ontology data, model configs
- `self.canonical_vocab` — read-only during parallel phase, written only in sequential normalization
- `self.component_extractor`, `self.materials_extractor`, `self.process_consumables_extractor` — their `extract()` methods are async and take all inputs as arguments. The only mutable state is `last_transcript_path` on `ComponentExtractor`, which moves to the context.
- `self.country_enricher` — stateless; uses the `CountryDataRepository` passed to it

**Shared objects that need per-technology instances**:
- `CountryDataRepository` — has mutable in-memory cache dict and DuckDB connection
- `RunUsage` — mutable counters
- Transcript path — was stored on shared `ComponentExtractor.last_transcript_path`

**Note on Ollama**: When using a local Ollama server (single GPU), set `max_concurrent_technologies: 1` to avoid serialization issues with the Ollama client. The pydantic-ai OpenAI client is safe for concurrent use.

### Concurrency Control

```python
sem = asyncio.Semaphore(config.max_concurrent_technologies)

async def _process_with_limit(tech, ...):
    async with sem:
        return await self.process_technology(tech, ...)

results = await asyncio.gather(*[
    _process_with_limit(tech, ...) for tech in technologies
])
```

The semaphore defaults to 10. For Tier 5 OpenAI (30,000 RPM), this is conservative — could safely go to 60. The knob exists for:
- Lower API tiers with stricter rate limits
- Local Ollama runs (single GPU, one request at a time)
- Memory-constrained environments

### LLM Call Estimate

Per technology (d3d3v3 config):
- Stage 1 (components): 3 debaters + consensus = ~4 calls
- Stage 2 (materials): ~12 components × 4 calls = ~48 calls
- Stage 2b (process consumables): 1 extractor + 1 judge = 2 calls
- Stage 3 (countries): mostly cached, ~5-10 LLM fallback calls
- **Total: ~61 calls per technology**

At 10 concurrent technologies: peak ~610 concurrent call streams. At 30,000 RPM, this is ~2% of capacity.

## Shared Resource Handling

### Output CSV

**Current**: Append rows to a single file after each technology completes.

**New**: Each technology returns its rows as a list of dicts. After `gather` completes, the main loop writes all rows to the CSV in one pass. Technology order in the CSV follows the tech list order (not completion order) for deterministic output.

### DuckDB (USGS Data) and Country Cache

**Current**: Single `CountryDataRepository` with one DuckDB connection and one in-memory cache dict shared across all technologies.

**New**: Each concurrent technology gets its own `CountryDataRepository` instance (via `TechnologyContext`) with its own DuckDB connection and its own cache dict. DuckDB supports concurrent reads from the same file, so no file copying is needed (unlike the multi-run parallel runner which copies the DB file).

Trade-off: per-technology caches mean duplicate USGS queries for the same material across technologies. This is acceptable because USGS queries are fast local DuckDB reads, not LLM calls. The alternative (shared cache with locking) adds complexity for minimal benefit.

### Canonical Vocabulary

**No change needed.** The vocabulary is read during the parallel phase (for ontology matching in Stage 2b) and written only during the sequential normalization phase (Phase 2). No contention.

### LLM Fallback Cache

**Current**: Hash-based filenames (`md5(material_name).json`) in a shared directory. No locking.

**New**: Add a file lock around cache writes using the `filelock` library (cross-platform, pip-installable). The risk is low (two technologies requesting the same non-USGS material simultaneously would write identical data to the same file), but a lock prevents corruption. Lock the individual cache file during write.

### RunUsage (Token Tracking)

**Current**: Single mutable `RunUsage` object passed to all technologies, accumulating totals.

**New**: Each technology gets its own `RunUsage` instance. After `gather`, the main loop sums them into a combined total. This avoids race conditions on the shared counters.

## Progress Tracking & Checkpointing

### Progress Reporting

With concurrent technologies, interleaved per-technology log output is unreadable. Change to:

**Main log**: Progress counter only.
```
[1/60] Smartphone completed (47s, 61 LLM calls)
[2/60] MRI Machine completed (52s, 58 LLM calls)
...
[60/60] All technologies complete (total: 4m 23s)
```

**Per-technology logs**: Detailed stage-by-stage output goes to `logs/technologies/{technology_name}.log`. This preserves debuggability without cluttering the main log.

### Checkpointing

**Current**: Index-based — stores the index of the last completed technology. On resume, skips technologies before that index.

**New**: Set-based — stores the set of completed technology names in the checkpoint file. On resume:
1. Load completed set from checkpoint
2. Filter tech list to only uncompleted technologies
3. Run parallel phase on remaining technologies
4. If all complete, proceed to normalization

Checkpoint file format:
```json
{
  "completed_technologies": ["Smartphone", "MRI Machine", ...],
  "timestamp": "2026-03-25T14:30:00",
  "config_hash": "abc123"
}
```

Written atomically (write to temp file, then rename) after each technology completes. An `asyncio.Lock` protects concurrent writes to the checkpoint file (all tasks run in the same event loop, so an asyncio lock suffices — no file lock needed).

## Configuration

### New Config Options

```json
{
  "parallel_technologies": false,
  "max_concurrent_technologies": 10
}
```

- `parallel_technologies`: Enable/disable. Defaults to `false` for backwards compatibility.
- `max_concurrent_technologies`: Semaphore limit. Defaults to 10. Set to 1 for effectively sequential (useful for debugging).

### CLI Flags

```
--parallel-technologies true|false    (uses existing _str_to_bool type)
--max-concurrent-technologies N       (type=int)
```

CLI flags override config file values. These are added to the existing argparse in `main.py`, following the established `_str_to_bool` pattern for boolean flags.

### Composability with `scripts/parallel_runs.py`

The multi-run parallel runner spawns N independent pipeline processes, each with its own config. Since `parallel_technologies` is a config option, each spawned run inherits it automatically. No changes needed to `parallel_runs.py`.

Combined example: 3 parallel runs × 10 concurrent technologies = 30 concurrent LLM call streams. At 30,000 RPM this is well within limits.

## Error Handling

### Per-Technology Failures

If a technology fails during the parallel phase:
1. Log the error with full traceback to the per-technology log file
2. Record it as failed (not completed) in the checkpoint
3. Continue processing other technologies — don't fail the entire batch
4. Report failed technologies in the summary

After the parallel phase, if any technologies failed:
```
WARNING: 2/60 technologies failed:
  - Quantum Computer: TimeoutError in Stage 2
  - Satellite Bus: API rate limit exceeded
Proceeding with normalization for 58 completed technologies.
Re-run with --parallel-technologies to retry failed technologies (checkpoint will skip completed ones).
```

### Retry on Resume

On resume, only failed and not-yet-started technologies are processed. Completed technologies are skipped via the checkpoint set.

## Files Modified

| File | Change |
|---|---|
| `src/stdn_agentic/orchestrator/pipeline.py` | `TechnologyContext` dataclass; parallel technology loop with semaphore; in-memory row collection; set-based checkpointing with `asyncio.Lock`; per-tech `CountryDataRepository`/`RunUsage`; progress counter; per-technology log files |
| `src/stdn_agentic/orchestrator/pipeline.py` | `process_technology()` accepts `TechnologyContext`, returns transcript path in result dict |
| `src/stdn_agentic/orchestrator/component_extractor.py` | Remove `last_transcript_path` instance state; return transcript path from `extract()` instead |
| `src/stdn_agentic/main.py` | New CLI flags: `--parallel-technologies`, `--max-concurrent-technologies` |
| `src/stdn_agentic/models.py` | New config fields: `parallel_technologies`, `max_concurrent_technologies` |
| `src/stdn_agentic/data/repository.py` | File lock on LLM fallback cache writes (using `filelock` library) |

## What Does NOT Change

- `_normalize_output()` — runs sequentially after parallel phase
- `scripts/parallel_runs.py` — inherits config automatically
- Stage internals (debate, extraction, enrichment) — unchanged
- All agent code — unchanged
- `self.deps` (STDNDependencies) — read-only, safe to share
- `self.canonical_vocab` — read-only during parallel phase
