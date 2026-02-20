# Shallow Technology Dependency Network (STDN) Agentic Framework
## Policy Brief: Multi-Agent System for Technology Supply Chain Analysis

**Prepared for:** U.S. Intelligence Community Leadership  
**Prepared by:** Biocomplexity Institute, University of Virginia  
**Date:** January 2026  
**Classification:** UNCLASSIFIED

---

## EXECUTIVE SUMMARY

The STDN Agentic Framework is a multi-agent AI system that produces **Shallow Technology Dependency Networks (STDNs)** by decomposing technologies into **components → materials → producing countries**. The system uses optional multi-agent debate for components and materials, and optional voting/consensus for country estimates only when the system falls back to LLM-based country data (enabled by default unless overridden via CLI or supported env vars). Outputs are structured (CSV/JSON) and configurable (JSON + CLI); auditability is strongest when transcripts are enabled, otherwise outputs provide structured records with provenance fields but without debate traces.

**Current Capability:** A repeatable four-stage pipeline with configurable debate, deterministic agreement feedback, semantic normalization for component naming, country data retrieval (memory cache → USGS database → LLM fallback cache → fresh LLM fallback, with voting/consensus when enabled), and post-processing normalization for cross-run consistency. The system provides confidence scores and provenance at each stage where applicable.

**Operational Status:** Functional prototype with robust documentation, config-first control, and parallel batch execution support. The framework requires operator-provided datasets (technology lists, materials ontology, USGS database) and supports multiple LLM backends (Ollama, OpenAI, Anthropic).

**Next Steps:** Expand authoritative data sources, benchmark accuracy against curated ground truth, and integrate into downstream risk assessment workflows.

---

## PROBLEM AND APPROACH

### Analytic Challenge

Supply chain dependency analysis requires coordinated reasoning across abstraction layers: components, raw materials, and producing countries. Manual approaches are slow, hard to audit, and difficult to scale across many technologies.

### Agentic Solution Design (Current Behavior)

STDN Agentic addresses this by structuring the analysis into four stages with optional multi-agent debate:

1. **Stage 1 – Component Extraction**  
   Multi-agent debate (Jaccard-based convergence). Component names are **semantically normalized** (LLM-based) to ensure convergence across variant naming.

2. **Stage 2 – Materials Mapping**  
   Per-component materials identification with optional debate. Material names are **rule-normalized** and matched against a controlled ontology.

3. **Stage 3 – Country Data**  
   Authoritative retrieval from USGS where possible. If missing, a **Borda-voting LLM fallback** is used, with caching and confidence annotations.

4. **Stage 4 – Post-Processing Normalization & Outputs**  
   Batch normalization of component names across outputs and generation of normalized CSV/JSON artifacts for analysis.

### Deterministic Oversight and Auditability

- **System-generated agreement feedback** is deterministic (not LLM-based).  
- **Config-first behavior** ensures reproducibility: CLI flags override environment variables only where explicitly supported, and `config.json` remains the source of truth for core settings.  
- **Outputs** include confidence scores and data source attribution; debate transcripts are generated only when enabled.

---

## IMPLEMENTATION ARCHITECTURE (CURRENT)

The system is built around:

- **STDN Orchestrator:** end-to-end pipeline coordination  
- **Agents:** component, materials, and country agents with structured outputs  
- **Debate Orchestrators:** multi-round debate for components/materials; voting for countries  
- **Data Access:** USGS DuckDB queries and cached LLM fallback results  
- **Normalization:** LLM semantic normalization for components + batch normalization across runs  

All behavior is driven through a single CLI (`stdn`), with batch mode support (`stdn-parallel`).

---

## CURRENT CAPABILITIES

### Inputs

- Technology list (CSV)
- Materials ontology + HS-code listings
- USGS database (DuckDB)
- Optional LLM backends (local Ollama or hosted APIs)

### Outputs

- **Raw CSV**: output for each run  
- **Normalized CSV/JSON**: post-processed outputs  
- **Transcripts**: debate records (JSON + TXT) when enabled  

### Confidence and Provenance

Each stage includes confidence scores and provenance where applicable:
- **Stage 1/2:** peer support and debate convergence  
- **Stage 3:** data source (USGS vs LLM) and confidence weighting  
- **Stage 4:** normalization manifests and output provenance  

---

## LIMITATIONS AND RISKS (CURRENT)

- **Data Coverage:** USGS is authoritative but incomplete for some materials. LLM fallback fills gaps but introduces uncertainty.  
- **Ontology Constraints:** Material mapping depends on a curated ontology; coverage gaps require operator updates.  
- **Scalability:** Parallel runs are supported, but empirical benchmarking at large scale is ongoing.  
- **Model Dependence:** Output quality depends on LLM backend selection and prompt adherence.

---

## OPERATIONAL CAPABILITIES

### Configurability

- **Config-first** behavior with clear precedence:
  1. CLI flags (debate/voting)
  2. Environment variables (only explicitly supported toggles/overrides)
  3. `config.json` (core configuration)
- **Defaults (code-level):** component/material debate default to false; country voting defaults to true unless overridden by CLI or supported environment variable.

### Parallel Execution

- `stdn-parallel` supports batched runs for stability analysis.
- Post-processing normalization is run once per batch to avoid redundant work.

---

## PERFORMANCE & QUALITY CONTROLS

### Debate Convergence

- Convergence is tracked with Jaccard similarity.
- Debate ends when convergence exceeds a threshold or when max rounds are reached.
- Runtime and throughput are configuration- and model-dependent; the code does not enforce fixed performance guarantees.

### Validation

- Structured outputs validated with Pydantic schemas.
- Deterministic system feedback reduces variability.

---

## PLANNED ENHANCEMENTS

**Near-term**
- Expand authoritative data sources beyond USGS
- Improve ontology coverage and maintenance workflows
- Benchmark against curated ground-truth datasets

**Mid-term**
- Automated data refresh and taxonomy versioning
- Structured evaluation of model performance across domains

**Long-term**
- Scenario analysis and integration into risk models
- Temporal tracking of supply chain shifts

---

## CONCLUSION

The STDN Agentic Framework is a functional, configurable, and auditable system for supply chain dependency analysis. It balances automation with structured validation and offers a path toward scalable, repeatable analysis as data and model coverage improve.

**Recommendation:** Proceed with phased integration into analytic workflows, emphasizing validation against expert baselines and expanding authoritative data sources to reduce reliance on LLM fallback.