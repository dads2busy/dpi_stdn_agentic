# STDN Agentic

**Shallow Technology Dependency Network** generation using multi-agent debate and Pydantic AI.

A research tool for analyzing technology supply chains by extracting component hierarchies, identifying raw materials, and mapping global production sources using a combination of LLM-based agents, USGS mineral commodity databases, and multi-agent consensus systems.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Usage](#usage)
- [Output Format](#output-format)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Citation](#citation)

---

## Overview

**STDN Agentic** generates **Shallow Technology Dependency Networks** - structured representations of:
1. **Component hierarchies** within technologies (e.g., smartphone → display, battery, processor)
2. **Raw material compositions** for each component (e.g., display → glass, indium, rare earth elements)
3. **Global production sources** for each material (e.g., indium → China 60%, South Korea 15%)

The system uses **multi-agent debate** to achieve consensus on component extraction, combining multiple LLM perspectives to reduce hallucination and improve accuracy.

### What is "Shallow"?

"Shallow" refers to a **single-level decomposition**: technologies → components → materials. Unlike deep hierarchical networks, STDN focuses on the first critical layer of supply chain dependencies, making it computationally efficient for policy analysis.

```
Technology Level:        Smartphone
                            |
Component Level:     [Display] [Battery] [Processor] [Camera]
                        |         |          |           |
Material Level:     Glass     Lithium    Silicon     Glass
                    Indium    Cobalt     Copper      Rare Earths
                    REE       Nickel     Gold        Aluminum
```

---

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    STDN Generation Pipeline                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
         ┌────────────────────────────────────────┐
         │   1. MULTI-AGENT DEBATE SYSTEM         │
         │   ┌──────────┐  ┌──────────┐           │
         │   │ Agent 1  │  │ Agent 2  │           │
         │   │ (qwen)   │  │ (qwen)   │           │
         │   └────┬─────┘  └─────┬────┘           │
         │        │              │                 │
         │   ┌────▼──────────────▼────┐           │
         │   │  Semantic Normalization│           │
         │   │  (LLM-based consensus) │           │
         │   └────────────┬────────────┘           │
         │                ▼                        │
         │         ComponentList                   │
         └────────────────┬───────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────────────┐
         │   2. MATERIALS EXTRACTION              │
         │   (with fuzzy ontology matching)       │
         │                                         │
         │   Components → Materials Agent          │
         │   + Retry Logic (exponential backoff)  │
         │   + Ontology Validation                 │
         └────────────────┬───────────────────────┘
                          │
                          ▼
         ┌────────────────────────────────────────┐
         │   3. COUNTRY DATA AGGREGATION          │
         │                                         │
         │   ┌─────────────┐    ┌──────────────┐  │
         │   │ USGS DB     │ or │ LLM Fallback │  │
         │   │ (DuckDB)    │    │ (Estimated)  │  │
         │   └─────────────┘    └──────────────┘  │
         │                                         │
         │   + Caching Layer                       │
         └────────────────┬───────────────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │  CSV Output   │
                  │  + Transcripts│
                  └───────────────┘
```

### Component Architecture

```
src/stdn_agentic/
├── agents/
│   ├── component_agent.py    # Component extraction with debate
│   ├── materials_agent.py    # Materials extraction + fuzzy matching
│   ├── country_agent.py      # LLM-based country fallback
│   └── factory.py            # Agent creation & caching
├── orchestrator/
│   ├── pipeline.py           # Main orchestration logic
│   └── debater.py            # Multi-agent debate system
├── data/
│   ├── usgs_client.py        # DuckDB USGS database client
│   ├── repository.py         # Unified data access layer
│   └── cache.py              # Material/country data cache
├── models.py                 # Pydantic models (STDNDependencies, ConfigModel)
└── main.py                   # CLI entry point
```

---

## Features

### ✨ Core Capabilities

- **Multi-Agent Debate**: 3 independent LLM agents debate and reach consensus on component lists
- **Semantic Normalization**: LLM-based merging of similar components ("battery pack" ≈ "lithium-ion battery")
- **Fuzzy Material Matching**: Multi-strategy matching (exact, variant, partial, similarity) against material ontology
- **USGS Database Integration**: DuckDB-based querying of World Mineral Commodity Reports (2022-2025)
- **LLM Fallback**: Automatic fallback to LLM estimates when USGS data unavailable
- **Intelligent Caching**: Reduces redundant queries for repeated materials
- **Retry Logic**: Exponential backoff for Ollama stability (1s, 2s, 4s delays)
- **Debate Transcripts**: Full audit trail of agent discussions saved to JSON

### 🔧 Technical Highlights

- **Pydantic AI v0.0.14+** agents with proper type safety
- **Ollama compatibility mode** (tools disabled by default)
- **Pandas DataFrame** handling for USGS queries
- **Pydantic v2** ConfigDict (no deprecation warnings)
- **Comprehensive validation** (7 checkpoints in materials extraction)
- **Type-safe models** with basedpyright compatibility

---

## Installation

### Prerequisites

- **Python 3.12+**
- **Ollama** (or OpenAI API key)
- **DuckDB** (installed automatically)
- **uv** (Astral's package manager)

### Install uv

```
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Install STDN Agentic

```
# Clone repository
git clone https://github.com/yourusername/dpi_stdn_agentic.git
cd dpi_stdn_agentic

# Create virtual environment and install dependencies
uv venv
uv pip install -e .

# Install Ollama (if not already installed)
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Pull the Qwen 2.5 model
ollama pull qwen2.5:7b
```

---

## Configuration

### Configuration File (`config.json`)

```
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:7b",
  "output_dir": "./output",
  "output_csv_filename": "stdns_output",
  
  "materials_hs_codes_listing": "./data/hs_codes_and_usgs_names.csv",
  "materials_column_name": "Elements_Compounds",
  
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "top_n_countries": 5,
  
  "years_to_query": ,
  "write_nulls_to_output": true,
  
  "topp": 0.000001,
  "materials_use_topp": true,
  "materials_iteration_count": 10,
  "materials_count_threshold": 5
}
```

### Environment Variables (`.env`)

```
# Disable material validation tools (Ollama compatibility)
STDN_DISABLE_MATERIAL_TOOLS=1

# Ollama configuration
OLLAMA_MODEL=qwen2.5:7b
STDN_MODEL=ollama:qwen2.5:7b

# Optional: OpenAI fallback
# OPENAI_API_KEY=your-key-here
```

### Technology List (`data/tech_list.csv`)

```
tech
Smartphone
Electric Vehicle Battery
Quantum Computer
Night Vision Goggles
MRI Machine
Solar Panel
```

---

## Database Setup

### USGS World Mineral Commodity Database

The system uses a DuckDB database with USGS production data. **Important**: Column names are UPPERCASE except `value_type`.

#### Database Schema

```
world_mineral_commodity_report
├── COMMODITY (VARCHAR)   - Material name (e.g., "LITHIUM")
├── COUNTRY (VARCHAR)     - Producing country (e.g., "CHINA")
├── MEAS_YR (INTEGER)     - Measurement year (e.g., 2024)
├── SRC_YR (INTEGER)      - Source report year (e.g., 2023)
├── MEAS_TYPE (VARCHAR)   - Type (e.g., "PRODUCTION", "RESERVES")
├── VALUE (VARCHAR)       - Production amount (stored as text)
├── MEAS_UNIT (VARCHAR)   - Unit (e.g., "metric tons")
└── value_type (VARCHAR)  - Value type (e.g., "Number")
```

#### Verify Database

```
uv run python -c "
import duckdb
conn = duckdb.connect('./data/world_mineral_commodity_reports_2022-2025_v8.db')
print(conn.execute('SELECT COUNT(*) FROM world_mineral_commodity_report').fetchone())
print(conn.execute('DESCRIBE world_mineral_commodity_report').fetchall())
"
```

---

## Usage

### Basic Usage

```
# Run with default config
uv run stdn -i config.json

# Or using module syntax
uv run python -m stdn_agentic.main -i config.json
```

### Advanced Options

```
# Generate country data only (no technology processing)
uv run stdn -i config.json --generate-country-data

# Use different model
STDN_MODEL="ollama:llama3.1:8b" uv run stdn -i config.json

# Debug mode with verbose logging
uv run python -m stdn_agentic.main -i config.json --debug
```

### Example Session

```
Loading configuration from: config.json

✓ Connected to USGS database: 1 tables

================================================================================
STDN Generation Started: 2025-11-18 00:16:52
================================================================================

🎤 Multi-agent debate ENABLED:
   Max rounds: 3
   Convergence threshold: 0.51

Processing: Smartphone

DEBATE: Smartphone
ROUND 1:
  Convergence: 10.8%
  Generating critiques...
ROUND 2:
  Convergence: 53.0%
  ✅ Convergence threshold reached!

✓ Extracted 23 components
  🔍 Extracting materials for 23 components...
  ✅ Extracted materials for 23 components

Querying USGS for Glass (year 2024/2023)
⚠ No USGS data found, using LLM fallback...
✓ LLM returned 5 countries

Querying USGS for Lithium (year 2024/2023)
✓ USGS returned 5 countries

✓ Output written to: ./output/stdns_output.csv
✓ Successfully processed: Smartphone
```

---

## Output Format

### CSV Output (`stdns_output.csv`)

```
technology,component,material,country,meas_unit,amount,percentage
Smartphone,display,Glass,China,metric tons,12500000,45.2
Smartphone,display,Indium,China,metric tons,350,60.1
Smartphone,battery pack,Lithium,Australia,metric tons,55000,45.8
Smartphone,battery pack,Cobalt,DRC,metric tons,125000,68.3
```

### Debate Transcripts

Saved to `debate_transcripts/results/`:

```
{
  "technology": "Smartphone",
  "timestamp": "2025-11-18T00:17:49",
  "rounds": [
    {
      "round": 1,
      "proposals": {
        "Agent_1": ["display", "battery", "processor", ...],
        "Agent_2": ["screen", "power module", "CPU", ...],
        "Agent_3": ["touchscreen", "battery pack", "chip", ...]
      },
      "critiques": {
        "Agent_1→Agent_2": "Consider separating display and touchscreen...",
        ...
      }
    }
  ],
  "final_consensus": ["display", "battery pack", "processor", ...]
}
```

---

## Troubleshooting

### Issue: `invalid message content type: <nil>` (400 Error)

**Cause**: Ollama rejecting tool-based prompts

**Solution**:
```
export STDN_DISABLE_MATERIAL_TOOLS=1
uv run stdn -i config.json
```

### Issue: `'country' column not found`

**Cause**: Database columns are uppercase

**Solution**: Columns fixed in latest version. Update `usgs_client.py` to use:
- `COUNTRY`, `COMMODITY`, `MEAS_TYPE`, `MEAS_UNIT`, `VALUE`, `MEAS_YR`, `SRC_YR`
- Exception: `value_type` (lowercase)

### Issue: `pd is not defined`

**Cause**: Missing pandas import

**Solution**: Add to `data/repository.py`:
```
import pandas as pd
```

### Issue: Materials extraction fails randomly

**Cause**: Ollama instability with complex prompts

**Solutions**:
1. **Reduce ontology sample**: Change `[:100]` to `[:50]` in `extract_materials_safe`
2. **Switch model**: `export STDN_MODEL="ollama:llama3.1:8b"`
3. **Retry logic enabled**: Already implemented with exponential backoff

### Issue: No USGS data found for common materials

**Cause**: Commodity name mismatch (e.g., "Iron" vs "IRON ORE")

**Solution**: Check exact commodity names in database:
```
uv run python -c "
import duckdb
conn = duckdb.connect('./data/world_mineral_commodity_reports_2022-2025_v8.db')
print(conn.execute('SELECT DISTINCT COMMODITY FROM world_mineral_commodity_report ORDER BY COMMODITY').fetchall())
"
```

---

## Development

### Project Structure

```
dpi_stdn_agentic/
├── src/stdn_agentic/
│   ├── agents/              # LLM agents
│   ├── orchestrator/        # Pipeline & debate
│   ├── data/                # USGS client & caching
│   ├── models.py            # Pydantic models
│   └── main.py              # CLI
├── data/
│   ├── tech_list.csv        # Input technologies
│   ├── hs_codes_and_usgs_names.csv  # Material ontology
│   └── world_mineral_commodity_reports_2022-2025_v8.db  # USGS data
├── output/                  # Generated STDNs
├── debate_transcripts/      # Agent debate logs
├── config.json              # Configuration
├── pyproject.toml           # Package metadata
└── README.md
```

### Running Tests

```
# Unit tests
uv run pytest tests/

# Database connectivity test
uv run python debug_duckdb.py

# Type checking
uv run basedpyright src/
```

### Code Style

- **Type hints**: Required for all functions
- **Pydantic models**: For all data structures
- **Logging**: Use `logger` not `print()` (except user-facing output)
- **Error handling**: Always wrap external calls in try/except
- **Docstrings**: Google style for all public functions

---

## Citation

If you use this tool in research, please cite:

```
@software{stdn_agentic2025,
  title = {STDN Agentic: Multi-Agent Shallow Technology Dependency Networks},
  author = {Your Name},
  year = {2025},
  url = {https://github.com/yourusername/dpi_stdn_agentic}
}
```

---

## License

MIT License - see LICENSE file for details.

---

## Acknowledgments

- **USGS**: World Mineral Commodity Reports data
- **Pydantic AI**: Agent framework
- **Ollama**: Local LLM serving
- **Qwen Team**: Qwen 2.5 model

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/dpi_stdn_agentic/issues
- Documentation: https://github.com/yourusername/dpi_stdn_agentic/wiki

---

**Version**: 0.1.0  
**Last Updated**: November 2025
