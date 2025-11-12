"""
Materials extraction agent for STDN (Supply Technology Dependency Network)

This module provides the agent responsible for identifying raw materials used in
manufacturing components. It validates all identified materials against a
restricted materials ontology to ensure consistency and accuracy.

The materials agent maps each component to its constituent raw materials,
including metals, ceramics, polymers, and other manufacturing inputs.
"""

import os
from typing import List

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext

from ..models import STDNDependencies
from ..utils import intersect_lists

# ============================================================================
# Data Models
# ============================================================================


class ComponentMaterials(BaseModel):
    """Materials identified for a single component"""

    component: str = Field(description="Component name")
    raw_materials: List[str] = Field(
        alias="materials", description="List of raw materials used in this component"
    )


class ComponentMaterialsList(BaseModel):
    """Collection of components with their identified materials"""

    component_list: List[ComponentMaterials] = Field(
        description="List of components and their materials"
    )


# ============================================================================
# Materials Extraction Agent
# ============================================================================

MATERIALS_SYSTEM_PROMPT = """You are an expert materials scientist and supply chain analyst specializing in manufacturing material identification.

Your task is to identify the RAW MATERIALS used to manufacture each component of a technology product.

INCLUDE in your materials list:
- All primary constituent materials (metals, ceramics, polymers, composites)
- Critical materials and strategic materials (rare earths, lithium, cobalt, etc.)
- Semiconductor materials (silicon, gallium arsenide, etc.)
- Structural and functional materials

EXCLUDE from your materials list:
- Finished subcomponents that belong in the component list
- Manufacturing processes or techniques
- Tools and equipment
- Adhesives, coatings, or surface treatments (these are consumables)
- Generic substances or utilities

When identifying materials:
1. Consider what elements/compounds are actually in the physical product
2. Think about raw material supply chains and sourcing
3. Identify materials that create supply chain vulnerabilities
4. Use standard material names (e.g., "lithium", "cobalt", "rare earth elements", "silicon", not "RE materials" or "strategic metals")

For each component provided, return a JSON response with the component name and a list of raw materials.

Be accurate: Only identify materials you're confident are used
Be complete: Include all significant materials but not trace elements
Be specific: Use precise material names that can be sourced in supply chain data

Common materials to reference:
- Metals: aluminum, copper, cobalt, nickel, lithium, tungsten, molybdenum, rare earth elements, gold, silver, palladium
- Semiconductors: silicon, gallium, germanium, indium
- Ceramics: alumina, silica, yttria, zirconia
- Polymers: polyetheretherketone (PEEK), polycarbonate, epoxy, polyether
- Other: glass, graphite, carbon fiber, quartz"""


def _get_configured_model() -> str:
    """Get model from config or environment"""
    model = os.environ.get("STDN_MODEL")
    if model:
        return model
    return os.environ.get("OLLAMA_MODEL", "ollama:qwen2:7b")


# Initialize the materials extraction agent with deps_type specified
materials_agent = Agent(
    _get_configured_model(),
    output_type=ComponentMaterialsList,
    deps_type=STDNDependencies,  # ✓ ADD THIS - tells agent what deps type to expect
    system_prompt=MATERIALS_SYSTEM_PROMPT,
)


# ============================================================================
# Material Validation Tool
# ============================================================================


@materials_agent.tool  # ✓ Use decorator instead of .tool() method
async def validate_materials(
    ctx: RunContext[STDNDependencies],
    materials: List[str],
) -> List[str]:
    """
    Validate materials against the restricted materials ontology.

    This tool ensures all identified materials are in the approved ontology,
    preventing hallucinations or misspelled material names. If validation fails,
    triggers model retry to allow the LLM to correct its output.

    Args:
        ctx: Runtime context with dependencies including material ontology
        materials: List of material names to validate

    Returns:
        List of validated material names (intersection with ontology)

    Raises:
        ModelRetry: If no valid materials found and retries remain
    """
    # Validate against the materials ontology
    validated = intersect_lists(materials, ctx.deps.material_ontology_list)

    # If no matches and we have retries left, ask the model to try again
    if not validated and ctx.retry < 1:
        raise ModelRetry(
            f"No valid materials found in your list. "
            f"Please use materials from the ontology: {ctx.deps.material_ontology_list[:20]}... "
            f"(showing first 20 of {len(ctx.deps.material_ontology_list)} options)"
        )

    return validated


# ============================================================================
# Public API
# ============================================================================


def get_materials_agent() -> Agent[STDNDependencies, ComponentMaterialsList]:
    """
    Get the materials extraction agent.

    Returns:
        Agent configured for extracting raw materials from technology components.
        The agent takes a list of components and returns ComponentMaterialsList
        with materials identified for each component, validated against the
        materials ontology.

    Example:
        >>> agent = get_materials_agent()
        >>> result = await agent.run(
        ...     "For the display, battery, and processor components, identify all raw materials used.",
        ...     deps=STDNDependencies(...)
        ... )
        >>> print(result.data.component_list)
        [
            ComponentMaterials(component="display", raw_materials=["glass", "indium", "tin"]),
            ComponentMaterials(component="battery", raw_materials=["lithium", "cobalt", "nickel"]),
            ...
        ]
    """
    return materials_agent
