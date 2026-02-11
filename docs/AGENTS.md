# STDN Agent System

STDN Agentic uses specialized agents for the three pipeline stages (components, materials, countries) plus a factory helper for constructing agents. The agents can operate both independently (single-agent mode) and collaboratively (multi-agent debate/voting mode) to reach consensus on technology dependencies.

## Configuration Precedence (config-first)

1. **CLI flags** (highest precedence for debate/voting settings)
2. **Environment variables / `.env`** only for explicitly supported runtime toggles and overrides
3. **`config.json`** is the source of truth for core configuration (paths/models/output)

Environment variables do **not** automatically override all `config.json` fields—only settings explicitly read from the environment affect runtime behavior.

## Model configuration (current)

Models are configured primarily via `config.json`:
- `model`: default model identifier
- `component_model`, `materials_model`, `country_model`: per-agent overrides
- `component_normalization_model`: model used specifically for semantic component-name normalization mappings (recommended: `openai:gpt-4.1`)

During multi-agent component debate, semantic mapping/normalization is a schema-sensitive step. Using a more reliable model for normalization can reduce validation failures.

## Reliability / retries (current)

`pydantic_ai.Agent` defaults to low retry counts. STDN Agentic supports an explicit override:

- `STDN_AGENT_RETRIES` (env var): sets the retry count used when constructing agents (including output validation retries where configured).

This is especially important for structured outputs validated against Pydantic schemas.

## Agent Overview

| Agent | Stage | Purpose | Confidence | Collaboration Type |
|-------|-------|---------|-----------|--------------------|
| **Component Agent** | 1 | Extracts primary manufacturing components from technology descriptions | 0.85-0.95 | Debate with convergence (Jaccard-based) |
| **Materials Agent** | 2 | Identifies raw materials needed for each component | 0.70-0.90 | Debate with convergence (Jaccard-based) |
| **Country Agent** | 3 | Estimates top-producing countries for raw materials | 0.95 (USGS) → 0.75 (LLM) | Voting/consensus for LLM fallback (when USGS misses) |
| **Factory** | All | Creates and configures agent instances | — | — |

---

## Stage 1: Component Agent

**File:** `agents/component_agent.py`

**Purpose:** Transforms a high-level technology description into a list of primary manufacturing components with confidence scores.

### Key Features

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
   - **Multi-agent debate**: N agents with different perspectives, Jaccard convergence metric
     - **Round 1**: Independent proposals with full component generation
     - **Subsequent rounds**: Selection-based refinement from candidate list (agents cannot invent new components)
     - **Semantic normalization (schema-sensitive)**: near-duplicate names are mapped to canonical forms before convergence is computed
     - **Name preservation**: Fuzzy matching ensures component names stay consistent across rounds

### Input Schema

```
User query: "Extract components from smartphone"
Technology: smartphone
Role: personal computing device
Domain: consumer electronics
```

### Output Schema (ComponentList)

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

Notes:
- The system may also maintain intermediate fields (e.g., normalized names) during debate to compute convergence reliably.
- Semantic normalization mappings are driven by `component_normalization_model` (config-first), which is intentionally allowed to differ from `component_model`.

---

## Stage 2: Materials Agent

**File:** `agents/materials_agent.py`

**Purpose:** Maps each component to the raw materials required for manufacturing.

### Key Features

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

### Input Schema

```
Component: "Battery Pack"
Expected materials: [various, will be generated]
```

### Output Schema (ComponentMaterialsList)

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

---

## Stage 3: Country Agent

**File:** `agents/country_agent.py`

**Purpose:** Estimates top-producing countries for raw materials with production percentages.

### Key Features

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

### Input Schema

```
Material: "Lithium"
Year: 2024
Target: Top 5 producing countries
```

### Output Schema (CountryList)

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

## Three-Tier Country Data Retrieval

Stage 3 uses a sophisticated three-tier query hierarchy to reliably source country production data.

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

### Code Flow

```python
async def get_country_data(material, year):
    # Tier 1: Memory cache
    if key in self.cache:
        return self.cache[key]
```

## Parallel-run considerations (stdn-parallel)

When running batch experiments via the parallel launcher:

- Child runs commonly set `skip_postprocess_normalization=true` and `skip_json_output=true` so that normalization/JSON generation can be performed **once per batch** after consolidation.
- Raw outputs may use per-run collision-proof naming (e.g., include `_runN_`) during execution to avoid timestamp collisions, and are renamed back to standard naming after completion.
- For reproducibility, prefer configuring debate/voting via CLI flags (used by the launcher) rather than relying on environment defaults.


    # Tier 2: USGS database
    usgs_data = self.query_usgs(material, year)
    if usgs_data:
        usgs_data.confidence = 0.95
        self.cache[key] = usgs_data
        return usgs_data

    # Tier 3: LLM fallback cache
    cached_result = self.llm_cache.get(hs_code, material, year)
    if cached_result:
        self.cache[key] = cached_result
        return cached_result

    # Tier 4: Fresh LLM debate (expensive)
    llm_result = await self.run_llm_debate(material, year)
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
