"""Public debate API for STDN.

This package exposes the main multi-agent debate primitives for
components, materials, and country production.
"""

from .component_debater import MultiAgentDebater
from .component_models import AgentProposal, DebateRound
from .material_country_debater import MaterialCountryDebater
from .material_country_models import CountryProposal
from .material_debater import MaterialDebater
from .material_models import MaterialDebateRound, MaterialProposal

__all__ = [
    # Base/component debate
    "MultiAgentDebater",
    "AgentProposal",
    "DebateRound",
    # Material debate
    "MaterialDebater",
    "MaterialProposal",
    "MaterialDebateRound",
    # Country debate
    "MaterialCountryDebater",
    "CountryProposal",
]
