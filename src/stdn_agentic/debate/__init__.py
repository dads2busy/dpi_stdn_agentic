"""
Multi-agent debate system for consensus-building
"""

# Import from new debater.py
from .debater import AgentProposal, DebateRound, MultiAgentDebater
from .material_debater import MaterialDebater, MaterialDebateRound, MaterialProposal

__all__ = [
    "MultiAgentDebater",
    "AgentProposal",
    "DebateRound",
    "MaterialDebater",
    "MaterialProposal",
    "MaterialDebateRound",
]
