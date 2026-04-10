# DPI STDN Agentic — Development Guide

Multi-agent AI system for automated supply chain dependency analysis. Orchestrates LLM-powered agents through iterative debate to map technology → component → material → country dependency networks.

## Commands

### CLI Entry Points

```bash
# Single pipeline run
uv run stdn -i config.json

# With debate overrides
uv run stdn -i config.json --enable-component-debate true --num-agents-component 5

# Parallel batch runs (N instances, same config)
uv run stdn-parallel --config-type d5v1v1 --num-runs 5 --base-config config.json
```

### Testing

```bash
pytest src/stdn_agentic/tests/ -v                     # All tests
pytest src/stdn_agentic/tests/unit/ -v                 # Unit only
pytest src/stdn_agentic/tests/integration/ -v          # Integration only
pytest -m "not slow" -v                                # Skip slow tests
pytest --cov=stdn_agentic --cov-report=html            # Coverage
```

### Build

```bash
uv build
```

## Architecture

### Directory Structure

```
src/stdn_agentic/
├── main.py              # CLI orchestrator, config discovery, argument parsing
├── models.py            # ConfigModel (config validation), STDNDependencies (runtime deps)
├── agents/              # Component, Materials, Country agent implementations + factory
├── orchestrator/        # Pipeline stages (5 extractors), checkpoint management, state tracking
├── debate/              # Multi-agent debate engines (component, material, country debaters)
├── data/                # USGS client, caching layer (MaterialCache), loaders
├── core/                # Shared schemas, constants, base agent class
├── normalization/       # Post-processing component name mapping, canonical vocabulary
├── reporting/           # Debate transcript logging and formatting
└── tests/               # Unit, integration, e2e tests
```

### Pipeline Flow (4 Stages)

1. **Stage 1 — Component Extraction**: N agents debate to extract technology → components with confidence scores. Convergence measured via Jaccard similarity across agent proposals.
2. **Stage 2a — Materials Mapping**: For each component, N agents debate to identify constituent materials. Same Jaccard convergence.
3. **Stage 2b — Process Consumables** (optional): Extracts assembly/component-level consumables if `enable_process_consumables=true`.
4. **Stage 3 — Country Data**: Looks up production data per material. Multi-tier: USGS database first → LLM fallback cache → LLM debate → voting. Returns top-N countries per material.
5. **Stage 4 — Post-Processing**: Component name normalization using canonical vocabulary, JSON/CSV output generation.

### Data Flow

```
Input: tech_list.csv + config.json
  → Stage 1-3: Incremental CSV writes as each technology completes
  → Raw CSV:        output/raw/stdns_output_<config>_<timestamp>.csv
  → Normalized CSV:  output/normalized/stdns_output_<config>_<timestamp>.csv
  → Structured JSON: output/normalized/stdns_output_<config>_<timestamp>.json
  → Transcripts:     output/transcripts/<technology>_<config>_<timestamp>.txt/json
```

### Debate System

- `MultiAgentDebater` orchestrates N agents → critique rounds → convergence scoring
- Agents propose independently → peers critique → proposals refined in next round
- Convergence = max Jaccard similarity across all agent pair-wise comparisons
- Stops when convergence >= threshold OR max_debate_rounds reached
- Final output = union of all proposals, confidence weighted by agent alignment
- Same pattern for component, material, and country debates

### Caching

- **MaterialCache** (`data/cache.py`): TTL-based disk cache (default 24h) for material queries. Keys hashed to safe filenames, file locks prevent concurrent corruption.
- **LLMFallbackCache** (`data/llm_fallback_cache.py`): Persistent JSON cache for LLM country data. Fallback flow: USGS → check cache → call LLM debate → store result. Default TTL 720h.
- Cache locations: `.cache/` (material), `./data/llm_fallback_cache/` (LLM fallback)

### Key Classes

- `STDNOrchestrator` (`orchestrator/pipeline.py`) — Coordinates all stages, checkpoint/resume, CSV writing
- `ComponentExtractor` — Runs debate, normalizes components, confidence scoring
- `MaterialsExtractor` — Material extraction with debate
- `CountryDataEnricher` — Country data enrichment with USGS/LLM fallback
- `CountryDataRepository` — Repository pattern for country data queries with multi-tier lookup
- `CheckpointManager` — Persists state every N techs (configurable); resumes on restart if same config

## Configuration

### Config File (JSON)

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "qwen2.5:7b",
  "output_dir": "./output",
  "output_csv_filename": "stdns_output",

  "component_model": null,
  "materials_model": null,
  "country_model": null,

  "materials_hs_codes_listing": "./data/hs_codes_and_usgs_names.csv",
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "years_to_query": [2023, 2024],

  "enable_process_consumables": true,
  "parallel_technologies": false,
  "max_concurrent_technologies": 10,
  "top_n_countries": 5,
  "enable_checkpoints": false,
  "component_debate_use_personas": false
}
```

### Key Parameters

- `model` — Default LLM (format: `"provider:model"`, e.g., `"ollama:qwen2.5:7b"`, `"openai:gpt-4"`)
- Per-agent model overrides: `component_model`, `materials_model`, `country_model`
- Debate temperature: `component_debate_temperature`, `material_debate_temperature`, `country_debate_temperature`
- Debate top-p: `component_debate_top_p` (default 0.0001)
- `enable_process_consumables` — Stage 2b toggle
- `top_n_countries` — Max countries per material (1-20, default 5)
- `enable_llm_fallback_cache` — Persistent fallback cache (default true, TTL 720h)

### Environment Variables

- `STDN_MODEL` — Fallback default model (auto-set from config.model)
- `ENABLE_COMPONENT_DEBATE`, `ENABLE_MATERIAL_DEBATE`, `ENABLE_COUNTRY_DEBATE` — Stage toggles
- `NUM_AGENTS_COMPONENT`, `NUM_AGENTS_MATERIAL`, `NUM_AGENTS_COUNTRY` — Agent counts
- `MAX_DEBATE_ROUNDS` — Max debate iterations
- `CONVERGENCE_THRESHOLD` — Jaccard threshold (default 0.8)
- `STDN_AGENT_RETRIES` — PydanticAI agent retry count (default 5)
- `OLLAMA_BASE_URL` — Ollama endpoint (default `http://localhost:11434/v1`)
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` — API keys for cloud providers

### Config Precedence

CLI args > environment variables > config.json defaults. Not all env vars override config fields.

## Data

### Input

CSV with column `tech` (technology name); optionally `role`, `domain` for per-tech contextualization.

### Output CSV Columns

`technology`, `component`, `component_confidence`, `component_reasoning`, `material`, `material_confidence`, `material_reasoning`, `hs_code`, `country`, `meas_unit`, `amount`, `percentage`, `country_confidence`, `country_reasoning`, `dependency_type` (constituent|process_consumable), `extraction_provenance`

### Config Marker in Filenames

- `d3v1v1` = debate-3 agents for components, single-agent for materials and countries
- `v1v1v1` = all single-agent (no debate)
- Format: `d{component_agents}v{material_agents}v{country_agents}`

## Key Patterns

### Adding a New Technology

1. Add row to tech list CSV: `technology_name,role,domain`
2. Run pipeline — agents auto-extract components, materials, countries
3. Post-processing normalizes component names via LLM semantic mapping
4. Optional: pre-populate canonical vocabulary (`data/component_canonical_vocab.json`)

### Parallel Runs

- `stdn-parallel` spawns N child processes, each with same config but unique timestamp
- Raw outputs use `_runN_` suffix to avoid collisions
- Useful for measuring debate quality variance at different agent counts

### Gotchas

- Config string (d3v1v1) must match in transcripts and output filenames for traceability
- Process consumables stage is optional; toggle carefully if downstream code expects it
- Checkpoint resume only works if config (debate settings, model) hasn't changed since checkpoint
- LLM fallback cache is persistent; clear `./data/llm_fallback_cache/` manually if stale results interfere
- Country name casing varies in LLM output (e.g., "CHINA" vs "China") — normalize downstream

## Testing

### Structure

```
src/stdn_agentic/tests/
├── unit/           # Fast isolated tests (mocked dependencies)
├── integration/    # Multi-component tests (real data/caches, no external APIs)
└── e2e/            # Full pipeline tests (10+ seconds, real orchestrator)
```

### Key Fixtures (conftest.py)

- `sample_ontology` — Standard material list
- `sample_components` — Standard component names
- `mock_stdn_dependencies` — Mocked runtime deps
- `mock_run_context` — Mocked agent context

Tests mirror source structure: `src/stdn_agentic/agents/` → `tests/unit/agents/test_*.py`

## Supply Chain Knowledge Base

For broader context on supply chain intelligence work — materials, technologies, countries, policies, and how this project connects to related work — read the wiki index at:

~/git/personal-ai-wiki/index.md

Then read relevant wiki pages based on the current task. The wiki is maintained following the schema in ~/git/personal-ai-wiki/CLAUDE.md.
