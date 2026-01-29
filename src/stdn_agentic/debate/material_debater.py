"""
Multi-agent debate for material selection.

This module is typically used by constructing a single MaterialDebater
per technology run, then calling `run_full_debate` (or individual phases)
with a component list to obtain a consensus set of raw materials.

This module implements debate-driven consensus for identifying raw materials
for each component. Multiple LLM agents propose materials, critique each
other's proposals, and converge on consensus through iterative refinement.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from pydantic_ai import RunUsage

from ..agents import get_materials_agent
from ..logging_config import get_logger
from ..models import STDNDependencies
from .material_models import MaterialDebateRound, MaterialProposal
from .material_normalization import normalize_component_name, normalize_material_name

logger = get_logger(__name__)


class MaterialDebater:
    """Coordinate multi-agent material extraction and consensus.

    The public entrypoints are:
    - phase1_independent_generation: initial per-agent material proposals
    - run_debate_round: critique-driven refinement rounds
    - build_adaptive_consensus / run_full_debate: final consensus material set
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

    async def _check_ollama_health(self) -> bool:
        """Check if Ollama is responsive before starting debate."""
        try:
            logger.debug("Checking Ollama health...")

            # Simple test using component agent (already available)
            from ..agents import get_component_agent

            test_agent = get_component_agent(model_name=self.deps.get_materials_model())

            # Create minimal deps for test
            from dataclasses import replace

            test_deps = replace(self.deps, top_p=0.9)  # Use default sampling

            result = await test_agent.run(
                "List one component of a smartphone",
                deps=test_deps,
            )

            if result and result.output:
                logger.debug("Ollama health check passed")
                return True
            else:
                logger.warning("Ollama returned empty result")
                return False

        except Exception as e:
            logger.error("Ollama health check failed: %s", e)
            return False

    async def phase1_independent_generation(
        self,
        componentlist: list[str],
        technology: str,
        usage: RunUsage | None = None,
    ) -> dict[str, list[MaterialProposal]]:
        """Run phase 1: independent material proposals from multiple agents.

        Validates inputs and dependencies, builds an ontology-aware prompt,
        then runs all agents once to obtain initial `MaterialProposal`s.
        """
        logger.info("=" * 60)
        logger.info("PHASE 1: INDEPENDENT MATERIAL PROPOSALS - %s", technology)
        logger.info("=" * 60)

        valid_components = self._phase1_validate_inputs(componentlist, technology)
        if not valid_components:
            return {}

        agent_proposals: dict[str, list[MaterialProposal]] = {}

        if not self._phase1_validate_dependencies():
            return {}

        ontology_str = self._phase1_build_ontology_string()
        if not ontology_str:
            return {}

        agent = self._phase1_create_materials_agent()
        if agent is None:
            return {}

        perspectives = self._phase1_build_perspectives()

        # single call that contains the loop + per-agent logic
        await self._phase1_run_all_agents(
            valid_components, technology, agent, ontology_str, perspectives, agent_proposals
        )

        if not agent_proposals:
            logger.error("No agent proposals generated for %s", technology)
        else:
            total_proposals = sum(len(props) for props in agent_proposals.values())
            logger.info(
                "Generated %d total proposals from %d agents",
                total_proposals,
                len(agent_proposals),
            )

        return agent_proposals

    def _phase1_print_agent_summary(
        self,
        agent_id: str,
        proposals: list[MaterialProposal],
    ) -> None:
        from collections import defaultdict

        comp_mat_counts = defaultdict(int)
        for p in proposals:
            comp_mat_counts[p.normalizedcomponent] += 1

        logger.info(
            "%s: %d material proposals across %d components",
            agent_id,
            len(proposals),
            len(comp_mat_counts),
        )

    async def _phase1_run_agent_with_retries(
        self,
        agent_id: str,
        agent,
        prompt: str,
        technology: str,
    ) -> list[MaterialProposal]:
        """Run a single agent with retries and return its proposals."""
        max_retries = 5

        for attempt in range(max_retries):
            try:
                from dataclasses import replace

                debate_deps = replace(self.deps, top_p=self.debate_top_p)

                if not debate_deps.model or not debate_deps.model.strip():
                    logger.error(f"{agent_id}: Model name is empty in deps")
                    break

                result = await agent.run(prompt, deps=debate_deps)

                proposals = self._phase1_extract_proposals(agent_id, result)
                if not proposals:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                    else:
                        logger.warning("%s: Failed - no valid proposals", agent_id)
                        break

                return proposals

            except Exception as e:
                error_str = str(e)
                is_transient = (
                    "invalid message content type" in error_str
                    or "400" in error_str
                    or "BadRequestError" in error_str
                    or "<nil>" in error_str
                )

                if is_transient and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.warning(
                        "%s transient error (attempt %d/%d): %s",
                        agent_id,
                        attempt + 1,
                        max_retries,
                        e,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        "Error in %s proposal for %s: %s",
                        agent_id,
                        technology,
                        e,
                        exc_info=True,
                    )
                    break

        # Ensure a list is always returned
        return []

    async def _phase1_run_all_agents(
        self,
        valid_components: list[str],
        technology: str,
        agent,
        ontology_str: str,
        perspectives: list[str],
        agent_proposals: dict[str, list[MaterialProposal]],
    ) -> None:
        """Run all agents for phase 1 and populate agent_proposals."""
        for agent_num in range(1, self.num_agents + 1):
            agent_id = f"Agent{agent_num}"

            await asyncio.sleep(2.0)  # Give Ollama time to recover

            perspective = perspectives[(agent_num - 1) % len(perspectives)]
            if not perspective or not perspective.strip():
                perspective = "Identify essential raw materials for manufacturing."
                logger.warning(f"{agent_id}: Using fallback perspective")

            component_str = "\n".join(f"- {comp}" for comp in valid_components)
            if not component_str or len(component_str.strip()) < 3:
                logger.error("%s: Failed to build component string", agent_id)
                continue

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

            if not self._phase1_validate_prompt(agent_id, prompt):
                continue

            proposals = await self._phase1_run_agent_with_retries(
                agent_id, agent, prompt, technology
            )
            if not proposals:
                continue

            agent_proposals[agent_id] = proposals
            self._phase1_print_agent_summary(agent_id, proposals)

    def _phase1_validate_inputs(self, componentlist: list[str], technology: str) -> list[str]:
        """Filter and validate the component list and technology name."""
        if not componentlist or len(componentlist) == 0:
            logger.error("Empty component list for %s", technology)
            return []

        if not technology or not technology.strip():
            logger.error("Empty technology name")
            return []

        valid_components = [c for c in componentlist if c and c.strip()]
        if not valid_components:
            logger.error("All components are None/empty for %s", technology)
            return []

        if len(valid_components) < len(componentlist):
            filtered_count = len(componentlist) - len(valid_components)
            logger.warning("Filtered out %d None/empty components", filtered_count)

        return valid_components

    def _phase1_validate_dependencies(self) -> bool:
        """Ensure model and material ontology are available before starting."""
        if not self.deps or not self.deps.model:
            logger.error("Invalid dependencies - no model configured")
            return False

        if not self.deps.material_ontology_list or len(self.deps.material_ontology_list) == 0:
            logger.error("Material ontology is empty")
            return False

        return True

    def _phase1_build_ontology_string(self) -> str | None:
        """Build a compact comma-separated sample of the ontology for prompts."""
        ontology_sample = self.deps.material_ontology_list[:50]
        ontology_str = ", ".join(ontology_sample)

        if not ontology_str or len(ontology_str.strip()) < 10:
            logger.error("Ontology string is empty or too short")
            return None

        return ontology_str

    def _phase1_create_materials_agent(self):
        """Create the materials agent used for all material debate phases."""
        try:
            agent = get_materials_agent(model_name=self.deps.get_materials_model())
        except Exception as e:
            logger.error("Failed to create materials agent: %s", e)
            return None
        return agent

    def _phase1_build_perspectives(self) -> list[str]:
        """Return a small set of prompt perspectives to diversify agents."""
        perspectives = [
            "Focus on primary structural and functional materials.",
            "Consider trace elements and specialty materials critical to performance.",
            "Emphasize materials with known supply chain constraints.",
        ]
        perspectives = [p for p in perspectives if p and p.strip()]
        if not perspectives:
            perspectives = ["Identify essential raw materials for manufacturing."]
            logger.warning("Using fallback perspective")
        return perspectives

    def _phase1_validate_prompt(self, agent_id: str, prompt: str) -> bool:
        """Sanity-check prompts for common issues before sending to the LLM."""
        if not prompt or len(prompt.strip()) < 50:
            logger.error("%s: Invalid prompt (too short or empty)", agent_id)
            return False

        if "None" in prompt or "<nil>" in prompt or "null" in prompt:
            logger.error("%s: Prompt contains None/null values", agent_id)
            logger.debug("Problematic prompt snippet: %s", prompt[:300])
            return False

        if "\n\n\n\n" in prompt or "  \n  \n" in prompt:
            logger.warning("%s: Prompt has excessive whitespace", agent_id)

        logger.debug("%s: Prompt preview: %s...", agent_id, prompt[:200])
        return True

    def _phase1_extract_proposals(
        self,
        agent_id: str,
        result,
    ) -> list[MaterialProposal]:
        if not result:
            logger.warning("%s: Agent returned None result", agent_id)
            return []

        if not result.output:
            logger.warning("%s: Result has no output", agent_id)
            return []

        if not hasattr(result.output, "component_list"):
            logger.error("%s: Output missing 'component_list' field", agent_id)
            return []

        if not result.output.component_list:
            logger.warning("%s: component_list is empty", agent_id)
            return []

        proposals: list[MaterialProposal] = []

        for cm in result.output.component_list:
            if not hasattr(cm, "component") or not cm.component:
                logger.warning("%s: Skipping component with no name", agent_id)
                continue

            comp_norm = normalize_component_name(cm.component)

            if not hasattr(cm, "raw_materials") or not cm.raw_materials:
                logger.warning("%s: Component '%s' has no materials", agent_id, cm.component)
                continue

            for material in cm.raw_materials:
                material_name = material.name if hasattr(material, "name") else str(material)

                if not material_name or not material_name.strip():
                    logger.warning("%s: Skipping empty material for %s", agent_id, cm.component)
                    continue

                material_confidence = (
                    material.confidence if hasattr(material, "confidence") else 0.8
                )

                mat_norm = normalize_material_name(material_name)

                proposal = MaterialProposal(
                    agentid=agent_id,
                    component=cm.component,
                    material=material_name,
                    confidence=material_confidence,
                    reasoning=f"Proposed by {agent_id} as key material for {cm.component}",
                    normalizedcomponent=comp_norm,
                    normalizedmaterial=mat_norm,
                    round=1,
                )
                proposals.append(proposal)

        return proposals

    def calculate_convergence(
        self,
        proposals: list[MaterialProposal],
    ) -> float:
        """Compute agreement score across agents for component-material pairs."""
        if not proposals:
            return 0.0

        # Group by agent and component
        agent_comp_mats: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for prop in proposals:
            agent_comp_mats[prop.agentid][prop.normalizedcomponent].add(prop.normalizedmaterial)

        if len(agent_comp_mats) < 2:
            return 1.0

        components = set()
        for agent_mats in agent_comp_mats.values():
            components.update(agent_mats.keys())

        if not components:
            return 0.0

        agents = list(agent_comp_mats.keys())
        total_similarity, num_comparisons = self._calculate_component_similarities(
            agent_comp_mats, components, agents
        )

        return total_similarity / num_comparisons if num_comparisons > 0 else 0.0

    def _calculate_component_similarities(
        self,
        agent_comp_mats: dict[str, dict[str, set[str]]],
        components: set[str],
        agents: list[str],
    ) -> tuple[float, int]:
        """Calculate total similarity and comparison count across components."""
        total_similarity = 0.0
        num_comparisons = 0

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

        return total_similarity, num_comparisons

    def generate_critiques_with_influence(
        self,
        proposals: list[MaterialProposal],
        round_num: int,
    ) -> dict[str, dict[str, list[str]]]:
        """Generate structured critiques using peer support and coverage signals."""
        critiques: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

        # Group by component and material
        comp_mat_support: dict[str, dict[str, list[MaterialProposal]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for prop in proposals:
            comp_mat_support[prop.normalizedcomponent][prop.normalizedmaterial].append(prop)

        # Generate critiques for each component-material pair
        for comp, mat_support in comp_mat_support.items():
            # Get all materials proposed for this component
            all_materials_for_comp = list(mat_support.keys())

            for mat_norm, supporting in mat_support.items():
                num_supporting = len(supporting)
                support_rate = num_supporting / self.num_agents

                # Get original material name and reasoning from first supporter
                orig_material = supporting[0].material
                sample_reasoning = supporting[0].reasoning[:100] if supporting[0].reasoning else ""

                if support_rate >= 0.67:
                    # Strong consensus - reinforce
                    avg_conf = sum(p.confidence for p in supporting) / len(supporting)
                    critiques[comp][mat_norm].append(
                        f"✓ CONSENSUS: {num_supporting}/{self.num_agents} agents agree on {orig_material} "
                        f"(avg confidence: {avg_conf:.2f}). Strong evidence: {sample_reasoning}"
                    )
                elif support_rate >= 0.33:
                    # Partial support - provide specific guidance
                    non_supporters = self.num_agents - num_supporting
                    other_mats = [m for m in all_materials_for_comp if m != mat_norm]

                    critique = f"⚠ PARTIAL: {num_supporting}/{self.num_agents} agents proposed {orig_material}. "

                    if other_mats:
                        # Show what other agents proposed instead
                        alternatives = ", ".join(other_mats[:3])
                        critique += (
                            f"{non_supporters} agent(s) proposed alternatives: {alternatives}. "
                        )
                        critique += f"Evaluate if {orig_material} is functionally distinct or if materials can be consolidated."
                    else:
                        # Material omitted by some agents
                        critique += f"{non_supporters} agent(s) omitted this material. "
                        critique += f"Consider: Is {orig_material} truly essential for {comp}?"

                    critiques[comp][mat_norm].append(critique)
                else:
                    # Isolated proposal - challenge strongly
                    other_agents_count = self.num_agents - num_supporting
                    critiques[comp][mat_norm].append(
                        f"❌ ISOLATED: Only {num_supporting}/{self.num_agents} agent proposed {orig_material} "
                        f"while {other_agents_count} agents did not. Reasoning: {sample_reasoning}. "
                        f"Verify if this material is critical or too specific/redundant for {comp}."
                    )

            # Add component-level guidance if there are too many materials
            if len(all_materials_for_comp) > 8:
                critiques[comp]["_component_level"] = [
                    f"⚠ {comp} has {len(all_materials_for_comp)} proposed materials - "
                    f"focus on primary/essential materials and consolidate variants."
                ]

        return dict(critiques)

    async def _run_single_debate_agent_round(
        self,
        agent_id: str,
        agent,
        component_str: str,
        ontology_str: str,
        critique_text: str,
        technology: str,
        previous_proposals: list[MaterialProposal],
        round_num: int,
        refined_proposals: dict[str, list[MaterialProposal]],
    ) -> None:
        """Execute a single agent's refinement call with retries for one round."""
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

        if not prompt or len(prompt.strip()) < 50:
            logger.error(f"{agent_id}: Invalid prompt for round {round_num}")
            return

        if not self.deps or not self.deps.model:
            logger.error(f"{agent_id}: Invalid dependencies for round {round_num}")
            return

        max_retries = 5
        success = False

        for attempt in range(max_retries):
            try:
                from dataclasses import replace

                debate_deps = replace(self.deps, top_p=self.debate_top_p)

                logger.debug("%s using top_p=%s", agent_id, self.debate_top_p)

                result = await agent.run(prompt, deps=debate_deps)

                if result and result.output and result.output.component_list:
                    proposals: list[MaterialProposal] = []

                    for cm in result.output.component_list:
                        comp_norm = normalize_component_name(cm.component)

                        for material in cm.raw_materials:
                            material_name = (
                                material.name if hasattr(material, "name") else str(material)
                            )

                            mat_norm = normalize_material_name(material_name)

                            peer_support = sum(
                                1
                                for p in previous_proposals
                                if (
                                    p.normalizedcomponent == comp_norm
                                    and p.normalizedmaterial == mat_norm
                                    and p.agentid != agent_id
                                )
                            )
                            confidence = min(0.95, 0.7 + peer_support * self.peer_support_boost)

                            proposal = MaterialProposal(
                                agentid=agent_id,
                                component=cm.component,
                                material=material_name,
                                confidence=confidence,
                                reasoning=(
                                    f"Round {round_num} refinement with peer support: {peer_support}"
                                ),
                                normalizedcomponent=comp_norm,
                                normalizedmaterial=mat_norm,
                                round=round_num,
                            )
                            proposals.append(proposal)

                    refined_proposals[agent_id] = proposals
                    success = True
                    break

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
                        "%s round %d transient error (attempt %d/%d): %s",
                        agent_id,
                        round_num,
                        attempt + 1,
                        max_retries,
                        e,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        "Error in %s round %d for %s: %s",
                        agent_id,
                        round_num,
                        technology,
                        e,
                    )
                    break

        if not success:
            refined_proposals[agent_id] = [p for p in previous_proposals if p.agentid == agent_id]

    async def run_debate_round(
        self,
        componentlist: list[str],
        technology: str,
        previous_proposals: list[MaterialProposal],
        critiques: list[str],
        round_num: int,
        usage: RunUsage | None = None,
    ) -> dict[str, list[MaterialProposal]]:
        """Run one refinement round for all agents using previous critiques."""
        logger.info("Round %d:", round_num)

        refined_proposals: dict[str, list[MaterialProposal]] = {}

        # Prepare context strings
        component_str = "\n".join(f"- {comp}" for comp in componentlist)
        ontology_sample = self.deps.material_ontology_list[:50]
        ontology_str = ", ".join(ontology_sample)

        # Format critiques
        critique_text = "\n".join(f"- {c}" for c in critiques)

        # Get materials agent
        agent = get_materials_agent(model_name=self.deps.get_materials_model())

        # Each agent refines proposals based on critiques
        for agent_num in range(1, self.num_agents + 1):
            agent_id = f"Agent{agent_num}"
            await asyncio.sleep(2.0)  # Give Ollama time to recover

            await self._run_single_debate_agent_round(
                agent_id=agent_id,
                agent=agent,
                component_str=component_str,
                ontology_str=ontology_str,
                critique_text=critique_text,
                technology=technology,
                previous_proposals=previous_proposals,
                round_num=round_num,
                refined_proposals=refined_proposals,
            )

        return refined_proposals

    def build_adaptive_consensus(
        self,
        proposals: list[MaterialProposal],
        convergence_score: float,
        expected_components: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Build the final component→materials mapping with adaptive thresholds."""
        if not proposals:
            return {}

        component_lookup = {comp.lower().strip(): comp for comp in expected_components}

        logger.debug("Building consensus with component name enforcement...")
        logger.debug("  Expected components: %s", expected_components)

        def find_correct_component_name(comp_name: str) -> str:
            """Find the correct component name from expected components."""
            comp_lower = comp_name.lower().strip()

            if comp_lower in component_lookup:
                return component_lookup[comp_lower]

            base_name = comp_lower.split("(")[0].strip()
            if base_name in component_lookup:
                return component_lookup[base_name]

            for key, correct_name in component_lookup.items():
                if base_name in key or key in base_name:
                    return correct_name

            logger.warning(f"Component '{comp_name}' not found in expected components")
            return comp_name

        comp_mat_support: dict[str, dict[str, list[MaterialProposal]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for prop in proposals:
            corrected_comp = find_correct_component_name(prop.normalizedcomponent)
            mat_norm = prop.normalizedmaterial
            comp_mat_support[corrected_comp][mat_norm].append(prop)

        if convergence_score >= 0.7:
            min_support_frac = 2.0 / 3.0
        elif convergence_score <= 0.3:
            min_support_frac = 1.0 / 3.0
        else:
            frac = (convergence_score - 0.3) / (0.7 - 0.3)
            min_support_frac = (1.0 / 3.0) + frac * (1.0 / 3.0)

        min_support = max(1, int(round(min_support_frac * max(self.num_agents, 1))))

        logger.debug("  Convergence: %.2f", convergence_score)
        logger.debug("  Min support required: %d/%d agents", min_support, self.num_agents)

        consensus: dict[str, list[dict[str, Any]]] = {}
        self._build_component_consensus(consensus, comp_mat_support, min_support)

        return consensus

    def _build_component_consensus(
        self,
        consensus: dict[str, list[dict[str, Any]]],
        comp_mat_support: dict[str, dict[str, list[MaterialProposal]]],
        min_support: int,
    ) -> None:
        """Populate the consensus dict for each component using scoring rules."""
        for comp_norm, mat_support in comp_mat_support.items():
            component_materials: list[dict[str, Any]] = []

            for mat_norm, props in mat_support.items():
                vote_rate = len(props) / self.num_agents
                avg_confidence = sum(p.confidence for p in props) / len(props)

                score = (
                    (1.0 - self.confidence_weight) * vote_rate
                    + self.confidence_weight * avg_confidence
                    + self.peer_support_boost * (len(props) - 1)
                )

                if len(props) >= min_support:
                    best_prop = max(props, key=lambda p: p.confidence)

                    original_name = self.material_name_map.get(
                        mat_norm,
                        best_prop.material,
                    )

                    component_materials.append(
                        {
                            "name": original_name,
                            "confidence": avg_confidence,
                            "reasoning": best_prop.reasoning,
                            "score": score,
                            "support": len(props),
                        }
                    )

            component_materials.sort(key=lambda m: m["score"], reverse=True)

            if component_materials:
                consensus[comp_norm] = component_materials
                logger.debug("  %s: %d materials", comp_norm, len(component_materials))

    async def run_full_debate(
        self,
        componentlist: list[str],
        technology: str,
        usage: RunUsage | None = None,
    ) -> dict[str, Any]:
        """Run the full three-phase material debate and return consensus output."""
        logger.info("=" * 60)
        logger.info("MULTI-AGENT MATERIAL DEBATE: %s", technology)
        logger.info("Components: %d", len(componentlist))
        logger.info("=" * 60)

        # Create normalized-to-original mapping from ontology
        # Build once at start, use throughout consensus building
        self.material_name_map = {}
        for original_name in self.deps.material_ontology_list:
            normalized = normalize_material_name(original_name)
            self.material_name_map[normalized] = original_name

        logger.debug("Material ontology: %d materials loaded", len(self.material_name_map))

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
        logger.info("=" * 60)
        logger.info("PHASE 2: DEBATE ROUNDS")
        logger.info("=" * 60)

        rounds_completed = 1
        convergence = self.calculate_convergence(all_proposals)
        logger.info("Initial convergence: %.1f%%", convergence * 100)

        self.debate_history = []

        for round_num in range(2, self.max_rounds + 1):
            if convergence >= self.convergence_threshold:
                logger.info("Convergence threshold reached!")
                break

            logger.info("Round %d/%d...", round_num, self.max_rounds)

            # Generate critiques
            critiques = self.generate_critiques_with_influence(all_proposals, round_num)

            # Refine proposals
            current_proposals = await self.run_debate_round(
                componentlist, technology, all_proposals, critiques, round_num, usage
            )

            all_proposals = [p for props in current_proposals.values() for p in props]
            convergence = self.calculate_convergence(all_proposals)
            logger.info("  Convergence: %.1f%%", convergence * 100)

            # Store round data
            consensus_so_far = self.build_adaptive_consensus(
                all_proposals,
                convergence,
                expected_components=componentlist,
            )
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
        logger.info("=" * 60)
        logger.info("PHASE 3: BUILDING CONSENSUS")
        logger.info("=" * 60)

        consensus = self.build_adaptive_consensus(
            all_proposals,
            convergence_score=convergence,
            expected_components=componentlist,  # ✅ ADD THIS
        )

        # DEDUPLICATION: consensus now contains dicts, not strings
        for component in consensus:
            seen = set()
            unique_materials = []
            for mat_dict in consensus[
                component
            ]:  # mat_dict is {"name": ..., "confidence": ..., "reasoning": ...}
                mat_name = mat_dict["name"]
                mat_norm = normalize_material_name(mat_name)
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
        logger.info(
            "Consensus: %d components, %d materials",
            len(consensus_names),
            total_materials,
        )

        for comp, mats in consensus_names.items():
            logger.debug(
                "  %s: %s%s",
                comp,
                ", ".join(mats[:5]),
                f" +{len(mats) - 5} more" if len(mats) > 5 else "",
            )

        # Return consensus with full dict structure (includes confidence)
        return {
            "consensus": consensus,  # Dicts with name, confidence, reasoning
            "convergence": convergence,
            "rounds": rounds_completed,
            "technology": technology,
        }
