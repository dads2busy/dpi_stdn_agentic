# STDN Agentic Framework

The STDN Agentic framework is a multi-agent AI system for generating **Shallow Technology Dependency Networks (STDNs)** through iterative debate, critique, and consensus-building. Instead of treating technology supply-chain mapping as a one-off prompt, the framework decomposes the problem into explicit stages—component extraction, materials identification, and production profiling—each implemented as a set of cooperating agents with clear responsibilities. This README walks through the motivation, architecture, agents, debate mechanisms, and usage so that both supply-chain analysts and multi-agent engineers can understand how the system works and how to extend it.

---

## Concept and objectives

Understanding global supply chains for complex technologies requires more than simply listing parts: it involves reasoning about components, raw materials, and which countries dominate production for those materials. Traditionally, this analysis requires substantial domain expertise and manual research across technical documentation and statistical yearbooks. STDN Agentic aims to automate a large portion of that reasoning by orchestrating LLM-powered agents that can propose, critique, and refine technology dependency networks in a structured and auditable way.

The framework focuses specifically on *shallow* technology dependency networks: graphs with a small number of layers that remain interpretable. Each STDN connects technologies → components → materials → producing countries, with confidence scores and reasoning attached at each step. This structure captures the most policy-relevant dependencies (such as concentration risk in particular materials or countries) while keeping outputs simple enough to review, debug, and use in downstream analyses and dashboards.

**Technical implementation:** The framework is packaged as `stdn-agentic` (see `pyproject.toml`) with a main entry point at `stdn_agentic.main:main` registered as the `stdn` console script. Core dependencies include `pydantic>=2.5.0` and `pydantic-ai>=0.0.14` for typed agent definitions, `pandas>=2.0.0` for CSV handling, `duckdb>=1.2.2` for production data queries, and `ollama>=0.3.0` for local LLM inference. Input technologies are read from CSV into Pydantic models representing technologies, components, and materials, with all agent outputs validated against explicit schemas defined in `src/stdn_agentic/agents/` and `src/stdn_agentic/debate/`.

---

## High-level architecture

At a high level, STDN Agentic is built around a central orchestrator that coordinates a three-stage pipeline and a set of specialized agents that perform domain reasoning. The orchestrator is responsible for loading configuration, iterating over input technologies, managing multi-agent debates, handling checkpointing, and writing outputs. The agents are responsible for proposing components, mapping materials, and querying or approximating production data, each running on a configurable LLM backend such as Ollama or a hosted provider.

You can visualize the architecture as a shallow stack of layers:

```text
CLI / stdn command
          ↓
   STDNOrchestrator (pipeline.py)
          ↓
 ┌──────────────────────┬──────────────────────┬──────────────────────┐
 │ Stage 1:             │ Stage 2:             │ Stage 3:             │
 │ Component Extraction │ Materials Mapping    │ Country Data         │
 ├──────────────────────┼──────────────────────┼──────────────────────┤
 │ • 3 Debating Agents  │ • 3 Debating Agents  │ • USGS Database      │
 │ • Jaccard-based      │ • Jaccard-based      │ • LLM Fallback       │
 │   convergence        │   convergence        │ • Borda Voting       │
 │ • LLM normalization  │ • Material ontology  │ • 30-day Cache       │
 │ • Confidence scoring │   matching           │ • Multi-tier Query   │
 └──────────────────────┴──────────────────────┴──────────────────────┘
          ↓
   CSV + JSON outputs + debate transcripts
```

**Module organization:** The codebase is structured as follows:

```text
src/stdn_agentic/
  ├── main.py                    # CLI entry point, config discovery, async orchestration
  ├── models.py                  # ConfigModel and STDNDependencies Pydantic models
  ├── dependencies.py            # Dependency initialization and management
  ├── utils.py                   # JSON loading, config validation, file I/O
  ├── agents/
  │   ├── component_agent.py     # Component extraction agent (ComponentList schema)
  │   ├── materials_agent.py     # Material identification agent (ComponentMaterialsList schema)
  │   ├── country_agent.py       # Country production estimation agent (CountryList schema)
  │   └── factory.py             # Agent factory for creating configured agent instances
  ├── orchestrator/
  │   ├── pipeline.py            # STDNOrchestrator - main pipeline coordinator
  │   ├── component_extractor.py # ComponentExtractor - Stage 1 logic (multi-agent debate)
  │   ├── materials_extractor.py # MaterialsExtractor - Stage 2 logic (multi-agent debate)
  │   ├── country_data_enricher.py # CountryDataEnricher - Stage 3 logic (database + fallback)
  │   └── state_manager.py       # State management utilities
  ├── data/
  │   ├── loaders.py             # CSV and ontology loading utilities
  │   ├── repository.py          # CountryDataRepository (three-tier data retrieval)
  │   ├── usgs_client.py         # DuckDB client for USGS production data
  │   ├── cache.py               # Material-country caching layer
  │   └── llm_fallback_cache.py  # Persistent cache for LLM debate results (30-day TTL)
  ├── debate/
  │   ├── component_debater.py   # Multi-agent debate orchestrator for components
  │   │                          # - Jaccard similarity convergence metric
  │   │                          # - LLM-based semantic normalization
  │   │                          # - Peer support calculation
  │   ├── component_models.py    # Data models for component debate
  │   ├── component_normalization.py  # Component name canonicalization
  │   ├── material_debater.py    # Multi-agent debate orchestrator for materials
  │   │                          # - Fuzzy matching to ontology
  │   │                          # - Material variant mappings
  │   ├── material_models.py     # Data models for material debate
  │   ├── material_normalization.py   # Material name canonicalization
  │   ├── material_country_debater.py # Borda voting for country consensus
  │   │                          # - Rank-based voting (top N countries)
  │   │                          # - Confidence-weighted aggregation
  │   └── material_country_models.py  # Data models for country debate
  ├── reporting/
  │   └── debate_reporter.py     # Debate transcript generation (JSON + TXT)
  └── debate_transcripts/
      └── results/               # Saved debate transcripts with timestamps
```

This architecture keeps the technology dependency network shallow at both the data and code levels. The orchestrator sees stages as black boxes with typed inputs and outputs (Pydantic models), agents know only their own tools and schemas, and data-access components hide details of the USGS and ontology files. That separation allows you to change models, swap data backends, or extend debate strategies without rewriting the whole system.

---

## The Agent System

STDN Agentic uses four specialized agents, each with distinct responsibilities and reasoning patterns. The agents are designed to work both independently (single-agent mode) and collaboratively (multi-agent debate mode) to achieve consensus on technology dependencies.

### Agent Overview

| Agent | Stage | Purpose | Confidence | Debate Type |
|-------|-------|---------|-----------|------------|
| **Component Agent** | 1 | Extracts primary manufacturing components from technology descriptions | 0.85-0.95 | Jaccard-based convergence |
| **Materials Agent** | 2 | Identifies raw materials needed for each component | 0.70-0.90 | Jaccard-based convergence |
| **Country Agent** | 3 | Estimates top-producing countries for raw materials | 0.95 (USGS) → 0.75 (LLM) | Borda voting (fallback only) |
| **Factory** | All | Creates and configures agent instances with caching | — | — |

### Stage 1: Component Agent

**File:** `agents/component_agent.py`

**Purpose:** Transforms a high-level technology description into a list of primary manufacturing components with confidence scores.

**Key Features:**

1. **Technology Specification Validation** - Identifies the most common, industry-standard form of a technology
   - Input: "battery" → Output: "Lithium-ion battery pack (NMC chemistry)"
   - Uses LLM reasoning to validate and refine terminology

2. **Component Classification** - Distinguishes primary components from raw materials
   - **INCLUDE**: Major subassemblies (display, battery, processor, chassis)
   - **EXCLUDE**: Raw materials, tools, consumables, fasteners

3. **Confidence Scoring** - Assigns 0.0-1.0 scores based on universality
   - 0.9-1.0: Always present (display in smartphone)
   - 0.7-0.89: Common but may vary (camera in phone)
   - 0.5-0.69: Optional/design-dependent (wireless charging)

4. **Dual-Mode Operation**:
   - **Single-agent**: Direct LLM inference → components
   - **Multi-agent debate**: 3 agents with different perspectives, Jaccard convergence metric

**Input Schema:**
```
User query: "Extract components from smartphone"
Technology: smartphone
Role: personal computing device
Domain: consumer electronics
```

**Output Schema (ComponentList):**
```python
{
  "technology_specification": "Touchscreen smartphone with OLED display",
  "technology_reasoning": "OLED displays represent 60% of premium devices as of 2024",
  "component_list": [
    {"name": "Display Module", "confidence": 0.95, "reasoning": "Universal UI interface"},
    {"name": "Battery Pack", "confidence": 0.95, "reasoning": "Essential for portability"},
    {"name": "Camera Module", "confidence": 0.90, "reasoning": "Standard feature"},
    ...
  ]
}
```

### Stage 2: Materials Agent

**File:** `agents/materials_agent.py`

**Purpose:** Maps each component to the raw materials required for manufacturing.

**Key Features:**

1. **Raw Material Extraction** - Identifies fundamental inputs to component manufacturing
   - Battery Pack → Lithium, Cobalt, Nickel, Copper, Aluminum, Graphite
   - Display Module → Glass, Indium, Rare Earth Elements, Silver

2. **Material Variant Mapping** - Normalizes common aliases
   - "lithium-ion" → "Lithium"
   - "stainless steel" → "Steel"
   - Chemical symbols: "Li", "Co", "Ni" → Full names

3. **Fuzzy Ontology Matching** - Maps agent outputs to canonical material names
   - Multi-strategy matching (exact, variant, word-level, fuzzy similarity)
   - Ensures outputs align with USGS/mining industry terminology
   - Prevents "Lithium" vs "Li" vs "Lithium Ion" inconsistencies

4. **Confidence-based Reasoning** - Scores material essentiality
   - 0.9-1.0: Cannot manufacture without it
   - 0.7-0.89: Standard material, rarely substituted
   - 0.5-0.59: One of several possible materials
   - 0.3-0.49: Optional or easily substituted

**Input Schema:**
```
Component: "Battery Pack"
Expected materials: [various, will be generated]
```

**Output Schema (ComponentMaterialsList):**
```python
{
  "component_list": [
    {
      "component": "Battery Pack",
      "raw_materials": [
        {"name": "Lithium", "confidence": 0.95, "reasoning": "Primary energy storage element"},
        {"name": "Cobalt", "confidence": 0.85, "reasoning": "Cathode material; NMC standard"},
        {"name": "Nickel", "confidence": 0.80, "reasoning": "Cathode material; ratio varies"},
        ...
      ]
    }
  ]
}
```

### Stage 3: Country Agent

**File:** `agents/country_agent.py`

**Purpose:** Estimates top-producing countries for raw materials with production percentages.

**Key Features:**

1. **Global Production Mapping** - Identifies major producing countries by volume
   - Leverages expert knowledge of mining operations and trade flows
   - Ranks countries by production share (e.g., China 60%, Australia 25%, Chile 15%)

2. **Confidence-based Reasoning** - Scores estimate reliability
   - 0.9-1.0: Recent authoritative data (USGS, World Bank)
   - 0.8-0.89: Well-documented major producer
   - 0.7-0.79: Known producer, reasonable estimates
   - 0.5-0.69: Limited data, extrapolated estimates

3. **Data Source Attribution** - Explains basis for estimates
   - USGS Mineral Commodity Summaries 2024
   - National geological surveys
   - Industry reports
   - Academic research

**Input Schema:**
```
Material: "Lithium"
Year: 2024
Target: Top 5 producing countries
```

**Output Schema (CountryList):**
```python
{
  "country_list": [
    {
      "country": "China",
      "percentage": 62,
      "amount": 78000,
      "meas_unit": "metric tons",
      "confidence": 0.92,
      "reasoning": "USGS 2024 - dominates production and refining"
    },
    {
      "country": "Australia",
      "percentage": 18,
      "amount": 22000,
      "meas_unit": "metric tons",
      "confidence": 0.90,
      "reasoning": "USGS verified - second largest producer"
    },
    ...
  ]
}
```

---

## Multi-Agent Debate System

STDN Agentic uses three debate mechanisms, each tailored to its stage's reasoning patterns:

### Debate Type 1: Jaccard Similarity (Components & Materials)

**Used in:** Stage 1 (Components) and Stage 2 (Materials)

**Why Jaccard?** Components and materials are categorical (you either propose something or you don't). Jaccard similarity measures overlap: how much do agents' proposed sets agree?

**Formula:**
```
Jaccard Similarity = |Set A ∩ Set B| / |Set A ∪ Set B|
```

For N agents, calculate all pairwise Jaccard similarities and average them. This produces a convergence score 0.0-1.0 where:
- 0.0 = Complete disagreement
- 1.0 = Perfect consensus

**How It Works:**

1. **Round 0 - Independent Proposals**
   - Agent 1 (Engineer perspective): Proposes components/materials
   - Agent 2 (Supply Chain perspective): Independent proposal
   - Agent 3 (Materials Science perspective): Independent proposal

2. **Compute Convergence**
   - Normalize proposal names (Jaccard + semantic normalization)
   - Calculate Jaccard overlap between all agent pairs
   - Average to get round convergence score

3. **Generate Critiques** (if convergence < threshold)
   - Highlight consensus components (supported by 2+ agents)
   - Critique isolated proposals (only 1 agent proposed)
   - Recommend removing low-confidence items with no peer support

4. **Refinement Round**
   - Each agent sees peer proposals and critiques
   - Agents resubmit refined proposals
   - Repeat until convergence ≥ threshold (default 0.75) or max rounds reached

5. **Final Consensus**
   - Merge all proposals from final round
   - Weight confidence by peer support:
     ```
     final_confidence = (agent_confidence × 0.7) + (peer_support_boost × 0.3)
     ```
   - Return top-N components/materials by weighted confidence

**Example: Component Debate for Smartphone**

```
Round 1:
  Agent 1: Display (0.95), Battery (0.95), Processor (0.85), Vibrator (0.70)
  Agent 2: Display (0.92), Battery (0.92), Camera (0.88), Speaker (0.75)
  Agent 3: Display (0.90), Battery (0.93), Processor (0.88), Camera (0.85)
  
  Convergence: 
    A1 ∩ A2 = {Display, Battery} / {Display, Battery, Processor, Camera, Vibrator, Speaker} = 2/6 = 0.33
    A1 ∩ A3 = {Display, Battery, Processor} / {Display, Battery, Processor, Camera, Vibrator} = 3/5 = 0.60
    A2 ∩ A3 = {Display, Battery, Camera} / {Display, Battery, Camera, Speaker, Processor} = 3/5 = 0.60
    Average: (0.33 + 0.60 + 0.60) / 3 = 0.51 < 0.75 threshold → Continue

Round 2 Critiques:
  - Display & Battery: Full consensus (all 3 agents) → Strong
  - Processor: 2/3 agents → Solid
  - Camera: 2/3 agents → Solid
  - Vibrator: 1/3 agents (only Agent 1) → Critique: "Isolated proposal"
  - Speaker: 1/3 agents (only Agent 2) → Critique: "Isolated proposal"

Agents Refine:
  Agent 1: Reconsiders Vibrator (isolated); keeps it at 0.65 (optional)
  Agent 2: Reconsiders Speaker (isolated); keeps it at 0.75 (common feature)
  Agent 3: Confident in core 3

Round 2 Convergence: 0.78 > 0.75 → STOP

Final Consensus:
  Display (confidence: 0.92, support: 3/3)
  Battery (confidence: 0.93, support: 3/3)
  Processor (confidence: 0.87, support: 2/3)
  Camera (confidence: 0.86, support: 2/3)
```

**Confidence Adjustment:**
- Base confidence: Average of agent proposals
- Support boost: Peer agents supporting the component
- Formula: `final_confidence = base_confidence + (peer_support × 0.15)`

### Debate Type 2: Borda Voting (Countries - Fallback Only)

**Used in:** Stage 3 (Country Data) when USGS database returns no data

**Why Borda?** Countries are naturally ranked by production volume. Borda voting aggregates ranked votes without iterative debate, producing top-N consensus efficiently.

**Borda Voting Formula:**
```
For top_n_proposed = 10:
  Rank 1 → 10 points
  Rank 2 → 9 points
  ...
  Rank 10 → 1 point
  
Total Borda Score = Sum of points across all agent votes
```

**How It Works:**

1. **Phase 1 - Expert Proposals**
   - Expert 1 (Mining expert): "China (1), Australia (2), Chile (3), ..."
   - Expert 2 (Mining expert): "China (1), Australia (2), Argentina (3), ..."
   - Expert 3 (Mining expert): "China (1), Russia (2), Chile (3), ..."

2. **Phase 2 - Borda Scoring**
   - China: 10+10+10 = 30 points (3 first-place votes)
   - Australia: 9+9+0 = 18 points (2 second-place votes)
   - Chile: 8+0+8 = 16 points (2 third-place votes)
   - Argentina: 0+8+0 = 8 points (1 third-place vote)
   - Russia: 0+0+9 = 9 points (1 second-place vote)

3. **Phase 3 - Confidence Aggregation**
   - Average confidence across proposals for each country
   - Average production amounts and percentages
   - Count how many experts voted for each country

4. **Phase 4 - Sort & Select**
   - Sort by Borda score descending
   - Return top 5 countries with:
     - Borda score
     - Number of votes (how many experts proposed it)
     - Average confidence
     - Average production data

**Example: Lithium Country Voting**

```
Expert Proposals:
  Expert 1: [China(1), Australia(2), Chile(3), Argentina(4), Canada(5), ...]
  Expert 2: [China(1), Australia(2), Chile(3), Brazil(4), Argentina(5), ...]
  Expert 3: [China(1), Russia(2), Australia(3), Chile(4), Argentina(5), ...]

Borda Scores:
  China: 10+10+10 = 30 (unanimous rank 1)
  Australia: 9+9+8 = 26 (3 votes, mostly high)
  Chile: 8+8+7 = 23 (3 votes, solid)
  Argentina: 7+7+6 = 20 (3 votes, lower tier)
  Canada: 6+0+0 = 6 (1 vote)
  Russia: 0+0+9 = 9 (1 vote)
  Brazil: 0+6+0 = 6 (1 vote)

Final Consensus (Top 5):
  1. China - 30 pts (3/3 votes, confidence 0.92)
  2. Australia - 26 pts (3/3 votes, confidence 0.91)
  3. Chile - 23 pts (3/3 votes, confidence 0.85)
  4. Argentina - 20 pts (3/3 votes, confidence 0.78)
  5. Russia - 9 pts (1/3 votes, confidence 0.72)
```

---

## Three-Tier Country Data Retrieval (Stage 3)

Stage 3 uses a sophisticated three-tier query hierarchy to reliably source country production 

### Query Order

1. **Memory Cache (~5ms)** - Fastest
   - Checks if query result already loaded in current session

2. **USGS Database (~100-500ms)** - Primary
   - Queries DuckDB database of Mineral Commodity Summaries
   - Returns real production data for tracked commodities
   - **Confidence: 0.95** (authoritative government data)
   - If hit → Cache and return immediately

3. **LLM Fallback Cache (~50-100ms)** - Prior Work
   - Checks for cached results from previous LLM debates
   - **TTL**: 30 days (long enough to amortize LLM cost)
   - **Confidence**: 0.80 (inherited from prior debate)
   - If hit → Return immediately without re-debating

4. **Fresh LLM Debate (~15-30 seconds)** - Expensive
   - Only runs if USGS and cache both miss
   - Uses Borda voting with 3 mining experts
   - Generates top 5 countries with confidence scores
   - Caches result for 30 days
   - **Confidence**: 0.75-0.80 (expert consensus)

**Code Flow:**
```python
async def get_country_data(material, year):
    # Tier 1: Memory cache
    if key in self.cache:
        return self.cache[key]
    
    # Tier 2: USGS database
    usgs_data = self.query_usgs(material, year)
    if usgs_
        usgs_data.confidence = 0.95
        self.cache[key] = usgs_data
        return usgs_data
    
    # Tier 3: LLM fallback cache
    cached_result = self.llm_cache.get(hs_code, material, year)
    if cached_result:
        self.cache[key] = cached_result
        return cached_result
    
    # Tier 4: Fresh LLM debate (expensive)
    llm_result = await self.run_lm_debate(material, year)
    self.llm_cache.set(hs_code, material, year, llm_result)
    self.cache[key] = llm_result
    return llm_result
```

### Confidence Score Semantics

| Source | Confidence | Meaning |
|--------|-----------|---------|
| USGS Database | 0.95 | Authoritative U.S. government data with global verification |
| LLM Cache Hit | 0.80 | Previously computed expert consensus, reused |
| LLM Debate (3 experts, Borda) | 0.75-0.80 | Fresh expert consensus; varies by agreement level |
| LLM Solo (no debate) | 0.60-0.75 | Single LLM estimate; highest uncertainty |

---

## Configuration model

Configuration in STDN Agentic lives in a JSON file (by default `config.json`) and is designed to be explicit but approachable so that both engineers and analysts can adjust the system without editing code.

### Minimal configuration

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:7b",
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "output_dir": "./output"
}
```

### Full configuration with debate options

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

### Key Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enable_llm_fallback_cache` | bool | true | Cache LLM debate results for 30 days |
| `llm_fallback_cache_ttl_hours` | int | 720 | Cache TTL in hours (720 = 30 days) |
| `save_transcripts` | bool | true | Save debate JSON/TXT transcripts |

**Note:** Debate settings are configured via environment variables (see below), not in config.json.

### Debate Environment Variables

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

### `.env` File Configuration

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

### Environment Variable Overrides

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

## Installation and prerequisites

The framework is designed to be straightforward to install on a typical Python development environment while supporting both local and remote LLM backends.

### Requirements

- **Python 3.10+**  
- **[uv](https://github.com/astral-sh/uv)** for fast dependency management  
- At least one LLM backend:
  - **Local:** [Ollama](https://ollama.com/) with models like `qwen2.5:7b`
  - **Remote:** OpenAI, Anthropic, or other hosted API

### Quick installation

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

### Environment setup

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

---

## Core pipeline stages

### Stage 1 – Component Extraction

The component extraction stage turns a high-level technology entry (such as "Solar Panel") into a list of major components that have their own supply chains, like solar cells, junction boxes, or aluminum frames.

**Single-agent mode:**
```bash
uv run stdn --input tech_list.csv --output output.csv
```

**Multi-agent debate mode:**
```bash
export ENABLE_COMPONENT_DEBATE=true
export MAX_DEBATE_ROUNDS=5
export CONVERGENCE_THRESHOLD=0.75
uv run stdn --input tech_list.csv --output output.csv
```

When debate is enabled:
1. Three agents with different perspectives independently propose components
2. Proposals are normalized using LLM semantic mapping
3. Jaccard convergence is calculated
4. Agents generate critiques highlighting consensus vs. isolated proposals
5. Process iterates until convergence ≥ threshold or max rounds reached
6. Final confidence scores are adjusted based on peer support

**Output columns:**
- `technology`: Input technology
- `technology_specification`: Standardized industry form
- `component`: Component name (normalized)
- `component_confidence`: Score 0.0-1.0
- `component_reasoning`: Justification for component and confidence

### Stage 2 – Materials Identification

Materials identification maps each component to the raw materials required for manufacturing.

**Single-agent mode:** Materials are extracted directly without debate.

**Multi-agent debate mode (optional):**
```bash
export ENABLE_MATERIAL_DEBATE=true
uv run stdn --input tech_list.csv --output output.csv
```

When debate is enabled for materials:
1. Three agents independently propose raw materials for each component
2. Material names are mapped to canonical forms using fuzzy ontology matching
3. Jaccard convergence is calculated per component
4. Similar debate, critique, and refinement rounds occur
5. Materials with low peer support may be downweighted or removed

**Key feature:** Material variant mapping automatically normalizes:
- "lithium-ion" → "Lithium"
- "stainless steel" → "Steel"
- Chemical symbols: "Li", "Co" → Full names

**Output columns:**
- `component`: Component name
- `material`: Raw material name (canonicalized)
- `material_confidence`: Score 0.0-1.0
- `material_reasoning`: Role and confidence justification

### Stage 3 – Country Production Data

Country production data uses a three-tier retrieval system with automatic fallback to LLM debate when primary sources unavailable.

**Data retrieval order:**
1. **Memory cache** - Previous queries in session
2. **USGS database** - Primary (0.95 confidence)
3. **LLM fallback cache** - Previous debate (0.80 confidence, 30-day TTL)
4. **Fresh LLM debate** - Borda voting (0.75-0.80 confidence)

**Enable multi-agent debate for LLM fallback:**
```bash
export ENABLE_COUNTRY_DEBATE=true
uv run stdn --input tech_list.csv --output output.csv
```

When Borda voting is used:
1. Three mining experts independently rank top 10 countries by production volume
2. Borda points are calculated for each country
3. Top 5 countries are selected by Borda score
4. Confidence and production data are averaged across experts
5. Result is cached for 30 days

**Output columns:**
- `material`: Raw material
- `country`: Top-producing country
- `meas_unit`: Unit of measurement (metric tons, etc.)
- `amount`: Production amount (numeric)
- `percentage`: Share of global production
- `country_confidence`: Score 0.0-1.0 (0.95 for USGS, 0.75-0.80 for LLM)
- `country_reasoning`: Data source and confidence justification

---

## Running the pipeline

### Basic execution

```bash
# Simple run (uses .env defaults)
uv run stdn

# With explicit config file
uv run stdn -i config.json
```

### Command-line arguments

The pipeline supports command-line arguments that override `.env` settings:

```bash
uv run stdn [OPTIONS]

Options:
  -i, --input-file FILE           JSON configuration file
  --enable-component-debate BOOL  Enable component debate (default: from .env)
  --enable-material-debate BOOL   Enable material debate (default: from .env)
  --enable-country-debate BOOL    Enable country voting (default: from .env)
  --num-agents-component N        Agents for component debate (default: 3)
  --num-agents-material N         Agents for material debate (default: 3)
  --num-agents-country N          Agents for country voting (default: 3)
  --max-debate-rounds N           Maximum debate rounds (default: 3)
  --convergence-threshold FLOAT   Convergence threshold (default: 0.8)
  --save-transcripts BOOL         Save debate transcripts (default: true)
```

**Examples:**

```bash
# Disable all debate (single agent mode) - fastest
uv run stdn --enable-component-debate false --enable-material-debate false --enable-country-debate false

# Enable component debate with 5 agents
uv run stdn --enable-component-debate true --num-agents-component 5

# Full debate with custom settings
uv run stdn --enable-component-debate true --enable-material-debate true --enable-country-debate true \
  --num-agents-component 5 --max-debate-rounds 5 --convergence-threshold 0.75
```

**Priority order:** CLI arguments > `.env` file > defaults

### Output files

The pipeline generates:
- **`stdns_output_{debate_config}_{timestamp}.csv`** - Main STDN output with all confidence scores and reasoning
- **`debate_transcripts/results/`** - JSON and TXT debate transcripts (if `save_transcripts=true`)
  - Example: `solar_panel_20260122_143022.txt`, `solar_panel_20260122_143022.json`

#### Output file naming convention

The CSV output filename encodes the debate configuration for each of the three phases (component, material, country):

**Format:** `stdns_output_{phase1}{phase2}{phase3}_{timestamp}.csv`

Where each phase code is:
- `d{n}` = debate enabled with n agents
- `v{n}` = voting/single-agent with n agents (v1 = single agent, no debate)

**Examples:**

| Filename | Meaning |
|----------|---------|
| `stdns_output_d3d3v3_20260127_143022.csv` | Debate (3 agents) for components, debate (3 agents) for materials, voting (3 agents) for country |
| `stdns_output_v1v1v1_20260127_143022.csv` | Single agent throughout (no debate) |
| `stdns_output_d3v1v3_20260127_143022.csv` | Debate (3 agents) for components, single agent for materials, voting (3 agents) for country |
| `stdns_output_d5d4v1_20260127_143022.csv` | Debate (5 agents) for components, debate (4 agents) for materials, single agent for country |

**Note:** The country phase always uses `v` (voting) rather than `d` (debate) because it uses Borda voting, not iterative debate.

#### Debate transcripts

Transcripts include:
- Round-by-round agent proposals
- Peer critiques and feedback
- Convergence scores for each round
- Final consensus and confidence adjustments
- Borda voting tallies (for country stage)

### Monitoring and debugging

**View real-time output:**
```bash
uv run stdn --input data/tech_list.csv --output results/output.csv 2>&1 | tee run.log
```

**Read debate transcripts:**
```bash
cat debate_transcripts/results/solar_panel_*.txt
# or examine detailed JSON:
cat debate_transcripts/results/solar_panel_*.json | jq '.'
```

**Check convergence metrics:**
```bash
# Extract from TXT transcript
grep -i "convergence" debate_transcripts/results/*.txt

# Extract from JSON
jq '.debate_history[].convergence_score' debate_transcripts/results/*.json
```

---

## Advanced topics

### Extending the agents

To add a new agent (e.g., a supply chain risk agent), create:

1. **New agent file** in `agents/`:
   ```python
   from pydantic import BaseModel
   from pydantic_ai import Agent
   
   class RiskAssessment(BaseModel):
       risk_category: str
       risk_score: float  # 0.0-1.0
       reasoning: str
   
   def get_risk_agent():
       return Agent(
           model="ollama:qwen2.5:7b",
           output_type=RiskAssessment,
           system_prompt="You are a supply chain risk expert..."
       )
   ```

2. **Register in factory** in `agents/factory.py`:
   ```python
   def create_risk_agent(self):
       return get_risk_agent()
   ```

3. **Add stage** in `orchestrator/pipeline.py`:
   ```python
   async def stage_4_risk_assessment(self, ...):
       # Implement debate logic or single-agent processing
       pass
   ```

### Customizing debate parameters

Modify `config.json` or environment variables:
- `max_debate_rounds`: Increase for more thorough convergence (default 5)
- `convergence_threshold`: Raise to require higher agreement (default 0.75)
- `debate_top_p`: Lower for more deterministic proposals (default 0.0001)
- `peer_support_boost`: Increase to reward consensus (default 0.15)

### Changing LLM backends

**Use OpenAI instead of Ollama:**
```json
{
  "model": "openai:gpt-4-turbo"
}
```

**Use Anthropic:**
```json
{
  "model": "anthropic:claude-3-sonnet"
}
```

The framework is model-agnostic; only the model name string needs to change.

---

## Design principles

1. **Explainability** - Every component, material, and country has a confidence score and reasoning
2. **Consensus-driven** - Multi-agent debate reduces LLM hallucinations through peer review
3. **Auditable** - Debate transcripts capture the full reasoning chain
4. **Efficient** - Multi-tier caching avoids redundant expensive LLM calls
5. **Modular** - Stages are independent; new stages can be added without modifying existing ones
6. **Type-safe** - Pydantic models enforce schema validation at every stage

---

## Troubleshooting

### No LLM output

**Issue:** Agent runs but returns empty results

**Solutions:**
- Verify LLM is running: `ollama list`, `ollama serve`
- Check model is pulled: `ollama pull qwen2.5:7b`
- Verify model endpoint: curl http://localhost:11434/api/tags
- Check `top_p` not too low (try 0.1 first, then lower for debate)

### Convergence never reached

**Issue:** Debate runs max rounds without reaching threshold

**Solutions:**
- Lower `convergence_threshold` (e.g., 0.65 instead of 0.75)
- Increase `max_debate_rounds` to allow more iterations
- Check if agents are diverse enough (may need different perspective prompts)
- Review debate transcript to see what proposals differ

### USGS database not found

**Issue:** "Database not found" error during Stage 3

**Solutions:**
- Verify path in `config.json`: `"usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db"`
- Check file exists: `ls -la ./data/world_mineral_commodity_reports_2022-2025_v8.db`
- If missing, download from official USGS source or use LLM fallback

### Memory issues with large batches

**Issue:** Out of memory error with many technologies

**Solutions:**
- Enable checkpointing: `"enable_checkpoints": true`
- Reduce batch size in config
- Process in smaller batches
- Increase available memory

---

## Performance characteristics

| Component | Time | Cost |
|-----------|------|------|
| Single technology (no debate) | 5-10 seconds | ~$0.01 |
| Single technology (full debate) | 30-60 seconds | ~$0.10 |
| 100 technologies (no debate) | 8-15 minutes | ~$1.00 |
| 100 technologies (full debate) | 30-60 minutes | ~$10.00 |

**Optimization notes:**
- First run of a material without USGS data costs ~$0.15 (3 LLM debate calls)
- Subsequent queries for same material within 30 days cost ~$0.005 (cache hit)
- Memory cache hits cost negligible (~milliseconds)
- USGS database hits cost ~$0 (no API calls, just database query)

---

## Citation and References

For research use, cite this system as:

```bibtex
@software{stdn_agentic_2025,
  title={STDN Agentic: Multi-Agent Framework for Technology Dependency Networks},
  author={Your Organization},
  year={2025},
  url={https://github.com/your-org/dpi_stdn_agentic}
}
```

---

## Contributing

To contribute, please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `uv run pytest`
5. Submit a pull request with a clear description

---

## License

[Specify your license here, e.g., MIT, Apache 2.0]
