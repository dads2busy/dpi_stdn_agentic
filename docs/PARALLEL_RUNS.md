# Parallel Runs Guide (`stdn-parallel`)

This guide explains how to run **parallel batch experiments** with STDN Agentic using the `stdn-parallel` launcher, how output naming works, where files go, and how to monitor progress.

If you only want to run a single pipeline once, see the single-run mode (`stdn`) in `README.md` and `docs/PIPELINE.md`.

---

## When to use `stdn` vs `stdn-parallel`

### Use `stdn` (single run) when:
- You want one end-to-end pipeline run for a technology list.
- You are iterating on prompts/configuration and want quick feedback.
- You want the default end-of-run post-processing behavior (unless you explicitly disable it).

### Use `stdn-parallel` (parallel batch runs) when:
- You want **multiple independent runs** under the same debate/voting settings to study stability/variance.
- You want to run **multiple runs concurrently** to reduce wall-clock time.
- You want **one shared post-processing normalization pass** across all raw outputs of a batch.

---

## Basic usage

### Single run (for reference)
```bash
uv run stdn -i config.json
```

### Parallel batch run
Run 5 parallel pipelines with a debate configuration marker:

```bash
uv run stdn-parallel \
  --config-type d5v1v1 \
  --num-runs 5 \
  --base-config config.json \
  --delay 5
```

**What this does:**
- Creates per-run DB copies and per-run config files.
- Launches each run with a short delay between them.
- Validates that each run produces its output file.
- Monitors that files are being created / growing.
- After all runs finish:
  - renames per-run raw outputs back to standard naming
  - runs one shared normalization across the consolidated raw outputs
  - generates JSON from normalized CSVs

---

## `--config-type` format

`--config-type` is a compact string that describes the run mode per stage:

- Stage order: **component**, **material**, **country**
- Each segment is `[d|v][N]`
  - `dN`: debate with N agents
  - `vN`: voting/single mode encoding (for non-debate stages; country uses voting semantics when enabled)

Examples:

- `v1v1v1`: fully single-agent style pipeline (no debate)
- `d5v1v1`: debate in components with 5 agents; materials single; countries single/voting marker
- `d3d3v3`: debate in components & materials; country voting with 3

> Note: Output filenames encode an “actual filename marker” consistent with orchestrator behavior (especially for the country stage, which is encoded as voting `vN`).

---

## Configuration precedence (Policy A: config-first)

STDN Agentic is **config-first**:

1. **CLI flags** (highest precedence for debate/voting settings)
2. **Environment variables / `.env`** only for explicitly supported runtime toggles and overrides
3. **`config.json`** is the source of truth for core configuration (paths/models/output)

Environment variables do **not** automatically override all config fields.

For parallel experiments, prefer **explicit CLI configuration via `stdn-parallel --config-type ...`** rather than relying on `.env` defaults.

---

## Outputs: where files go

### Raw outputs
- Directory: `output/raw/`
- Files: `stdns_output_<marker>_<timestamp>.csv` (standard naming)

During parallel runs, collision-proof per-run naming is used:
- `output/raw/stdns_output_<marker>_runN_<marker>_<timestamp>.csv`

The `_runN_` segment prevents collisions when multiple runs write files around the same timestamp.

### Normalized outputs + JSON
- Directory: `output/normalized/`
- Files:
  - normalized CSVs: `stdns_output_<marker>_<timestamp>.csv`
  - JSON (from normalized CSV): `stdns_output_<marker>_<timestamp>.json`
  - normalization manifests: `normalization_manifest_<timestamp>.json`

### Logs
- Per-run logs: `output/<config-type>_runN.log`
  - Example: `output/d5v1v1_run3.log`
- Launcher log: whatever you redirect `stdn-parallel` to (recommended).

### Debate transcripts
- Directory: `src/stdn_agentic/debate_transcripts/results/`
- These are written when transcript saving is enabled.

---

## Post-processing behavior in parallel mode

Parallel child runs generally set:
- `skip_postprocess_normalization=true`
- `skip_json_output=true`

This prevents N redundant normalization/JSON passes while runs are still ongoing.

After all runs complete, the launcher performs:
1. Rename per-run raw outputs back to standard naming (removes `_runN_`)
2. One shared normalization pass across all raw outputs for the batch
3. JSON generation from normalized CSVs

---

## Monitoring progress

### Monitor logs (most reliable)
Tail per-run logs:
```bash
tail -f output/d5v1v1_run*.log
```

Progress is often best estimated by counting:
- `Successfully processed: <tech>` lines
- `STDN Generation Completed` summary lines

### Monitor raw CSV growth (bursty)
Raw CSVs are typically written/appended **at phase boundaries** (so growth can be “bursty” rather than continuous). Don’t assume “no growth for 30 seconds” means “stuck”; check logs too.

### Check that processes are alive
On macOS/Linux:
```bash
ps aux | egrep 'stdn -i config_d5v1v1_run|stdn-parallel --config-type d5v1v1' | grep -v egrep
```

---

## Recommended stability settings

### Retries
To reduce failures from schema validation and transient tool/model behavior:

```bash
export STDN_AGENT_RETRIES=5
```

### Normalization model (config-driven)
For component semantic normalization mapping (a schema-sensitive step), use a more reliable model:

In `config.json`:
```json
"component_normalization_model": "openai:gpt-4.1"
```

This allows the main extraction agents to use a lighter model (e.g. `openai:gpt-4.1-mini`) while normalization uses a stronger model.

---

## Common pitfalls

- **Starting “3 more” after a “2 run” batch**: the launcher uses `run1..runN` numbering and renaming logic. Launching a second batch with overlapping run indices can cause collisions. Prefer stopping and relaunching a single coherent 5-run batch, or extend the launcher to support a `--start-run-index`.
- **Assuming `.env` overrides config**: under Policy A, `.env` only affects behavior where env vars are explicitly read.
- **Interpreting partial outputs as success**: confirm completion by checking the per-run log summary and counts of “Successfully processed”.

---

## Example: reproducible 5-run batch

```bash
export STDN_AGENT_RETRIES=5

uv run stdn-parallel \
  --config-type d5v1v1 \
  --num-runs 5 \
  --base-config config.json \
  --delay 5
```
