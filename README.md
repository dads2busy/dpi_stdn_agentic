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
│ • 3 Debating Agents  │ • 3 Debating Agents  │ • USGS Database      │
│ • Jaccard-based      │ • Jaccard-based      │ • LLM Fallback       │
│   convergence        │   convergence        │ • Borda Voting       │
└──────────────────────┴──────────────────────┴──────────────────────┘
```

## Quick Start

### Installation

```bash
git clone https://github.com/NSSAC/dpi_stdn_agentic.git
cd dpi_stdn_agentic
uv sync
cp .env.example .env
# Edit .env to configure API keys and settings
```

### Running

```bash
# Single-agent mode (fastest)
uv run stdn

# Multi-agent debate mode
export ENABLE_COMPONENT_DEBATE=true
export ENABLE_MATERIAL_DEBATE=true
export ENABLE_COUNTRY_DEBATE=true
uv run stdn
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_COMPONENT_DEBATE` | false | Enable multi-agent debate for components |
| `ENABLE_MATERIAL_DEBATE` | false | Enable multi-agent debate for materials |
| `ENABLE_COUNTRY_DEBATE` | false | Enable Borda voting for countries |
| `NUM_AGENTS_COMPONENT` | 3 | Number of agents for component debate |
| `NUM_AGENTS_MATERIAL` | 3 | Number of agents for material debate |
| `NUM_AGENTS_COUNTRY` | 3 | Number of agents for country voting |
| `MAX_DEBATE_ROUNDS` | 3 | Maximum debate iterations |
| `CONVERGENCE_THRESHOLD` | 0.8 | Jaccard similarity threshold |

### Output Files

Output filenames encode the debate configuration:

| Filename | Configuration |
|----------|---------------|
| `stdns_output_d3d3v3_*.csv` | Debate (3 agents) for all phases |
| `stdns_output_v1v1v1_*.csv` | Single agent, no debate |

## Documentation

| Document | Description |
|----------|-------------|
| [AGENTS.md](docs/AGENTS.md) | Detailed documentation of the agent system including Component, Materials, and Country agents with their schemas and confidence scoring |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Complete configuration guide including JSON config, environment variables, and installation instructions |
| [PIPELINE.md](docs/PIPELINE.md) | Pipeline stages documentation with module organization, execution modes, and troubleshooting |
| [PROMPTS.md](docs/PROMPTS.md) | Complete reference of all LLM prompts used in the system including agent system prompts, debate prompts, and orchestrator prompts |
| [DEBATE_SYSTEM.md](docs/DEBATE_SYSTEM.md) | Multi-agent debate mechanism including Jaccard convergence, critique generation, and Borda voting |
| [DEBATE_EVIDENCE_REPORT.md](docs/DEBATE_EVIDENCE_REPORT.md) | Empirical analysis comparing debate vs. single-agent mode across stability, confidence, and hallucination reduction |

## Project Structure

```
src/stdn_agentic/
├── main.py                 # CLI entry point
├── agents/                 # Agent definitions (component, materials, country)
├── orchestrator/           # Pipeline coordination and stage logic
├── debate/                 # Multi-agent debate orchestrators
│   ├── component_debater.py
│   ├── material_debater.py
│   └── material_country_debater.py
├── data/                   # Data loaders, USGS client, caching
└── debate_transcripts/     # Saved debate transcripts
```

## Key Features

- **Multi-agent debate** with Jaccard-based convergence for components and materials
- **Borda voting** for country production data consensus
- **Three-tier data retrieval**: Memory cache → USGS database → LLM fallback
- **30-day LLM cache** to avoid redundant expensive calls
- **Debate transcripts** in JSON and TXT formats for auditability
- **Confidence scoring** at every stage with reasoning

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) for dependency management
- LLM backend: [Ollama](https://ollama.com/) (local) or OpenAI/Anthropic API

## License

[Specify license]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests: `uv run pytest`
4. Submit a pull request
