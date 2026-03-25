# Parallel Technology Processing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable concurrent processing of technologies within a single pipeline run, reducing wall-clock time from hours to minutes.

**Architecture:** Two-phase execution — Phase 1 parallelizes per-technology stages (1, 2, 2b, 3) via `asyncio.gather` + `Semaphore`, with per-technology isolation via `TechnologyContext`. Phase 2 runs normalization sequentially after all technologies complete.

**Tech Stack:** Python asyncio, Pydantic v2, filelock (new dependency), DuckDB

**Spec:** `docs/superpowers/specs/2026-03-25-parallel-technologies-design.md`

**Code repo:** `~/git/dpi_stdn_agentic`

---

## File Map

### New files

| File | Purpose |
|---|---|
| `src/stdn_agentic/orchestrator/technology_context.py` | `TechnologyContext` dataclass — per-technology isolated state |

### Modified files

| File | What changes |
|---|---|
| `src/stdn_agentic/models.py` | Add `parallel_technologies` and `max_concurrent_technologies` config fields |
| `src/stdn_agentic/main.py` | Add `--parallel-technologies` and `--max-concurrent-technologies` CLI flags; wire override logic |
| `src/stdn_agentic/orchestrator/component_extractor.py` | Remove `last_transcript_path` instance state; return it from extraction methods instead |
| `src/stdn_agentic/orchestrator/pipeline.py` | `process_technology()` accepts `TechnologyContext`; new `_run_parallel()` method; set-based checkpointing; in-memory row collection; per-technology logging; progress counter |
| `src/stdn_agentic/data/cache.py` | Add `filelock` around `MaterialCache.set()` writes |
| `pyproject.toml` | Add `filelock` dependency |

---

## Task 1: Add Config Fields and CLI Flags

**Files:**
- Modify: `src/stdn_agentic/models.py:176-183` (near existing `enable_process_consumables` field)
- Modify: `src/stdn_agentic/main.py:316-329` (near existing `--enable-process-consumables` arg)
- Modify: `src/stdn_agentic/main.py:124-149` (CLI override section)

- [ ] **Step 1: Add config fields to `ConfigModel`**

In `models.py`, add after the `enable_process_consumables` field (around line 183):

```python
parallel_technologies: bool = Field(
    default=False,
    description="Enable parallel processing of technologies within a single run",
)
max_concurrent_technologies: int = Field(
    default=10,
    ge=1,
    le=200,
    description="Max concurrent technologies when parallel_technologies is enabled",
)
```

- [ ] **Step 2: Add CLI flags to `main.py`**

In the argparse section (after `--save-transcripts` around line 376), add:

```python
parser.add_argument(
    "--parallel-technologies",
    type=_str_to_bool,
    default=None,
    metavar="BOOL",
    help="Enable parallel technology processing (default: from config or false)",
)
parser.add_argument(
    "--max-concurrent-technologies",
    type=int,
    default=None,
    metavar="N",
    help="Max concurrent technologies (default: from config or 10)",
)
```

- [ ] **Step 3: Add CLI override logic**

In the `process_all_technologies()` function where other CLI overrides are applied (around line 124-149), add:

```python
if cli_args.parallel_technologies is not None:
    config.parallel_technologies = cli_args.parallel_technologies
if cli_args.max_concurrent_technologies is not None:
    config.max_concurrent_technologies = cli_args.max_concurrent_technologies
```

- [ ] **Step 4: Verify config loads**

```bash
cd ~/git/dpi_stdn_agentic
source .venv/bin/activate
python -c "
from stdn_agentic.models import ConfigModel
c = ConfigModel()
print(f'parallel_technologies={c.parallel_technologies}, max_concurrent={c.max_concurrent_technologies}')
"
```

Expected: `parallel_technologies=False, max_concurrent=10`

- [ ] **Step 5: Commit**

```bash
git add src/stdn_agentic/models.py src/stdn_agentic/main.py
git commit -m "feat: add parallel_technologies config and CLI flags"
```

---

## Task 2: Create TechnologyContext and Refactor process_technology()

**Files:**
- Create: `src/stdn_agentic/orchestrator/technology_context.py`
- Modify: `src/stdn_agentic/orchestrator/component_extractor.py:96` (remove `last_transcript_path`)
- Modify: `src/stdn_agentic/orchestrator/pipeline.py:434-582` (`process_technology` signature and body)

- [ ] **Step 1: Create `TechnologyContext` dataclass**

Create `src/stdn_agentic/orchestrator/technology_context.py`:

```python
"""Per-technology isolated state for concurrent processing."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic_ai import RunUsage

from ..data.repository import CountryDataRepository
from .country_data_enricher import CountryDataEnricher


@dataclass
class TechnologyContext:
    """Holds per-technology mutable state to avoid shared-state races.

    Each concurrent technology task gets its own context with:
    - country_repo: own DuckDB connection and in-memory cache
    - country_enricher: own enricher wrapping the per-tech repo
    - usage: own token/request counters
    - transcript_path: own transcript file path
    """
    country_repo: CountryDataRepository
    country_enricher: CountryDataEnricher
    usage: RunUsage = field(default_factory=RunUsage)
    transcript_path: Optional[Path] = None
```

- [ ] **Step 2: Remove `last_transcript_path` from ComponentExtractor**

In `component_extractor.py`, find `self.last_transcript_path: Optional[Path] = None` (line 96) and remove it. Then find where it's set during extraction and instead return the transcript path as part of the extraction result.

Search for all places `last_transcript_path` is set (e.g., `self.last_transcript_path = ...`) and change them to return the path from the method instead.

- [ ] **Step 3: Update `process_technology()` signature**

In `pipeline.py`, change the signature from:

```python
async def process_technology(
    self,
    tech: str,
    role: str,
    domain: str,
    usage: RunUsage,
    use_material_debate: bool = False,
) -> Optional[Dict[str, Any]]:
```

To:

```python
async def process_technology(
    self,
    tech: str,
    role: str,
    domain: str,
    ctx: TechnologyContext,
    use_material_debate: bool = False,
) -> Optional[Dict[str, Any]]:
```

- [ ] **Step 4: Update `process_technology()` body**

Replace all references to `usage` with `ctx.usage`. Replace `self.country_enricher` calls with `ctx.country_enricher` (the enricher holds its own `self.country_repo`, so using the per-tech enricher automatically uses the per-tech repo — no need to modify enricher internals). Replace the `self.component_extractor.last_transcript_path` read (around line 488-492) with `ctx.transcript_path`, and set `ctx.transcript_path` after component extraction returns.

Include `transcript_path` in the return dict:

```python
return {
    "technology": tech,
    "components": components,
    "materials": materials_list,
    "enriched_data": enriched_data,
    "pc_enriched_data": pc_enriched_data,
    "transcript_path": ctx.transcript_path,
}
```

- [ ] **Step 5: Update callers in `run_pipeline()`**

In the sequential technology loop (around line 1138), update the call to create a `TechnologyContext` per technology:

```python
from .technology_context import TechnologyContext

# Inside the loop:
ctx = TechnologyContext(
    country_repo=self.country_repo,
    country_enricher=self.country_enricher,
    usage=usage,
)
result = await self.process_technology(tech, tech_role, tech_domain, ctx, ...)
```

This keeps sequential mode working with existing shared state.

- [ ] **Step 6: Verify sequential mode still works**

Run a quick test with 1-2 technologies:

```bash
cd ~/git/dpi_stdn_agentic
source .venv/bin/activate
python -m stdn_agentic.main -i config_test_process_consumables.json
```

Expected: Pipeline completes without errors, output matches previous behavior.

- [ ] **Step 7: Commit**

```bash
git add src/stdn_agentic/orchestrator/technology_context.py \
        src/stdn_agentic/orchestrator/component_extractor.py \
        src/stdn_agentic/orchestrator/pipeline.py
git commit -m "refactor: introduce TechnologyContext for per-technology isolated state"
```

---

## Task 3: Add File Lock to LLM Fallback Cache

**Files:**
- Modify: `pyproject.toml` (add `filelock` dependency)
- Modify: `src/stdn_agentic/data/cache.py:91-108` (`MaterialCache.set()`)

- [ ] **Step 1: Add `filelock` dependency**

```bash
cd ~/git/dpi_stdn_agentic
source .venv/bin/activate
pip install filelock
```

Add `filelock` to `pyproject.toml` in the dependencies section.

- [ ] **Step 2: Add lock to `MaterialCache.set()`**

In `cache.py`, modify the `set()` method (lines 91-108) to use a file lock:

```python
from filelock import FileLock

def set(self, key: str, value: Any):
    cache_file = self._get_cache_path(key)
    lock_file = cache_file.with_suffix(".lock")
    cache_data = {
        "timestamp": datetime.now().isoformat(),
        "key": key,
        "value": value,
    }
    with FileLock(lock_file, timeout=10):
        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=2, default=str)
```

- [ ] **Step 3: Verify cache still works**

```bash
python -c "
from stdn_agentic.data.cache import MaterialCache
c = MaterialCache('./data/llm_fallback_cache', ttl_hours=720)
c.set('test_key', {'test': True})
result = c.get('test_key')
print('get:', result)
assert result is not None and result['value']['test'] == True
# Clean up test artifacts
import os
os.remove(c._get_cache_path('test_key'))
lock_path = c._get_cache_path('test_key').with_suffix('.lock')
if lock_path.exists(): os.remove(lock_path)  # filelock leaves .lock files
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/stdn_agentic/data/cache.py
git commit -m "feat: add file lock to LLM fallback cache writes"
```

---

## Task 4: Implement Parallel Technology Loop

**Files:**
- Modify: `src/stdn_agentic/orchestrator/pipeline.py:1049-1248` (`run_pipeline()`)

This is the core task — adding the `_run_parallel()` method and the branch in `run_pipeline()`.

- [ ] **Step 1: Add `_run_parallel()` method**

Add a new method to `STDNOrchestrator`:

```python
async def _run_parallel(
    self,
    technologies: List[str],
    role: str,
    domain: str,
    tech_roles: Optional[Dict[str, str]],
    tech_domains: Optional[Dict[str, str]],
    use_material_debate: bool,
) -> Dict[str, Any]:
    """Process technologies concurrently with semaphore-based throttling."""
    import asyncio
    import time

    sem = asyncio.Semaphore(self.config.max_concurrent_technologies)
    checkpoint_lock = asyncio.Lock()
    completed_techs: set[str] = set()
    all_results: dict[str, dict] = {}  # tech_name -> result
    failed_techs: dict[str, str] = {}  # tech_name -> error message
    total = len(technologies)
    completed_count = 0
    start_time = time.time()

    # Load checkpoint if resuming
    # ... (load completed set, filter technologies)

    async def _process_one(tech: str):
        nonlocal completed_count
        tech_role = (tech_roles or {}).get(tech, role)
        tech_domain = (tech_domains or {}).get(tech, domain)
        tech_start = time.time()

        # Create per-technology context with isolated repo + enricher
        # Mirror the constructor args from pipeline.py __init__ (lines 272-284, 350-356)
        tech_repo = CountryDataRepository(
            database_path=self.config.usgs_database,
            deps=self.deps,
            top_n=5,
            use_llm_fallback=True,
            enable_llm_cache=self.config.enable_llm_fallback_cache,
            llm_cache_dir=self.config.llm_fallback_cache_dir,
            llm_cache_ttl_hours=self.config.llm_fallback_cache_ttl_hours,
            country_no_debate_top_p=self.country_no_debate_top_p,
            country_debate_top_p=self.country_debate_top_p,
            country_no_debate_temperature=self.country_no_debate_temperature,
            country_debate_temperature=self.country_debate_temperature,
        )
        tech_enricher = CountryDataEnricher(
            country_repo=tech_repo,
            reporter=self.reporter,
            write_nulls=self.config.write_nulls_to_output,
            use_debate=self.config.enable_country_debate,
            num_agents=self.config.num_agents_country,
        )
        ctx = TechnologyContext(
            country_repo=tech_repo,
            country_enricher=tech_enricher,
        )

        async with sem:
            try:
                result = await self.process_technology(
                    tech, tech_role, tech_domain, ctx, use_material_debate
                )
                elapsed = time.time() - tech_start
                completed_count += 1
                logger.info(f"[{completed_count}/{total}] {tech} completed ({elapsed:.0f}s)")
                all_results[tech] = result

                # Update checkpoint
                async with checkpoint_lock:
                    completed_techs.add(tech)
                    # Write checkpoint atomically
                    # ...

            except Exception as e:
                logger.error(f"[FAILED] {tech}: {e}")
                failed_techs[tech] = str(e)

    # Launch all tasks
    await asyncio.gather(*[_process_one(tech) for tech in technologies])

    # Sum usage across all contexts
    # ... (aggregate RunUsage from each result)

    # Write combined CSV (ordered by tech list, not completion order)
    # ... (iterate technologies in original order, write rows)

    elapsed_total = time.time() - start_time
    logger.info(f"All technologies complete ({elapsed_total:.0f}s)")
    if failed_techs:
        logger.warning(f"{len(failed_techs)}/{total} technologies failed:")
        for tech, err in failed_techs.items():
            logger.warning(f"  - {tech}: {err}")

    return {
        "successful": len(all_results),
        "failed": len(failed_techs),
        "total": total,
        "failed_technologies": failed_techs,
    }
```

Note: The code above is a skeleton. The implementer should read the existing `run_pipeline()` loop (lines 1138-1248) and adapt the CSV writing, checkpoint, and usage tracking patterns from there.

- [ ] **Step 2: Add branch in `run_pipeline()`**

At the top of `run_pipeline()`, after checkpoint loading and CSV initialization, add:

```python
if self.config.parallel_technologies:
    result = await self._run_parallel(
        technologies, role, domain, tech_roles, tech_domains,
        use_material_debate=use_material_debate,
    )
    # Proceed to normalization
    if not self.config.skip_postprocess_normalization:
        await self._normalize_output()
    return result
```

The existing sequential loop remains as the `else` branch (no changes needed to it beyond the TechnologyContext changes from Task 2).

- [ ] **Step 3: Implement in-memory CSV collection**

In `_run_parallel()`, after `gather` completes, write the combined CSV:

```python
# Write combined CSV in tech list order
with open(self.output_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    for tech in technologies:
        result = all_results.get(tech)
        if not result:
            continue
        for row in result["enriched_data"]:
            row["dependency_type"] = "constituent"
            row["extraction_provenance"] = ""
            writer.writerow(row)
        for row in result.get("pc_enriched_data", []):
            writer.writerow(row)
```

- [ ] **Step 4: Implement set-based checkpointing**

Write checkpoint after each technology completes (inside the `checkpoint_lock`):

```python
import json
import tempfile

async with checkpoint_lock:
    completed_techs.add(tech)
    checkpoint_data = {
        "completed_technologies": sorted(completed_techs),
        "timestamp": datetime.now().isoformat(),
    }
    # Atomic write
    checkpoint_path = Path(self.checkpoint_dir) / "parallel_checkpoint.json"
    tmp = checkpoint_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(checkpoint_data, indent=2))
    tmp.rename(checkpoint_path)
```

On resume, load the checkpoint and filter:

```python
checkpoint_path = Path(self.checkpoint_dir) / "parallel_checkpoint.json"
if checkpoint_path.exists():
    data = json.loads(checkpoint_path.read_text())
    completed_techs = set(data["completed_technologies"])
    technologies = [t for t in technologies if t not in completed_techs]
    logger.info(f"Resuming: {len(completed_techs)} already completed, {len(technologies)} remaining")
```

- [ ] **Step 5: Verify parallel mode works**

Run with a small tech list (2-3 technologies):

```bash
python -m stdn_agentic.main -i config_test_process_consumables.json --parallel-technologies true --max-concurrent-technologies 2
```

Expected: Technologies process concurrently (check timestamps in output), results match sequential mode.

- [ ] **Step 6: Commit**

```bash
git add src/stdn_agentic/orchestrator/pipeline.py
git commit -m "feat: implement parallel technology processing with semaphore"
```

---

## Task 5: Per-Technology Logging

**Files:**
- Modify: `src/stdn_agentic/orchestrator/pipeline.py` (in `_run_parallel()`)

- [ ] **Step 1: Set up per-technology log routing with `contextvars`**

Use Python's `contextvars` to tag the current technology on each async task, then route logs to per-technology files using a filter.

```python
import contextvars
import logging
from pathlib import Path

# Module-level context var
_current_technology: contextvars.ContextVar[str] = contextvars.ContextVar("current_technology", default="")

class TechnologyLogFilter(logging.Filter):
    """Only passes log records matching the handler's technology."""
    def __init__(self, tech_name: str):
        super().__init__()
        self.tech_name = tech_name

    def filter(self, record):
        return _current_technology.get("") == self.tech_name
```

Inside `_process_one()`, set the context var and add a filtered handler:

```python
_current_technology.set(tech)

tech_log_dir = Path("logs/technologies")
tech_log_dir.mkdir(parents=True, exist_ok=True)
safe_name = tech.replace("/", "_").replace(" ", "_")
tech_handler = logging.FileHandler(tech_log_dir / f"{safe_name}.log")
tech_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
tech_handler.addFilter(TechnologyLogFilter(tech))

root_logger = logging.getLogger()
root_logger.addHandler(tech_handler)
try:
    result = await self.process_technology(...)
finally:
    root_logger.removeHandler(tech_handler)
    tech_handler.close()
```

This works because `contextvars` are per-task in asyncio — each concurrent task gets its own value even though they share a thread.

- [ ] **Step 2: Add summary statistics**

After `gather` completes:

```python
elapsed_total = time.time() - start_time
logger.info("=" * 60)
logger.info(f"Parallel processing complete: {len(all_results)}/{total} succeeded in {elapsed_total:.0f}s")
if failed_techs:
    logger.warning(f"{len(failed_techs)} failed:")
    for tech, err in failed_techs.items():
        logger.warning(f"  - {tech}: {err}")
logger.info("=" * 60)
```

- [ ] **Step 3: Commit**

```bash
git add src/stdn_agentic/orchestrator/pipeline.py
git commit -m "feat: add per-technology logging and progress counter"
```

---

## Task 6: Integration Test

**Files:**
- No new test files (use existing test config with `--parallel-technologies`)

- [ ] **Step 1: Run full test with parallel mode**

Use the test config with a small tech list:

```bash
cd ~/git/dpi_stdn_agentic
source .venv/bin/activate
python -m stdn_agentic.main -i config_test_process_consumables.json \
    --parallel-technologies true \
    --max-concurrent-technologies 3
```

Verify:
- All technologies complete
- Output CSV has correct rows
- No duplicate or missing data

- [ ] **Step 2: Compare parallel vs sequential output**

Run the same config sequentially, then diff:

```bash
# Sequential
python -m stdn_agentic.main -i config_test_process_consumables.json
mv output/raw/stdns_output_*.csv /tmp/sequential_output.csv

# Parallel
python -m stdn_agentic.main -i config_test_process_consumables.json \
    --parallel-technologies true
mv output/raw/stdns_output_*.csv /tmp/parallel_output.csv

# Compare (sort both since row order may differ)
sort /tmp/sequential_output.csv > /tmp/seq_sorted.csv
sort /tmp/parallel_output.csv > /tmp/par_sorted.csv
diff /tmp/seq_sorted.csv /tmp/par_sorted.csv
```

Expected: Identical content (row order may differ).

- [ ] **Step 3: Test checkpoint resume**

Start a parallel run, kill it mid-way (Ctrl+C), then resume:

```bash
# Start and interrupt
python -m stdn_agentic.main -i config_d3d3v3.json --parallel-technologies true
# (Ctrl+C after a few technologies complete)

# Resume
python -m stdn_agentic.main -i config_d3d3v3.json --parallel-technologies true
```

Expected: Resumes from where it left off, skips completed technologies.

- [ ] **Step 4: Test with max_concurrent=1 (effectively sequential)**

```bash
python -m stdn_agentic.main -i config_test_process_consumables.json \
    --parallel-technologies true --max-concurrent-technologies 1
```

Expected: Works correctly, same output as sequential mode.

- [ ] **Step 5: Commit any fixes**

```bash
git add src/stdn_agentic/orchestrator/pipeline.py
git commit -m "fix: integration test fixes for parallel technology processing"
```
