Based on my thorough review of the README.md file, I've identified several areas for improvement including clarity, completeness, technical accuracy, and consistency. Here's the enhanced version:

---

# STDN Agentic - Supply Technology Dependency Network Generator

A modular, multi-agent system for generating Supply Technology Dependency Networks (STDNs) using Pydantic AI agents with USGS database integration and LLM fallback.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [Component Overview](#component-overview)
  - [Agents Layer](#agents-layer)
  - [Data Layer](#data-layer)
  - [Debate System](#debate-system)
  - [Orchestrator](#orchestrator)
  - [Reporting](#reporting)
- [Pipeline Flow](#pipeline-flow)
  - [Key Decision Points](#key-decision-points)
  - [Cross-Cutting Concerns](#cross-cutting-concerns)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
  - [Environment Configuration](#environment-configuration)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Running with Multi-Agent Debate](#running-with-multi-agent-debate)
    - [Method 1: Configuration via .env File (Simplest)](#method-1-configuration-via-env-file-simplest)
    - [Method 2: Programmatic Configuration (Single Technology)](#method-2-programmatic-configuration-single-technology)
    - [Method 3: Programmatic Batch Processing (Advanced)](#method-3-programmatic-batch-processing-advanced)
  - [Advanced Usage Examples](#advanced-usage-examples)
  - [How Debate Works for Multiple Technologies](#how-debate-works-for-multiple-technologies)
- [Multi-Agent Debate System](#multi-agent-debate-system)
  - [Debate Parameters](#debate-parameters)
  - [Quick Test](#quick-test)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Design Patterns](#design-patterns)
  - [Adding New Features](#adding-new-features)
  - [Running Tests](#running-tests)
- [Data Sources](#data-sources)
  - [USGS Database](#usgs-database)
  - [LLM Fallback](#llm-fallback)
- [API Reference](#api-reference)
  - [Core Classes](#core-classes)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

***

## Overview

STDN Agentic analyzes technologies to extract their component dependencies and material supply chains. It uses a multi-agent debate system to achieve consensus on components and materials, then enriches the data with country-level production information from USGS databases.

### Key Features

- **Multi-Agent Consensus**: Debate-based consensus building with configurable rounds
- **USGS Integration**: Direct access to USGS mineral commodity production data (2022-2025)
- **Intelligent Fallback**: LLM-based estimation when database data unavailable
- **Smart Caching**: Minimize redundant queries with TTL-based caching (24-hour default)
- **Modular Architecture**: Clean separation of concerns for maintainability
- **Full Audit Trail**: Detailed debate transcripts and checkpoint support
- **Comprehensive Testing**: Unit and integration test coverage

### Use Cases

- Supply chain vulnerability analysis
- Critical materials assessment
- Geopolitical risk evaluation
- Technology dependency mapping
- Policy research and analysis

***

## Architecture

The project follows a clean, modular architecture organized into specialized packages:

```
src/stdn_agentic/
├── agents/           # Multi-agent extraction system
├── data/             # Data access and persistence layer
├── debate/           # Multi-agent consensus system
├── orchestrator/     # Pipeline coordination
├── reporting/        # Output generation
├── core/             # Base classes and schemas
├── models.py         # Pydantic data models
├── dependencies.py   # Dependency injection container
└── utils.py          # Shared utility functions
```

### Component Overview

#### Agents Layer (`agents/`)

Specialized Pydantic AI agents for data extraction:

- **ComponentAgent** (`component_agent.py`): Extracts primary technology components (displays, batteries, processors)
- **MaterialsAgent** (`materials_agent.py`): Identifies raw materials with ontology validation
- **CountryDataAgent** (`country_agent.py`): Retrieves country production data with LLM fallback
- **AgentFactory** (`factory.py`): Creates and manages agent instances with caching

#### Data Layer (`data/`)

Robust data access with fallback strategies:

- **USGSClient** (`usgs_client.py`): Queries USGS mineral commodity DuckDB database
- **CountryDataRepository** (`repository.py`): Coordinates USGS primary + LLM fallback
- **MaterialCache** (`cache.py`): TTL-based caching to reduce redundant queries
- **DataLoader** (`loaders.py`): CSV/JSON loading and saving utilities

#### Debate System (`debate/`)

Multi-agent consensus building:

- Configurable debate rounds (1-10 rounds)
- Jaccard similarity convergence scoring
- Agent critique generation
- Majority voting for consensus
- Full debate history tracking

#### Orchestrator (`orchestrator/`)

Pipeline coordination and management:

- **Pipeline** (`pipeline.py`): End-to-end technology processing workflow
- **Checkpoint** (`checkpoint.py`): Checkpoint/resume for long-running batch jobs
- **StateManager** (`state_manager.py`): Pipeline state management with transitions
- **ErrorHandler** (`error_handler.py`): Error handling with retry logic and exponential backoff

#### Reporting (`reporting/`)

Output generation and audit trails:

- **DebateReporter** (`debate_reporter.py`): Human-readable debate transcripts and machine-readable JSON exports
- Policy-ready formatted briefs
- Timestamped audit logs

***

## Pipeline Flow

The STDN generation pipeline processes technologies through multiple stages, with agents interacting at specific points:

```
┌─────────────────────────────────────────────┐
│  STAGE 1: COMPONENT EXTRACTION              │
├─────────────────────────────────────────────┤
│  Input: Tech List (CSV)                     │
│  └─► ComponentAgent (x3)                    │
│       └─► Multi-Agent Debate                │
│            - Agent 1: display, battery...   │
│            - Agent 2: screen, battery...    │
│            - Agent 3: display, battery...   │
│       └─► MultiAgentDebater                 │
│            - Run consensus rounds           │
│            - Convergence scoring            │
│            - Agent critiques                │
│  Output: Consensus Components               │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  STAGE 2: MATERIALS EXTRACTION              │
├─────────────────────────────────────────────┤
│  For each component:                        │
│  └─► MaterialsAgent                         │
│       - Extract materials                   │
│       - Validate against ontology           │
│       - Filter invalid materials            │
│       - Retry if no valid materials found   │
│  Output: Component → Materials mapping      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  STAGE 3: COUNTRY DATA ENRICHMENT           │
├─────────────────────────────────────────────┤
│  For each material:                         │
│  └─► CountryDataRepository                  │
│       1. Check cache                        │
│       2. Query USGS database                │
│       3. LLM fallback if needed             │
│  Output: Country production data            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  STAGE 4: OUTPUT GENERATION                 │
├─────────────────────────────────────────────┤
│  └─► DebateReporter (if enabled)            │
│       - Text transcripts                    │
│       - JSON exports                        │
│  └─► CSV Output                             │
│       Technology, Component, Material,      │
│       Country, Amount, Unit, Percentage     │
│  └─► CheckpointManager (if enabled)         │
└─────────────────────────────────────────────┘
```

### Key Decision Points

1. **Component Extraction**: Single agent vs. multi-agent debate (configurable)
2. **Material Validation**: Strict ontology checking with retry on failure
3. **Country Data**: USGS primary → Cache check → LLM fallback cascade
4. **Error Handling**: Automatic retry with exponential backoff

### Cross-Cutting Concerns

- **ErrorHandler**: Retry logic & error recovery at each stage
- **StateManager**: Track pipeline progress & transitions
- **MaterialCache**: Reduce redundant queries (24hr TTL)

***

## Installation

### Prerequisites

- **Python 3.10 - 3.12** (Python 3.12 recommended)
- **uv package manager** ([Installation guide](https://github.com/astral-sh/uv))
- **Ollama** for local LLM OR **OpenAI API key**
- **USGS Database**: DuckDB file with mineral commodity data (`world_mineral_commodity_reports_2022-2025_v8.db`)

### Setup

1. **Clone the repository**:

```bash
git clone <repository-url>
cd dpi_stdn_agentic
```

2. **Install dependencies with uv**:

```bash
uv sync
```

3. **Place the USGS database file**:

```bash
# Ensure the database is in the data directory
cp /path/to/world_mineral_commodity_reports_2022-2025_v8.db ./data/
```

4. **Set up Ollama** (if using local LLM):

```bash
# Install Ollama: https://ollama.ai
# Pull a model
ollama pull qwen2.5:7b
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
# LLM Configuration
# Option 1: Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:7b

# Option 2: OpenAI
# OPENAI_API_KEY=sk-your-key-here
# STDN_MODEL=openai:gpt-4

# Database
DATABASE_PATH=./data/world_mineral_commodity_reports_2022-2025_v8.db

# Output
OUTPUT_DIR=./output
OUTPUT_CSV_FILENAME=stdn_results

# Caching
CACHE_DIR=./.cache
CACHE_TTL_HOURS=24

# Multi-Agent Debate Settings
ENABLE_DEBATE=true
MAX_DEBATE_ROUNDS=3
CONVERGENCE_THRESHOLD=0.8
SAVE_TRANSCRIPTS=true
```

***

## Usage

### Basic Usage

**Step 1**: Create a technology list CSV (`tech_list.csv`):

```csv
tech,role,domain
smartphone,supply chain analyst,consumer electronics
electric vehicle,policy analyst,automotive
solar panel,researcher,renewable energy
wind turbine,analyst,renewable energy
```

**Step 2**: Create a configuration JSON (`config.json`):

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:7b",
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "output_dir": "./output",
  "output_csv_filename": "stdn_results",
  "write_nulls_to_output": false,
  "years_to_query": [2024, 2025],
  "top_n_countries": 5
}
```

**Step 3**: Run the pipeline:

```bash
# Process all technologies in the CSV (uses .env settings)
uv run stdn -i config.json

# Or run programmatically
uv run python -m stdn_agentic.main --config config.json
```

**Output**: Results saved to `./output/stdn_results.csv`

***

### Running with Multi-Agent Debate

Multi-agent debate automatically runs for **ALL** technologies in your CSV file. The following methods differ only in how you configure the debate parameters.

#### Method 1: Configuration via .env File (Simplest)

Use this when you want the simplest setup and are processing all technologies from a CSV.

1. **Set debate parameters in `.env`**:

```bash
ENABLE_DEBATE=true
MAX_DEBATE_ROUNDS=3
CONVERGENCE_THRESHOLD=0.8
SAVE_TRANSCRIPTS=true
```

2. **Run with standard command**:

```bash
uv run stdn -i config.json
```

**When to use**: Simplest method, processes all technologies with debate enabled.

---

#### Method 2: Programmatic Configuration (Single Technology)

Use this when you want to process just one specific technology with full control.

```python
import asyncio
from stdn_agentic import STDNOrchestrator
from stdn_agentic.models import ConfigModel
from pydantic_ai import RunUsage

async def main():
    config = ConfigModel(
        import_tech_list="./data/tech_list.csv",
        model="ollama:qwen2.5:7b",
        usgs_database="./data/world_mineral_commodity_reports_2022-2025_v8.db",
        output_dir="./output",
        output_csv_filename="stdn_debate_results"
    )

    orchestrator = STDNOrchestrator(
        config,
        enable_debate=True,
        max_debate_rounds=3,
        convergence_threshold=0.8,
        save_transcripts=True
    )

    # Process ONLY ONE technology
    usage = RunUsage()
    result = await orchestrator.process_technology(
        tech="smartphone",
        role="supply chain analyst",
        domain="consumer electronics",
        usage=usage
    )

    print(f"Components: {result['components']}")
    print(f"Debate transcript: ./debate_transcripts/results/")

if __name__ == "__main__":
    asyncio.run(main())
```

**Run it**:

```bash
uv run python run_single_tech.py
```

**When to use**: Testing or processing one specific technology.

***

#### Method 3: Programmatic Batch Processing (Advanced)

Use this when you want custom logic for processing all technologies (e.g., error handling, progress tracking, custom filtering).

```python
import asyncio
import csv
from stdn_agentic import STDNOrchestrator
from stdn_agentic.models import ConfigModel
from pydantic_ai import RunUsage

async def process_batch():
    config = ConfigModel(
        import_tech_list="./data/tech_list.csv",
        model="ollama:qwen2.5:7b",
        usgs_database="./data/world_mineral_commodity_reports_2022-2025_v8.db",
        output_dir="./output",
        output_csv_filename="batch_debate_results"
    )

    orchestrator = STDNOrchestrator(
        config,
        enable_debate=True,
        max_debate_rounds=3,
        convergence_threshold=0.8,
        enable_checkpoints=True,  # Add checkpoint support
        save_transcripts=True
    )

    # Read all technologies from CSV
    with open(config.import_tech_list, 'r') as f:
        technologies = list(csv.DictReader(f))

    print(f"Processing {len(technologies)} technologies with debate...")

    results = []
    usage = RunUsage()
    for i, tech_row in enumerate(technologies, 1):
        print(f"[{i}/{len(technologies)}] {tech_row['tech']}")
        try:
            result = await orchestrator.process_technology(
                tech=tech_row['tech'],
                role=tech_row.get('role', 'analyst'),
                domain=tech_row.get('domain', 'technology'),
                usage=usage
            )
            results.append(result)
            # Write incrementally
            orchestrator.write_csv_output(result, start_new_file=(i == 1))
        except Exception as e:
            print(f"Error: {e}")
            continue  # Skip failed tech and continue

    print(f"Processed {len(results)}/{len(technologies)} technologies")
    print(f"Output: {orchestrator.output_file}")

asyncio.run(process_batch())
```

**Run it**:

```bash
uv run python run_batch_custom.py
```

**When to use**: Custom error handling, filtering, or progress tracking.

***

#### When to Use Each Method

| Method | Use When... | Processes |
|--------|------------|-----------|
| **Method 1** (.env) | You want the simplest setup | All technologies in CSV |
| **Method 2** (Single tech) | Testing or processing one specific technology | One technology only |
| **Method 3** (Custom batch) | You need custom error handling, filtering, or progress tracking | All technologies in CSV with custom logic |

***

### Advanced Usage Examples

**Use Repository Pattern with Fallback**:

```python
from stdn_agentic.data import CountryDataRepository
from stdn_agentic.dependencies import initialize_dependencies

deps = initialize_dependencies(config)
repo = CountryDataRepository(
    database_path="./data/world_mineral_commodity_reports_2022-2025_v8.db",
    deps=deps,
    top_n=5,
    use_llm_fallback=True  # Enable LLM fallback
)

# Get country data (tries USGS first, falls back to LLM)
countries = await repo.get_country_data("Lithium", 2025, 2024)

for country in countries:
    print(f"{country['country']}: {country['percentage']:.1f}%")

# Check cache stats
stats = repo.get_cache_stats()
print(f"Cached materials: {stats['cached_materials']}")
```

***

### How Debate Works for Multiple Technologies

When debate is enabled via any method, the system runs **independent debate sessions** for each technology:

```
Technology 1: smartphone
  ├─► Agent 1 proposes components
  ├─► Agent 2 proposes components
  ├─► Agent 3 proposes components
  ├─► Debate Round 1, 2, 3...
  ├─► Consensus
  └─► Save transcript

Technology 2: electric vehicle
  ├─► Agent 1 proposes components
  ├─► Agent 2 proposes components
  ├─► Agent 3 proposes components
  ├─► Debate Round 1, 2, 3...
  ├─► Consensus
  └─► Save transcript

Technology 3: solar panel
  ├─► Agent 1 proposes components
  ├─► Agent 2 proposes components
  ├─► Agent 3 proposes components
  ├─► Debate Round 1, 2, 3...
  ├─► Consensus
  └─► Save transcript
```

**Each technology gets**:
- Independent 3-agent debate
- Separate debate transcript
- Consensus-based components

***

## Multi-Agent Debate System

### Debate Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_debate` | bool | False | Enable multi-agent consensus |
| `max_debate_rounds` | int | 3 | Maximum debate rounds (1-10) |
| `convergence_threshold` | float | 0.8 | Stop when convergence ≥ threshold (0.0-1.0) |
| `save_transcripts` | bool | True | Save detailed debate logs |

**Convergence Threshold Guide**:

| Threshold | Meaning | Notes |
|-----------|---------|-------|
| 0.6 | Low consensus (60% agreement) | Fast but lower quality |
| 0.8 | Good consensus (80% agreement) | **Recommended** |
| 0.9 | High consensus (90% agreement) | Slower but higher quality |
| 1.0 | Perfect consensus | Rarely achieved |

**Rounds Guide**:

| Rounds | Notes |
|--------|-------|
| 2 rounds | Fast, moderate quality |
| 3 rounds | Balanced speed/quality **(Recommended)** |
| 5+ rounds | High quality, slower |

***

### Quick Test

Test debate functionality:

```bash
cat > test_debate.py << 'EOF'
import asyncio
from stdn_agentic import STDNOrchestrator
from stdn_agentic.models import ConfigModel
from pydantic_ai import RunUsage

async def test():
    config = ConfigModel(
        import_tech_list="./data/tech_list.csv",
        model="ollama:qwen2.5:7b",
        usgs_database="./data/world_mineral_commodity_reports_2022-2025_v8.db",
        output_dir="./output",
        output_csv_filename="test"
    )

    orch = STDNOrchestrator(config, enable_debate=True, max_debate_rounds=2)
    result = await orch.process_technology("smartphone", "analyst", "tech", RunUsage())
    print(f"Components: {result['components']}")

asyncio.run(test())
EOF

uv run python test_debate.py
```

***

## Development

### Project Structure

This project uses modern Python architecture patterns:

- **Separation of Concerns**: Each package has a single responsibility
- **Dependency Injection**: Dependencies passed explicitly via `STDNDependencies`
- **Repository Pattern**: Data layer abstraction (`CountryDataRepository`)
- **Factory Pattern**: Agent creation via `AgentFactory`
- **Strategy Pattern**: Multiple debate strategies (future enhancement)

### Adding New Features

**Add a new agent**:

1. Create `src/stdn_agentic/agents/new_agent.py`
2. Define Pydantic models for input/output
3. Create agent with `Agent(model, output_type, deps_type)`
4. Add to `agents/__init__.py`
5. Update `AgentFactory` if needed

**Add a new data source**:

1. Create client in `src/stdn_agentic/data/new_client.py`
2. Implement repository pattern if needed
3. Add caching support
4. Write unit tests
5. Update `data/__init__.py`

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test files
uv run pytest tests/test_debate.py -v -s

# Run with coverage
uv run pytest tests/ --cov=src/stdn_agentic --cov-report=html

# Run integration tests only
uv run pytest tests/test_phase2c_integration.py -v
```

***

## Data Sources

### USGS Database

The system uses a DuckDB database containing USGS Mineral Commodity Summaries (2022-2025):

- **File**: `world_mineral_commodity_reports_2022-2025_v8.db`
- **Tables**: Structured production data by material, country, and year
- **Query Interface**: `USGSClient` provides async query methods
- **Coverage**: 80+ minerals/materials with country-level production data

### LLM Fallback

When USGS data is unavailable, the system falls back to LLM-based estimation:

- Uses Pydantic AI structured outputs
- Validates response format with Pydantic models
- Includes confidence scores
- Caches results to avoid redundant queries

---

## API Reference

### Core Classes

#### `STDNOrchestrator`

Main pipeline orchestrator.

```python
orchestrator = STDNOrchestrator(
    config: ConfigModel,
    enable_checkpoints: bool = False,
    enable_debate: bool = False,
    max_debate_rounds: int = 3,
    convergence_threshold: float = 0.8,
    save_transcripts: bool = True
)

# Process single technology
result = await orchestrator.process_technology(
    tech: str,
    role: str,
    domain: str,
    usage: RunUsage
) -> Dict[str, Any]

# Run full pipeline
results = await orchestrator.run_pipeline(
    technologies: List[str],
    role: str = "supply chain analyst",
    domain: str = "technology"
) -> Dict[str, Any]
```

#### `CountryDataRepository`

Data repository with USGS + LLM fallback.

```python
repo = CountryDataRepository(
    database_path: str,
    deps: STDNDependencies,
    top_n: int = 5,
    use_llm_fallback: bool = True
)

# Get country production data
countries = await repo.get_country_data(
    material: str,
    src_year: int,
    meas_year: int,
    usage: str = ""
) -> List[Dict[str, Any]]

# Check cache stats
stats = repo.get_cache_stats()
```

#### `MultiAgentDebater`

Multi-agent consensus system.

```python
debater = MultiAgentDebater(
    max_rounds: int = 3,
    convergence_threshold: float = 0.8
)

# Run debate
result = await debater.run_debate(
    technology: str,
    agent_proposals: Dict[str, List[Dict]]
) -> Dict[str, Any]
```

***

## Configuration Reference

### ConfigModel Fields

**Required**:

- `import_tech_list` (str): Path to CSV file containing technology list (column: `tech`)
- `model` (str): Model identifier (e.g., `ollama:qwen2.5:7b`, `openai:gpt-4`)
- `output_dir` (str): Directory path for output files
- `output_csv_filename` (str): Output CSV filename (without `.csv` extension)

**Optional**:

- `materials_hs_codes_listing` (str): Path to CSV mapping HS codes to USGS material names (default: `./data/hs_codes_and_usgs_names.csv`)
- `materials_column_name` (str): Column name in HS codes file containing material names (default: `Elements/Compounds`)
- `materials_top_countries_repository` (str): Path to JSON with top producing countries per material (default: `./data/material_top_countries_granite3.1-dense.8b.json`)
- `usgs_database` (str): Path to USGS mineral commodities SQLite database (default: `./data/world_mineral_commodity_reports_2022-2025_v8.db`)
- `top_n_countries` (int): Number of top producing countries to include per material (default: 5, range: 1-20)
- `generate_country_data` (bool): Whether to generate country production data (default: False)
- `country_data_mode` (Literal["full", "incremental", "update"]): Mode for country data generation (default: "full")
- `materials_to_update` (List[str]): Specific materials to update for incremental/update modes (default: None)
- `years_to_query` (List[int]): Years to query for historical production data (default: )
- `write_nulls_to_output` (bool): Whether to write rows with null country data to output CSV (default: True)
- `top_p` (float): Top-p (nucleus sampling) parameter for generation (default: 0.000001, range: 0.0-1.0)
- `materials_use_top_p` (bool): Whether to use top-p sampling for materials extraction (default: True)
- `materials_iteration_count` (int): Number of iterations for materials extraction consensus (default: 10, range: 1-100)
- `materials_count_threshold` (int): Threshold for material count consensus across iterations (default: 5, range: 1-50)

***

## Troubleshooting

### Common Issues

**1. Database not found**:

```bash
Error: Database not found in ./data
```

**Solution**: Ensure the USGS database is in the correct location:

```bash
cp /path/to/world_mineral_commodity_reports_2022-2025_v8.db ./data/
```

***

**2. Ollama connection error**:

```bash
Error: Could not connect to Ollama
```

**Solution**:
- Check if Ollama is running: `ollama serve`
- Verify model is pulled: `ollama pull qwen2.5:7b`
- Check `.env` has correct `OLLAMA_BASE_URL`

***

**3. No materials extracted**:

```bash
Warning: No materials extracted for technology X
```

**Solution**:
- Check material ontology file exists: `./data/hs_codes_and_usgs_names.csv`
- Verify `materials_column_name` in config matches CSV column
- Try increasing `materials_iteration_count` in config

***

**4. Debate not converging**:

```bash
Warning: Debate did not converge after N rounds
```

**Solution**:
- Lower `convergence_threshold` (e.g., from 0.8 to 0.6)
- Increase `max_debate_rounds` (e.g., from 3 to 5)
- Check that agents are producing varied proposals

***

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Development workflow**:

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests before committing
uv run pytest tests/ -v

# Format code
uv run black src/ tests/
uv run ruff check src/ tests/ --fix

# Type checking
uv run basedpyright src/
```

***

## License

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

***

**For questions or support**: Open an issue on GitHub or contact the maintainers.

[1](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/29503869/e19fe296-4a82-497a-990a-a06967c26612/concatenated_files.txt)
