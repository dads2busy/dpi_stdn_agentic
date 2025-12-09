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
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .component_models import (
    AgentProposal,
    ComponentWithConfidence,
    DebateResponse,
    DebateRound,
)
from .component_normalization import (
    normalize_component_name,
    normalize_components_with_llm,
)

logger = logging.getLogger(__name__)


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
        max_rounds: int = 5,
        convergence_threshold: float = 0.75,
        confidence_weight: float = 0.3,
        peer_support_boost: float = 0.15,
        debate_top_p: float = 0.0001,
    ) -> None:
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.confidence_weight = confidence_weight
        self.peer_support_boost = peer_support_boost
        self.debate_history: List[DebateRound] = []
        self.debate_top_p = debate_top_p

    async def _normalize_initial_proposals(
        self,
        initial_proposals: Dict[str, List[Dict[str, Any]]],
        component_agent: Any,
        deps: Any,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Semantically normalize all component names across all agents BEFORE debate.
        """
        all_proposals: List[Dict[str, Any]] = []
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

        all_component_names = [
            p.get("component") or p.get("component_name", "") for p in all_proposals
        ]

        print(
            f"\n🔄 Semantic normalization of {len(set(all_component_names))} unique components..."
        )

        normalization_map = await normalize_components_with_llm(
            all_component_names,
            component_agent,
            deps,
        )

        print(f"✓ Normalized to {len(set(normalization_map.values()))} unique concepts\n")

        normalized_proposals: Dict[str, List[Dict[str, Any]]] = {}
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
                normalized = normalization_map.get(original, normalize_component_name(original))
                p["normalized_component"] = normalized
                updated.append(p)

            normalized_proposals[agent_id] = updated

        return normalized_proposals

    # ... rest of MultiAgentDebater stays as-is, but if it previously called
    # self.normalize_component_name or self.normalize_components_with_llm,
    # update those calls to use normalize_component_name(...) and
    # normalize_components_with_llm(...) from the imports.

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

        unique_names = list(set(component_names))
        if len(unique_names) <= 1:
            return {name: self.normalize_component_name(name) for name in unique_names}

        class ComponentMapping(BaseModel):
            mappings: Dict[str, str] = Field(description="Component name mappings")

        names_list = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(unique_names))
        prompt = f"""Map duplicate/similar component names to canonical names.

    CRITICAL: All output must be in English only. If any input names are in other
    languages, translate them to English equivalents before mapping.

    AVOID OVERLY GENERIC NAMES:
    - Do NOT use vague terms like "Chip", "Module", "Component", "Part", "Unit"
    - Use SPECIFIC names like "Memory Chip", "Power IC", "Display Module"
    - If a component is too generic to identify, mark it as "Generic Component"

    NAMES:
    {names_list}

    RULES:
    - Treat names as the same if they differ only by spacing, prefixes/suffixes,
      or generic qualifiers like "module", "system", "unit", "assembly".
    - Treat names as different if they represent clearly different functions.
    - Use clear, standard English terminology for all canonical names.
    - Prefer specific technical terms over generic ones.

    EXAMPLES:
    - "Main Circuit Board (PCB)" → "Main Circuit Board"
    - "PCB" → "Main Circuit Board"
    - "Motherboard" → "Main Circuit Board"
    - "Display Module (OLED)" → "Display Module"
    - "OLED Display" → "Display Module"
    - "Touch Screen" → "Display Module"
    - "Memory (RAM)" → "Memory"
    - "RAM" → "Memory"
    - "Memory (RAM & Storage)" → "Memory"
    - "Storage" → "Storage"
    - "Flash Storage" → "Storage"

    Return JSON with a single field "mappings" mapping each original name
    to its canonical form.
    """

        try:
            agent = Agent(
                model=deps.model,
                output_type=ComponentMapping,
                deps_type=type(deps),
                system_prompt="You are a component naming expert. Normalize component names to canonical English forms. Always respond in English only.",
            )

            result = await agent.run(prompt, deps=deps)
            mapping = dict(result.output.mappings)

            # Ensure complete coverage
            for name in unique_names:
                mapping.setdefault(name, self.normalize_component_name(name))

            # ✅ DEBUG LOGGING
            print("\n🔍 LLM Normalization Results:")
            print(f"   Input: {len(unique_names)} unique component names")
            print(f"   Output: {len(set(mapping.values()))} normalized canonical names")

            # Group by normalized name to show what got merged
            normalized_groups = {}
            for original, normalized in mapping.items():
                if normalized not in normalized_groups:
                    normalized_groups[normalized] = []
                normalized_groups[normalized].append(original)

            print("\n   Normalization Mappings:")
            for normalized, originals in sorted(normalized_groups.items()):
                if len(originals) > 1:
                    # Show merged components
                    print(f"   ✓ '{normalized}' ← merged from {len(originals)} variants:")
                    for orig in originals:
                        print(f"      - '{orig}'")
                else:
                    # No change
                    if originals[0] != normalized:
                        print(f"   → '{originals[0]}' → '{normalized}'")

            logger.info("✓ LLM normalization produced %d unique names", len(set(mapping.values())))
            return mapping

        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM normalization failed: %s", exc)
            print("⚠️ LLM normalization failed, using rule-based fallback")
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
    ) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """
        Build consensus using semantically normalized component names.

        Returns:
            Tuple of (consensus_names, component_details) where component_details
            maps normalized names to their original names, confidence, and reasoning.
        """
        if not proposals:
            return [], {}

        (
            norm_to_confidences,
            norm_to_agents,
            norm_to_proposals,
        ) = self._aggregate_proposals_by_norm(proposals)

        if not norm_to_confidences:
            return [], {}

        num_agents = max(len(agent_set) for agent_set in norm_to_agents.values())
        min_support = self._compute_min_support(convergence_score, num_agents)

        scores = self._score_consensus_candidates(
            norm_to_confidences,
            norm_to_agents,
            num_agents,
            min_support,
        )

        self._log_consensus_scoring_debug(
            convergence_score,
            min_support,
            num_agents,
            norm_to_confidences,
            norm_to_agents,
            scores,
        )

        consensus = [name for name, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]

        component_details = self._build_component_details(consensus, norm_to_proposals)

        return consensus, component_details

    def _aggregate_proposals_by_norm(
        self,
        proposals: List[Dict[str, Any]],
    ) -> tuple[
        Dict[str, List[float]],
        Dict[str, set[str]],
        Dict[str, List[Dict[str, Any]]],
    ]:
        norm_to_confidences: Dict[str, List[float]] = defaultdict(list)
        norm_to_agents: Dict[str, set[str]] = defaultdict(set)
        norm_to_proposals: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for prop in proposals:
            agent_id = self._get_prop_value(prop, "agent_id", "unknown")

            norm = (
                self._get_prop_value(prop, "normalized_component")
                or self._get_prop_value(prop, "component")
                or self._get_prop_value(prop, "component_name")
                or ""
            )

            norm = norm.strip()
            if norm:
                norm = " ".join(word.capitalize() for word in norm.split())

            if not norm or not norm.strip():
                continue

            confidence = float(self._get_prop_value(prop, "confidence", 0.8))
            norm_to_confidences[norm].append(confidence)
            norm_to_agents[norm].add(agent_id)
            norm_to_proposals[norm].append(prop)

        return norm_to_confidences, norm_to_agents, norm_to_proposals

    def _compute_min_support(
        self,
        convergence_score: float,
        num_agents: int,
    ) -> int:
        if convergence_score >= 0.9:
            min_support_frac = 2.0 / 3.0
        elif convergence_score <= 0.3:
            min_support_frac = 1.0 / 3.0
        else:
            frac = (convergence_score - 0.3) / (0.9 - 0.3)
            min_support_frac = (1.0 / 3.0) + frac * (1.0 / 3.0)

        return max(1, int(round(min_support_frac * max(num_agents, 1))))

    def _score_consensus_candidates(
        self,
        norm_to_confidences: Dict[str, List[float]],
        norm_to_agents: Dict[str, set[str]],
        num_agents: int,
        min_support: int,
    ) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        MIN_CONFIDENCE = 0.7

        for norm_name, confs in norm_to_confidences.items():
            support = len(norm_to_agents[norm_name])
            avg_conf = sum(confs) / len(confs)
            support_frac = support / max(num_agents, 1)

            score = (
                (1.0 - self.confidence_weight) * support_frac
                + self.confidence_weight * avg_conf
                + self.peer_support_boost * (support - 1)
            )

            if support >= min_support and avg_conf >= MIN_CONFIDENCE:
                scores[norm_name] = score
            elif support >= min_support:
                print(
                    f"   ⚠️ Excluded '{norm_name}': confidence {avg_conf:.2f} below {MIN_CONFIDENCE}"
                )

        return scores

    def _log_consensus_scoring_debug(
        self,
        convergence_score: float,
        min_support: int,
        num_agents: int,
        norm_to_confidences: Dict[str, List[float]],
        norm_to_agents: Dict[str, set[str]],
        scores: Dict[str, float],
    ) -> None:
        print("\n🔍 Consensus Scoring Debug:")
        print(f"   Convergence: {convergence_score:.2f}")
        print(f"   Min support required: {min_support}/{num_agents} agents")
        print(f"   Peer support boost: {self.peer_support_boost}")
        print("\n   Component Scoring:")

        all_norms = sorted(norm_to_confidences.keys())
        for norm_name in all_norms:
            support = len(norm_to_agents[norm_name])
            confs = norm_to_confidences[norm_name]
            avg_conf = sum(confs) / len(confs)

            if norm_name in scores:
                score = scores[norm_name]
                print(
                    f"   ✓ '{norm_name}': {support}/{num_agents} agents, "
                    f"avg_conf={avg_conf:.2f}, score={score:.3f}"
                )
            else:
                print(
                    f"   ✗ '{norm_name}': {support}/{num_agents} agents, "
                    f"avg_conf={avg_conf:.2f} — EXCLUDED (below min_support)"
                )

    def _build_component_details(
        self,
        consensus: List[str],
        norm_to_proposals: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Dict[str, Any]]:
        component_details: Dict[str, Dict[str, Any]] = {}

        for norm_name in consensus:
            matching_props = norm_to_proposals[norm_name]

            best_prop = max(
                matching_props,
                key=lambda p: self._get_prop_value(p, "confidence", 0.0),
            )

            original_name = (
                self._get_prop_value(best_prop, "component")
                or self._get_prop_value(best_prop, "component_name")
                or norm_name.title()
            )

            confidence = self._get_prop_value(best_prop, "confidence", 0.75)
            reasoning = self._get_prop_value(
                best_prop,
                "reasoning",
                "Consensus component from debate",
            )

            component_details[norm_name] = {
                "original_name": original_name,
                "confidence": float(confidence),
                "reasoning": reasoning,
            }

        return component_details

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

        # Build context from previous proposals
        prev_context = "\n".join(
            f"- {self._get_prop_value(p, 'agent_id', 'unknown')}: "
            f"{self._get_prop_value(p, 'component') or self._get_prop_value(p, 'component_name', '')} "
            f"(confidence={self._get_prop_value(p, 'confidence', 0.8):.2f})"
            for p in previous_proposals
        )
        critique_text = "\n".join(critiques)

        # Validate that we have content to send to LLM
        if not prev_context or not prev_context.strip():
            prev_context = "No previous proposals available."
            logger.warning(f"Round {roundnum}: No previous proposals, using fallback text")

        if not critique_text or not critique_text.strip():
            critique_text = "Focus on reaching consensus on essential components."
            logger.warning(f"Round {roundnum}: No critiques, using fallback text")

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

            # Build the debate prompt
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

            # Validate final prompt before sending to LLM
            if not prompt or not prompt.strip() or len(prompt) < 100:
                logger.error(
                    f"Invalid prompt for {agent_id} in round {roundnum}: "
                    f"prompt too short or empty (length={len(prompt) if prompt else 0})"
                )
                print(
                    f"  ❌ Skipping {agent_id}: invalid prompt (length={len(prompt) if prompt else 0})"
                )
                # Fall back to previous proposals for this agent
                prev_for_agent = [
                    p for p in previous_proposals if self._get_prop_value(p, "agent_id") == agent_id
                ]
                new_proposals[agent_id] = prev_for_agent
                continue  # Skip to next agent

            try:
                # Use very low Top-P for deterministic, focused refinements
                debate_deps = replace(deps, top_p=self.debate_top_p)

                # Debug output to trace what's being sent
                print(f"  🔍 {agent_id} calling LLM with:")
                print(f"     - Prompt length: {len(prompt)} chars")
                print(f"     - Previous proposals: {len(previous_proposals)}")
                print(f"     - Critiques: {len(critiques)}")

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
                    print(
                        f"  ✓ {agent_id}: {len(proposals_list)} components (avg conf: {avg_conf:.2f})"
                    )
                else:
                    logger.warning(f"No components returned from {agent_id} in round {roundnum}")
                    print(f"  ⚠️ {agent_id}: No components returned")
                    new_proposals[agent_id] = []

            except Exception as exc:  # noqa: BLE001
                logger.error("Error in debate round %s for %s: %s", roundnum, agent_id, exc)
                print(f"  ❌ Error in {agent_id}: {exc}")
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
        """
        convergence = 0.0
        rounds_completed = 0
        debate_rounds: List[Dict[str, Any]] = []

        print("=" * 80)
        print(f"DEBATE: {technology}")
        print("=" * 80)

        current_proposals = await self._normalize_initial_proposals(
            initial_proposals,
            component_agent,
            deps,
        )

        (
            convergence,
            rounds_completed,
            debate_rounds,
            current_proposals,
        ) = await self._run_debate_rounds(
            technology,
            current_proposals,
            component_agent,
            deps,
            convergence,
            rounds_completed,
            debate_rounds,
        )

        all_final_proposals = self._flatten_final_proposals(current_proposals)

        await self._apply_final_normalization(
            all_final_proposals,
            component_agent,
            deps,
            rounds_completed,
        )

        consensus, component_details = self.build_adaptive_consensus_semantic(
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

    async def _run_debate_rounds(
        self,
        technology: str,
        current_proposals: Dict[str, List[Dict[str, Any]]],
        component_agent: Any,
        deps: Any,
        convergence: float,
        rounds_completed: int,
        debate_rounds: List[Dict[str, Any]],
    ) -> tuple[
        float,
        int,
        List[Dict[str, Any]],
        Dict[str, List[Dict[str, Any]]],
    ]:
        for roundnum in range(self.max_rounds):
            print(f"ROUND {roundnum + 1}:")

            all_proposals = self._flatten_proposals_for_round(
                current_proposals,
                roundnum,
            )

            if not all_proposals:
                print("  ⚠ No proposals available for this round.")
                break

            self._log_round_confidence_stats(all_proposals)

            convergence = self.calculate_convergence_semantic(all_proposals)
            print(f"  Convergence: {convergence:.1%}")
            rounds_completed = roundnum + 1

            debate_rounds.append(
                {
                    "round_num": roundnum + 1,
                    "convergence": convergence,
                    "proposals": current_proposals.copy(),
                    "rounds_completed": rounds_completed,
                },
            )

            if convergence >= self.convergence_threshold:
                print("  ✅ Convergence threshold reached!")
                break

            if roundnum < self.max_rounds - 1:
                print("  Generating critiques...")
                critiques = self.generate_critiques_with_influence(
                    all_proposals,
                    roundnum + 1,
                )
                print("  Refining proposals based on peer feedback...")
                current_proposals = await self.run_debate_round(
                    technology=technology,
                    previous_proposals=all_proposals,
                    critiques=critiques,
                    component_agent=component_agent,
                    deps=deps,
                    roundnum=roundnum + 2,
                )

        return convergence, rounds_completed, debate_rounds, current_proposals

    def _flatten_proposals_for_round(
        self,
        current_proposals: Dict[str, List[Dict[str, Any]]],
        roundnum: int,
    ) -> List[Dict[str, Any]]:
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
        return all_proposals

    def _log_round_confidence_stats(
        self,
        all_proposals: List[Dict[str, Any]],
    ) -> None:
        confidences = [p.get("confidence", 0.8) for p in all_proposals]
        avg_conf = sum(confidences) / len(confidences)
        min_conf = min(confidences)
        max_conf = max(confidences)
        print(f"  Confidence: avg={avg_conf:.2f}, min={min_conf:.2f}, max={max_conf:.2f}")

    def _flatten_final_proposals(
        self,
        current_proposals: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        all_final_proposals: List[Dict[str, Any]] = []
        for agent_props in current_proposals.values():
            all_final_proposals.extend(agent_props)
        return all_final_proposals

    async def _apply_final_normalization(
        self,
        all_final_proposals: List[Dict[str, Any]],
        component_agent: Any,
        deps: Any,
        rounds_completed: int,
    ) -> None:
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

        print(f"\n🔍 Final Proposals Summary (After Round {rounds_completed}):")

        component_counts: Dict[str, int] = {}
        component_agents: Dict[str, set[str]] = {}
        for prop in all_final_proposals:
            norm = prop.get("normalized_component", prop.get("component", ""))
            agent = prop.get("agent_id", "unknown")

            if norm not in component_counts:
                component_counts[norm] = 0
                component_agents[norm] = set()

            component_counts[norm] += 1
            component_agents[norm].add(agent)

        print("   Components proposed by agents:")
        for name in sorted(component_counts.keys()):
            agent_count = len(component_agents[name])
            total_count = component_counts[name]
            agents = ", ".join(sorted(component_agents[name]))
            print(f"   - '{name}': {agent_count}/3 agents ({total_count} proposals) [{agents}]")

        print("\n🔍 All final proposals before consensus:")
        for prop in all_final_proposals:
            norm = prop.get("normalized_component", prop.get("component", ""))
            agent = prop.get("agent_id", "unknown")
            conf = prop.get("confidence", 0.0)
            print(f"  '{norm}' - agent: {agent}, confidence: {conf:.2f}")


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
