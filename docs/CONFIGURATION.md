# STDN Configuration Guide

Configuration in STDN Agentic is **config-first**: a JSON config file (by default `config.json`) is the source of truth for core settings, while `.env` / environment variables are used only for **explicitly supported runtime toggles and overrides**.

## Configuration Precedence

1. **CLI flags** (highest precedence for debate/voting settings)
2. **Environment variables / `.env`** (only where explicitly supported by the code)
3. **`config.json`** (source of truth for core configuration: paths, models, output)

Environment variables do **not** automatically override every `config.json` field; only settings explicitly read from the environment affect runtime behavior.

This guide documents:
- `config.json` fields (core configuration)
- supported environment variables (runtime toggles/overrides)
- differences between single runs (`stdn`) and parallel runs (`stdn-parallel`)

## Minimal Configuration

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "openai:gpt-4.1-mini",
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "output_dir": "./output"
}
```

You can also use an Ollama model, e.g. `"model": "ollama:qwen2.5:7b"`, as long as your runtime is configured accordingly.

## Full Configuration (models + output + caching)

```json
{
  "import_tech_list": "./data/tech_list.csv",

  "model": "openai:gpt-4.1-mini",
  "component_model": "openai:gpt-4.1-mini",
  "materials_model": "openai:gpt-4.1-mini",
  "country_model": "openai:gpt-4.1-mini",

  "component_normalization_model": "openai:gpt-4.1",

  "output_dir": "./output",
  "output_csv_filename": "stdns_output",

  "materials_hs_codes_listing": "./data/hs_codes_and_usgs_names.csv",
  "materials_column_name": "Elements_Compounds",

  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "top_n_countries": 5,
  "years_to_query": [2024, 2023],
  "write_nulls_to_output": true,

  "enable_llm_fallback_cache": true,
  "llm_fallback_cache_dir": "./data/llm_fallback_cache",
  "llm_fallback_cache_ttl_hours": 720,

  "save_transcripts": true,
  "checkpoint_interval": 5,

  "skip_postprocess_normalization": false,
  "skip_json_output": false
}
```

Notes:
- `component_normalization_model` is used specifically for **semantic component-name normalization mappings** (e.g., to reduce schema validation failures). A more reliable model (e.g. `openai:gpt-4.1`) is recommended.
- In parallel runs, the launcher sets `skip_postprocess_normalization=true` and `skip_json_output=true` in the per-run configs so post-processing can be done once per batch.

## Key Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `import_tech_list` | string | — | Path to input CSV with technology list |
| `model` | string | — | Default LLM model identifier (e.g., `openai:gpt-4.1-mini`, `ollama:qwen2.5:7b`) |
| `component_model` | string\|null | null | Per-agent model override for component extraction (defaults to `model`) |
| `materials_model` | string\|null | null | Per-agent model override for materials extraction (defaults to `model`) |
| `country_model` | string\|null | null | Per-agent model override for country data (defaults to `model`) |
| `component_normalization_model` | string\|null | null | Model used specifically for semantic component-name normalization mappings (defaults to `component_model` → `model`) |
| `usgs_database` | string | — | Path to USGS DuckDB database |
| `output_dir` | string | `./output` | Directory for output files |
| `output_csv_filename` | string | `stdns_output` | Base name for output CSV files |
| `materials_hs_codes_listing` | string | — | Path to HS codes and material names CSV |
| `materials_column_name` | string | `Elements_Compounds` | Column name for materials in HS codes file |
| `top_n_countries` | int | 5 | Number of top countries to return per material |
| `years_to_query` | list[int] | `[2024, 2023]` | Years to query for production data |
| `write_nulls_to_output` | bool | true | Include null values in output |
| `enable_llm_fallback_cache` | bool | true | Cache LLM fallback results for a TTL period |
| `llm_fallback_cache_dir` | string | `./data/llm_fallback_cache` | Directory for LLM fallback cache |
| `llm_fallback_cache_ttl_hours` | int | 720 | Cache TTL in hours (720 = 30 days) |
| `save_transcripts` | bool | true | Save debate JSON/TXT transcripts |
| `checkpoint_interval` | int | 5 | Save checkpoint every N technologies |
| `skip_postprocess_normalization` | bool | false | Skip end-of-run batch normalization (recommended true for parallel child runs) |
| `skip_json_output` | bool | false | Skip end-of-run JSON generation (recommended true for parallel child runs) |

---

## Debate and Runtime Environment Variables (supported)

Debate/voting settings can be provided as:
- **CLI flags** (preferred for reproducibility; used by `stdn-parallel` when launching child runs)
- **environment variables** (convenient defaults for local runs)

### Debate toggles and parameters

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_COMPONENT_DEBATE` | bool | false | Enable multi-agent debate for components (CLI can override) |
| `ENABLE_MATERIAL_DEBATE` | bool | false | Enable multi-agent debate for materials (CLI can override) |
| `ENABLE_COUNTRY_DEBATE` | bool | false | Enable voting/consensus for countries (CLI can override) |
| `NUM_AGENTS_COMPONENT` | int | 3 | Number of agents for component debate |
| `NUM_AGENTS_MATERIAL` | int | 3 | Number of agents for material debate |
| `NUM_AGENTS_COUNTRY` | int | 3 | Number of agents for country voting |
| `MAX_DEBATE_ROUNDS` | int | 3 | Maximum debate iterations per stage |
| `CONVERGENCE_THRESHOLD` | float | 0.8 | Similarity threshold to stop debating |
| `DEBATE_TOP_P` | float | 0.0001 | Sampling parameter for debate agents |
| `SAVE_TRANSCRIPTS` | bool | true | Save debate JSON/TXT transcripts |

### Reliability overrides

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STDN_AGENT_RETRIES` | int | 5 | Retry count used for pydantic_ai Agent validation/tool-call behavior (and output validation retries where configured) |
| `STDN_COMPONENT_NORMALIZATION_MODEL` | string | (none) | Optional override for the semantic component-name normalization model. Prefer `component_normalization_model` in `config.json` for config-first behavior. |

---

## .env File Configuration

Create a `.env` file in the project root to configure debate settings:

```bash
# .env file example
OLLAMA_BASE_URL=http://localhost:11434/v1

# Debate toggles (per phase)
ENABLE_COMPONENT_DEBATE=true
ENABLE_MATERIAL_DEBATE=true
ENABLE_COUNTRY_DEBATE=true

# Number of agents per phase (only used when debate is enabled)
NUM_AGENTS_COMPONENT=3
NUM_AGENTS_MATERIAL=3
NUM_AGENTS_COUNTRY=3

# Debate parameters
MAX_DEBATE_ROUNDS=3
CONVERGENCE_THRESHOLD=0.7

# Caching
ENABLE_LLM_FALLBACK_CACHE=true
```

---

## Environment Variable Overrides

You can also set these as shell environment variables (useful for local development):

```bash
# Debate toggles (per phase)
export ENABLE_COMPONENT_DEBATE=true
export ENABLE_MATERIAL_DEBATE=true
export ENABLE_COUNTRY_DEBATE=true

# Number of agents per phase (only used when debate is enabled)
export NUM_AGENTS_COMPONENT=3
export NUM_AGENTS_MATERIAL=3
export NUM_AGENTS_COUNTRY=3

# Debate parameters
export MAX_DEBATE_ROUNDS=3
export CONVERGENCE_THRESHOLD=0.8
export SAVE_TRANSCRIPTS=true
export DEBATE_TOP_P=0.0001

# Reliability
export STDN_AGENT_RETRIES=5
```

For parallel batch runs, prefer passing debate settings via the `stdn-parallel --config-type ...` launcher rather than relying on environment variables.

---

## Installation and Prerequisites

### Requirements

- **Python 3.10+**
- **[uv](https://github.com/astral-sh/uv)** for fast dependency management
- At least one LLM backend:
  - **Local:** [Ollama](https://ollama.com/) with models like `qwen2.5:7b`
  - **Remote:** OpenAI, Anthropic, or other hosted API

### Quick Installation

```bash
# Clone the repository
git clone https://github.com/your-org/dpi_stdn_agentic.git
cd dpi_stdn_agentic

# Install dependencies
uv sync

# Install with development tools
uv sync --group dev

# Set up environment configuration
cp .env.example .env
# Edit .env to add your API keys and customize settings

# (Optional) Install and start Ollama for local LLM inference
ollama serve
ollama pull qwen2.5:7b
```

### Environment Setup

The `.env` file contains runtime configuration including API keys and debate settings. Copy the example file and customize it:

```bash
cp .env.example .env
```

Then edit `.env` to add your API keys:

```bash
# For Anthropic Claude models
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# For OpenAI models (optional)
# OPENAI_API_KEY=your-openai-api-key-here
```

**Important:** The `.env` file is excluded from git (via `.gitignore`) to protect your API keys. Never commit secrets to the repository.
