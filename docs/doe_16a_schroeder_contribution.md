# Agentic AI for power grid scenario generation and cascading failure analysis

Aaron Schroeder, PhD, University of Virginia, Biocomplexity Institute

## Relevant experience

Over the past year we have built two agentic AI systems for analyzing complex dependency networks, both operational with published results. The architecture is structurally similar to what this proposal needs for power grids.

The STDN Agentic Framework (Schroeder et al., 2026) decomposes manufactured technologies into supply chain networks: components, materials, producing countries. It has generated networks for 180 technologies across microelectronics, pharmaceuticals, and biotechnology. Output quality comes from two sources we are actively quantifying: pipeline structure (ontology constraints, role-conditioned prompts, semantic normalization) accounts for the largest single improvement in precision and stability, while multi-agent debate (three agents proposing, critiquing, and converging through deterministic feedback) adds further verifiable gains validated against gold standards. Every dependency carries a confidence score and provenance label. Country data is sourced from the USGS Minerals Yearbook where available, with LLM consensus as fallback.

A second system (Schroeder et al., AAMAS 2025) does bottom-up discovery: starting from seed materials, six agents trace industrial transformation chains and represent them as directed hypergraphs. Agents call external tools (HS code databases, web search, reference caches) through the Model Context Protocol (MCP), and every discovered process must be backed by scored references.

## Application to the power grid problem

The proposal calls for an agentic framework coupling nonlinear power simulations, a digital twin, and scenario generation for cascading failure analysis. We have built this kind of multi-stage pipeline, and several things we learned carry over.

The STDN system wraps database queries, caching layers, and LLM agents into a pipeline that supports checkpointing and config-driven behavior. The same orchestrator pattern can wrap power flow solvers (PSS/E, PowerWorld, or the team's AC power flow codes) as tools that agents invoke, configure, and interpret results from. The MCP integration from the MEKH system already shows how to connect LLM agents to external computational tools through a standardized protocol, and we would apply this same approach to simulation codes.

The multi-agent debate protocol matters here because grid vulnerability assessment has something in common with supply chain analysis: wrong answers are costly, and a single model's perspective is not enough. Having multiple agents independently analyze a fault scenario, critique each other's cascade predictions, and converge through deterministic feedback has produced more reliable results than single-agent inference in our supply chain work. We expect the same pattern to hold for grid analysis, though it would need to be validated empirically.

For scenario generation, the STDN system already runs parallel batch execution (N independent pipeline instances with configuration variation), which maps naturally to Monte Carlo generation for grid scenarios: varying demand, fault locations, renewable penetration, attack vectors across ensemble runs. The checkpoint and caching architecture handles the bookkeeping.

We have also used the STDN pipeline's outputs to study cascading disruptions in trade networks. In related work (Vullikanti, Marathe, Schroeder et al., 2026), we built multiplex networks from UN Comtrade data for microelectronic precursor materials and modeled what happens when a supplier country is removed: how trade flows reroute through longer paths, where congestion builds on substitute routes, and which coalitions of countries can mitigate the disruption. The analytical structure is similar to what the DOE proposal needs for power grids: remove a node, trace how flows redistribute, identify where cascading failures propagate. We have already done this for trade networks and the methods transfer.

Both systems also track provenance carefully. Confidence scores, source labels, debate transcripts, everything an analyst needs to trace a recommendation back to the data and reasoning behind it. For grid work, this matters because utility operators and regulators will want to know why the system flagged a particular vulnerability, not just that it did.

## Proposed role

We would contribute the agentic architecture design and implementation for Topic 2. In practice, this means designing the orchestration pipeline that connects the digital twin from Topic 1 to the scenario generation and cascading failure analysis tools, implementing tool integration with existing power simulation codes, and adapting the multi-agent debate protocol for grid vulnerability assessment.
