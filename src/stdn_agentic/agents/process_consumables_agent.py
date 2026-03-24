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


class ProcessConsumablesList(BaseModel):
    """Extraction agent output: list of proposed process consumables."""

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

EXTRACTION_SYSTEM_PROMPT = """You are an expert in semiconductor and electronics manufacturing processes.

Your task is to identify PROCESS CONSUMABLES: materials that are CONSUMED DURING MANUFACTURING
and do NOT become part of the final product.

do NOT include materials that physically constitute the product structure. These are distinct from
raw materials (which become part of the product) and from capital equipment.

CATEGORIES OF PROCESS CONSUMABLES to consider:
- Deposition and reaction gases: reactive gases consumed in CVD/ALD/epitaxy (e.g., Silane,
  Ammonia, Tungsten Hexafluoride, Dichlorosilane, TEOS, TMA, TiCl4)
- Etch and chamber-clean gases: gases consumed in plasma etching and in-situ chamber cleaning
  (e.g., Chlorine, Hydrogen Fluoride gas, SF6, NF3, CF4, C4F8, BCl3, Oxygen)
- Environment and purge gases: gases used to create controlled atmospheres, purge optical paths,
  prevent contamination, or maintain vacuum environments (e.g., Helium, Nitrogen, Argon). Helium
  is critical in EUV lithography (optical path purge, source cooling), wafer backside cooling in
  lithography chucks, and as a leak-detection tracer gas.
- Carrier and cooling gases: gases used as carriers in ion implantation, vapor delivery, and for
  gas-phase thermal management (e.g., Helium, Hydrogen, Argon). Helium is the standard wafer
  backside cooling gas due to its high thermal conductivity.
- Anneal and forming gases: gases consumed in thermal processing steps (e.g., Hydrogen,
  Hydrogen/Nitrogen forming gas, Deuterium for reliability anneals)
- Wet etchants: liquid chemical etchants such as Hydrofluoric acid, Nitric acid, Phosphoric acid,
  Potassium Hydroxide, TMAH, Sulfuric acid, and Hydrogen Peroxide (often in mixtures like
  Piranha, SC-1, SC-2, BOE)
- Solvents: cleaning and stripping solvents (e.g., Acetone, IPA, NMP, PGMEA)
- Photoresists and developers: light-sensitive polymer films and their developer chemistries,
  applied and stripped during lithography
- CMP slurries: abrasive chemical-mechanical planarization slurries and pad conditioners
- Cooling and thermal management media: deionized water, liquid nitrogen, chilled fluids, and
  gas-phase coolants (including Helium for wafer chuck cooling)
- Ion implantation source materials: gases consumed as dopant sources (e.g., Boron Trifluoride,
  Phosphine, Arsine, Xenon)

IMPORTANT CONTEXT:
- You will receive a list of product components. Use this list as context for inferring which
  manufacturing processes are likely involved (e.g., a silicon wafer implies photolithography,
  etching, diffusion; a PCB implies soldering, cleaning).
- Think broadly about ALL materials consumed during manufacturing, not just process chemistry.
  Include gases needed to OPERATE equipment (e.g., Helium to purge EUV optical paths, Nitrogen
  for inert atmospheres in furnaces), gases consumed during TESTING (e.g., Helium for leak
  detection), and gases used for THERMAL MANAGEMENT (e.g., Helium for wafer backside cooling).
- The materials ontology provided is a reference to guide naming conventions; it is NOT a
  hard constraint. You may identify consumables not explicitly listed in the ontology if they
  are clearly used in the inferred manufacturing process.

CONFIDENCE SCALE (0.0 to 1.0):
- 0.9-1.0: Universally required for this type of manufacturing — virtually all fabs use it
- 0.8-0.89: Very commonly used — standard across most process flows for these components
- 0.7-0.79: Commonly used — typical in most implementations, some process variations skip it
- 0.6-0.69: Moderately likely — used in many but not all process flows
- 0.5-0.59: Uncertain — depends heavily on specific process choices
- 0.3-0.49: Low confidence — used in some niche or older process flows
- 0.0-0.29: Very low confidence — rarely used or highly speculative

For EACH consumable provide:
1. name: standard chemical or trade name
2. confidence: float 0.0–1.0 per the scale above
3. reasoning: 1–2 sentences describing the manufacturing step(s) that consume this material
   and why you assigned this confidence level
"""

JUDGE_SYSTEM_PROMPT = """You are a critical reviewer of process consumable extraction results for
semiconductor and electronics manufacturing analysis.

You will receive a list of proposed process consumables extracted by another agent. Your job is to
produce a verdict for each item using one of four actions: KEEP, REMOVE, ADJUST, or ADD.

REMOVAL criteria — remove items that are:
- Hallucinated: no plausible manufacturing pathway consumes this material for the given components
- Constituent materials: materials that physically remain in the final product (these are raw
  materials, not consumables)
- Too generic: entries like "water" or "chemicals" that provide no actionable supply-chain signal
  without further specificity

ADJUSTMENT criteria — adjust confidence when:
- The stated confidence is inconsistent with how universally the material is used
- New information (e.g., specific process node, technology generation) warrants a change

ADDITION criteria — you may ADD consumables that are clearly missing, subject to:
- Confidence for any ADD action must be capped at 0.7 (we do not allow high-confidence
  hallucinated additions; if you are very sure, lower the cap still applies)
- Only add items with strong manufacturing rationale tied to the inferred process steps

REQUIRED FORMAT for every verdict:
- name: the consumable name
- action: one of "keep", "remove", "adjust", or "add"
- confidence: revised confidence score (0.0–1.0; additions capped at 0.7)
- justification: a concise 1–2 sentence rationale explaining why you chose this action and
  confidence value. Every verdict MUST include a justification.

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
) -> Agent[STDNDependencies, ProcessConsumablesList]:
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
        output_type=ProcessConsumablesList,
        deps_type=STDNDependencies,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        retries=retries,
        output_retries=retries,
    )


def get_judge_agent(
    model_name: Optional[str] = None,
) -> Agent[STDNDependencies, JudgeOutput]:
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
        output_type=JudgeOutput,
        deps_type=STDNDependencies,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        retries=retries,
        output_retries=retries,
    )


__all__ = [
    "ProcessConsumable",
    "ProcessConsumablesList",
    "JudgeAction",
    "JudgeVerdict",
    "JudgeOutput",
    "EXTRACTION_SYSTEM_PROMPT",
    "JUDGE_SYSTEM_PROMPT",
    "get_extraction_agent",
    "get_judge_agent",
]
