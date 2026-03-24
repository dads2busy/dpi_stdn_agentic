"""
STDN Agents Module

Provides agent factories and models for STDN pipeline.
"""

from .component_agent import (
    ComponentList,
    ComponentWithConfidence,  # ADD THIS
    get_component_agent,
)
from .country_agent import (
    CountryList,
    CountryPercentage,
    get_country_data_agent,
)
from .factory import AgentFactory
from .materials_agent import (
    ComponentMaterials,
    ComponentMaterialsList,
    MaterialWithConfidence,  # ADD THIS if not already there
    get_materials_agent,
)
from .process_consumables_agent import (
    ProcessConsumable,
    ProcessConsumablesList,
    JudgeAction,
    JudgeVerdict,
    JudgeOutput,
    get_extraction_agent,
    get_judge_agent,
)

__all__ = [
    # Component agent
    "ComponentList",
    "ComponentWithConfidence",  # ADD THIS
    "get_component_agent",
    # Materials agent
    "ComponentMaterials",
    "ComponentMaterialsList",
    "MaterialWithConfidence",  # ADD THIS if not already there
    "get_materials_agent",
    # Country agent
    "CountryList",
    "CountryPercentage",
    "get_country_data_agent",
    # Process consumables agent
    "ProcessConsumable",
    "ProcessConsumablesList",
    "JudgeAction",
    "JudgeVerdict",
    "JudgeOutput",
    "get_extraction_agent",
    "get_judge_agent",
    # Factory
    "AgentFactory",
]
