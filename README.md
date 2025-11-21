# dpi_stdn_agentic

**Shallow Technology Dependency Network (STDN) Generation & Analysis**  
Multi-agent, LLM-driven, fully auditable, and reproducible supply network modeling.

***

## Table of Contents

- [Overview](#overview)
- [What Is a Shallow Technology Dependency Network?](#what-is-a-shallow-technology-dependency-network)
- [Key Features](#key-features)
- [Architecture & Debate Pipeline](#architecture--debate-pipeline)
- [Data Model](#data-model)
- [Pipeline Inputs & Outputs](#pipeline-inputs--outputs)
- [Configuration & Environment](#configuration--environment)
- [Usage](#usage)
- [Extensibility & Integration](#extensibility--integration)
- [Development Standards & Testing](#development-standards--testing)
- [FAQ](#faq)
- [Citations & Policy Use](#citations--policy-use)

***

## Overview

`dpi_stdn_agentic` generates highly explainable, single-layer ("shallow") technology dependency networks. It automates the extraction of:
- Key technology components,
- Their constituent raw materials,
- And the country-level distribution of those materials’ production or supply.

This is performed through orchestrated debate and consensus among multiple LLM agents—making all reasoning steps transparent and reproducible.

***

## What Is a Shallow Technology Dependency Network?

A **Shallow Technology Dependency Network (STDN)** encodes, for a target technology:
- **Primary components** (the most significant modules/assemblies needed for function or manufacture),
- **Raw materials** for each component (metals, minerals, chemicals, etc.),
- **The principal countries** producing or supplying those materials (quantified as percentage market share, tonnage, or HS code association).

Unlike fully recursive "deep" BOMs, STDNs focus on a single level of decomposition—ideal for policy intervention, FTA supply planning, and rapid supply risk assessment.

***

## Key Features

- **Multi-Agent LLM Debate:** Leverages independent LLM "personas" to propose, defend, and critique technology decompositions and material lists.
- **Consistent Ontology Enforcement:** Raw materials are cross-validated against industry/material ontologies; ambiguous matches spark additional debate rounds.
- **Country-Level Data Sourcing:** Uses USGS global mineral production stats as ground truth, with LLM fallback if ambiguities or gaps arise.
- **Transparent Audit Trail:** Every stage (component, material, country) produces a transcript—enabling forensic reconstruction of every decision.
- **Configurable & Reproducible:** Full decoupling of parameters (`config.json`), secrets (`.env`), and inputs/outputs; pipeline runs are precisely reproducible.

***

## Architecture & Debate Pipeline

Debate and consensus mechanisms are used at each key pipeline stage:

```
+--------------------+
| 1. Component Debate |
|  (Component Agents) |
+--------------------+
           |
           v
+---------------------+
| 2. Material Debate  |
|  (Materials Agents) |
+---------------------+
           |
           v
+---------------------+
| 3. Country Debate   |
|  (Country Agents)   |
+---------------------+
```

### Debate Process by Stage

#### 1. Component Selection Debate

```
[ Component Agents ]
      |         |          |
   +--+---------+----------+--+
   | Independent proposal rounds  |
   +-------------+---------------+
                 |
                 v
       +-----------------------+
       |   Component Debate    |
       | (LLM Agent Personas)  |
       +-----------------------+
                 |
        Consensus Components
```
- **Agents:** Multiple LLM-powered *Component Agents* with varied personas (specialist, generalist, risk analyst, etc.)
- **Inputs:** Technology CSV or database records (see `tech_list.csv`)
- **Outputs:** Consensus list of primary physical components

#### 2. Material Selection Debate

```
     [ Materials Agents ]
      |         |          |
   +--+---------+----------+--+
   | Independent material proposals |
   +-------------+---------------+
                 |
                 v
    +-----------------------------+
    |   Material Debate Process   |
    | (LLM Material Agents)       |
    +-----------------------------+
                 |
        Consensus Materials Set
```
- **Agents:** Multiple LLM-powered *Materials Agents* (ontology specialist, substitution analyst, etc.)
- **Inputs:** Consensus component set from above  
- **Outputs:** List of raw materials for each component with ontology/HS code validation

#### 3. Country Data Enrichment Debate

```
      [ Country Agents ]
       |        |        |
     +-+--------+--------+-+
     | USGS Query/LLM Estimate      |
     +--------------+--------------+
                    |
                    v
        +---------------------------+
        | Country Data Debate/Consensus|
        | (LLM Country Agents + DB validation) |
        +---------------------------+
                    |
                Final Country Data
```
- **Agents:** LLM-powered *Country Agents* (statistical analyst, policy reviewer, foreign trade specialist, etc.)
- **Inputs:** Material list per component  
- **Outputs:** For each material, country-wise stats (production, % global, HS code); USGS DB is queried first, LLM fallback used for unlisted materials.

***

## Data Model

This project ensures complete data integrity using [Pydantic](https://docs.pydantic.dev/) and standard Python dataclasses.  
*(See `src/stdn_agentic/models.py` for canonical definitions.)*

**Core model highlights:**
- `ComponentList` – list of extracted components per technology
- `ComponentMaterialsList` – mapping from each component to a set of materials
- `CountryList` – mapping from each material to country split (% and tonnage, optionally with HS code)
- `ConfigModel` – all pipeline configuration, paths, and operational controls
- `Debate*` structures – encapsulate agent IDs, proposals, critiques, and consensus history

***

## Pipeline Inputs & Outputs

### Inputs

- `config.json` – default pipeline settings, file paths, main model selection, static parameters
- `.env` – environment-specific tokens, keys, and override flags
- `data/tech_list.csv` – list of target technologies
- `data/hs_codes_and_usgs_names.csv` – mapping from ontology names ↔ HS codes/USGS records
- `data/world_mineral_commodity_reports_2022-2025_v8.db` – USGS DuckDB database of global mineral statistics

### Outputs

- `output/stdns_output.csv` / `output/stdns_output.json` – normalized STDN for all targets
- `src/stdn_agentic/debate_transcripts/results/` – per-run-full agent debate transcripts at every stage
- Log files, pipeline performance metrics

#### Example Output (CSV row)

| Technology | Component | Material | Country | Production | % Global | HS Code  |
|------------|-----------|----------|---------|------------|----------|----------|
| Smartphone | Battery   | Lithium  | China   | 78,000t    | 75.5     | 85076000 |

***

## Configuration & Environment

**Best Practice:**  
- **Static, version-controlled config:** `config.json` (model names, file paths, non-secret toggles)
- **Secrets and deployment specifics:**  `.env` (API keys, database URLs, fast-override flags only as needed)

| Type                        | File        | Example                        |
|-----------------------------|-------------|--------------------------------|
| Model/paths/static params   | config.json | model, top_n_countries, years  |
| API keys/endpoints          | .env        | OPENAI_API_KEY, OLLAMA_URL     |
| Per-deployment feature flag | .env        | ENABLE_DEBATE [optional]       |

Precedence: `.env` overrides only if explicitly checked for, and always document this logic.

***

## Usage

### 1. Prepare Data and Config  
- Fill out `data/tech_list.csv` with technologies to analyze.
- Customize `config.json` for your project (model name, years, paths, etc.)
- Copy `.env.example` to `.env` and set API keys if needed.

### 2. Run the Full Pipeline

```bash
uv run python src/stdn_agentic/main.py
```

### 3. Inspect Outputs

- See results in `output/`, and all debate transcripts in `src/stdn_agentic/debate_transcripts/results/`.

### 4. [Optional] Debug USGS DB

```bash
uv run python debug_duckdb.py
```

***

## Extensibility & Integration

- **Add new agent personas:** Extend/rewrite personalities in `src/stdn_agentic/agents/`.
- **Swap LLM providers:** Change `model` in `config.json`, or rewrite agent construction logic.
- **Ontology customization:** Edit mappings and allowable terms in `data/hs_codes_and_usgs_names.csv`.
- **Data enrichment:** Attach more granular USGS datasets or provide more detailed tech/country splits.
- **API integration:** Wrap `STDNOrchestrator` as a service endpoint for programmatic analysis.

***

## Development Standards & Testing

- **Code style:** Follows Ruff linter (`pyproject.toml` config), Black-compatible
- **Type safety:** All public functions and classes use complete type hints (enforced in CI)
- **Logging:** Standard structured logging instead of print
- **Testing:**  
  - Pytest-based suite in `src/stdn_agentic/tests/` (both unit and integration tests)
  - Test fixtures for I/O, agent composition, and fuzzy-matching/ontology logic
- **Documentation:** All public APIs, classes, and non-trivial internal logic require docstrings.

***

## FAQ

**Q: How is "shallow" different from a full BOM?**  
A: Shallow means only the primary dependency layer (components → materials → countries) is mapped, not a recursive full multi-level bill of materials.

**Q: Where does agent debate actually improve accuracy?**  
A: Multiple LLMs generate, defend, and critique answers, significantly decreasing systematic hallucinations or incomplete coverage. Transcripts provide auditable context for all agent choices.

**Q: How transparent/auditable is this pipeline?**  
A: Every debate, critique, and final consensus judgment is saved with agent IDs, prompts, proposals, and reasoning, making the pipeline suitable for audits, peer review, or explainable policy analysis.

**Q: Can I use this for custom technologies or materials?**  
A: Yes. Just update your tech list and, if needed, the ontologies and mappings. The pipeline is generalizable.
