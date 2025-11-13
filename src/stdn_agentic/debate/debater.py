"""
Multi-agent debate system for STDN (Supply Technology Dependency Network)

This module implements an enhanced debate functionality for achieving consensus
between multiple agents analyzing technology components and materials.

Key enhancements:
- Critique-driven convergence with feedback influence
- Component name normalization for better matching
- Peer support calculation to boost consensus
- Adaptive voting thresholds based on convergence
- Confidence-weighted consensus building
"""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


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
# Enhanced Multi-Agent Debater
# ============================================================================


class MultiAgentDebater:
    """
    Enhanced multi-round debate between agents for consensus-building.

    Key improvements:
    - Critiques actively influence next round proposals
    - Component name normalization reduces false disagreements
    - Peer support boosts consensus formation
    - Adaptive voting thresholds based on convergence score
    - Confidence-weighted decision making

    The debate system runs iterative rounds where:
    - Agents propose components/materials with confidence scores
    - Agents generate critiques that influence subsequent rounds
    - Convergence is measured with enhanced normalization
    - Debate stops when convergence threshold is reached or max rounds exhausted

    This is particularly valuable for government/policy work where:
    - Multiple perspectives improve accuracy
    - Transparent reasoning is required
    - Dissenting views must be documented
    """

    def __init__(
        self,
        max_rounds: int = 3,
        convergence_threshold: float = 0.8,
        confidence_weight: float = 0.3,
        peer_support_boost: float = 0.15,
    ):
        """
        Initialize the enhanced multi-agent debater.

        Args:
            max_rounds: Maximum number of debate rounds (default: 3)
            convergence_threshold: Stop debate when convergence >= this value (default: 0.8)
            confidence_weight: Weight for confidence in voting (default: 0.3)
            peer_support_boost: Confidence boost per supporting agent (default: 0.15)
        """
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.confidence_weight = confidence_weight
        self.peer_support_boost = peer_support_boost
        self.debate_history: List[DebateRound] = []

    def normalize_component_name(self, name: str) -> str:
        """
        Normalize component names for better comparison.

        Removes common variations and trailing qualifiers to detect
        when agents are proposing the same component with different names.

        Args:
            name: Component name to normalize

        Returns:
            Normalized component name
        """
        # Remove common variations
        normalized = name.lower().strip()
        normalized = normalized.replace("-", " ").replace("_", " ")

        # Remove trailing qualifiers (system, module, unit, assembly, etc.)
        stopwords = [
            "system",
            "module",
            "unit",
            "assembly",
            "subsystem",
            "array",
            "pack",
            "device",
            "component",
        ]
        words = normalized.split()

        if len(words) > 1 and words[-1] in stopwords:
            normalized = " ".join(words[:-1])

        return normalized

    def calculate_peer_support(
        self, component: str, proposals: List[Dict], exclude_agent: Optional[str] = None
    ) -> int:
        """
        Calculate how many OTHER agents support this component.

        Args:
            component: Component name to check
            proposals: All agent proposals
            exclude_agent: Optional agent ID to exclude from count

        Returns:
            Number of supporting agents (excluding specified agent)
        """
        normalized = self.normalize_component_name(component)
        support_count = 0

        for proposal in proposals:
            # Skip if this is the excluded agent
            if exclude_agent and proposal.get("agent_id") == exclude_agent:
                continue

            prop_normalized = self.normalize_component_name(
                proposal.get("component", proposal.get("component_name", ""))
            )

            # If normalized names match, count as support
            if prop_normalized == normalized:
                support_count += 1

        return support_count

    def generate_critiques_with_influence(self, proposals: List[Dict], round_num: int) -> List[str]:
        """
        Generate critiques that actively influence next round.

        Critiques include:
        - Consensus signals for highly-supported components
        - Warnings for isolated proposals
        - Round-specific guidance for convergence

        Args:
            proposals: All proposals from current round
            round_num: Current round number

        Returns:
            List of critique strings to provide to agents
        """
        critiques = []
        component_support = defaultdict(list)

        # Group proposals by normalized name
        for prop in proposals:
            comp_name = prop.get("component", prop.get("component_name", ""))
            norm_name = self.normalize_component_name(comp_name)
            component_support[norm_name].append(prop)

        # Generate critiques based on support levels
        for norm_name, supporting_props in component_support.items():
            support_count = len(supporting_props)
            avg_confidence = sum(p.get("confidence", 0.8) for p in supporting_props) / support_count

            if support_count >= 2:
                # Strong consensus - encourage keeping
                original_names = [
                    p.get("component", p.get("component_name", "")) for p in supporting_props
                ]
                critiques.append(
                    f"✓ CONSENSUS: '{original_names[0]}' has {support_count} agent(s) "
                    f"support (avg confidence: {avg_confidence:.2f}). "
                    f"RECOMMENDATION: Include in final list."
                )
            elif support_count == 1:
                # Isolated proposal - question it
                prop = supporting_props[0]
                agent_id = prop.get("agent_id", "unknown")
                comp_name = prop.get("component", prop.get("component_name", ""))
                conf = prop.get("confidence", 0.8)

                critiques.append(
                    f"⚠️ ISOLATED: '{comp_name}' proposed by {agent_id} "
                    f"but no other agents support it (confidence: {conf:.2f}). "
                    f"RECOMMENDATION: Provide stronger justification or consider removing."
                )

        # Add round-specific guidance
        if round_num == 1:
            critiques.append(
                f"\n🎯 ROUND {round_num + 1} GUIDANCE: "
                f"Review peer proposals and either support strong candidates or "
                f"provide specific reasoning why your unique proposals are essential."
            )
        elif round_num >= 2:
            critiques.append(
                f"\n🎯 ROUND {round_num + 1} GUIDANCE: "
                f"Converge toward consensus. Drop weakly-justified unique proposals. "
                f"Support components with peer agreement."
            )

        return critiques

    def calculate_convergence(self, proposals: List[Dict]) -> float:
        """
        Calculate convergence score with enhanced normalization.

        Uses normalized component names to detect agreement even
        with minor naming variations.

        Args:
            proposals: All proposals from current round

        Returns:
            Convergence score (0.0 to 1.0)
        """
        if len(proposals) == 0:
            return 0.0

        # Normalize all component names
        normalized_components = [
            self.normalize_component_name(p.get("component", p.get("component_name", "")))
            for p in proposals
        ]

        # Count occurrences of each normalized component
        component_counts = Counter(normalized_components)

        # Calculate weighted convergence
        # Components with more support contribute more to convergence
        total_support = sum(component_counts.values())
        weighted_support = sum(count**2 for count in component_counts.values())

        # Normalize by theoretical maximum (all agents agree on everything)
        max_possible = len(proposals) ** 2

        convergence = weighted_support / max_possible if max_possible > 0 else 0.0

        return convergence

    async def run_debate(
        self, technology: str, initial_proposals: Dict[str, List[Dict]], component_agent, deps
    ) -> Dict:
        """
        Run multi-round debate with critique-driven convergence.

        Args:
            technology: Technology name
            initial_proposals: Initial agent proposals {agent_id: [proposals]}
            component_agent: Agent to use for refinement
            deps: Dependencies

        Returns:
            Dict with final consensus components and metadata
        """
        print(f"\n{'=' * 80}")
        print(f"DEBATE: {technology}")
        print(f"{'=' * 80}\n")

        current_proposals = initial_proposals

        for round_num in range(self.max_rounds):
            # Flatten proposals for analysis
            all_proposals = [
                {**prop, "agent_id": agent_id}
                for agent_id, props in current_proposals.items()
                for prop in props
            ]

            # Calculate convergence
            convergence = self.calculate_convergence(all_proposals)

            print(f"ROUND {round_num + 1}: ", end="")

            if convergence >= self.convergence_threshold:
                print(f"CONVERGENCE REACHED ({convergence * 100:.1f}%)")
                break
            else:
                print(f"Convergence: {convergence * 100:.1f}%")

            # Generate critiques for next round
            if round_num < self.max_rounds - 1:
                critiques = self.generate_critiques_with_influence(all_proposals, round_num)

                # Run next round with critiques
                current_proposals = await self._run_debate_round(
                    technology=technology,
                    previous_proposals=all_proposals,
                    critiques=critiques,
                    component_agent=component_agent,
                    deps=deps,
                    round_num=round_num + 1,
                )

        # Build final consensus
        final_proposals = [
            {**prop, "agent_id": agent_id}
            for agent_id, props in current_proposals.items()
            for prop in props
        ]

        consensus = self._build_adaptive_consensus(final_proposals, convergence)

        return {
            "technology": technology,
            "components": consensus,
            "confidence": convergence,
            "rounds": round_num + 1,
        }

    async def _run_debate_round(
        self,
        technology: str,
        previous_proposals: List[Dict],
        critiques: List[str],
        component_agent,
        deps,
        round_num: int,
    ) -> Dict[str, List[Dict]]:
        """
        Run a single debate round with critique feedback.

        Args:
            technology: Technology name
            previous_proposals: Proposals from previous round
            critiques: Generated critiques
            component_agent: Agent for refinement
            deps: Dependencies
            round_num: Current round number

        Returns:
            Dict mapping agent_id to refined proposals
        """

        # Format previous proposals for context
        prev_context = "\n".join(
            [
                f"- {p['agent_id']}: {p.get('component', p.get('component_name', ''))} "
                f"(confidence: {p.get('confidence', 0.8):.2f})"
                for p in previous_proposals
            ]
        )

        critique_text = "\n".join(critiques)

        new_proposals = {}

        # Each agent refines based on critiques
        for agent_num in range(1, 4):  # 3 agents
            agent_id = f"Agent_{agent_num}"

            prompt = f"""DEBATE ROUND {round_num}: Refine component extraction for {technology}

PREVIOUS ROUND PROPOSALS:
{prev_context}

PEER CRITIQUES AND GUIDANCE:
{critique_text}

YOUR TASK:
1. Review peer proposals and critiques
2. Support strong consensus candidates
3. Drop isolated proposals unless critically justified
4. Propose refined component list

Extract the primary components (aim for convergence with peers)."""

            try:
                result = await component_agent.run(prompt, deps=deps, model=deps.model)

                if result and result.output:
                    components = (
                        result.output.component_list
                        if hasattr(result.output, "component_list")
                        else result.output
                    )

                    new_proposals[agent_id] = [
                        {
                            "component": comp,
                            "confidence": 0.85,  # Could extract from result
                            "reasoning": "Refined based on debate",
                        }
                        for comp in components
                    ]
            except Exception as e:
                logger.error(f"Error in debate round {round_num} for {agent_id}: {e}")
                # Keep previous proposals if refinement fails
                prev_agent_proposals = [
                    p for p in previous_proposals if p.get("agent_id") == agent_id
                ]
                new_proposals[agent_id] = prev_agent_proposals

        return new_proposals

    def _build_adaptive_consensus(
        self, proposals: List[Dict], convergence_score: float
    ) -> List[str]:
        """
        Build consensus with adaptive voting threshold.

        Lower convergence = more inclusive threshold to avoid
        extracting too few components.

        Args:
            proposals: All final proposals
            convergence_score: Final convergence score

        Returns:
            List of consensus component names
        """
        # Adaptive threshold based on convergence
        if convergence_score >= 0.7:
            vote_threshold = 0.67  # Strong consensus required
        elif convergence_score >= 0.4:
            vote_threshold = 0.5  # Majority
        elif convergence_score >= 0.2:
            vote_threshold = 0.4  # Plurality
        else:
            vote_threshold = 0.33  # At least 1 of 3 agents

        # Count votes by normalized name
        component_votes = defaultdict(lambda: {"count": 0, "confidence": [], "original": None})

        for prop in proposals:
            comp_name = prop.get("component", prop.get("component_name", ""))
            norm_name = self.normalize_component_name(comp_name)

            component_votes[norm_name]["count"] += 1
            component_votes[norm_name]["confidence"].append(prop.get("confidence", 0.8))

            # Keep first original name seen
            if component_votes[norm_name]["original"] is None:
                component_votes[norm_name]["original"] = comp_name

        # Calculate total agents
        agent_ids = set(p.get("agent_id", "") for p in proposals)
        total_agents = len(agent_ids) if agent_ids else 3

        # Select components meeting threshold
        consensus = []

        for norm_name, data in component_votes.items():
            vote_ratio = data["count"] / total_agents
            avg_confidence = sum(data["confidence"]) / len(data["confidence"])

            # Weight vote by confidence
            weighted_score = (
                vote_ratio * (1 - self.confidence_weight) + avg_confidence * self.confidence_weight
            )

            if weighted_score >= vote_threshold:
                consensus.append(data["original"])

        logger.info(
            f"Consensus built: {len(consensus)} components "
            f"(threshold: {vote_threshold:.2f}, convergence: {convergence_score:.2f})"
        )

        return sorted(consensus)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "MultiAgentDebater",
    "AgentProposal",
    "DebateRound",
]
