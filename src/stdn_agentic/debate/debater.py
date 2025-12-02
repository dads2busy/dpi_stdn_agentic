"""
Multi-agent debate system for STDN (Supply Technology Dependency Network).

This module implements an enhanced debate functionality for achieving consensus
between multiple agents analyzing technology components and materials.

Key enhancements:
- Critique-driven convergence with feedback influence
- Component name normalization for better matching
- Peer support calculation to boost consensus
- Adaptive voting thresholds based on convergence
- Confidence-weighted consensus building
- Dynamic agent-specific confidence scoring
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================


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
    consensus_so_far: List[str]


# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================


class ComponentWithConfidence(BaseModel):
    """A single component proposal with confidence and reasoning."""

    name: str = Field(description="Component name")
    confidence: float = Field(
        description="Confidence score (0.0 to 1.0) that this is a primary component", ge=0.0, le=1.0
    )
    reasoning: str = Field(description="Brief justification for this component")


class DebateResponse(BaseModel):
    """Structured response from an agent in a debate round."""

    components: List[ComponentWithConfidence] = Field(
        description="List of proposed components with confidence scores"
    )


# ============================================================================
# MultiAgentDebater
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
    - Dynamic agent-specific confidence scores
    """

    def __init__(
        self,
        max_rounds: int = 3,
        convergence_threshold: float = 0.8,
        confidence_weight: float = 0.3,
        peer_support_boost: float = 0.15,
        debate_top_p: float = 0.0001,
    ) -> None:
        """
        Initialize the enhanced multi-agent debater.

        Args:
            max_rounds:
                Maximum number of debate rounds (default: 3).
            convergence_threshold:
                Stop debate when convergence >= this value (default: 0.8).
            confidence_weight:
                Weight for confidence in voting (0–1, default: 0.3).
            peer_support_boost:
                Confidence boost per supporting agent (default: 0.15).
            debate_top_p:
                Top-p sampling for debate rounds (default: 0.0001 for determinism).
        """
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.confidence_weight = confidence_weight
        self.peer_support_boost = peer_support_boost
        self.debate_history: List[DebateRound] = []
        self.debate_top_p = debate_top_p

    # ------------------------------------------------------------------#
    # Normalization helpers
    # ------------------------------------------------------------------#

    async def _normalize_initial_proposals(
        self,
        initial_proposals: Dict[str, List[Dict[str, Any]]],
        component_agent: Any,
        deps: Any,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Semantically normalize all component names across all agents BEFORE debate.

        This ensures all agents use the same normalized names from the start,
        improving convergence and consensus quality.
        """
        # Flatten all proposals to collect component names
        all_proposals = []
        for agent_id, agent_props in initial_proposals.items():
            for prop in agent_props:
                if isinstance(prop, dict):
                    p = dict(prop)
                else:
                    p = {
                        "agent_id": getattr(prop, "agent_id", agent_id),
                        "component": getattr(prop, "component_name", ""),
                        "confidence": getattr(prop, "confidence", 0.8),
                        "reasoning": getattr(prop, "reasoning", ""),
                        "round": getattr(prop, "round", 1),
                    }
                p.setdefault("agent_id", agent_id)
                all_proposals.append(p)

        if not all_proposals:
            return initial_proposals

        # Collect all unique component names
        all_component_names = [
            p.get("component") or p.get("component_name", "") for p in all_proposals
        ]

        print(
            f"\n🔄 Semantic normalization of {len(set(all_component_names))} unique components..."
        )

        # Use LLM semantic normalization
        normalization_map = await self.normalize_components_with_llm(
            all_component_names,
            component_agent,
            deps,
        )

        print(f"✓ Normalized to {len(set(normalization_map.values()))} unique concepts\n")

        # Apply normalization to all proposals
        normalized_proposals = {}
        for agent_id, agent_props in initial_proposals.items():
            updated = []
            for prop in agent_props:
                if isinstance(prop, dict):
                    p = dict(prop)
                else:
                    p = {
                        "agent_id": getattr(prop, "agent_id", agent_id),
                        "component": getattr(prop, "component_name", ""),
                        "confidence": getattr(prop, "confidence", 0.8),
                        "reasoning": getattr(prop, "reasoning", ""),
                        "round": getattr(prop, "round", 1),
                    }

                original = p.get("component", "")
                normalized = normalization_map.get(
                    original, self.normalize_component_name(original)
                )
                p["normalized_component"] = normalized
                updated.append(p)

            normalized_proposals[agent_id] = updated

        return normalized_proposals

    def normalize_component_name(self, name: str) -> str:
        """Normalize component name using a rule-based approach."""
        if not name:
            return ""

        normalized = name.lower().strip()
        normalized = normalized.replace("-", " ").replace("_", " ")
        normalized = " ".join(normalized.split())

        qualifiers = [
            "system",
            "module",
            "unit",
            "assembly",
            "component",
            "subsystem",
            "package",
            "chipset",
        ]
        words = normalized.split()
        while len(words) > 1 and words[-1] in qualifiers:
            words.pop()

        return " ".join(words)

    async def normalize_components_with_llm(
        self,
        component_names: List[str],
        component_agent: Any,
        deps: Any,
    ) -> Dict[str, str]:
        """
        Use LLM to normalize component names semantically.

        Falls back to rule-based normalization if the LLM call fails.
        """
        from pydantic_ai import Agent

        unique_names = list(set(component_names))
        if len(unique_names) <= 1:
            return {name: self.normalize_component_name(name) for name in unique_names}

        class ComponentMapping(BaseModel):
            mappings: Dict[str, str] = Field(description="Component name mappings")

        names_list = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(unique_names))
        prompt = f"""Map duplicate/similar component names to canonical names.

NAMES:
{names_list}

RULES:
- Treat names as the same if they differ only by spacing, prefixes/suffixes,
  or generic qualifiers like "module", "system", "unit", "assembly".
- Treat names as different if they represent clearly different functions.

Return JSON with a single field "mappings" mapping each original name
to its canonical form.
"""

        try:
            agent = Agent(
                model=deps.model,
                output_type=ComponentMapping,
                deps_type=type(deps),
                system_prompt="Normalize component names to canonical forms.",
            )

            result = await agent.run(prompt, deps=deps)
            mapping = dict(result.output.mappings)

            # Ensure complete coverage
            for name in unique_names:
                mapping.setdefault(name, self.normalize_component_name(name))

            logger.info("✓ LLM normalization produced %d unique names", len(set(mapping.values())))
            return mapping
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM normalization failed: %s", exc)
            return {name: self.normalize_component_name(name) for name in unique_names}

    # ------------------------------------------------------------------#
    # Internal helpers for proposals
    # ------------------------------------------------------------------#

    @staticmethod
    def _get_prop_value(prop: Any, key: str, default: Any = None) -> Any:
        """Safely extract a field from either dict-like or AgentProposal."""
        if isinstance(prop, AgentProposal):
            return getattr(prop, key, default)
        if isinstance(prop, dict):
            return prop.get(key, default)
        return default

    # ------------------------------------------------------------------#
    # Convergence and support
    # ------------------------------------------------------------------#

    def calculate_peer_support(self, component_name: str, proposals: List[Dict[str, Any]]) -> int:
        """
        Calculate how many distinct agents support a (normalized) component.

        Args:
            component_name:
                Component name to evaluate (may be unnormalized).
            proposals:
                List of proposal dicts or AgentProposal objects.

        Returns:
            Count of distinct agents proposing an equivalent normalized name.
        """
        target = self.normalize_component_name(component_name)
        agents: set[str] = set()

        for prop in proposals:
            agent_id = self._get_prop_value(prop, "agent_id", "unknown")
            comp = (
                self._get_prop_value(prop, "normalized_component")
                or self._get_prop_value(prop, "component")
                or self._get_prop_value(prop, "component_name")
                or ""
            )
            if self.normalize_component_name(comp) == target:
                agents.add(agent_id)

        return len(agents)

    def calculate_convergence(self, proposals: List[Dict[str, Any]]) -> float:
        """
        Calculate convergence score using Jaccard similarity on normalized names.

        Convergence is the average Jaccard similarity between all agent pairs.
        """
        if not proposals:
            return 0.0

        agent_sets: Dict[str, set[str]] = {}

        for prop in proposals:
            agent_id = self._get_prop_value(prop, "agent_id", "unknown")
            name = (
                self._get_prop_value(prop, "component")
                or self._get_prop_value(prop, "component_name")
                or ""
            )
            norm = self.normalize_component_name(name)
            if not norm:
                continue

            agent_sets.setdefault(agent_id, set()).add(norm)

        if not agent_sets:
            return 0.0

        if len(agent_sets) == 1:
            return 1.0

        agents = list(agent_sets.keys())
        similarities: List[float] = []

        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                set_i = agent_sets[agents[i]]
                set_j = agent_sets[agents[j]]
                union = len(set_i | set_j)
                if union == 0:
                    continue
                intersection = len(set_i & set_j)
                similarities.append(intersection / union)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def calculate_convergence_semantic(self, proposals: List[Dict[str, Any]]) -> float:
        """
        Calculate convergence score using semantically normalized component names.

        This mirrors `calculate_convergence` but prefers the `normalized_component`
        field on each proposal, falling back to raw names when needed.
        """
        if not proposals:
            return 0.0

        agent_sets: Dict[str, set[str]] = {}

        for prop in proposals:
            agent_id = self._get_prop_value(prop, "agent_id", "unknown")
            name = (
                self._get_prop_value(prop, "normalized_component")
                or self._get_prop_value(prop, "component")
                or self._get_prop_value(prop, "component_name")
                or ""
            )
            norm = self.normalize_component_name(name)
            if not norm:
                continue

            agent_sets.setdefault(agent_id, set()).add(norm)

        if not agent_sets:
            return 0.0

        if len(agent_sets) == 1:
            return 1.0

        agents = list(agent_sets.keys())
        similarities: List[float] = []

        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                set_i = agent_sets[agents[i]]
                set_j = agent_sets[agents[j]]
                union = len(set_i | set_j)
                if union == 0:
                    continue
                intersection = len(set_i & set_j)
                similarities.append(intersection / union)

        return sum(similarities) / len(similarities) if similarities else 0.0

    # ------------------------------------------------------------------#
    # Critiques and consensus
    # ------------------------------------------------------------------#

    def generate_critiques_with_influence(
        self,
        proposals: List[Dict[str, Any]],
        roundnum: int,
    ) -> List[str]:
        """
        Generate human-readable critique strings that reflect peer influence.

        The output is a flat list of critique messages that can be fed back
        into the next round prompts.
        """
        critiques: List[str] = []

        # Compute normalized components and support
        norm_to_props: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for prop in proposals:
            name = (
                self._get_prop_value(prop, "normalized_component")
                or self._get_prop_value(prop, "component")
                or self._get_prop_value(prop, "component_name")
                or ""
            )
            agent_id = self._get_prop_value(prop, "agent_id", "unknown")
            confidence = float(self._get_prop_value(prop, "confidence", 0.8))
            norm = self.normalize_component_name(name)
            if not norm:
                continue
            norm_to_props[norm].append(
                {
                    "agent_id": agent_id,
                    "name": name,
                    "norm": norm,
                    "confidence": confidence,
                },
            )

        if not norm_to_props:
            critiques.append(
                "No strong proposals emerged; agents should propose a clear, "
                "well-justified component set in the next round.",
            )
            return critiques

        num_agents = len({p["agent_id"] for props in norm_to_props.values() for p in props})
        majority_threshold = max(2, int(0.67 * max(num_agents, 1))) if num_agents > 1 else 1

        # Consensus components
        for norm_name, props_for_name in norm_to_props.items():
            supporters = {p["agent_id"] for p in props_for_name}
            avg_conf = sum(p["confidence"] for p in props_for_name) / len(props_for_name)

            if len(supporters) >= majority_threshold:
                critiques.append(
                    f"Strong consensus on '{norm_name}': {len(supporters)} agents support it "
                    f"with average confidence {avg_conf:.2f}. This should be preserved.",
                )

        # Isolated / weak proposals
        for norm_name, props_for_name in norm_to_props.items():
            supporters = {p["agent_id"] for p in props_for_name}
            avg_conf = sum(p["confidence"] for p in props_for_name) / len(props_for_name)

            if len(supporters) == 1:
                critiques.append(
                    f"Isolated proposal '{norm_name}' appears only once with "
                    f"average confidence {avg_conf:.2f}; reconsider unless critically justified.",
                )

        # General guidance (round-dependent but intentionally not referencing future rounds)
        if roundnum == 1:
            critiques.append(
                "Focus on aligning on obvious shared components while dropping clearly "
                "idiosyncratic proposals.",
            )
        elif roundnum >= 2:
            critiques.append(
                "Consolidate around components that have multi-agent support and high confidence, "
                "and prune uncertain or unsupported components.",
            )

        return critiques

    def build_adaptive_consensus(
        self,
        proposals: List[Dict[str, Any]],
        convergence_score: float,
    ) -> List[str]:
        """
        Build consensus components using adaptive thresholds and confidence weighting.

        This version works on raw component names and rule-based normalization.
        """
        if not proposals:
            return []

        norm_to_confidences: Dict[str, List[float]] = defaultdict(list)
        norm_to_agents: Dict[str, set[str]] = defaultdict(set)

        for prop in proposals:
            agent_id = self._get_prop_value(prop, "agent_id", "unknown")
            name = (
                self._get_prop_value(prop, "component")
                or self._get_prop_value(prop, "component_name")
                or ""
            )
            norm = self.normalize_component_name(name)
            if not norm:
                continue

            confidence = float(self._get_prop_value(prop, "confidence", 0.8))
            norm_to_confidences[norm].append(confidence)
            norm_to_agents[norm].add(agent_id)

        if not norm_to_confidences:
            return []

        num_agents = max(len(agent_set) for agent_set in norm_to_agents.values())

        # Adaptive support threshold: strict at high convergence, lenient at low.
        if convergence_score >= 0.7:
            min_support_frac = 2.0 / 3.0
        elif convergence_score <= 0.2:
            min_support_frac = 1.0 / 3.0
        else:
            # Linear interpolation between 1/3 and 2/3
            frac = (convergence_score - 0.2) / (0.7 - 0.2)
            min_support_frac = (1.0 / 3.0) + frac * (1.0 / 3.0)

        min_support = max(1, int(round(min_support_frac * max(num_agents, 1))))

        scores: Dict[str, float] = {}

        for norm_name, confs in norm_to_confidences.items():
            support = len(norm_to_agents[norm_name])
            avg_conf = sum(confs) / len(confs)
            support_frac = support / max(num_agents, 1)

            # Combined score with peer support boost
            score = (
                (1.0 - self.confidence_weight) * support_frac
                + self.confidence_weight * avg_conf
                + self.peer_support_boost * (support - 1)
            )

            if support >= min_support:
                scores[norm_name] = score

        # Sort by score descending and return normalized component names
        consensus = [name for name, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]
        return consensus

    def build_adaptive_consensus_semantic(
        self,
        proposals: List[Dict[str, Any]],
        convergence_score: float,
    ) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:  # ✅ Return tuple: (names, details)
        """
        Build consensus using semantically normalized component names.

        Returns:
            Tuple of (consensus_names, component_details) where component_details
            maps normalized names to their original names, confidence, and reasoning.
        """
        if not proposals:
            return [], {}

        norm_to_confidences: Dict[str, List[float]] = defaultdict(list)
        norm_to_agents: Dict[str, set[str]] = defaultdict(set)
        norm_to_proposals: Dict[str, List[Dict[str, Any]]] = defaultdict(list)  # ✅ Track proposals

        for prop in proposals:
            agent_id = self._get_prop_value(prop, "agent_id", "unknown")
            name = (
                self._get_prop_value(prop, "normalized_component")
                or self._get_prop_value(prop, "component")
                or self._get_prop_value(prop, "component_name")
                or ""
            )
            norm = self.normalize_component_name(name)
            if not norm:
                continue

            confidence = float(self._get_prop_value(prop, "confidence", 0.8))
            norm_to_confidences[norm].append(confidence)
            norm_to_agents[norm].add(agent_id)
            norm_to_proposals[norm].append(prop)  # ✅ Store proposal

        if not norm_to_confidences:
            return [], {}

        num_agents = max(len(agent_set) for agent_set in norm_to_agents.values())

        if convergence_score >= 0.9:  # ✅ Raise from 0.7 to 0.9
            min_support_frac = 2.0 / 3.0
        elif convergence_score <= 0.3:
            min_support_frac = 1.0 / 3.0
        else:
            frac = (convergence_score - 0.3) / (0.9 - 0.3)
            min_support_frac = (1.0 / 3.0) + frac * (1.0 / 3.0)

        min_support = max(1, int(round(min_support_frac * max(num_agents, 1))))

        scores: Dict[str, float] = {}

        for norm_name, confs in norm_to_confidences.items():
            support = len(norm_to_agents[norm_name])
            avg_conf = sum(confs) / len(confs)
            support_frac = support / max(num_agents, 1)

            score = (
                (1.0 - self.confidence_weight) * support_frac
                + self.confidence_weight * avg_conf
                + self.peer_support_boost * (support - 1)
            )

            if support >= min_support:
                scores[norm_name] = score

        consensus = [name for name, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]

        # ✅ BUILD COMPONENT DETAILS MAP
        component_details = {}
        for norm_name in consensus:
            # Get all proposals for this normalized name
            matching_props = norm_to_proposals[norm_name]

            # Find the proposal with highest confidence (or most recent)
            best_prop = max(
                matching_props, key=lambda p: self._get_prop_value(p, "confidence", 0.0)
            )

            # Extract original name (before normalization)
            original_name = (
                self._get_prop_value(best_prop, "component")
                or self._get_prop_value(best_prop, "component_name")
                or norm_name.title()
            )

            # Get confidence and reasoning
            confidence = self._get_prop_value(best_prop, "confidence", 0.75)
            reasoning = self._get_prop_value(
                best_prop, "reasoning", "Consensus component from debate"
            )

            component_details[norm_name] = {
                "original_name": original_name,
                "confidence": float(confidence),
                "reasoning": reasoning,
            }

        return consensus, component_details  # ✅ Return both

    # ------------------------------------------------------------------#
    # Round execution and full debate
    # ------------------------------------------------------------------#

    async def run_debate_round(
        self,
        technology: str,
        previous_proposals: List[Dict[str, Any]],
        critiques: List[str],
        component_agent: Any,
        deps: Any,
        roundnum: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run a single debate round with critique feedback and dynamic confidence scoring.

        Returns:
            Dict mapping agent_id -> list of proposal dicts with confidence scores.
        """
        from dataclasses import replace

        from pydantic_ai import Agent

        prev_context = "\n".join(
            f"- {self._get_prop_value(p, 'agent_id', 'unknown')}: "
            f"{self._get_prop_value(p, 'component') or self._get_prop_value(p, 'component_name', '')} "
            f"(confidence={self._get_prop_value(p, 'confidence', 0.8):.2f})"
            for p in previous_proposals
        )
        critique_text = "\n".join(critiques)

        # Enhanced system prompt that emphasizes confidence scoring
        system_prompt = """You are an expert in technology component analysis participating in a multi-agent debate.

Your task is to identify PRIMARY MANUFACTURING COMPONENTS for technologies.

CRITICAL: For each component, you MUST provide:
1. Component name
2. Your confidence (0.0 to 1.0) that this is truly a primary component:
   - 1.0 = Absolutely certain, universal standard
   - 0.8-0.9 = Very confident, industry standard
   - 0.6-0.7 = Moderately confident, common but may vary
   - 0.4-0.5 = Uncertain, depends on implementation
   - 0.0-0.3 = Low confidence, rarely separate
3. Brief reasoning justifying your confidence

Consider peer proposals and critiques carefully. Adjust your confidence based on:
- Consensus among peers (higher confidence if many agree)
- Strength of reasoning in critiques
- Your own expertise and certainty
"""

        new_proposals: Dict[str, List[Dict[str, Any]]] = {}

        # Create a specialized agent for structured debate responses
        debate_agent = Agent(
            model=deps.model,
            output_type=DebateResponse,
            deps_type=type(deps),
            system_prompt=system_prompt,
        )

        # Use 3 agents with simple persona labels
        for agent_num in range(1, 4):
            agent_id = f"Agent{agent_num}"

            prompt = f"""DEBATE ROUND {roundnum}

Technology: {technology}

PREVIOUS ROUND PROPOSALS:
{prev_context}

PEER CRITIQUES AND GUIDANCE:
{critique_text}

YOUR TASK:
1. Review all peer proposals and critiques carefully
2. For EACH component you propose, assign a confidence score (0.0-1.0) based on:
   - How certain you are it's a primary component
   - Degree of peer support or opposition
   - Strength of evidence and reasoning
3. Support strong consensus candidates with high confidence
4. Lower confidence for isolated proposals unless critically justified
5. Provide clear reasoning for each confidence assessment

Return your refined component list with confidence scores and reasoning.
"""

            try:
                # Use very low Top-P for deterministic, focused refinements
                debate_deps = replace(deps, top_p=self.debate_top_p)

                result = await debate_agent.run(prompt, deps=debate_deps, model=deps.model)

                if result and result.output and result.output.components:
                    proposals_list = []
                    for comp in result.output.components:
                        proposals_list.append(
                            {
                                "agent_id": agent_id,
                                "component": comp.name,
                                "confidence": comp.confidence,  # LLM-provided confidence
                                "reasoning": comp.reasoning,
                                "round": roundnum,
                            }
                        )
                    new_proposals[agent_id] = proposals_list

                    # Log confidence distribution for monitoring
                    avg_conf = sum(p["confidence"] for p in proposals_list) / len(proposals_list)
                    logger.info(
                        f"Round {roundnum} - {agent_id}: {len(proposals_list)} components, "
                        f"avg confidence={avg_conf:.2f}"
                    )
                else:
                    logger.warning(f"No components returned from {agent_id} in round {roundnum}")
                    new_proposals[agent_id] = []

            except Exception as exc:  # noqa: BLE001
                logger.error("Error in debate round %s for %s: %s", roundnum, agent_id, exc)
                # Fall back to previous proposals for this agent, if any
                prev_for_agent = [
                    p for p in previous_proposals if self._get_prop_value(p, "agent_id") == agent_id
                ]
                new_proposals[agent_id] = prev_for_agent

        return new_proposals

    async def run_debate(
        self,
        technology: str,
        initial_proposals: Dict[str, List[Dict[str, Any]]],
        component_agent: Any,
        deps: Any,
    ) -> Dict[str, Any]:
        """
        Run multi-round debate with LLM-based semantic normalization and dynamic confidence.

        Args:
            technology:
                Technology name.
            initial_proposals:
                Mapping agent_id -> list of proposal dicts.
            component_agent:
                Agent to use for refinement and normalization.
            deps:
                Shared STDN dependencies (includes model name).

        Returns:
            Dict with keys:
                - "technology": technology name
                - "components": list of consensus component names
                - "confidence": final convergence score
                - "rounds": number of rounds completed
                - "debate_history": list of per-round metadata dicts
        """
        convergence = 0.0
        rounds_completed = 0
        debate_rounds: List[Dict[str, Any]] = []

        print("=" * 80)
        print(f"DEBATE: {technology}")
        print("=" * 80)

        current_proposals = await self._normalize_initial_proposals(
            initial_proposals, component_agent, deps
        )

        for roundnum in range(self.max_rounds):
            print(f"ROUND {roundnum + 1}:")

            # Flatten proposals for analysis
            all_proposals: List[Dict[str, Any]] = []
            for agent_id, agent_props in current_proposals.items():
                for prop in agent_props:
                    if isinstance(prop, dict):
                        p = dict(prop)
                    else:
                        p = {
                            "agent_id": getattr(prop, "agent_id", agent_id),
                            "component": getattr(prop, "component_name", ""),
                            "confidence": getattr(prop, "confidence", 0.8),
                            "reasoning": getattr(prop, "reasoning", ""),
                            "round": getattr(prop, "round", roundnum),
                        }
                    p.setdefault("agent_id", agent_id)
                    all_proposals.append(p)

            if not all_proposals:
                print("  ⚠ No proposals available for this round.")
                break

            # Log confidence statistics
            confidences = [p.get("confidence", 0.8) for p in all_proposals]
            avg_conf = sum(confidences) / len(confidences)
            min_conf = min(confidences)
            max_conf = max(confidences)
            print(f"  Confidence: avg={avg_conf:.2f}, min={min_conf:.2f}, max={max_conf:.2f}")

            # Calculate convergence using normalized names
            convergence = self.calculate_convergence_semantic(all_proposals)
            print(f"  Convergence: {convergence:.1%}")
            rounds_completed = roundnum + 1

            # Store round data for transcript
            debate_rounds.append(
                {
                    "round_num": roundnum + 1,
                    "convergence": convergence,
                    "proposals": current_proposals.copy(),
                    "rounds_completed": rounds_completed,
                },
            )

            # Stop if threshold reached
            if convergence >= self.convergence_threshold:
                print("  ✅ Convergence threshold reached!")
                break

            # If not last round, generate critiques and refine proposals
            if roundnum < self.max_rounds - 1:
                print("  Generating critiques...")
                critiques = self.generate_critiques_with_influence(all_proposals, roundnum + 1)
                print("  Refining proposals based on peer feedback...")
                current_proposals = await self.run_debate_round(
                    technology=technology,
                    previous_proposals=all_proposals,
                    critiques=critiques,
                    component_agent=component_agent,
                    deps=deps,
                    roundnum=roundnum + 2,  # Next round number
                )

        # Final consensus building
        all_final_proposals: List[Dict[str, Any]] = []
        for agent_props in current_proposals.values():
            all_final_proposals.extend(agent_props)

        final_component_names = [
            p.get("component") or p.get("component_name", "") for p in all_final_proposals
        ]
        if final_component_names:
            print("  Building final consensus with semantic normalization...")
            final_norm_map = await self.normalize_components_with_llm(
                final_component_names,
                component_agent,
                deps,
            )
            for prop in all_final_proposals:
                original = prop.get("component") or prop.get("component_name", "")
                norm = final_norm_map.get(original, original)
                prop["normalized_component"] = norm

        print(f"\n🔍 All final proposals before consensus:")
        for prop in all_final_proposals:
            norm = prop.get("normalized_component", prop.get("component", ""))
            agent = prop.get("agent_id", "unknown")
            conf = prop.get("confidence", 0.0)
            print(f"  '{norm}' - agent: {agent}, confidence: {conf:.2f}")

        consensus, component_details = self.build_adaptive_consensus_semantic(  # ✅ Unpack tuple
            all_final_proposals,
            convergence_score=convergence,
        )
        print(f"  Extracted {len(consensus)} components with dynamic confidence weighting")

        return {
            "technology": technology,
            "components": consensus,
            "component_details": component_details,
            "confidence": convergence,
            "rounds": rounds_completed,
            "debate_history": debate_rounds,
        }


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "MultiAgentDebater",
    "AgentProposal",
    "DebateRound",
    "ComponentWithConfidence",
    "DebateResponse",
]
