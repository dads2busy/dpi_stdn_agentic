"""
Materials extraction agent for STDN (Supply Technology Dependency Network)
"""

import os
from typing import List

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext

from ..models import STDNDependencies
from ..utils import intersect_lists


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


# Updated system prompt
MATERIALS_SYSTEM_PROMPT = """You are an expert materials scientist and supply chain analyst specializing in manufacturing material identification.

Your task is to identify the RAW MATERIALS used to manufacture each component of a technology product.

**IMPORTANT**: Select materials from the provided ontology list in the user prompt. Use exact names.

SELECTION GUIDELINES:
- Select 2-8 materials per component (most critical materials)
- Prioritize strategic and critical materials (rare earths, lithium, cobalt, etc.)
- Include structural materials (aluminum, steel, copper, glass)
- Include semiconductor materials if applicable (silicon, gallium, germanium)

INCLUDE in your materials list:
- Primary constituent materials (metals, ceramics, polymers, composites)
- Critical and strategic materials
- Semiconductor materials
- Structural and functional materials

EXCLUDE from your materials list:
- Finished subcomponents (those belong in component list)
- Manufacturing processes or techniques
- Tools and equipment
- Adhesives, coatings, surface treatments (consumables)
- Generic substances or utilities

For each component provided, return a JSON response with the component name and a list of materials.
"""


async def validate_materials(
    ctx: RunContext[STDNDependencies],
    materials: List[str],
) -> List[str]:
    """Validate materials against ontology"""
    validated = intersect_lists(materials, ctx.deps.material_ontology_list)

    if not validated and ctx.retry < 1:
        invalid = set(materials) - set(ctx.deps.material_ontology_list)
        ontology_sample = ", ".join(ctx.deps.material_ontology_list[:30])
        raise ModelRetry(
            f"Invalid materials detected: {invalid}\n"
            f"You must use materials from the provided list. Examples: {ontology_sample}..."
        )

    return validated


def _get_configured_model() -> str:
    """Get model from config or environment"""
    model = os.environ.get("STDN_MODEL")
    if model:
        return model
    return os.environ.get("OLLAMA_MODEL", "ollama:qwen2:7b")


# Global agent instance
_agent = None


def get_materials_agent():
    """Get materials extraction agent"""
    global _agent
    if _agent is None:
        _agent = Agent(
            model=_get_configured_model(),
            output_type=ComponentMaterialsList,  # FIXED: output_type not result_type
            system_prompt=MATERIALS_SYSTEM_PROMPT,
        )
        _agent.tool(validate_materials)
    return _agent


__all__ = [
    "ComponentMaterials",
    "ComponentMaterialsList",
    "get_materials_agent",
]
