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
- [STDN Calculations Reference](#stdn-calculations-reference)
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

## STDN Calculations Reference

This document describes all mathematical calculations used in the STDN (Supply Technology Dependency Network) agentic system.

### 1. Convergence Calculation

Convergence measures agreement between agents using **Jaccard similarity**, averaged across all agent pairs.

#### Formula

For $n$ agents:

$$
\text{Convergence} = \frac{2}{n(n-1)} \sum_{i=1}^{n-1} \sum_{j=i+1}^{n} \frac{|A_i \cap A_j|}{|A_i \cup A_j|}
$$

Where:
- $A_i$ = set of components/materials proposed by agent $i$
- $|A_i \cap A_j|$ = intersection (shared proposals between agents)
- $|A_i \cup A_j|$ = union (all unique proposals from both agents)

#### Example

With 3 agents and pairwise similarities of 0.50, 0.50, and 0.20:

$$
\text{Convergence} = \frac{0.50 + 0.50 + 0.20}{3} = 0.40 = 40\%
$$

#### Interpretation

| Range | Meaning |
|-------|---------|
| 0% - 30% | Low agreement, agents have very different proposals |
| 30% - 60% | Moderate agreement, some common components |
| 60% - 80% | High agreement, strong consensus forming |
| 80% - 100% | Very high agreement, agents mostly aligned |

---

### 2. Confidence Scoring

#### Vote-Weighted Confidence

Combines vote rate and average agent confidence:

$$
\text{Final Confidence} = (\text{Vote Rate} \times 0.6) + (\text{Avg Confidence} \times 0.4)
$$

Where:

$$
\text{Vote Rate} = \frac{\text{Supporting Agents}}{\text{Total Agents}}
$$

$$
\text{Avg Confidence} = \frac{\sum \text{Agent Confidences}}{\text{Supporting Agents}}
$$

#### Example

If 2 out of 3 agents support a material with average confidence 0.85:

$$
\text{Final} = (0.667 \times 0.6) + (0.85 \times 0.4) = 0.40 + 0.34 = 0.74
$$

---

### 3. Consensus Building Score

#### Adaptive Scoring with Peer Support

$$
\text{Score} = (1 - w_c) \times \text{Support Fraction} + w_c \times \text{Avg Confidence} + b \times (\text{Support} - 1)
$$

**Parameters:**
- $w_c$ = confidence weight (default: 0.3)
- $b$ = peer support boost (default: 0.15)
- Support Fraction = proportion of agents supporting the proposal

#### Example

If 3 agents support a component with average confidence 0.80:

$$
\text{Score} = (0.7 \times 1.0) + (0.3 \times 0.80) + (0.15 \times 2) = 0.7 + 0.24 + 0.30 = 1.24
$$

---

### 4. Adaptive Voting Threshold

The voting threshold adjusts based on convergence level to balance strictness and inclusiveness.

#### Formula

$$
\text{Threshold} = \begin{cases}
\frac{2}{3} & \text{if convergence} \geq 0.7 \text{ (strict)} \\[10pt]
\frac{1}{3} & \text{if convergence} \leq 0.2 \text{ (lenient)} \\[10pt]
\frac{1}{3} + \left(\frac{\text{convergence} - 0.2}{0.5}\right) \times \frac{1}{3} & \text{otherwise (interpolated)}
\end{cases}
$$

#### Example

At 45% convergence:

$$
\text{Threshold} = \frac{1}{3} + \left(\frac{0.45 - 0.2}{0.5}\right) \times \frac{1}{3} = 0.333 + (0.5 \times 0.333) = 0.50
$$

---

### 5. Country Production Normalization

When country production percentages don't sum to 100%, they are normalized:

$$
\text{Normalized}_i = \frac{\text{Percentage}_i}{\sum_{j=1}^{n} \text{Percentage}_j} \times 100
$$

---

### 6. Peer Support Calculation

Counts the number of unique agents proposing an equivalent normalized concept:

$$
\text{Support}(x) = |\{i : \text{Agent}_i \text{ proposes normalized}(x)\}|
$$

---

### Summary Table

| Calculation | Formula | Default Values | Purpose |
|-------------|---------|----------------|---------|
| **Convergence** | Jaccard similarity average | threshold = 0.51-0.8 | Measure agent agreement |
| **Final Confidence** | $0.6 \times \text{vote} + 0.4 \times \text{confidence}$ | — | Combine voting & confidence |
| **Consensus Score** | Support + confidence + boost | $w_c=0.3$, $b=0.15$ | Rank proposals |
| **Adaptive Threshold** | Linear interpolation | strict=0.67, lenient=0.33 | Adjust by convergence |
| **Normalization** | Percentage rescaling | sum to 100% | Ensure valid percentages |

---

### Confidence Scale Reference

All confidence scores in the system use a 0.0 to 1.0 scale:

- **0.9-1.0**: Absolutely certain, universal standard
- **0.8-0.9**: Very confident, industry standard
- **0.6-0.7**: Moderately confident, common but may vary
- **0.4-0.5**: Uncertain, depends on implementation
- **0.0-0.3**: Low confidence, rarely separate

---

### Typical Debate Convergence Pattern

A healthy multi-agent debate typically shows this pattern:

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
