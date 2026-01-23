# Shallow Technology Dependency Network (STDN) Agentic Framework
## Dual-Use Technology Supply Chain Analysis and Intelligence Budget Estimation

## Policy Brief: Multi-Agent System for Technology Supply Chain Analysis

**Prepared for:** U.S. Intelligence Community Leadership  
**Prepared by:** Biocomplexity Institute, University of Virginia  
**Date:** January 2026  
**Classification:** UNCLASSIFIED

---

## EXECUTIVE SUMMARY

The STDN Agentic Framework is a multi-agent artificial intelligence system designed to systematically map technology supply chains at policy-relevant levels of granularity. Rather than treating supply-chain analysis as a one-time manual process, the framework decomposes complex technology networks into three analytical layers—components, materials, and producing countries—coordinated through LLM-powered agents that iteratively debate and refine their assessments. The system currently produces validated output on pilot technologies and is ready for integration with additional data sources and operational workflows.

**Current Capability:** The framework processes a technology specification through three sequential stages with built-in peer critique and confidence scoring. Outputs include structured dependency networks with confidence metrics, audit trails of reasoning, and multi-agent debate transcripts suitable for quality review and downstream analytical work. The system has been operationalized to process unclassified budget data for supply chain dependency extraction, with a completed pilot run analyzing 4,438 R-1 budget accounts across fiscal years 2020–2025.

**Operational Status:** Functional prototype with repeatable pipeline, configurable backends, and integrated checkpointing. Framework requires operator-provided datasets (technology lists, materials ontologies, USGS production databases) but handles parsing, validation, and schema enforcement internally. Initial application to DoD R&D budget exhibits demonstrates readiness for classified or unclassified structured data ingestion.

**Next Steps:** Expansion to additional budget exhibits (P-1 procurement, O-1 operations), validation of supply chain dependencies against contracting records and industrial reports, and integration into risk assessment workflows.

---

## PROBLEM AND APPROACH

### Analytic Challenge

Understanding dependencies in complex technology supply chains demands reasoning across multiple layers of abstraction: which components comprise a system, which raw materials go into those components, and which countries control the production of those materials. This analysis traditionally requires substantial domain expertise distributed across engineers, materials scientists, and trade specialists. Manual approaches are time-intensive, difficult to audit, and challenging to scale across multiple technologies or update periodically.

### Agentic Solution Design

The STDN framework addresses this challenge through structured multi-agent reasoning, and has been piloted on DoD R-1 Research, Development, Test & Evaluation (RDT&E) budget exhibits as an initial operational test case for the larger DDAS intelligence budget estimation system. R-1 was selected as the starting point because it offers high coverage of intelligence-related RDT&E, is consistently formatted across fiscal years, and is fully unclassified while still capturing a substantial fraction of intelligence-relevant activity.

1. **Decomposition:** Each analytical layer (components, materials, countries) is implemented as a separate processing stage with clearly defined Pydantic data schemas.

2. **Multi-Perspective Debate:** Rather than single-agent extraction, each stage optionally coordinates multiple agents with different analytical framings. For example, component extraction employs agents instructed to focus on procurable subassemblies, structural elements, and manufactured components respectively.

3. **Peer Critique:** Agents critique each other's proposals in subsequent rounds, with reasoning grounded in textual justifications. Proposals receiving support from multiple agents receive higher confidence scores.

4. **Deterministic State Management:** All agent outputs are validated against explicit schemas (Pydantic v2.5+), ensuring that outputs remain machine-parseable and suitable for database ingestion or downstream analytical systems.

### Implementation Architecture

The framework is built on Pydantic AI (0.0.14+) and consists of four principal components:

- **Orchestrator** (`STDNOrchestrator`): Manages pipeline state, iteration logic, checkpointing, and output serialization.
- **Agent Factory:** Provisions agents with configurable LLM backends (local Ollama, OpenAI, Anthropic).
- **Data Loaders:** Ingest technology lists (CSV), materials ontologies, and production databases (USGS mineral commodity reports via DuckDB).
- **Debate Coordinators:** Implement multi-round discussion, convergence detection, and consensus scoring.

All components are documented in source code and the project README and operate as a single CLI command (`stdn`) with JSON configuration.

---

## CURRENT STATE AND DEMONSTRATED CAPABILITIES

### Application to Intelligence Budget Estimation (R-1 Pilot)

Within the DDAS intelligence budget estimation system, the same agentic principles have been applied to R-1 DoD RDT&E exhibits to estimate the classified portion of U.S. intelligence spending. As of January 2026, the system has processed 4,438 R-1 budget accounts across fiscal years 2020–2025, reconciling observable line items against published National Intelligence Program (NIP) and Military Intelligence Program (MIP) toplines.

R-1 was selected as the initial data source for three reasons:

- **Coverage:** R-1 captures an estimated ~85% of total intelligence-related spending in RDT&E, providing a substantive but tractable subset of the broader intelligence budget for initial automation.
- **Structure:** R-1 exhibits share a consistent tabular format across years, with stable field names and program element (PE) numbering schemes. This allows automated parsing, validation, and deduplication to perform reliably.
- **Classification Posture:** R-1 is fully unclassified, enabling development, testing, and refinement of the agentic workflow without handling classified inputs.

For each fiscal year from 2020 to 2025, the system produces an estimate of the "black budget" residual by reconciling NIP+MIP toplines with identified R-1 intelligence-related accounts, adjusted for deduplication and reprogramming. The resulting residuals range from approximately $82B–$105B and account for 96–99% of the disclosed totals, indicating that most intelligence spending remains outside observable R-1 accounts and underscoring the need to integrate additional sources (P-1, O-1, contractor filings).

### What the System Does

**Input:** A technology specification (name, domain, intended role)  
**Process:** 

- **Stage 1 – Component Extraction:** Identifies major components and subassemblies through debate among three agents with distinct perspectives. Produces structured list with per-component confidence scores (0.0–1.0 range).
- **Stage 2 – Materials Mapping:** For each component, identifies constituent raw materials using materials ontology and optional multi-agent debate. Enforces consistency with predefined materials taxonomy and applies retry logic for edge cases.
- **Stage 3 – Country Production Data:** Queries USGS mineral commodity databases and applies statistical models to estimate which countries produce or control production of identified materials. Falls back to LLM inference where production data is sparse or recent.

**Output:** 

- Structured CSV with rows: Technology → Component → Material → Top Producing Countries (with confidence and reasoning).
- JSON and TXT debate transcripts showing agent proposals, peer critiques, and convergence metrics for quality review.
- Checkpoint files enabling resumption after failures or manual review.

### Validation and Audit Trail

All intermediate outputs are validated against explicit Pydantic schemas before writing to disk. The system records:

- Agent-generated text (proposals and reasoning)
- Confidence scores with peer-support weighting
- Round-by-round debate history with timestamp
- Data source attribution (USGS query results, ontology lookups)

This design allows subject-matter experts or automated validators to review reasoning and adjust confidence thresholds or dispute specific material-to-country mappings.

### Configuration and Extensibility

The system operates via JSON configuration file (`config.json`), which specifies:

- Input data paths (technology list, ontologies, production databases)
- LLM backend and model selection
- Pipeline parameters (debate rounds, convergence thresholds, top-N countries for reporting)
- Output directory and naming conventions

Configuration is decoupled from code, permitting rapid iteration on parameter tuning or data source swapping without redeployment.

---

## TECHNICAL MATURITY AND LIMITATIONS

### Production Readiness

**Strengths:**
- Fully automated end-to-end pipeline with error handling and recovery mechanisms
- Schema-based validation prevents garbage output
- Repeatable results across identical inputs
- Transparent reasoning captured in transcripts

**Current Constraints:**
- Pilot stage with small test technology datasets; scalability to 100+ technologies has not been operationally demonstrated
- Debate logic optimized for 3-agent consensus; effectiveness with larger agent pools unknown
- Materials ontology requires operator curation; automatically handling novel materials remains difficult
- Production country data relies on USGS commodity reports (2022–2025 vintage); gaps in emerging materials or sensitive technologies

### Known Data Gaps

The framework currently ingests USGS mineral commodity databases and materials-to-HS-code mappings. Coverage is strong for conventional materials (rare earths, cobalt, lithium) but limited for:

- Specialized semiconductors and integrated circuits (design-level dependencies)
- Proprietary component specifications (manufacturer-specific formulations)
- Real-time production allocation across countries (relies on historical annual data)
- Classified or restricted materials outside USGS scope

### LLM Backend Dependency

The system's output quality is contingent on the underlying LLM's ability to reason about supply chains. Current testing uses Qwen 2.5 (7B and 14B parameter variants via Ollama) and OpenAI models. Smaller models may miss subtle material dependencies; larger models incur latency or cost trade-offs. No formal benchmarking against ground-truth supply chains has been conducted.

---

## OPERATIONAL CAPABILITIES

### Current Capacity

- **Per-run throughput:** Processes 5–20 technologies per execution (depending on debate configuration and LLM latency)
- **Runtime:** Approximately 2–5 minutes per technology with debate enabled; seconds per technology without debate
- **Output formats:** CSV (normalized and queryable), JSON (machine-readable), TXT (human-readable transcripts)
- **Checkpoint frequency:** Configurable; default is every 5 technologies, enabling partial recovery

### Integration Points

The system reads from and writes to:

- **Input:** CSV technology lists, JSON materials ontologies, DuckDB databases
- **Output:** CSV dependency networks, JSON debate records, TXT summaries
- **Backends:** Local Ollama instances, OpenAI/Anthropic APIs, DuckDB for production data

All data flows are file-based or database-based, enabling integration with existing data pipelines or downstream analysis tools (dashboards, risk models, etc.).

---

## PERFORMANCE AND CONFIDENCE SCORING

### Debate Convergence

In multi-agent debate mode, the framework tracks overlap between agent proposals across rounds. Debate terminates when:

- Overlap exceeds configurable convergence threshold (default: 80%), or
- Maximum debate rounds reached (configurable; default: 10)

Components or materials supported by multiple agents receive confidence scores weighted by peer support. Isolated proposals from single agents receive lower scores. This mechanism reduces hallucination by prioritizing consensus.

### Confidence Metrics

All outputs include confidence scores on a 0.0–1.0 scale with textual justification. Scores reflect:

- Peer consensus (components/materials identified by multiple agents)
- Data source reliability (USGS production data vs. LLM inference)
- Material-to-country mapping confidence based on market share data

---

## PLANNED ENHANCEMENTS AND INTEGRATION PATHWAY

### Near-term (Q1–Q2 2026)

- **Data Source Integration:** Incorporate P-1 (Procurement) and O-1 (Operations & Maintenance) budget exhibits for validation and to identify undisclosed dependencies
- **Scalability Testing:** Run framework on portfolio of 50–200 technologies; identify bottlenecks
- **Benchmark Validation:** Compare STDN outputs against existing supply chain reports and subject-matter expert assessments

### Medium-term (Q3–Q4 2026)

- **Taxonomy Refinement:** Expand materials ontology and HS-code mappings based on pilot results
- **Automated Data Updates:** Implement quarterly USGS database refresh and materials taxonomy versioning
- **Dashboard Integration:** Develop visualization layer for dependency graphs and confidence metrics

### Long-term (2027+)

- **Temporal Dependency Tracking:** Model how supply chains shift with geopolitical events, sanctions, or technology transitions
- **Scenario Analysis:** Enable "what-if" modeling (e.g., disruption to a specific material, substitution pathways)
- **Integration with Risk Models:** Connect STDN outputs to quantitative supply chain risk assessment tools

---

## RESOURCE AND GOVERNANCE REQUIREMENTS

### Operational Needs

- **Computing:** Single workstation sufficient for current scale; parallelization possible with LangGraph multi-process coordination
- **Data:** USGS databases, materials ontologies, and technology specifications provided or curated by operator
- **LLM Backend:** Local Ollama (free, low latency) or hosted APIs (OpenAI, Anthropic) with associated costs

### Governance

- **Model Selection:** Framework accepts any LLM backend; operator selects based on latency, cost, and policy requirements
- **Output Review:** Debate transcripts are designed for human review; confidence thresholds can be adjusted post-run before downstream use
- **Data Classification:** System itself is unclassified; outputs inherit classification of input technologies

---

## CONCLUSION

The STDN Agentic Framework provides a systematic, auditable approach to technology supply chain analysis at a policy-relevant level of abstraction. It is suitable for integration into analytical workflows requiring repeatable, transparent dependency mapping. Current state is a functional prototype with known data gaps and bounded LLM scalability; the framework is ready for operational testing with expanded data sources and larger technology portfolios.

**Recommendation:** Proceed with phased integration, beginning with validation against existing supply chain assessments and expansion to larger technology datasets. Success metrics should include debate convergence rates, expert validation accuracy, and processing time scalability.