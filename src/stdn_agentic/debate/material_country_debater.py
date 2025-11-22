"""
Material-Country mapping debate system for STDN

This module implements multi-agent debate for country production data when USGS
database lookups fail. Multiple mining experts propose and vote on top-producing
countries to reach consensus through simple voting.

Integration point: CountryDataRepository._query_llm_with_debate()
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional

from pydantic_ai import RunUsage

from ..agents import get_country_data_agent
from ..models import STDNDependencies

logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class CountryProposal:
    """A country production proposal from an agent."""

    agent_id: str
    country: str
    meas_unit: str
    amount: float
    percentage: float
    rank: int  # Cardinal rank (1-10)
    round_num: int
    confidence: float = 0.8  # ADD THIS - default for backward compatibility
    reasoning: str = ""  # ADD THIS


# ============================================================================
# MaterialCountryDebater
# ============================================================================


class MaterialCountryDebater:
    """
    Multi-agent consensus for country production data.

    Uses 3 materials mining experts to independently identify top 10 producing
    countries in cardinal order, then selects top 5 through simple voting.

    Key features:
    - All agents are "materials mining and production experts"
    - Each proposes top 10 countries in ranked order
    - Simple voting to select consensus top 5
    - No iterative refinement needed for factual data
    """

    def __init__(
        self,
        deps: STDNDependencies,
        num_agents: int = 3,
        top_n_proposed: int = 10,
        top_n_consensus: int = 5,
        debate_top_p: float = 0.0001,
    ) -> None:
        """
        Initialize material-country debater.

        Args:
            deps: STDN dependencies (for LLM access)
            num_agents: Number of expert agents (default: 3)
            top_n_proposed: Number of countries each agent proposes (default: 10)
            top_n_consensus: Number of countries in final consensus (default: 5)
            debate_top_p: Top-p for debate (low for deterministic)
        """
        self.deps = deps
        self.num_agents = num_agents
        self.top_n_proposed = top_n_proposed
        self.top_n_consensus = top_n_consensus
        self.debate_top_p = debate_top_p
        self.proposals: List[CountryProposal] = []

    async def run_debate(
        self,
        material: str,
        year: int,
        usage: Optional[RunUsage] = None,
    ) -> Dict[str, Any]:  # ← Changed from List[Dict[str, Any]]
        """
        Run multi-agent voting for country production data.

        Args:
            material: Material name
            year: Target year for production data
            usage: Optional usage tracker

        Returns:
            List of country data dicts with consensus top 5
        """
        print(f"\n{'=' * 60}")
        print(f"COUNTRY CONSENSUS: {material} ({year})")
        print(f"{'=' * 60}\n")

        # Phase 1: Independent proposals from experts
        all_proposals = await self._collect_expert_proposals(material, year, usage)

        if not all_proposals:
            print("✗ No proposals generated")
            return []

        # Phase 2: Simple voting to select top 5
        consensus = self._build_voting_consensus(all_proposals)

        print(f"\n✓ Final consensus: {len(consensus)} countries")
        for i, country_data in enumerate(consensus, 1):
            print(f"  {i}. {country_data['country']}: {country_data['percentage']:.1f}%")

        return {
            "consensus": consensus,
            "proposals": self.proposals,
            "num_agents": self.num_agents,
            "top_n_proposed": self.top_n_proposed,
        }

    async def _collect_expert_proposals(
        self,
        material: str,
        year: int,
        usage: Optional[RunUsage] = None,
    ) -> List[CountryProposal]:
        """Collect top 10 proposals from each mining expert."""
        print("PHASE 1: Expert Proposals")
        print("-" * 60)

        all_proposals: List[CountryProposal] = []

        # Create debate deps with low top_p for deterministic proposals
        debate_deps = replace(self.deps, top_p=self.debate_top_p)

        # All agents are mining experts
        expert_type = "materials mining and production expert"

        for agent_idx in range(self.num_agents):
            agent_id = f"Expert_{agent_idx + 1}"

            print(f"  {agent_id} ({expert_type})...")

            try:
                agent = get_country_data_agent()

                prompt = self._create_expert_prompt(material, year)

                # Use debate_deps with low top_p
                result = await agent.run(prompt, deps=debate_deps)

                if result and result.output:
                    country_list = result.output.country_list

                    # Store proposals with rank
                    for rank, cp in enumerate(country_list[: self.top_n_proposed], start=1):
                        proposal = CountryProposal(
                            agent_id=agent_id,
                            country=cp.country,
                            meas_unit=cp.measurement_unit or "metric tons",
                            amount=cp.amount,
                            percentage=cp.percentage,
                            rank=rank,
                            round_num=1,
                            confidence=cp.confidence,
                            reasoning=cp.reasoning,
                        )
                        all_proposals.append(proposal)

                    print(f"    ✓ Proposed {len(country_list[: self.top_n_proposed])} countries")

            except Exception as e:
                logger.error(f"Agent {agent_id} failed: {e}")
                print(f"    ✗ Failed: {e}")

        return all_proposals

    def _create_expert_prompt(self, material: str, year: int) -> str:
        """Create prompt for mining expert to rank top 10 countries."""
        return f"""You are a materials mining and production expert.

Provide the top {self.top_n_proposed} countries that produced {material} in {year},
ranked in descending order by production volume.

Requirements:
- List countries in cardinal order (1st, 2nd, 3rd, etc.)
- Use the most recent data available (preferably {year} or within 2-3 years)
- Provide specific numeric production amounts with units
- Include percentage of global production for each country
- Use standard country names (not abbreviations)
- Focus on major producers with significant global market share

Return exactly {self.top_n_proposed} countries in order of production volume."""

    def _build_voting_consensus(
        self,
        all_proposals: List[CountryProposal],
    ) -> List[Dict[str, Any]]:
        """
        Build consensus using confidence-weighted Borda voting.

        Returns:
            List of country dicts with confidence and reasoning
        """
        if not all_proposals:
            return []

        # Group proposals by country (case-insensitive)
        country_data: Dict[str, List[CountryProposal]] = defaultdict(list)

        for prop in all_proposals:
            country_lower = prop.country.lower().strip()
            country_data[country_lower].append(prop)

        # Calculate Borda scores (existing logic)
        borda_scores: Dict[str, float] = defaultdict(float)
        for prop in all_proposals:
            country_lower = prop.country.lower().strip()
            # Borda: top rank gets n points, second gets n-1, etc.
            points = self.top_n_proposed - prop.rank + 1
            borda_scores[country_lower] += points

        # Build consensus with confidence
        consensus = []

        for country_lower, proposals in country_data.items():
            if not proposals:
                continue

            # Calculate weighted average confidence - DEFINE IT HERE
            total_confidence = sum(p.confidence for p in proposals)
            avg_confidence = total_confidence / len(proposals)

            # Calculate weighted average production values
            total_amount = sum(p.amount for p in proposals)
            avg_amount = total_amount / len(proposals)

            total_percentage = sum(p.percentage for p in proposals)
            avg_percentage = total_percentage / len(proposals)

            # Get best reasoning (from highest confidence proposal)
            best_proposal = max(proposals, key=lambda p: p.confidence)
            best_reasoning = best_proposal.reasoning if best_proposal.reasoning else ""

            # Use original country name (not lowercased)
            country_name = proposals[0].country
            common_unit = proposals[0].meas_unit

            # Get Borda score
            borda_score = borda_scores.get(country_lower, 0.0)

            consensus.append(
                {
                    "country": country_name,
                    "meas_unit": common_unit,
                    "amount": avg_amount,
                    "percentage": avg_percentage,
                    "borda_score": borda_score,
                    "num_votes": len(proposals),
                    "confidence": avg_confidence,
                    "reasoning": best_reasoning,
                }
            )

        # Sort by Borda score descending
        consensus.sort(key=lambda x: x["borda_score"], reverse=True)

        # Return top N
        return consensus[: self.top_n_consensus]

    def format_debate_for_transcript(
        self,
        material: str,
        debate_result: Dict[str, Any],
    ) -> str:
        """
        Format full debate process for transcript.

        Args:
            material: Material name
            debate_result: Result dict from run_debate

        Returns:
            Formatted debate transcript string
        """
        lines = []
        lines.append(f"\n{'=' * 80}")
        lines.append(f"COUNTRY PRODUCTION DEBATE: {material}")
        lines.append(f"{'=' * 80}\n")

        # Phase 1: Agent Proposals
        lines.append("PHASE 1: EXPERT PROPOSALS")
        lines.append("-" * 80)

        proposals_by_agent: Dict[str, List[CountryProposal]] = {}
        for prop in debate_result.get("proposals", []):
            if prop.agent_id not in proposals_by_agent:
                proposals_by_agent[prop.agent_id] = []
            proposals_by_agent[prop.agent_id].append(prop)

        for agent_id in sorted(proposals_by_agent.keys()):
            props = sorted(proposals_by_agent[agent_id], key=lambda p: p.rank)
            lines.append(f"\n{agent_id} (Mining Expert):")
            lines.append(f"  Proposed {len(props)} countries:")
            for prop in props:
                lines.append(
                    f"    {prop.rank}. {prop.country} - "
                    f"{prop.amount:,.2f} {prop.meas_unit} ({prop.percentage:.1f}%)"
                    f"(confidence: {prop.confidence:.2f})"
                )

        # Phase 2: Voting Results
        lines.append(f"\n{'=' * 80}")
        lines.append("PHASE 2: BORDA COUNT VOTING")
        lines.append("-" * 80)

        # Calculate voting details
        from collections import defaultdict

        country_scores: Dict[str, float] = defaultdict(float)
        country_votes: Dict[str, int] = defaultdict(int)
        country_ranks: Dict[str, List[int]] = defaultdict(list)

        for prop in debate_result.get("proposals", []):
            country_lower = prop.country.lower()
            score = debate_result["top_n_proposed"] + 1 - prop.rank
            country_scores[country_lower] += score
            country_votes[country_lower] += 1
            country_ranks[country_lower].append(prop.rank)

        sorted_countries = sorted(country_scores.items(), key=lambda x: x[1], reverse=True)

        lines.append("\nVoting Results (Rank × Agents):")
        for country_lower, score in sorted_countries[:10]:
            votes = country_votes[country_lower]
            ranks = country_ranks[country_lower]
            avg_rank = sum(ranks) / len(ranks)
            lines.append(
                f"  {country_lower.title()}: "
                f"score={score:.1f}, votes={votes}/{self.num_agents}, avg_rank={avg_rank:.1f}"
            )

        # Phase 3: Final Consensus
        lines.append(f"\n{'=' * 80}")
        lines.append("PHASE 3: FINAL CONSENSUS (Top 5)")
        lines.append("-" * 80)

        consensus = debate_result.get("consensus", [])
        if not consensus:
            lines.append("  (No consensus reached)")
        else:
            for idx, country_data in enumerate(consensus, 1):
                lines.append(f"\n{idx}. {country_data['country']}")
                lines.append(
                    f"   Production: {country_data['amount']:,.2f} {country_data['meas_unit']}"
                )
                lines.append(f"   Global Share: {country_data['percentage']:.1f}%")
                lines.append(f"   Confidence: {country_data['confidence']:.2f}")
                if country_data.get("reasoning"):
                    lines.append(f"   Reasoning: {country_data['reasoning']}")

        lines.append(f"\n{'=' * 80}\n")
        return "\n".join(lines)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "MaterialCountryDebater",
    "CountryProposal",
]
