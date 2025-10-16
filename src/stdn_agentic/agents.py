"""
Pydantic AI agents for component, material, and country data extraction
"""

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, ModelRetry
from typing import List

from stdn_agentic.models import STDNDependencies
from stdn_agentic.utils import intersect_lists

# ============================================================================
# DATA MODELS FOR AGENTS
# ============================================================================

class ComponentList(BaseModel):
    """Structured output for technology components"""
    component_list: list[str] = Field(description="Primary technology components")


class ComponentMaterials(BaseModel):
    """Raw materials for a single component"""
    component: str
    raw_materials_list: list[str]


class ComponentMaterialsList(BaseModel):
    """Collection of components with their materials"""
    component_list: list[ComponentMaterials]


class CountryPercentage(BaseModel):
    """Single country production data"""
    country: str
    meas_unit: str
    amount: float
    percentage: float


class CountryList(BaseModel):
    """List of countries with production data"""
    country_list: List[CountryPercentage]


# ============================================================================
# COMPONENT EXTRACTION AGENT
# ============================================================================

component_agent = Agent[STDNDependencies, ComponentList](
    model='ollama:qwen2.5:7b',
    deps_type=STDNDependencies,
    output_type=ComponentList,
    system_prompt=(
        "You are an expert in technology manufacturing. "
        "Create a list only of the primary technology components used in manufacture. "
        "Do not include raw materials, tools, machines, tapes, adhesives, glues, or connectors. "
        "Return only component names."
    )
)


# ============================================================================
# MATERIALS EXTRACTION AGENT
# ============================================================================

materials_agent = Agent[STDNDependencies, ComponentMaterialsList](
    model='ollama:qwen2.5:7b',
    deps_type=STDNDependencies,
    output_type=ComponentMaterialsList,
    system_prompt=(
        "You are a materials science expert. "
        "Extract raw materials for components using ONLY elements from the provided ontology. "
        "Create a separate element for each raw material. "
        "Do not return imprecise descriptive phrases."
    )
)


@materials_agent.tool(retries=2)
async def validate_materials(
    ctx: RunContext[STDNDependencies],
    materials: list[str]
) -> list[str]:
    """Validate materials against restricted ontology"""
    validated = intersect_lists(materials, ctx.deps.material_ontology_list)
    
    if not validated and ctx.retry < 1:
        raise ModelRetry(
            f"No valid materials found. Use only materials from: {ctx.deps.material_ontology[:300]}..."
        )
    
    return validated


# ============================================================================
# COUNTRY DATA EXTRACTION AGENT
# ============================================================================

country_data_agent = Agent[None, CountryList](
    model='ollama:qwen2.5:7b',
    output_type=CountryList,
    system_prompt=(
        "You are an expert in global mineral production and supply chains. "
        "Provide accurate data about top producing countries for specific materials. "
        "Always include country name, production amount, unit of measure, and percentage of global supply."
    )
)


# ============================================================================
# AGENT ACCESSORS
# ============================================================================

def get_component_agent() -> Agent[STDNDependencies, ComponentList]:
    """Get the component extraction agent"""
    return component_agent


def get_materials_agent() -> Agent[STDNDependencies, ComponentMaterialsList]:
    """Get the materials extraction agent"""
    return materials_agent


def get_country_data_agent() -> Agent[None, CountryList]:
    """Get the country data extraction agent"""
    return country_data_agent
