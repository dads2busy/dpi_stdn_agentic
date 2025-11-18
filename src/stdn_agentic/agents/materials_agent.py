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
from typing import Iterator, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, ModelRetry, RunContext

from ..models import STDNDependencies

logger = logging.getLogger(__name__)

# Environment flag to control tool usage (for backends that don't support tools well)
DISABLE_MATERIAL_TOOLS = os.getenv("STDN_DISABLE_MATERIAL_TOOLS", "1") == "1"

# ============================================================================
# Data Models
# ============================================================================


class ComponentMaterials(BaseModel):
    """Materials identified for a single component."""

    component: str = Field(description="Component name")
    raw_materials: List[str] = Field(alias="materials", description="List of raw materials")

    model_config = ConfigDict(populate_by_name=True)


class ComponentMaterialsList(BaseModel):
    """Collection of components with their materials."""

    component_list: List[ComponentMaterials] = Field(
        alias="componentlist", description="List of components and their materials"
    )

    model_config = ConfigDict(populate_by_name=True)

    def __len__(self) -> int:
        """Return the number of component materials."""
        return len(self.component_list)

    def __iter__(self) -> Iterator[ComponentMaterials]:
        """Allow iteration over component materials."""
        return iter(self.component_list)

    def __getitem__(self, index: int) -> ComponentMaterials:
        """Allow indexing."""
        return self.component_list[index]


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
    """
    for ont_mat in ontology:
        if material_lower == ont_mat.lower():
            return ont_mat
    return None


def _variant_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Map common variants to standard names.
    """
    if material_lower in VARIANT_MAP:
        mapped = VARIANT_MAP[material_lower]
        if mapped in ontology:
            return mapped
    return None


def _word_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Match individual significant words in material name.
    """
    words = material_lower.split()

    for word in words:
        if len(word) >= 4:
            for ont_mat in ontology:
                if word in ont_mat.lower():
                    logger.debug(
                        "Word match: '%s' -> '%s' (via '%s')", material_lower, ont_mat, word
                    )
                    return ont_mat

    return None


def _chemical_symbol_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Match chemical symbols (short terms 2-3 chars).
    """
    words = material_lower.split()
    chemical_symbols = [w for w in words if 2 <= len(w) <= 3]

    for symbol in chemical_symbols:
        for ont_mat in ontology:
            ont_lower = ont_mat.lower()

            if ont_lower.startswith(symbol):
                logger.debug(
                    "Chemical symbol match: '%s' -> '%s' (via '%s')",
                    material_lower,
                    ont_mat,
                    symbol,
                )
                return ont_mat

            if symbol in ont_lower.split():
                logger.debug(
                    "Chemical symbol match: '%s' -> '%s' (via '%s')",
                    material_lower,
                    ont_mat,
                    symbol,
                )
                return ont_mat

    return None


def _partial_match(material_lower: str, ontology: List[str]) -> Optional[str]:
    """
    Check for partial substring match.
    """
    for ont_mat in ontology:
        ont_lower = ont_mat.lower()
        if len(ont_lower) >= 4 and (ont_lower in material_lower or material_lower in ont_lower):
            logger.debug("Partial match: '%s' -> '%s'", material_lower, ont_mat)
            return ont_mat

    return None


def _fuzzy_similarity_match(
    material_lower: str,
    ontology: List[str],
    min_similarity: float = 0.75,
) -> Optional[str]:
    """
    Fuzzy similarity matching using SequenceMatcher.
    """
    best_match: Optional[str] = None
    best_score = 0.0

    for ont_mat in ontology:
        similarity = SequenceMatcher(None, material_lower, ont_mat.lower()).ratio()
        if similarity > best_score and similarity >= min_similarity:
            best_score = similarity
            best_match = ont_mat

    if best_match:
        logger.debug(
            "Fuzzy matched '%s' -> '%s' (score: %.2f)",
            material_lower,
            best_match,
            best_score,
        )
        return best_match

    return None


def enhanced_material_match(
    material: str,
    ontology: List[str],
    min_similarity: float = 0.75,
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
    """
    material_lower = material.lower().strip()

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
            logger.info("Mapped '%s' -> '%s'", material, match)
        return match

    logger.warning("No match found for material: '%s'", material)
    return material


# ============================================================================
# Validation Function (Agent Tool)
# ============================================================================


async def validate_materials(
    ctx: RunContext[STDNDependencies],
    materials: List[str],
) -> List[str]:
    """Enhanced validation with comprehensive None/empty checks."""
    if materials is None:
        logger.error("validate_materials received None")
        if ctx.retry < 1:
            raise ModelRetry(
                "Materials list is None. Please return a valid list of material names as strings.",
            )
        return []

    if not isinstance(materials, list):
        logger.error("validate_materials received %s instead of list", type(materials))
        if ctx.retry < 1:
            raise ModelRetry(
                "Expected a list of materials, but received "
                f"{type(materials).__name__}. "
                "Please return a list of material name strings.",
            )
        return []

    valid_materials: List[str] = []
    for material in materials:
        if material is None:
            continue
        if not isinstance(material, str):
            continue
        stripped = material.strip()
        if not stripped:
            continue
        valid_materials.append(stripped)

    if not valid_materials:
        logger.warning("All materials were None/empty after filtering")
        if ctx.retry < 1:
            raise ModelRetry(
                "All provided materials were empty or invalid. "
                "Please provide valid material name strings.",
            )
        return []

    validated: List[str] = []
    unmapped: List[str] = []

    for material in valid_materials:
        mapped = enhanced_material_match(material, ctx.deps.material_ontology_list)
        if mapped in ctx.deps.material_ontology_list:
            validated.append(mapped)
        else:
            unmapped.append(material)

    if validated:
        if unmapped:
            logger.info(
                "Fuzzy-mapped %d materials, couldn't map: %s",
                len(validated),
                unmapped,
            )
        return validated

    if ctx.retry < 1:
        ontology_sample = ", ".join(ctx.deps.material_ontology_list[:50])
        raise ModelRetry(
            f"Could not map any materials to ontology. Please use names from: {ontology_sample}...",
        )

    return valid_materials if valid_materials else []


# ============================================================================
# Legacy Fuzzy Match Function (for backward compatibility)
# ============================================================================


def fuzzy_match_material(material: str, ontology: List[str]) -> str:
    """
    Legacy fuzzy match function (for backward compatibility).
    Calls the enhanced_material_match function.
    """
    return enhanced_material_match(material, ontology)


# ============================================================================
# Agent Initialization
# ============================================================================


def _get_configured_model() -> str:
    """Get model from config or environment."""
    model = os.environ.get("STDN_MODEL")
    if model:
        return model
    return os.environ.get("OLLAMA_MODEL", "ollama:qwen2.5:7b")


_agent: Optional[Agent[STDNDependencies, ComponentMaterialsList]] = None


def get_materials_agent(
    model_name: Optional[str] = None,
) -> Agent[STDNDependencies, ComponentMaterialsList]:
    """
    Get materials extraction agent with enhanced validation.

    If model_name is provided, it overrides the default model from configuration
    or environment variables. The agent is cached and will be recreated if the
    requested model differs from the currently cached model.

    Returns:
        Agent configured for materials extraction with fuzzy matching validation.
        The agent uses the validate_materials function as a tool to map
        LLM-generated material names to the standard ontology when tools are
        enabled.
    """
    global _agent

    model_to_use = model_name or _get_configured_model()

    if _agent is None or getattr(_agent, "model", None) != model_to_use:
        _agent = Agent(
            model=model_to_use,
            output_type=ComponentMaterialsList,
            deps_type=STDNDependencies,
            system_prompt=MATERIALS_SYSTEM_PROMPT,
        )

        # DISABLED BY DEFAULT - Ollama backends often reject tool calls
        # Set STDN_DISABLE_MATERIAL_TOOLS=0 to enable if your backend supports it
        if not DISABLE_MATERIAL_TOOLS:
            _agent.tool(validate_materials)
            logger.info("Materials validation tool enabled")
        else:
            logger.info(
                "Materials validation tool DISABLED (Ollama compatibility mode). "
                "Set STDN_DISABLE_MATERIAL_TOOLS=0 to enable."
            )

    return _agent


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "ComponentMaterials",
    "ComponentMaterialsList",
    "get_materials_agent",
    "enhanced_material_match",
    "fuzzy_match_material",
]
