"""
Multi-agent debate system for consensus-building
"""

from .debater import AgentProposal, DebateRound, MultiAgentDebater
from .material_country_debater import CountryProposal, MaterialCountryDebater
from .material_debater import MaterialDebater
from .material_models import MaterialDebateRound, MaterialProposal

__all__ = [
    # Base debate
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
