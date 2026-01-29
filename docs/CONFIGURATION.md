# STDN Configuration Guide

Configuration in STDN Agentic lives in a JSON file (by default `config.json`) and is designed to be explicit but approachable so that both engineers and analysts can adjust the system without editing code.

## Minimal Configuration

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:7b",
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "output_dir": "./output"
}
```

## Full Configuration with Debate Options

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:14b",
  "output_dir": "./output",
  "output_csv_filename": "stdns_output",

  "materials_hs_codes_listing": "./data/hs_codes_and_usgs_names.csv",
  "materials_column_name": "Elements_Compounds",

  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "top_n_countries": 5,
  "years_to_query": [2024, 2023],
  "write_nulls_to_output": true,

  "enable_llm_fallback_cache": true,
  "llm_fallback_cache_dir": "./cache/llm_fallback",
  "llm_fallback_cache_ttl_hours": 720,

  "save_transcripts": true,
  "checkpoint_interval": 5
}
```

## Key Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `import_tech_list` | string | — | Path to input CSV with technology list |
| `model` | string | — | LLM model specification (e.g., `ollama:qwen2.5:7b`) |
| `usgs_database` | string | — | Path to USGS DuckDB database |
| `output_dir` | string | `./output` | Directory for output files |
| `output_csv_filename` | string | `stdns_output` | Base name for output CSV files |
| `materials_hs_codes_listing` | string | — | Path to HS codes and material names CSV |
| `materials_column_name` | string | `Elements_Compounds` | Column name for materials in HS codes file |
| `top_n_countries` | int | 5 | Number of top countries to return per material |
| `years_to_query` | list[int] | `[2024, 2023]` | Years to query for production data |
| `write_nulls_to_output` | bool | true | Include null values in output |
| `enable_llm_fallback_cache` | bool | true | Cache LLM debate results for 30 days |
| `llm_fallback_cache_dir` | string | `./cache/llm_fallback` | Directory for LLM fallback cache |
| `llm_fallback_cache_ttl_hours` | int | 720 | Cache TTL in hours (720 = 30 days) |
| `save_transcripts` | bool | true | Save debate JSON/TXT transcripts |
| `checkpoint_interval` | int | 5 | Save checkpoint every N technologies |

---

## Debate Environment Variables

Debate settings are configured via environment variables, not in config.json.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_COMPONENT_DEBATE` | bool | false | Enable multi-agent debate for components |
| `ENABLE_MATERIAL_DEBATE` | bool | false | Enable multi-agent debate for materials |
| `ENABLE_COUNTRY_DEBATE` | bool | false | Enable Borda voting for countries (when USGS misses) |
| `NUM_AGENTS_COMPONENT` | int | 3 | Number of agents for component debate |
| `NUM_AGENTS_MATERIAL` | int | 3 | Number of agents for material debate |
| `NUM_AGENTS_COUNTRY` | int | 3 | Number of agents for country voting |
| `MAX_DEBATE_ROUNDS` | int | 3 | Maximum debate iterations per stage |
| `CONVERGENCE_THRESHOLD` | float | 0.8 | Jaccard similarity threshold to stop debating |
| `DEBATE_TOP_P` | float | 0.0001 | Top-p sampling (very low for deterministic proposals) |
| `SAVE_TRANSCRIPTS` | bool | true | Save debate JSON/TXT transcripts |

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

You can also set these as shell environment variables:

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
```

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
