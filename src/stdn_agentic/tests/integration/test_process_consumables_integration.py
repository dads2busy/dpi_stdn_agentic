import json
import tempfile
import csv
import os

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


class TestJsonOutputStructure:
    def _write_test_csv(self, path: str):
        """Write a minimal CSV with both dependency types."""
        fieldnames = [
            "technology", "component", "component_confidence", "component_reasoning",
            "material", "material_confidence", "material_reasoning", "hs_code",
            "country", "meas_unit", "amount", "percentage",
            "country_confidence", "country_reasoning", "dependency_type",
            "extraction_provenance",
        ]
        rows = [
            {
                "technology": "SoC", "component": "Die", "component_confidence": "0.95",
                "component_reasoning": "core", "material": "Silicon",
                "material_confidence": "0.95", "material_reasoning": "substrate",
                "hs_code": "2804", "country": "China", "meas_unit": "mt",
                "amount": "1000", "percentage": "40",
                "country_confidence": "0.92", "country_reasoning": "USGS",
                "dependency_type": "constituent", "extraction_provenance": "",
            },
            {
                "technology": "SoC", "component": "", "component_confidence": "",
                "component_reasoning": "", "material": "Helium",
                "material_confidence": "0.85", "material_reasoning": "CVD gas",
                "hs_code": "", "country": "United States", "meas_unit": "mcf",
                "amount": "500", "percentage": "55",
                "country_confidence": "0.95", "country_reasoning": "USGS",
                "dependency_type": "process_consumable", "extraction_provenance": "extractor",
            },
        ]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_json_has_typed_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            self._write_test_csv(csv_path)

            from stdn_agentic.orchestrator.pipeline import build_structured_json
            result = build_structured_json(csv_path)

            assert "SoC" in result
            tech = result["SoC"]
            assert "constituent_dependencies" in tech
            assert "process_consumables" in tech

            components = tech["constituent_dependencies"]["components"]
            assert any(c["name"] == "Die" for c in components)
            die = next(c for c in components if c["name"] == "Die")
            assert any(m["name"] == "Silicon" for m in die["materials"])

            pc_materials = tech["process_consumables"]["materials"]
            assert any(m["name"] == "Helium" for m in pc_materials)
            helium = next(m for m in pc_materials if m["name"] == "Helium")
            assert helium["extraction_provenance"] == "extractor"
