# STDN Agentic - Shallow Technology Dependency Network Generator

A multi-agent AI system built with Pydantic AI that automatically extracts technology components, identifies raw materials, and maps global supply chains for complex technologies using local LLMs via Ollama.

## Overview

This project uses an agentic AI framework to analyze technologies and generate **Shallow Technology Dependency Networks (STDNs)**. It breaks down technologies into their component parts, identifies the raw materials needed for each component, and enriches the data with country-level production information.

### What It Does

Given a technology (e.g., "Smartphone", "Electric Vehicle Battery"), the system:
1. **Extracts** the primary manufacturing components
2. **Identifies** raw materials for each component (validated against a materials ontology)
3. **Enriches** materials with country production data and HS codes
4. **Generates** country data repositories (optional) by querying USGS database and LLMs
5. **Outputs** structured data in CSV and JSON formats

## Architecture

The system follows a **multi-agent orchestrator pattern** where specialized AI agents handle different extraction tasks, coordinated by a central orchestrator.

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Main Entry                           │
│                       (main.py)                              │
│  -  Configuration loading                                     │
│  -  CLI argument parsing                                      │
│  -  Country data generation (optional)                        │
│  -  Orchestrator initialization                               │
└──────────────────────┬─────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│ Country Data         │    │  STDNOrchestrator    │
│ Generator            │    │  (orchestrator.py)   │
│ (country_agent.py)   │    │  -  Multi-agent       │
│  -  USGS queries      │    │    pipeline          │
│  -  LLM fallback      │    │  -  Data enrichment   │
│  -  Incremental       │    │  -  Output generation │
│    updates           │    │                      │
└──────────────────────┘    └──────┬───────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            ┌──────────┐   ┌──────────┐  ┌──────────┐
            │Component │   │Materials │  │ Country  │
            │  Agent   │   │  Agent   │  │  Agent   │
            │(agents.py│   │(agents.py│  │(agents.py│
            └──────────┘   └──────────┘  └──────────┘
                    │              │              │
                    └──────────────┴──────────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │   Data Models    │
                          │   (models.py)    │
                          │  -  Pydantic      │
                          │    validation    │
                          └──────────────────┘
```

## Core Components

### 1. `models.py` - Data Models and Validation

Defines the structured data schemas using Pydantic for type-safe operations:

- **`ComponentList`**: List of technology components
- **`ComponentMaterials`**: Materials for a single component
- **`ComponentMaterialsList`**: Collection of components with their materials
- **`CountryPercentage`**: Country production data structure
- **`CountryList`**: List of countries with production statistics
- **`STDNDependencies`**: Runtime dependencies passed to agents (ontology, country data, etc.)
- **`ConfigModel`**: Configuration validation model with country data generation options

**Role**: Ensures data consistency throughout the pipeline and provides automatic validation.

### 2. `agents.py` - AI Agents

Three specialized Pydantic AI agents that interact with Ollama:

#### Component Agent
- **Purpose**: Extracts primary manufacturing components from technology descriptions
- **Input**: Technology name and expert role
- **Output**: Validated list of components
- **Example**: "Smartphone" → ["Display Screen", "Battery", "Processor", "Camera Module"]

#### Materials Agent
- **Purpose**: Identifies raw materials for each component using a restricted ontology
- **Input**: Component list and materials ontology
- **Output**: Component-material mappings
- **Validation**: Includes a tool that validates materials against the ontology
- **Example**: "Display Screen" → ["Silicon", "Indium", "Tin oxide"]

#### Country Data Agent
- **Purpose**: Queries LLM for top producing countries when USGS data is unavailable
- **Input**: Material name, year, and top N requirement
- **Output**: Structured country production data with percentages
- **Fallback**: Used when USGS database lacks information for specific materials

**Role**: Encapsulates AI interaction logic with structured outputs and retry mechanisms.

### 3. `country_agent.py` - Country Data Generation

The `CountryDataGenerator` class generates and maintains the country production data repository:

#### Features

**Data Sources**:
- **Primary**: USGS Mineral Commodity Database for authoritative production data
- **Fallback**: LLM queries when USGS data is unavailable

**Generation Modes**:
- **Full**: Complete rebuild of country data (ignores existing file)
- **Incremental**: Add only new materials not in existing data
- **Update**: Selectively update specific materials

#### Key Methods

- **`_query_usgs_top_countries()`**: Query USGS database for top N producing countries
- **`_query_usgs_world_totals()`**: Get world production totals for percentage calculations
- **`_query_usgs_country_details()`**: Retrieve detailed production metrics by measure type
- **`_query_llm_for_countries()`**: Use LLM as fallback for missing USGS data
- **`_get_materials_to_process()`**: Determine which materials to process based on mode
- **`generate_country_data()`**: Main orchestration method with automatic backup creation

**Role**: Generates and maintains the materials-to-countries mapping used by the STDN pipeline.

### 4. `dependencies.py` - Dependency Initialization

Initializes the shared dependencies that all agents need:

- **Material Ontology**: Loads and structures the list of valid raw materials from CSV
- **Country Data**: Loads pre-computed or generated top producer countries for each material
- **Ollama Client**: Configures connection to local Ollama instance

**Role**: Centralizes data loading and provides consistent context to all agents.

### 5. `orchestrator.py` - Workflow Coordination

The `STDNOrchestrator` class manages the complete STDN pipeline:

#### Pipeline Steps

1. **Component Extraction**
   - Calls Component Agent with technology description
   - Validates output contains components
   - Implements timeout protection (default 180s)

2. **Materials Extraction**
   - Constructs prompt with components and ontology
   - Calls Materials Agent
   - Validates materials against restricted ontology

3. **Data Enrichment**
   - Maps materials to HS codes (Harmonized System trade codes)
   - Looks up top producer countries from repository
   - Filters by configured years (e.g., 2023, 2024)

4. **Output Generation**
   - Writes JSON files (one per technology) with full nested structure
   - Writes consolidated CSV with denormalized data
   - Records timing information for performance analysis

**Role**: Coordinates the multi-step workflow and handles errors gracefully.

### 6. `utils.py` - Helper Functions

Utility functions for data processing:

- **`read_json_to_dict()`**: Loads JSON configuration files
- **`create_ontology()`**: Builds material lists from CSV data
- **`create_ontology_dict()`**: Creates lookup dictionaries with HS codes
- **`intersect_lists()`**: Validates materials against ontology
- **`embed_comma_delimited_str()`**: Properly escapes CSV fields with commas
- **`validate_config()`**: Ensures required configuration parameters exist

**Role**: Provides reusable data manipulation functions.

### 7. `main.py` - Entry Point

Command-line interface and application initialization:

- Parses CLI arguments for STDN generation and country data management
- Searches for configuration files in multiple locations
- Validates configuration
- Optionally generates/updates country data repository
- Launches async orchestration loop
- Tracks overall usage statistics

**Role**: Provides user interface and application lifecycle management.

## Data Flow

### STDN Generation Flow
```
Input: tech_list.csv
    ↓
[Technology] → Component Agent → [Components]
    ↓
[Components] → Materials Agent → [Component-Material Pairs]
    ↓
[Materials] → Ontology Validation → [Valid Materials]
    ↓
[Valid Materials] → Country Repository Lookup → [Material-Country Data]
    ↓
Output: technology.json + stdns_output.csv
```

### Country Data Generation Flow
```
Input: materials_ontology.csv + USGS database
    ↓
[Materials] → Check USGS Database
    ↓
    ├─[Has Data]→ Query USGS → [Country Production Data]
    │
    └─[No Data]→ Query Country Agent (LLM) → [Estimated Production Data]
    ↓
Aggregate → material_top_countries.json
```

## Configuration

The system is configured via a JSON file:

```
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:7b",
  "output_dir": "./output",
  "output_csv_filename": "stdns_output",
  "materials_hs_codes_listing": "./data/hs_codes_and_usgs_names.csv",
  "materials_column_name": "Element/Compound",
  "materials_top_countries_repository": "./data/material_top_countries.json",
  
  "usgs_database": "./data/world_mineral_commodity_reports.db",
  "top_n_countries": 5,
  "generate_country_data": false,
  "country_data_mode": "full",
  "materials_to_update": null,
  
  "years_to_query": ,
  "topp": 0.000001,
  "write_nulls_to_output": true
}
```

### Key Configuration Parameters

**STDN Generation**:
- **`import_tech_list`**: CSV with technologies to analyze (columns: domain, tech, role)
- **`model`**: Ollama model identifier (must have `ollama:` prefix)
- **`materials_hs_codes_listing`**: CSV mapping materials to HS codes
- **`materials_column_name`**: Column name for materials in the ontology CSV
- **`materials_top_countries_repository`**: JSON file with country production data
- **`years_to_query`**: List of years to include in country data
- **`write_nulls_to_output`**: Whether to write rows with missing data

**Country Data Generation**:
- **`usgs_database`**: Path to DuckDB database with USGS Mineral Commodity reports
- **`top_n_countries`**: Number of top producing countries to include (default: 5)
- **`generate_country_data`**: Enable country data generation mode
- **`country_data_mode`**: Generation strategy - "full", "incremental", or "update"
- **`materials_to_update`**: List of specific materials to update (for "update" mode)

## Installation

```
# Clone the repository
git clone <repository-url>
cd dpi_stdn_agentic

# Install dependencies with uv
uv sync

# Set up environment variables
echo 'OLLAMA_BASE_URL=http://localhost:11434/v1' > .env

# Ensure Ollama is running with required model
ollama pull qwen2.5:7b
```

## Usage

### Basic STDN Generation

```
# Generate STDNs using existing country data
uv run stdn -i config.json
```

### Country Data Management

#### Generate New Country Data Repository
```
# Full rebuild - recreate entire country data file
uv run stdn -i config.json --generate-countries --country-mode full
```

#### Incremental Updates
```
# Add only new materials not in existing file
uv run stdn -i config.json --generate-countries --country-mode incremental
```

#### Update Specific Materials
```
# Update only Lithium and Cobalt data
uv run stdn -i config.json --generate-countries --country-mode update --update-materials Lithium Cobalt

# Update multiple materials
uv run stdn -i config.json --generate-countries --country-mode update --update-materials "Rare Earth Elements" Silicon Graphite
```

### Advanced Options

```
# Use specific config file
uv run stdn -i path/to/config.json

# Let it auto-discover config
uv run stdn

# Set config via environment variable
export STDN_CONFIG=/path/to/config.json
uv run stdn

# Generate countries then process technologies
uv run stdn -i config.json --generate-countries --country-mode incremental
```

## Input Data Requirements

### Technology List (`tech_list.csv`)

```
domain,tech,role
Electronics,Smartphone,an electronics manufacturing expert
Transportation,Electric Vehicle Battery,a battery technology specialist
Computing,Quantum Computer,a quantum computing researcher
```

### Materials Ontology (`hs_codes_and_usgs_names.csv`)

Must contain columns:
- Material/element name (configurable via `materials_column_name`)
- `HSCode`: Harmonized System trade classification code
- `USGS_Name`: Optional mapping to USGS commodity names for database queries

### USGS Database (`world_mineral_commodity_reports.db`)

DuckDB database containing USGS Mineral Commodity Summary tables with:
- Production data by country, year, and commodity
- Multiple measure types (production, reserves, exports, etc.)
- World total calculations for percentage derivations

### Country Data Repository (`material_top_countries.json`)

Generated or pre-existing JSON structure:
```
{
  "Lithium": [
    {
      "year": 2023,
      "query_source": "USGS",
      "top_countries": [
        {
          "country": "Chile",
          "reported_assets": [
            {
              "meas_type": "Production",
              "meas_unit": "metric tons",
              "value": 44000,
              "percent": 26.5
            }
          ]
        }
      ]
    }
  ]
}
```

## Output Format

### JSON Output (per technology)

```
{
  "technology": "Smartphone",
  "component_list": [
    {
      "component": "Display Screen",
      "raw_material_list": [
        {
          "raw_material": "Silicon",
          "hscode": "280461",
          "country_year_breakdown": [...]
        }
      ]
    }
  ]
}
```

### CSV Output (consolidated)

Columns: `Technology, Component, Material, HS Code, Query Source, Year, Country, MeasType, MeasUnit, Amount, Percent`

Denormalized format suitable for analysis and visualization.

## Project Structure

```
dpi_stdn_agentic/
├── src/
│   └── stdn_agentic/
│       ├── __init__.py          # Package initialization
│       ├── agents.py            # AI agent definitions (3 agents)
│       ├── country_agent.py     # Country data generator
│       ├── dependencies.py      # Dependency initialization
│       ├── main.py              # CLI entry point
│       ├── models.py            # Pydantic data models
│       ├── orchestrator.py      # Pipeline orchestration
│       └── utils.py             # Helper functions
├── data/
│   ├── tech_list.csv            # Input technologies
│   ├── hs_codes_and_usgs_names.csv  # Materials ontology
│   ├── world_mineral_commodity_reports.db  # USGS database
│   └── material_top_countries.json  # Country production data
├── output/                      # Generated output files
├── config.json                  # Runtime configuration
├── pyproject.toml              # Project metadata
└── README.md                   # This file
```

## Error Handling

The system includes robust error handling:

- **Timeout Protection**: Agents timeout after 180s (configurable)
- **Validation Retry**: Materials agent retries validation failures
- **Graceful Degradation**: Individual technology failures don't stop the pipeline
- **USGS Fallback**: Automatic LLM fallback when USGS data is unavailable
- **Backup Creation**: Automatic timestamped backups when updating country data
- **Detailed Error Reporting**: Errors logged with context and stack traces

## Key Design Decisions

### Why Multi-Agent Architecture?

- **Separation of Concerns**: Each agent has a single, well-defined responsibility
- **Modularity**: Agents can be updated, tested, or replaced independently
- **Type Safety**: Structured outputs ensure data consistency
- **Observability**: Each agent's behavior can be monitored separately
- **Hybrid Data Sources**: Seamless integration of database queries and LLM inference

### Why Pydantic AI?

- **Structured Outputs**: Automatic validation of LLM responses
- **Type Safety**: Pydantic models catch errors at runtime
- **Ollama Integration**: Native support for local LLM deployment
- **Tool Support**: Agents can call Python functions for validation

### Why Hybrid USGS + LLM Approach?

- **Accuracy**: USGS provides authoritative, verified production data
- **Coverage**: LLM fills gaps for materials not tracked by USGS
- **Transparency**: `query_source` field tracks data provenance
- **Efficiency**: Database queries are faster than LLM calls

### Why Src Layout?

- **Import Safety**: Prevents accidental imports from development directory
- **Professional Standard**: Aligns with Python packaging best practices
- **Testing Isolation**: Ensures tests run against installed package

## Dependencies

- **pydantic-ai**: Agent framework with structured outputs
- **pydantic**: Data validation and settings management
- **pandas**: Data manipulation and CSV handling
- **ollama**: Local LLM provider
- **python-dotenv**: Environment variable management
- **duckdb**: Embedded database for USGS data queries

## License

[Your License Here]

## Contributors

[Your Name/Team]

## Contact

[Contact Information]


