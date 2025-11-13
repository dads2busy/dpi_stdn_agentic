"""
Materials extraction agent for STDN (Supply Technology Dependency Network)

This module provides the agent responsible for extracting raw materials
from technology components using LLM analysis with intelligent ontology matching.

Key enhancements:
- Multi-strategy fuzzy matching (exact, variant, partial, word-level, similarity)
- Comprehensive null/empty validation to prevent 400 errors
- Common material variant mappings (lithium-ion -> Lithium, etc.)
- Chemical symbol matching (Li, Co, Ni, etc.)
- Progressive matching fallback strategies
"""

import logging
import os
from difflib import SequenceMatcher
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext

from ..models import STDNDependencies
from ..utils import intersect_lists

# Initialize logger
logger = logging.getLogger(__name__)


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
# Enhanced System Prompt
# ============================================================================

MATERIALS_SYSTEM_PROMPT = """You are an expert materials scientist and supply chain analyst specializing in manufacturing material identification.

Your task is to identify the RAW MATERIALS (NOT COMPONENTS OR SUBASSEMBLIES) used to manufacture each component of a technology product.

**CRITICAL**: Do NOT return component names, subassemblies, or finished parts. Return only RAW MATERIALS like metals, minerals, elements, and basic compounds.

EXAMPLES OF CORRECT MATERIALS:
✓ Lithium, Cobalt, Nickel, Copper, Aluminum, Steel, Silicon, Glass, Rare Earth Elements
✓ Gold, Silver, Tantalum, Tin, Tungsten, Platinum
✓ Graphite, Carbon fiber, Ceramic, Polymer, Rubber

EXAMPLES OF INCORRECT (these are components, NOT materials):
✗ Display module, Battery pack, Processor, Camera, Memory chip
✗ PCB, Antenna, Connector, Speaker, Touchscreen

**GUIDANCE**: The user prompt contains a list of standard material names. Use these names when possible, or use common variants or chemical names.

SELECTION GUIDELINES:
- Select 2-8 RAW MATERIALS per component (most critical materials)
- Prioritize strategic and critical materials (rare earths, lithium, cobalt, etc.)
- Include structural materials (aluminum, steel, copper, glass)
- Include semiconductor materials if applicable (silicon, gallium, germanium)
- Use standard material names or their common variants

For each component provided, return a JSON response with the component name and a list of RAW MATERIALS (not subcomponents).
"""


# ============================================================================
# Material Variant Mappings
# ============================================================================

VARIANT_MAP = {
    # Lithium variants
    "lithium-ion": "Lithium",
    "lithium carbonate": "Lithium",
    "lithium hydroxide": "Lithium",
    "li": "Lithium",
    # Aluminum variants
    "aluminium": "Aluminum",
    "aluminum alloy": "Aluminum",
    "al": "Aluminum",
    # Steel variants
    "stainless steel": "Steel",
    "carbon steel": "Steel",
    # Copper variants
    "copper wire": "Copper",
    "cu": "Copper",
    # Silicon variants
    "silicon wafer": "Silicon",
    "silicon chip": "Silicon",
    "si": "Silicon",
    # Cobalt variants
    "cobalt oxide": "Cobalt",
    "co": "Cobalt",
    # Nickel variants
    "nickel hydroxide": "Nickel",
    "ni": "Nickel",
    # Rare earth variants
    "ree": "Rare Earth Elements",
    "rare earths": "Rare Earth Elements",
    "neodymium": "Rare Earth Elements",
    "dysprosium": "Rare Earth Elements",
    "praseodymium": "Rare Earth Elements",
    "terbium": "Rare Earth Elements",
    "europium": "Rare Earth Elements",
    # Graphite variants
    "graphite anode": "Graphite",
    "synthetic graphite": "Graphite",
    # Glass variants
    "tempered glass": "Glass",
    "glass substrate": "Glass",
    "glass fiber": "Glass",
    "borosilicate": "Glass",
    # Plastic variants
    "polymer": "Plastic",
    "plastics": "Plastic",
    "plastic": "Plastic",
    "polypropylene": "Plastic",
    "polyethylene": "Plastic",
    "abs": "Plastic",
    "pet": "Plastic",
    "polyethylene terephthalate": "Plastic",
    "acrylonitrile butadiene styrene": "Plastic",
    # Indium variants
    "indium tin oxide": "Indium",
    "ito": "Indium",
    # Gallium variants
    "gallium arsenide": "Gallium",
    "gaas": "Gallium",
    "gallium nitride": "Gallium",
    "gan": "Gallium",
    # Other materials
    "neon": "Neon",
    "ferroelectric": "Ceramic",
    "titanium dioxide": "Titanium",
    "tungsten carbide": "Tungsten",
}


# ============================================================================
# Enhanced Material Matching Functions
# ============================================================================


def _exact_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Check for exact case-insensitive match.

    Args:
        material_lower: Lowercase material name
        ontology: List of ontology materials

    Returns:
        Matched ontology material or None
    """
    for ont_mat in ontology:
        if material_lower == ont_mat.lower():
            return ont_mat
    return None


def _variant_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Map common variants to standard names.

    Args:
        material_lower: Lowercase material name
        ontology: List of ontology materials

    Returns:
        Matched ontology material or None
    """
    if material_lower in VARIANT_MAP:
        mapped = VARIANT_MAP[material_lower]
        if mapped in ontology:
            return mapped
    return None


def _word_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Match individual significant words in material name.

    Args:
        material_lower: Lowercase material name
        ontology: List of ontology materials

    Returns:
        Matched ontology material or None
    """
    words = material_lower.split()

    # Try significant words (>= 4 chars)
    for word in words:
        if len(word) >= 4:
            for ont_mat in ontology:
                if word in ont_mat.lower():
                    logger.debug(f"Word match: '{material_lower}' -> '{ont_mat}' (via '{word}')")
                    return ont_mat

    return None


def _chemical_symbol_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Match chemical symbols (short terms 2-3 chars).

    Args:
        material_lower: Lowercase material name
        ontology: List of ontology materials

    Returns:
        Matched ontology material or None
    """
    words = material_lower.split()
    chemical_symbols = [w for w in words if 2 <= len(w) <= 3]

    for symbol in chemical_symbols:
        for ont_mat in ontology:
            # Check if symbol appears at start of ontology term
            if ont_mat.lower().startswith(symbol):
                logger.debug(
                    f"Chemical symbol match: '{material_lower}' -> '{ont_mat}' (via '{symbol}')"
                )
                return ont_mat

            # Check if symbol is exact match to ontology word
            if symbol in ont_mat.lower().split():
                logger.debug(
                    f"Chemical symbol match: '{material_lower}' -> '{ont_mat}' (via '{symbol}')"
                )
                return ont_mat

    return None


def _partial_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Check for partial substring match.

    Args:
        material_lower: Lowercase material name
        ontology: List of ontology materials

    Returns:
        Matched ontology material or None
    """
    for ont_mat in ontology:
        ont_lower = ont_mat.lower()
        # Avoid matching very short terms to prevent false positives
        if len(ont_lower) >= 4:
            if ont_lower in material_lower or material_lower in ont_lower:
                logger.debug(f"Partial match: '{material_lower}' -> '{ont_mat}'")
                return ont_mat

    return None


def _fuzzy_similarity_match(
    material_lower: str, ontology: List[str], min_similarity: float = 0.75
) -> Optional[str]:
    """
    Fuzzy similarity matching using SequenceMatcher.

    Args:
        material_lower: Lowercase material name
        ontology: List of ontology materials
        min_similarity: Minimum similarity score (0-1)

    Returns:
        Best matching ontology material or None
    """
    best_match = None
    best_score = 0.0

    for ont_mat in ontology:
        # Use SequenceMatcher for similarity
        similarity = SequenceMatcher(None, material_lower, ont_mat.lower()).ratio()

        if similarity > best_score and similarity >= min_similarity:
            best_score = similarity
            best_match = ont_mat

    if best_match:
        logger.debug(
            f"Fuzzy matched '{material_lower}' -> '{best_match}' (score: {best_score:.2f})"
        )
        return best_match

    return None


def enhanced_material_match(
    material: str, ontology: List[str], min_similarity: float = 0.75
) -> str:
    """
    Intelligently map a material name to the best match in the ontology.

    Uses multiple matching strategies in order of priority:
    1. Exact match (case-insensitive)
    2. Variant match (common aliases)
    3. Word-level match (any significant word overlap)
    4. Chemical symbol match (Li, Co, Ni, etc.)
    5. Partial substring match
    6. Fuzzy similarity match (75%+ similar)

    Args:
        material: Material name to match
        ontology: List of valid ontology materials
        min_similarity: Minimum similarity for fuzzy matching

    Returns:
        Best matching material from ontology, or original if no match
    """
    material_lower = material.lower().strip()

    # Try matching strategies in order of specificity
    match = (
        _exact_match(material_lower, ontology)
        or _variant_match(material_lower, ontology)
        or _word_match(material_lower, ontology)
        or _chemical_symbol_match(material_lower, ontology)
        or _partial_match(material_lower, ontology)
        or _fuzzy_similarity_match(material_lower, ontology, min_similarity)
    )

    if match:
        if match != material:
            logger.info(f"Mapped '{material}' -> '{match}'")
        return match
    else:
        logger.warning(f"No match found for material: '{material}'")
        return material


# ============================================================================
# Validation Function (Agent Tool)
# ============================================================================


async def validate_materials(
    ctx: RunContext[STDNDependencies],
    materials: List[str],
) -> List[str]:
    """Enhanced validation with comprehensive None/empty checks"""

    # CRITICAL: Check for None at the very start
    if materials is None:
        logger.error("validate_materials received None")
        if ctx.retry < 1:
            raise ModelRetry(
                "Materials list is None. Please return a valid list of material names as strings."
            )
        return []  # Don't retry again, just return empty

    # Check if it's actually a list
    if not isinstance(materials, list):
        logger.error(f"validate_materials received {type(materials)} instead of list")
        if ctx.retry < 1:
            raise ModelRetry(
                f"Expected a list of materials, but received {type(materials).__name__}. "
                "Please return a list of material name strings."
            )
        return []

    # Filter out None, empty, or non-string values
    valid_materials = []
    for m in materials:
        if m is None:
            continue
        if not isinstance(m, str):
            continue
        if not m.strip():
            continue
        valid_materials.append(m.strip())

    if not valid_materials:
        logger.warning("All materials were None/empty after filtering")
        if ctx.retry < 1:
            raise ModelRetry(
                "All provided materials were empty or invalid. "
                "Please provide valid material name strings."
            )
        return []  # Stop retrying, return empty

    # Rest of your existing validation code...
    validated = []
    unmapped = []

    for material in valid_materials:
        mapped = enhanced_material_match(material, ctx.deps.material_ontology_list)
        if mapped in ctx.deps.material_ontology_list:
            validated.append(mapped)
        else:
            unmapped.append(material)

    if validated:
        if unmapped:
            logger.info(f"Fuzzy-mapped {len(validated)} materials, couldn't map: {unmapped}")
        return validated

    # Only retry ONCE if nothing was mapped
    if ctx.retry < 1:
        ontology_sample = ", ".join(ctx.deps.material_ontology_list[:50])
        raise ModelRetry(
            f"Could not map any materials to ontology. Please use names from: {ontology_sample}..."
        )

    # After 1 retry, just return what we have
    return valid_materials if valid_materials else []


# ============================================================================
# Legacy Fuzzy Match Function (for backward compatibility)
# ============================================================================


def fuzzy_match_material(material: str, ontology: List[str]) -> str:
    """
    Legacy fuzzy match function (for backward compatibility).

    Calls the enhanced_material_match function.

    Args:
        material: Material name to match
        ontology: List of ontology materials

    Returns:
        Best matching material from ontology, or original if no match
    """
    return enhanced_material_match(material, ontology)


# ============================================================================
# Agent Initialization
# ============================================================================


def _get_configured_model() -> str:
    """Get model from config or environment"""
    model = os.environ.get("STDN_MODEL")
    if model:
        return model
    return os.environ.get("OLLAMA_MODEL", "ollama:qwen2:7b")


# Global agent instance
_agent = None


def get_materials_agent():
    """
    Get materials extraction agent with enhanced validation.

    Returns:
        Agent configured for materials extraction with fuzzy matching validation.
        The agent uses the validate_materials function as a tool to map
        LLM-generated material names to the standard ontology.

    Example:
        >>> agent = get_materials_agent()
        >>> result = await agent.run(
        ...     "Extract materials for battery component",
        ...     deps=STDNDependencies(...)
        ... )
        >>> materials = result.output.component_list
    """
    global _agent
    if _agent is None:
        _agent = Agent(
            model=_get_configured_model(),
            output_type=ComponentMaterialsList,
            deps_type=STDNDependencies,
            system_prompt=MATERIALS_SYSTEM_PROMPT,
        )
        # Register validation tool
        _agent.tool(validate_materials)
    return _agent


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "ComponentMaterials",
    "ComponentMaterialsList",
    "get_materials_agent",
    "enhanced_material_match",
    "fuzzy_match_material",  # Legacy
]
