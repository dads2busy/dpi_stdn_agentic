# STDN Agentic Framework

A multi-agent AI system for generating **Shallow Technology Dependency Networks (STDNs)** through iterative debate, critique, and consensus-building.

## Overview

STDN Agentic automates the analysis of global technology supply chains by orchestrating LLM-powered agents that propose, critique, and refine technology dependency networks. The framework maps:

```
Technologies → Components → Materials → Producing Countries
```

Each link includes confidence scores and reasoning, making the analysis auditable and interpretable.

## Architecture

The system uses a three-stage pipeline with optional multi-agent debate at each stage:

```
┌──────────────────────┬──────────────────────┬──────────────────────┐
│ Stage 1:             │ Stage 2:             │ Stage 3:             │
│ Component Extraction │ Materials Mapping    │ Country Data         │
├──────────────────────┼──────────────────────┼──────────────────────┤
│ • N debating agents  │ • N debating agents  │ • USGS Database      │
│ • Jaccard-based      │ • Jaccard-based      │ • LLM fallback       │
│   convergence        │   convergence        │ • Voting/consensus   │
└──────────────────────┴──────────────────────┴──────────────────────┘
```

## Quick Start

### Installation

```bash
git clone https://github.com/NSSAC/dpi_stdn_agentic.git
cd dpi_stdn_agentic
uv sync

# Optional: create a .env for runtime toggles and API keys.
# (See docs/CONFIGURATION.md for what env vars are supported.)
cp .env.example .env
```

## Configuration Precedence (Policy A)

STDN Agentic follows **config-first** configuration (Policy A):

1. **CLI flags** (highest precedence for debate/voting settings)
2. **Environment variables / `.env`** for supported runtime toggles and explicit overrides
3. **`config.json`** is the source of truth for core configuration (paths/models/output)

Environment variables do **not** automatically override every `config.json` field; only settings explicitly read from the environment affect runtime behavior.

## Running

### Single run (non-parallel)

Run a single pipeline from a JSON config:

```bash
uv run stdn -i config.json
```

Override debate/voting per stage via CLI flags:

```bash
uv run stdn -i config.json \
  --enable-component-debate true \
  --enable-material-debate false \
  --enable-country-debate false \
  --num-agents-component 5 \
  --num-agents-material 1 \
  --num-agents-country 1
```

### Parallel runs (batch experiments)

Use the parallel launcher to run N pipelines concurrently for a specific debate configuration:

```bash
uv run stdn-parallel --config-type d5v1v1 --num-runs 5 --base-config config.json --delay 5
```

Notes:
- During parallel runs, each child run uses collision-proof naming (`..._runN_...`) to avoid timestamp collisions.
- After all runs complete, raw outputs are renamed back to the standard naming and shared post-processing can run once.

## Configuration

### Configuration Precedence (Policy A: config-first)

STDN Agentic follows **config-first** configuration (Policy A):

1. **CLI flags** (highest precedence for debate/voting settings)
2. **Environment variables / `.env`** for supported runtime toggles and explicit overrides
3. **`config.json`** is the source of truth for core configuration (paths/models/output)

Environment variables do **not** automatically override every `config.json` field; only settings explicitly read from the environment affect runtime behavior.

### Environment Variables (selected)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_COMPONENT_DEBATE` | false | Enable multi-agent debate for components (CLI can override) |
| `ENABLE_MATERIAL_DEBATE` | false | Enable multi-agent debate for materials (CLI can override) |
| `ENABLE_COUNTRY_DEBATE` | false | Enable voting/consensus for countries (CLI can override) |
| `NUM_AGENTS_COMPONENT` | 3 | Number of agents for component debate |
| `NUM_AGENTS_MATERIAL` | 3 | Number of agents for material debate |
| `NUM_AGENTS_COUNTRY` | 3 | Number of agents for country voting |
| `MAX_DEBATE_ROUNDS` | 3 | Maximum debate iterations |
| `CONVERGENCE_THRESHOLD` | 0.8 | Jaccard similarity threshold |
| `STDN_AGENT_RETRIES` | 5 | PydanticAI Agent retry count for validation/tool-call behavior |

### Output Files
### Models (high level)

`config.json` supports:
- `model`: default model
- `component_model`, `materials_model`, `country_model`: per-agent overrides
- `component_normalization_model`: model used specifically for semantic component-name normalization mappings (recommended: `openai:gpt-4.1`)

## Output Files

### Raw and normalized outputs

- Raw CSVs are written under `output/raw/`
- Normalized CSVs and JSON are written under `output/normalized/`

### Filename markers

Output filenames include a marker that encodes the debate configuration, e.g.:

| Example | Meaning |
|--------|---------|
| `stdns_output_d3v1v1_*.csv` | components debate with 3 agents; materials single-agent; countries voting/single (marker is `v1` when disabled) |
| `stdns_output_v1v1v1_*.csv` | single-agent / no debate |

During parallel runs, per-run raw files include `_runN_` to avoid collisions, and are renamed back after completion.

## Documentation

| Document | Description |
|----------|-------------|
| [AGENTS.md](docs/AGENTS.md) | Agent system including schemas and confidence scoring |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | JSON config, env vars, and run modes |
| [PIPELINE.md](docs/PIPELINE.md) | Pipeline stages, execution modes, outputs, and troubleshooting |
| [PARALLEL_RUNS.md](docs/PARALLEL_RUNS.md) | Parallel batch experiments (`stdn-parallel`), collision-proof outputs, and monitoring |
| [PROMPTS.md](docs/PROMPTS.md) | Reference of LLM prompts |
| [DEBATE_SYSTEM.md](docs/DEBATE_SYSTEM.md) | Multi-agent debate mechanism including convergence and voting |
| [DEBATE_EVIDENCE_REPORT.md](docs/DEBATE_EVIDENCE_REPORT.md) | Empirical analysis comparing debate vs. single-agent mode |
| [SAMPLE_TRANSCRIPT.md](docs/SAMPLE_TRANSCRIPT.md) | Annotated example debate transcript |

## Project Structure

```
src/stdn_agentic/
├── main.py                 # CLI entry point
├── agents/                 # Agent definitions (component, materials, country)
├── orchestrator/           # Pipeline coordination and stage logic
├── debate/                 # Multi-agent debate orchestrators
├── data/                   # Data loaders, USGS client, caching
└── debate_transcripts/     # Saved debate transcripts
```

## Key Features

- Multi-agent debate with convergence metrics (components/materials)
- Voting/consensus for country production data when applicable
- Multi-tier data retrieval: in-memory cache → USGS database → LLM fallback
- Persistent caches and auditable debate transcripts
- Confidence scoring at every stage with reasoning
- Parallel batch runner (`stdn-parallel`) for experiment sweeps

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) for dependency management
- LLM backend: Ollama (local) or OpenAI/Anthropic API

## License

[Specify license]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests: `uv run pytest`
4. Submit a pull request
