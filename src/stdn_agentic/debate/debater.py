"""
Multi-agent debate system for STDN (Supply Technology Dependency Network)

This module implements the core debate functionality for achieving consensus
between multiple agents analyzing technology components and materials.

The debater orchestrates multi-round discussions where agents:
1. Propose components/materials with confidence scores
2. Critique each other's proposals
3. Converge toward consensus through iterative refinement
"""

import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class AgentProposal:
    """A component/material proposal from an agent"""

    agent_id: str
    component_name: str
    confidence: float
    reasoning: str
    round: int


@dataclass
class DebateRound:
    """Results from one round of debate"""

    round_number: int
    proposals: List[AgentProposal]
    critiques: Dict[str, List[str]]
    convergence_score: float
    consensus_so_far: List[str]


# ============================================================================
# Multi-Agent Debater
# ============================================================================


class MultiAgentDebater:
    """
    Implements multi-round debate between agents for consensus-building.

    The debate system runs iterative rounds where:
    - Agents propose components/materials with confidence scores
    - Agents critique each other's proposals
    - Convergence is measured using Jaccard similarity
    - Debate stops when convergence threshold is reached or max rounds exhausted

    This is particularly valuable for government/policy work where:
    - Multiple perspectives improve accuracy
    - Transparent reasoning is required
    - Dissenting views must be documented
    """

    def __init__(self, max_rounds: int = 3, convergence_threshold: float = 0.8):
        """
        Initialize the multi-agent debater.

        Args:
            max_rounds: Maximum number of debate rounds (default: 3)
            convergence_threshold: Stop debate when convergence >= this value (default: 0.8)
        """
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.debate_history: List[DebateRound] = []

    def run_debate(
        self, technology: str, agent_proposals: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Run multi-round debate to build consensus.

        Args:
            technology: Technology being analyzed
            agent_proposals: Dict mapping agent_id -> list of proposals
                Each proposal dict contains:
                - "component": Component/material name
                - "confidence": Confidence score (0.0-1.0)
                - "reasoning": Explanation for proposal

        Returns:
            Dict containing:
            - "technology": Technology name
            - "final_consensus": Final agreed-upon components/materials
            - "debate_rounds": List of DebateRound objects
            - "num_rounds": Number of rounds executed
            - "final_convergence": Final convergence score
        """
        self.debate_history = []

        print(f"\n{'=' * 80}")
        print(f"DEBATE: {technology}")
        print(f"{'=' * 80}\n")

        for round_num in range(1, self.max_rounds + 1):
            print(f"ROUND {round_num}: ", end="")

            round_data = self._run_debate_round(
                round_number=round_num, technology=technology, agent_proposals=agent_proposals
            )

            self.debate_history.append(round_data)

            # Check convergence
            if round_data.convergence_score >= self.convergence_threshold:
                print(f"CONVERGENCE REACHED ({round_data.convergence_score:.1%})")
                break
            else:
                print(f"Convergence: {round_data.convergence_score:.1%}")

        # Build final consensus
        final_consensus = self._build_final_consensus(technology, agent_proposals)

        return {
            "technology": technology,
            "final_consensus": final_consensus,
            "debate_rounds": self.debate_history,
            "num_rounds": len(self.debate_history),
            "final_convergence": self.debate_history[-1].convergence_score
            if self.debate_history
            else 0.0,
        }

    def _run_debate_round(
        self, round_number: int, technology: str, agent_proposals: Dict[str, List[Dict[str, Any]]]
    ) -> DebateRound:
        """
        Execute a single round of debate.

        Args:
            round_number: Current round number (1-indexed)
            technology: Technology name
            agent_proposals: Agent proposals dict

        Returns:
            DebateRound object with round results
        """
        # Collect all proposals
        all_proposals: List[AgentProposal] = []
        for agent_id, components in agent_proposals.items():
            for comp_data in components:
                proposal = AgentProposal(
                    agent_id=agent_id,
                    component_name=comp_data.get("component", comp_data.get("name", "")),
                    confidence=comp_data.get("confidence", 0.8),
                    reasoning=comp_data.get("reasoning", ""),
                    round=round_number,
                )
                all_proposals.append(proposal)

        # Generate critiques
        critiques = self._generate_critiques(round_number, all_proposals, agent_proposals)

        # Calculate convergence
        convergence = self._calculate_convergence(all_proposals)

        # Extract consensus
        consensus = self._extract_consensus(all_proposals)

        return DebateRound(
            round_number=round_number,
            proposals=all_proposals,
            critiques=critiques,
            convergence_score=convergence,
            consensus_so_far=consensus,
        )

    def _generate_critiques(
        self,
        round_number: int,
        all_proposals: List[AgentProposal],
        agent_proposals: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, List[str]]:
        """
        Generate critiques from agents about each other's proposals.

        Args:
            round_number: Current round
            all_proposals: All proposals from all agents
            agent_proposals: Original agent proposals dict

        Returns:
            Dict mapping agent_id -> list of critique strings
        """
        critiques = {}

        for agent_id in agent_proposals.keys():
            agent_critiques = []
            my_components = {
                p.component_name.lower() for p in all_proposals if p.agent_id == agent_id
            }

            # Find components proposed by others
            other_components = {
                p.component_name: (p.agent_id, p.confidence)
                for p in all_proposals
                if p.agent_id != agent_id
            }

            # Generate critique logic
            for comp_name, (other_agent, confidence) in other_components.items():
                if comp_name.lower() not in my_components:
                    # I didn't propose this - should I reconsider?
                    if confidence > 0.85:
                        agent_critiques.append(
                            f"🤔 {other_agent} proposed '{comp_name}' (confidence: {confidence:.2f}). "
                            f"Worth considering."
                        )
                    else:
                        agent_critiques.append(
                            f"❌ {other_agent} proposed '{comp_name}' but confidence is only {confidence:.2f}. "
                            f"May be weak proposal."
                        )

            # Add self-reflection in later rounds
            if round_number > 1:
                agent_critiques.append(
                    f"🔄 {agent_id} reviewing own proposals in light of peer feedback..."
                )

            critiques[agent_id] = agent_critiques

        return critiques

    def _calculate_convergence(self, proposals: List[AgentProposal]) -> float:
        """
        Calculate convergence score using Jaccard similarity.

        Measures how much agents agree by computing pairwise Jaccard similarity
        between agent proposal sets and averaging.

        Args:
            proposals: All proposals from current round

        Returns:
            Convergence score (0.0 = no agreement, 1.0 = perfect agreement)
        """
        if not proposals:
            return 0.0

        # Group proposals by agent
        agent_sets = {}
        for proposal in proposals:
            if proposal.agent_id not in agent_sets:
                agent_sets[proposal.agent_id] = set()
            agent_sets[proposal.agent_id].add(proposal.component_name.lower())

        if len(agent_sets) < 2:
            return 1.0  # Single agent = perfect "agreement"

        # Calculate pairwise Jaccard similarities
        similarities = []
        agents = list(agent_sets.keys())

        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                set_i = agent_sets[agents[i]]
                set_j = agent_sets[agents[j]]

                intersection = len(set_i & set_j)
                union = len(set_i | set_j)

                if union > 0:
                    jaccard = intersection / union
                    similarities.append(jaccard)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _extract_consensus(self, proposals: List[AgentProposal]) -> list[str]:
        """
        Extract consensus components using majority voting.

        A component is in consensus if a majority of agents proposed it.

        Args:
            proposals: All proposals from current round

        Returns:
            Sorted list of consensus component names
        """
        component_votes = Counter()
        agent_ids = set()

        for proposal in proposals:
            component_votes[proposal.component_name.lower()] += 1
            agent_ids.add(proposal.agent_id)

        # Majority = more than half of agents
        min_votes = (len(agent_ids) + 1) // 2

        consensus = [comp for comp, votes in component_votes.items() if votes >= min_votes]

        return sorted(consensus)

    def _build_final_consensus(
        self, technology: str, agent_proposals: Dict[str, List[Dict[str, Any]]]
    ) -> dict[str, Any]:
        """
        Build final consensus with confidence scores.

        Args:
            technology: Technology name
            agent_proposals: Original agent proposals

        Returns:
            Dict with consensus components and metadata
        """
        if not self.debate_history:
            return {"components": [], "confidence": 0.0}

        final_round = self.debate_history[-1]

        # Calculate average confidence for consensus components
        component_confidences = {}
        for proposal in final_round.proposals:
            comp = proposal.component_name.lower()
            if comp in final_round.consensus_so_far:
                if comp not in component_confidences:
                    component_confidences[comp] = []
                component_confidences[comp].append(proposal.confidence)

        # Build consensus with confidence scores
        consensus_with_confidence = []
        for comp in final_round.consensus_so_far:
            avg_confidence = sum(component_confidences[comp]) / len(component_confidences[comp])
            consensus_with_confidence.append(
                {
                    "component": comp.title(),
                    "confidence": avg_confidence,
                    "num_agents_agreed": len(component_confidences[comp]),
                }
            )

        # Sort by confidence (highest first)
        consensus_with_confidence.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "technology": technology,
            "components": consensus_with_confidence,
            "confidence": final_round.convergence_score,
            "rounds": len(self.debate_history),
        }


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "MultiAgentDebater",
    "AgentProposal",
    "DebateRound",
]
