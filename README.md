Here's a comprehensive README with an ASCII process diagram showing the full pipeline flow:

# STDN Agentic - Supply Technology Dependency Network Generator

> A modular, multi-agent system for generating Supply Technology Dependency Networks (STDNs) using Pydantic AI agents with USGS database integration and LLM fallback.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.ps://img.shieldsmg.shields.io/badge/tests-passing-brightgreen.
## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Pipeline Flow](#pipeline-flow)
- [Installation](#installation)
- [Usage](#usage)
- [Development](#development)
- [Data Sources](#data-sources)
- [API Reference](#api-reference)
- [Contributing](#contributing)
- [License](#license)

## Overview

STDN Agentic analyzes technologies to extract their component dependencies and material supply chains. It uses a multi-agent debate system to achieve consensus on components and materials, then enriches the data with country-level production information from USGS databases.

**Key Features:**
- 🤖 **Multi-Agent Consensus**: Debate-based consensus building with configurable rounds
- 📊 **USGS Integration**: Direct access to mineral commodity production data
- 🔄 **Intelligent Fallback**: LLM-based estimation when database data unavailable
- 💾 **Smart Caching**: Minimize redundant queries with TTL-based caching
- 🏗️ **Modular Architecture**: Clean separation of concerns for maintainability
- 📝 **Full Audit Trail**: Detailed debate transcripts and checkpoint support
- ✅ **Comprehensive Testing**: Unit and integration test coverage

**Use Cases:**
- Supply chain vulnerability analysis
- Critical materials assessment
- Geopolitical risk evaluation
- Technology dependency mapping
- Policy research and analysis

## Architecture

The project follows a clean, modular architecture organized into specialized packages:

```
src/stdn_agentic/
├── agents/           # Multi-agent extraction system
│   ├── component_agent.py    # Technology component extraction
│   ├── materials_agent.py    # Material identification & validation
│   ├── country_agent.py      # Country production data schemas
│   └── factory.py            # Agent creation & lifecycle management
├── data/             # Data access and persistence layer
│   ├── usgs_client.py        # USGS DuckDB database client
│   ├── repository.py         # Data repository with fallback strategy
│   ├── cache.py              # TTL-based material caching
│   └── loaders.py            # CSV/JSON data utilities
├── debate/           # Multi-agent consensus system
│   └── debater.py            # Debate orchestration & convergence
├── orchestrator/     # Pipeline coordination
│   ├── pipeline.py           # Main STDN orchestrator
│   ├── checkpoint.py         # Save/resume functionality
│   ├── state_manager.py      # Pipeline state tracking
│   └── error_handler.py      # Error recovery & retry logic
├── reporting/        # Output generation
│   └── debate_reporter.py    # Debate transcripts & reports
├── models.py         # Pydantic data models & schemas
├── dependencies.py   # Dependency injection container
└── utils.py          # Shared utility functions
```

### Component Overview

#### **Agents Layer** (`agents/`)
Specialized Pydantic AI agents for data extraction:
- **ComponentAgent**: Extracts primary technology components (displays, batteries, processors)
- **MaterialsAgent**: Identifies raw materials with ontology validation
- **CountryDataAgent**: Retrieves country production data (LLM fallback)
- **AgentFactory**: Creates and manages agent instances with caching

#### **Data Layer** (`data/`)
Robust data access with fallback strategies:
- **USGSClient**: Queries USGS mineral commodity DuckDB database
- **CountryDataRepository**: Coordinates USGS primary + LLM fallback
- **MaterialCache**: TTL-based caching to reduce redundant queries
- **DataLoader**: CSV/JSON loading and saving utilities

#### **Debate System** (`debate/`)
Multi-agent consensus building:
- Configurable debate rounds (1-10 rounds)
- Jaccard similarity convergence scoring
- Agent critique generation
- Majority voting for consensus
- Full debate history tracking

#### **Orchestrator** (`orchestrator/`)
Pipeline coordination and management:
- End-to-end technology processing workflow
- Checkpoint/resume for long-running batch jobs
- Pipeline state management with transitions
- Error handling with retry logic
- Progress tracking and monitoring

#### **Reporting** (`reporting/`)
Output generation and audit trails:
- Human-readable debate transcripts
- Machine-readable JSON exports
- Policy-ready formatted briefs
- Timestamped audit logs

## Pipeline Flow

The STDN generation pipeline processes technologies through multiple stages, with agents interacting at specific points:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         STDN GENERATION PIPELINE                        │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│  Input Tech  │  "smartphone", "electric vehicle", "solar panel"
│  List (CSV)  │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: COMPONENT EXTRACTION                                          │
│  ┌────────────────────────┐                                             │
│  │  ComponentAgent x3     │  Extract tech components independently      │
│  │  (Multi-Agent Debate)  │  Agent 1: ["display", "battery", "camera"]  │
│  └───────────┬────────────┘  Agent 2: ["screen", "battery", "cpu"]     │
│              │               Agent 3: ["display", "battery", "chip"]    │
│              ▼                                                           │
│  ┌────────────────────────┐                                             │
│  │  MultiAgentDebater     │  Run consensus rounds with critiques        │
│  │  (Convergence Check)   │  • Jaccard similarity scoring              │
│  └───────────┬────────────┘  • Agent critiques & refinement            │
│              │               • Majority voting                          │
│              │                                                           │
│              ▼                                                           │
│  ┌────────────────────────┐                                             │
│  │  Consensus Components  │  Final agreed list: ["display", "battery", │
│  │                        │  "processor", "camera"]                     │
│  └───────────┬────────────┘                                             │
└──────────────┼─────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: MATERIALS EXTRACTION                                          │
│  ┌────────────────────────┐                                             │
│  │  MaterialsAgent        │  For each component:                        │
│  │  (with Validation)     │  • Display → glass, indium, tin            │
│  └───────────┬────────────┘  • Battery → lithium, cobalt, nickel       │
│              │               • Processor → silicon, copper, gold        │
│              ▼                                                           │
│  ┌────────────────────────┐                                             │
│  │  validate_materials()  │  Check against material ontology            │
│  │  (Tool Function)       │  • Filter invalid materials                │
│  └───────────┬────────────┘  • Retry if no valid materials found       │
│              │                                                           │
│              ▼                                                           │
│  ┌────────────────────────┐                                             │
│  │  Validated Materials   │  {component: [materials], ...}              │
│  │                        │                                             │
│  └───────────┬────────────┘                                             │
└──────────────┼─────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: COUNTRY DATA ENRICHMENT                                       │
│  ┌────────────────────────┐                                             │
│  │  CountryDataRepository │  For each material:                         │
│  │  (USGS + LLM Fallback) │                                             │
│  └───────────┬────────────┘                                             │
│              │                                                           │
│       ┌──────┴──────┐                                                   │
│       │             │                                                   │
│       ▼             ▼                                                   │
│  ┌─────────┐   ┌─────────────┐                                        │
│  │  USGS   │   │  Material   │  Check cache first                     │
│  │  Client │   │  Cache      │                                        │
│  └────┬────┘   └──────┬──────┘                                        │
│       │               │                                                │
│       │  Cache Miss   │                                                │
│       ▼               │                                                │
│  ┌──────────────────┐ │                                                │
│  │  Query USGS DB   │ │  "Lithium" → Chile, Australia, China         │
│  │  (Primary Source)│ │                                                │
│  └────┬─────────────┘ │                                                │
│       │               │                                                │
│  Data │               │                                                │
│  Found│               │                                                │
│       ▼               │                                                │
│  ┌────────────┐      │                                                │
│  │  Success   │──────┴──► Cache & Return                             │
│  └────────────┘                                                        │
│       │ No Data                                                        │
│       ▼                                                                │
│  ┌────────────────────┐                                               │
│  │  CountryDataAgent  │  LLM Fallback: Generate estimates             │
│  │  (LLM Fallback)    │  with confidence scores                       │
│  └───────────┬────────┘                                               │
│              │                                                         │
│              ▼                                                         │
│  ┌────────────────────┐                                               │
│  │  Country List with │  [{country, amount, unit, percentage}, ...]   │
│  │  Production Data   │                                               │
│  └───────────┬────────┘                                               │
└──────────────┼─────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 4: OUTPUT GENERATION                                             │
│  ┌────────────────────────┐                                             │
│  │  DebateReporter        │  Generate transcripts:                      │
│  │  (if debate enabled)   │  • Text format for review                  │
│  └───────────┬────────────┘  • JSON format for analysis                │
│              │                                                           │
│              ▼                                                           │
│  ┌────────────────────────┐                                             │
│  │  CSV Output            │  Technology → Components → Materials →      │
│  │  (stdn_results.csv)    │  Countries with production data            │
│  └───────────┬────────────┘                                             │
│              │                                                           │
│              ▼                                                           │
│  ┌────────────────────────┐                                             │
│  │  CheckpointManager     │  Save state for resume (if enabled)         │
│  │  (if enabled)          │                                             │
│  └────────────────────────┘                                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  CROSS-CUTTING CONCERNS                                                 │
│  • ErrorHandler: Retry logic & error recovery at each stage            │
│  • StateManager: Track pipeline progress & transitions                 │
│  • MaterialCache: Reduce redundant queries (24hr TTL)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Decision Points

1. **Component Extraction**: Single agent vs. multi-agent debate (configurable)
2. **Material Validation**: Strict ontology checking with retry on failure
3. **Country Data**: USGS primary → Cache check → LLM fallback cascade
4. **Error Handling**: Automatic retry with exponential backoff

## Installation

### Prerequisites

- **Python 3.10+** (Python 3.12 recommended)
- **uv package manager**: [Installation guide](https://github.com/astral-sh/uv)
- **Ollama** (for local LLM) OR **OpenAI API key**
- **USGS Database**: DuckDB file with mineral commodity data

### Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/dpi_stdn_agentic.git
cd dpi_stdn_agentic

# Install dependencies with uv
uv sync

# Install development dependencies
uv sync --group dev

# Configure environment
cp .env.example .env
# Edit .env with your configuration
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
# LLM Configuration (Ollama)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2:7b

# Or use OpenAI
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

# Debate Settings (optional)
ENABLE_DEBATE=true
MAX_DEBATE_ROUNDS=3
CONVERGENCE_THRESHOLD=0.8
```

### Verify Installation

```bash
# Test imports
uv run python -c "from stdn_agentic import STDNOrchestrator; print('✓ Installation successful')"

# Run tests
uv run pytest tests/ -v

# Type checking
uv run basedpyright src/
```

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
  "model": "ollama:qwen2:7b",
  "database_path": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "output_dir": "./output",
  "output_csv_filename": "stdn_results",
  "write_nulls_to_output": false
}
```

**Step 3**: Run the pipeline:

```bash
# Process all technologies in the list
uv run stdn -i config.json

# Or run programmatically
uv run python -m stdn_agentic.main --config config.json
```

### Advanced Usage

#### Enable Multi-Agent Debate

```python
from stdn_agentic import STDNOrchestrator
from stdn_agentic.models import ConfigModel
from pydantic_ai import RunUsage

# Load configuration
config = ConfigModel(
    import_tech_list="./data/tech_list.csv",
    model="ollama:qwen2:7b",
    database_path="./data/usgs.db",
    output_dir="./output",
    output_csv_filename="results"
)

# Create orchestrator with debate enabled
orchestrator = STDNOrchestrator(
    config,
    enable_debate=True,           # Enable multi-agent consensus
    max_debate_rounds=3,          # Run up to 3 debate rounds
    convergence_threshold=0.8,     # Stop at 80% convergence
    save_transcripts=True          # Save debate logs
)

# Process a single technology
usage = RunUsage()
result = await orchestrator.process_technology(
    tech="smartphone",
    role="supply chain analyst",
    domain="consumer electronics",
    usage=usage
)

print(f"Components: {result['components']}")
print(f"Materials: {result['materials']}")
```

#### Enable Checkpointing for Long Runs

```python
orchestrator = STDNOrchestrator(
    config,
    enable_checkpoints=True,  # Save state every N technologies
    enable_debate=True
)

# Pipeline will automatically save/resume from checkpoints
# Checkpoint files saved to ./checkpoints/
```

#### Use Agent Factory Directly

```python
from stdn_agentic.agents import AgentFactory
from stdn_agentic.dependencies import initialize_dependencies

# Initialize dependencies
deps = initialize_dependencies(config)

# Create agent factory
factory = AgentFactory(config={"enable_caching": True})

# Get agents
component_agent = factory.create_component_agent()
materials_agent = factory.create_materials_agent()
country_agent = factory.create_country_agent()

# Run component extraction
result = await component_agent.run(
    "Extract components from a smartphone",
    deps=deps
)
print(result.output.component_list)
```

#### Query USGS Database Directly

```python
from stdn_agentic.data import USGSClient

# Connect to database
with USGSClient("./data/usgs.db", top_n=5) as client:
    # Query top lithium producers
    countries = client.query_top_countries("Lithium", 2025, 2024)
    print(countries['country'].tolist())

    # Get world production totals
    totals = client.query_world_totals("Lithium", 2025, 2024)
    print(f"World production: {totals.get('PRODUCTION', 0)}")

    # Get country-specific details
    details = client.query_country_details("Lithium", "Chile", 2025, 2024)
    for detail in details:
        print(f"{detail['meas_type']}: {detail['value']} {detail['meas_unit']}")
```

#### Use Repository Pattern with Fallback

```python
from stdn_agentic.data import CountryDataRepository
from stdn_agentic.dependencies import initialize_dependencies

deps = initialize_dependencies(config)

repo = CountryDataRepository(
    database_path="./data/usgs.db",
    deps=deps,
    top_n=5,
    use_llm_fallback=True  # Enable LLM fallback
)

# Get country data (tries USGS first, LLM fallback if no data)
countries = await repo.get_country_data("Lithium", 2025, 2024)

for country in countries:
    print(f"{country['country']}: {country['percentage']:.1f}%")

# Check cache stats
stats = repo.get_cache_stats()
print(f"Cached materials: {stats['cached_materials']}")
```

## Development

### Project Structure

This project uses modern Python architecture patterns:

- **Separation of Concerns**: Each package has a single responsibility
- **Dependency Injection**: Dependencies passed explicitly via `STDNDependencies`
- **Repository Pattern**: Data layer abstraction (`CountryDataRepository`)
- **Factory Pattern**: Agent creation via `AgentFactory`
- **Strategy Pattern**: Multiple debate strategies (future enhancement)

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests (requires database)
uv run pytest tests/integration/ -v

# Specific test file
uv run pytest tests/unit/test_agents.py -v

# With coverage report
uv run pytest tests/ --cov=src/stdn_agentic --cov-report=html

# View coverage
open htmlcov/index.html
```

### Type Checking

```bash
# Check entire project
uv run basedpyright src/stdn_agentic/

# Check specific module
uv run basedpyright src/stdn_agentic/agents/

# Check with strict mode
uv run basedpyright --strict src/stdn_agentic/
```

### Code Formatting & Linting

```bash
# Format code with black
uv run black src/ tests/

# Check formatting without changes
uv run black --check src/

# Lint with ruff
uv run ruff check src/

# Auto-fix linting issues
uv run ruff check --fix src/

# Sort imports
uv run ruff check --select I --fix src/
```

### Adding New Features

**Add a new agent:**

1. Create `src/stdn_agentic/agents/new_agent.py`
2. Define Pydantic models for input/output
3. Create agent with `Agent(model, output_type, deps_type)`
4. Add to `agents/__init__.py`
5. Update `AgentFactory` if needed

**Add a new data source:**

1. Create client in `src/stdn_agentic/data/new_client.py`
2. Implement repository pattern if needed
3. Add caching support
4. Write unit tests
5. Update `data/__init__.py`

## Data Sources

### USGS Mineral Commodity Database

The primary data source is the USGS (United States Geological Survey) Mineral Commodity Reports database:

- **Format**: DuckDB database
- **Coverage**: 2022-2025 mineral production data
- **Contents**: Production amounts, reserves, countries, measurement units
- **Update Frequency**: Annual USGS reports

**Database Schema:**

```sql
-- Main table structure
CREATE TABLE world_mineral_commodity_report (
    src_yr INTEGER,           -- Source year of report
    meas_yr INTEGER,          -- Measurement year
    commodity VARCHAR,        -- Material name
    country VARCHAR,          -- Country name
    meas_type VARCHAR,        -- PRODUCTION, RESERVES, etc.
    value VARCHAR,            -- Production amount
    meas_unit VARCHAR,        -- metric tons, kg, etc.
    value_type VARCHAR        -- Number, Estimate, etc.
);
```

### Material Ontology

Material names are validated against a curated ontology (`data/material_ontology.csv`):

```csv
material_name,category,aliases
Lithium,metal,"lithium carbonate,lithium hydroxide"
Cobalt,metal,"cobalt oxide,cobalt sulfate"
Rare Earth Elements,metal,"REE,rare earths,neodymium,dysprosium"
```

### LLM Fallback

When USGS data is unavailable, the system falls back to LLM-based estimation:

- Uses Pydantic AI structured outputs
- Validates response format with Pydantic models
- Includes confidence scores
- Caches results to avoid redundant queries

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
```

#### `AgentFactory`

Creates and manages agent instances.

```python
factory = AgentFactory(config: Optional[Dict[str, Any]] = None)

# Create agents
component_agent = factory.create_component_agent()
materials_agent = factory.create_materials_agent()
country_agent = factory.create_country_agent()

# Batch creation
agents = factory.create_all_agents()
```

#### `CountryDataRepository`

Coordinates country data retrieval with USGS + LLM fallback.

```python
repo = CountryDataRepository(
    database_path: str,
    deps: STDNDependencies,
    top_n: int = 5,
    use_llm_fallback: bool = True
)

countries = await repo.get_country_data(
    material: str,
    src_year: int,
    meas_year: int,
    usage: Optional[RunUsage] = None
) -> List[Dict]
```

#### `USGSClient`

Direct USGS database client.

```python
with USGSClient(database_path: str, top_n: int = 5) as client:
    # Query top countries
    countries = client.query_top_countries(material, src_year, meas_year)

    # Get world totals
    totals = client.query_world_totals(material, src_year, meas_year)

    # Get country details
    details = client.query_country_details(material, country, src_year, meas_year)
```

### Data Models

#### `ComponentList`

```python
from stdn_agentic.agents import ComponentList

components = ComponentList(
    component_list=["display", "battery", "processor"]
)
```

#### `ComponentMaterialsList`

```python
from stdn_agentic.agents import ComponentMaterialsList, ComponentMaterials

materials = ComponentMaterialsList(
    component_list=[
        ComponentMaterials(
            component="battery",
            materials=["lithium", "cobalt", "nickel"]
        )
    ]
)
```

#### `CountryList`

```python
from stdn_agentic.agents import CountryList, CountryPercentage

countries = CountryList(
    country_list=[
        CountryPercentage(
            country="Chile",
            meas_unit="metric tons",
            amount=100000,
            percentage=65.5
        )
    ]
)
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make your changes** with tests
4. **Run tests**: `uv run pytest tests/ -v`
5. **Run type checking**: `uv run basedpyright src/`
6. **Format code**: `uv run black src/ tests/`
7. **Commit**: `git commit -m "feat: add your feature"`
8. **Push**: `git push origin feature/your-feature`
9. **Open a Pull Request**

### Code Style

- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for public APIs
- Keep functions focused and small (<50 lines)
- Add tests for new features

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- **USGS** for mineral commodity data
- **Pydantic AI** for structured LLM outputs
- **Astral (uv)** for fast package management
- **DuckDB** for embedded analytics database

## Citation

If you use this software in your research, please cite:

```bibtex
@software{stdn_agentic,
  title = {STDN Agentic: Supply Technology Dependency Network Generator},
  author = {Aaron Schroeder, Mandy Wilson},
  year = {2025},
  url = {https://github.com/NSSAC/dpi_stdn_agentic}
}
```

***

**Questions or Issues?** Open an issue on [GitHub](https://github.com/yourusername/dpi_stdn_agentic/issues)

**Need Support?** Check the [documentation](https://github.com/yourusername/dpi_stdn_agentic/wiki) or start a [discussion](https://github.com/yourusername/dpi_stdn_agentic/discussions)
