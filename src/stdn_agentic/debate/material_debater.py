"""
Multi-agent debate for material selection.

This module implements debate-driven consensus for identifying raw materials
for each component. Multiple LLM agents propose materials, critique each
other's proposals, and converge on consensus through iterative refinement.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, RunUsage

from ..agents import ComponentMaterialsList, get_materials_agent
from ..models import STDNDependencies

logger = logging.getLogger(__name__)


@dataclass
class MaterialProposal:
    """A material proposal from an agent for a specific component."""

    agentid: str
    component: str
    material: str
    confidence: float
    reasoning: str
    normalizedcomponent: str
    normalizedmaterial: str
    round: int


@dataclass
class MaterialDebateRound:
    """Results from one round of material debate."""

    roundnumber: int
    proposals: list[MaterialProposal]
    critiques: dict[str, dict[str, list[str]]]  # {component: {material: [critiques]}}
    convergencescore: float
    consensussofar: dict[str, list[str]]  # {component: [materials]}


class MaterialDebater:
    """
    Multi-agent debate for material selection consensus.

    Follows the same pattern as MultiAgentDebater for components:
    - Phase 1: Independent material proposals from multiple agents
    - Phase 2: Iterative debate with critiques and refinement
    - Phase 3: Adaptive consensus building with confidence scoring

    This replaces single-agent material extraction with multi-agent consensus.
    """

    def __init__(
        self,
        deps: STDNDependencies,
        num_agents: int = 3,
        max_rounds: int = 3,
        convergence_threshold: float = 0.75,
        confidence_weight: float = 0.3,
        peer_support_boost: float = 0.15,
        debate_top_p: float = 0.0001,
    ) -> None:
        """
        Initialize material debater.

        Args:
            deps: STDN dependencies with LLM access and material ontology
            num_agents: Number of agents in debate (default 3)
            max_rounds: Maximum debate rounds (default 3)
            convergence_threshold: Stop when convergence >= this (default 0.75)
            confidence_weight: Weight for confidence in voting (default 0.3)
            peer_support_boost: Confidence boost per supporting agent (default 0.15)
        """
        self.deps = deps
        self.num_agents = num_agents
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.confidence_weight = confidence_weight
        self.peer_support_boost = peer_support_boost
        self.debate_history: list[MaterialDebateRound] = []
        self.debate_top_p = debate_top_p

    def normalize_component_name(self, name: str) -> str:
        """
        Normalize component name for comparison.

        Follows same logic as MultiAgentDebater.
        """
        if not name:
            return ""

        # Lowercase and strip
        normalized = name.lower().strip()

        # Remove hyphens, underscores
        normalized = normalized.replace("-", " ").replace("_", " ")

        # Collapse whitespace
        normalized = " ".join(normalized.split())

        # Remove trailing qualifiers
        qualifiers = [
            "module",
            "system",
            "unit",
            "assembly",
            "component",
            "subsystem",
            "device",
            "apparatus",
            "mechanism",
            "pack",
        ]
        for qualifier in qualifiers:
            if normalized.endswith(f" {qualifier}"):
                normalized = normalized[: -len(qualifier) - 1].strip()

        return normalized

    def normalize_material_name(self, name: str) -> str:
        """Normalize material name for comparison."""
        if not name:
            return ""

        normalized = name.lower().strip()
        normalized = normalized.replace("-", " ").replace("_", " ")
        normalized = " ".join(normalized.split())

        # Handle common variations
        material_variants = {
            "lithium ion": "lithium",
            "li-ion": "lithium",
            "rare earth elements": "rare earth",
            "ree": "rare earth",
            "stainless steel": "steel",
        }

        return material_variants.get(normalized, normalized)

    async def _check_ollama_health(self) -> bool:
        """Check if Ollama is responsive before starting debate."""
        try:
            logger.info("Checking Ollama health...")
            print("  Testing Ollama connection...")

            # Simple test using component agent (already available)
            from ..agents import get_component_agent

            test_agent = get_component_agent(model_name=self.deps.model)

            # Create minimal deps for test
            from dataclasses import replace

            test_deps = replace(self.deps, top_p=0.9)  # Use default sampling

            result = await test_agent.run(
                "List one component of a smartphone",
                deps=test_deps,
            )

            if result and result.output:
                logger.info("✓ Ollama health check passed")
                print("  ✓ Ollama is responsive")
                return True
            else:
                logger.warning("⚠️  Ollama returned empty result")
                print("  ⚠️  Ollama returned empty result")
                return False

        except Exception as e:
            logger.error(f"❌ Ollama health check failed: {e}")
            print(f"  ❌ Connection failed: {e}")
            return False

    async def phase1_independent_generation(
        self,
        componentlist: list[str],
        technology: str,
        usage: RunUsage | None = None,
    ) -> dict[str, list[MaterialProposal]]:
        """
        Phase 1: Independent material proposals from multiple agents.

        Args:
            componentlist: List of component names
            technology: Technology name for context
            usage: Optional RunUsage tracker

        Returns:
            Dict mapping agent_id to list of MaterialProposal objects
        """
        print("=" * 60)
        print(f"PHASE 1: INDEPENDENT MATERIAL PROPOSALS - {technology}")
        print("=" * 60)

        agent_proposals: dict[str, list[MaterialProposal]] = {}

        # Prepare ontology string
        ontology_sample = self.deps.material_ontology_list[:50]
        ontology_str = ", ".join(ontology_sample)

        # Get materials agent
        agent = get_materials_agent(model_name=self.deps.model)

        # Each agent generates independent proposals
        for agent_num in range(1, self.num_agents + 1):
            agent_id = f"Agent{agent_num}"

            # ADD DELAY BEFORE EACH AGENT (including first one)
            await asyncio.sleep(2.0)  # Give Ollama time to recover

            # Each agent gets slightly different perspective
            perspectives = [
                "Focus on primary structural and functional materials.",
                "Consider trace elements and specialty materials critical to performance.",
                "Emphasize materials with known supply chain constraints.",
            ]
            perspective = perspectives[(agent_num - 1) % len(perspectives)]

            # Build component string
            component_str = "\n".join(f"- {comp}" for comp in componentlist)

            prompt = (
                f"Extract RAW MATERIALS (NOT components or subassemblies) for these "
                f"components of a {technology}:\n{component_str}\n\n"
                f"AVAILABLE RAW MATERIALS (use exact names or common variants):\n{ontology_str}\n\n"
                f"PERSPECTIVE: {perspective}\n\n"
                f"CRITICAL INSTRUCTIONS:\n"
                f"- For each component, identify 2-8 key RAW MATERIALS (metals, minerals, elements, compounds)\n"
                f"- Do NOT return component names, subassemblies, or finished parts\n"
                f"- Return only basic materials like Aluminum, Copper, Silicon, Lithium, Glass, Steel\n"
                f"- Use standard material names from the ontology\n\n"
                f"Return a JSON response with 'component_list' containing 'component' and 'materials' fields."
            )

            # ADD VALIDATION HERE:
            if not prompt or len(prompt.strip()) < 50:
                logger.error(f"{agent_id}: Invalid prompt (too short or empty)")
                print(f"{agent_id}: Skipping due to invalid prompt")
                continue

            if not self.deps or not self.deps.model:
                logger.error(f"{agent_id}: Invalid dependencies")
                print(f"{agent_id}: Skipping due to invalid dependencies")
                continue

            # RETRY LOGIC: Handle transient Ollama errors
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    # Use configured Top-P for deterministic proposals
                    from dataclasses import replace

                    debate_deps = replace(self.deps, top_p=self.debate_top_p)

                    result = await agent.run(prompt, deps=debate_deps)

                    # CORRECTED ACCESS - field is 'component_list' (WITH underscore)
                    if result and result.output and result.output.component_list:
                        proposals = []

                        for cm in result.output.component_list:
                            comp_norm = self.normalize_component_name(cm.component)

                            # CORRECTED ACCESS - field is 'raw_materials' (WITH underscore)
                            for material in cm.raw_materials:
                                # Extract material name from MaterialWithConfidence object
                                material_name = (
                                    material.name if hasattr(material, "name") else str(material)
                                )
                                material_confidence = (
                                    material.confidence if hasattr(material, "confidence") else 0.8
                                )

                                mat_norm = self.normalize_material_name(material_name)

                                proposal = MaterialProposal(
                                    agentid=agent_id,
                                    component=cm.component,
                                    material=material_name,  # Use extracted name
                                    confidence=material_confidence,  # Use extracted confidence
                                    reasoning=f"Proposed by {agent_id} as key material for {cm.component}",
                                    normalizedcomponent=comp_norm,
                                    normalizedmaterial=mat_norm,
                                    round=1,
                                )
                                proposals.append(proposal)

                        agent_proposals[agent_id] = proposals

                        # Count materials per component
                        comp_mat_counts = defaultdict(int)
                        for p in proposals:
                            comp_mat_counts[p.normalizedcomponent] += 1

                        print(
                            print(
                                f"{agent_id} (top_p={self.debate_top_p}): {len(proposals)} material proposals across {len(comp_mat_counts)} components"
                            )
                        )
                        break  # Success - exit retry loop

                except Exception as e:
                    error_str = str(e)
                    is_transient = (
                        "invalid message content type" in error_str
                        or "400" in error_str
                        or "BadRequestError" in error_str
                    )

                    if is_transient and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 3
                        logger.warning(
                            f"{agent_id} transient error (attempt {attempt + 1}/{max_retries}): {e}"
                        )
                        print(f"{agent_id}: Retry in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Error in {agent_id} proposal for {technology}: {e}")
                        print(f"{agent_id}: Failed to generate proposal")
                        break

        if not agent_proposals:
            logger.error(f"No agent proposals generated for {technology}")
            print("❌ No agent proposals generated")

        return agent_proposals

    def calculate_convergence(
        self,
        proposals: list[MaterialProposal],
    ) -> float:
        """
        Calculate convergence based on component-material agreement.

        Returns:
            Convergence score from 0.0 (no agreement) to 1.0 (perfect consensus)
        """
        if not proposals:
            return 0.0

        # Group by agent and component
        agent_comp_mats: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for prop in proposals:
            agent_comp_mats[prop.agentid][prop.normalizedcomponent].add(prop.normalizedmaterial)

        if len(agent_comp_mats) < 2:
            return 1.0

        # Calculate Jaccard similarity for each component across agent pairs
        components = set()
        for agent_mats in agent_comp_mats.values():
            components.update(agent_mats.keys())

        if not components:
            return 0.0

        total_similarity = 0.0
        num_comparisons = 0

        agents = list(agent_comp_mats.keys())
        for comp in components:
            for i in range(len(agents)):
                for j in range(i + 1, len(agents)):
                    set1 = agent_comp_mats[agents[i]].get(comp, set())
                    set2 = agent_comp_mats[agents[j]].get(comp, set())

                    if set1 or set2:
                        intersection = len(set1 & set2)
                        union = len(set1 | set2)

                        if union > 0:
                            similarity = intersection / union
                            total_similarity += similarity
                            num_comparisons += 1

        return total_similarity / num_comparisons if num_comparisons > 0 else 0.0

    def generate_critiques_with_influence(
        self,
        proposals: list[MaterialProposal],
        round_num: int,
    ) -> dict[str, dict[str, list[str]]]:
        """
        Generate critiques with peer support analysis.

        Args:
            proposals: All current proposals
            round_num: Current round number

        Returns:
            Nested dict: {component: {material: [critiques]}}
        """
        critiques: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

        # Group by component and material
        comp_mat_support: dict[str, dict[str, list[MaterialProposal]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for prop in proposals:
            comp_mat_support[prop.normalizedcomponent][prop.normalizedmaterial].append(prop)

        # Generate critiques for each component-material pair
        for comp, mat_support in comp_mat_support.items():
            for mat_norm, supporting in mat_support.items():
                num_supporting = len(supporting)
                support_rate = num_supporting / self.num_agents

                # Get original material name (non-normalized)
                orig_material = supporting[0].material

                if support_rate >= 0.67:
                    # Strong consensus
                    critiques[comp][mat_norm].append(
                        f"CONSENSUS: {num_supporting}/{self.num_agents} agents agree on {orig_material}. "
                        f"Strong evidence for this material."
                    )
                elif support_rate >= 0.33:
                    # Partial support
                    critiques[comp][mat_norm].append(
                        f"PARTIAL: {num_supporting}/{self.num_agents} agents proposed {orig_material}. "
                        f"Consider if this is truly essential or could be consolidated."
                    )
                else:
                    # Isolated proposal
                    critiques[comp][mat_norm].append(
                        f"ISOLATED: Only {num_supporting}/{self.num_agents} agent(s) proposed {orig_material}. "
                        f"Verify if this is truly a key material or too specific."
                    )

        return dict(critiques)

    async def run_debate_round(
        self,
        componentlist: list[str],
        technology: str,
        previous_proposals: list[MaterialProposal],
        critiques: list[str],
        round_num: int,
        usage: RunUsage | None = None,
    ) -> dict[str, list[MaterialProposal]]:
        """
        Run a single debate round with critique-driven refinement.

        Args:
            componentlist: List of component names
            technology: Technology name
            previous_proposals: Proposals from previous round
            critiques: Generated critiques for this round
            round_num: Current round number
            usage: Optional RunUsage tracker

        Returns:
            Dict mapping agent_id to refined proposals
        """
        print(f"\nROUND {round_num}:")

        refined_proposals: dict[str, list[MaterialProposal]] = {}

        # Prepare context strings
        component_str = "\n".join(f"- {comp}" for comp in componentlist)
        ontology_sample = self.deps.material_ontology_list[:50]
        ontology_str = ", ".join(ontology_sample)

        # Format critiques
        critique_text = "\n".join(f"- {c}" for c in critiques)

        # Get materials agent
        agent = get_materials_agent(model_name=self.deps.model)

        # Each agent refines proposals based on critiques
        for agent_num in range(1, self.num_agents + 1):
            agent_id = f"Agent{agent_num}"

            # ADD DELAY BEFORE EACH AGENT
            await asyncio.sleep(2.0)  # Give Ollama time to recover

            prompt = (
                f"ROUND {round_num} - Refine material proposals for {technology}\n\n"
                f"COMPONENTS:\n{component_str}\n\n"
                f"AVAILABLE RAW MATERIALS:\n{ontology_str}\n\n"
                f"PEER FEEDBACK FROM ROUND {round_num - 1}:\n{critique_text}\n\n"
                f"INSTRUCTIONS:\n"
                f"- Review the peer feedback carefully\n"
                f"- Support materials with CONSENSUS (multiple agents agree)\n"
                f"- Reconsider ISOLATED proposals (only one agent suggested)\n"
                f"- Focus on materials that are both technically sound AND have peer support\n"
                f"- Return refined material assignments for each component\n\n"
                f"Return a JSON response with 'component_list' containing 'component' and 'materials' fields."
            )

            # ADD VALIDATION HERE:
            if not prompt or len(prompt.strip()) < 50:
                logger.error(f"{agent_id}: Invalid prompt for round {round_num}")
                continue

            if not self.deps or not self.deps.model:
                logger.error(f"{agent_id}: Invalid dependencies for round {round_num}")
                continue

            # RETRY LOGIC: Handle transient Ollama errors
            max_retries = 5
            success = False

            for attempt in range(max_retries):
                try:
                    # Use configured Top-P for deterministic refinements
                    from dataclasses import replace

                    debate_deps = replace(self.deps, top_p=self.debate_top_p)

                    print(f"  🔍 {agent_id} using top_p={self.debate_top_p}")

                    result = await agent.run(prompt, deps=debate_deps)

                    # CORRECTED ACCESS - use component_list (WITH underscore)
                    if result and result.output and result.output.component_list:
                        proposals = []

                        for cm in result.output.component_list:
                            comp_norm = self.normalize_component_name(cm.component)

                            # CORRECTED ACCESS - raw_materials (WITH underscore)
                            for material in cm.raw_materials:
                                # Extract material name from MaterialWithConfidence object
                                material_name = (
                                    material.name if hasattr(material, "name") else str(material)
                                )

                                mat_norm = self.normalize_material_name(material_name)

                                # Boost confidence for consensus materials
                                peer_support = sum(
                                    1
                                    for p in previous_proposals
                                    if p.normalizedcomponent == comp_norm
                                    and p.normalizedmaterial == mat_norm
                                    and p.agentid != agent_id
                                )
                                confidence = min(0.95, 0.7 + peer_support * self.peer_support_boost)

                                proposal = MaterialProposal(
                                    agentid=agent_id,
                                    component=cm.component,
                                    material=material_name,  # Use extracted name
                                    confidence=confidence,
                                    reasoning=f"Round {round_num} refinement with peer support: {peer_support}",
                                    normalizedcomponent=comp_norm,
                                    normalizedmaterial=mat_norm,
                                    round=round_num,
                                )
                                proposals.append(proposal)

                        refined_proposals[agent_id] = proposals
                        success = True
                        break  # Success - exit retry loop

                except Exception as e:
                    error_str = str(e)
                    is_transient = (
                        "invalid message content type" in error_str
                        or "400" in error_str
                        or "BadRequestError" in error_str
                    )

                    if is_transient and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 3
                        logger.warning(
                            f"{agent_id} round {round_num} transient error "
                            f"(attempt {attempt + 1}/{max_retries}): {e}"
                        )
                        print(f"{agent_id}: Retry in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        # Final attempt failed
                        logger.error(f"Error in {agent_id} round {round_num} for {technology}: {e}")
                        print(f"{agent_id}: Failed to generate proposal")
                        break

            # If all retries failed, fall back to previous proposals
            if not success:
                refined_proposals[agent_id] = [
                    p for p in previous_proposals if p.agentid == agent_id
                ]

        return refined_proposals

    def build_adaptive_consensus(
        self,
        proposals: list[MaterialProposal],
        convergence_score: float,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Build consensus with adaptive voting threshold and confidence scoring.

        Args:
            proposals: All final proposals from debate
            convergence_score: Convergence score (0-1)

        Returns:
            Dict mapping NORMALIZED component names to list of material dicts with confidence
        """
        # Adaptive threshold: high convergence = strict, low = lenient
        vote_threshold = 0.67 if convergence_score > 0.7 else 0.33

        # Group by normalized component and normalized material
        comp_mat_support: dict[str, dict[str, list[MaterialProposal]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for prop in proposals:
            comp_mat_support[prop.normalizedcomponent][prop.normalizedmaterial].append(prop)

        consensus: dict[str, list[dict[str, Any]]] = {}

        for comp_norm, mat_support in comp_mat_support.items():
            component_materials = []

            for _, props in mat_support.items():
                vote_rate = len(props) / self.num_agents
                avg_confidence = sum(p.confidence for p in props) / len(props)

                # Final confidence: weighted by vote rate and confidence
                final_confidence = vote_rate * 0.6 + avg_confidence * 0.4

                # Include if meets threshold
                if vote_rate >= vote_threshold or (vote_rate >= 0.33 and avg_confidence > 0.9):
                    # Use highest confidence proposal's original material name
                    best_prop = max(props, key=lambda p: p.confidence)

                    component_materials.append(
                        {
                            "name": best_prop.material,  # Original material name (for display)
                            "confidence": final_confidence,
                            "reasoning": f"Debate consensus: {len(props)}/{self.num_agents} agents, avg confidence {avg_confidence:.2f}",
                        }
                    )

            if component_materials:
                # ✅ USE NORMALIZED COMPONENT NAME (maintains consistency throughout pipeline)
                consensus[comp_norm] = component_materials

        return consensus

    async def run_full_debate(
        self,
        componentlist: list[str],
        technology: str,
        usage: RunUsage | None = None,
    ) -> dict[str, Any]:
        """
        Execute complete multi-agent debate for material selection.

        Args:
            componentlist: List of component names
            technology: Technology name for context
            usage: Optional RunUsage tracker

        Returns:
            Dict with consensus materials and debate metadata
        """
        print(f"\n{'=' * 60}")
        print(f"MULTI-AGENT MATERIAL DEBATE: {technology}")
        print(f"Components: {len(componentlist)}")
        print(f"{'=' * 60}")

        # # ADD HEALTH CHECK HERE:
        # print("Checking Ollama availability...")
        # if not await self._check_ollama_health():
        #     logger.error("Ollama is not responsive. Aborting material debate.")
        #     print("❌ Ollama health check failed - cannot proceed with material debate")
        #     # Return empty consensus
        #     return {
        #         "consensus": {},
        #         "debate_history": [],
        #         "convergence_scores": [],
        #     }

        # print("✓ Ollama is ready\n")

        # Phase 1: Independent generation
        initial_proposals = await self.phase1_independent_generation(
            componentlist, technology, usage
        )

        if not initial_proposals:
            logger.error(f"No agent proposals for {technology} materials")
            return {"consensus": {}, "convergence": 0.0, "rounds": 0}

        current_proposals = initial_proposals
        all_proposals = [p for props in current_proposals.values() for p in props]

        # Phase 2: Debate rounds
        print(f"\n{'=' * 60}")
        print("PHASE 2: DEBATE ROUNDS")
        print(f"{'=' * 60}")

        rounds_completed = 1
        convergence = self.calculate_convergence(all_proposals)
        print(f"Initial convergence: {convergence:.1%}")

        self.debate_history = []

        for round_num in range(2, self.max_rounds + 1):
            if convergence >= self.convergence_threshold:
                print("Convergence threshold reached!")
                break

            print(f"\nRound {round_num}...")

            # Generate critiques
            critiques = self.generate_critiques_with_influence(all_proposals, round_num)

            # Refine proposals
            current_proposals = await self.run_debate_round(
                componentlist, technology, all_proposals, critiques, round_num, usage
            )

            all_proposals = [p for props in current_proposals.values() for p in props]
            convergence = self.calculate_convergence(all_proposals)
            print(f"Convergence: {convergence:.1%}")

            # Store round data
            consensus_so_far = self.build_adaptive_consensus(all_proposals, convergence)
            debate_round = MaterialDebateRound(
                roundnumber=round_num,
                proposals=all_proposals.copy(),
                critiques=critiques,
                convergencescore=convergence,
                consensussofar=consensus_so_far,
            )
            self.debate_history.append(debate_round)

            rounds_completed = round_num

        # Phase 3: Build consensus
        print(f"\n{'=' * 60}")
        print("PHASE 3: BUILDING CONSENSUS")
        print(f"{'=' * 60}")

        consensus = self.build_adaptive_consensus(all_proposals, convergence)

        # DEDUPLICATION: consensus now contains dicts, not strings
        for component in consensus:
            seen = set()
            unique_materials = []
            for mat_dict in consensus[
                component
            ]:  # mat_dict is {"name": ..., "confidence": ..., "reasoning": ...}
                mat_name = mat_dict["name"]
                mat_norm = self.normalize_material_name(mat_name)
                if mat_norm not in seen:
                    unique_materials.append(mat_dict)  # Keep the full dict
                    seen.add(mat_norm)
            consensus[component] = unique_materials

        # Extract just names for display
        consensus_names = {}
        for comp, material_dicts in consensus.items():
            material_names = [mat_dict["name"] for mat_dict in material_dicts]
            consensus_names[comp] = material_names

        total_materials = sum(len(mats) for mats in consensus_names.values())
        print(f"Consensus: {len(consensus_names)} components, {total_materials} materials")

        for comp, mats in consensus_names.items():
            print(
                f"  - {comp}: {', '.join(mats[:5])}"
                + (f" +{len(mats) - 5} more" if len(mats) > 5 else "")
            )

        # Return consensus with full dict structure (includes confidence)
        return {
            "consensus": consensus,  # Dicts with name, confidence, reasoning
            "convergence": convergence,
            "rounds": rounds_completed,
            "technology": technology,
        }
