"""Stage 2b: Process Consumables Extraction.

Uses a single extraction agent followed by a judge agent to identify
manufacturing process consumables for a technology.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic_ai import RunUsage

from ..agents.process_consumables_agent import (
    ProcessConsumable,
    ProcessConsumablesList,
    JudgeAction,
    JudgeOutput,
    get_extraction_agent,
    get_judge_agent,
)
from ..models import STDNDependencies
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessConsumablesResult:
    """Final output of Stage 2b."""
    materials: list[ProcessConsumable]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_judge_output(cls, judge_output: JudgeOutput, extractor_count: int) -> "ProcessConsumablesResult":
        kept = judge_output.kept_and_added
        materials = []
        for v in kept:
            name = v.name
            if name.lower().startswith("add:"):
                name = name[4:].strip()
            materials.append(
                ProcessConsumable(
                    name=name,
                    confidence=v.confidence,
                    reasoning=v.justification,
                    extraction_provenance="judge_addition" if v.action == JudgeAction.ADD else "extractor",
                )
            )
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
    """Orchestrates Stage 2b: extraction agent -> judge agent."""

    def __init__(self, deps: STDNDependencies, model_name: str = "openai:gpt-4.1-mini"):
        self.deps = deps
        self.model_name = model_name

    async def extract_process_consumables(
        self, technology: str, components: list[str], usage: Optional[RunUsage] = None,
    ) -> ProcessConsumablesResult:
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
        for m in result.materials:
            tag = " [judge_addition]" if m.extraction_provenance == "judge_addition" else ""
            logger.info(f"  Stage 2b material: {m.name} (confidence: {m.confidence}){tag}")
        return result

    async def _run_extraction(self, technology: str, components: list[str], usage: Optional[RunUsage]) -> ProcessConsumablesList:
        agent = get_extraction_agent(self.model_name)
        ontology_names = ", ".join(self.deps.material_ontology_list[:50])
        prompt = (
            f"Technology: {technology}\n"
            f"Components: {', '.join(components)}\n\n"
            f"Materials ontology (reference, not a constraint): {ontology_names}\n\n"
            f"Identify process consumables for this technology's manufacturing."
        )
        result = await agent.run(prompt, deps=self.deps)
        return result.output

    async def _run_judge(self, technology: str, components: list[str], extraction_output: ProcessConsumablesList, usage: Optional[RunUsage]) -> JudgeOutput:
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
        result = await agent.run(prompt, deps=self.deps)
        return result.output
