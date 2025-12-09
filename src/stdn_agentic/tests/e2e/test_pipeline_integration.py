"""
Integration test for pipeline and agent communication.
Tests the complete flow: ComponentAgent -> MaterialsAgent -> Pipeline
"""

import asyncio
import os
from pathlib import Path

import pytest

from stdn_agentic.agents import (
    ComponentList,
    ComponentMaterials,
    ComponentMaterialsList,
    get_component_agent,
    get_materials_agent,
)
from stdn_agentic.dependencies import initialize_dependencies
from stdn_agentic.models import ConfigModel, STDNDependencies


@pytest.fixture
def test_config():
    """Create test configuration."""
    return ConfigModel(
        import_tech_list="./data/tech_list.csv",
        model="ollama:qwen2.5:7b",
        output_dir="./output",
        output_csv_filename="test_output",
        usgs_database="./data/world_mineral_commodity_reports_2022-2025_v8.db",
        years_to_query=[2023, 2024],
        top_n_countries=5,
    )


@pytest.fixture
def test_deps(test_config):
    """Initialize test dependencies."""
    return initialize_dependencies(test_config)


class TestDataModels:
    """Test Pydantic models work correctly."""

    def test_component_list_creation(self):
        """Test ComponentList with both field name and alias."""
        # Using field name
        comp_list1 = ComponentList(component_list=["battery", "display"])
        assert len(comp_list1) == 2
        assert comp_list1.component_list == ["battery", "display"]

        # Using alias
        comp_list2 = ComponentList(componentlist=["battery", "display"])
        assert len(comp_list2) == 2
        assert comp_list2.component_list == ["battery", "display"]

        # Using model_validate
        comp_list3 = ComponentList.model_validate({"componentlist": ["battery"]})
        assert len(comp_list3) == 1

    def test_component_list_iteration(self):
        """Test ComponentList supports iteration."""
        comp_list = ComponentList(component_list=["battery", "display", "processor"])

        # Test __len__
        assert len(comp_list) == 3

        # Test __iter__
        components = list(comp_list)
        assert components == ["battery", "display", "processor"]

        # Test __getitem__
        assert comp_list[0] == "battery"
        assert comp_list[1] == "display"

    def test_component_materials_creation(self):
        """Test ComponentMaterials with field names and aliases."""
        # Using field name
        mat1 = ComponentMaterials(
            component="battery", raw_materials=["Lithium", "Cobalt", "Nickel"]
        )
        assert mat1.component == "battery"
        assert len(mat1.raw_materials) == 3

        # Using alias
        mat2 = ComponentMaterials(component="battery", materials=["Lithium", "Cobalt"])
        assert len(mat2.raw_materials) == 2

    def test_component_materials_list_creation(self):
        """Test ComponentMaterialsList with field names and aliases."""
        # Using field name
        mat_list1 = ComponentMaterialsList(
            component_list=[
                ComponentMaterials(component="battery", raw_materials=["Lithium"]),
                ComponentMaterials(component="display", raw_materials=["Glass"]),
            ]
        )
        assert len(mat_list1) == 2
        assert mat_list1.component_list[0].component == "battery"

        # Using alias
        mat_list2 = ComponentMaterialsList(
            componentlist=[
                ComponentMaterials(component="battery", materials=["Lithium"]),
            ]
        )
        assert len(mat_list2) == 1

        # Empty list
        mat_list3 = ComponentMaterialsList(component_list=[])
        assert len(mat_list3) == 0

    def test_component_materials_list_iteration(self):
        """Test ComponentMaterialsList supports iteration."""
        mat_list = ComponentMaterialsList(
            component_list=[
                ComponentMaterials(component="battery", raw_materials=["Lithium"]),
                ComponentMaterials(component="display", raw_materials=["Glass"]),
            ]
        )

        # Test iteration
        for cm in mat_list:
            assert isinstance(cm, ComponentMaterials)
            assert cm.component in ["battery", "display"]

        # Test indexing
        assert mat_list[0].component == "battery"


class TestAgentCommunication:
    """Test agent creation and basic communication."""

    def test_component_agent_creation(self):
        """Test component agent can be created."""
        agent = get_component_agent()
        assert agent is not None
        assert agent.output_type == ComponentList

    def test_materials_agent_creation(self):
        """Test materials agent can be created."""
        agent = get_materials_agent()
        assert agent is not None
        assert agent.output_type == ComponentMaterialsList

    @pytest.mark.asyncio
    async def test_component_agent_run(self, test_deps):
        """Test component agent produces valid output."""
        agent = get_component_agent()

        result = await agent.run("Extract the primary components of a smartphone", deps=test_deps)

        assert result is not None
        assert result.output is not None
        assert isinstance(result.output, ComponentList)
        assert len(result.output.component_list) > 0

        print(f"\n✓ Component agent extracted {len(result.output.component_list)} components:")
        for comp in result.output.component_list[:5]:
            print(f"  - {comp}")

    @pytest.mark.asyncio
    async def test_materials_agent_run(self, test_deps):
        """Test materials agent produces valid output."""
        agent = get_materials_agent()

        prompt = """Extract RAW MATERIALS for these components of a smartphone:
- Battery Pack
- Display Module

AVAILABLE RAW MATERIALS: Lithium, Cobalt, Nickel, Aluminum, Copper, Glass, Indium, Silicon

Return JSON with componentlist containing component and materials fields."""

        result = await agent.run(prompt, deps=test_deps)

        assert result is not None
        assert result.output is not None
        assert isinstance(result.output, ComponentMaterialsList)
        assert len(result.output.component_list) > 0

        print(
            f"\n✓ Materials agent extracted materials for {len(result.output.component_list)} components:"
        )
        for cm in result.output.component_list:
            print(f"  - {cm.component}: {', '.join(cm.raw_materials)}")


class TestPipelineFlow:
    """Test complete pipeline data flow."""

    @pytest.mark.asyncio
    async def test_component_to_materials_flow(self, test_deps):
        """Test data flows correctly from component agent to materials agent."""
        # Step 1: Extract components
        comp_agent = get_component_agent()
        comp_result = await comp_agent.run(
            "Extract the primary components of a smartphone", deps=test_deps
        )

        component_list = comp_result.output
        assert isinstance(component_list, ComponentList)
        assert len(component_list) > 0

        print(f"\n✓ Step 1: Extracted {len(component_list)} components")

        # Step 2: Extract materials for components
        mat_agent = get_materials_agent()

        components_str = "\n".join(f"- {comp}" for comp in component_list.component_list[:3])
        ontology_str = ", ".join(test_deps.material_ontology_list[:50])

        materials_prompt = f"""Extract RAW MATERIALS for these components of a smartphone:

{components_str}

AVAILABLE RAW MATERIALS: {ontology_str}

Return JSON with componentlist containing component and materials fields."""

        mat_result = await mat_agent.run(materials_prompt, deps=test_deps)

        materials_list = mat_result.output
        assert isinstance(materials_list, ComponentMaterialsList)
        assert len(materials_list) > 0

        print(f"✓ Step 2: Extracted materials for {len(materials_list)} components")

        # Step 3: Verify data structure
        total_materials = sum(len(cm.raw_materials) for cm in materials_list.component_list)
        print(f"✓ Step 3: Total materials identified: {total_materials}")

        for cm in materials_list.component_list:
            print(f"  - {cm.component}: {len(cm.raw_materials)} materials")
            assert cm.component is not None
            assert len(cm.raw_materials) > 0

    @pytest.mark.asyncio
    async def test_type_compatibility(self, test_deps):
        """Test that all types work together correctly."""
        # Create ComponentList
        comp_list = ComponentList(component_list=["battery", "display"])

        # Simulate pipeline passing ComponentList to extract_materials_safe
        # This mimics: materials_result = await self.extract_materials_safe(
        #     componentlist=ComponentList(component_list=components),
        #     ...
        # )

        def simulate_pipeline_call(componentlist: ComponentList) -> bool:
            """Simulate the type checking that happens in pipeline."""
            # This should not raise type errors
            assert isinstance(componentlist, ComponentList)
            assert len(componentlist.component_list) > 0

            # Test iteration
            for comp in componentlist.component_list:
                assert isinstance(comp, str)

            return True

        result = simulate_pipeline_call(comp_list)
        assert result is True
        print("\n✓ Type compatibility test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
