# STDN Pipeline Stages

This document describes the four-stage pipeline that transforms technology descriptions into Shallow Technology Dependency Networks (STDNs), including post-processing normalization (Stage 4), and how to run it in **single-run** and **parallel batch** modes.

## Running: single vs parallel

### Single run (`stdn`)

`stdn` runs one pipeline end-to-end from a JSON configuration file:

```bash
uv run stdn -i config.json
```

You can override debate/voting per stage via CLI flags:

```bash
uv run stdn -i config.json \
  --enable-component-debate true \
  --enable-material-debate false \
  --enable-country-debate false \
  --num-agents-component 5 \
  --num-agents-material 1 \
  --num-agents-country 1
```

### Parallel batch runs (`stdn-parallel`)

`stdn-parallel` launches multiple pipeline runs in parallel for a given debate configuration:

```bash
uv run stdn-parallel --config-type d5v1v1 --num-runs 5 --base-config config.json --delay 5
```

Key behaviors in parallel mode:
- Each child run writes collision-proof raw outputs containing `_runN_` in the filename to avoid timestamp collisions.
- After all runs complete, raw outputs are renamed back to the standard naming (removing `_runN_`), then post-processing normalization and JSON generation are run once across the consolidated batch.
- Child runs typically set `skip_postprocess_normalization=true` and `skip_json_output=true` in their generated configs so post-processing is not redundantly executed per run.

## Normalization: two distinct steps (important)

STDN Agentic performs **two different kinds of normalization** that serve different purposes and happen at different times:

1. **In-debate semantic mapping (during Stage 1 debate)**
   - Purpose: improve debate convergence by mapping near-duplicate component names (e.g., “CPU” vs “Processor”) to canonical forms before computing similarity.
   - Timing: occurs *inside* the component debate loop (e.g., after Round 1 proposals and again before final consensus).
   - Model: uses the **component normalization model** (config-first), e.g. `component_normalization_model` in `config.json`.

2. **Post-processing batch normalization (after raw CSVs exist)**
   - Purpose: normalize component names **across output files** and produce normalized artifacts for analysis.
   - Timing: runs after raw outputs are written. In parallel batches, it is intentionally run **once** after all runs complete.
   - Behavior: uses canonical vocabulary lookup and an LLM mapping step for unknown names, writing normalized CSVs (and JSON) under `output/normalized/`.

These two steps are complementary:
- the in-debate semantic mapping helps the debate mechanism work reliably,
- the post-processing batch normalization makes outputs comparable and analysis-friendly across runs.

## High-Level Architecture

```text
CLI / stdn (single run) or stdn-parallel (batch launcher)
          ↓
   STDNOrchestrator (orchestrator/pipeline.py)
          ↓
 ┌──────────────────────┬──────────────────────┬──────────────────────┬────────────────────────┐
 │ Stage 1:             │ Stage 2:             │ Stage 3:             │ Stage 4:               │
 │ Component Extraction │ Materials Mapping    │ Country Data         │ Post-Processing Norm.  │
 ├──────────────────────┼──────────────────────┼──────────────────────┼────────────────────────┤
 │ • N debating agents  │ • N debating agents  │ • USGS Database      │ • Batch normalization  │
 │ • Jaccard-based      │ • Jaccard-based      │ • LLM fallback       │ • Canonical vocab      │
 │   convergence        │   convergence        │ • voting/consensus   │ • JSON output          │
 │ • Semantic name      │ • Rule-based +       │ • Caching            │                        │
 │   normalization      │   ontology matching  │                      │                        │
 │ • Confidence scoring │ • Confidence scoring │ • Confidence scoring │                        │
 └──────────────────────┴──────────────────────┴──────────────────────┴────────────────────────┘
          ↓
   Raw CSV output (output/raw/)
          ↓
 ┌─────────────────────────────────────────────────────────────────────┐
 │              Stage 4: Post-Processing Normalization                │
 ├─────────────────────────────────────────────────────────────────────┤
 │ • Batch component name normalization across a run group             │
 │ • Canonical vocabulary lookup (cached mappings)                     │
 │ • LLM semantic normalization for unknown names                      │
 │ • Persistent vocabulary updates + normalization manifests           │
 └─────────────────────────────────────────────────────────────────────┘
          ↓
   Normalized CSV output (output/normalized/) + JSON + debate transcripts
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

### Single-Agent Mode (no debate)

Single-agent mode is achieved by setting the debate flags to false (country voting defaults to true if unset) and using agent counts of 1:

```bash
uv run stdn -i config.json \
  --enable-component-debate false \
  --enable-material-debate false \
  --enable-country-debate false \
  --num-agents-component 1 \
  --num-agents-material 1 \
  --num-agents-country 1
```

### Multi-Agent Debate Mode

Enable debate for Stage 1 via CLI flags (recommended for reproducibility):

```bash
uv run stdn -i config.json \
  --enable-component-debate true \
  --num-agents-component 3 \
  --max-debate-rounds 5 \
  --convergence-threshold 0.75
```

### Debate Process

When debate is enabled:
1. **Round 1 (Initial Proposals)**: Three agents with different perspectives independently propose components
2. **LLM Normalization**: Proposals are normalized using LLM semantic normalization to map variations to canonical names
3. **Convergence Check**: Jaccard convergence is calculated across agent proposals
4. **System-Generated Agreement-Based Feedback**: The system generates agreement-based feedback highlighting:
   - CONSENSUS items (all agents agree)
   - MAJORITY items (2/3 agents agree)
   - ISOLATED items (only 1 agent proposed)
5. **Subsequent Rounds (Selection-Based)**: Agents are presented with a **candidate list** of all unique components from the previous round and must **SELECT** which to include (not propose new ones)
6. **Name Preservation**: A fuzzy matching function ensures LLM responses map back to original component names
7. **Iteration**: Process repeats until convergence ≥ threshold or max rounds reached
8. **Final Scoring**: Confidence scores are adjusted based on peer support levels

### LLM Semantic Normalization (config-driven model)

Component-name semantic normalization is used to map near-duplicates (e.g., “CPU” vs “Processor Chip”) to canonical names for convergence and downstream consistency.

The model used for semantic normalization is configurable:
- `component_normalization_model` in `config.json` (preferred; config-first)
- optional env override `STDN_COMPONENT_NORMALIZATION_MODEL` (only if explicitly used)

Using a more reliable model for normalization (e.g. `openai:gpt-4.1`) can substantially reduce schema validation failures during mapping.

### LLM Semantic Normalization

Component names are normalized by sending them to an LLM that understands semantic equivalence. This allows the system to recognize that different names refer to the same component:

- "Li-ion Battery", "Lithium Ion Battery Pack", "Battery (Lithium)" → "Lithium-ion Battery"
- "CPU", "Central Processing Unit", "Processor Chip" → "CPU"
- "LCD Panel", "Liquid Crystal Display" → "LCD Display"

The LLM maps all variations to a single canonical name, enabling accurate Jaccard similarity calculation even when agents use different terminology. Falls back to rule-based normalization (qualifier removal) if the LLM call fails.

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

Materials are extracted directly without debate when `--enable-material-debate false` (or the corresponding environment default is false).

### Multi-Agent Debate Mode

```bash
export ENABLE_MATERIAL_DEBATE=true
uv run stdn --input tech_list.csv --output output.csv
```

### Debate Process

When debate is enabled for materials:
1. Three agents independently propose raw materials for each component
2. Names are normalized using **rule-based normalization** and matched against the ontology
3. Jaccard convergence is calculated per component
4. Similar debate, System-Generated Agreement-Based Feedback, and refinement rounds occur
5. Materials with low peer support may be downweighted or removed

### Rule-Based Normalization

Unlike Stage 1's LLM-based approach, materials normalization uses deterministic string transformations:

1. **Qualifier removal**: Generic suffixes like "module", "system", "unit", "assembly" are stripped
   - "Battery Management System Module" → "Battery Management System"

2. **Variant mapping**: Hardcoded lookup table maps common variations:
   - "lithium-ion", "li-ion" → "lithium"
   - "rare earth elements", "ree" → "rare earth"
   - "stainless steel" → "steel"

3. **Ontology matching**: Material names are matched against a predefined list of valid materials from USGS commodity classifications

This approach is faster than LLM calls and sufficient for materials because the ontology provides a constrained vocabulary. Component names have more variation and require semantic understanding.

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

### Enable Voting/Consensus for LLM Fallback

Enable the country voting/consensus mode via CLI flags:

```bash
uv run stdn -i config.json \
  --enable-country-debate true \
  --num-agents-country 3
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
