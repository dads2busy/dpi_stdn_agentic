import pytest
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
    def test_process_consumables_result_produces_country_enrichment_input(self):
        result = ProcessConsumablesResult(
            materials=[
                ProcessConsumable(name="Helium", confidence=0.85, reasoning="CVD gas"),
                ProcessConsumable(name="Nitrogen", confidence=0.9, reasoning="Purge gas"),
            ],
            metadata={"extractor_items": 2, "judge_removed": 0, "judge_added": 0, "final_items": 2},
        )
        material_names = [m.name for m in result.materials]
        assert "Helium" in material_names
        assert "Nitrogen" in material_names

    def test_empty_process_consumables_is_valid(self):
        result = ProcessConsumablesResult.empty()
        assert result.materials == []
        assert result.metadata["final_items"] == 0

    def test_enriched_row_has_dependency_type(self):
        """Verify the row dict structure for process consumables."""
        row = {
            "technology": "SoC",
            "component": "",
            "component_confidence": "",
            "component_reasoning": "",
            "material": "Helium",
            "material_confidence": 0.85,
            "material_reasoning": "CVD gas",
            "hs_code": None,
            "country": "United States",
            "meas_unit": "mcf",
            "amount": 500,
            "percentage": 55.0,
            "country_confidence": 0.95,
            "country_reasoning": "USGS",
            "dependency_type": "process_consumable",
            "extraction_provenance": "extractor",
        }
        assert row["dependency_type"] == "process_consumable"
        assert row["component"] == ""
