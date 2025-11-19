"""
Material-Country mapping debate system for STDN

This module implements multi-agent debate for country production data when USGS
database lookups fail. Multiple mining experts propose and vote on top-producing
countries to reach consensus through simple voting.

Integration point: CountryDataRepository._query_llm_with_debate()
"""

from __future__ import annotations

import logging
from collections import Counter
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
    ) -> List[Dict[str, Any]]:
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

        return consensus

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
                            meas_unit=cp.meas_unit,
                            amount=cp.amount,
                            percentage=cp.percentage,
                            rank=rank,
                            round_num=1,
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
        """Build consensus using ranked voting to select top 5."""
        print(f"\n{'=' * 60}")
        print("PHASE 2: VOTING CONSENSUS")
        print(f"{'=' * 60}")

        # Score countries using Borda count (weighted by rank)
        # Rank 1 gets highest score, rank 10 gets lowest
        country_scores: Dict[str, float] = {}
        country_data: Dict[str, List[CountryProposal]] = {}

        for proposal in all_proposals:
            country_lower = proposal.country.lower()

            # Borda score: 11 - rank (so rank 1 = 10 points, rank 10 = 1 point)
            score = self.top_n_proposed + 1 - proposal.rank

            if country_lower not in country_scores:
                country_scores[country_lower] = 0.0
                country_data[country_lower] = []

            country_scores[country_lower] += score
            country_data[country_lower].append(proposal)

        # Sort by score and select top N
        sorted_countries = sorted(country_scores.items(), key=lambda x: x[1], reverse=True)[
            : self.top_n_consensus
        ]

        print(f"\nVoting results (Borda count):")
        for country_lower, score in sorted_countries:
            proposals = country_data[country_lower]
            num_votes = len(proposals)
            avg_rank = sum(p.rank for p in proposals) / num_votes
            print(
                f"  - {proposals[0].country}: score={score:.1f}, votes={num_votes}, avg_rank={avg_rank:.1f}"
            )

        # Build final consensus with averaged values
        consensus = []

        for country_lower, _ in sorted_countries:
            proposals = country_data[country_lower]

            # Average the production values across agents who proposed this country
            avg_amount = sum(p.amount for p in proposals) / len(proposals)
            avg_percentage = sum(p.percentage for p in proposals) / len(proposals)

            # Use most common unit
            units = [p.meas_unit for p in proposals]
            common_unit = Counter(units).most_common(1)[0][0]

            # Use original country name (not lowercased)
            country_name = proposals[0].country

            consensus.append(
                {
                    "country": country_name,
                    "meas_unit": common_unit,
                    "amount": avg_amount,
                    "percentage": avg_percentage,
                }
            )

        return consensus


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "MaterialCountryDebater",
    "CountryProposal",
]
