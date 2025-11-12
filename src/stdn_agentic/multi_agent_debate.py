# multi_agent_debate.py

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import List, Literal, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext

from stdn_agentic.agents import ComponentList  # ComponentList is in agents.py

# Import from your existing code
from stdn_agentic.models import ConfigModel, STDNDependencies


class ComponentProposal(BaseModel):
    """Single agent's component proposal"""

    name: str
    reasoning: str = Field(description="Why this is a primary component")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    is_valid: bool = Field(default=True, description="Is this truly a component?")


class AgentResponse(BaseModel):
    """Agent's complete response with critiques"""

    agent_id: str
    components: List[ComponentProposal]
    critique_of_others: Optional[str] = Field(
        default=None, description="Critique of other agents' proposals"
    )


class DebateRoundResult(BaseModel):
    """Result from one debate round"""

    round_num: int
    agent_responses: List[AgentResponse]
    convergence_score: float = Field(
        ge=0.0, le=1.0, description="How much agents agree (1.0 = full consensus)"
    )


class FinalConsensus(BaseModel):
    """Final agreed-upon component list"""

    components: List[ComponentProposal]
    debate_summary: str
    num_rounds: int
    confidence: float = Field(ge=0.0, le=1.0)


@dataclass
class DebateConfig:
    """Configuration for debate process"""

    num_agents: int = 3
    max_rounds: int = 3
    consensus_threshold: float = 0.8
    min_confidence: float = 0.6
    agent_personas: List[str] = None

    def __post_init__(self):
        if self.agent_personas is None:
            self.agent_personas = [
                "Manufacturing Engineer - Focus on physical assemblies and subcomponents",
                "Supply Chain Analyst - Focus on procurable, shippable components",
                "Materials Scientist - Focus on distinguishing components from raw materials",
            ]


class MultiAgentComponentDebate:
    """
    Multi-agent debate system for component extraction
    """

    def __init__(self, model: str, deps: STDNDependencies, config: DebateConfig = None):
        self.model = model
        self.deps = deps
        self.config = config or DebateConfig()

        # Create multiple agents with different personas
        self.agents = self._create_debate_agents()

    def _create_debate_agents(self) -> List[Agent]:
        """Create multiple agents with diverse personas"""
        agents = []

        for idx, persona in enumerate(
            self.config.agent_personas[: self.config.num_agents]
        ):
            agent = Agent[STDNDependencies, AgentResponse](
                model=self.model,
                deps_type=STDNDependencies,
                output_type=AgentResponse,
                system_prompt=self._get_agent_system_prompt(persona, idx),
            )
            agents.append(agent)

        return agents

    def _get_agent_system_prompt(self, persona: str, agent_id: int) -> str:
        """Generate system prompt for each agent with specific persona"""
        return f"""You are Agent {agent_id + 1}, a {persona}.

Your task is to identify PRIMARY MANUFACTURING COMPONENTS for a technology product.

INCLUDE:
- Major subassemblies that are procured or manufactured separately
- Functional modules with distinct supply chains
- Structural components that form the product architecture

EXCLUDE:
- Raw materials (metals, plastics, chemicals) - these are inputs TO components
- Manufacturing tools and equipment
- Consumables (adhesives, fasteners, solvents)
- Generic supplies

For each component you identify:
1. Provide the specific name
2. Explain your reasoning
3. Rate your confidence (0.0-1.0)
4. Mark whether it's truly a component vs. a material/tool

When reviewing other agents' proposals:
- Think critically and independently
- Challenge classifications you disagree with
- Provide specific reasoning for your critiques
- Don't just agree to reach consensus - accuracy matters more

Remember: You are {persona}. Bring this perspective to your analysis."""

    async def phase_1_independent_generation(
        self, technology: str
    ) -> List[AgentResponse]:
        """
        Phase 1: Each agent independently generates component list
        """
        print(f"\n{'=' * 60}")
        print("PHASE 1: Independent Component Generation")
        print(f"{'=' * 60}")

        tasks = []
        for idx, agent in enumerate(self.agents):
            task = self._agent_initial_response(agent, idx, technology)
            tasks.append(task)

        # Run all agents in parallel
        responses = await asyncio.gather(*tasks)

        # Print initial proposals
        for response in responses:
            print(f"\n{response.agent_id}:")
            print(f"  Proposed {len(response.components)} components")

        return responses

    async def _agent_initial_response(
        self, agent: Agent, agent_id: int, technology: str
    ) -> AgentResponse:
        """Single agent generates initial response"""

        prompt = f"""Technology: {technology}

Generate a list of primary manufacturing components for this technology.

For each component provide:
- Name
- Reasoning
- Confidence score
- Whether it's a valid component (not a raw material or tool)

Think independently and be thorough."""

        result = await agent.run(prompt, deps=self.deps)

        # Add agent ID
        response = result.data
        response.agent_id = f"Agent {agent_id + 1}"

        return response

    async def phase_2_debate(
        self, technology: str, initial_responses: List[AgentResponse]
    ) -> List[DebateRoundResult]:
        """
        Phase 2: Multi-round debate where agents critique and revise
        """
        print(f"\n{'=' * 60}")
        print("PHASE 2: Multi-Agent Debate")
        print(f"{'=' * 60}")

        debate_history = []
        current_responses = initial_responses

        for round_num in range(1, self.config.max_rounds + 1):
            print(f"\n--- Debate Round {round_num} ---")

            # Calculate convergence
            convergence = self._calculate_convergence(current_responses)
            print(f"Current convergence: {convergence:.1%}")

            # Create debate round result
            round_result = DebateRoundResult(
                round_num=round_num,
                agent_responses=current_responses,
                convergence_score=convergence,
            )
            debate_history.append(round_result)

            # Check if we've reached consensus
            if convergence >= self.config.consensus_threshold:
                print(f"Consensus reached at {convergence:.1%}!")
                break

            # Run debate round
            current_responses = await self._debate_round(
                technology, current_responses, round_num
            )

        return debate_history

    async def _debate_round(
        self, technology: str, previous_responses: List[AgentResponse], round_num: int
    ) -> List[AgentResponse]:
        """Execute one round of debate"""

        # Format other agents' proposals for review
        other_proposals = self._format_proposals_for_review(previous_responses)

        tasks = []
        for idx, agent in enumerate(self.agents):
            # Get this agent's previous response
            prev_response = previous_responses[idx]

            task = self._agent_debate_round(
                agent=agent,
                agent_id=idx,
                technology=technology,
                own_previous_response=prev_response,
                other_proposals=other_proposals,
                round_num=round_num,
            )
            tasks.append(task)

        # Run all agents in parallel
        new_responses = await asyncio.gather(*tasks)

        return new_responses

    def _format_proposals_for_review(self, responses: List[AgentResponse]) -> str:
        """Format all agent proposals for peer review"""
        formatted = []

        for response in responses:
            formatted.append(f"\n{response.agent_id} proposed:")
            for comp in response.components:
                formatted.append(
                    f"  - {comp.name} "
                    f"(confidence: {comp.confidence:.2f}, "
                    f"valid: {comp.is_valid})"
                )
                formatted.append(f"    Reasoning: {comp.reasoning}")

        return "\n".join(formatted)

    async def _agent_debate_round(
        self,
        agent: Agent,
        agent_id: int,
        technology: str,
        own_previous_response: AgentResponse,
        other_proposals: str,
        round_num: int,
    ) -> AgentResponse:
        """Single agent participates in one debate round"""

        prompt = f"""Technology: {technology}

=== YOUR PREVIOUS PROPOSAL (Round {round_num - 1}) ===
{self._format_single_response(own_previous_response)}

=== OTHER AGENTS' PROPOSALS ===
{other_proposals}

=== YOUR TASK ===
Review the other agents' proposals and your own.

1. Critique others' proposals:
   - Which components do you agree/disagree with?
   - Are any of their "components" actually raw materials or tools?
   - Did they miss any critical components?

2. Revise your own proposal:
   - Keep components you're confident about
   - Add components others found that you missed
   - Remove items others convinced you are invalid
   - Adjust confidence scores based on debate

Think critically and independently. Don't just agree with the majority.

Provide:
- Updated component list with confidence scores
- Your critique of other agents' proposals
"""

        result = await agent.run(prompt, deps=self.deps)
        response = result.data
        response.agent_id = f"Agent {agent_id + 1}"

        return response

    def _format_single_response(self, response: AgentResponse) -> str:
        """Format single agent's response"""
        lines = []
        for comp in response.components:
            lines.append(
                f"- {comp.name} (confidence: {comp.confidence:.2f}, "
                f"valid: {comp.is_valid})"
            )
        return "\n".join(lines)

    def _calculate_convergence(self, responses: List[AgentResponse]) -> float:
        """
        Calculate how much agents agree
        Returns 0.0 (no agreement) to 1.0 (perfect consensus)
        """
        # Extract all proposed component names
        all_components = []
        for response in responses:
            valid_comps = [
                c.name.lower().strip() for c in response.components if c.is_valid
            ]
            all_components.append(set(valid_comps))

        if not all_components:
            return 0.0

        # Calculate Jaccard similarity across all agent pairs
        num_agents = len(all_components)
        if num_agents < 2:
            return 1.0

        total_similarity = 0.0
        num_pairs = 0

        for i in range(num_agents):
            for j in range(i + 1, num_agents):
                intersection = len(all_components[i] & all_components[j])
                union = len(all_components[i] | all_components[j])

                if union > 0:
                    similarity = intersection / union
                    total_similarity += similarity
                    num_pairs += 1

        return total_similarity / num_pairs if num_pairs > 0 else 0.0

    def phase_3_build_consensus(
        self, debate_history: List[DebateRoundResult]
    ) -> FinalConsensus:
        """
        Phase 3: Build final consensus using weighted voting
        """
        print(f"\n{'=' * 60}")
        print("PHASE 3: Building Consensus")
        print(f"{'=' * 60}")

        # Get final round responses
        final_round = debate_history[-1]
        final_responses = final_round.agent_responses

        # Collect all proposed components with votes
        component_votes = {}  # component_name -> list of proposals

        for response in final_responses:
            for comp in response.components:
                if not comp.is_valid or comp.confidence < self.config.min_confidence:
                    continue

                # Normalize name
                name_key = comp.name.lower().strip()

                if name_key not in component_votes:
                    component_votes[name_key] = []

                component_votes[name_key].append(
                    {
                        "proposal": comp,
                        "agent": response.agent_id,
                        "confidence": comp.confidence,
                    }
                )

        # Build consensus components
        consensus_components = []

        for name_key, votes in component_votes.items():
            num_votes = len(votes)
            vote_rate = num_votes / len(self.agents)

            # Calculate weighted confidence
            avg_confidence = sum(v["confidence"] for v in votes) / num_votes

            # Weighted by vote rate and confidence
            final_confidence = (vote_rate * 0.6) + (avg_confidence * 0.4)

            print(f"\nComponent: {votes[0]['proposal'].name}")
            print(f"  Votes: {num_votes}/{len(self.agents)} agents")
            print(f"  Avg confidence: {avg_confidence:.2f}")
            print(f"  Final confidence: {final_confidence:.2f}")

            # Include if at least 2 agents agree OR 1 agent with very high confidence
            if num_votes >= 2 or (num_votes == 1 and avg_confidence >= 0.9):
                # Use the highest quality reasoning
                best_proposal = max(votes, key=lambda v: v["confidence"])["proposal"]

                consensus_components.append(
                    ComponentProposal(
                        name=best_proposal.name,
                        reasoning=best_proposal.reasoning,
                        confidence=final_confidence,
                        is_valid=True,
                    )
                )

        # Sort by confidence
        consensus_components.sort(key=lambda c: c.confidence, reverse=True)

        # Generate summary
        summary = self._generate_debate_summary(debate_history, consensus_components)

        consensus = FinalConsensus(
            components=consensus_components,
            debate_summary=summary,
            num_rounds=len(debate_history),
            confidence=sum(c.confidence for c in consensus_components)
            / len(consensus_components)
            if consensus_components
            else 0.0,
        )

        print(f"\nFinal consensus: {len(consensus_components)} components")
        print(f"Overall confidence: {consensus.confidence:.2f}")

        return consensus

    def _generate_debate_summary(
        self,
        debate_history: List[DebateRoundResult],
        final_components: List[ComponentProposal],
    ) -> str:
        """Generate summary of debate process"""
        lines = [
            f"Debate completed in {len(debate_history)} rounds",
            f"Initial convergence: {debate_history[0].convergence_score:.1%}",
            f"Final convergence: {debate_history[-1].convergence_score:.1%}",
            f"Consensus components: {len(final_components)}",
        ]
        return "\n".join(lines)

    async def run_full_debate(self, technology: str) -> FinalConsensus:
        """
        Execute complete multi-agent debate process
        """
        print(f"\n{'#' * 60}")
        print(f"MULTI-AGENT DEBATE: {technology}")
        print(f"{'#' * 60}")

        # Phase 1: Independent generation
        initial_responses = await self.phase_1_independent_generation(technology)

        # Phase 2: Debate
        debate_history = await self.phase_2_debate(technology, initial_responses)

        # Phase 3: Consensus
        final_consensus = self.phase_3_build_consensus(debate_history)

        return final_consensus


# Integration with existing orchestrator


async def extract_components_with_debate(
    technology: str,
    model: str,
    deps: STDNDependencies,
    num_agents: int = 3,
    max_rounds: int = 3,
) -> ComponentList:
    """
    Extract components using multi-agent debate
    Returns ComponentList compatible with your existing code
    """
    debate_config = DebateConfig(
        num_agents=num_agents,
        max_rounds=max_rounds,
        consensus_threshold=0.8,
        min_confidence=0.6,
    )

    debate = MultiAgentComponentDebate(model=model, deps=deps, config=debate_config)

    consensus = await debate.run_full_debate(technology)

    # Convert to your existing ComponentList format
    component_list = ComponentList(
        component_list=[comp.name for comp in consensus.components]
    )

    return component_list
