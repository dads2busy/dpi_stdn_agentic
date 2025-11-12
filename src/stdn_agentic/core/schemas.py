"""
Shared Pydantic schemas for debate and consensus
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class ComponentProposal(BaseModel):
    """Single agent proposal for components"""
    agent_id: str
    components: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class MaterialProposal(BaseModel):
    """Single agent proposal for materials"""
    agent_id: str
    materials: List[str]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class DebateProposal(BaseModel):
    """Generic proposal in debate"""
    agent_id: str
    content: Dict
    confidence: float
    round_number: int


class DebateRound(BaseModel):
    """Single round of debate"""
    round_number: int
    proposals: List[DebateProposal]
    critiques: Dict[str, List[str]]
    convergence_score: float


class DebateResult(BaseModel):
    """Final debate result with consensus"""
    final_consensus: List[str]
    convergence_score: float
    rounds: List[DebateRound]
    dissenting_views: Optional[Dict[str, List[str]]] = None
