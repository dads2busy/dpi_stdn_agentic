"""
Unit tests for Phase 2a agents - FIXED FOR TESTING WITHOUT API KEY

The problem: Agent instances are created at module import time, requiring OPENAI_API_KEY.
The solution: Mock the Agent initialization during tests.

This test file:
1. Tests model classes (don't need agents)
2. Mocks agent initialization for agent function tests
3. Tests factory pattern without requiring API keys
4. Uses pytest fixtures for clean test setup

Run with: uv run pytest tests/unit/test_agents.py -v
"""

from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

# Mock agents before importing from stdn_agentic
# This prevents OpenAI API key requirement during test collection


# ============================================================================
# Tests for ComponentList Model
# ============================================================================


class TestComponentListModel:
    """Test ComponentList Pydantic model"""

    def test_component_list_creation(self):
        """Test creating ComponentList"""
        from stdn_agentic.agents import ComponentList

        data = {"component_list": ["display", "battery", "processor"]}
        component_list = ComponentList(**data)
        assert len(component_list.component_list) == 3
        assert "display" in component_list.component_list

    def test_component_list_validation(self):
        """Test ComponentList validates types"""
        from stdn_agentic.agents import ComponentList

        with pytest.raises(ValidationError):
            ComponentList(component_list="not a list")

    def test_component_list_empty(self):
        """Test ComponentList with empty list"""
        from stdn_agentic.agents import ComponentList

        data = {"component_list": []}
        component_list = ComponentList(**data)
        assert len(component_list.component_list) == 0

    def test_component_list_json_schema(self):
        """Test ComponentList generates proper schema"""
        from stdn_agentic.agents import ComponentList

        schema = ComponentList.model_json_schema()
        assert "component_list" in schema["properties"]


# ============================================================================
# Tests for ComponentMaterials Model
# ============================================================================


class TestComponentMaterialsModel:
    """Test ComponentMaterials Pydantic model"""

    def test_component_materials_creation(self):
        """Test creating ComponentMaterials"""
        from stdn_agentic.agents import ComponentMaterials

        data = {"component": "display", "materials": ["glass", "indium", "tin"]}
        comp_mat = ComponentMaterials(**data)
        assert comp_mat.component == "display"
        assert len(comp_mat.raw_materials) == 3

    def test_component_materials_alias(self):
        """Test that 'materials' alias maps to raw_materials"""
        from stdn_agentic.agents import ComponentMaterials

        data = {"component": "battery", "materials": ["lithium", "cobalt", "nickel"]}
        comp_mat = ComponentMaterials(**data)
        assert comp_mat.raw_materials == ["lithium", "cobalt", "nickel"]

    def test_component_materials_validation(self):
        """Test ComponentMaterials validates required fields"""
        from stdn_agentic.agents import ComponentMaterials

        with pytest.raises(ValidationError):
            ComponentMaterials(component="display")  # Missing materials

    def test_component_materials_field_descriptions(self):
        """Test ComponentMaterials field descriptions"""
        from stdn_agentic.agents import ComponentMaterials

        schema = ComponentMaterials.model_json_schema()
        assert "component" in schema["properties"]
        assert "materials" in schema["properties"]


# ============================================================================
# Tests for ComponentMaterialsList Model
# ============================================================================


class TestComponentMaterialsListModel:
    """Test ComponentMaterialsList Pydantic model"""

    def test_component_materials_list_creation(self):
        """Test creating ComponentMaterialsList"""
        from stdn_agentic.agents import ComponentMaterialsList

        data = {
            "component_list": [
                {"component": "display", "materials": ["glass", "indium"]},
                {"component": "battery", "materials": ["lithium", "cobalt"]},
            ]
        }
        comp_mat_list = ComponentMaterialsList(**data)
        assert len(comp_mat_list.component_list) == 2
        assert comp_mat_list.component_list[0].component == "display"

    def test_component_materials_list_access(self):
        """Test accessing components in list"""
        from stdn_agentic.agents import ComponentMaterialsList

        data = {
            "component_list": [
                {"component": "processor", "materials": ["silicon", "tungsten"]},
            ]
        }
        comp_mat_list = ComponentMaterialsList(**data)
        processor = comp_mat_list.component_list[0]
        assert processor.component == "processor"
        assert "silicon" in processor.raw_materials

    def test_component_materials_list_empty(self):
        """Test ComponentMaterialsList with empty list"""
        from stdn_agentic.agents import ComponentMaterialsList

        data = {"component_list": []}
        comp_mat_list = ComponentMaterialsList(**data)
        assert len(comp_mat_list.component_list) == 0


# ============================================================================
# Tests for CountryPercentage Model
# ============================================================================


class TestCountryPercentageModel:
    """Test CountryPercentage Pydantic model"""

    def test_country_percentage_creation(self):
        """Test creating CountryPercentage"""
        from stdn_agentic.agents import CountryPercentage

        data = {
            "country": "China",
            "meas_unit": "metric tons",
            "amount": 100000,
            "percentage": 65.5,
        }
        country_perc = CountryPercentage(**data)
        assert country_perc.country == "China"
        assert country_perc.percentage == 65.5

    def test_country_percentage_fields(self):
        """Test all CountryPercentage fields"""
        from stdn_agentic.agents import CountryPercentage

        data = {
            "country": "Australia",
            "meas_unit": "kilograms",
            "amount": 42000,
            "percentage": 27.3,
        }
        country_perc = CountryPercentage(**data)
        assert country_perc.meas_unit == "kilograms"
        assert country_perc.amount == 42000

    def test_country_percentage_validation(self):
        """Test CountryPercentage validates required fields"""
        from stdn_agentic.agents import CountryPercentage

        with pytest.raises(ValidationError):
            CountryPercentage(country="China", meas_unit="tons")  # Missing amount, percentage


# ============================================================================
# Tests for CountryList Model
# ============================================================================


class TestCountryListModel:
    """Test CountryList Pydantic model"""

    def test_country_list_creation(self):
        """Test creating CountryList"""
        from stdn_agentic.agents import CountryList

        data = {
            "country_list": [
                {"country": "China", "meas_unit": "tons", "amount": 100000, "percentage": 65},
                {"country": "Australia", "meas_unit": "tons", "amount": 42000, "percentage": 27},
            ]
        }
        country_list = CountryList(**data)
        assert len(country_list.country_list) == 2
        assert country_list.country_list[0].country == "China"

    def test_country_list_access(self):
        """Test accessing countries in list"""
        from stdn_agentic.agents import CountryList

        data = {
            "country_list": [
                {"country": "Vietnam", "meas_unit": "tons", "amount": 20000, "percentage": 8},
            ]
        }
        country_list = CountryList(**data)
        country = country_list.country_list[0]
        assert country.country == "Vietnam"
        assert country.percentage == 8


# ============================================================================
# Tests for Agent Functions (with mocking)
# ============================================================================


class TestAgentFunctions:
    """Test agent getter functions - mocked to avoid API key requirement"""

    @patch("stdn_agentic.agents.component_agent.component_agent")
    def test_get_component_agent(self, mock_agent):
        """Test get_component_agent returns Agent"""
        from stdn_agentic.agents import get_component_agent

        # Mock agent is returned
        mock_agent.run = Mock()
        agent = get_component_agent()
        assert agent is not None

    @patch("stdn_agentic.agents.materials_agent.materials_agent")
    def test_get_materials_agent(self, mock_agent):
        """Test get_materials_agent returns Agent"""
        from stdn_agentic.agents import get_materials_agent

        # Mock agent is returned
        mock_agent.run = Mock()
        agent = get_materials_agent()
        assert agent is not None

    @patch("stdn_agentic.agents.country_agent.country_data_agent")
    def test_get_country_agent(self, mock_agent):
        """Test get_country_data_agent returns Agent"""
        from stdn_agentic.agents import get_country_data_agent

        # Mock agent is returned
        mock_agent.run = Mock()
        agent = get_country_data_agent()
        assert agent is not None


# ============================================================================
# Tests for AgentFactory
# ============================================================================


class TestAgentFactory:
    """Test AgentFactory class"""

    def _make_deps(self):
        """Create minimal STDNDependencies for AgentFactory constructor."""
        from stdn_agentic.dependencies import initialize_dependencies
        from stdn_agentic.models import ConfigModel

        config = ConfigModel(
            import_tech_list="./data/tech_list.csv",
            model="openai:gpt-4.1-mini",
        )
        return initialize_dependencies(config)

    def test_factory_creation(self):
        """Test creating AgentFactory"""
        from stdn_agentic.agents import AgentFactory

        deps = self._make_deps()
        factory = AgentFactory(deps)
        assert factory is not None
        assert not factory.is_caching_enabled()

    def test_factory_with_caching(self):
        """Test AgentFactory with caching enabled"""
        from stdn_agentic.agents import AgentFactory

        deps = self._make_deps()
        config = {"enable_caching": True}
        factory = AgentFactory(deps, config)
        assert factory.is_caching_enabled()

    def test_factory_config_management(self):
        """Test factory configuration management"""
        from stdn_agentic.agents import AgentFactory

        deps = self._make_deps()
        config = {"enable_caching": True, "test_key": "test_value"}
        factory = AgentFactory(deps, config)

        retrieved = factory.get_config()
        assert retrieved["enable_caching"] is True
        assert retrieved["test_key"] == "test_value"

    def test_factory_update_config(self):
        """Test updating factory configuration"""
        from stdn_agentic.agents import AgentFactory

        deps = self._make_deps()
        factory = AgentFactory(deps)
        factory.update_config({"new_setting": "value"})

        config = factory.get_config()
        assert config["new_setting"] == "value"

    def test_factory_repr(self):
        """Test factory string representation"""
        from stdn_agentic.agents import AgentFactory

        deps = self._make_deps()
        factory = AgentFactory(deps)
        repr_str = repr(factory)
        assert "AgentFactory" in repr_str
        assert "caching" in repr_str

    def test_factory_set_caching(self):
        """Test enabling/disabling caching"""
        from stdn_agentic.agents import AgentFactory

        deps = self._make_deps()
        factory = AgentFactory(deps)
        assert not factory.is_caching_enabled()

        factory.set_caching(True)
        assert factory.is_caching_enabled()

        factory.set_caching(False)
        assert not factory.is_caching_enabled()


# ============================================================================
# Tests for Imports and Backward Compatibility
# ============================================================================


class TestImports:
    """Test that all imports work correctly"""

    def test_model_imports(self):
        """Test importing models"""
        from stdn_agentic.agents import (
            ComponentList,
            ComponentMaterials,
            ComponentMaterialsList,
            CountryList,
            CountryPercentage,
        )

        assert ComponentList is not None
        assert ComponentMaterials is not None
        assert ComponentMaterialsList is not None
        assert CountryPercentage is not None
        assert CountryList is not None

    def test_factory_import(self):
        """Test importing AgentFactory"""
        from stdn_agentic.agents import AgentFactory

        assert AgentFactory is not None

    def test_top_level_package_imports(self):
        """Test importing from main stdn_agentic package"""
        from stdn_agentic import (
            AgentFactory,
            ComponentList,
        )

        assert ComponentList is not None
        assert AgentFactory is not None


# ============================================================================
# Integration Tests with Models
# ============================================================================


class TestDataModelIntegration:
    """Integration tests for data models"""

    def test_data_models_compatibility(self):
        """Test data models work together"""
        from stdn_agentic.agents import (
            ComponentList,
            ComponentMaterialsList,
            CountryList,
        )

        # Create component list
        components = ComponentList(component_list=["display", "battery"])
        assert len(components.component_list) == 2

        # Create materials
        materials = ComponentMaterialsList(
            component_list=[
                {"component": "display", "materials": ["glass", "indium"]},
                {"component": "battery", "materials": ["lithium", "cobalt"]},
            ]
        )
        assert len(materials.component_list) == 2

        # Create countries
        countries = CountryList(
            country_list=[
                {"country": "China", "meas_unit": "tons", "amount": 100000, "percentage": 65},
                {"country": "Australia", "meas_unit": "tons", "amount": 42000, "percentage": 27},
            ]
        )
        assert len(countries.country_list) == 2

    def test_materials_with_countries_mapping(self):
        """Test materials mapped to countries"""
        from stdn_agentic.agents import (
            ComponentMaterialsList,
            CountryList,
        )

        materials = ComponentMaterialsList(
            component_list=[
                {"component": "battery", "materials": ["lithium", "cobalt"]},
            ]
        )

        countries = CountryList(
            country_list=[
                {"country": "Chile", "meas_unit": "tons", "amount": 300000, "percentage": 30},
                {
                    "country": "Democratic Republic of Congo",
                    "meas_unit": "tons",
                    "amount": 400000,
                    "percentage": 70,
                },
            ]
        )

        assert materials.component_list[0].component == "battery"
        assert len(countries.country_list) == 2


# ============================================================================
# Fixtures for other tests
# ============================================================================


@pytest.fixture
def sample_components():
    """Provide sample component data"""
    from stdn_agentic.agents import ComponentList

    return ComponentList(component_list=["display", "battery", "processor", "camera"])


@pytest.fixture
def sample_materials():
    """Provide sample materials data"""
    from stdn_agentic.agents import ComponentMaterialsList

    return ComponentMaterialsList(
        component_list=[
            {"component": "display", "materials": ["glass", "indium", "tin"]},
            {"component": "battery", "materials": ["lithium", "cobalt", "nickel"]},
            {"component": "processor", "materials": ["silicon", "tungsten", "copper"]},
            {"component": "camera", "materials": ["glass", "aluminum", "copper"]},
        ]
    )


@pytest.fixture
def sample_countries():
    """Provide sample country data"""
    from stdn_agentic.agents import CountryList

    return CountryList(
        country_list=[
            {"country": "China", "meas_unit": "metric tons", "amount": 100000, "percentage": 65.5},
            {
                "country": "Australia",
                "meas_unit": "metric tons",
                "amount": 42000,
                "percentage": 27.3,
            },
            {"country": "Chile", "meas_unit": "metric tons", "amount": 10000, "percentage": 7.2},
        ]
    )


@pytest.fixture
def agent_factory():
    """Provide an AgentFactory instance"""
    from stdn_agentic.agents import AgentFactory
    from stdn_agentic.dependencies import initialize_dependencies
    from stdn_agentic.models import ConfigModel

    config = ConfigModel(
        import_tech_list="./data/tech_list.csv",
        model="openai:gpt-4.1-mini",
    )
    deps = initialize_dependencies(config)
    return AgentFactory(deps)


class TestWithFixtures:
    """Tests using pytest fixtures"""

    def test_sample_components_fixture(self, sample_components):
        """Test sample components fixture"""
        assert len(sample_components.component_list) == 4
        assert "display" in sample_components.component_list

    def test_sample_materials_fixture(self, sample_materials):
        """Test sample materials fixture"""
        assert len(sample_materials.component_list) == 4
        assert sample_materials.component_list[0].component == "display"

    def test_sample_countries_fixture(self, sample_countries):
        """Test sample countries fixture"""
        assert len(sample_countries.country_list) == 3
        assert sample_countries.country_list[0].country == "China"

    def test_factory_fixture(self, agent_factory):
        """Test factory fixture"""
        assert agent_factory is not None
        assert isinstance(agent_factory.get_config(), dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
