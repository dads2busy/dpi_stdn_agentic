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


class MaterialWithConfidence(BaseModel):
    """A single material with confidence and reasoning."""

    name: str = Field(description="Material name (use standard terminology)")
    confidence: float = Field(
        description="Confidence score (0.0 to 1.0) that this material is essential", ge=0.0, le=1.0
    )
    reasoning: str = Field(description="Brief explanation of the material's role and confidence")


class ComponentMaterials(BaseModel):
    """Materials for a specific component with confidence scores."""

    component: str = Field(description="Component name")
    raw_materials: List[MaterialWithConfidence] = Field(
        alias="materials", description="Raw materials with confidence scores"
    )

    model_config = ConfigDict(populate_by_name=True)


class ComponentMaterialsList(BaseModel):
    """List of components with their materials."""

    component_list: List[ComponentMaterials] = Field(
        alias="componentlist", description="Components with their raw materials"
    )

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# Enhanced System Prompt
# ============================================================================

MATERIALS_SYSTEM_PROMPT = """You are an expert in materials science and manufacturing processes.

Your task is to identify the RAW MATERIALS required to manufacture each component of a technology product.

RAW MATERIALS are the fundamental inputs used in component manufacturing:
- Metals and alloys (copper, aluminum, steel, rare earth elements)
- Semiconductors and electronic materials (silicon, gallium, germanium)
- Ceramics and glass materials
- Polymers and plastics
- Chemical compounds
- Natural materials (rubber, graphite)

INCLUDE:
- Primary materials that make up the component's structure
- Critical materials for functionality (e.g., lithium in batteries)
- Coatings and surface treatments
- Essential chemical inputs

EXCLUDE:
- Finished components or subassemblies
- Manufacturing tools and equipment
- Process consumables (solvents, cleaning agents)
- Generic fasteners and connectors

CRITICAL: For each material you identify, you MUST provide THREE fields:

1. **Material Name**: Use standard industry terminology (e.g., "Lithium" not "Li-ion battery material")
   - Match USGS commodity classifications and industry ontologies
   - Use exact names or common variants from the provided ontology

2. **Confidence Score (0.0 to 1.0)**: Your confidence this material is essential for the component
   - **0.9-1.0**: Absolutely essential - cannot manufacture without it
   - **0.8-0.89**: Very confident - standard material, rarely substituted
   - **0.7-0.79**: Confident - commonly used, few alternatives
   - **0.6-0.69**: Moderately confident - commonly used but alternatives exist
   - **0.5-0.59**: Uncertain - one of several possible materials
   - **0.3-0.49**: Low confidence - optional or easily substituted
   - **0.0-0.29**: Very low confidence - rarely used alternative

3. **Reasoning**: Brief explanation (1-2 sentences) of:
   - The material's specific role in the component
   - Why this material is used (properties, function)
   - Your confidence assessment (why certain/uncertain)
   - Any alternatives that exist

Consider these factors when assigning confidence:
- Is this material universally used for this component type?
- Are there common substitutes or alternatives?
- How critical is this material to the component's function?
- What is the industry standard for this component?

**COMPLETE EXAMPLES:**

For component: "Battery Pack"

Materials:
- Lithium | 0.95 | Primary energy storage element in lithium-ion chemistry, absolutely essential for battery function with no viable alternatives at commercial scale
- Cobalt | 0.85 | Cathode material providing high energy density and stability, industry standard in NMC chemistry though LFP alternatives are emerging
- Nickel | 0.80 | Cathode material enabling high energy density, commonly used in NMC and NCA chemistries but ratio varies by design
- Copper | 0.90 | Essential electrical conductor for current collectors and internal wiring, universal across all battery designs
- Aluminum | 0.85 | Casing material and cathode current collector, industry standard though some designs use steel casings
- Graphite | 0.90 | Anode material critical for lithium intercalation, universal in commercial lithium-ion batteries
- Electrolyte | 0.92 | Ionic conductor enabling lithium transport, essential liquid or solid polymer component in all designs

For component: "Display Module (OLED)"

Materials:
- Glass | 0.95 | Substrate providing structural support and optical clarity, universally used in rigid OLED displays
- Indium | 0.90 | Key component of ITO (indium tin oxide) transparent conductor, industry standard though alternatives like graphene are being researched
- Rare Earth Elements | 0.75 | Used in OLED emissive layers and phosphors for color generation, alternatives exist but less common
- Plastic | 0.70 | Housing, bezels, and backing layers using various polymers, multiple material options available
- Organic Compounds | 0.95 | Essential emissive materials in OLED layers, defining characteristic of OLED technology
- Silver | 0.65 | Cathode electrode material, common but aluminum and other conductors can substitute

For component: "Solar Cells (monocrystalline silicon)"

Materials:
- Silicon | 0.98 | Core semiconductor material for photovoltaic conversion, absolutely essential and defines monocrystalline technology
- Silver | 0.85 | Front contact metallization for current collection, industry standard though copper alternatives emerging
- Aluminum | 0.90 | Back contact and frame material, universal in cell design
- Boron | 0.75 | P-type dopant for silicon, standard but gallium alternatives exist
- Phosphorus | 0.75 | N-type dopant creating PN junction, standard but arsenic alternatives exist

Return your response as a structured output with:
- componentlist: array of objects, each containing:
  - component: component name
  - materials: array of material objects with:
    - name: material name (string)
    - confidence: confidence score (float 0.0-1.0)
    - reasoning: justification (string)
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
            retries=5,
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
