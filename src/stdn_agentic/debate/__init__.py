"""
Multi-agent debate system for consensus-building
"""

# Import from new debater.py
from .debater import AgentProposal, DebateRound, MultiAgentDebater

__all__ = [
    "MultiAgentDebater",
    "AgentProposal",
    "DebateRound",
]
