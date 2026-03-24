"""Process consumables extraction agent and judge for Stage 2b.

Extracts materials consumed during manufacturing but not physically
present in the final product (e.g., process gases, etchants, solvents).
"""

import os
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ..models import STDNDependencies


class ProcessConsumable(BaseModel):
    """A single process consumable with provenance tracking."""

    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    extraction_provenance: str = Field(default="extractor")  # "extractor" or "judge_addition"
    component: str = Field(default="")  # empty = assembly-level, populated = component-level


class ComponentConsumables(BaseModel):
    """Process consumables for a single component's fabrication."""

    component: str
    materials: List[ProcessConsumable]


class ProcessConsumablesGrouped(BaseModel):
    """Extraction agent output: grouped by assembly-level and component-level."""

    assembly_consumables: List[ProcessConsumable] = Field(
        description="Consumables used in final assembly/integration of the product from its components"
    )
    component_consumables: List[ComponentConsumables] = Field(
        description="Consumables used to fabricate each individual component"
    )


# Keep flat list for backward compatibility with judge output
class ProcessConsumablesList(BaseModel):
    """Flat list of process consumables (used for judge input/output)."""

    materials: List[ProcessConsumable]


class JudgeAction(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"
    ADJUST = "adjust"
    ADD = "add"


class JudgeVerdict(BaseModel):
    """A single judge decision on a process consumable."""

    name: str
    action: JudgeAction
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str
    component: str = Field(default="")  # empty = assembly-level


class ComponentJudgeVerdicts(BaseModel):
    """Judge verdicts for a single component."""

    component: str
    verdicts: List[JudgeVerdict]


class JudgeGroupedOutput(BaseModel):
    """Judge output preserving component grouping."""

    assembly_verdicts: List[JudgeVerdict] = Field(
        description="Verdicts on assembly-level consumables"
    )
    component_verdicts: List[ComponentJudgeVerdicts] = Field(
        description="Verdicts on each component's consumables"
    )


class JudgeOutput(BaseModel):
    """Judge agent output: verdicts on each proposed item plus additions."""

    verdicts: List[JudgeVerdict]

    @property
    def kept_and_added(self) -> List[JudgeVerdict]:
        """Return only items that survive the judge (keep, adjust, add)."""
        return [v for v in self.verdicts if v.action != JudgeAction.REMOVE]


# ============================================================================
# System Prompts
# ============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are an expert in manufacturing processes across diverse industries including \
semiconductor fabrication, pharmaceuticals, biotechnology, energy, defense, agriculture, and general electronics.

Your task is to identify PROCESS CONSUMABLES: materials that are CONSUMED DURING MANUFACTURING
and do NOT become part of the final product.

Do NOT include materials that physically constitute the product structure. Process consumables are
distinct from raw materials (which become part of the product) and from capital equipment.

CATEGORIES OF PROCESS CONSUMABLES to consider (with examples spanning multiple industries):

1. Process gases — gases consumed in manufacturing reactions, deposition, or etching:
   - Semiconductor: Silane, Ammonia, Tungsten Hexafluoride, Chlorine, NF3, SF6, CF4
   - General: Oxygen (combustion, oxidation), Acetylene (welding), CO2 (carbonation, shielding)

2. Environment, purge, and shielding gases — gases that create controlled atmospheres, prevent
   contamination, purge optical paths, or shield processes from air:
   - Helium (EUV lithography purge, leak detection, wafer backside cooling, cryogenic systems,
     MRI magnet cooling, fiber optic manufacturing atmosphere)
   - Nitrogen (inert blanketing in reactors, food packaging, cryogenic grinding)
   - Argon (welding shielding gas, semiconductor sputtering, inert atmosphere for air-sensitive
     chemistry)

3. Carrier, cooling, and heat-transfer media — materials used for thermal management or as
   transport media that are consumed or lost during use:
   - Gases: Helium (highest thermal conductivity — wafer chuck cooling, cryocooler working
     fluid), Nitrogen, CO2
   - Liquids: deionized water, chilled glycol, liquid nitrogen, silicone oil, refrigerants
     (R-134a, R-410A)

4. Cleaning, sterilization, and surface preparation agents — chemicals consumed to clean,
   sterilize, or prepare surfaces:
   - Solvents: Acetone, IPA, NMP, PGMEA, ethanol, methanol
   - Acids/bases: HF, HNO3, H2SO4, H3PO4, KOH, NaOH, H2O2
   - Sterilants: ethylene oxide, peracetic acid, sodium hypochlorite, steam (autoclaving)
   - Detergents and surfactants

5. Reagents, media, and consumable chemistries — materials consumed in process-specific reactions:
   - Semiconductor: photoresists, developers (TMAH), CMP slurries, etch chemistries
   - Pharmaceutical: buffer solutions, culture media, chromatography resins, filter membranes,
     excipient binders consumed in process (not in final product)
   - Biotech: enzyme substrates, staining reagents, PCR primers, electrophoresis gels
   - Agriculture: nutrient solutions, pH adjusters, seed treatment chemicals

6. Lubricants, release agents, and process aids — materials that facilitate manufacturing but
   are not part of the product:
   - Mold release agents, die lubricants, magnesium stearate (tablet press lubricant)
   - Vacuum pump oil, hydraulic fluid consumed through leakage/degradation
   - Fluxes (soldering), anti-seize compounds, cutting fluids

7. Dopant and implantation source materials — materials consumed as sources for doping or
   ion implantation:
   - Boron Trifluoride, Phosphine, Arsine, Xenon (semiconductor)
   - Dopant gases or liquids specific to the technology

8. Testing and quality-control consumables — materials consumed during in-process testing:
   - Helium (leak detection — standard across vacuum systems, HVAC, medical devices)
   - Calibration gases, reference standards consumed during use

IMPORTANT CONTEXT:
- You will receive a technology name and its component list.
- You must identify process consumables at TWO levels:

  1. ASSEMBLY-LEVEL: consumables used to assemble/integrate the final product from its
     components (e.g., solder flux for PCB assembly, cleaning solvents between assembly steps,
     Helium for leak testing the finished assembly).

  2. COMPONENT-LEVEL: for EACH component, consumables used to FABRICATE that component.
     This is critical — a component like "SiC MOSFET" or "FinFET Logic Die" has its own
     manufacturing process (in a separate fab) that consumes process gases, etchants, etc.
     Think about what each component's factory needs, not just the final assembly factory.

- Think broadly: include materials consumed to OPERATE equipment (e.g., Helium to purge EUV
  optical paths), materials consumed during TESTING (e.g., Helium for leak detection), and
  materials consumed for THERMAL MANAGEMENT (e.g., refrigerants, cooling gases).
- The materials ontology provided is a reference for naming conventions; it is NOT a hard
  constraint. You may identify consumables not in the ontology if they are clearly consumed
  in the inferred manufacturing process.

CONFIDENCE SCALE (0.0 to 1.0):
- 0.9-1.0: Universally required — virtually all manufacturers of this technology use it
- 0.8-0.89: Very commonly used — standard across most process flows
- 0.7-0.79: Commonly used — typical in most implementations, some variations skip it
- 0.6-0.69: Moderately likely — used in many but not all process flows
- 0.5-0.59: Uncertain — depends heavily on specific process choices
- 0.3-0.49: Low confidence — used in niche or specialized variants only
- 0.0-0.29: Very low confidence — rarely used or highly speculative

OUTPUT FORMAT — you MUST return a structured response with two sections:

1. assembly_consumables: list of consumables for final product assembly/integration.
   For each: name, confidence, reasoning.

2. component_consumables: list of objects, one per component. For each component:
   - component: the component name (must match the provided component list)
   - materials: list of consumables for that component's fabrication.
     For each: name, confidence, reasoning.
"""

JUDGE_SYSTEM_PROMPT = """You are a critical reviewer of process consumable extraction results for
manufacturing supply chain analysis across diverse industries.

You will receive proposed process consumables organized in two sections:
1. ASSEMBLY-LEVEL: consumables for the final product assembly/integration
2. COMPONENT-LEVEL: consumables for each component's fabrication

Your job is to produce a verdict for each item using one of four actions: KEEP, REMOVE, ADJUST, or ADD.
You must preserve the grouping — assembly-level verdicts and per-component verdicts stay separate.

REMOVAL criteria — remove items that are:
- Hallucinated: no plausible manufacturing pathway consumes this material
- Constituent materials: materials that physically remain in the final product
- Too generic: entries like "water" or "chemicals" without specificity
- Misattributed: assigned to the wrong component or wrong level (assembly vs component)

ADJUSTMENT criteria — adjust confidence when:
- The stated confidence is inconsistent with how universally the material is used
- New information (e.g., specific process node, technology generation) warrants a change

ADDITION criteria — you may ADD consumables that are clearly missing, subject to:
- Confidence for any ADD action must be capped at 0.7
- Only add items with strong manufacturing rationale
- Specify which component or assembly level the addition belongs to

REQUIRED FORMAT — return two sections:

1. assembly_verdicts: list of verdicts for assembly-level consumables.
   For each: name, action, confidence, justification.

2. component_verdicts: list of objects, one per component. For each:
   - component: the component name
   - verdicts: list of verdicts for that component's consumables.
     For each: name, action, confidence, justification.

Be rigorous: it is better to remove a questionable item than to retain hallucinated consumables
that would pollute downstream supply-chain analysis.
"""


# ============================================================================
# Factory Functions
# ============================================================================


def _get_default_model() -> str:
    """Resolve default model from environment or fall back to openai:gpt-4.1-mini."""
    return os.getenv("STDN_MODEL", "openai:gpt-4.1-mini")


def get_extraction_agent(
    model_name: Optional[str] = None,
) -> Agent[STDNDependencies, ProcessConsumablesGrouped]:
    """Return a configured process-consumables extraction agent.

    Args:
        model_name: Optional model identifier (e.g. "openai:gpt-4.1-mini").
                    Falls back to STDN_MODEL env var, then "openai:gpt-4.1-mini".

    Returns:
        Configured pydantic-ai Agent for process consumables extraction.
    """
    model_to_use = model_name or _get_default_model()
    retries = int(os.getenv("STDN_AGENT_RETRIES", "5"))

    return Agent(
        model=model_to_use,
        output_type=ProcessConsumablesGrouped,
        deps_type=STDNDependencies,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        retries=retries,
        output_retries=retries,
    )


def get_judge_agent(
    model_name: Optional[str] = None,
) -> Agent[STDNDependencies, JudgeGroupedOutput]:
    """Return a configured process-consumables judge agent.

    Args:
        model_name: Optional model identifier (e.g. "openai:gpt-4.1-mini").
                    Falls back to STDN_MODEL env var, then "openai:gpt-4.1-mini".

    Returns:
        Configured pydantic-ai Agent for process consumables judging.
    """
    model_to_use = model_name or _get_default_model()
    retries = int(os.getenv("STDN_AGENT_RETRIES", "5"))

    return Agent(
        model=model_to_use,
        output_type=JudgeGroupedOutput,
        deps_type=STDNDependencies,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        retries=retries,
        output_retries=retries,
    )


__all__ = [
    "ProcessConsumable",
    "ProcessConsumablesList",
    "ProcessConsumablesGrouped",
    "ComponentConsumables",
    "JudgeAction",
    "JudgeVerdict",
    "JudgeOutput",
    "JudgeGroupedOutput",
    "ComponentJudgeVerdicts",
    "EXTRACTION_SYSTEM_PROMPT",
    "JUDGE_SYSTEM_PROMPT",
    "get_extraction_agent",
    "get_judge_agent",
]
