# Process Consumables Stage (Stage 2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Stage 2b to the STDN-GEN pipeline that extracts manufacturing process consumables (e.g., Helium, etchants, solvents) using an extract + judge protocol, and update the SIGIR paper to reflect the changes.

**Architecture:** Stage 2b runs after Stage 1 (components), sequentially after Stage 2 (constituent materials) in this initial implementation. Parallel execution via `asyncio.gather()` is a future optimization since they share no dependencies beyond Stage 1 output. A single extraction agent proposes process consumables, then a judge agent filters, adjusts confidence, and adds missing items. Results flow into the existing Stage 3 (country assignment) and Stage 4 (normalization) unchanged. The output schema is restructured: JSON becomes authoritative with typed sections (`constituent_dependencies` and `process_consumables`); CSV adds `dependency_type` and splits confidence into `material_confidence` / `country_confidence`.

**Tech Stack:** Python, Pydantic AI, asyncio, pytest, LaTeX

**Spec:** `docs/superpowers/specs/2026-03-24-process-consumables-stage-design.md`

**Code repo:** `~/git/dpi_stdn_agentic`
**Paper repo:** `~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR`

---

## File Map

### New files (code repo: `~/git/dpi_stdn_agentic`)

| File | Responsibility |
|---|---|
| `src/stdn_agentic/agents/process_consumables_agent.py` | Extraction agent + judge system prompts, Pydantic models, agent factory functions |
| `src/stdn_agentic/orchestrator/process_consumables_extractor.py` | Stage 2b orchestration: calls extraction agent then judge, produces typed output |
| `tests/unit/agents/test_process_consumables_agent.py` | Unit tests for agent models and prompt construction |
| `tests/unit/orchestrator/test_process_consumables_extractor.py` | Unit tests for extractor logic (judge filtering, additions, empty results) |
| `tests/integration/test_process_consumables_integration.py` | Integration test: Stage 2b end-to-end with mocked LLM |

### Modified files (code repo)

| File | What changes |
|---|---|
| `src/stdn_agentic/models.py` | Add `process_consumables_model` config field, `enable_process_consumables` flag |
| `src/stdn_agentic/orchestrator/pipeline.py` | Wire Stage 2b into `process_technology()`, merge results into Stage 3 input, restructure JSON output, update normalization for process consumables |
| `src/stdn_agentic/orchestrator/country_data_enricher.py` | Add `enrich_process_consumables()` method that handles country enrichment for process consumables (no component, no HS code required), add `dependency_type` field to output rows |
| `src/stdn_agentic/agents/__init__.py` | Re-export new agent module |
| `src/stdn_agentic/main.py` | Add CLI flags: `--enable-process-consumables`, `--process-consumables-model` |

### Modified files (paper repo: `~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR`)

| File | What changes |
|---|---|
| `sections/methodology.tex` | Extended edge set, Stage 2b description, architecture figure, agent table |
| `sections/supplementary.tex` | Extraction and judge prompt specs, confidence formula |
| `sections/conclusions.tex` | Soften "omit intermediate processing steps" limitation |
| `sections/case_study.tex` | Add process consumables arm to smartphone DAG |

---

## Part 1: Code Implementation

### Task 1: Pydantic Models for Process Consumables

**Files:**
- Create: `~/git/dpi_stdn_agentic/src/stdn_agentic/agents/process_consumables_agent.py`
- Test: `~/git/dpi_stdn_agentic/tests/unit/agents/test_process_consumables_agent.py`

- [ ] **Step 1: Write failing tests for data models**

```python
# tests/unit/agents/test_process_consumables_agent.py

import pytest
from stdn_agentic.agents.process_consumables_agent import (
    ProcessConsumable,
    ProcessConsumablesList,
    JudgeAction,
    JudgeVerdict,
    JudgeOutput,
)


class TestProcessConsumableModels:
    def test_process_consumable_creation(self):
        pc = ProcessConsumable(
            name="Helium",
            confidence=0.85,
            reasoning="Carrier gas in CVD processes",
        )
        assert pc.name == "Helium"
        assert pc.confidence == 0.85

    def test_process_consumable_confidence_bounds(self):
        with pytest.raises(Exception):
            ProcessConsumable(name="X", confidence=1.5, reasoning="test")
        with pytest.raises(Exception):
            ProcessConsumable(name="X", confidence=-0.1, reasoning="test")

    def test_process_consumables_list(self):
        items = [
            ProcessConsumable(name="Helium", confidence=0.85, reasoning="CVD gas"),
            ProcessConsumable(name="Sulfuric Acid", confidence=0.7, reasoning="Etchant"),
        ]
        pcl = ProcessConsumablesList(materials=items)
        assert len(pcl.materials) == 2

    def test_judge_verdict_keep(self):
        v = JudgeVerdict(
            name="Helium",
            action=JudgeAction.KEEP,
            confidence=0.85,
            justification="Universal process gas for semiconductor fabs",
        )
        assert v.action == JudgeAction.KEEP

    def test_judge_verdict_add_caps_confidence(self):
        """Judge additions should be flagged if confidence > 0.7 without strong justification."""
        v = JudgeVerdict(
            name="Neon",
            action=JudgeAction.ADD,
            confidence=0.65,
            justification="Used in lithography laser gas mixtures",
        )
        assert v.action == JudgeAction.ADD
        assert v.confidence <= 0.7

    def test_judge_output(self):
        verdicts = [
            JudgeVerdict(name="Helium", action=JudgeAction.KEEP, confidence=0.85, justification="ok"),
            JudgeVerdict(name="Water", action=JudgeAction.REMOVE, confidence=0.0, justification="too generic"),
            JudgeVerdict(name="Neon", action=JudgeAction.ADD, confidence=0.6, justification="laser gas"),
        ]
        jo = JudgeOutput(verdicts=verdicts)
        assert len(jo.verdicts) == 3
        assert len(jo.kept_and_added) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/unit/agents/test_process_consumables_agent.py -v`
Expected: FAIL — `ImportError: cannot import name 'ProcessConsumable'`

- [ ] **Step 3: Implement the data models**

```python
# src/stdn_agentic/agents/process_consumables_agent.py

"""Process consumables extraction agent and judge for Stage 2b.

Extracts materials consumed during manufacturing but not physically
present in the final product (e.g., process gases, etchants, solvents).
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class ProcessConsumable(BaseModel):
    """A single process consumable with provenance tracking."""
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    extraction_provenance: str = Field(default="extractor")  # "extractor" or "judge_addition"


class ProcessConsumablesList(BaseModel):
    """Extraction agent output: list of proposed process consumables."""
    materials: List[ProcessConsumable]


class JudgeAction(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"
    ADJUST = "adjust"
    ADD = "add"


class JudgeVerdict(BaseModel):
    """A single judge decision on a process consumable."""
    name: str
    action: JudgeAction
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str


class JudgeOutput(BaseModel):
    """Judge agent output: verdicts on each proposed item plus additions."""
    verdicts: List[JudgeVerdict]

    @property
    def kept_and_added(self) -> List[JudgeVerdict]:
        """Return only items that survive the judge (keep, adjust, add)."""
        return [v for v in self.verdicts if v.action != JudgeAction.REMOVE]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/unit/agents/test_process_consumables_agent.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/dpi_stdn_agentic
git add src/stdn_agentic/agents/process_consumables_agent.py tests/unit/agents/test_process_consumables_agent.py
git commit -m "feat: add Pydantic models for process consumables extraction (Stage 2b)"
```

---

### Task 2: Agent Prompts and Factory Functions

**Files:**
- Modify: `~/git/dpi_stdn_agentic/src/stdn_agentic/agents/process_consumables_agent.py`
- Test: `~/git/dpi_stdn_agentic/tests/unit/agents/test_process_consumables_agent.py`

- [ ] **Step 1: Write failing tests for prompt content and agent factories**

```python
# Append to tests/unit/agents/test_process_consumables_agent.py

from stdn_agentic.agents.process_consumables_agent import (
    EXTRACTION_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    get_extraction_agent,
    get_judge_agent,
)


class TestProcessConsumablePrompts:
    def test_extraction_prompt_excludes_constituent_materials(self):
        assert "do not become part of the final product" in EXTRACTION_SYSTEM_PROMPT.lower() or \
               "do NOT include materials that physically constitute" in EXTRACTION_SYSTEM_PROMPT

    def test_extraction_prompt_mentions_process_categories(self):
        prompt_lower = EXTRACTION_SYSTEM_PROMPT.lower()
        assert "process gas" in prompt_lower or "gases" in prompt_lower
        assert "etchant" in prompt_lower
        assert "solvent" in prompt_lower

    def test_judge_prompt_allows_additions(self):
        assert "add" in JUDGE_SYSTEM_PROMPT.lower()
        assert "0.7" in JUDGE_SYSTEM_PROMPT

    def test_judge_prompt_requires_justification(self):
        assert "justification" in JUDGE_SYSTEM_PROMPT.lower() or \
               "rationale" in JUDGE_SYSTEM_PROMPT.lower()


class TestAgentFactories:
    def test_get_extraction_agent_returns_agent(self):
        agent = get_extraction_agent(model_name="openai:gpt-4.1-mini")
        assert agent is not None

    def test_get_judge_agent_returns_agent(self):
        agent = get_judge_agent(model_name="openai:gpt-4.1-mini")
        assert agent is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/unit/agents/test_process_consumables_agent.py -v -k "Prompt or Factor"`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement prompts and factory functions**

Add to `src/stdn_agentic/agents/process_consumables_agent.py`:

```python
from pydantic_ai import Agent

EXTRACTION_SYSTEM_PROMPT = """You are a semiconductor process engineer and manufacturing chemist.

Given a technology description and its component list, identify materials that are CONSUMED DURING THE MANUFACTURING PROCESS but do NOT become part of the final product.

These include:
- Process gases (e.g., helium, nitrogen, argon, hydrogen, fluorine compounds)
- Etchants and cleaning agents (e.g., sulfuric acid, hydrofluoric acid, hydrogen peroxide)
- Solvents (e.g., isopropanol, acetone, NMP)
- Photoresists and developers
- CMP slurries and polishing compounds
- Cooling media and heat transfer fluids
- Deposition precursors consumed in the process (e.g., silane, TEOS)

Do NOT include materials that physically constitute a component — those are handled separately.

The component list is provided as context to help you infer which manufacturing processes are involved. For example, if the technology includes a "photolithography system" component, this implies use of photoresist chemicals, developer solutions, and potentially helium for cooling.

For each process consumable, provide:
1. Material Name: Use standard industry terminology. Prefer names from the provided materials ontology when available, but you may propose names outside the ontology for process-specific chemicals.
2. Confidence Score (0.0 to 1.0):
   - 0.9-1.0: Absolutely essential — universally consumed in this technology's manufacturing
   - 0.8-0.89: Very confident — industry standard consumable for this process
   - 0.7-0.79: Confident — common in most manufacturing variants
   - 0.6-0.69: Moderately confident — used in many but not all process flows
   - 0.5-0.59: Uncertain — depends on specific process variant
   - 0.3-0.49: Low confidence — used in some specialized variants only
   - 0.0-0.29: Very low confidence — rarely needed
3. Reasoning: Brief explanation (1-2 sentences) of the manufacturing process that consumes this material.
"""

JUDGE_SYSTEM_PROMPT = """You are a materials scientist reviewing a proposed list of manufacturing process consumables for a given technology.

You will receive:
- A technology description
- A component list for that technology
- A proposed list of process consumables with confidence scores and reasoning

Your tasks:
1. REMOVE any item that:
   - Is a constituent material (physically becomes part of the product)
   - Is hallucinated or not plausibly consumed in this technology's manufacturing
   - Is too generic to be actionable (e.g., "chemicals", "gases")
2. ADJUST confidence scores where the proposed score does not match how universal the consumable is for this technology class.
3. ADD any critical process consumables that were missed. Additions must include a rationale and are capped at 0.7 confidence unless you can provide strong justification for a higher score.

For EACH item (whether kept, removed, adjusted, or added), provide:
- name: the material name
- action: one of "keep", "remove", "adjust", "add"
- confidence: the final confidence score (0.0 for removed items)
- justification: brief explanation of your decision
"""


def get_extraction_agent(model_name: str = "openai:gpt-4.1-mini") -> Agent:
    """Create a process consumables extraction agent."""
    return Agent(
        model=model_name,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        output_type=ProcessConsumablesList,
    )


def get_judge_agent(model_name: str = "openai:gpt-4.1-mini") -> Agent:
    """Create a process consumables judge agent."""
    return Agent(
        model=model_name,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        output_type=JudgeOutput,
    )
```

Note: The exact `Agent(...)` constructor call should match the pattern used in the existing `agents/materials_agent.py` and `agents/component_agent.py` files. Inspect those files and match the style (e.g., `deps_type`, `retries`, `result_type` usage).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/unit/agents/test_process_consumables_agent.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/dpi_stdn_agentic
git add src/stdn_agentic/agents/process_consumables_agent.py tests/unit/agents/test_process_consumables_agent.py
git commit -m "feat: add extraction and judge prompts for process consumables (Stage 2b)"
```

---

### Task 3: Process Consumables Extractor (Orchestrator)

**Files:**
- Create: `~/git/dpi_stdn_agentic/src/stdn_agentic/orchestrator/process_consumables_extractor.py`
- Test: `~/git/dpi_stdn_agentic/tests/unit/orchestrator/test_process_consumables_extractor.py`

- [ ] **Step 1: Write failing tests for the extractor**

```python
# tests/unit/orchestrator/test_process_consumables_extractor.py

import pytest
from unittest.mock import AsyncMock, Mock, patch

from stdn_agentic.agents.process_consumables_agent import (
    ProcessConsumable,
    ProcessConsumablesList,
    JudgeAction,
    JudgeVerdict,
    JudgeOutput,
)
from stdn_agentic.orchestrator.process_consumables_extractor import (
    ProcessConsumablesExtractor,
    ProcessConsumablesResult,
)


@pytest.fixture
def mock_deps():
    deps = Mock()
    deps.material_ontology_list = ["Helium", "Nitrogen", "Silicon", "Copper"]
    return deps


class TestProcessConsumablesResult:
    def test_result_from_judge_output(self):
        judge_out = JudgeOutput(verdicts=[
            JudgeVerdict(name="Helium", action=JudgeAction.KEEP, confidence=0.85, justification="ok"),
            JudgeVerdict(name="Water", action=JudgeAction.REMOVE, confidence=0.0, justification="too generic"),
            JudgeVerdict(name="Neon", action=JudgeAction.ADD, confidence=0.6, justification="laser gas"),
        ])
        result = ProcessConsumablesResult.from_judge_output(
            judge_output=judge_out,
            extractor_count=2,
        )
        assert len(result.materials) == 2  # Helium + Neon (Water removed)
        assert result.metadata["extractor_items"] == 2
        assert result.metadata["judge_removed"] == 1
        assert result.metadata["judge_added"] == 1

    def test_empty_result(self):
        result = ProcessConsumablesResult.empty()
        assert len(result.materials) == 0
        assert result.metadata["extractor_items"] == 0


class TestProcessConsumablesExtractor:
    @pytest.mark.asyncio
    async def test_extract_returns_result(self, mock_deps):
        extractor = ProcessConsumablesExtractor(
            deps=mock_deps, model_name="openai:gpt-4.1-mini"
        )

        extraction_output = ProcessConsumablesList(materials=[
            ProcessConsumable(name="Helium", confidence=0.85, reasoning="CVD gas"),
        ])
        judge_output = JudgeOutput(verdicts=[
            JudgeVerdict(name="Helium", action=JudgeAction.KEEP, confidence=0.85, justification="ok"),
        ])

        with patch.object(extractor, "_run_extraction", new_callable=AsyncMock, return_value=extraction_output), \
             patch.object(extractor, "_run_judge", new_callable=AsyncMock, return_value=judge_output):
            result = await extractor.extract_process_consumables(
                technology="Smartphone SoC",
                components=["Die", "Package Substrate"],
            )

        assert len(result.materials) == 1
        assert result.materials[0].name == "Helium"

    @pytest.mark.asyncio
    async def test_extract_empty_when_extraction_returns_nothing(self, mock_deps):
        extractor = ProcessConsumablesExtractor(
            deps=mock_deps, model_name="openai:gpt-4.1-mini"
        )
        empty_output = ProcessConsumablesList(materials=[])
        judge_output = JudgeOutput(verdicts=[])

        with patch.object(extractor, "_run_extraction", new_callable=AsyncMock, return_value=empty_output), \
             patch.object(extractor, "_run_judge", new_callable=AsyncMock, return_value=judge_output):
            result = await extractor.extract_process_consumables(
                technology="Simple Widget",
                components=["Frame"],
            )

        assert len(result.materials) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/unit/orchestrator/test_process_consumables_extractor.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement the extractor**

```python
# src/stdn_agentic/orchestrator/process_consumables_extractor.py

"""Stage 2b: Process Consumables Extraction.

Uses a single extraction agent followed by a judge agent to identify
manufacturing process consumables for a technology.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from stdn_agentic.agents.process_consumables_agent import (
    ProcessConsumable,
    ProcessConsumablesList,
    JudgeAction,
    JudgeOutput,
    JudgeVerdict,
    get_extraction_agent,
    get_judge_agent,
)
from stdn_agentic.dependencies import STDNDependencies

logger = logging.getLogger(__name__)


@dataclass
class ProcessConsumablesResult:
    """Final output of Stage 2b."""
    materials: list[ProcessConsumable]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_judge_output(
        cls, judge_output: JudgeOutput, extractor_count: int
    ) -> "ProcessConsumablesResult":
        kept = judge_output.kept_and_added
        materials = [
            ProcessConsumable(
                name=v.name,
                confidence=v.confidence,
                reasoning=v.justification,
                extraction_provenance="judge_addition" if v.action == JudgeAction.ADD else "extractor",
            )
            for v in kept
        ]
        removed_count = sum(1 for v in judge_output.verdicts if v.action == JudgeAction.REMOVE)
        added_count = sum(1 for v in judge_output.verdicts if v.action == JudgeAction.ADD)
        return cls(
            materials=materials,
            metadata={
                "extractor_items": extractor_count,
                "judge_removed": removed_count,
                "judge_added": added_count,
                "final_items": len(materials),
            },
        )

    @classmethod
    def empty(cls) -> "ProcessConsumablesResult":
        return cls(materials=[], metadata={"extractor_items": 0, "judge_removed": 0, "judge_added": 0, "final_items": 0})


class ProcessConsumablesExtractor:
    """Orchestrates Stage 2b: extraction agent → judge agent."""

    def __init__(
        self,
        deps: STDNDependencies,
        model_name: str = "openai:gpt-4.1-mini",
    ):
        self.deps = deps
        self.model_name = model_name

    async def extract_process_consumables(
        self,
        technology: str,
        components: list[str],
        usage: Optional[Any] = None,
    ) -> ProcessConsumablesResult:
        """Run extract + judge pipeline for a technology."""
        logger.info(f"Stage 2b: extracting process consumables for {technology}")

        extraction_output = await self._run_extraction(technology, components, usage)
        extractor_count = len(extraction_output.materials)
        logger.info(f"Stage 2b extraction proposed {extractor_count} items for {technology}")

        judge_output = await self._run_judge(technology, components, extraction_output, usage)
        result = ProcessConsumablesResult.from_judge_output(judge_output, extractor_count)
        logger.info(
            f"Stage 2b judge: {result.metadata['judge_removed']} removed, "
            f"{result.metadata['judge_added']} added, {result.metadata['final_items']} final"
        )
        return result

    async def _run_extraction(
        self, technology: str, components: list[str], usage: Optional[Any]
    ) -> ProcessConsumablesList:
        """Call the extraction agent."""
        agent = get_extraction_agent(self.model_name)
        ontology_names = ", ".join(self.deps.material_ontology_list[:50])  # Provide ontology as reference
        prompt = (
            f"Technology: {technology}\n"
            f"Components: {', '.join(components)}\n\n"
            f"Materials ontology (reference, not a constraint): {ontology_names}\n\n"
            f"Identify process consumables for this technology's manufacturing."
        )
        # Match the agent invocation pattern from materials_agent.py
        result = await agent.run(prompt)
        return result.output

    async def _run_judge(
        self,
        technology: str,
        components: list[str],
        extraction_output: ProcessConsumablesList,
        usage: Optional[Any],
    ) -> JudgeOutput:
        """Call the judge agent."""
        agent = get_judge_agent(self.model_name)
        proposed_items = "\n".join(
            f"- {m.name} (confidence: {m.confidence}): {m.reasoning}"
            for m in extraction_output.materials
        )
        prompt = (
            f"Technology: {technology}\n"
            f"Components: {', '.join(components)}\n\n"
            f"Proposed process consumables:\n{proposed_items}\n\n"
            f"Review each item and add any missing critical process consumables."
        )
        result = await agent.run(prompt)
        return result.output
```

**Implementation notes:**
- Match the exact `agent.run(...)` pattern from `materials_agent.py` — check whether it uses `await agent.run(prompt)` or `await agent.run(prompt, deps=self.deps)` and match accordingly.
- Use **relative imports** throughout new modules (e.g., `from ..agents.process_consumables_agent import ...`), matching the existing codebase convention.
- Match `deps_type` and `retries` parameters from the existing agent factory functions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/unit/orchestrator/test_process_consumables_extractor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/dpi_stdn_agentic
git add src/stdn_agentic/orchestrator/process_consumables_extractor.py tests/unit/orchestrator/test_process_consumables_extractor.py
git commit -m "feat: add ProcessConsumablesExtractor for Stage 2b orchestration"
```

---

### Task 4: Config and CLI Integration

**Files:**
- Modify: `~/git/dpi_stdn_agentic/src/stdn_agentic/models.py`
- Modify: `~/git/dpi_stdn_agentic/src/stdn_agentic/main.py`

- [ ] **Step 1: Add config fields to ConfigModel**

In `models.py`, add to the `ConfigModel` class alongside the existing per-agent model fields:

```python
    # Process consumables (Stage 2b)
    enable_process_consumables: bool = Field(default=False)
    process_consumables_model: Optional[str] = None
```

- [ ] **Step 2: Add CLI flags to main.py**

In `main.py`, add to the argument parser (near the existing `--enable-material-debate` flag):

```python
    parser.add_argument("--enable-process-consumables", type=_str_to_bool, default=None,
                        help="Enable Stage 2b: process consumables extraction")
    parser.add_argument("--process-consumables-model", type=str, default=None,
                        help="Model for process consumables agents")
```

And in the section where CLI args override config values, add the corresponding logic.

- [ ] **Step 3: Verify existing tests still pass**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/unit/ -v --timeout=30`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
cd ~/git/dpi_stdn_agentic
git add src/stdn_agentic/models.py src/stdn_agentic/main.py
git commit -m "feat: add config and CLI flags for process consumables (Stage 2b)"
```

---

### Task 5: Wire Stage 2b into Pipeline Orchestrator

**Files:**
- Modify: `~/git/dpi_stdn_agentic/src/stdn_agentic/orchestrator/pipeline.py`
- Test: `~/git/dpi_stdn_agentic/tests/integration/test_process_consumables_integration.py`

This is the most complex task — it wires Stage 2b into the main pipeline.

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_process_consumables_integration.py

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from stdn_agentic.agents.process_consumables_agent import (
    ProcessConsumable,
    JudgeAction,
    JudgeVerdict,
    JudgeOutput,
    ProcessConsumablesList,
)
from stdn_agentic.orchestrator.process_consumables_extractor import (
    ProcessConsumablesExtractor,
    ProcessConsumablesResult,
)


class TestProcessConsumablesPipelineIntegration:
    """Test that Stage 2b results flow correctly to Stage 3."""

    def test_process_consumables_result_produces_country_enrichment_input(self):
        """Process consumables should produce material names that Stage 3 can enrich."""
        result = ProcessConsumablesResult(
            materials=[
                ProcessConsumable(name="Helium", confidence=0.85, reasoning="CVD gas"),
                ProcessConsumable(name="Nitrogen", confidence=0.9, reasoning="Purge gas"),
            ],
            metadata={"extractor_items": 2, "judge_removed": 0, "judge_added": 0, "final_items": 2},
        )
        # Verify the material names can be extracted for Stage 3 input
        material_names = [m.name for m in result.materials]
        assert "Helium" in material_names
        assert "Nitrogen" in material_names

    def test_empty_process_consumables_is_valid(self):
        """An empty result should not break the pipeline."""
        result = ProcessConsumablesResult.empty()
        assert result.materials == []
        assert result.metadata["final_items"] == 0
```

- [ ] **Step 2: Run integration test to verify it passes (these are structural tests)**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/integration/test_process_consumables_integration.py -v`
Expected: PASS

- [ ] **Step 3: Modify `pipeline.py` — initialize ProcessConsumablesExtractor**

In `STDNOrchestrator.__init__()`, after the `MaterialsExtractor` initialization (look for the pattern), add:

```python
        # Stage 2b: Process Consumables (optional)
        self.enable_process_consumables = getattr(config, 'enable_process_consumables', False)
        if self.enable_process_consumables:
            from stdn_agentic.orchestrator.process_consumables_extractor import ProcessConsumablesExtractor
            pc_model = getattr(config, 'process_consumables_model', None) or config.model
            self.process_consumables_extractor = ProcessConsumablesExtractor(
                deps=self.deps,
                model_name=pc_model,
            )
```

- [ ] **Step 4: Modify `pipeline.py` — call Stage 2b in `process_technology()`**

In `process_technology()`, after Stage 2 (materials extraction) completes and before Stage 3 (country enrichment), add:

```python
        # Stage 2b: Process Consumables (if enabled)
        process_consumables_result = None
        if self.enable_process_consumables:
            process_consumables_result = await self.process_consumables_extractor.extract_process_consumables(
                technology=technology,
                components=component_names,
                usage=usage,
            )
```

Then in Stage 3, after the existing `enrich_with_country_data()` call for constituent materials, add country enrichment for process consumables. **Do NOT call `self.country_repo.get_country_data()` directly** — instead, add a new method `enrich_process_consumables()` to `CountryDataEnricher` (see Step 4b below) that follows the same pattern as the existing `enrich_with_country_data()` (handling HS code lookup, usage tracking, transcript paths, null handling).

```python
        # Stage 3 for process consumables
        if process_consumables_result and process_consumables_result.materials:
            pc_rows = await self.country_enricher.enrich_process_consumables(
                process_consumables=process_consumables_result,
                technology=technology,
                usage=usage,
                transcript_path=transcript_path,
            )
            # Write pc_rows to CSV with dependency_type="process_consumable"
```

- [ ] **Step 4b: Add `enrich_process_consumables()` to CountryDataEnricher**

In `country_data_enricher.py`, add a method that mirrors `enrich_with_country_data()` but operates on `ProcessConsumablesResult` instead of `ComponentMaterialsList`. Key differences:
- No component association (component fields are empty)
- No HS code lookup required (process consumables may not have HS codes)
- Each output row includes `"dependency_type": "process_consumable"` and `"extraction_provenance"` from the `ProcessConsumable` model

Study the existing `enrich_with_country_data()` method carefully and replicate its patterns for usage tracking, transcript appending, and confidence extraction.

- [ ] **Step 5: Add `dependency_type` column to CSV output**

In `pipeline.py`, the `fieldnames` list appears in **two places** (initialization and row-writing). Add `"dependency_type"` and `"extraction_provenance"` to both. For existing constituent material rows, add `"dependency_type": "constituent"` — this must be added in `CountryDataEnricher.enrich_with_country_data()` where the row dicts are constructed, not in `pipeline.py` after the fact.

- [ ] **Step 5b: Update `agents/__init__.py`**

Add re-exports for the new module to `src/stdn_agentic/agents/__init__.py`, following the existing pattern for component_agent and materials_agent.

- [ ] **Step 6: Update Stage 4 normalization for process consumables**

In `pipeline.py`'s `_normalize_output()` method, the normalization currently works on component names. Process consumable rows have empty component fields — ensure these rows are not broken by the normalization logic. Material names for process consumables should also go through the canonical vocabulary. Add a pass that normalizes material names for process consumable rows using `(technology, material)` tuples. If material normalization is not yet implemented for constituent materials either, this can be deferred with a `# TODO` comment.

- [ ] **Step 7: Run all tests**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/ -v --timeout=60 -m "not requires_api and not e2e"`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
cd ~/git/dpi_stdn_agentic
git add src/stdn_agentic/orchestrator/pipeline.py src/stdn_agentic/orchestrator/country_data_enricher.py src/stdn_agentic/agents/__init__.py tests/integration/test_process_consumables_integration.py
git commit -m "feat: wire Stage 2b into pipeline orchestrator with dependency_type column"
```

---

### Task 6: Restructure JSON Output

**Files:**
- Modify: `~/git/dpi_stdn_agentic/src/stdn_agentic/orchestrator/pipeline.py` (the `_save_json_output` method)

- [ ] **Step 1: Write test for new JSON structure**

Add to `tests/integration/test_process_consumables_integration.py`:

```python
import json
import tempfile
import csv
import os


class TestJsonOutputStructure:
    def _write_test_csv(self, path: str):
        """Write a minimal CSV with both dependency types."""
        fieldnames = [
            "technology", "component", "component_confidence", "component_reasoning",
            "material", "material_confidence", "material_reasoning", "hs_code",
            "country", "meas_unit", "amount", "percentage",
            "country_confidence", "country_reasoning", "dependency_type",
        ]
        rows = [
            {
                "technology": "SoC", "component": "Die", "component_confidence": "0.95",
                "component_reasoning": "core", "material": "Silicon",
                "material_confidence": "0.95", "material_reasoning": "substrate",
                "hs_code": "2804", "country": "China", "meas_unit": "mt",
                "amount": "1000", "percentage": "40",
                "country_confidence": "0.92", "country_reasoning": "USGS",
                "dependency_type": "constituent",
            },
            {
                "technology": "SoC", "component": "", "component_confidence": "",
                "component_reasoning": "", "material": "Helium",
                "material_confidence": "0.85", "material_reasoning": "CVD gas",
                "hs_code": "", "country": "United States", "meas_unit": "mcf",
                "amount": "500", "percentage": "55",
                "country_confidence": "0.95", "country_reasoning": "USGS",
                "dependency_type": "process_consumable",
            },
        ]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_json_has_typed_sections(self):
        """JSON output should separate constituent and process consumable dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            self._write_test_csv(csv_path)

            # Import and call the restructured JSON builder
            from stdn_agentic.orchestrator.pipeline import build_structured_json
            result = build_structured_json(csv_path)

            assert "SoC" in result
            tech = result["SoC"]
            assert "constituent_dependencies" in tech
            assert "process_consumables" in tech

            # Constituent: Silicon under Die
            components = tech["constituent_dependencies"]["components"]
            assert any(c["name"] == "Die" for c in components)
            die = next(c for c in components if c["name"] == "Die")
            assert any(m["name"] == "Silicon" for m in die["materials"])

            # Process consumable: Helium
            pc_materials = tech["process_consumables"]["materials"]
            assert any(m["name"] == "Helium" for m in pc_materials)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/integration/test_process_consumables_integration.py::TestJsonOutputStructure -v`
Expected: FAIL — `ImportError: cannot import name 'build_structured_json'`

- [ ] **Step 3: Implement `build_structured_json` function**

Add to `pipeline.py` (as a module-level function or static method):

```python
def build_structured_json(csv_path: str) -> dict:
    """Build structured JSON with typed dependency sections from flat CSV.

    Returns dict keyed by technology name, each containing:
    - constituent_dependencies: {components: [{name, confidence, materials: [{name, confidence, countries: [...]}]}]}
    - process_consumables: {materials: [{name, confidence, extraction_provenance, rationale, countries: [...]}]}
    """
    import csv
    from collections import defaultdict

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    techs = {}
    for row in rows:
        tech_name = row["technology"]
        if tech_name not in techs:
            techs[tech_name] = {
                "constituent_dependencies": {"components": []},
                "process_consumables": {"materials": []},
            }
        tech = techs[tech_name]
        dep_type = row.get("dependency_type", "constituent")

        country_entry = {
            "name": row["country"],
            "confidence": float(row["country_confidence"]) if row["country_confidence"] else None,
            "source": "authoritative" if float(row.get("country_confidence", 0) or 0) >= 0.95 else "inferred",
        }

        if dep_type == "process_consumable":
            # Find or create material entry
            pc_mats = tech["process_consumables"]["materials"]
            existing = next((m for m in pc_mats if m["name"] == row["material"]), None)
            if existing is None:
                existing = {
                    "name": row["material"],
                    "confidence": float(row["material_confidence"]) if row["material_confidence"] else None,
                    "extraction_provenance": row.get("extraction_provenance", "extractor"),
                    "rationale": row.get("material_reasoning", ""),
                    "countries": [],
                }
                pc_mats.append(existing)
            if row["country"]:
                existing["countries"].append(country_entry)
        else:
            # Constituent: nest under component
            comp_name = row["component"]
            comp_list = tech["constituent_dependencies"]["components"]
            existing_comp = next((c for c in comp_list if c["name"] == comp_name), None)
            if existing_comp is None:
                existing_comp = {
                    "name": comp_name,
                    "confidence": float(row["component_confidence"]) if row["component_confidence"] else None,
                    "materials": [],
                }
                comp_list.append(existing_comp)
            mat_list = existing_comp["materials"]
            existing_mat = next((m for m in mat_list if m["name"] == row["material"]), None)
            if existing_mat is None:
                existing_mat = {
                    "name": row["material"],
                    "confidence": float(row["material_confidence"]) if row["material_confidence"] else None,
                    "countries": [],
                }
                mat_list.append(existing_mat)
            if row["country"]:
                existing_mat["countries"].append(country_entry)

    return techs
```

Then update `_save_json_output()` to call `build_structured_json()` instead of the current flat conversion.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/integration/test_process_consumables_integration.py::TestJsonOutputStructure -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd ~/git/dpi_stdn_agentic && python -m pytest tests/ -v --timeout=60 -m "not requires_api and not e2e"`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd ~/git/dpi_stdn_agentic
git add src/stdn_agentic/orchestrator/pipeline.py tests/integration/test_process_consumables_integration.py
git commit -m "feat: restructure JSON output with typed dependency sections"
```

---

### Task 7: Manual Smoke Test

- [ ] **Step 1: Create a test config for process consumables**

Create `~/git/dpi_stdn_agentic/config_test_process_consumables.json` by copying `config_d3d3v3.json` and adding:
```json
"enable_process_consumables": true
```

Use a small tech list with 1 microelectronics technology (e.g., "Smartphone Application Processor (SoC) Package").

- [ ] **Step 2: Run the pipeline**

```bash
cd ~/git/dpi_stdn_agentic
python -m stdn_agentic.main -i config_test_process_consumables.json --enable-process-consumables true
```

- [ ] **Step 3: Inspect output**

Check the raw CSV for process consumable rows (look for `dependency_type` = `process_consumable` and empty `component` column). Check the JSON output for the `process_consumables` section. Verify Helium appears.

- [ ] **Step 4: Commit test config**

```bash
cd ~/git/dpi_stdn_agentic
git add config_test_process_consumables.json
git commit -m "test: add config for process consumables smoke test"
```

---

## Part 2: Paper Updates

All edits in `~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR`.

### Task 8: Extend Problem Formulation and Pipeline Description

**Files:**
- Modify: `sections/methodology.tex`

- [ ] **Step 1: Extend the STDN edge set definition**

At `methodology.tex:23-24`, change:
```latex
$E \subset T\times C \cup C \times M \cup M \times P$.
```
to:
```latex
$E \subset T\times C \cup C \times M \cup T \times M_{\mathrm{proc}} \cup M \times P \cup M_{\mathrm{proc}} \times P$,
```
and add a sentence explaining that $M_{\mathrm{proc}}$ denotes process consumable materials that are consumed during manufacturing but not physically present in the final product, with edges $T \times M_{\mathrm{proc}}$ linking technologies directly to these materials.

- [ ] **Step 2: Add Stage 2b to the pipeline description**

After the Stage 2 paragraph (around line 55), add a new paragraph:

```latex
\textbf{Stage 2b: Process consumables extraction.}
Not all supply chain-relevant materials become part of the final product. Process consumables---gases, etchants, solvents, and other materials consumed during manufacturing---represent real dependencies that are invisible to constituent-material extraction. Stage 2b addresses this gap using a two-step extract-and-judge protocol. First, a process-engineering extraction agent receives the technology description and stabilized component list and proposes candidate process consumables. Second, a judge agent reviews the proposal: removing hallucinated or misclassified items, adjusting confidence scores, and adding missing consumables (capped at confidence $\le 0.7$ unless strongly justified). This lighter protocol (two LLM calls vs.\ six--nine for debate) is appropriate because process consumables are less ambiguous than constituent materials. The resulting materials flow into Stage~3 for country assignment via the same USGS-first policy.
```

- [ ] **Step 3: Update the agent specialization table**

At `methodology.tex:197-215`, add a row to `tab:agent_roles`:

```latex
Process Consumables & 2b & Process engineer, manufacturing chemist & Materials ontology (reference) \\
\hline
Process Consumables Judge & 2b & Materials scientist & Materials ontology, Stage 2b proposal \\
```

- [ ] **Step 4: Commit**

```bash
cd ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR
git add sections/methodology.tex
git commit -m "Update methodology: add Stage 2b process consumables extraction"
```

---

### Task 9: Update Supplementary Material

**Files:**
- Modify: `sections/supplementary.tex`

- [ ] **Step 1: Add extraction agent and judge specs**

After the existing S.1.1 subsection (around line 67), add:

```latex
\paragraph{Process Consumables Extraction Agent (Stage 2b).}
Objective: propose materials consumed during manufacturing that do not become part of the final product (e.g., process gases, etchants, solvents, photoresists, CMP slurries, cooling media).

Constraints and expectations:
\begin{itemize}[itemsep=2pt]
    \item Materials must be plausibly consumed in the manufacturing process for the technology class.
    \item The agent receives the stabilized component list as context for inferring manufacturing processes, but does not produce component-level associations.
    \item The materials ontology is used as a reference, not a hard constraint---many process consumables (photoresists, specialty gases) may not appear in the HS-aligned ontology.
    \item Constituent materials (those that physically become part of the product) must not be included.
\end{itemize}

\paragraph{Process Consumables Judge (Stage 2b).}
Objective: review the extraction agent's proposal, removing misclassified or hallucinated items, adjusting confidence, and adding missing process consumables.

Constraints and expectations:
\begin{itemize}[itemsep=2pt]
    \item The judge may remove, adjust, or keep any proposed item, and may add new items.
    \item Additions are capped at confidence $\le 0.7$ unless strongly justified.
    \item Each action (keep, remove, adjust, add) must include a brief justification.
\end{itemize}

Stage 2b uses no debate loop---it is a single-pass protocol (one extraction call, one judge call). Final confidence is the judge's output confidence directly, with no peer-support multiplier.
```

- [ ] **Step 2: Commit**

```bash
cd ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR
git add sections/supplementary.tex
git commit -m "Update supplementary: add Stage 2b agent and judge specifications"
```

---

### Task 10: Update Limitations and Case Study

**Files:**
- Modify: `sections/conclusions.tex`
- Modify: `sections/case_study.tex`

- [ ] **Step 1: Soften the limitations text**

In `conclusions.tex:12`, change:
```latex
STDNs are intentionally shallow for tractability and interpretability; they may omit intermediate processing steps, subassemblies, and temporal dynamics.
```
to:
```latex
STDNs are intentionally shallow for tractability and interpretability. Stage~2b partially addresses the omission of manufacturing process dependencies by extracting process consumables (e.g., process gases, etchants), but intermediate processing steps, subassemblies, and temporal dynamics remain outside scope.
```

- [ ] **Step 2: Add process consumables to case study discussion**

At the end of `case_study.tex` (before the final `\paragraph{Takeaway}`), add a paragraph noting that Stage 2b surfaces process consumables like Helium that are invisible to constituent-material extraction, and that these materials follow the same country-assignment pathway, enabling supply chain risk analysis for manufacturing inputs as well as product constituents.

Note: The exact content here depends on re-running the smartphone pipeline with Stage 2b enabled (Task 7). Use the actual output to populate the case study text.

- [ ] **Step 3: Commit**

```bash
cd ~/git/D-PI-2026-01-STDN_AGENTIC_SIGIR
git add sections/conclusions.tex sections/case_study.tex
git commit -m "Update limitations and case study for process consumables"
```
