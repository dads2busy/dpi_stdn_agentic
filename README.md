# STDN Agentic Framework

A multi-agent AI framework for generating **Shallow Technology Dependency Networks (STDNs)** through iterative debate and consensus-building. The system extracts technology components, identifies raw materials, and enriches with global production data using LLM-powered agents and USGS databases.

***

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation & Usage](#installation--usage)
  - [Prerequisites](#prerequisites)
  - [Quick Start](#quick-start)
  - [Configuration](#configuration)
  - [Running the Pipeline](#running-the-pipeline)
  - [Advanced Usage](#advanced-usage)
- [Pipeline Stages](#pipeline-stages)
  - [Stage 1: Component Extraction](#stage-1-component-extraction)
  - [Stage 2: Materials Identification](#stage-2-materials-identification)
  - [Stage 3: Country Production Data](#stage-3-country-production-data)
- [Multi-Agent Debate System](#multi-agent-debate-system)
- [Output Format](#output-format)
- [Technical Details](#technical-details)

***

## Overview

**Problem:** Understanding global supply chains for complex technologies requires identifying components, materials, and production countries—a task traditionally requiring extensive domain expertise and manual research.

**Solution:** STDN Agentic uses multiple AI agents that debate and reach consensus on:
1. **Components**: What are the major subassemblies? (e.g., "Solar Cells", "Junction Box")
2. **Materials**: What raw materials are needed? (e.g., Silicon, Copper, Glass)
3. **Production**: Which countries produce these materials and in what quantities?

**Key Features:**
- ✅ Multi-agent debate with critique-driven convergence
- ✅ Dynamic confidence scoring for all outputs
- ✅ Strict ontology enforcement (materials must exist in USGS database)
- ✅ Comprehensive transcripts with reasoning chains
- ✅ CSV output with confidence scores and justifications

***

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STDNOrchestrator                          │
│  • Coordinates 3-stage pipeline                             │
│  • Manages debate system and transcripts                    │
│  • Handles checkpointing and error recovery                 │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Component    │   │  Materials    │   │   Country     │
│    Agent      │   │    Agent      │   │    Repo       │
│               │   │               │   │               │
│ • Extracts    │   │ • Maps comp → │   │ • USGS DB     │
│   components  │   │   materials   │   │ • LLM fallback│
│ • Debate      │   │ • Ontology    │   │ • Debate      │
│   support     │   │   constrained │   │   (optional)  │
└───────────────┘   └───────────────┘   └───────────────┘
```

***

## Installation & Usage

### Prerequisites

**Required:**
- **Python 3.10+**
- **[uv](https://github.com/astral-sh/uv)** - Fast Python package installer and resolver
- **Ollama** (for local LLM inference) or API keys for OpenAI/Anthropic

**Install uv:**
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

**Install Ollama** (for local models):
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull recommended model
ollama pull qwen2.5:7b
```

### Quick Start

**1. Clone the repository:**
```bash
git clone https://github.com/[your-repo]/dpi_stdn_agentic.git
cd dpi_stdn_agentic
```

**2. Install dependencies with uv:**
```bash
# Install all dependencies (creates .venv automatically)
uv sync

# Or install with development dependencies
uv sync --group dev
```

**3. Set up configuration:**
```bash
# Copy example config
cp config_example.json config.json

# Edit config.json with your paths and settings
# Minimum required: import_tech_list, model, usgs_database
```

**4. Prepare your technology list:**

Create a CSV file with technologies to analyze:
```csv
tech,role,domain
Solar Panel,supply chain analyst,renewable energy
Lithium-ion Battery,materials engineer,energy storage
Wind Turbine,mechanical engineer,renewable energy
```

**5. Run the pipeline:**
```bash
# Basic run (single-agent mode, fast)
uv run stdn -i config.json

# With component debate enabled
ENABLE_DEBATE=true uv run stdn -i config.json

# With full multi-agent debate (all stages)
ENABLE_DEBATE=true \
ENABLE_MATERIAL_DEBATE=true \
ENABLE_COUNTRY_DEBATE=true \
uv run stdn -i config.json
```

### Configuration

#### **Minimal config.json**

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:7b",
  "usgs_database": "./data/usgs_production.db",
  "output_dir": "./output"
}
```

#### **Full config.json with all options**

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:14b",
  "output_dir": "./output",
  "output_csv_filename": "stdns_output",
  
  "materials_hs_codes_listing": "./data/hs_codes_and_usgs_names.csv",
  "materials_column_name": "Elements_Compounds",
  "materials_top_countries_repository": "./data/material_top_countries.json",
  
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "top_n_countries": 5,
  "years_to_query": [2024, 2023],
  "write_nulls_to_output": true,
  
  "topp": 0.000001,
  "materials_use_topp": true,
  "materials_iteration_count": 10,
  "materials_count_threshold": 5,
  
  "enable_checkpoints": true,
  "checkpoint_interval": 5
}
```

#### **Configuration Parameters**

| Parameter | Description | Default |
|-----------|-------------|---------|  
| `import_tech_list` | Path to CSV with technology list | (required) |
| `model` | Model identifier (e.g., `ollama:qwen2.5:7b`, `openai:gpt-4`) | (required) |
| `usgs_database` | Path to USGS SQLite database | (required) |
| `output_dir` | Output directory for CSV and transcripts | `./output` |
| `output_csv_filename` | Output CSV name (no extension) | `stdns_output` |
| `top_n_countries` | Number of top producing countries | `5` |
| `years_to_query` | Years for historical data | `[2024, 2023]` |
| `write_nulls_to_output` | Include rows with missing country data | `true` |
| `enable_checkpoints` | Enable state persistence | `true` |
| `checkpoint_interval` | Save state every N technologies | `5` |

### Running the Pipeline

#### **Basic Commands**

```bash
# Standard run with default config
uv run stdn

# Specify config file explicitly
uv run stdn -i config.json

# Use environment variable for config
export STDN_CONFIG=./config.json
uv run stdn
```

#### **Debate Mode Options**

**Component Debate Only** (recommended starting point):
```bash
ENABLE_DEBATE=true uv run stdn -i config.json
```

**Full Multi-Agent Debate** (highest quality, slower):
```bash
ENABLE_DEBATE=true \
ENABLE_MATERIAL_DEBATE=true \
ENABLE_COUNTRY_DEBATE=true \
MAX_DEBATE_ROUNDS=3 \
CONVERGENCE_THRESHOLD=0.8 \
uv run stdn -i config.json
```

**Fast Mode** (single-agent, no debate):
```bash
# No environment variables needed - this is the default
uv run stdn -i config.json
```

#### **Environment Variables**

| Variable | Description | Default |
|----------|-------------|---------|  
| `ENABLE_DEBATE` | Enable component debate | `false` |
| `ENABLE_MATERIAL_DEBATE` | Enable materials debate | `false` |
| `ENABLE_COUNTRY_DEBATE` | Enable country data debate | `false` |
| `MAX_DEBATE_ROUNDS` | Maximum debate rounds | `3` |
| `CONVERGENCE_THRESHOLD` | Stop when overlap ≥ threshold | `0.8` |
| `SAVE_TRANSCRIPTS` | Save debate transcripts | `true` |
| `DEBATE_TOP_P` | Top-p sampling for debate | `0.0001` |
| `STDN_CONFIG` | Config file path | (none) |

### Advanced Usage

#### **Using Different Models**

**Ollama (local):**
```json
{
  "model": "ollama:qwen2.5:14b"
}
```

```bash
# Make sure model is pulled
ollama pull qwen2.5:14b
uv run stdn -i config.json
```

**OpenAI:**
```json
{
  "model": "openai:gpt-4"
}
```

```bash
export OPENAI_API_KEY=your_api_key_here
uv run stdn -i config.json
```

**Anthropic Claude:**
```json
{
  "model": "anthropic:claude-3-sonnet-20240229"
}
```

```bash
export ANTHROPIC_API_KEY=your_api_key_here
uv run stdn -i config.json
```

#### **Running Tests**

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/stdn_agentic --cov-report=html

# Run specific test file
uv run pytest src/stdn_agentic/tests/test_pipeline_integration.py

# Run unit tests only
uv run pytest src/stdn_agentic/tests/unit/
```

#### **Development Tools**

```bash
# Format code with black
uv run black src/

# Lint with ruff
uv run ruff check src/

# Type checking with basedpyright
uv run basedpyright src/

# Run all quality checks
uv run black src/ && uv run ruff check src/ && uv run basedpyright src/
```

#### **Inspecting Outputs**

```bash
# View generated CSV
head -n 20 output/stdns_output.csv

# View latest debate transcript
ls -lt src/stdn_agentic/debate_transcripts/results/ | head -n 5
cat src/stdn_agentic/debate_transcripts/results/Solar_Panel_*.txt

# Count technologies processed
wc -l output/stdns_output.csv

# Check unique materials
cut -d',' -f5 output/stdns_output.csv | sort -u | wc -l
```

#### **Performance Tuning**

**Parallel Processing** (experimental):
```json
{
  "parallel_processing": true,
  "max_parallel_jobs": 3
}
```

**Timeout Adjustments:**
```json
{
  "component_timeout": 180,
  "materials_timeout": 180,
  "country_timeout": 120
}
```

**Reduce Debate Rounds for Speed:**
```bash
ENABLE_DEBATE=true \
MAX_DEBATE_ROUNDS=2 \
CONVERGENCE_THRESHOLD=0.9 \
uv run stdn -i config.json
```

***

## Pipeline Stages

### Stage 1: Component Extraction

**Goal:** Identify the major manufactured components/subassemblies of a technology.

#### **Process:**

1. **Multi-Agent Proposal** (if debate enabled):
   - 3 agents analyze the technology from different perspectives:
     - **Agent 1**: "Focus on major procurable subassemblies with distinct supply chains"
     - **Agent 2**: "Focus on structural components required for construction"
     - **Agent 3**: "Distinguish manufactured components from raw materials"
   
   - Each agent proposes 4-8 components with:
     - **Name**: Component identifier
     - **Confidence** (0-1): LLM's certainty
     - **Reasoning**: Why this component is essential

2. **Debate Rounds**:
   - Agents review each other's proposals
   - Generate **critiques** identifying:
     - ✓ **Consensus** (3/3 agents agree)
     - ⚠ **Partial support** (2/3 agents, with alternatives suggested)
     - ❌ **Isolated proposals** (1/3 agents, questioned for necessity)
   
   - Agents refine proposals based on critiques
   - **Convergence calculation**:
     ```python
     overlap_score = (number_of_agreed_components) / (total_unique_components)
     ```
   
   - Stop when: `overlap_score ≥ convergence_threshold` (default: 0.8) or max rounds (default: 3)

3. **Consensus Building**:
   - Components mentioned by ≥2 agents → **consensus set**
   - Confidence calculation:
     ```python
     final_confidence = (num_supporting_agents / total_agents) × avg_agent_confidence
     ```
   - Reasoning merged from all supporting agents

#### **Example Output** (Solar Panel):

| Component | Confidence | Reasoning |
|-----------|------------|-----------|  
| Solar Cells (monocrystalline silicon) | 0.98 | Core photovoltaic conversion element, universally present |
| Tempered Glass Cover | 0.95 | Front protective layer, industry standard in virtually all modules |
| Aluminum Frame | 0.90 | Structural support and mounting interface, standard in most installations |
| Junction Box | 0.92 | Essential for safe electrical integration and performance optimization |
| EVA Encapsulant | 0.88 | Protective polymer layer, industry standard |
| Backsheet | 0.85 | Rear protective layer providing electrical insulation |

***

### Stage 2: Materials Identification

**Goal:** Map each component to its constituent raw materials (metals, minerals, compounds).

#### **Process:**

1. **Ontology Loading**:
   - Load `hs_codes_and_usgs_names.csv` (650+ materials)
   - Materials include: Silicon, Aluminum, Copper, Glass, Rare earths, etc.
   - **Strict constraint**: Materials MUST be in this list

2. **Materials Extraction** (per component):
   
   **Single-Agent Mode** (default):
   - LLM receives:
     - Component name
     - **FULL ontology list** (all 650+ materials)
     - Strict prompt: "Use ONLY exact names from list, no synonyms"
   
   - Returns: 2-8 materials per component
   
   - **Post-extraction filtering**:
     ```python
     ontology_set = set(material_ontology_list)
     for material in extracted_materials:
         if material.name not in ontology_set:
             log_warning(f"Filtered out '{material.name}'")
             remove_material()
     ```

   **Multi-Agent Debate Mode** (optional):
   - 3 agents independently propose materials
   - Debate with critiques showing alternatives:
     ```
     ⚠ PARTIAL: 2/3 agents proposed "Aluminum". 1 agent proposed "Steel" instead.
     Evaluate if Aluminum is functionally distinct or if materials can be consolidated.
     ```
   - Consensus materials have higher confidence

3. **Confidence Assignment**:
   - **Debate mode**: Based on agent agreement (3/3 = 0.95, 2/3 = 0.70)
   - **Single-agent**: Default 0.80
   - **Reasoning**: Tracks which debate round and peer support level

#### **Example Output** (Solar Panel → Solar Cells):

| Material | Confidence | Reasoning |
|----------|------------|-----------|  
| Silicon | 0.95 | Round 2 refinement with peer support: 2 agents |
| Aluminum | 0.90 | Used for electrical contacts, 2/3 agent consensus |
| Silver | 0.70 | Front contact metallization, 1/3 agent proposal |

#### **Validation:**
```
✓ 21 materials extracted
✓ 100% in ontology (no filtered materials)
✓ Average 3.5 materials per component
```

***

### Stage 3: Country Production Data

**Goal:** Identify which countries produce each material and their production share.

#### **Process:**

1. **USGS Database Lookup**:
   - Query `usgs_production.db` for material name
   - Fields: `country`, `amount`, `meas_unit`, `year`
   - Calculate percentage of global production:
     ```python
     total_global = sum(country_amounts)
     percentage = (country_amount / total_global) × 100
     ```

2. **Top-N Selection**:
   - Return top 5 countries by production volume
   - Include "OTHER" category for remaining producers
   - Confidence: 0.95 (USGS data is authoritative)

3. **LLM Fallback** (if no USGS data):
   - LLM estimates production based on:
     - Industry reports
     - Trade data
     - Geographic factors
   - Confidence: 0.70-0.85 (lower than USGS)
   - **Reasoning** includes data sources

4. **Country Debate Mode** (optional):
   - 3 agents independently research production data
   - Debate to reconcile discrepancies
   - Consensus countries and percentages selected

#### **Example Output** (Silicon production):

| Country | Amount | Unit | Percentage | Confidence | Reasoning |
|---------|--------|------|------------|------------|-----------|  
| CHINA | 3600.0 | THOUSAND METRIC TONS | 40.0% | 0.95 | USGS Mineral Commodity Summaries 2024 |
| RUSSIA | 570.0 | THOUSAND METRIC TONS | 6.33% | 0.95 | USGS authoritative data |
| BRAZIL | 190.0 | THOUSAND METRIC TONS | 2.11% | 0.95 | USGS authoritative data |
| NORWAY | 200.0 | THOUSAND METRIC TONS | 2.22% | 0.95 | USGS authoritative data |
| OTHER | 100.0 | THOUSAND METRIC TONS | 1.11% | 0.95 | Aggregated remaining producers |

***

## Multi-Agent Debate System

### **Critique-Driven Convergence**

The debate system uses **structured critiques** to guide agents toward consensus:

#### **Critique Generation:**
```python
def generate_critique(proposals, component):
    agent_support = count_supporting_agents(component)
    
    if agent_support == 3:
        return f"✓ CONSENSUS: 3/3 agents agree on {component}. Strong evidence."
    
    elif agent_support == 2:
        alternatives = get_alternatives_from_other_agent(component)
        return f"⚠ PARTIAL: 2/3 agents proposed {component}. " \
               f"1 agent proposed: {alternatives}. " \
               f"Evaluate if functionally distinct."
    
    else:  # agent_support == 1
        alternatives = get_all_other_proposals(component)
        return f"❌ ISOLATED: Only 1/3 agents proposed {component}. " \
               f"Others proposed: {alternatives}. " \
               f"Is this truly essential?"
```

#### **Convergence Calculation:**

```python
def calculate_convergence(round_proposals):
    # Build agreement matrix
    all_components = set()
    for agent, proposals in round_proposals.items():
        all_components.update(proposals)
    
    # Count agreements
    agreed_components = []
    for component in all_components:
        supporting_agents = count_supporters(component, round_proposals)
        if supporting_agents >= 2:  # Majority
            agreed_components.append(component)
    
    # Convergence score
    convergence = len(agreed_components) / len(all_components)
    
    return convergence, agreed_components
```

#### **Confidence Weighting:**

Final confidence incorporates:
1. **Base confidence**: Average of agent-proposed confidences
2. **Support weight**: Number of supporting agents
3. **Peer boost**: Bonus per additional supporting agent

```python
base_confidence = mean([agent.confidence for agent in supporters])
support_weight = num_supporters / total_agents
peer_boost = (num_supporters - 1) × 0.15

final_confidence = base_confidence × support_weight + peer_boost
final_confidence = min(final_confidence, 1.0)  # Cap at 1.0
```

***

## Output Format

### **CSV Output** (`stdn_output.csv`)

Each row represents: **Technology → Component → Material → Country**

| Column | Type | Description | Example |
|--------|------|-------------|---------|  
| `technology` | str | Technology name | "Solar Panel" |
| `component` | str | Component name (normalized) | "solar cells (monocrystalline silicon)" |
| `component_confidence` | float | Component confidence (0-1) | 0.98 |
| `component_reasoning` | str | Why component is essential | "Core photovoltaic conversion element..." |
| `material` | str | Raw material name | "Silicon" |
| `material_confidence` | float | Material confidence (0-1) | 0.95 |
| `material_reasoning` | str | Material extraction context | "Round 2 refinement with peer support: 2" |
| `hs_code` | str | Harmonized System trade code | "280469" |
| `country` | str | Producing country | "CHINA" |
| `meas_unit` | str | Production unit | "THOUSAND METRIC TONS" |
| `amount` | float | Production quantity | 3600.0 |
| `percentage` | float | % of global production | 40.0 |
| `country_confidence` | float | Country data confidence | 0.95 |
| `country_reasoning` | str | Data source | "USGS Mineral Commodity Summaries 2024" |

### **Transcript Output** (`.txt` files)

Saved to: `src/stdn_agentic/debate_transcripts/results/`

**Structure:**
```
================================================================================
MULTI-AGENT DEBATE TRANSCRIPT: Solar Panel
Generated: 2025-12-01T21:11:49
================================================================================

TECHNOLOGY SPECIFICATION:
  Monocrystalline silicon photovoltaic (PV) module
  Reasoning: 85% of global production as of 2024...

PHASE 1: INDEPENDENT COMPONENT EXTRACTION
  Agent_1: 6 components proposed (avg confidence: 0.91)
  Agent_2: 6 components proposed (avg confidence: 0.92)
  Agent_3: 6 components proposed (avg confidence: 0.91)

PHASE 2: DEBATE ROUNDS
  ROUND 1: Convergence: 75.0%
    Critiques:
      - Solar Cells: ✓ CONSENSUS (3/3 agents)
      - Aluminum Frame: ⚠ PARTIAL (2/3 agents, alternatives: Steel Frame)
  
  ROUND 2: Convergence: 100.0% ✓ Threshold reached

PHASE 3: FINAL CONSENSUS
  Total Debate Rounds: 2
  Overall Confidence: 0.95
  
  Final Components (6):
    ✓ Solar Cells (monocrystalline silicon) - confidence: 0.98
    ✓ Tempered Glass Cover - confidence: 0.95
    ✓ Aluminum Frame - confidence: 0.90
    ... [continued]

MATERIALS EXTRACTION DEBATE
  ROUND 1: Convergence: 24.4%
    solar cells (monocrystalline silicon):
      - Silicon: ✓ CONSENSUS (3/3 agents, confidence: 0.98)
      - Aluminum: ⚠ PARTIAL (2/3 agents, alternatives: Steel)
      - Silver: ❌ ISOLATED (1/3 agents, alternatives: Copper)

  ROUND 2: Convergence: 85.0% ✓ Threshold reached

FINAL MATERIAL ASSIGNMENTS
  solar cells (monocrystalline silicon):
    • Silicon (confidence: 0.95) → 3/3 agents, avg confidence 0.95
    • Aluminum (confidence: 0.76) → 2/3 agents, avg confidence 0.90
    • Silver (confidence: 0.48) → 1/3 agents, avg confidence 0.70

COUNTRY PRODUCTION DATA
  solar cells (monocrystalline silicon):
    Silicon:
      • CHINA: 40.0% (confidence: 0.95)
        → USGS Mineral Commodity Summaries 2024
      • RUSSIA: 6.33% (confidence: 0.95)
      • BRAZIL: 2.11% (confidence: 0.95)
    
    Aluminum:
      • CHINA: 58.57% (confidence: 0.95)
        → USGS authoritative data
      ... [continued]

================================================================================
END OF STDN TRANSCRIPT
================================================================================
```

***

## Technical Details

### **Technology Stack**

**Core Dependencies:**
- `pydantic-ai>=0.0.14` - LLM agent framework with structured outputs
- `pydantic>=2.5.0` - Data validation and settings management
- `ollama>=0.3.0` - Local LLM inference client
- `pandas>=2.0.0` - Data manipulation and CSV I/O
- `duckdb>=1.2.2` - Embedded analytics for USGS data
- `python-dotenv>=1.0.0` - Environment configuration

**Development Tools:**
- `pytest>=7.0.0` - Testing framework
- `pytest-asyncio>=0.20.0` - Async test support
- `ruff>=0.1.0` - Fast Python linter
- `black>=23.0.0` - Code formatter
- `basedpyright>=1.0.0` - Type checker

**Python Version:** 3.10+

### **Project Structure**

```
dpi_stdn_agentic/
├── src/stdn_agentic/
│   ├── agents/              # Agent implementations
│   │   ├── component_agent.py
│   │   ├── materials_agent.py
│   │   └── country_agent.py
│   ├── debate/              # Multi-agent debate system
│   │   ├── debater.py
│   │   ├── material_debater.py
│   │   └── material_country_debater.py
│   ├── orchestrator/        # Pipeline coordination
│   │   ├── pipeline.py
│   │   ├── checkpoint.py
│   │   ├── error_handler.py
│   │   └── state_manager.py
│   ├── data/                # Data access layer
│   │   ├── repository.py
│   │   ├── usgs_client.py
│   │   ├── loaders.py
│   │   └── cache.py
│   ├── core/                # Core types and schemas
│   │   ├── schemas.py
│   │   ├── base_agent.py
│   │   └── constants.py
│   ├── reporting/           # Output generation
│   │   └── debate_reporter.py
│   ├── tests/               # Test suite
│   └── main.py              # CLI entry point
├── data/                    # Data files
│   ├── hs_codes_and_usgs_names.csv
│   ├── usgs_production.db
│   └── tech_list.csv
├── output/                  # Generated outputs
├── config.json              # Configuration
├── pyproject.toml           # Project metadata
└── README.md
```

### **Model Support**

The framework supports multiple LLM providers:

| Provider | Model Examples | Configuration |
|----------|----------------|---------------|
| **Ollama** | `ollama:qwen2.5:7b`, `ollama:llama3:8b` | Local, no API key needed |
| **OpenAI** | `openai:gpt-4`, `openai:gpt-3.5-turbo` | Set `OPENAI_API_KEY` |
| **Anthropic** | `anthropic:claude-3-sonnet-20240229` | Set `ANTHROPIC_API_KEY` |

**Recommended Models:**
- **Fast & Local**: `ollama:qwen2.5:7b` (~4GB RAM)
- **Balanced**: `ollama:qwen2.5:14b` (~9GB RAM)
- **Best Quality**: `openai:gpt-4` or `anthropic:claude-3-sonnet`

### **Material Ontology Enforcement**

The system enforces strict ontology compliance for materials:

```python
# Before (raw LLM output):
"Ethylene-vinyl acetate"        ❌ Not in ontology
"PET film"                      ❌ Not in ontology
"Aluminum alloy 6061"           ❌ Too specific

# After (filtered to ontology):
"Polyethylene"                  ✓ Base polymer
"Polyethylene terephthalate"    ✓ Exact match
"Aluminum"                      ✓ Base metal
```

**Enforcement mechanism:**
1. LLM prompt includes FULL ontology list (650+ materials)
2. Post-extraction filtering removes non-ontology materials
3. Console warnings: `⚠️ Filtered out 'EVA' (not in ontology)`

### **Normalization**

Component and material names are normalized for matching:

```python
def normalize_name(name: str) -> str:
    return name.lower().strip()

# Examples:
"Solar Cells (Monocrystalline Silicon)" → "solar cells (monocrystalline silicon)"
"Tempered Glass Cover"                  → "tempered glass cover"
"Junction Box"                          → "junction box"
```

This ensures consistency between debate phases and CSV output.

### **Confidence Score Interpretation**

| Range | Interpretation | Source |
|-------|----------------|--------|
| 0.95-1.0 | High confidence | 3/3 agent consensus, USGS data |
| 0.80-0.94 | Good confidence | 2/3 agents, single-agent extraction |
| 0.70-0.79 | Moderate confidence | 2/3 agents (materials), LLM fallback |
| 0.50-0.69 | Low confidence | 1/3 agent proposals, uncertain LLM estimates |
| 0.0-0.49 | Very low confidence | Isolated proposals, speculative data |

### **Performance Considerations**

**Single technology (6 components, debate mode):**
- Component extraction: ~30 seconds (3 agents × 3 rounds)
- Materials extraction: ~45 seconds (3 agents × 2 rounds × 6 components)
- Country  ~5 seconds (USGS lookups)
- **Total**: ~80 seconds

**Optimizations:**
- Use `enable_debate=False` for 3x speedup (lower quality)
- Reduce `max_debate_rounds` to 2 for faster convergence
- Increase `convergence_threshold` to 0.9 for earlier stopping
- Use local Ollama models to avoid API rate limits

### **Error Handling**

```python
# Transient LLM errors (network, timeouts)
→ Retry with exponential backoff (2s, 4s, 6s)

# Missing USGS data
→ LLM fallback with lower confidence

# Empty components/materials
→ Log warning, skip technology, continue pipeline

# Ontology violations
→ Filter materials, log violations, continue with valid materials
```

### **Checkpointing & Resume**

Enable checkpointing for long-running jobs:

```json
{
  "enable_checkpoints": true,
  "checkpoint_interval": 5
}
```

To resume from checkpoint:
```bash
# Checkpoints are automatically detected and loaded
uv run stdn -i config.json
```

Checkpoint files stored in: `.checkpoints/`

***

## Citation

If you use this framework in research, please cite:

```bibtex
@software{stdn_agentic,
  title = {STDN Agentic: Multi-Agent Framework for Supply Chain Network Analysis},
  author = {[Your Name]},
  year = {2025},
  url = {https://github.com/[your-repo]}
}
```

***

## License

MIT License - See LICENSE file for details

***

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Development setup:**
```bash
# Clone and install with dev dependencies
git clone https://github.com/[your-repo]/dpi_stdn_agentic.git
cd dpi_stdn_agentic
uv sync --group dev

# Run tests before submitting PR
uv run pytest
uv run black src/
uv run ruff check src/
```

***

## Contact

For questions or contributions:
- **Issues**: [GitHub Issues](https://github.com/[your-repo]/issues)
- **Discussions**: [GitHub Discussions](https://github.com/[your-repo]/discussions)
- **Email**: [your-email]
