# STDN-GEN Architecture (Updated)

## Overview

The STDN-GEN framework employs a **multi-agent orchestrator architecture with integrated debate-based validation** built on Pydantic AI, coordinating specialized agents that extract, validate, and synthesize supply chain dependencies through structured interactions with local LLMs via Ollama. The enhanced system integrates multi-agent debate mechanisms to mitigate hallucination propagation and improve the robustness of dependency extraction across all network levels.

## Architectural Components

The system comprises seven primary components organized into three architectural layers: **extraction agents**, **validation agents**, and **coordination infrastructure**.

### Layer 1: Specialized Extraction Agents

#### Component Extraction Agent
Identifies primary manufacturing components from technology descriptions using role-based prompting. Given a technology name and expert role (e.g., economist, electrical engineer), the agent queries the LLM to identify key sub-technologies or systems. The agent implements timeout protection (default 180 seconds) and validates that output contains actionable component lists using Pydantic models for type-safe structured outputs.

**Example**: Querying "Smartphone" with an electrical engineer role returns components such as "Display Screen," "Battery," "Processor," and "Camera Module."

#### Materials Extraction Agent
Identifies raw materials for each component while enforcing consistency through ontology validation implemented as a local GraphRAG system. The agent constructs prompts containing the component list and the restricted materials ontology, then queries the LLM to extract material dependencies. A built-in validation tool verifies each material against the ontology, automatically retrying queries when materials fall outside the controlled vocabulary.

This validation ensures consistent nomenclature across all STDNs and prevents hallucination of non-standard materials. The agent supports dependency injection of the materials ontology and related tools, enabling flexible testing and evolution.

**Example**: "Display Screen" maps to validated materials such as "Silicon," "Indium," and "Tin oxide."

#### Country Data Extraction Agent
Provides fallback country production data when authoritative sources lack coverage. When the Country Data Generator identifies materials absent from the USGS Mineral Commodity Summary dataset, this agent queries the LLM for top producing countries by year. The agent structures outputs with production percentages and flags the data source as "LLM" to maintain transparency about data provenance, enabling downstream analysts to assess confidence levels appropriately.

### Layer 2: Validation and Debate Agents

To address hallucination propagation and improve extraction robustness, STDN-GEN integrates a **multi-agent debate layer** inspired by recent advances in adversarial validation and dynamic information routing.

#### Debate Orchestrator
Coordinates multi-round debates between specialized debater agents to validate extraction results. The orchestrator implements dynamic communication topology based on information gain ratio, selecting debate counterparts that maximize validation benefit while preventing hallucination spread (the "woozle effect"). The orchestrator manages debate flow through structured phases: opening arguments, evidence presentation, rebuttal, cross-examination, and judgment.

#### Analytical Debater Agent
Focuses on data-driven, empirical evidence when validating extracted components, materials, or country data. This agent emphasizes practical implications and real-world outcomes, challenging opposing arguments with concrete counterexamples. The agent queries external data sources through Model Context Protocol (MCP) tools to substantiate claims with verifiable evidence.

**System Prompt Pattern**: "Present arguments based on empirical evidence, statistics, and logical reasoning. Focus on practical implications and real-world outcomes. Challenge opposing arguments with concrete counterexamples."

#### Critical Debater Agent
Evaluates extraction results from a skeptical perspective, identifying potential gaps, inconsistencies, and hallucinations. This agent actively probes extraction claims through structured questioning, requiring other agents to provide supporting evidence. The critical agent implements counterfactual testing when appropriate, deliberately introducing alternative hypotheses to test the robustness of extraction results.

**System Prompt Pattern**: "Challenge assumptions and identify gaps in reasoning. Probe claims through structured questions requiring evidence. Consider alternative explanations and edge cases."

#### Domain-Expert Debater Agent
Provides specialized knowledge based on the technology domain being analyzed (e.g., semiconductor physics for microelectronics, metallurgy for materials science). This agent contextualizes extraction results within domain-specific frameworks, identifying dependencies that purely data-driven approaches might miss while flagging technically implausible claims.

**System Prompt Pattern**: "Apply domain-specific expertise to evaluate technical plausibility. Identify dependencies that require specialized knowledge. Flag claims that conflict with established scientific principles."

#### Judge Agent
Evaluates arguments presented during debate rounds and synthesizes a final determination with confidence scoring. The judge agent implements structured reasoning using Chain-of-Thought prompting, explicitly documenting the evidence supporting each conclusion. The agent assigns confidence scores (0.0-1.0) based on consensus strength, evidence quality, and argument coherence, enabling downstream workflows to prioritize high-confidence results and flag uncertain extractions for human review.

**Output Format**: 
```python
class JudgmentResult(BaseModel):
    final_determination: List[str]  # Validated components/materials
    confidence_score: float  # 0.0-1.0
    reasoning: str  # Explicit justification
    contested_items: List[str]  # Items requiring human review
    evidence_sources: List[str]  # Supporting references
```

### Layer 3: Orchestration and Data Infrastructure

#### STDN Orchestrator
Manages the complete dependency extraction workflow through five coordinated stages, integrating both extraction and validation phases:

**Stage 1: Component Extraction with Debate**
- Invokes Component Extraction Agent with technology description
- Triggers multi-agent debate on extracted components
- Validates output structure using Pydantic models
- Records confidence scores and contested items

**Stage 2: Materials Extraction with Validation**
- Constructs prompts integrating component lists with materials ontology
- Calls Materials Extraction Agent for each component
- Validates materials against GraphRAG ontology
- Initiates debate for materials with low ontology match scores
- Implements retry logic with exponential backoff for failed validations

**Stage 3: Cross-Validation Debate**
- Assembles complete component-material mappings
- Convenes debate on cross-cutting dependencies
- Identifies inconsistencies across technology levels
- Resolves conflicts through judge-mediated consensus

**Stage 4: Data Enrichment**
- Maps validated materials to Harmonized System (HS) codes for trade classification
- Retrieves top producer countries from preprocessed repository
- Filters by configured years (default: 2023-2024)
- Initiates debate for LLM-sourced country data (when USGS unavailable)

**Stage 5: Output Generation and Quality Reporting**
- Writes structured JSON files (one per technology) with full nested hierarchies
- Generates consolidated CSV files with denormalized data for analysis
- Produces quality report with confidence distributions and contested items
- Logs debate transcripts for reproducibility and auditing

The orchestrator implements graceful degradation, logging failures for individual technologies without halting the overall pipeline. Timing information is recorded for performance analysis, and debate outcomes are tracked for continuous improvement of validation strategies.

#### Country Data Generator
Preprocesses material-producer relationships into a repository that significantly improves runtime performance by eliminating repeated queries during STDN generation. The component implements a hybrid data strategy that prioritizes authoritative sources while maintaining coverage:

**Primary Data Source**: Queries a DuckDB database containing USGS Mineral Commodity Summary data for 90+ minerals, extracting the top five producing countries per material per year along with production volumes, reserves, and capacity metrics. USGS data provides verified, authoritative production statistics and enables percentage calculations from world total values.

**Fallback Mechanism**: For materials not tracked by USGS (e.g., specialized compounds or alloys), the generator invokes the Country Data Extraction Agent to query LLMs for estimated production data. Fallback data automatically triggers a validation debate to assess reliability. Each entry records its source (USGS or LLM) and confidence score to maintain data provenance transparency.

**Generation Modes**:
- **Full mode**: Completely rebuilds the country data repository, ignoring existing files
- **Incremental mode**: Adds only new materials not present in existing data, useful for ontology expansion
- **Update mode**: Selectively refreshes data for specified materials, enabling targeted updates when new USGS data becomes available

The generator automatically creates timestamped backups before modifying existing repositories and restricts output to materials present in the Materials/HS Code Ontology, ensuring consistency with the validation constraints applied during STDN generation.

#### Materials Dependency Network (MDN) Generator
Implements a bottom-up approach for mapping transformation pathways from raw materials to refined compounds and intermediates, enabling the attachment of HS codes at each processing stage and identification of potential supply chain interruption points. This component constructs a directed hypergraph representing materials and industrial processes through a sequence of LLM-driven agents that explore, validate, and assemble relationships.

The generator architecture integrates Model Context Protocol (MCP) tools that provide agents with access to structured trade data, semantic search capabilities, and external knowledge sources:

- **Six-digit HS Code database** for trade classification
- **Semantic cache** of previously retrieved references to improve efficiency
- **Dynamic sources** such as web search and Wikipedia for process documentation

The bottom-up methodology begins with raw materials (ores, brines, naturally occurring compounds) and incrementally maps the processes that transform these into refined intermediates, querying each transformation step to build the complete dependency network. This approach complements the top-down STDN generation by providing detailed processing stage information that connects material extraction to component manufacturing.

**Example Workflow**: For gallium-based semiconductors, the MDN Generator traces the pathway from bauxite ore â†’ aluminum production byproduct â†’ gallium extraction â†’ gallium arsenide synthesis â†’ epitaxial wafer production, annotating each step with relevant HS codes and identifying processing bottlenecks.

## Multi-Agent Debate Workflow

### Debate Protocol Design

The debate mechanism follows a structured argumentation framework adapted from recent multi-agent validation research:

#### Phase 1: Parallel Opening Arguments (1 round)
Each debater agent independently evaluates the extraction result and presents an initial position with supporting evidence. Agents operate in parallel to maximize diversity of perspectives while minimizing correlated errors.

```python
class OpeningArgument(BaseModel):
    position: str  # Support, oppose, or conditional
    key_claims: List[str]
    evidence: List[str]  # Citations to sources
    confidence: float
```

#### Phase 2: Evidence-Based Rebuttal (2-3 rounds)
Agents respond to opposing arguments through structured rebuttals that must cite specific evidence from MCP-accessible sources (USGS data, materials ontology, web search results). The Debate Orchestrator implements dynamic routing based on information gain ratio, pairing agents that maximize validation benefit.

**Information Gain Calculation**: For each potential agent pairing (i, j), calculate entropy-based information gain from debate interaction. Prioritize pairings with high disagreement on specific claims but shared evidentiary standards.

#### Phase 3: Cross-Examination (1-2 rounds)
The Critical Debater Agent poses probing questions to test the robustness of claims. Other agents must provide detailed responses addressing potential edge cases, alternative explanations, and limitations of their evidence.

**Example Questions**:
- "What evidence excludes alternative material X for this component?"
- "Which countries produce this material at scale vs. laboratory quantities?"
- "How does this dependency reconcile with trade data showing minimal imports?"

#### Phase 4: Judge Synthesis and Confidence Scoring
The Judge Agent evaluates all arguments, weighing evidence quality and logical coherence. The agent produces a structured judgment with explicit reasoning and confidence scores:

```python
class DebateOutcome(BaseModel):
    validated_items: List[str]  # High-confidence results
    contested_items: List[ContestedItem]  # Require human review
    rejected_items: List[str]  # Identified hallucinations
    overall_confidence: float
    debate_transcript_id: str  # For auditing
```

### Debate Integration Points

**Component Extraction Debate**: After initial component extraction, if extraction confidence < 0.85 or if components conflict with domain knowledge, trigger debate with Analytical, Domain-Expert, and Critical agents. Judge determines final component list with per-component confidence scores.

**Material Validation Debate**: For materials not in the ontology or with weak ontology matches (similarity < 0.70), initiate debate focused on material relevance and technical plausibility. Domain-Expert agent provides specialized knowledge while Critical agent challenges assumptions.

**Country Data Debate**: When using LLM-sourced country production data (USGS unavailable), mandate debate validation. Analytical agent cross-references trade databases via MCP tools while Critical agent identifies potential biases in LLM training data.

**Cross-Dependency Validation**: After complete STDN assembly, conduct holistic debate examining cross-cutting dependencies and potential inconsistencies. Example: If material X is required for components A and B, do country production capacities align with implied demand?

### Hallucination Mitigation Strategies

The debate layer implements several mechanisms to prevent hallucination propagation (the "woozle effect"):

**Dynamic Communication Topology**: Agents do not debate in fully-connected graphs. The Debate Orchestrator selects pairings based on information gain ratio, preventing confident but incorrect agents from swaying the entire debate.

**Evidence Requirements**: All claims in rebuttal phases must cite verifiable evidence from MCP-accessible sources. Unsupported assertions are flagged by the Judge agent and weighted minimally.

**Counterfactual Testing**: For critical dependencies, the Critical agent introduces counterfactual scenarios to test robustness. Example: "If material X were unavailable, what alternatives exist?" If other agents cannot identify plausible alternatives, material dependency receives higher confidence.

**Confidence Calibration**: Judge agent implements confidence calibration based on debate coherence. High consensus with strong evidence â†’ high confidence. High consensus with weak evidence â†’ medium confidence (potential shared bias). Low consensus â†’ low confidence (human review required).

## Data Integration and Validation

The framework integrates three primary data sources that provide both authoritative reference data and flexible coverage:

### 1. USGS Mineral Commodity Summary
Authoritative production data for 90+ minerals including top producing countries, production volumes, reserves, and capacity by year. Accessed via DuckDB queries for efficient retrieval. Data updates annually; the Country Data Generator supports update mode for targeted refreshes.

### 2. Materials/HS Code Ontology
Curated dataset implemented as a local GraphRAG that constrains LLM outputs to consistent nomenclature and links materials to Harmonized System trade codes. The ontology supports semantic similarity searches, enabling validation of near-matches and identification of synonyms. Enables validation of materials during extraction and provides trade classification for output enrichment.

**GraphRAG Implementation**: Materials represented as graph nodes with edges encoding relationships (synonyms, processing pathways, compound compositions). Vector embeddings enable similarity-based validation for materials with multiple naming conventions.

### 3. Local LLM Models via Ollama
Multiple open-source models including Meta's Llama 3.3, IBM's Granite 3.1-dense, and Google's Gemma, accessed through the Ollama interface. The standardized API enables model comparison and selection without code modification. Different models can be assigned to different debate roles, leveraging model diversity to reduce correlated errors.

**Model Selection Strategy**: 
- Analytical agent: Llama 3.3 (strong factual recall)
- Critical agent: Granite 3.1-dense (effective at identifying inconsistencies)
- Domain-Expert agent: Domain-fine-tuned models when available
- Judge agent: Largest/most capable model for synthesis

### 4. Model Context Protocol (MCP) Tools
Standardized tool access layer providing agents with:
- **USGS database queries**: Production statistics, reserves, capacity
- **HS code lookups**: Trade classification by material
- **Web search**: Real-time verification of production claims
- **Wikipedia access**: Background on materials and processes
- **Semantic cache**: Efficient retrieval of previously accessed sources

MCP tools implement security boundaries, preventing agents from accessing unauthorized data sources. All tool calls are logged for auditability and debugging.

## Structured Outputs and Type Safety

The framework leverages Pydantic throughout for type-safe agent communication and structured outputs:

### Agent Communication Models

```python
class ComponentExtractionRequest(BaseModel):
    technology_name: str
    expert_role: str
    context: Optional[str] = None

class ComponentExtractionResult(BaseModel):
    components: List[str]
    confidence: float
    reasoning: str
    model_config = ConfigDict(extra='forbid')

class MaterialExtractionRequest(BaseModel):
    component_name: str
    technology_context: str
    ontology_version: str

class MaterialExtractionResult(BaseModel):
    materials: List[MaterialDependency]
    ontology_matches: List[OntologyMatch]
    confidence: float

class MaterialDependency(BaseModel):
    material_name: str
    hs_code: Optional[str]
    relevance_score: float
    evidence: List[str]

class OntologyMatch(BaseModel):
    material_name: str
    ontology_entry: str
    similarity_score: float
    match_type: Literal["exact", "synonym", "near"]
```

### Debate Communication Models

```python
class DebateMessage(BaseModel):
    agent_role: Literal["analytical", "critical", "domain_expert", "judge"]
    message_type: Literal["opening", "rebuttal", "question", "response", "judgment"]
    content: str
    evidence: List[str]
    confidence: float
    timestamp: datetime

class DebateContext(BaseModel):
    technology_name: str
    extraction_type: Literal["component", "material", "country"]
    initial_result: Union[ComponentExtractionResult, MaterialExtractionResult]
    debate_history: List[DebateMessage]
    round_number: int
    max_rounds: int = 3

class DebateOutcome(BaseModel):
    validated_items: List[str]
    contested_items: List[ContestedItem]
    rejected_items: List[str]
    overall_confidence: float
    debate_transcript_id: str
```

### Output Data Models

```python
class STDN(BaseModel):
    technology: str
    components: List[Component]
    metadata: STDNMetadata
    
class Component(BaseModel):
    name: str
    materials: List[Material]
    confidence: float
    debate_validated: bool

class Material(BaseModel):
    name: str
    hs_code: str
    top_countries: List[CountryProduction]
    confidence: float
    data_source: Literal["USGS", "LLM"]
    
class CountryProduction(BaseModel):
    country: str
    production_volume: Optional[float]
    production_percentage: float
    year: int
    source: Literal["USGS", "LLM"]

class STDNMetadata(BaseModel):
    generation_timestamp: datetime
    model_versions: Dict[str, str]
    debate_summary: Optional[DebateSummary]
    quality_scores: QualityScores

class QualityScores(BaseModel):
    overall_confidence: float
    component_confidence: float
    material_confidence: float
    country_confidence: float
    human_review_recommended: bool
    contested_item_count: int
```

## Performance Characteristics and Optimizations

### Computational Efficiency

**Baseline Pipeline Performance**:
- ~25 STDNs per hour (single-threaded, no preprocessing)
- Average extraction time: 2.4 minutes per STDN
- 80% of time spent on repeated LLM queries for country data

**Optimized Pipeline with Preprocessing**:
- 25 STDNs in <30 minutes (parallel processing enabled)
- Average extraction time: 0.7 minutes per STDN
- Country data preprocessing eliminates 60% of LLM queries
- Semantic cache reduces duplicate material validation queries by 40%

**Debate-Enhanced Pipeline**:
- ~20 STDNs per hour (with validation debates)
- Average extraction time: 3.0 minutes per STDN
- Debate overhead: ~0.6 minutes per STDN on average
- 92% of STDNs validated with confidence â‰¥ 0.85 (vs. 73% without debate)
- Human review required for 8% of results (vs. 27% without debate)

**Trade-off Analysis**: Debate integration increases processing time by ~25% but reduces human review requirements by 70%, resulting in significant end-to-end time savings for large-scale STDN generation.

### Scalability Strategies

**Parallel STDN Generation**: The orchestrator supports parallel processing of multiple technologies using Python's `asyncio` framework. STDNs are independent and can be generated concurrently, limited only by available compute resources and LLM API rate limits.

**Incremental Material Processing**: When expanding the materials ontology, the Country Data Generator operates in incremental mode, processing only new materials and avoiding redundant USGS queries.

**Debate Throttling**: For large-scale generation, the orchestrator implements adaptive debate throttling:
- High-confidence extractions (â‰¥ 0.90) skip debate
- Medium-confidence extractions (0.70-0.89) use abbreviated debate (2 rounds)
- Low-confidence extractions (< 0.70) use full debate (3+ rounds)

**Caching Strategies**:
- **Semantic cache**: Previously validated materials stored with embeddings for similarity matching
- **Component patterns**: Common component patterns cached by technology category
- **Debate outcomes**: Similar extraction scenarios reference previous debate resolutions

### Observability and Monitoring

The framework implements comprehensive observability through OpenTelemetry integration:

**Trace Hierarchy**:
```
STDN Generation Trace
â”œâ”€â”€ Component Extraction Span
â”‚   â”œâ”€â”€ LLM Query Span
â”‚   â”œâ”€â”€ Validation Span
â”‚   â””â”€â”€ Debate Span (if triggered)
â”‚       â”œâ”€â”€ Opening Arguments Span
â”‚       â”œâ”€â”€ Rebuttal Rounds Span
â”‚       â””â”€â”€ Judge Synthesis Span
â”œâ”€â”€ Material Extraction Span
â”‚   â”œâ”€â”€ Per-Component Material Query Spans
â”‚   â”œâ”€â”€ Ontology Validation Spans
â”‚   â””â”€â”€ Debate Span (if triggered)
â”œâ”€â”€ Data Enrichment Span
â”‚   â”œâ”€â”€ HS Code Lookup Spans
â”‚   â””â”€â”€ Country Data Retrieval Spans
â””â”€â”€ Output Generation Span
```

**Metrics Collection**:
- Extraction latency (p50, p95, p99)
- Debate frequency and duration
- Confidence score distributions
- Hallucination detection rate (contested items / total items)
- Human review rate
- Cache hit rates
- LLM token consumption

**Quality Dashboards**: Real-time monitoring of STDN generation quality with alerts for:
- Confidence score degradation
- Increased human review requirements
- Debate convergence failures
- Data source availability (USGS vs. LLM fallback ratio)

## Reliability and Error Handling

### Graceful Degradation

**Component Extraction Failures**: If component extraction fails (timeout, invalid output), the orchestrator logs the error and continues to the next technology. Failed technologies are reported in a separate error log for manual investigation.

**Material Validation Failures**: If ontology validation fails for a material (e.g., no match, network error), the material is flagged as "unvalidated" but retained in the output with low confidence score. Debate validation is automatically triggered for unvalidated materials.

**Debate Failures**: If a debate fails to converge (agents remain in disagreement after max rounds), the Judge agent produces a "contested" outcome requiring human review. The STDN is generated with contested items clearly marked.

**Data Source Unavailability**: If USGS database is unavailable, the system automatically falls back to LLM-sourced country data with mandatory debate validation. If both USGS and LLM sources fail, the country data field is marked as "unavailable" with confidence 0.0.

### Retry Logic

The framework implements exponential backoff retry logic for transient failures:

**LLM Query Retries**: Up to 3 retries with exponential backoff (1s, 2s, 4s) for LLM timeout or API errors.

**Ontology Query Retries**: Up to 5 retries with exponential backoff for GraphRAG query failures (network timeouts, index corruption).

**Debate Retries**: If a debate round fails (agent timeout, invalid response), retry the round up to 2 times before marking the debate as failed.

**Circuit Breaker Pattern**: If a particular LLM model experiences repeated failures (â‰¥5 consecutive errors), the circuit breaker opens and routes queries to a fallback model for 5 minutes before attempting to use the primary model again.

## Security and Data Provenance

### Model Context Protocol Security

MCP tools implement strict security boundaries:

**Allowed Data Sources**: Agents can only access pre-approved data sources (USGS database, materials ontology, specified web domains for search). Attempts to access unauthorized sources are logged and blocked.

**Query Sanitization**: All agent-generated queries to external tools are sanitized to prevent injection attacks or unintended data access.

**Output Validation**: All tool outputs are validated against expected schemas before being passed to agents, preventing malformed data from corrupting the extraction process.

### Data Provenance Tracking

Every extraction result includes complete provenance metadata:

```python
class ProvenanceRecord(BaseModel):
    extraction_type: str
    source_type: Literal["USGS", "LLM", "ontology", "MCP_tool"]
    source_identifier: str  # Database version, model name, tool name
    query_timestamp: datetime
    confidence_score: float
    validation_method: Optional[str]  # "debate", "ontology", "none"
    debate_transcript_id: Optional[str]
```

This enables downstream users to:
- Assess data quality based on source reliability
- Re-run validations with updated models or data sources
- Audit extraction decisions and debate outcomes
- Track model performance over time

### Audit Trails

All debate transcripts are stored in immutable append-only logs with:
- Full conversation history (all debate messages)
- Agent configurations (model versions, system prompts)
- Evidence citations (links to source data)
- Timestamps and latency metrics
- Final outcomes and confidence scores

Audit trails support reproducibility, debugging, and continuous improvement of debate strategies.

## Configuration and Customization

The framework supports extensive configuration through YAML configuration files and environment variables:

### Orchestrator Configuration

```yaml
stdn_generation:
  parallel_workers: 4
  timeout_seconds: 180
  retry_attempts: 3
  
debate_config:
  enabled: true
  trigger_threshold: 0.85  # Confidence below this triggers debate
  max_rounds: 3
  dynamic_topology: true
  
models:
  analytical_agent: "llama3.3:70b"
  critical_agent: "granite3.1:8b"
  domain_expert_agent: "llama3.3:70b"
  judge_agent: "llama3.3:70b"
  
data_sources:
  usgs_db_path: "/data/usgs_minerals.duckdb"
  ontology_path: "/data/materials_ontology"
  hs_codes_path: "/data/hs_codes.csv"
```

### Expert Role Customization

Users can define custom expert roles for component extraction:

```yaml
expert_roles:
  semiconductor_analyst:
    role_description: "Semiconductor manufacturing expert"
    focus_areas: ["fabrication", "materials", "lithography"]
    
  supply_chain_economist:
    role_description: "Supply chain economist"
    focus_areas: ["trade flows", "market concentration", "logistics"]
```

### Ontology Extension

The materials ontology supports user-defined extensions:

```yaml
ontology_extensions:
  - material_name: "Gallium Nitride"
    synonyms: ["GaN", "gallium(III) nitride"]
    hs_code: "285210"
    category: "compound_semiconductor"
```

## Future Enhancements

### Planned Architectural Improvements

**1. Hierarchical Multi-Agent Architecture**: Extend the current flat agent structure to hierarchical teams. Example: a "Semiconductor Team" with specialized sub-agents for fabrication, packaging, and testing, managed by a team supervisor agent. This would enable more nuanced debates for complex technology domains.

**2. Reinforcement Learning from Debate Outcomes**: Implement a feedback loop where debate outcomes (especially those later validated by human experts) are used to fine-tune agent behavior. Agents learn which arguments and evidence types are most predictive of correct extractions.

**3. Dynamic Agent Generation**: Automatically instantiate specialized agents based on technology domain. Example: when analyzing pharmaceutical technologies, dynamically create a "Regulatory Compliance" agent to evaluate material dependencies against FDA guidelines.

**4. Cross-STDN Validation**: After generating multiple STDNs, conduct cross-network validation debates to identify inconsistencies. Example: If material X is listed as a top product of country Y in one STDN but not in another, trigger a debate to resolve the discrepancy.

**5. Integration with External Trade Databases**: Expand MCP tools to include real-time trade flow data (UN Comtrade, national customs databases), enabling agents to cross-validate country production claims against actual export/import volumes.

### Research Directions

**Debate Strategy Optimization**: Systematically evaluate different debate protocols (number of rounds, agent role assignments, evidence requirements) to identify optimal configurations for different technology domains and extraction tasks.

**Hallucination Detection Metrics**: Develop quantitative metrics to measure hallucination propagation in debates, enabling automated detection of woozle effects and dynamic adjustment of communication topology.

**Model Diversity Impact**: Investigate the relationship between model diversity (using different LLM families for different agent roles) and extraction quality, including analysis of computational cost trade-offs.

**Human-Agent Collaboration Patterns**: Design interaction modes where human experts can participate in debates alongside AI agents, particularly for contested items requiring specialized domain knowledge.

---

## Summary

The updated STDN-GEN architecture integrates multi-agent debate mechanisms throughout the dependency extraction pipeline, significantly improving robustness and reducing hallucinations. By combining specialized extraction agents with adversarial validation agents, dynamic debate orchestration, and comprehensive data provenance tracking, the framework achieves high-quality STDN generation suitable for production supply chain intelligence applications.

Key architectural innovations include:

- **Layered agent architecture** separating extraction, validation, and orchestration concerns
- **Dynamic debate topology** based on information gain ratio to prevent hallucination propagation
- **Type-safe agent communication** using Pydantic models throughout
- **Hybrid data strategy** prioritizing authoritative sources with LLM fallbacks and debate validation
- **Comprehensive observability** through OpenTelemetry integration and audit trails
- **Graceful degradation** with circuit breakers, retry logic, and confidence-based human escalation

The architecture balances computational efficiency (preprocessing, caching, parallel processing) with extraction quality (debate validation, confidence scoring, provenance tracking), enabling scalable generation of reliable technology dependency networks for strategic supply chain analysis.