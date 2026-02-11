# Research Plan: How Many Agents Do We Need?

## The Question

We're using multi-agent debate to extract technology components and materials, but we don't know the optimal number of agents. More agents means more cross-checking, but also more API costs and time. Where's the sweet spot?

## Approach

We'll run the pipeline with 2, 3, 4, and 5 agents in the component debate phase (keeping material/country at single-agent to isolate the effect). For each configuration, we'll do 5 parallel runs on a subset of 5-7 diverse technologies.

## What We'll Measure

**Quality (human-evaluated)**
- Have raters create gold-standard component lists before seeing any outputs
- Blind evaluation: raters score outputs without knowing which configuration produced them
- Calculate precision and recall against the gold standard

**Efficiency**
- Total API tokens consumed per run
- Wall-clock time per technology
- Cost per valid extracted item

**Convergence**
- Average rounds to reach consensus
- Initial vs final agreement percentages
- How many isolated proposals get filtered out

## What We Expect to Find

Costs will scale roughly linearly with agent count. Quality will likely improve from 2→3 agents, but we suspect diminishing returns beyond that. The goal is to find the configuration that maximizes quality-per-dollar.

## Output

A recommendation for the default agent count, backed by precision/recall numbers and cost analysis. If different phases benefit from different counts, we'll note that too.
