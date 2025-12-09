# tests/test_component_confidence_mapping.py
"""
Quick test to verify component confidence is correctly transferred
from component extraction to country enrichment phase.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai import RunUsage

from stdn_agentic.agents import ComponentMaterials, ComponentMaterialsList
from stdn_agentic.agents.materials_agent import MaterialWithConfidence
from stdn_agentic.orchestrator.country_data_enricher import CountryDataEnricher


@pytest.fixture
def mock_country_repo():
    """Mock country data repository."""
    repo = AsyncMock()
    # Return sample country data
    repo.get_country_data = AsyncMock(
        return_value=[
            {
                "country": "China",
                "meas_unit": "metric tons",
                "amount": 10000.0,
                "percentage": 60.0,
                "hs_code": None,
                "confidence": 0.9,
                "reasoning": "Test data",
            }
        ]
    )
    return repo


@pytest.fixture
def component_confidence_map():
    """
    Component confidence map as created in process_technology().
    Keys are normalized: lowercase and stripped.
    """
    return {
        "battery (rechargeable lithium ion)": {  # ← Normalized key
            "confidence": 0.95,
            "reasoning": "Primary storage component with high peer support",
        },
        "display screen": {
            "confidence": 0.92,
            "reasoning": "Essential UI component",
        },
        "camera lens": {
            "confidence": 0.85,
            "reasoning": "Standard camera component",
        },
    }


@pytest.fixture
def materials_list_with_varied_formatting():
    """
    Materials list with component names that might have different formatting.
    This simulates what comes from materials extraction.
    """
    return ComponentMaterialsList(
        componentlist=[  # ← Use 'componentlist' not 'component_list'
            ComponentMaterials(
                component="Battery (Rechargeable Lithium Ion)",  # ← Mixed case
                materials=[  # ← Use 'materials' alias, not 'raw_materials'
                    MaterialWithConfidence(
                        name="Lithium",
                        confidence=0.95,
                        reasoning="Battery chemistry",
                    ),
                ],
            ),
            ComponentMaterials(
                component="Display Screen",  # ← Title case
                materials=[
                    MaterialWithConfidence(
                        name="Glass",
                        confidence=0.9,
                        reasoning="Screen material",
                    ),
                ],
            ),
            ComponentMaterials(
                component="camera lens",  # ← Lowercase
                materials=[
                    MaterialWithConfidence(
                        name="Glass",
                        confidence=0.88,
                        reasoning="Lens material",
                    ),
                ],
            ),
        ]
    )


@pytest.mark.asyncio
async def test_component_confidence_normalization(
    mock_country_repo,
    component_confidence_map,
    materials_list_with_varied_formatting,
):
    """
    Test that component confidence is correctly retrieved despite formatting differences.

    This verifies the fix where we normalize component names before lookup:
        normalized_component = component.lower().strip()
        comp_info = component_confidence_map.get(normalized_component, {})
    """

    enricher = CountryDataEnricher(
        country_repo=mock_country_repo,
        write_nulls=True,
        use_debate=False,
    )

    usage = RunUsage()

    enriched_data = await enricher.enrich_with_country_data(
        materials_list=materials_list_with_varied_formatting,
        technology="Smartphone",
        usage=usage,
        component_confidence_map=component_confidence_map,
    )

    # Verify we got data
    assert len(enriched_data) > 0

    # Group by component for easier testing
    by_component = {}
    for row in enriched_data:
        comp = row["component"]
        if comp not in by_component:
            by_component[comp] = []
        by_component[comp].append(row)

    # Test 1: Battery with mixed case should get confidence 0.95
    battery_rows = by_component.get("Battery (Rechargeable Lithium Ion)", [])
    assert len(battery_rows) > 0, "Battery component not found in output"
    assert battery_rows[0]["component_confidence"] == 0.95, (
        f"Battery confidence should be 0.95, got {battery_rows[0]['component_confidence']}"
    )
    assert "Primary storage" in battery_rows[0]["component_reasoning"]

    # Test 2: Display Screen with title case should get confidence 0.92
    display_rows = by_component.get("Display Screen", [])
    assert len(display_rows) > 0, "Display Screen component not found in output"
    assert display_rows[0]["component_confidence"] == 0.92, (
        f"Display Screen confidence should be 0.92, got {display_rows[0]['component_confidence']}"
    )

    # Test 3: camera lens with lowercase should get confidence 0.85
    camera_rows = by_component.get("camera lens", [])
    assert len(camera_rows) > 0, "camera lens component not found in output"
    assert camera_rows[0]["component_confidence"] == 0.85, (
        f"camera lens confidence should be 0.85, got {camera_rows[0]['component_confidence']}"
    )

    print("\n✅ All component confidence values correctly transferred!")
    print(f"   Battery: {battery_rows[0]['component_confidence']}")
    print(f"   Display: {display_rows[0]['component_confidence']}")
    print(f"   Camera: {camera_rows[0]['component_confidence']}")


@pytest.mark.asyncio
async def test_missing_component_confidence_defaults_to_zero(
    mock_country_repo,
    component_confidence_map,
):
    """
    Test that components not in the confidence map default to 0.0.
    """

    # Materials list with a component NOT in the confidence map
    materials_list = ComponentMaterialsList(
        componentlist=[  # ← Use 'componentlist' not 'component_list'
            ComponentMaterials(
                component="Unknown Component",
                materials=[  # ← Use 'materials' alias
                    MaterialWithConfidence(
                        name="Silicon",
                        confidence=0.9,
                        reasoning="Test material",
                    ),
                ],
            ),
        ]
    )

    enricher = CountryDataEnricher(
        country_repo=mock_country_repo,
        write_nulls=True,
        use_debate=False,
    )

    usage = RunUsage()

    enriched_data = await enricher.enrich_with_country_data(
        materials_list=materials_list,
        technology="Test Tech",
        usage=usage,
        component_confidence_map=component_confidence_map,
    )

    assert len(enriched_data) > 0
    assert enriched_data[0]["component_confidence"] == 0.0, (
        "Unknown component should default to 0.0 confidence"
    )

    print("\n✅ Unknown component correctly defaults to 0.0 confidence")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
