"""
Pydantic AI agents for component and material extraction
"""

from pydantic_ai import Agent, RunContext, ModelRetry
from stdn_agentic.models import STDNDependencies, ComponentList, ComponentMaterialsList
from .utils import intersect_lists


# Component extraction agent
component_agent = Agent[STDNDependencies, ComponentList](
    model='ollama:qwen2.5:7b',  # Will be overridden with config
    deps_type=STDNDependencies,
    output_type=ComponentList,
    instructions=(
        "Create a list only of the primary technology components used in manufacture. "
        "Do not include raw materials, tools, machines, tapes, adhesives, glues, or connectors. "
        "Return only component names."
    )
)


# Materials extraction agent
materials_agent = Agent[STDNDependencies, ComponentMaterialsList](
    model='ollama:qwen2.5:7b',  # Will be overridden with config
    deps_type=STDNDependencies,
    output_type=ComponentMaterialsList,
    instructions=(
        "For each component, extract raw materials using ONLY elements from the provided ontology. "
        "Create a separate element for each raw material. Do not return imprecise descriptive phrases."
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


def get_component_agent() -> Agent[STDNDependencies, ComponentList]:
    """Get the component extraction agent"""
    return component_agent


def get_materials_agent() -> Agent[STDNDependencies, ComponentMaterialsList]:
    """Get the materials extraction agent"""
    return materials_agent
