"""
Materials extraction agent for STDN (Supply Technology Dependency Network)
"""

import os
from typing import List, Optional

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


# Updated system prompt - more flexible
MATERIALS_SYSTEM_PROMPT = """You are an expert materials scientist and supply chain analyst specializing in manufacturing material identification.

Your task is to identify the RAW MATERIALS used to manufacture each component of a technology product.

**GUIDANCE**: The user prompt contains a list of standard material names. Try to use these names when possible, but you may also use common variants or chemical names.

SELECTION GUIDELINES:
- Select 2-8 materials per component (most critical materials)
- Prioritize strategic and critical materials (rare earths, lithium, cobalt, etc.)
- Include structural materials (aluminum, steel, copper, glass)
- Include semiconductor materials if applicable (silicon, gallium, germanium)
- Use standard material names or their common variants

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

Examples of acceptable material names:
- "Lithium" or "lithium carbonate" or "lithium-ion"
- "Aluminum" or "aluminium" or "aluminum alloy"
- "Rare Earth Elements" or "REE" or "neodymium"
- "Steel" or "stainless steel" or "carbon steel"

For each component provided, return a JSON response with the component name and a list of materials.
"""


# Common material variant mappings
VARIANT_MAP = {
    "lithium-ion": "Lithium",
    "lithium carbonate": "Lithium",
    "lithium hydroxide": "Lithium",
    "li": "Lithium",
    "aluminium": "Aluminum",
    "aluminum alloy": "Aluminum",
    "al": "Aluminum",
    "stainless steel": "Steel",
    "carbon steel": "Steel",
    "copper wire": "Copper",
    "cu": "Copper",
    "silicon wafer": "Silicon",
    "silicon chip": "Silicon",
    "si": "Silicon",
    "cobalt oxide": "Cobalt",
    "co": "Cobalt",
    "nickel hydroxide": "Nickel",
    "ni": "Nickel",
    "ree": "Rare Earth Elements",
    "rare earths": "Rare Earth Elements",
    "neodymium": "Rare Earth Elements",
    "dysprosium": "Rare Earth Elements",
    "praseodymium": "Rare Earth Elements",
    "graphite anode": "Graphite",
    "synthetic graphite": "Graphite",
    "tempered glass": "Glass",
    "glass substrate": "Glass",
    "glass fiber": "Glass",
    "polymer": "Plastic",
    "plastics": "Plastic",
    "polypropylene": "Plastic",
    "polyethylene": "Plastic",
    "indium tin oxide": "Indium",
    "ito": "Indium",
    "gallium arsenide": "Gallium",
    "gaas": "Gallium",
    "neon": "Neon",
    "ferroelectric": "Ceramic",  # Ferroelectric materials are ceramics
    "abs": "Plastic",  # ABS plastic
    "pet": "Plastic",  # PET plastic
    "polyethylene terephthalate": "Plastic",
    "acrylonitrile butadiene styrene": "Plastic",
}


def _exact_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """Check for exact case-insensitive match"""
    for ont_mat in ontology:
        if material_lower == ont_mat.lower():
            return ont_mat
    return None


def _partial_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """Check for partial substring match"""
    for ont_mat in ontology:
        ont_lower = ont_mat.lower()
        if material_lower in ont_lower or ont_lower in material_lower:
            return ont_mat
    return None


def _variant_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """Map common variants to standard names"""
    if material_lower in VARIANT_MAP:
        mapped = VARIANT_MAP[material_lower]
        if mapped in ontology:
            return mapped
    return None


def _word_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """Match individual words in material name"""
    words = material_lower.split()
    for word in words:
        if len(word) > 3:  # Ignore very short words
            for ont_mat in ontology:
                if word in ont_mat.lower():
                    return ont_mat
    return None


def fuzzy_match_material(material: str, ontology: List[str]) -> str:
    """
    Intelligently map a material name to the best match in the ontology.

    This function handles:
    - Case insensitivity
    - Common variants (aluminum/aluminium, lithium/lithium-ion)
    - Chemical vs common names
    - Partial matches

    Args:
        material: The material name to match
        ontology: List of valid ontology materials

    Returns:
        Best matching material from ontology, or original if no match
    """
    material_lower = material.lower().strip()

    # Try matching strategies in order of specificity
    match = (
        _exact_match(material_lower, ontology)
        or _variant_match(material_lower, ontology)
        or _partial_match(material_lower, ontology)
        or _word_match(material_lower, ontology)
    )

    return match if match else material


async def validate_materials(
    ctx: RunContext[STDNDependencies],
    materials: List[str],
) -> List[str]:
    """
    Validate and map materials to ontology using fuzzy matching.

    This is more permissive than strict validation - it attempts to map
    material variants to standard ontology names.
    """
    validated = []
    unmapped = []

    for material in materials:
        # Try to map material to ontology
        mapped = fuzzy_match_material(material, ctx.deps.material_ontology_list)

        # Check if mapping was successful (found in ontology)
        if mapped in ctx.deps.material_ontology_list:
            validated.append(mapped)
        else:
            unmapped.append(material)

    # If we got some valid materials, that's good enough
    if validated:
        if unmapped:
            print(f"  ℹ️  Fuzzy-mapped {len(validated)} materials, couldn't map: {unmapped}")
        return validated

    # If NO materials could be mapped and we haven't retried yet, ask LLM to try again
    if not validated and ctx.retry < 1:
        ontology_sample = ", ".join(ctx.deps.material_ontology_list[:50])
        raise ModelRetry(
            f"Could not map any materials to ontology.\n"
            f"Attempted: {materials}\n"
            f"Please use names from this list or their common variants:\n"
            f"{ontology_sample}..."
        )

    # Last resort: return what we have
    return validated if validated else materials


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
            output_type=ComponentMaterialsList,
            deps_type=STDNDependencies,
            system_prompt=MATERIALS_SYSTEM_PROMPT,
        )
        _agent.tool(validate_materials)
    return _agent


__all__ = [
    "ComponentMaterials",
    "ComponentMaterialsList",
    "get_materials_agent",
]
