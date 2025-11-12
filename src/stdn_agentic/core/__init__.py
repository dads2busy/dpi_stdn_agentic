"""
Core abstractions and shared utilities for STDN agents
"""

from .base_agent import BaseAgent
from .schemas import (
    DebateProposal,
    DebateRound,
    DebateResult,
    ComponentProposal,
    MaterialProposal,
)

__all__ = [
    "BaseAgent",
    "DebateProposal",
    "DebateRound",
    "DebateResult",
    "ComponentProposal",
    "MaterialProposal",
]
