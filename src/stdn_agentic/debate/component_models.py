from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass
class AgentProposal:
    """A component/material proposal from an agent."""

    agent_id: str
    component_name: str
    confidence: float  # Now dynamically set by LLM
    reasoning: str
    round: int


@dataclass
class DebateRound:
    """Results from one round of debate."""

    round_number: int
    proposals: List[AgentProposal]
    critiques: Dict[str, List[str]]
    convergence_score: float
    consensus_score: Optional[float] = None
    consensus_so_far: Optional[List[str]] = None


class ComponentWithConfidence(BaseModel):
    """A single component proposal with confidence and reasoning."""

    name: str = Field(description="Component name")
    confidence: float = Field(
        description="Confidence score (0.0 to 1.0) that this is a primary component",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(description="Brief justification for this component")


class DebateResponse(BaseModel):
    """Structured response from an agent in a debate round."""

    components: List[ComponentWithConfidence] = Field(
        description="List of proposed components with confidence scores"
    )
