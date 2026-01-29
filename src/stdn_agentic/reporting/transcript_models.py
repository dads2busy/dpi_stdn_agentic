"""
Data models for structured debate transcripts.

These models define the schema for capturing and formatting debate data
in a clear, auditable format for policy and analysis use.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SupportLevel(Enum):
    """Level of agent support for a proposal."""

    CONSENSUS = "consensus"  # All agents agree (3/3)
    MAJORITY = "majority"  # Majority agrees (2/3)
    ISOLATED = "isolated"  # Single agent only (1/3)


@dataclass
class ProposalItem:
    """A single proposed item (component or material) from an agent."""

    name: str
    confidence: float
    reasoning: str
    normalized_name: Optional[str] = None


@dataclass
class AgentProposal:
    """Complete proposal from a single agent."""

    agent_id: str
    role: str  # e.g., "Manufacturing Engineer", "Supply Chain Analyst"
    items: List[ProposalItem] = field(default_factory=list)
    technology_specification: Optional[str] = None
    technology_reasoning: Optional[str] = None


@dataclass
class CritiqueItem:
    """A critique for a specific item."""

    item_name: str
    support_level: SupportLevel
    supporting_agents: List[str]
    opposing_agents: List[str]
    avg_confidence: float
    critique_text: str


@dataclass
class RoundChanges:
    """Track what changed in a debate round."""

    items_added: List[str] = field(default_factory=list)
    items_removed: List[str] = field(default_factory=list)
    confidence_changes: Dict[str, tuple] = field(default_factory=dict)  # item -> (old, new)


@dataclass
class DebateRound:
    """Data for a single debate round."""

    round_num: int
    convergence_score: float
    threshold_reached: bool
    proposals: List[AgentProposal] = field(default_factory=list)
    critiques: List[CritiqueItem] = field(default_factory=list)
    changes_from_previous: Optional[RoundChanges] = None

    # Computed support analysis
    consensus_items: List[str] = field(default_factory=list)  # 3/3 support
    majority_items: List[str] = field(default_factory=list)  # 2/3 support
    isolated_items: List[str] = field(default_factory=list)  # 1/3 support


@dataclass
class ConsensusItem:
    """A final consensus item."""

    name: str
    confidence: float
    support_count: int  # How many agents proposed it
    total_agents: int
    reasoning: str


@dataclass
class StageResult:
    """Result of a single pipeline stage (components, materials, or countries)."""

    stage_name: str
    rounds_completed: int
    initial_convergence: float
    final_convergence: float
    threshold: float
    threshold_reached: bool

    # Round data
    rounds: List[DebateRound] = field(default_factory=list)

    # Final consensus
    consensus_items: List[ConsensusItem] = field(default_factory=list)

    # Summary stats
    total_proposed: int = 0
    total_in_consensus: int = 0
    isolated_filtered: int = 0


@dataclass
class CountryData:
    """Production data for a single country."""

    country: str
    production: float
    unit: str
    percentage: float
    confidence: float
    reasoning: str
    data_source: str  # "USGS Database" or "LLM Fallback"


@dataclass
class MaterialCountryData:
    """Country production data for a material."""

    material: str
    material_confidence: float
    data_source: str
    countries: List[CountryData] = field(default_factory=list)


@dataclass
class DebateTranscript:
    """Complete transcript for a technology analysis."""

    # Metadata
    technology: str
    technology_specification: str
    technology_reasoning: str
    timestamp: datetime

    # Configuration
    num_agents: int
    max_rounds: int
    convergence_threshold: float

    # Stage results
    component_stage: Optional[StageResult] = None
    material_stage: Optional[StageResult] = None
    country_data: List[MaterialCountryData] = field(default_factory=list)

    # Overall summary
    total_components: int = 0
    total_materials: int = 0
    total_countries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metadata": {
                "technology": self.technology,
                "technology_specification": self.technology_specification,
                "technology_reasoning": self.technology_reasoning,
                "timestamp": self.timestamp.isoformat(),
                "config": {
                    "num_agents": self.num_agents,
                    "max_rounds": self.max_rounds,
                    "convergence_threshold": self.convergence_threshold,
                },
            },
            "component_stage": self._stage_to_dict(self.component_stage),
            "material_stage": self._stage_to_dict(self.material_stage),
            "country_data": [self._country_data_to_dict(cd) for cd in self.country_data],
            "summary": {
                "total_components": self.total_components,
                "total_materials": self.total_materials,
                "total_countries": self.total_countries,
            },
        }

    def _stage_to_dict(self, stage: Optional[StageResult]) -> Optional[Dict]:
        if not stage:
            return None
        return {
            "stage_name": stage.stage_name,
            "rounds_completed": stage.rounds_completed,
            "initial_convergence": stage.initial_convergence,
            "final_convergence": stage.final_convergence,
            "threshold": stage.threshold,
            "threshold_reached": stage.threshold_reached,
            "rounds": [self._round_to_dict(r) for r in stage.rounds],
            "consensus": [self._consensus_item_to_dict(c) for c in stage.consensus_items],
            "stats": {
                "total_proposed": stage.total_proposed,
                "total_in_consensus": stage.total_in_consensus,
                "isolated_filtered": stage.isolated_filtered,
            },
        }

    def _round_to_dict(self, round_data: DebateRound) -> Dict:
        return {
            "round_num": round_data.round_num,
            "convergence_score": round_data.convergence_score,
            "threshold_reached": round_data.threshold_reached,
            "proposals": [self._proposal_to_dict(p) for p in round_data.proposals],
            "critiques": [self._critique_to_dict(c) for c in round_data.critiques],
            "changes": self._changes_to_dict(round_data.changes_from_previous),
            "support_analysis": {
                "consensus": round_data.consensus_items,
                "majority": round_data.majority_items,
                "isolated": round_data.isolated_items,
            },
        }

    def _proposal_to_dict(self, proposal: AgentProposal) -> Dict:
        return {
            "agent_id": proposal.agent_id,
            "role": proposal.role,
            "items": [
                {
                    "name": item.name,
                    "confidence": item.confidence,
                    "reasoning": item.reasoning,
                    "normalized_name": item.normalized_name,
                }
                for item in proposal.items
            ],
            "technology_specification": proposal.technology_specification,
            "technology_reasoning": proposal.technology_reasoning,
        }

    def _critique_to_dict(self, critique: CritiqueItem) -> Dict:
        return {
            "item_name": critique.item_name,
            "support_level": critique.support_level.value,
            "supporting_agents": critique.supporting_agents,
            "opposing_agents": critique.opposing_agents,
            "avg_confidence": critique.avg_confidence,
            "critique_text": critique.critique_text,
        }

    def _changes_to_dict(self, changes: Optional[RoundChanges]) -> Optional[Dict]:
        if not changes:
            return None
        return {
            "added": changes.items_added,
            "removed": changes.items_removed,
            "confidence_changes": {
                k: {"from": v[0], "to": v[1]} for k, v in changes.confidence_changes.items()
            },
        }

    def _consensus_item_to_dict(self, item: ConsensusItem) -> Dict:
        return {
            "name": item.name,
            "confidence": item.confidence,
            "support": f"{item.support_count}/{item.total_agents}",
            "reasoning": item.reasoning,
        }

    def _country_data_to_dict(self, data: MaterialCountryData) -> Dict:
        return {
            "material": data.material,
            "material_confidence": data.material_confidence,
            "data_source": data.data_source,
            "countries": [
                {
                    "country": c.country,
                    "production": c.production,
                    "unit": c.unit,
                    "percentage": c.percentage,
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                }
                for c in data.countries
            ],
        }


# Format constants for text output
TRANSCRIPT_WIDTH = 80
HEADER_CHAR = "="
SUBHEADER_CHAR = "-"


def format_header(text: str, char: str = HEADER_CHAR, width: int = TRANSCRIPT_WIDTH) -> str:
    """Format a section header."""
    return f"\n{char * width}\n{text}\n{char * width}\n"


def format_subheader(text: str, char: str = SUBHEADER_CHAR, width: int = TRANSCRIPT_WIDTH) -> str:
    """Format a subsection header."""
    return f"\n{text}\n{char * width}\n"
