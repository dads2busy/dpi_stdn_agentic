# Hybrid Model Routing — Planning Sketch

> **Status:** Planning sketch (not yet committed to execution). When ready to implement, use `superpowers:subagent-driven-development` or `superpowers:executing-plans` and convert the phases below into bite-sized TDD tasks. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the debate pipeline on cheap/local models by default (Ollama), and escalate to Anthropic only when local quality demonstrably falls short — minimizing API spend without sacrificing final output quality.

**Architecture:** Two layers of routing.
1. **Static per-stage routing** (zero code change): use existing `component_model` / `materials_model` / `country_model` / `process_consumables_model` / `component_normalization_model` fields in `ConfigModel` to assign cheap models to cheap stages and expensive models to high-value stages.
2. **Dynamic escalation** (new): wrap `pydantic_ai.Agent.run()` in an `EscalatingAgent` that calls a primary (cheap) model, evaluates a quality predicate against the result, and re-runs on a fallback (expensive) model when the predicate fails. Wire predicates into `ComponentExtractor`, `MaterialsExtractor`, and `MultiAgentDebater`.

**Tech Stack:** Python 3.10+, Pydantic AI (provider-agnostic via `"provider:model"` strings), Ollama (local), Anthropic API (fallback). No Claude Code / Claude Agent SDK — those don't fit the batch-debate workload (rate limits).

**Why not Claude Agent SDK / Max subscription:** Pydantic AI calls `api.anthropic.com` directly with `ANTHROPIC_API_KEY`. Max OAuth tokens are gated to Claude Code; using them would require rewriting the agent layer on top of `claude-agent-sdk`. Even then, Max's 5-hour rolling + weekly limits would throttle a debate-heavy batch (`d5v1v1` × full tech list × 4 stages = thousands of calls). Keep API billing for Anthropic-quality calls; minimize *which* calls reach Anthropic.

---

## File Structure

**Existing files (already support per-stage model assignment — no change needed for Phase 0):**

- `src/stdn_agentic/models.py:164-179` — `ConfigModel.component_model`, `materials_model`, `country_model`, `process_consumables_model` already exist.
- `src/stdn_agentic/models.py:48-90` — `STDNDependencies.get_*_model()` already routes per-stage.
- `src/stdn_agentic/agents/factory.py:106,127,148` — `AgentFactory.create_*_agent()` already reads the per-stage models.
- `src/stdn_agentic/agents/component_agent.py:230-237`, `materials_agent.py:572-579`, `country_agent.py:177-...` — already accept any `"provider:model"` string Pydantic AI understands.

**New file:**

- `src/stdn_agentic/agents/escalation.py` — `EscalatingAgent` wrapper.

**Files to modify:**

- `src/stdn_agentic/models.py` — add fallback-model and escalation-policy config fields.
- `src/stdn_agentic/agents/factory.py` — build `EscalatingAgent` when a fallback model is configured.
- `src/stdn_agentic/orchestrator/component_extractor.py` — invoke `EscalatingAgent` with `min_confidence` predicate.
- `src/stdn_agentic/orchestrator/materials_extractor.py` — same.
- `src/stdn_agentic/debate/component_debater.py` — call escalation when convergence stalls below threshold after `max_rounds // 2` rounds.
- `src/stdn_agentic/debate/material_debater.py` — same.
- `docs/CONFIGURATION.md` — document new config fields and escalation semantics.
- `config_*.json` (one new example) — `config_hybrid_example.json` showing recommended cheap/expensive split.

**Test files:**

- `src/stdn_agentic/tests/unit/agents/test_escalation.py` — unit tests for `EscalatingAgent` (mocked primary + fallback).
- `src/stdn_agentic/tests/integration/test_hybrid_routing.py` — integration test: low-confidence Ollama result triggers Anthropic fallback (use `pytest-mock` to stub Pydantic AI calls).

---

## Phase 0 — Static per-stage routing (zero code change)

**The cheapest win. Confirm this works before any code change.**

The existing config already supports a fully hybrid pipeline. Recommended split for `config_biotech_d3v1v1.json` / similar:

| Stage | Recommended model | Rationale |
|---|---|---|
| `component_model` | `ollama:qwen2.5:7b` | Many calls per tech (debate × N agents × M rounds). Ollama is free and fast. |
| `materials_model` | `ollama:qwen2.5:14b` (or 7b) | Same. Mostly recall over a fixed ontology. |
| `process_consumables_model` | `ollama:qwen2.5:7b` | Auxiliary stage, low-stakes. |
| `country_model` | `anthropic:claude-haiku-4-5-20251001` | Only invoked as USGS fallback. Few calls. Accuracy on geopolitical/production facts matters; Anthropic Haiku is cheap and strong here. |
| `component_normalization_model` | `anthropic:claude-haiku-4-5-20251001` | Runs once per pipeline. Cheapest per-run cost, biggest quality impact on final CSV. |

### Phase 0 tasks (when executing)

- [ ] Create `config_hybrid_example.json` — copy `config_biotech_d3v1v1.json`, set the five fields above.
- [ ] Run `uv run stdn -i config_hybrid_example.json` on a small tech list (3–5 techs).
- [ ] Diff the resulting normalized CSV against an existing Anthropic-only run. Spot-check: does the component/material vocabulary match? Are country lists similar?
- [ ] Document outcome in `docs/CONFIGURATION.md` under a new "Hybrid model routing" section.

**No code changes. No tests. Just configuration validation.** If Phase 0 quality is acceptable, skip Phase 1+.

---

## Phase 1 — `EscalatingAgent` wrapper

**Only proceed if Phase 0 shows quality gaps on specific stages.**

### File to create: `src/stdn_agentic/agents/escalation.py`

```python
"""
EscalatingAgent: try a cheap primary model, escalate to a fallback model
when a quality predicate rejects the primary result.

Design:
- Wraps two pydantic_ai.Agent instances with identical output types.
- Caller provides a predicate: (output) -> Optional[str].
  Return None to accept; return a string reason to escalate.
- Logs every escalation event to stdn_agentic.logging_config logger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, Optional, TypeVar

from pydantic_ai import Agent
from pydantic_ai.result import RunResult

from ..logging_config import get_logger
from ..models import STDNDependencies

logger = get_logger(__name__)

T = TypeVar("T")

Predicate = Callable[[T], Optional[str]]


@dataclass
class EscalationEvent:
    stage: str
    reason: str
    primary_model: str
    fallback_model: str
    technology: Optional[str] = None


class EscalatingAgent(Generic[T]):
    """Primary/fallback agent pair with predicate-driven escalation."""

    def __init__(
        self,
        stage: str,
        primary: Agent[STDNDependencies, T],
        fallback: Agent[STDNDependencies, T],
        accept: Predicate[T],
        on_escalate: Optional[Callable[[EscalationEvent], None]] = None,
    ) -> None:
        self.stage = stage
        self.primary = primary
        self.fallback = fallback
        self.accept = accept
        self.on_escalate = on_escalate

    async def run(
        self,
        prompt: str,
        *,
        deps: STDNDependencies,
        technology: Optional[str] = None,
    ) -> RunResult[T]:
        result = await self.primary.run(prompt, deps=deps)
        reject_reason = self.accept(result.output)
        if reject_reason is None:
            return result

        event = EscalationEvent(
            stage=self.stage,
            reason=reject_reason,
            primary_model=str(self.primary.model),
            fallback_model=str(self.fallback.model),
            technology=technology,
        )
        logger.warning(
            "[escalation] stage=%s tech=%s reason=%s primary=%s fallback=%s",
            event.stage,
            event.technology,
            event.reason,
            event.primary_model,
            event.fallback_model,
        )
        if self.on_escalate is not None:
            self.on_escalate(event)

        return await self.fallback.run(prompt, deps=deps)
```

### Phase 1 tasks (when executing — TDD)

- [ ] Write `tests/unit/agents/test_escalation.py`: mock primary returns a `ComponentList` with one component at `confidence=0.2`; predicate rejects anything below `0.5`; assert fallback is called and its output returned.
- [ ] Write second test: mock primary returns `confidence=0.9`; assert fallback is NOT called.
- [ ] Write third test: assert `on_escalate` callback receives an `EscalationEvent` with the correct `reason` string.
- [ ] Implement `escalation.py` as above. Run `pytest src/stdn_agentic/tests/unit/agents/test_escalation.py -v` until all three pass.
- [ ] Commit: `feat(agents): add EscalatingAgent wrapper`.

---

## Phase 2 — Config fields for escalation

### Modify: `src/stdn_agentic/models.py`

Add to `ConfigModel` (after the existing per-agent model block at line 179):

```python
# ========================================================================
# Escalation / Fallback Model Configuration
# ========================================================================

component_fallback_model: Optional[str] = Field(
    default=None,
    description=(
        "Fallback model invoked when primary component-extraction output fails "
        "the quality predicate (low confidence or stalled debate convergence). "
        "Set to None to disable escalation for this stage."
    ),
)
materials_fallback_model: Optional[str] = Field(
    default=None,
    description="Fallback model for materials extraction (escalation).",
)
country_fallback_model: Optional[str] = Field(
    default=None,
    description="Fallback model for country data (escalation).",
)

component_min_confidence: float = Field(
    default=0.5,
    ge=0.0,
    le=1.0,
    description=(
        "Minimum mean confidence on the primary component list. "
        "Output below this threshold triggers escalation to component_fallback_model."
    ),
)
material_min_confidence: float = Field(
    default=0.5,
    ge=0.0,
    le=1.0,
    description="Mean-confidence threshold for materials escalation.",
)
country_min_confidence: float = Field(
    default=0.5,
    ge=0.0,
    le=1.0,
    description="Mean-confidence threshold for country escalation.",
)
debate_stall_convergence_floor: float = Field(
    default=0.4,
    ge=0.0,
    le=1.0,
    description=(
        "If Jaccard convergence is below this value after max_rounds // 2 rounds, "
        "escalate the next round's agents to the fallback model."
    ),
)
```

Add matching fields to `STDNDependencies` (after line 64) and getter methods (after line 90):

```python
component_fallback_model: Optional[str] = None
materials_fallback_model: Optional[str] = None
country_fallback_model: Optional[str] = None

def get_component_fallback_model(self) -> Optional[str]:
    return self.component_fallback_model

def get_materials_fallback_model(self) -> Optional[str]:
    return self.materials_fallback_model

def get_country_fallback_model(self) -> Optional[str]:
    return self.country_fallback_model
```

### Phase 2 tasks

- [ ] Add fields and getters as shown above.
- [ ] Update `dependencies.py` (or wherever `STDNDependencies` is constructed from `ConfigModel`) to copy the new fields through.
- [ ] Add unit test: `ConfigModel(**{...full_valid_dict})` accepts the new fields, defaults applied when absent.
- [ ] Run `pytest src/stdn_agentic/tests/ -v -k config` until green.
- [ ] Commit: `feat(config): add fallback-model and escalation-threshold fields`.

---

## Phase 3 — Wire escalation into factory + extractors

### Modify: `src/stdn_agentic/agents/factory.py`

Replace the body of `create_component_agent()` (currently lines 93-112) with logic that builds an `EscalatingAgent` when a fallback is configured:

```python
def create_component_agent(self):
    if self._caching_enabled and self._component_agent is not None:
        return self._component_agent

    primary = get_component_agent(model_name=self.deps.get_component_model())
    fallback_model = self.deps.get_component_fallback_model()

    if fallback_model is None:
        agent = primary
    else:
        fallback = get_component_agent(model_name=fallback_model)
        from .escalation import EscalatingAgent
        agent = EscalatingAgent(
            stage="component",
            primary=primary,
            fallback=fallback,
            accept=_component_quality_predicate(self.deps),
        )

    if self._caching_enabled:
        self._component_agent = agent
    return agent
```

Add a helper at the top of `factory.py`:

```python
def _component_quality_predicate(deps: STDNDependencies):
    threshold = getattr(deps, "component_min_confidence", 0.5)

    def predicate(output) -> Optional[str]:
        comps = getattr(output, "component_list", None) or []
        if not comps:
            return "empty_component_list"
        mean_conf = sum(c.confidence for c in comps) / len(comps)
        if mean_conf < threshold:
            return f"mean_confidence={mean_conf:.2f}<{threshold}"
        return None

    return predicate
```

Mirror the pattern for `create_materials_agent()` and `create_country_agent()`.

### Modify: `src/stdn_agentic/debate/component_debater.py`

In `MultiAgentDebater.run_debate()` (find the round loop), after each round compute convergence as today. After round `max_rounds // 2`, if convergence < `debate_stall_convergence_floor`, swap the agent list to fallback-model-backed agents for the remaining rounds. Sketch:

```python
if (
    round_idx == self.max_rounds // 2
    and convergence < self.stall_floor
    and self.fallback_agents is not None
):
    logger.warning(
        "[escalation] debate stalled at round=%d convergence=%.2f — swapping to fallback agents",
        round_idx,
        convergence,
    )
    self.agents = self.fallback_agents
```

`MultiAgentDebater.__init__` needs new params: `stall_floor: float`, `fallback_agents: Optional[List[Agent]] = None`. Plumb these from `ComponentExtractor`.

### Phase 3 tasks

- [ ] Implement factory changes + predicate helpers. Unit test factory: when `component_fallback_model` is set, `create_component_agent()` returns an `EscalatingAgent`; when None, returns a bare `Agent`.
- [ ] Implement debater changes. Unit test: mock convergence sequence `[0.2, 0.25, 0.3]` with `stall_floor=0.4`, `max_rounds=4` — assert `self.agents` is swapped at round index 2.
- [ ] Run full test suite: `pytest src/stdn_agentic/tests/ -v`. Expect green.
- [ ] Integration test on a 3-tech list with `component_model=ollama:qwen2.5:7b` and `component_fallback_model=anthropic:claude-haiku-4-5-20251001`. Confirm log lines `[escalation] stage=component ...` appear for at least one tech and absent for others.
- [ ] Commit: `feat: dynamic escalation from local to Anthropic on quality gates`.

---

## Phase 4 — Observability + cost accounting

### File to create: `src/stdn_agentic/reporting/escalation_log.py`

A thin JSONL appender that the `on_escalate` callback writes to. One record per escalation event:

```json
{"ts": "2026-05-20T14:32:01Z", "stage": "component", "tech": "Lithium-ion battery pack", "reason": "mean_confidence=0.41<0.50", "primary": "ollama:qwen2.5:7b", "fallback": "anthropic:claude-haiku-4-5-20251001"}
```

Path: `<output_dir>/escalation_log_<config>_<timestamp>.jsonl`.

### Phase 4 tasks

- [ ] Implement the JSONL writer.
- [ ] Wire `factory.py` to construct the writer once per run and pass `on_escalate` into every `EscalatingAgent`.
- [ ] Add `scripts/summarize_escalations.py` — reads JSONL, prints counts per stage + per technology, estimates Anthropic token cost using a hard-coded rate table at the top of the script.
- [ ] Document in `docs/CONFIGURATION.md` and `docs/PIPELINE.md`.
- [ ] Commit: `feat: escalation telemetry + cost summary script`.

---

## Self-review checklist

- [ ] Each phase produces working software on its own — Phase 0 alone is shippable; Phase 1 ships behind a feature flag (config field default is None); Phase 2-4 each extend without breaking.
- [ ] Every new file has an exact path. Every modified file references existing line ranges.
- [ ] Type names (`EscalationEvent`, `EscalatingAgent`, `Predicate`) used consistently across all phases.
- [ ] No `ANTHROPIC_API_KEY` setup steps — already in `.env` (see project root). Anthropic provider in Pydantic AI picks it up automatically.
- [ ] Tests called out per phase; integration test covers the full hybrid path end-to-end.
- [ ] Decision *not* to use Claude Agent SDK / Max subscription is documented at the top so future-you doesn't re-litigate it.

## Open questions for future planning sessions

1. Should `MaterialCache` and `LLMFallbackCache` be aware of *which model* produced a cached entry? A cheap-model cache hit served to a request that would have escalated could lock in lower quality. Consider a `min_model_tier` cache key.
2. Convergence-stall escalation triples the round budget's cost in the worst case (cheap rounds 1-2 + expensive rounds 3-N). Worth measuring before defaulting it on.
3. Country stage already has its own multi-tier flow (USGS → cache → LLM debate → vote). The LLM tier is where escalation belongs, not above the cache.
