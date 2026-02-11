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

import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ..logging_config import get_logger
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

logger = get_logger(__name__)


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

        # Get component names - check both "name" and "component" fields
        all_component_names = [
            p.get("name") or p.get("component") or p.get("component_name", "")
            for p in all_proposals
        ]

        logger.info(
            "Semantic normalization of %d unique components...",
            len(set(all_component_names)),
        )

        normalization_map = await normalize_components_with_llm(
            all_component_names,
            component_agent,
            deps,
        )

        logger.info("Normalized to %d unique concepts", len(set(normalization_map.values())))

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

                # Get original name from either "name" or "component" field
                original = p.get("name") or p.get("component", "")
                # Ensure "component" field is set for downstream processing
                if "component" not in p and "name" in p:
                    p["component"] = p["name"]
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

        If a canonical vocabulary is available, uses it as the authoritative
        reference for component names. Falls back to rule-based normalization
        if the LLM call fails.
        """

        unique_names = list(set(component_names))
        if len(unique_names) <= 1:
            return {name: self.normalize_component_name(name) for name in unique_names}

        # Check canonical vocab for existing mappings
        mapping: Dict[str, str] = {}
        names_needing_llm: List[str] = []

        if hasattr(self, "canonical_vocab") and self.canonical_vocab is not None:
            for name in unique_names:
                canonical = self.canonical_vocab.lookup(name)
                if canonical:
                    mapping[name] = canonical
                else:
                    names_needing_llm.append(name)

            if mapping:
                logger.info("Found %d names in canonical vocabulary", len(mapping))

            # If all names are in vocab, return early
            if not names_needing_llm:
                logger.info("All component names found in canonical vocabulary")
                return mapping
        else:
            names_needing_llm = unique_names

        class ComponentMapping(BaseModel):
            mappings: Dict[str, str] = Field(description="Component name mappings")

        names_list = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(names_needing_llm))

        # Build canonical vocabulary reference for the prompt
        canonical_examples = ""
        if hasattr(self, "canonical_vocab") and self.canonical_vocab is not None:
            # Get unique canonical names from vocab
            canonical_names = sorted(set(self.canonical_vocab.mappings.values()))
            if canonical_names:
                # Show a sample of canonical names for reference
                sample_size = min(50, len(canonical_names))
                sample_names = canonical_names[:sample_size]
                canonical_examples = f"""
    EXISTING CANONICAL VOCABULARY (use these names when applicable):
    {", ".join(sample_names)}
    {"..." if len(canonical_names) > sample_size else ""}

    IMPORTANT: When a component matches one of these canonical names, USE THE EXACT
    canonical name from this list. This ensures consistency across runs.
    """

        prompt = f"""Map duplicate/similar component names to canonical names.

    CRITICAL: All output must be in English only. If any input names are in other
    languages, translate them to English equivalents before mapping.
    {canonical_examples}
    AVOID OVERLY GENERIC NAMES:
    - Do NOT use vague terms like "Chip", "Module", "Component", "Part", "Unit" alone
    - Use SPECIFIC names like "Memory Chip", "Power IC", "Display Module", "Lithium-ion Battery"
    - Preserve material-relevant distinctions (battery chemistry, display technology, etc.)

    NAMES TO NORMALIZE:
    {names_list}

    RULES:
    - If a name matches or is similar to a canonical name above, use that canonical name
    - Treat names as the same if they differ only by spacing, prefixes/suffixes,
      or generic qualifiers like "module", "system", "unit", "assembly".
    - Treat names as different if they represent clearly different functions.
    - Use clear, standard English terminology for all canonical names.
    - Prefer specific technical terms over generic ones.
    - Preserve battery chemistry types (Lithium-ion, Lead-acid, NiMH, etc.)
    - Preserve display technology types (OLED, LCD, LED, etc.)

    Return JSON with a single field "mappings" mapping each original name
    to its canonical form.
    """

        try:
            # Use a dedicated, more reliable model for semantic normalization.
            #
            # Preference order:
            # 1) Config-driven dependency model (deps.get_component_normalization_model)
            # 2) Environment override (STDN_COMPONENT_NORMALIZATION_MODEL)
            # 3) Hard default (openai:gpt-4.1)
            normalization_model = None
            if hasattr(deps, "get_component_normalization_model"):
                try:
                    normalization_model = deps.get_component_normalization_model()
                except Exception:
                    normalization_model = None

            if not normalization_model or not str(normalization_model).strip():
                normalization_model = (
                    os.environ.get("STDN_COMPONENT_NORMALIZATION_MODEL", "openai:gpt-4.1").strip()
                    or "openai:gpt-4.1"
                )

            # pydantic_ai defaults retries=1; raise this to reduce premature failures.
            retries_env = os.environ.get("STDN_AGENT_RETRIES")
            retries = 5
            if retries_env is not None:
                try:
                    retries = int(retries_env)
                except ValueError:
                    retries = 5

            agent = Agent(
                model=normalization_model,
                output_type=ComponentMapping,
                deps_type=type(deps),
                system_prompt="You are a component naming expert. Normalize component names to canonical English forms. Always respond in English only.",
                retries=retries,
                output_retries=retries,
            )

            result = await agent.run(prompt, deps=deps)
            llm_mapping = dict(result.output.mappings)

            # Merge LLM results with vocab-based mappings
            for name in names_needing_llm:
                if name in llm_mapping:
                    mapping[name] = llm_mapping[name]
                else:
                    mapping[name] = self.normalize_component_name(name)

            # Ensure complete coverage for all original names
            for name in unique_names:
                mapping.setdefault(name, self.normalize_component_name(name))

            # Log normalization results
            logger.debug(
                "LLM Normalization: %d inputs -> %d canonical names",
                len(names_needing_llm),
                len(set(mapping.values())),
            )

            # Group by normalized name to show what got merged
            normalized_groups: Dict[str, List[str]] = {}
            for original, normalized in mapping.items():
                if normalized not in normalized_groups:
                    normalized_groups[normalized] = []
                normalized_groups[normalized].append(original)

            for normalized, originals in sorted(normalized_groups.items()):
                if len(originals) > 1:
                    logger.debug(
                        "  '%s' <- merged from %d variants: %s",
                        normalized,
                        len(originals),
                        originals,
                    )

            logger.info("✓ LLM normalization produced %d unique names", len(set(mapping.values())))
            return mapping

        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM normalization failed, using rule-based fallback: %s", exc)
            # Still return any vocab-based mappings we found
            for name in names_needing_llm:
                mapping.setdefault(name, self.normalize_component_name(name))
            return mapping

    # ------------------------------------------------------------------#
    # Internal helpers for proposals
    # ------------------------------------------------------------------#

    @staticmethod
    def _get_prop_value(prop: Any, key: str, default: Any = None) -> Any:
        """Safely extract a field from either dict-like or AgentProposal."""
        if isinstance(prop, AgentProposal):
            return getattr(prop, key, default)
        if isinstance(prop, dict):
            value = prop.get(key, default)
            # Special handling: if looking for "component", also check "name"
            if value is None and key == "component":
                value = prop.get("name", default)
            return value
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
                logger.debug(
                    "Excluded '%s': confidence %.2f below %.2f",
                    norm_name,
                    avg_conf,
                    MIN_CONFIDENCE,
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
        logger.debug("Consensus Scoring:")
        logger.debug("  Convergence: %.2f", convergence_score)
        logger.debug("  Min support required: %d/%d agents", min_support, num_agents)
        logger.debug("  Peer support boost: %.2f", self.peer_support_boost)

        all_norms = sorted(norm_to_confidences.keys())
        for norm_name in all_norms:
            support = len(norm_to_agents[norm_name])
            confs = norm_to_confidences[norm_name]
            avg_conf = sum(confs) / len(confs)

            if norm_name in scores:
                score = scores[norm_name]
                logger.debug(
                    "  [INCLUDED] '%s': %d/%d agents, avg_conf=%.2f, score=%.3f",
                    norm_name,
                    support,
                    num_agents,
                    avg_conf,
                    score,
                )
            else:
                logger.debug(
                    "  [EXCLUDED] '%s': %d/%d agents, avg_conf=%.2f",
                    norm_name,
                    support,
                    num_agents,
                    avg_conf,
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

        IMPORTANT: This method constrains agents to SELECT from existing proposed
        components rather than inventing new ones. The debate is about reaching
        consensus on WHICH components to include and with what confidence.

        Returns:
            Dict mapping agent_id -> list of proposal dicts with confidence scores.
        """
        from dataclasses import replace

        # Collect all unique component names from previous proposals
        unique_components: Dict[str, Dict[str, Any]] = {}
        for p in previous_proposals:
            comp_name = self._get_prop_value(p, "component") or self._get_prop_value(
                p, "component_name", ""
            )
            if comp_name and comp_name not in unique_components:
                unique_components[comp_name] = {
                    "name": comp_name,
                    "reasoning": self._get_prop_value(p, "reasoning", ""),
                    "confidence": self._get_prop_value(p, "confidence", 0.8),
                }

        # Build a numbered list of candidate components
        component_list = "\n".join(
            f"  {i + 1}. {comp['name']} (initial confidence: {comp['confidence']:.2f})"
            for i, comp in enumerate(unique_components.values())
        )

        # Build context from previous proposals grouped by agent
        agent_proposals: Dict[str, List[str]] = {}
        for p in previous_proposals:
            agent_id = self._get_prop_value(p, "agent_id", "unknown")
            comp_name = self._get_prop_value(p, "component") or self._get_prop_value(
                p, "component_name", ""
            )
            conf = self._get_prop_value(p, "confidence", 0.8)
            if agent_id not in agent_proposals:
                agent_proposals[agent_id] = []
            agent_proposals[agent_id].append(f"{comp_name} ({conf:.2f})")

        prev_context = "\n".join(
            f"  {agent_id}: {', '.join(comps)}"
            for agent_id, comps in sorted(agent_proposals.items())
        )

        critique_text = "\n".join(f"  - {c}" for c in critiques)

        # Validate that we have content to send to LLM
        if not component_list or not component_list.strip():
            logger.warning(f"Round {roundnum}: No components available for debate")
            return {}

        if not critique_text or not critique_text.strip():
            critique_text = "  - Focus on reaching consensus on essential components."

        # System prompt that emphasizes SELECTION not invention
        system_prompt = """You are an expert participating in a multi-agent debate to reach consensus on technology components.

CRITICAL RULES:
1. You MUST ONLY select from the CANDIDATE COMPONENTS list provided
2. Do NOT invent new component names - use the EXACT names from the list
3. Your job is to decide which components to INCLUDE and with what CONFIDENCE
4. Adjust confidence based on peer support and critique feedback

For each component you include, provide:
- The EXACT component name from the candidate list
- Your confidence (0.0-1.0) that it should be included
- Brief reasoning for your confidence level
"""

        new_proposals: Dict[str, List[Dict[str, Any]]] = {}

        # Create a specialized agent for structured debate responses
        debate_agent = Agent(
            model=deps.get_component_model(),
            output_type=DebateResponse,
            deps_type=type(deps),
            system_prompt=system_prompt,
        )

        # Get the original agent IDs from the proposals to maintain consistency
        original_agent_ids = sorted(
            set(self._get_prop_value(p, "agent_id", "unknown") for p in previous_proposals)
        )

        # Use the same number of agents as in initial proposals
        num_agents = max(len(original_agent_ids), 3)

        for agent_num in range(1, num_agents + 1):
            # Use consistent agent ID format (with underscore to match initial proposals)
            agent_id = f"Agent_{agent_num}"

            # Build the debate prompt
            prompt = f"""DEBATE ROUND {roundnum} - COMPONENT SELECTION

Technology: {technology}

CANDIDATE COMPONENTS (you MUST select from this list):
{component_list}

PREVIOUS ROUND - AGENT SELECTIONS:
{prev_context}

PEER CRITIQUES AND GUIDANCE:
{critique_text}

YOUR TASK:
1. Review the candidate components and peer feedback
2. SELECT which components from the list above should be included
3. For each selected component:
   - Use the EXACT name from the candidate list
   - Assign confidence (0.0-1.0) based on:
     * Peer support (higher if multiple agents selected it)
     * Critique feedback (adjust based on critiques)
     * Your assessment of its importance as a primary component
   - Provide brief reasoning

IMPORTANT: Only include components you believe should be in the final consensus.
Components with low peer support should have lower confidence unless critically justified.
"""

            try:
                # Use very low Top-P for deterministic, focused refinements
                debate_deps = replace(deps, top_p=self.debate_top_p)

                logger.debug(
                    "%s calling LLM: prompt=%d chars, candidates=%d, critiques=%d",
                    agent_id,
                    len(prompt),
                    len(unique_components),
                    len(critiques),
                )

                result = await debate_agent.run(
                    prompt, deps=debate_deps, model=deps.get_component_model()
                )

                if result and result.output and result.output.components:
                    proposals_list = []
                    for comp in result.output.components:
                        # Try to match to an existing component name
                        matched_name = self._match_to_existing_component(
                            comp.name, unique_components
                        )
                        proposals_list.append(
                            {
                                "agent_id": agent_id,
                                "component": matched_name,
                                "confidence": comp.confidence,
                                "reasoning": comp.reasoning,
                                "round": roundnum,
                            }
                        )
                    new_proposals[agent_id] = proposals_list

                    avg_conf = sum(p["confidence"] for p in proposals_list) / len(proposals_list)
                    logger.info(
                        "Round %d - %s: %d components selected, avg confidence=%.2f",
                        roundnum,
                        agent_id,
                        len(proposals_list),
                        avg_conf,
                    )
                else:
                    logger.warning("No components returned from %s in round %d", agent_id, roundnum)
                    new_proposals[agent_id] = []

            except Exception as exc:  # noqa: BLE001
                logger.error("Error in debate round %d for %s: %s", roundnum, agent_id, exc)
                # Fall back to previous proposals for this agent, if any
                prev_for_agent = [
                    p for p in previous_proposals if self._get_prop_value(p, "agent_id") == agent_id
                ]
                new_proposals[agent_id] = prev_for_agent

        return new_proposals

    def _match_to_existing_component(
        self,
        proposed_name: str,
        existing_components: Dict[str, Dict[str, Any]],
    ) -> str:
        """
        Match a proposed component name to an existing one.

        Uses exact match first, then normalized match, then fuzzy match.
        Returns the best matching existing name, or the proposed name if no match.
        """
        # Exact match
        if proposed_name in existing_components:
            return proposed_name

        # Normalized match
        proposed_norm = self.normalize_component_name(proposed_name)
        for existing_name in existing_components:
            if self.normalize_component_name(existing_name) == proposed_norm:
                return existing_name

        # Fuzzy match - check if proposed name is contained in or contains existing
        proposed_lower = proposed_name.lower()
        for existing_name in existing_components:
            existing_lower = existing_name.lower()
            if proposed_lower in existing_lower or existing_lower in proposed_lower:
                return existing_name

        # No match found - return proposed name but log warning
        logger.warning(
            "LLM proposed '%s' which doesn't match any existing component",
            proposed_name,
        )
        return proposed_name

    async def run_debate(
        self,
        technology: str,
        initial_proposals: Dict[str, List[Dict[str, Any]]],
        component_agent: Any,
        deps: Any,
        canonical_vocab: Any = None,
    ) -> Dict[str, Any]:
        """
        Run multi-round debate with LLM-based semantic normalization and dynamic confidence.

        Args:
            technology: Technology being analyzed
            initial_proposals: Initial proposals from agents
            component_agent: Agent for component extraction
            deps: Dependencies
            canonical_vocab: Optional CanonicalVocab for consistent naming
        """
        self.canonical_vocab = canonical_vocab
        convergence = 0.0
        rounds_completed = 0
        debate_rounds: List[Dict[str, Any]] = []

        logger.info("=" * 60)
        logger.info("COMPONENT DEBATE: %s", technology)
        logger.info("=" * 60)

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
        logger.info("Extracted %d components with dynamic confidence weighting", len(consensus))

        # Filter using the effective per-component confidence from component_details
        filtered_component_details: Dict[str, Dict[str, Any]] = {
            name: details
            for name, details in component_details.items()
            if details.get("confidence", 0.0) > 0.0
        }

        # Consensus is just the keys that survived
        filtered_consensus = list(filtered_component_details.keys())

        logger.info(
            "Kept %d components after filtering low-confidence entries",
            len(filtered_consensus),
        )

        return {
            "technology": technology,
            "components": filtered_consensus,
            "component_details": filtered_component_details,
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
        previous_proposals: List[Dict[str, Any]] = []

        for roundnum in range(self.max_rounds):
            logger.info("Round %d/%d:", roundnum + 1, self.max_rounds)

            all_proposals = self._flatten_proposals_for_round(
                current_proposals,
                roundnum,
            )

            if not all_proposals:
                logger.warning("No proposals available for round %d", roundnum + 1)
                break

            self._log_round_confidence_stats(all_proposals)

            convergence = self.calculate_convergence_semantic(all_proposals)
            threshold_reached = convergence >= self.convergence_threshold
            logger.info("  Convergence: %.1f%%", convergence * 100)
            rounds_completed = roundnum + 1

            # Compute support analysis for this round
            support_analysis = self.compute_support_analysis(all_proposals)

            # Compute changes from previous round
            round_changes = None
            if previous_proposals:
                round_changes = self.compute_round_changes(all_proposals, previous_proposals)

            # Generate structured critiques
            structured_critiques = self.generate_structured_critiques(all_proposals, roundnum + 1)

            # Build enhanced round data
            round_data = {
                "round_num": roundnum + 1,
                "convergence": convergence,
                "threshold": self.convergence_threshold,
                "threshold_reached": threshold_reached,
                "proposals": current_proposals.copy(),
                "rounds_completed": rounds_completed,
                # New enhanced data
                "support_analysis": {
                    "consensus": support_analysis["consensus"],
                    "majority": support_analysis["majority"],
                    "isolated": support_analysis["isolated"],
                },
                "critiques": structured_critiques,
                "changes_from_previous": round_changes,
            }
            debate_rounds.append(round_data)

            if threshold_reached:
                logger.info("  Convergence threshold reached!")
                break

            if roundnum < self.max_rounds - 1:
                logger.debug("  Generating critiques...")
                critiques = self.generate_critiques_with_influence(
                    all_proposals,
                    roundnum + 1,
                )
                logger.debug("  Refining proposals based on peer feedback...")

                # Store current proposals for next round comparison
                previous_proposals = all_proposals.copy()

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
        logger.debug("  Confidence: avg=%.2f, min=%.2f, max=%.2f", avg_conf, min_conf, max_conf)

    def compute_support_analysis(
        self,
        proposals: List[Dict[str, Any]],
        num_agents: int = 3,
    ) -> Dict[str, Any]:
        """
        Compute support level analysis for proposals.

        Categorizes each component by support level:
        - CONSENSUS: All agents agree (3/3)
        - MAJORITY: Majority agrees (2/3)
        - ISOLATED: Single agent only (1/3)

        Returns:
            Dict with 'consensus', 'majority', 'isolated' lists and 'details' dict
        """
        # Group components by normalized name
        comp_support: Dict[str, Dict[str, Any]] = {}

        for prop in proposals:
            agent_id = self._get_prop_value(prop, "agent_id", "unknown")
            name = (
                self._get_prop_value(prop, "normalized_component")
                or self._get_prop_value(prop, "component")
                or self._get_prop_value(prop, "component_name")
                or ""
            )
            confidence = float(self._get_prop_value(prop, "confidence", 0.8))
            reasoning = self._get_prop_value(prop, "reasoning", "")

            if not name:
                continue

            norm = self.normalize_component_name(name)
            if norm not in comp_support:
                comp_support[norm] = {
                    "display_name": name,
                    "agents": set(),
                    "confidences": [],
                    "reasonings": [],
                }
            comp_support[norm]["agents"].add(agent_id)
            comp_support[norm]["confidences"].append(confidence)
            comp_support[norm]["reasonings"].append(reasoning)

        # Categorize by support level
        consensus_items = []
        majority_items = []
        isolated_items = []
        details = {}

        for norm_name, data in comp_support.items():
            support_count = len(data["agents"])
            avg_conf = sum(data["confidences"]) / len(data["confidences"])

            item_detail = {
                "name": data["display_name"],
                "normalized_name": norm_name,
                "support_count": support_count,
                "total_agents": num_agents,
                "supporting_agents": list(data["agents"]),
                "avg_confidence": avg_conf,
                "reasoning": data["reasonings"][0] if data["reasonings"] else "",
            }

            if support_count == num_agents:
                item_detail["support_level"] = "consensus"
                consensus_items.append(norm_name)
            elif support_count > num_agents / 2:
                item_detail["support_level"] = "majority"
                majority_items.append(norm_name)
            else:
                item_detail["support_level"] = "isolated"
                isolated_items.append(norm_name)

            details[norm_name] = item_detail

        return {
            "consensus": consensus_items,
            "majority": majority_items,
            "isolated": isolated_items,
            "details": details,
        }

    def compute_round_changes(
        self,
        current_proposals: List[Dict[str, Any]],
        previous_proposals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compute what changed between two rounds.

        Returns:
            Dict with 'items_added', 'items_removed', and 'confidence_changes'
        """

        def get_components(proposals: List[Dict[str, Any]]) -> Dict[str, float]:
            """Extract normalized components and their avg confidence."""
            comp_conf: Dict[str, List[float]] = {}
            for prop in proposals:
                name = (
                    self._get_prop_value(prop, "normalized_component")
                    or self._get_prop_value(prop, "component")
                    or ""
                )
                if not name:
                    continue
                norm = self.normalize_component_name(name)
                confidence = float(self._get_prop_value(prop, "confidence", 0.8))
                if norm not in comp_conf:
                    comp_conf[norm] = []
                comp_conf[norm].append(confidence)

            return {k: sum(v) / len(v) for k, v in comp_conf.items()}

        current_comps = get_components(current_proposals)
        previous_comps = get_components(previous_proposals) if previous_proposals else {}

        current_set = set(current_comps.keys())
        previous_set = set(previous_comps.keys())

        items_added = list(current_set - previous_set)
        items_removed = list(previous_set - current_set)

        # Track confidence changes for items in both rounds
        confidence_changes = {}
        for comp in current_set & previous_set:
            old_conf = previous_comps[comp]
            new_conf = current_comps[comp]
            if abs(new_conf - old_conf) > 0.05:  # Only track significant changes
                confidence_changes[comp] = {"from": old_conf, "to": new_conf}

        return {
            "items_added": items_added,
            "items_removed": items_removed,
            "confidence_changes": confidence_changes,
        }

    def generate_structured_critiques(
        self,
        proposals: List[Dict[str, Any]],
        round_num: int,
        num_agents: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Generate structured critique objects for transcript recording.

        Returns a list of critique dicts with:
        - item_name: Component being critiqued
        - support_level: 'consensus', 'majority', or 'isolated'
        - supporting_agents: List of agent IDs that support
        - opposing_agents: List of agent IDs that don't support
        - avg_confidence: Average confidence across supporters
        - critique_text: Human-readable critique
        """
        support_analysis = self.compute_support_analysis(proposals, num_agents)
        critiques = []

        all_agents = set()
        for prop in proposals:
            all_agents.add(self._get_prop_value(prop, "agent_id", "unknown"))

        for norm_name, detail in support_analysis["details"].items():
            supporting = set(detail["supporting_agents"])
            opposing = list(all_agents - supporting)

            support_level = detail["support_level"]
            avg_conf = detail["avg_confidence"]

            # Generate critique text based on support level
            if support_level == "consensus":
                critique_text = (
                    f"Strong consensus on '{detail['name']}': all {num_agents} agents "
                    f"support with avg confidence {avg_conf:.2f}. Preserve this component."
                )
            elif support_level == "majority":
                critique_text = (
                    f"Majority support for '{detail['name']}': {detail['support_count']}/{num_agents} "
                    f"agents agree (conf: {avg_conf:.2f}). Consider strengthening consensus."
                )
            else:
                critique_text = (
                    f"Isolated proposal '{detail['name']}' from {detail['support_count']} agent(s) "
                    f"(conf: {avg_conf:.2f}). Requires justification or peer validation."
                )

            critiques.append(
                {
                    "item_name": detail["name"],
                    "normalized_name": norm_name,
                    "support_level": support_level,
                    "supporting_agents": detail["supporting_agents"],
                    "opposing_agents": opposing,
                    "avg_confidence": avg_conf,
                    "critique_text": critique_text,
                }
            )

        return critiques

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
            logger.debug("Building final consensus with semantic normalization...")
            final_norm_map = await self.normalize_components_with_llm(
                final_component_names,
                component_agent,
                deps,
            )
            for prop in all_final_proposals:
                original = prop.get("component") or prop.get("component_name", "")
                norm = final_norm_map.get(original, original)
                prop["normalized_component"] = norm

        logger.debug("Final Proposals Summary (After Round %d):", rounds_completed)

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

        for name in sorted(component_counts.keys()):
            agent_count = len(component_agents[name])
            total_count = component_counts[name]
            agents = ", ".join(sorted(component_agents[name]))
            logger.debug(
                "  '%s': %d/3 agents (%d proposals) [%s]",
                name,
                agent_count,
                total_count,
                agents,
            )


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
