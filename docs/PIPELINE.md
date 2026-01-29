# STDN Pipeline Stages

This document describes the three-stage pipeline that transforms technology descriptions into Shallow Technology Dependency Networks (STDNs).

## High-Level Architecture

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
   Raw CSV output (output/raw/)
          ↓
 ┌─────────────────────────────────────────────────────────────────────┐
 │                    Post-Processing Normalization                    │
 ├─────────────────────────────────────────────────────────────────────┤
 │ • Batch component name normalization across all outputs             │
 │ • Canonical vocabulary lookup (cached mappings)                     │
 │ • LLM semantic normalization for unknown names                      │
 │ • Persistent vocabulary updates                                     │
 └─────────────────────────────────────────────────────────────────────┘
          ↓
   Normalized CSV output (output/normalized/) + debate transcripts
```

## Module Organization

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
  ├── normalization/
  │   ├── canonical_vocab.py     # Persistent JSON vocabulary for component name mappings
  │   └── models.py              # Data models for normalized components
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

---

## Stage 1: Component Extraction

The component extraction stage turns a high-level technology entry (such as "Solar Panel") into a list of major components that have their own supply chains, like solar cells, junction boxes, or aluminum frames.

### Single-Agent Mode

```bash
uv run stdn --input tech_list.csv --output output.csv
```

### Multi-Agent Debate Mode

```bash
export ENABLE_COMPONENT_DEBATE=true
export MAX_DEBATE_ROUNDS=5
export CONVERGENCE_THRESHOLD=0.75
uv run stdn --input tech_list.csv --output output.csv
```

### Debate Process

When debate is enabled:
1. Three agents with different perspectives independently propose components
2. Proposals are normalized using LLM semantic mapping
3. Jaccard convergence is calculated
4. Agents generate critiques highlighting consensus vs. isolated proposals
5. Process iterates until convergence ≥ threshold or max rounds reached
6. Final confidence scores are adjusted based on peer support

### Output Columns

- `technology`: Input technology
- `technology_specification`: Standardized industry form
- `component`: Component name (normalized)
- `component_confidence`: Score 0.0-1.0
- `component_reasoning`: Justification for component and confidence

---

## Stage 2: Materials Identification

Materials identification maps each component to the raw materials required for manufacturing.

### Single-Agent Mode

Materials are extracted directly without debate.

### Multi-Agent Debate Mode

```bash
export ENABLE_MATERIAL_DEBATE=true
uv run stdn --input tech_list.csv --output output.csv
```

### Debate Process

When debate is enabled for materials:
1. Three agents independently propose raw materials for each component
2. Material names are mapped to canonical forms using fuzzy ontology matching
3. Jaccard convergence is calculated per component
4. Similar debate, critique, and refinement rounds occur
5. Materials with low peer support may be downweighted or removed

### Material Variant Mapping

Material variant mapping automatically normalizes:
- "lithium-ion" → "Lithium"
- "stainless steel" → "Steel"
- Chemical symbols: "Li", "Co" → Full names

### Output Columns

- `component`: Component name
- `material`: Raw material name (canonicalized)
- `material_confidence`: Score 0.0-1.0
- `material_reasoning`: Role and confidence justification

---

## Stage 3: Country Production Data

Country production data uses a three-tier retrieval system with automatic fallback to LLM debate when primary sources unavailable.

### Data Retrieval Order

1. **Memory cache** - Previous queries in session
2. **USGS database** - Primary (0.95 confidence)
3. **LLM fallback cache** - Previous debate (0.80 confidence, 30-day TTL)
4. **Fresh LLM debate** - Borda voting (0.75-0.80 confidence)

### Enable Multi-Agent Debate for LLM Fallback

```bash
export ENABLE_COUNTRY_DEBATE=true
uv run stdn --input tech_list.csv --output output.csv
```

### Borda Voting Process

When Borda voting is used:
1. Three mining experts independently rank top 10 countries by production volume
2. Borda points are calculated for each country
3. Top 5 countries are selected by Borda score
4. Confidence and production data are averaged across experts
5. Result is cached for 30 days

### Output Columns

- `material`: Raw material
- `country`: Top-producing country
- `meas_unit`: Unit of measurement (metric tons, etc.)
- `amount`: Production amount (numeric)
- `percentage`: Share of global production
- `country_confidence`: Score 0.0-1.0 (0.95 for USGS, 0.75-0.80 for LLM)
- `country_reasoning`: Data source and confidence justification

---

## Post-Processing Normalization

After all technologies are processed and raw CSV files are written, a post-processing normalization step ensures consistent component naming across all outputs.

### Purpose

Different LLM runs may produce variations of the same component name:
- "Li-ion Battery", "Lithium Ion Battery", "Battery Pack (Li-ion)" → "Lithium-ion Battery"
- "LCD Panel", "LCD Display", "Liquid Crystal Display" → "LCD Display"
- "CPU", "Central Processing Unit", "Processor" → "CPU"

Post-processing normalization consolidates these variations to canonical forms for consistent analysis.

### Process

1. **Find matching outputs**: Locate all raw CSV files with the same debate configuration (e.g., all `d3d3v3_*.csv` files)
2. **Extract unique components**: Collect all unique component names across matching files
3. **Vocabulary lookup**: Check canonical vocabulary (`data/component_canonical_vocab.json`) for cached mappings
4. **LLM normalization**: Send unknown names to LLM for semantic mapping
5. **Update vocabulary**: Add new mappings to persistent vocabulary for future runs
6. **Write normalized output**: Create normalized CSV files in `output/normalized/`

### Canonical Vocabulary

The canonical vocabulary is a persistent JSON cache that reduces LLM calls:

```json
{
    "version": "1.0",
    "mappings": {
        "li-ion battery": "Lithium-ion Battery",
        "lcd panel": "LCD Display",
        "central processing unit": "CPU"
    },
    "metadata": {
        "created_at": "2026-01-28T12:00:00",
        "updated_at": "2026-01-28T12:00:00",
        "total_mappings": 42
    }
}
```

**Location**: `data/component_canonical_vocab.json`

### Normalization Rules

The normalization preserves material-relevant distinctions:

| Preserve | Examples |
|----------|----------|
| Battery chemistry | Lithium-ion vs Lead-acid vs NiMH vs LFP |
| Display technology | OLED vs LCD vs LED vs Mini-LED |
| Semiconductor type | Silicon vs GaN vs SiC |
| Memory type | DRAM vs NAND Flash vs NOR Flash |

Generic qualifiers are removed:
- "system", "module", "unit", "assembly", "component", "subsystem", "package"

### Output Directories

```
output/
├── raw/
│   ├── stdns_output_d3d3v3_20260128_120000.csv  ← Raw output (as extracted)
│   └── ...
├── normalized/
│   ├── stdns_output_d3d3v3_20260128_120000.csv  ← Normalized output
│   └── ...
└── stdns_output_*.json  ← JSON serialization
```

### Standalone Normalization Script

Normalization can also be run independently on existing output files:

```bash
# Normalize all raw output files
python scripts/normalize_outputs.py --pattern "output/raw/stdns_output_*.csv"

# Normalize specific config group
python scripts/normalize_outputs.py --pattern "output/raw/stdns_output_d3d3v3_*.csv"

# Dry run (preview changes)
python scripts/normalize_outputs.py --pattern "output/raw/*.csv" --dry-run

# Custom vocabulary path
python scripts/normalize_outputs.py --pattern "output/raw/*.csv" --vocab data/my_vocab.json
```

---

## Normalization Throughout the Pipeline

Normalization occurs at multiple stages to ensure consistency:

| Stage | What | When | How |
|-------|------|------|-----|
| **Component Extraction** | Component names | Before debate rounds | LLM semantic mapping of agent proposals |
| **Component Debate** | Component names | During each round | Proposals normalized before Jaccard calculation |
| **Materials Extraction** | Component + material names | During extraction | Rule-based normalization + variant mapping |
| **Materials Debate** | Component + material names | During each round | Rule-based normalization + ontology matching |
| **Post-Processing** | Component names | After CSV output | Batch LLM normalization across all outputs |

### Material Variant Mapping

Built-in mappings for common material variations:

```python
{
    "lithium ion": "lithium",
    "li-ion": "lithium",
    "rare earth elements": "rare earth",
    "ree": "rare earth",
    "stainless steel": "steel",
}
```

### Component Qualifier Removal

Generic qualifiers automatically stripped from component names:
- "system", "module", "unit", "assembly", "component", "subsystem", "package", "chipset"

Example: "Battery Management System Module" → "Battery Management System"

---

## Running the Pipeline

### Basic Execution

```bash
# Simple run (uses .env defaults)
uv run stdn

# With explicit config file
uv run stdn -i config.json
```

### Command-Line Arguments

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

### Examples

```bash
# Disable all debate (single agent mode) - fastest
uv run stdn --enable-component-debate false --enable-material-debate false --enable-country-debate false

# Enable component debate with 5 agents
uv run stdn --enable-component-debate true --num-agents-component 5

# High convergence threshold (more debate rounds)
uv run stdn --enable-component-debate true --convergence-threshold 0.9

# Full debate mode with all stages
export ENABLE_COMPONENT_DEBATE=true
export ENABLE_MATERIAL_DEBATE=true
export ENABLE_COUNTRY_DEBATE=true
uv run stdn
```

---

## Troubleshooting

### Pipeline Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Config file not found` | Missing `config.json` | Create config file or specify with `-i` |
| `USGS database not found` | Missing DuckDB file | Check `usgs_database` path in config |
| `Model not available` | Ollama not running | Start Ollama: `ollama serve` |
| `Rate limit exceeded` | Too many API calls | Reduce batch size or add delays |

### Debate Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Low convergence | Agents disagree | Increase `MAX_DEBATE_ROUNDS` |
| Too many rounds | High threshold | Lower `CONVERGENCE_THRESHOLD` |
| Inconsistent outputs | Model randomness | Lower `DEBATE_TOP_P` |
| Slow processing | Too many agents | Reduce `NUM_AGENTS_*` |

### Performance Optimization

- **Fastest**: Disable all debate (single-agent mode)
- **Balanced**: Enable debate only for components
- **Most accurate**: Enable debate for all stages with high convergence threshold
- **Memory**: Use `checkpoint_interval` for large batches
