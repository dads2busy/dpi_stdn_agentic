# STDN Agentic Framework

A multi-agent AI framework for generating **Shallow Technology Dependency Networks (STDNs)** through iterative debate and consensus-building. The system extracts technology components, identifies raw materials, and enriches with global production data using LLM-powered agents and USGS databases.

***

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Pipeline Stages](#pipeline-stages)
  - [Stage 1: Component Extraction](#stage-1-component-extraction)
  - [Stage 2: Materials Identification](#stage-2-materials-identification)
  - [Stage 3: Country Production Data](#stage-3-country-production-data)
- [Multi-Agent Debate System](#multi-agent-debate-system)
- [Output Format](#output-format)
- [Configuration](#configuration)
- [Installation & Usage](#installation--usage)
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

## Configuration

### **config.json**

```json
{
  "model": "ollama/qwen2.5:14b",
  "usgs_database": "/path/to/usgs_production.db",
  "tech_list_path": "/path/to/technologies.csv",
  "output_dir": "./output",
  "output_csv_filename": "stdn_output",
  "src_year": 2024,
  "meas_year": 2025,
  "write_nulls_to_output": false
}
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `model` | LLM model identifier | "ollama/qwen2.5:14b" |
| `usgs_database` | Path to USGS SQLite database | (required) |
| `tech_list_path` | CSV with technology names and roles | (required) |
| `output_dir` | Output directory | "./output" |
| `output_csv_filename` | CSV filename (no extension) | "stdn_output" |
| `src_year` | USGS data source year | 2024 |
| `meas_year` | USGS measurement year | 2025 |
| `write_nulls_to_output` | Write rows even if no country data found | false |

### **technologies.csv**

```csv
technology,role,domain
Solar Panel,renewable energy consultant,technology
Electric Vehicle,automotive supply chain analyst,technology
Wind Turbine,energy systems engineer,technology
```

***

## Installation & Usage

### **Installation**

```bash
# Clone repository
git clone <repository_url>
cd stdn-agentic

# Install dependencies
pip install -e .

# Verify installation
python -c "from stdn_agentic import STDNOrchestrator; print('✓ Installed')"
```

### **Basic Usage**

```python
from stdn_agentic import STDNOrchestrator
from stdn_agentic.models import ConfigModel

# Load configuration
config = ConfigModel.from_json("config.json")

# Initialize orchestrator
orchestrator = STDNOrchestrator(
    config=config,
    enable_debate=True,              # Use multi-agent debate
    enable_material_debate=True,     # Debate for materials too
    enable_country_debate=False,     # Skip country debate (use USGS)
    max_debate_rounds=3,
    convergence_threshold=0.8,
    save_transcripts=True
)

# Run pipeline
import asyncio

async def main():
    technologies = ["Solar Panel", "Electric Vehicle"]
    results = await orchestrator.run_pipeline(
        technologies=technologies,
        role="supply chain analyst",
        domain="technology"
    )
    
    print(f"✓ Processed {results['successful']} technologies")
    print(f"✓ Output: {orchestrator.output_file}")

asyncio.run(main())
```

### **Command-Line Usage**

```bash
# Run full pipeline
python -m stdn_agentic.cli run --config config.json

# Single technology
python -m stdn_agentic.cli run --config config.json --tech "Solar Panel"

# Disable debate (faster, lower quality)
python -m stdn_agentic.cli run --config config.json --no-debate

# Custom parameters
python -m stdn_agentic.cli run \
    --config config.json \
    --max-rounds 5 \
    --convergence 0.9 \
    --no-transcripts
```

***

## Technical Details

### **Ontology Constraint Enforcement**

Materials are strictly validated against `hs_codes_and_usgs_names.csv`:

```python
# Before (incorrect LLM outputs):
"EVA"                           ❌ Not in ontology
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
- Country data: ~5 seconds (USGS lookups)
- **Total**: ~80 seconds

**Optimizations:**
- Use `enable_debate=False` for 3x speedup (lower quality)
- Reduce `max_debate_rounds` to 2 for faster convergence
- Increase `convergence_threshold` to 0.9 for earlier stopping

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

[Your License Here]

***

## Contact

For questions or contributions:
- **Email**: [your-email]
- **Issues**: [GitHub Issues URL]
- **Discussions**: [GitHub Discussions URL]
