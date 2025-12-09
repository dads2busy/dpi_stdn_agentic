from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaterialProposal:
    """A material proposal from an agent for a specific component.

    This is a shared data model used across material debate phases.
    """

    agentid: str
    component: str
    material: str
    confidence: float
    reasoning: str
    normalizedcomponent: str
    normalizedmaterial: str
    round: int


@dataclass
class MaterialDebateRound:
    """Results from one round of material debate.

    Captures proposals, critiques, convergence score, and consensus so far.
    """

    roundnumber: int
    proposals: list[MaterialProposal]
    critiques: dict[str, dict[str, list[str]]]  # {component: {material: [critiques]}}
    convergencescore: float
    consensussofar: dict[str, list[str]]  # {component: [materials]}
