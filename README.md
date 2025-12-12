# STDN Agentic Framework

The STDN Agentic framework is a multi-agent AI system for generating **Shallow Technology Dependency Networks (STDNs)** through iterative debate, critique, and consensus-building. Instead of treating technology supply-chain mapping as a one-off prompt, the framework decomposes the problem into explicit stages—component extraction, materials identification, and production profiling—each implemented as a set of cooperating agents with clear responsibilities. This README walks through the motivation, architecture, pipeline stages, multi-agent debate patterns, and usage so that both supply-chain analysts and multi-agent engineers can understand how the system works and how to extend it.

---

## Concept and objectives

Understanding global supply chains for complex technologies requires more than simply listing parts: it involves reasoning about components, raw materials, and which countries dominate production for those materials. Traditionally, this analysis requires substantial domain expertise and manual research across technical documentation and statistical yearbooks. STDN Agentic aims to automate a large portion of that reasoning by orchestrating LLM-powered agents that can propose, critique, and refine technology dependency networks in a structured and auditable way.

The framework focuses specifically on *shallow* technology dependency networks: graphs with a small number of layers that remain interpretable. Each STDN connects technologies → components → materials → producing countries, with confidence scores and reasoning attached at each step. This structure captures the most policy-relevant dependencies (such as concentration risk in particular materials or countries) while keeping outputs simple enough to review, debug, and use in downstream analyses and dashboards.

**Technical implementation:** The framework is packaged as `stdn-agentic` (see `pyproject.toml`) with a main entry point at `stdn_agentic.main:main` registered as the `stdn` console script. Core dependencies include `pydantic>=2.5.0` and `pydantic-ai>=0.0.14` for typed agent definitions, `pandas>=2.0.0` for CSV handling, `duckdb>=1.2.2` for production data queries, and `ollama>=0.3.0` for local LLM inference. Input technologies are read from CSV into Pydantic models representing technologies, components, and materials, with all agent outputs validated against explicit schemas defined in `src/stdn_agentic/core/schemas.py`.

---

## High-level architecture

At a high level, STDN Agentic is built around a central orchestrator that coordinates a three-stage pipeline and a set of agents that perform the domain reasoning. The orchestrator is responsible for loading configuration, iterating over input technologies, managing multi-agent debate rounds, handling checkpointing, and writing outputs. The agents are responsible for proposing components, mapping materials, and querying or approximating production data, each running on a configurable LLM backend such as Ollama or a hosted provider.

You can visualize the architecture as a shallow stack of layers:

```text
CLI / stdn command
          ↓
   STDN Orchestrator
 (pipeline + debate control)
          ↓
 ┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
 │ Stage 1: Component Agents │ Stage 2: Materials Agents │ Stage 3: Country Repo    │
 │  – Propose components     │  – Map components →       │  – Query USGS DB         │
 │  – Optional debate        │    ontology materials     │  – Optional LLM fallback │
 └───────────────────────────┴───────────────────────────┴───────────────────────────┘
          ↓
   CSV outputs + transcripts
```

**Module organization:** The codebase is structured as follows:

```text
src/stdn_agentic/
  ├── main.py                    # CLI entry point, config discovery, async orchestration
  ├── orchestrator.py            # STDNOrchestrator class coordinating all pipeline stages
  ├── models.py                  # ConfigModel and STDNDependencies Pydantic models
  ├── core/
  │   ├── schemas.py             # Shared debate schemas (ComponentProposal, DebateResult, etc.)
  │   ├── base_agent.py          # Abstract base class for all agents
  │   └── constants.py           # System-wide constants and default values
  ├── agents/
  │   ├── component_agent.py     # Component extraction agent (ComponentList schema)
  │   ├── materials_agent.py     # Material identification agent (MaterialsList schema)
  │   ├── country_agent.py       # Country production estimation agent
  │   └── factory.py             # Agent factory for creating configured agent instances
  ├── data/
  │   ├── loaders.py             # CSV and ontology loading utilities
  │   ├── repository.py          # MaterialsRepository for USGS data access
  │   ├── usgs_client.py         # DuckDB/SQLite client for production databases
  │   └── cache.py               # Material-country caching layer
  ├── debate/
  │   ├── component_debater.py   # Multi-agent debate for components
  │   ├── component_models.py    # Component debate Pydantic models
  │   ├── material_debater.py    # Multi-agent debate for materials
  │   ├── material_models.py     # Material debate Pydantic models
  │   ├── material_country_debater.py  # Optional country data debate
  │   └── *_normalization.py     # Text normalization for consensus matching
  └── utils.py                   # JSON loading, config validation, file I/O
```

This architecture keeps the technology dependency network shallow at both the data and code levels. The orchestrator sees stages as black boxes with typed inputs and outputs (Pydantic models), agents know only their own tools and schemas, and data-access components hide details of the USGS and ontology files. That separation allows you to change models, swap data backends, or extend debate strategies without rewriting the whole system.

---

## Installation and prerequisites

The framework is designed to be straightforward to install on a typical Python development environment while supporting both local and remote LLM backends. Installation consists of setting up Python, installing dependencies with `uv`, configuring a model backend (e.g., Ollama), and preparing configuration and input files. Once installed, the same setup can be used for quick single-agent runs or more thorough multi-agent debate runs.

### Requirements

- **Python 3.10+**  
- **[uv](https://github.com/astral-sh/uv)** for fast dependency management  
- At least one LLM backend:
  - **Local:** [Ollama](https://ollama.com/) with models like `qwen2.5:7b` or `qwen2.5:14b`
  - **Remote:** OpenAI or Anthropic, with appropriate API keys  

### Quick installation

```bash
# Clone the repository
git clone https://github.com/your-org/dpi_stdn_agentic.git
cd dpi_stdn_agentic

# Install dependencies (creates .venv, installs all packages)
uv sync

# Install with development tools (ruff, black, pytest, basedpyright)
uv sync --group dev

# (Optional) Install and start Ollama for local models
ollama serve
ollama pull qwen2.5:7b
```

**Technical details:** The `uv sync` command reads `pyproject.toml` and creates a virtual environment at `.venv/`, installing all dependencies listed under `[project.dependencies]` and optional `[dependency-groups]`. The main package is installed in editable mode, so changes to `src/stdn_agentic/` are immediately available. The `stdn` CLI script becomes available via `uv run stdn` or directly as `stdn` if you activate the virtual environment.

---

## Configuration model

Configuration in STDN Agentic lives in a JSON file (by default `config.json`) and is designed to be explicit but approachable so that both engineers and analysts can adjust the system without editing code. The configuration tells the orchestrator where to find technology inputs, which LLM model to use, where outputs should be written, and how USGS and ontology files are structured.

### Minimal configuration

```json
{
  "import_tech_list": "./data/tech_list.csv",
  "model": "ollama:qwen2.5:7b",
  "usgs_database": "./data/world_mineral_commodity_reports_2022-2025_v8.db",
  "output_dir": "./output"
}
```

### Full configuration with all options

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

**Technical implementation:** Configuration is loaded by `main.py` using a discovery mechanism that searches:
1. Explicit path via `-i` flag
2. `STDN_CONFIG` environment variable
3. Current directory: `config.json`, `.config.json`
4. User home: `~/.stdn/config.json`, `~/stdn/config.json`

Once found, JSON is parsed via `utils.read_json_to_dict()`, validated with `utils.validate_config()`, and instantiated as a `ConfigModel` Pydantic model (defined in `models.py`). This model provides type checking, defaults, and field validation. The `STDNOrchestrator` class accepts this `ConfigModel` instance and reads fields like `config.tech_list_path`, `config.model`, `config.usgs_database`, etc.

Environment variables can override behavior without changing JSON:
- `ENABLE_DEBATE=true` – enables component debate
- `ENABLE_MATERIAL_DEBATE=true` – enables materials debate
- `ENABLE_COUNTRY_DEBATE=true` – enables country data debate
- `MAX_DEBATE_ROUNDS=3` – maximum debate iterations
- `CONVERGENCE_THRESHOLD=0.8` – overlap threshold to stop debating
- `SAVE_TRANSCRIPTS=true` – write debate transcripts to disk
- `DEBATE_TOP_P=0.0001` – top-p sampling for debate agents

These are read in `main.py:process_all_technologies()` and passed to the `STDNOrchestrator` constructor.

---

## Core pipeline stages

The STDN pipeline is organized into three main stages that together build a shallow technology dependency network. Each stage takes a structured input, applies agentic reasoning (optionally with debate), and emits enriched records with confidence scores and justifications. The stages are intentionally simple to understand: components, materials, and production countries.

You can think about the pipeline as a layered diagram:

```text
Input technologies (CSV)
          ↓
Stage 1: Component Extraction
          ↓
Stage 2: Materials Identification
          ↓
Stage 3: Country Production Data
          ↓
 Combined STDN CSV + transcripts
```

Because the intermediate states are saved as structured data, you can inspect outputs after each stage—for example, verifying that components for a particular technology make sense—before using the final STDN CSV for downstream risk analysis or visualization.

### Stage 1 – Component extraction

The component extraction stage turns a high-level technology entry (such as "Solar Panel" with a role and domain) into a list of major components that have their own supply chains, like solar cells, junction boxes, or aluminum frames. Conceptually, this stage provides the first layer of the STDN, where complex technologies are decomposed into subassemblies that are both meaningful and tractable. It is designed to capture components that can plausibly be procured, manufactured, or constrained independently.

**Technical implementation:** The component agent is defined in `agents/component_agent.py` and uses Pydantic AI's `Agent` class. The agent is configured with:

- **System prompt:** `COMPONENT_SYSTEM_PROMPT` (detailed instructions on technology specification and component identification)
- **Result type:** `ComponentList`, a Pydantic model with fields:
  - `technology_specification: str` – standardized industry name
  - `technology_reasoning: str` – justification for specification
  - `component_list: List[ComponentWithConfidence]` – typed component proposals

Each `ComponentWithConfidence` has:
- `name: str` – component name
- `confidence: float` – 0.0–1.0 score
- `reasoning: str` – justification text

**Single-agent mode:** The orchestrator calls `await component_agent.run(user_prompt)` where `user_prompt` includes technology name, role, and domain. The LLM returns a structured `ComponentList` validated by Pydantic.

**Multi-agent debate mode:** When `ENABLE_DEBATE=true`, the orchestrator invokes `debate.component_debater.ComponentDebater`, which:
1. Creates 3 agent instances with different perspective prompts
2. Each agent independently proposes components (Round 0)
3. Computes overlap and generates critiques highlighting consensus vs. isolated proposals
4. Agents refine proposals based on critiques (Round 1, 2, …)
5. Stops when overlap ≥ `convergence_threshold` or `max_debate_rounds` reached
6. Merges proposals into consensus set, averaging confidence scores

Debate transcripts are saved to `src/stdn_agentic/debate_transcripts/results/` as JSON and TXT files with timestamps.

### Stage 2 – Materials identification

The materials identification stage maps each consensus component to its underlying raw materials—metals, minerals, or compounds—using a strict ontology derived from HS codes and USGS naming conventions. Conceptually, this stage answers the question "what specific substances does this component require?" while ensuring alignment with an authoritative vocabulary. It forms the second layer of the STDN by connecting components to materials in a controlled, auditable way.

**Technical implementation:** The materials agent is defined in `agents/materials_agent.py` with a system prompt that embeds the full materials ontology (loaded from `materials_hs_codes_listing` CSV, typically 650+ materials). The agent:

- **Input:** Component name, technology context, full ontology list
- **Output:** `MaterialsList` Pydantic model with:
  - `materials: List[MaterialWithConfidence]`
  - Each material has `name`, `confidence`, and `reasoning`

**Ontology enforcement:** After extraction, the orchestrator filters materials:

```python
ontology_set = set(load_materials_ontology())
for material in extracted_materials:
    if material.name not in ontology_set:
        logger.warning(f"Filtered '{material.name}' (not in ontology)")
        extracted_materials.remove(material)
```

This ensures all materials map to entries in the USGS database and HS code taxonomy.

**Multi-agent debate mode:** When `ENABLE_MATERIAL_DEBATE=true`, the `debate.material_debater.MaterialDebater` runs a similar process to component debate:
- 3 agents propose materials independently
- Agents critique alternatives (e.g., "2/3 agents said Aluminum, 1 said Steel—consolidate?")
- Convergence computed on normalized material names
- Final consensus merged from high-agreement proposals

All debate transcripts are saved with material-level reasoning chains.

### Stage 3 – Country production data

The country production data stage links materials to the countries that produce them, completing the shallow dependency network by adding geographic and quantitative context. Conceptually, this stage answers "who controls the supply of these materials?" and is the most directly relevant for geopolitical or risk analyses. It forms the third layer in the STDN by attaching production volumes and shares to each material.

**Technical implementation:** The country repository is implemented in `data/repository.py` as `MaterialsRepository`, which:

1. **Queries USGS database** (DuckDB or SQLite via `data/usgs_client.py`):
   ```python
   results = db.query(
       "SELECT country, amount, year FROM production WHERE material = ?",
       material_name
   )
   ```
   
2. **Calculates production shares:**
   ```python
   total_global = sum(row.amount for row in results)
   for row in results:
       row.percentage = (row.amount / total_global) * 100
   ```

3. **Returns top N countries** (default N=5) sorted by production volume, plus optional "OTHER" category

4. **Confidence scoring:**
   - USGS  `confidence = 0.95` (authoritative source)
   - LLM fallback: `confidence = 0.70–0.85` (estimated)

**LLM fallback:** When USGS data is missing, the system invokes `agents/country_agent.py` which uses a Pydantic AI agent to estimate production distribution based on:
- Industry reports
- Trade statistics
- Geographic factors (mineral deposits, refining capacity)

The agent returns a `CountryProductionList` Pydantic model with `countries: List[CountryProduction]`, each having:
- `country: str`
- `share_percentage: float`
- `confidence: float`
- `reasoning: str`

**Optional country debate:** With `ENABLE_COUNTRY_DEBATE=true`, the `debate.material_country_debater.MaterialCountryDebater` can run multi-agent consensus on production estimates, useful when USGS data is sparse or contested.

**Output:** Each technology-component-material-country tuple is written as a CSV row with columns:
```
technology, component, material, country, production_share, confidence, reasoning
```

---

## Multi-agent debate and convergence

Multi-agent debate is a core capability of STDN Agentic that improves robustness by having multiple agents collaborate and disagree before a final answer is chosen. Conceptually, debate simulates a small panel of experts who bring different perspectives to the problem, point out omissions, and converge on a consensus that reflects shared evidence rather than the quirks of a single model run.

**Debate architecture:** All debate functionality lives in `src/stdn_agentic/debate/` with separate debaters for each stage:

- `component_debater.py` – ComponentDebater for stage 1
- `material_debater.py` – MaterialDebater for stage 2
- `material_country_debater.py` – MaterialCountryDebater for stage 3 (optional)

**Debate flow:**

1. **Initialization:** Create N agents (default N=3) with different perspective prompts:
   ```python
   agents = [
       create_agent(perspective="procurable subassemblies"),
       create_agent(perspective="structural components"),
       create_agent(perspective="manufactured vs raw materials"),
   ]
   ```

2. **Proposal round (Round 0):** Each agent independently generates proposals:
   ```python
   proposals = []
   for agent in agents:
       result = await agent.run(prompt)
       proposals.append(ComponentProposal(
           agent_id=agent.id,
           components=result.component_list,
           confidence=result.confidence,
           reasoning=result.reasoning
       ))
   ```

3. **Convergence calculation:**
   ```python
   all_items = set(p.components for p in proposals)
   agreed_items = {item for item in all_items 
                   if sum(item in p.components for p in proposals) >= 2}
   overlap_score = len(agreed_items) / len(all_items)
   ```

4. **Critique generation:** For each item, classify as:
   - ✓ **Consensus** (3/3 agents agree)
   - ⚠ **Partial** (2/3 agents, with alternatives noted)
   - ❌ **Isolated** (1/3 agents, questioned)

5. **Refinement rounds:** Agents receive critiques and revise proposals:
   ```python
   for agent in agents:
       critique = build_critique(proposals, agent.id)
       refined = await agent.run(original_prompt + critique)
       proposals[agent.id] = refined
   ```

6. **Termination:** Stop when `overlap_score >= convergence_threshold` or `round_number >= max_debate_rounds`

7. **Consensus assembly:**
   ```python
   consensus = []
   for item in agreed_items:
       supporting_agents = [p for p in proposals if item in p.components]
       avg_confidence = mean(p.confidence for p in supporting_agents)
       merged_reasoning = " | ".join(p.reasoning for p in supporting_agents)
       consensus.append(ComponentWithConfidence(
           name=item,
           confidence=(len(supporting_agents) / N) * avg_confidence,
           reasoning=merged_reasoning
       ))
   ```

**Transcript format:** Debate transcripts are saved as structured JSON with schema:

```json
{
  "technology": "Solar Panel",
  "timestamp": "2025-12-11T14:32:15",
  "debate_config": {
    "max_rounds": 3,
    "convergence_threshold": 0.8,
    "num_agents": 3
  },
  "rounds": [
    {
      "round_number": 0,
      "proposals": [...],
      "overlap_score": 0.65
    },
    {
      "round_number": 1,
      "critiques": {...},
      "refined_proposals": [...],
      "overlap_score": 0.82
    }
  ],
  "final_consensus": [...]
}
```

**Performance tuning:** Debate can be computationally expensive. To optimize:
- Reduce `MAX_DEBATE_ROUNDS` (e.g., 2 instead of 3)
- Increase `CONVERGENCE_THRESHOLD` (e.g., 0.9 to terminate earlier)
- Use smaller models for debate (e.g., `qwen2.5:7b` instead of `14b`)
- Disable debate for materials/countries if component debate suffices

---

## Output formats and artifacts

The framework is designed to produce outputs that are both machine-friendly and human-auditable, reflecting its dual audience of data analysts and subject-matter experts. The primary artifact is a CSV file that lists, for each input technology, the derived components, materials, and producing countries, along with associated confidence scores and justification summaries.

### CSV output schema

**File:** `{output_dir}/{output_csv_filename}.csv` (default: `output/stdns_output.csv`)

**Columns:**
```csv
technology,technology_specification,technology_reasoning,component,component_confidence,component_reasoning,material,material_confidence,material_reasoning,country,production_share,country_confidence,country_reasoning
```

**Example row:**
```csv
Solar Panel,Monocrystalline silicon photovoltaic (PV) module,Represents 85% of global production...,Solar Cells,0.98,Core photovoltaic element universally present,Silicon,0.95,Primary semiconductor material,China,79.2,0.95,USGS 2024 data
```

**Writing logic:** The `STDNOrchestrator.run_pipeline()` method accumulates all technology-component-material-country tuples in memory, then writes them in a single batch:

```python
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=COLUMNS)
    writer.writeheader()
    for tech in technologies:
        for comp in tech.components:
            for mat in comp.materials:
                for country in mat.countries:
                    writer.writerow({
                        'technology': tech.name,
                        'component': comp.name,
                        'material': mat.name,
                        'country': country.name,
                        ...
                    })
```

### Debate transcripts

**Location:** `src/stdn_agentic/debate_transcripts/results/`

**Naming:** `{Technology}_{timestamp}.{json|txt}`

**Content:** Each transcript includes:
- Initial proposals from all agents
- Critique text for each round
- Refined proposals
- Convergence scores per round
- Final consensus with merged reasoning

**Text format example:**
```
=== STDN Component Debate Transcript ===
Technology: Solar Panel
Timestamp: 2025-12-11 14:32:15
Agents: 3
Max Rounds: 3
Convergence Threshold: 0.80

=== ROUND 0: Initial Proposals ===

Agent 1 (Procurable Subassemblies):
  - Solar Cells (monocrystalline silicon) [0.98]
  - Junction Box [0.92]
  ...

Agent 2 (Structural Components):
  - Solar Cells [0.95]
  - Aluminum Frame [0.90]
  ...

Overlap Score: 0.65 (below threshold)

=== ROUND 1: Critiques & Refinements ===

Critiques:
  ✓ CONSENSUS: Solar Cells (3/3 agents)
  ⚠ PARTIAL: Junction Box (2/3 agents) - Agent 2 omitted
  ...

Agent 1 Revised:
  ...
```

---

## CLI interface and basic usage

To make day-to-day use easy, STDN Agentic exposes a command-line interface that wraps the orchestrator with a simple `stdn` command. Conceptually, the CLI lets you think in terms of "run STDN on this configuration" rather than worrying about Python imports or module wiring.

### Basic commands

```bash
# Standard run using config.json in current directory
uv run stdn

# Specify config file explicitly
uv run stdn -i config.json
uv run stdn -i /path/to/custom_config.json

# Use environment variable for config path
export STDN_CONFIG=./config.json
uv run stdn
```

### Debate mode flags

**Component debate only (recommended starting point):**
```bash
ENABLE_DEBATE=true uv run stdn -i config.json
```

**Full multi-agent debate (highest quality, slower):**
```bash
ENABLE_DEBATE=true \
ENABLE_MATERIAL_DEBATE=true \
ENABLE_COUNTRY_DEBATE=true \
MAX_DEBATE_ROUNDS=3 \
CONVERGENCE_THRESHOLD=0.8 \
uv run stdn -i config.json
```

**Fast mode (single-agent, no debate):**
```bash
# No environment variables needed - this is the default
uv run stdn -i config.json
```

### Environment variables reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STDN_CONFIG` | str | (none) | Path to config file |
| `ENABLE_DEBATE` | bool | `false` | Enable component debate |
| `ENABLE_MATERIAL_DEBATE` | bool | `false` | Enable materials debate |
| `ENABLE_COUNTRY_DEBATE` | bool | `false` | Enable country data debate |
| `MAX_DEBATE_ROUNDS` | int | `3` | Maximum debate iterations |
| `CONVERGENCE_THRESHOLD` | float | `0.8` | Overlap threshold to stop |
| `SAVE_TRANSCRIPTS` | bool | `true` | Write debate transcripts |
| `DEBATE_TOP_P` | float | `0.0001` | Top-p sampling for debate |

**Technical flow:** When you run `uv run stdn`, the following happens:

1. `pyproject.toml` maps `stdn` → `stdn_agentic.main:main`
2. `main()` parses CLI args with `argparse` (accepts `-i` flag)
3. `find_config_file()` searches for config.json in priority order
4. `read_json_to_dict()` loads JSON, `validate_config()` checks required fields
5. `ConfigModel(**config_data)` instantiates Pydantic model with validation
6. `process_all_technologies()` is called with asyncio:
   - Reads environment variables for debate flags
   - Constructs `STDNOrchestrator` with config + debate settings
   - Loads technology CSV with `pandas` or `csv.DictReader`
   - Calls `await orchestrator.run_pipeline(technologies, ...)`
7. Orchestrator executes stages, saves CSV, returns stats
8. `main()` prints summary and returns exit code (0=success, 1=failure)

---

## Parallel and advanced execution modes

For larger technology lists or more demanding workflows, STDN Agentic supports advanced execution modes that can improve throughput or tailor behavior to specific use cases. Parallel processing can be enabled (subject to backend limits) so that multiple technologies are processed simultaneously, with the orchestrator coordinating parallel jobs and merging their outputs into a single CSV.

**Technical implementation:** The orchestrator uses `asyncio.gather()` to run multiple technology processing tasks concurrently:

```python
async def run_pipeline(self, technologies: List[str], ...) -> dict:
    tasks = [
        self.process_single_technology(tech, role, domain)
        for tech in technologies
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Merge results, handle failures, write CSV
```

**Concurrency limits:** Ollama and most LLM backends have concurrency limits (typically 1–4 simultaneous requests). To avoid overwhelming the backend:

```python
semaphore = asyncio.Semaphore(max_concurrent_jobs)
async with semaphore:
    result = await agent.run(prompt)
```

**Configuration:** Add to `config.json`:

```json
{
  "parallel_processing": true,
  "max_parallel_jobs": 3,
  "component_timeout": 180,
  "materials_timeout": 180,
  "country_timeout": 120
}
```

**Timeouts:** Each agent call is wrapped with `asyncio.wait_for()`:

```python
try:
    result = await asyncio.wait_for(
        agent.run(prompt),
        timeout=config.component_timeout
    )
except asyncio.TimeoutError:
    logger.error(f"Component extraction timed out for {tech}")
    # Fall back or skip
```

**Performance tuning tips:**

- **Reduce debate rounds:** `MAX_DEBATE_ROUNDS=2` instead of 3
- **Smaller models:** Use `qwen2.5:7b` for fast iterations, `14b` for final runs
- **Disable material/country debate:** Component debate alone often suffices
- **Checkpoint frequently:** `checkpoint_interval=5` to save progress every 5 technologies
- **Batch processing:** Split large tech lists into smaller files and run separately

---

## Project structure

The repository layout reflects the conceptual breakdown of the system into orchestration, agents, data access, and examples. This structure keeps the internal dependency graph shallow and makes it easier to navigate and extend.

```text
dpi_stdn_agentic/
├── src/
│   └── stdn_agentic/
│       ├── __init__.py
│       ├── main.py                # CLI entry point, config discovery
│       ├── orchestrator.py        # STDNOrchestrator pipeline coordinator
│       ├── models.py              # ConfigModel, STDNDependencies
│       ├── utils.py               # JSON/CSV utils, validation
│       ├── core/
│       │   ├── schemas.py         # Shared Pydantic models for debate
│       │   ├── base_agent.py      # Abstract agent base class
│       │   └── constants.py       # System constants
│       ├── agents/
│       │   ├── component_agent.py # Stage 1: Component extraction
│       │   ├── materials_agent.py # Stage 2: Materials mapping
│       │   ├── country_agent.py   # Stage 3: Country production
│       │   └── factory.py         # Agent factory pattern
│       ├── data/
│       │   ├── loaders.py         # CSV/ontology loading
│       │   ├── repository.py      # MaterialsRepository (USGS access)
│       │   ├── usgs_client.py     # DuckDB/SQLite client
│       │   └── cache.py           # Material-country caching
│       ├── debate/
│       │   ├── component_debater.py     # Component multi-agent debate
│       │   ├── component_models.py      # Component debate schemas
│       │   ├── component_normalization.py  # Text normalization
│       │   ├── material_debater.py      # Materials debate
│       │   ├── material_models.py       # Materials debate schemas
│       │   ├── material_normalization.py
│       │   ├── material_country_debater.py  # Country debate
│       │   └── material_country_models.py
│       └── debate_transcripts/
│           └── results/           # Saved debate JSON/TXT files
├── data/
│   ├── tech_list.csv              # Example technology inputs
│   ├── hs_codes_and_usgs_names.csv  # Materials ontology (650+ entries)
│   ├── world_mineral_commodity_reports_2022-2025_v8.db  # USGS production data
│   └── material_top_countries.json  # Pre-computed top producers
├── examples/
│   ├── PARALLEL_AGENTS_GUIDE.md   # Guide to parallel execution
│   └── sample_configs/            # Example configurations
├── output/
│   └── stdns_output.csv           # Generated STDN CSV
├── tests/
│   ├── unit/                      # Unit tests for agents, utils
│   ├── integration/               # Pipeline integration tests
│   └── fixtures/                  # Test data fixtures
├── .env                           # Environment variables (API keys, etc.)
├── config.json                    # Main configuration file
├── config_example.json            # Template configuration
├── pyproject.toml                 # Package metadata, dependencies
├── uv.lock                        # Locked dependency versions
└── README.md                      # This file
```

**Key design principles:**

- **agents/** – Each agent is self-contained with its system prompt and result schema
- **debate/** – Debate logic is separate from single-agent logic, making both modes testable independently
- **data/** – All data access (DB queries, CSV loads) is encapsulated, agents never write SQL
- **core/** – Shared schemas and base classes avoid circular imports
- **orchestrator.py** – Single orchestration module coordinates all stages, no cross-agent calls

---

## Testing and quality assurance

Because STDN Agentic is intended for analyses that may inform policy or strategic decisions, the project invests in testing and runtime quality checks. Automated tests range from unit tests that verify critical utilities (such as USGS queries and ontology filters) to integration tests that run the full pipeline on small sample technology lists.

### Running tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src/stdn_agentic --cov-report=html

# Run specific test file
uv run pytest tests/integration/test_pipeline.py

# Run unit tests only
uv run pytest tests/unit/

# Verbose output with logs
uv run pytest -v --log-cli-level=INFO
```

### Test organization

```text
tests/
├── unit/
│   ├── test_component_agent.py    # Agent schema validation, prompt handling
│   ├── test_materials_agent.py    # Ontology filtering, confidence scoring
│   ├── test_usgs_client.py        # Database queries, data normalization
│   ├── test_debate_convergence.py # Overlap calculation, consensus logic
│   └── test_utils.py              # JSON loading, config validation
├── integration/
│   ├── test_pipeline_single.py    # End-to-end single-agent run
│   ├── test_pipeline_debate.py    # End-to-end with debate enabled
│   └── test_usgs_integration.py   # Real database queries (requires fixture DB)
└── fixtures/
    ├── sample_tech_list.csv       # 5 test technologies
    ├── test_config.json           # Minimal test config
    ├── mock_ontology.csv          # Subset of materials for testing
    └── mock_usgs.db               # Small test database
```

### Test coverage goals

- **Agents:** ≥90% coverage on prompt handling, schema validation, error handling
- **Debate:** ≥85% coverage on convergence logic, critique generation, consensus merging
- **Data access:** ≥95% coverage on queries, caching, fallback logic
- **Orchestrator:** ≥80% coverage on stage coordination, checkpointing, CSV output

### Quality checks

**Linting and formatting:**
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

**Ruff configuration** (from `pyproject.toml`):
```toml
[tool.ruff]
target-version = "py310"
line-length = 100
select = ["E", "W", "F", "I", "C", "B"]  # pycodestyle, pyflakes, isort, comprehensions, bugbear
ignore = ["E501", "B008", "W191"]         # line length, function calls in defaults, tabs
exclude = [".git", "__pycache__", ".venv"]
```

**Runtime quality assurance:**

The system includes built-in QA through:

1. **Pydantic validation:** All agent outputs are type-checked at runtime
2. **Ontology enforcement:** Materials not in ontology are automatically filtered
3. **Confidence thresholds:** Low-confidence items can be flagged or excluded
4. **Debate transcripts:** Full reasoning chains preserved for auditing
5. **Logging:** Structured logs with timestamps, technology context, stage markers

**Example log output:**
```
2025-12-11 14:32:15 | INFO | orchestrator.py:45 | Processing technology: Solar Panel
2025-12-11 14:32:16 | INFO | component_agent.py:78 | Component extraction complete: 6 components
2025-12-11 14:32:17 | WARNING | materials_agent.py:92 | Filtered 'Steel' (not in ontology)
2025-12-11 14:32:18 | INFO | usgs_client.py:34 | USGS query for Silicon: 24 countries found
2025-12-11 14:32:18 | INFO | orchestrator.py:67 | Technology complete: Solar Panel (22 rows written)
```

---

## Extending and customizing the framework

STDN Agentic is designed as both a practical tool and a platform for research into multi-agent workflows and Shallow Technology Dependency Networks. Conceptually, you can treat each stage and agent as a modular building block that can be swapped, extended, or augmented to support new questions or domains.

### Common extension patterns

**1. Adding a new agent**

To add a "risk assessment" agent that scores concentration risk:

```python
# src/stdn_agentic/agents/risk_agent.py

from pydantic import BaseModel, Field
from pydantic_ai import Agent

class RiskScore(BaseModel):
    technology: str
    concentration_risk: float = Field(ge=0.0, le=1.0)
    reasoning: str

RISK_SYSTEM_PROMPT = """
You are a supply chain risk analyst. Given a technology's STDN,
calculate concentration risk based on:
- Material criticality
- Geographic concentration (HHI index)
- Substitutability
"""

risk_agent = Agent(
    'ollama:qwen2.5:14b',
    result_type=RiskScore,
    system_prompt=RISK_SYSTEM_PROMPT
)
```

Then integrate into orchestrator:

```python
# In orchestrator.py
async def assess_risk(self, stdn_data):
    result = await risk_agent.run(f"STDN: {stdn_data}")
    return result.data
```

**2. Adding a new data source**

To integrate trade data from UN Comtrade:

```python
# src/stdn_agentic/data/comtrade_client.py

class ComtradeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    async def get_trade_flows(self, material: str, year: int) -> List[TradeFlow]:
        # Query UN Comtrade API
        # Parse and return structured trade data
        pass
```

Use in country data stage:

```python
# In orchestrator.py or country_agent.py
comtrade = ComtradeClient(config.comtrade_api_key)
trade_data = await comtrade.get_trade_flows(material, year)
# Combine with USGS data or use as fallback
```

**3. Creating a new debate variant**

To add "weighted voting" where agents have different expertise levels:

```python
# src/stdn_agentic/debate/weighted_debater.py

class WeightedDebater:
    def __init__(self, agent_weights: Dict[str, float]):
        self.agent_weights = agent_weights
        
    def compute_consensus(self, proposals):
        weighted_items = {}
        for proposal in proposals:
            weight = self.agent_weights[proposal.agent_id]
            for item in proposal.components:
                weighted_items[item] = weighted_items.get(item, 0) + weight
        
        # Include items with weighted support > threshold
        consensus = [
            item for item, total_weight in weighted_items.items()
            if total_weight >= self.threshold
        ]
        return consensus
```

**4. Adding a visualization stage**

To generate network diagrams from STDN CSVs:

```python
# src/stdn_agentic/visualization/graph_builder.py

import networkx as nx
import matplotlib.pyplot as plt

def build_stdn_graph(csv_path: str) -> nx.DiGraph:
    G = nx.DiGraph()
    df = pd.read_csv(csv_path)
    
    for _, row in df.iterrows():
        G.add_edge(row['technology'], row['component'], layer='component')
        G.add_edge(row['component'], row['material'], layer='material')
        G.add_edge(row['material'], row['country'], 
                   weight=row['production_share'], layer='country')
    
    return G

def visualize_stdn(G: nx.DiGraph, output_path: str):
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_color='lightblue')
    plt.savefig(output_path)
```

**5. Implementing custom confidence aggregation**

To use Bayesian updating instead of simple averaging:

```python
# src/stdn_agentic/debate/bayesian_consensus.py

from scipy.stats import beta

def bayesian_confidence(agent_confidences: List[float], prior=(1, 1)):
    """Bayesian update from agent confidences."""
    alpha, beta_param = prior
    for conf in agent_confidences:
        # Treat confidence as probability of correctness
        alpha += conf
        beta_param += (1 - conf)
    
    # Posterior mean
    return alpha / (alpha + beta_param)
```

### Extension checklist

When adding new functionality:

- [ ] Define Pydantic models for inputs/outputs
- [ ] Write unit tests for new logic
- [ ] Add integration test covering end-to-end flow
- [ ] Update configuration schema if new settings needed
- [ ] Document new feature in examples/ or docs/
- [ ] Run linters (black, ruff) and type checker (basedpyright)
- [ ] Update this README with usage examples

---

## License and citation

This project is released under the **MIT License**. See `LICENSE` file for full terms.

When using STDN Agentic in research, policy analysis, or publications, please cite:

```bibtex
@software{stdn_agentic,
  title = {STDN Agentic Framework: Multi-Agent Shallow Technology Dependency Networks},
  author = {Your Organization},
  year = {2025},
  url = {https://github.com/your-org/dpi_stdn_agentic},
  version = {0.1.0}
}
```

### Acknowledgments

- Built with [Pydantic AI](https://ai.pydantic.dev/) for typed agent frameworks
- Production data from [USGS Mineral Commodity Summaries](https://www.usgs.gov/centers/national-minerals-information-center)
- Multi-agent debate inspired by research in ensemble LLM systems
- Special thanks to contributors and early adopters

---

## Additional resources

- **Architecture deep dive:** See `STDN-GEN Architecture (Updated).md` for detailed system design
- **Parallel execution guide:** See `examples/PARALLEL_AGENTS_GUIDE.md`
- **API documentation:** (Coming soon) Auto-generated docs from docstrings
- **Case studies:** (Coming soon) Example analyses of solar panels, EVs, semiconductors

---

**Questions or issues?** Open an issue on GitHub or contact the maintainers.
