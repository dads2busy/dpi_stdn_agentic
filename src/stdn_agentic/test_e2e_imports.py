"""Test all imports work together"""
import sys

print("Testing comprehensive imports...")

# Test main package
from stdn_agentic import (
    STDNDependencies,
    ConfigModel,
    ComponentList,
    ComponentMaterials,
    get_component_agent,
    get_materials_agent,
    get_country_data_agent,
    AgentFactory,
    __version__
)
print(f"✓ Main package imports (version {__version__})")

# Test agent submodule
from stdn_agentic.agents import (
    ComponentMaterialsList,
    CountryPercentage,
    CountryList
)
print("✓ Agent submodule imports")

# Test models
from stdn_agentic.models import STDNDependencies, ConfigModel
print("✓ Models import")

# Test utils (if refactored agents need them)
from stdn_agentic.utils import intersect_lists
print("✓ Utils import")

print("\n✓ All imports successful - refactoring complete!")
