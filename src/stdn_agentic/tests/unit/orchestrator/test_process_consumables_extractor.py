import pytest
from unittest.mock import AsyncMock, Mock, patch

from stdn_agentic.agents.process_consumables_agent import (
    ProcessConsumable,
    ProcessConsumablesGrouped,
    ComponentConsumables,
    JudgeAction,
    JudgeVerdict,
    JudgeGroupedOutput,
    ComponentJudgeVerdicts,
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
    def test_result_from_judge_output_assembly_and_component(self):
        judge_out = JudgeGroupedOutput(
            assembly_verdicts=[
                JudgeVerdict(name="Solder flux", action=JudgeAction.KEEP, confidence=0.9, justification="ok"),
                JudgeVerdict(name="Water", action=JudgeAction.REMOVE, confidence=0.0, justification="too generic"),
            ],
            component_verdicts=[
                ComponentJudgeVerdicts(
                    component="Die",
                    verdicts=[
                        JudgeVerdict(name="Helium", action=JudgeAction.KEEP, confidence=0.95, justification="EUV purge"),
                        JudgeVerdict(name="Neon", action=JudgeAction.ADD, confidence=0.6, justification="laser gas"),
                    ],
                ),
            ],
        )
        result = ProcessConsumablesResult.from_judge_output(judge_out, extractor_count=3)
        assert len(result.materials) == 3  # Solder flux + Helium + Neon (Water removed)
        assert result.metadata["judge_removed"] == 1
        assert result.metadata["judge_added"] == 1
        assert result.metadata["assembly_items"] == 1
        assert result.metadata["component_items"] == 2

    def test_component_attribution(self):
        judge_out = JudgeGroupedOutput(
            assembly_verdicts=[
                JudgeVerdict(name="Flux", action=JudgeAction.KEEP, confidence=0.9, justification="ok"),
            ],
            component_verdicts=[
                ComponentJudgeVerdicts(
                    component="Die",
                    verdicts=[
                        JudgeVerdict(name="Helium", action=JudgeAction.KEEP, confidence=0.95, justification="EUV"),
                    ],
                ),
            ],
        )
        result = ProcessConsumablesResult.from_judge_output(judge_out, extractor_count=2)
        flux = next(m for m in result.materials if m.name == "Flux")
        helium = next(m for m in result.materials if m.name == "Helium")
        assert flux.component == ""  # assembly-level
        assert helium.component == "Die"  # component-level

    def test_empty_result(self):
        result = ProcessConsumablesResult.empty()
        assert len(result.materials) == 0
        assert result.metadata["extractor_items"] == 0
        assert result.metadata["assembly_items"] == 0
        assert result.metadata["component_items"] == 0

    def test_extraction_provenance_tracked(self):
        judge_out = JudgeGroupedOutput(
            assembly_verdicts=[],
            component_verdicts=[
                ComponentJudgeVerdicts(
                    component="Die",
                    verdicts=[
                        JudgeVerdict(name="Helium", action=JudgeAction.KEEP, confidence=0.85, justification="ok"),
                        JudgeVerdict(name="Neon", action=JudgeAction.ADD, confidence=0.6, justification="laser gas"),
                    ],
                ),
            ],
        )
        result = ProcessConsumablesResult.from_judge_output(judge_out, extractor_count=1)
        helium = next(m for m in result.materials if m.name == "Helium")
        neon = next(m for m in result.materials if m.name == "Neon")
        assert helium.extraction_provenance == "extractor"
        assert neon.extraction_provenance == "judge_addition"


class TestProcessConsumablesExtractor:
    @pytest.mark.asyncio
    async def test_extract_returns_result(self, mock_deps):
        extractor = ProcessConsumablesExtractor(
            deps=mock_deps, model_name="openai:gpt-4.1-mini"
        )

        extraction_output = ProcessConsumablesGrouped(
            assembly_consumables=[
                ProcessConsumable(name="Flux", confidence=0.9, reasoning="soldering"),
            ],
            component_consumables=[
                ComponentConsumables(
                    component="Die",
                    materials=[
                        ProcessConsumable(name="Helium", confidence=0.85, reasoning="EUV purge"),
                    ],
                ),
            ],
        )
        judge_output = JudgeGroupedOutput(
            assembly_verdicts=[
                JudgeVerdict(name="Flux", action=JudgeAction.KEEP, confidence=0.9, justification="ok"),
            ],
            component_verdicts=[
                ComponentJudgeVerdicts(
                    component="Die",
                    verdicts=[
                        JudgeVerdict(name="Helium", action=JudgeAction.KEEP, confidence=0.85, justification="ok"),
                    ],
                ),
            ],
        )

        with patch.object(extractor, "_run_extraction", new_callable=AsyncMock, return_value=extraction_output), \
             patch.object(extractor, "_run_judge", new_callable=AsyncMock, return_value=judge_output):
            result = await extractor.extract_process_consumables(
                technology="Smartphone SoC",
                components=["Die", "Package Substrate"],
            )

        assert len(result.materials) == 2
        helium = next(m for m in result.materials if m.name == "Helium")
        assert helium.component == "Die"

    @pytest.mark.asyncio
    async def test_extract_empty_when_extraction_returns_nothing(self, mock_deps):
        extractor = ProcessConsumablesExtractor(
            deps=mock_deps, model_name="openai:gpt-4.1-mini"
        )
        empty_output = ProcessConsumablesGrouped(
            assembly_consumables=[],
            component_consumables=[],
        )
        judge_output = JudgeGroupedOutput(
            assembly_verdicts=[],
            component_verdicts=[],
        )

        with patch.object(extractor, "_run_extraction", new_callable=AsyncMock, return_value=empty_output), \
             patch.object(extractor, "_run_judge", new_callable=AsyncMock, return_value=judge_output):
            result = await extractor.extract_process_consumables(
                technology="Simple Widget",
                components=["Frame"],
            )

        assert len(result.materials) == 0
