"""Stage 2b: Process Consumables Extraction.

Uses a single extraction agent followed by a judge agent to identify
manufacturing process consumables at both the technology (assembly) level
and the component (fabrication) level.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic_ai import RunUsage

from ..agents.process_consumables_agent import (
    ProcessConsumable,
    ProcessConsumablesGrouped,
    ComponentConsumables,
    JudgeAction,
    JudgeGroupedOutput,
    ComponentJudgeVerdicts,
    get_extraction_agent,
    get_judge_agent,
)
from ..agents.materials_agent import (
    _exact_match,
    _variant_match,
)
from ..models import STDNDependencies
from ..logging_config import get_logger

logger = get_logger(__name__)


def _clean_name(name: str) -> str:
    """Strip 'Add:' prefix from judge-added material names."""
    if name.lower().startswith("add:"):
        return name[4:].strip()
    return name


def _verdicts_to_consumables(verdicts, component: str = "") -> list[ProcessConsumable]:
    """Convert judge verdicts to ProcessConsumable list, filtering removes."""
    materials = []
    for v in verdicts:
        if v.action == JudgeAction.REMOVE:
            continue
        materials.append(
            ProcessConsumable(
                name=_clean_name(v.name),
                confidence=v.confidence,
                reasoning=v.justification,
                extraction_provenance="judge_addition" if v.action == JudgeAction.ADD else "extractor",
                component=component,
            )
        )
    return materials


@dataclass
class ProcessConsumablesResult:
    """Final output of Stage 2b — includes both assembly-level and component-level consumables."""
    materials: list[ProcessConsumable]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_judge_output(
        cls, judge_output: JudgeGroupedOutput, extractor_count: int
    ) -> "ProcessConsumablesResult":
        # Assembly-level consumables (component = "")
        assembly_materials = _verdicts_to_consumables(
            judge_output.assembly_verdicts, component=""
        )

        # Component-level consumables
        component_materials = []
        for cv in judge_output.component_verdicts:
            component_materials.extend(
                _verdicts_to_consumables(cv.verdicts, component=cv.component)
            )

        all_materials = assembly_materials + component_materials

        # Count judge actions across all verdicts
        all_verdicts = list(judge_output.assembly_verdicts)
        for cv in judge_output.component_verdicts:
            all_verdicts.extend(cv.verdicts)

        removed_count = sum(1 for v in all_verdicts if v.action == JudgeAction.REMOVE)
        added_count = sum(1 for v in all_verdicts if v.action == JudgeAction.ADD)

        return cls(
            materials=all_materials,
            metadata={
                "extractor_items": extractor_count,
                "judge_removed": removed_count,
                "judge_added": added_count,
                "final_items": len(all_materials),
                "assembly_items": len(assembly_materials),
                "component_items": len(component_materials),
            },
        )

    @classmethod
    def empty(cls) -> "ProcessConsumablesResult":
        return cls(
            materials=[],
            metadata={
                "extractor_items": 0, "judge_removed": 0, "judge_added": 0,
                "final_items": 0, "assembly_items": 0, "component_items": 0,
            },
        )


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

        # Count total items from extraction
        extractor_count = len(extraction_output.assembly_consumables)
        for cc in extraction_output.component_consumables:
            extractor_count += len(cc.materials)
        logger.info(f"Stage 2b extraction proposed {extractor_count} items for {technology}")

        judge_output = await self._run_judge(technology, components, extraction_output, usage)
        result = ProcessConsumablesResult.from_judge_output(judge_output, extractor_count)

        logger.info(
            f"Stage 2b judge: {result.metadata['judge_removed']} removed, "
            f"{result.metadata['judge_added']} added, {result.metadata['final_items']} final "
            f"({result.metadata['assembly_items']} assembly + {result.metadata['component_items']} component)"
        )

        # Normalize material names against the ontology using strict matching only.
        # Process consumable names are often compound phrases ("Photoresists and developers
        # (TMAH)", "Coolants and refrigerants (e.g., glycol-water)") which cause false
        # positives with word-level, partial, fuzzy, and even chemical-symbol matching
        # (the word "and" matches "Kyanite and Related Minerals" via symbol match).
        # We only accept exact and variant matches for Stage 2b.
        ontology = self.deps.material_ontology_list
        normalized_count = 0
        for m in result.materials:
            name_lower = m.name.lower().strip()
            matched = (
                _exact_match(name_lower, ontology)
                or _variant_match(name_lower, ontology)
            )
            if matched and matched != m.name and matched in ontology:
                logger.info(f"  Stage 2b normalized: '{m.name}' -> '{matched}'")
                m.name = matched
                normalized_count += 1
        if normalized_count:
            logger.info(f"  Stage 2b: {normalized_count} material names normalized to ontology")

        # Log results grouped by level
        assembly_mats = [m for m in result.materials if not m.component]
        component_mats = [m for m in result.materials if m.component]

        if assembly_mats:
            logger.info("  Assembly-level consumables:")
            for m in assembly_mats:
                tag = " [judge_addition]" if m.extraction_provenance == "judge_addition" else ""
                logger.info(f"    {m.name} (confidence: {m.confidence}){tag}")

        if component_mats:
            # Group by component for logging
            by_component: dict[str, list[ProcessConsumable]] = {}
            for m in component_mats:
                by_component.setdefault(m.component, []).append(m)
            for comp, mats in sorted(by_component.items()):
                logger.info(f"  Component '{comp}' consumables:")
                for m in mats:
                    tag = " [judge_addition]" if m.extraction_provenance == "judge_addition" else ""
                    logger.info(f"    {m.name} (confidence: {m.confidence}){tag}")

        return result

    async def _run_extraction(
        self, technology: str, components: list[str], usage: Optional[RunUsage]
    ) -> ProcessConsumablesGrouped:
        agent = get_extraction_agent(self.model_name)
        ontology_names = ", ".join(self.deps.material_ontology_list[:50])
        component_list = "\n".join(f"  - {c}" for c in components)
        prompt = (
            f"Technology: {technology}\n\n"
            f"Components:\n{component_list}\n\n"
            f"Materials ontology (reference, not a constraint): {ontology_names}\n\n"
            f"Identify process consumables at BOTH levels:\n"
            f"1. Assembly-level: consumables for assembling {technology} from its components\n"
            f"2. Component-level: for EACH component listed above, consumables for fabricating that component"
        )
        result = await agent.run(prompt, deps=self.deps)
        return result.output

    async def _run_judge(
        self, technology: str, components: list[str],
        extraction_output: ProcessConsumablesGrouped, usage: Optional[RunUsage]
    ) -> JudgeGroupedOutput:
        agent = get_judge_agent(self.model_name)

        # Format assembly-level proposals
        assembly_items = "\n".join(
            f"  - {m.name} (confidence: {m.confidence}): {m.reasoning}"
            for m in extraction_output.assembly_consumables
        ) or "  (none proposed)"

        # Format component-level proposals
        component_sections = []
        for cc in extraction_output.component_consumables:
            items = "\n".join(
                f"    - {m.name} (confidence: {m.confidence}): {m.reasoning}"
                for m in cc.materials
            ) or "    (none proposed)"
            component_sections.append(f"  {cc.component}:\n{items}")
        component_text = "\n".join(component_sections) or "  (none proposed)"

        prompt = (
            f"Technology: {technology}\n"
            f"Components: {', '.join(components)}\n\n"
            f"ASSEMBLY-LEVEL proposed consumables:\n{assembly_items}\n\n"
            f"COMPONENT-LEVEL proposed consumables:\n{component_text}\n\n"
            f"Review each item and add any missing critical process consumables at either level."
        )
        result = await agent.run(prompt, deps=self.deps)
        return result.output
