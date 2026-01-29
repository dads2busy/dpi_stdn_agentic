"""
Component Extractor Module

This module handles component extraction from technology descriptions using
multi-agent debate with critique-driven convergence.

Features:
- Multi-agent debate system for component consensus
- Dynamic confidence scoring
- Debate transcript generation
- Technology specification refinement
"""

from datetime import datetime
from pathlib import Path

# Import CanonicalVocab with TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic_ai import RunUsage

from ..agents import ComponentList, ComponentWithConfidence, get_component_agent
from ..debate import MultiAgentDebater
from ..dependencies import STDNDependencies
from ..logging_config import get_logger
from ..reporting import DebateReporter

if TYPE_CHECKING:
    from ..normalization import CanonicalVocab

logger = get_logger(__name__)


# ============================================================================
# Component Extractor
# ============================================================================


class ComponentExtractor:
    """Handles component extraction with multi-agent debate"""

    def __init__(
        self,
        deps: STDNDependencies,
        model_name: str,
        debater: Optional[MultiAgentDebater] = None,
        reporter: Optional[DebateReporter] = None,
        timestamp: Optional[str] = None,
        debate_top_p: float = 0.0001,
        canonical_vocab: Optional["CanonicalVocab"] = None,
    ):
        """
        Initialize component extractor.

        Args:
            deps: STDN dependencies
            model_name: Model name for agent
            debater: Optional MultiAgentDebater instance
            reporter: Optional DebateReporter instance
            timestamp: Optional timestamp for transcript filenames
            debate_top_p: Top-p sampling for debate
            canonical_vocab: Optional canonical vocabulary for component normalization
        """
        self.deps = deps
        self.component_agent = get_component_agent(model_name=model_name)
        self.debater = debater
        self.reporter = reporter
        self.timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debate_top_p = debate_top_p
        self.canonical_vocab = canonical_vocab

    async def extract_components_simple(
        self, technology: str, usage: RunUsage
    ) -> Optional[ComponentList]:
        """
        Simple single-agent component extraction without debate.

        Args:
            technology: Technology name
            usage: RunUsage tracker

        Returns:
            ComponentList with components, or None if extraction fails
        """
        try:
            result = await self.component_agent.run(
                f"Extract the primary components of a {technology}",
                deps=self.deps,
            )

            if result and result.usage():
                usage.incr(result.usage())

            return result.output if result else None

        except Exception as e:
            logger.error(
                "Error in simple component extraction for %s: %s", technology, e, exc_info=True
            )
            return None

    async def extract_components_with_debate(
        self, technology: str, role: str, usage: RunUsage, num_agents: int = 3
    ) -> Optional[ComponentList]:
        """Extract components using enhanced multi-agent debate."""
        self._log_debate_header(technology)

        # Collect proposals
        (
            agent_proposals,
            agent_responses,
            tech_spec,
            tech_reasoning,
        ) = await self._collect_agent_proposals(technology, role, usage, num_agents)

        if not agent_proposals:
            logger.error("No proposals collected from any agent")
            return None

        # Run debate
        debate_result = await self._run_debate(technology, agent_proposals)
        if not debate_result:
            return None

        # Process results
        return self._create_final_component_list(
            technology, debate_result, agent_responses, tech_spec, tech_reasoning
        )

    async def _collect_agent_proposals(
        self, technology: str, role: str, usage: RunUsage, num_agents: int
    ) -> tuple[dict, list, str, str]:
        """Collect initial proposals from multiple agents."""
        logger.info("Collecting proposals from %d agents...", num_agents)
        logger.debug("Role: %s", role)

        agent_proposals = {}
        agent_responses = []
        technology_specification = technology
        technology_reasoning = ""

        for agent_num in range(1, num_agents + 1):
            result = await self._run_single_agent(agent_num, technology, role, num_agents, usage)

            if result:
                agent_id = f"Agent_{agent_num}"
                components_data, tech_spec, tech_reason = result
                agent_proposals[agent_id] = components_data
                agent_responses.append(
                    {
                        "agent_id": agent_id,
                        "components": components_data,
                        "technology_specification": tech_spec,
                        "technology_reasoning": tech_reason,
                    }
                )

                if agent_num == 1:
                    technology_specification = tech_spec
                    technology_reasoning = tech_reason

                logger.info("%s: %d components proposed", agent_id, len(components_data))

        return agent_proposals, agent_responses, technology_specification, technology_reasoning

    async def _run_single_agent(
        self, agent_num: int, technology: str, role: str, num_agents: int, usage: RunUsage
    ) -> Optional[tuple[list, str, str]]:
        """Run a single agent to collect component proposals."""
        try:
            perspective = self._get_agent_perspective(agent_num)
            prompt = self._create_agent_prompt(technology, role, perspective)

            from dataclasses import replace

            agent_deps = replace(self.deps, top_p=self.debate_top_p)
            result = await self.component_agent.run(prompt, deps=agent_deps)

            if not result or not result.output:
                logger.warning("No response from Agent_%d", agent_num)
                return None

            component_list = result.output
            if not component_list or not component_list.component_list:
                logger.warning("Empty component list from Agent_%d", agent_num)
                return None

            # Extract data
            tech_spec = getattr(component_list, "technology_specification", technology)
            tech_reason = getattr(component_list, "technology_reasoning", "")

            components_data = [
                {
                    "name": comp.name,
                    "confidence": comp.confidence,
                    "reasoning": comp.reasoning,
                }
                for comp in component_list.component_list
            ]

            if hasattr(result, "usage") and result.usage():
                usage.incr(result.usage())

            return components_data, tech_spec, tech_reason

        except Exception as e:
            logger.error("Error in Agent_%d: %s", agent_num, e, exc_info=True)
            return None

    def _get_agent_perspective(self, agent_num: int) -> str:
        """Get analytical perspective for agent."""
        perspectives = [
            "Focus on identifying major procurable subassemblies and modules with distinct supply chains",
            "Focus on structural components and physical assemblies required for construction",
            "Focus on distinguishing true manufactured components from raw materials and consumables",
        ]
        return (
            perspectives[agent_num - 1]
            if agent_num <= len(perspectives)
            else "Focus on identifying essential subsystems and modules"
        )

    def _create_agent_prompt(self, technology: str, role: str, perspective: str) -> str:
        """Create structured prompt for agent."""
        return f"""You are a {role} expert analyzing the '{technology}' technology.
    {perspective}

    **CRITICAL: You MUST respond ONLY in English. All component names, reasoning,
    and descriptions must be in English. Do not use any other languages.**

    IMPORTANT INSTRUCTIONS:
    1. FIRST, before listing components:
       - Provide a clear, specific technology specification (1-2 sentences)
       - Explain your reasoning for this specification

    2. THEN list 5-12 major COMPONENTS or SUBASSEMBLIES that are:
       - Manufactured items procured from suppliers (not raw materials)
       - Distinct parts with separate supply chains
       - Physical objects that can be purchased or manufactured

    3. For EACH component provide:
       - Component name
       - Confidence score (0.0-1.0) based on:
         * Clarity of the component's role
         * Distinctness from other components
         * Whether it's truly a procurable manufactured item
       - Brief reasoning (1-2 sentences) explaining why this is a distinct component

    DO NOT include:
    - Raw materials (copper, aluminum, silicon wafers, etc.)
    - Generic consumables (solder, adhesives, screws, etc.)
    - Overly generic categories ("electronic components", "mechanical parts")
    - Sub-parts that are always integrated into larger assemblies

    EXAMPLES:
    ✓ Battery pack - distinct procurable assembly
    ✓ Inverter module - manufactured subassembly with separate supply chain
    ✓ Mounting structure - structural component typically procured separately
    ✗ Copper wire - raw material, not a component
    ✗ Semiconductors - too generic, specify actual component using them
    ✗ Fasteners - consumable, not a major component

    Format your response exactly as:
    Technology Specification: [Your 1-2 sentence specification]
    Technology Reasoning: [Your explanation for this specification]

    Components:
    1. [Component Name]
       Confidence: [0.0-1.0]
       Reasoning: [Brief explanation]

    2. [Next Component Name]
       Confidence: [0.0-1.0]
       Reasoning: [Brief explanation]

    (continue for all components)
    """

    async def _run_debate(self, technology: str, agent_proposals: dict) -> Optional[dict]:
        """Run debate to reach consensus."""
        if not self.debater:
            logger.error("Debater not initialized")
            return None

        logger.info("=" * 60)
        logger.info("RUNNING MULTI-AGENT DEBATE")
        logger.info("=" * 60)

        debate_result = await self.debater.run_debate(
            technology=technology,
            initial_proposals=agent_proposals,
            component_agent=self.component_agent,
            deps=self.deps,
            canonical_vocab=self.canonical_vocab,
        )

        if not debate_result:
            logger.error("Debate failed to produce result")
            return None

        return debate_result

    def _create_final_component_list(
        self,
        technology: str,
        debate_result: dict,
        agent_responses: list,
        tech_spec: str,
        tech_reasoning: str,
    ) -> ComponentList:
        """Create final ComponentList from debate results."""
        final_component_names = debate_result.get("components", [])
        component_details = debate_result.get("component_details", {})

        # Update specs from debate if available
        tech_spec = debate_result.get("technology_specification", tech_spec)
        tech_reasoning = debate_result.get("technology_reasoning", tech_reasoning)

        self._log_consensus(tech_spec, final_component_names, component_details)

        # Save transcript
        if self.reporter:
            transcript_path = self._save_debate_transcript(
                technology, agent_responses, debate_result
            )
            if transcript_path:
                logger.info("Debate transcript saved to: %s", transcript_path)

        # Create components
        final_components = self._build_components(final_component_names, component_details)

        logger.info("Created %d ComponentWithConfidence objects", len(final_components))
        for comp in final_components:
            logger.debug("  %s (confidence: %.2f)", comp.name, comp.confidence)

        return ComponentList(
            componentlist=final_components,
            technology_specification=tech_spec,
            technology_reasoning=tech_reasoning,
        )

    def _build_components(self, names: list, details: dict) -> list:
        """Build ComponentWithConfidence objects."""
        components = []
        for norm_name in names:
            if norm_name in details:
                detail = details[norm_name]
                components.append(
                    ComponentWithConfidence(
                        name=norm_name,
                        confidence=detail["confidence"],
                        reasoning=detail["reasoning"],
                    )
                )
            else:
                logger.warning("No details found for '%s', using fallback", norm_name)
                components.append(
                    ComponentWithConfidence(
                        name=norm_name.title(),
                        confidence=0.75,
                        reasoning="Consensus component from multi-agent debate",
                    )
                )
        return components

    def _log_debate_header(self, technology: str) -> None:
        """Log debate header."""
        logger.info("=" * 60)
        logger.info("DEBATE-BASED COMPONENT EXTRACTION: %s", technology)
        logger.info("=" * 60)

    def _log_consensus(self, tech_spec: str, names: list, details: dict) -> None:
        """Log consensus results."""
        logger.info("=" * 60)
        logger.info("CONSENSUS REACHED")
        logger.info("=" * 60)
        logger.info("Technology Specification: %s", tech_spec)
        logger.info("Final Components (%d):", len(names))
        for i, comp_name in enumerate(names, 1):
            detail = details.get(comp_name, {})
            conf = detail.get("confidence", 0.0)
            logger.info("  %d. %s (confidence: %.2f)", i, comp_name, conf)

    def _save_debate_transcript(
        self, technology: str, agent_responses: List[Dict], debate_result: Dict
    ) -> Optional[Path]:
        """
        Save comprehensive debate transcript including materials assignment.

        Args:
            technology: Technology name
            agent_responses: Agent proposals and reasoning
            debate_result: Final debate consensus with rounds metadata

        Returns:
            Path to saved transcript (text version)
        """
        try:
            if not self.reporter:
                return None

            # Extract metadata from debate_result
            num_rounds = debate_result.get("rounds", 0)
            confidence = debate_result.get("confidence", 0.0)
            debate_history = debate_result.get("debate_history", [])

            # Extract tech spec from debate_result
            technology_specification = debate_result.get("technology_specification", technology)
            technology_reasoning = debate_result.get("technology_reasoning", "")

            logger.debug("Passing to reporter - Tech spec: %s", technology_specification)
            logger.debug(
                "Passing to reporter - Tech reasoning: %s...",
                technology_reasoning[:100] if technology_reasoning else "None",
            )

            # Build final consensus dict with proper metadata
            final_consensus = {
                "technology": technology,
                "technology_specification": technology_specification,
                "technology_reasoning": technology_reasoning,
                "components": debate_result.get("components", []),
                "confidence": confidence,
                "rounds": num_rounds,
                "convergence_score": confidence,
            }

            # Save text version
            filepath = self.reporter.save_debate_transcript(
                technology=technology,
                agent_responses=agent_responses,
                debate_history=debate_history,
                final_consensus=final_consensus,
                file_format="txt",
                timestamp=self.timestamp,
            )

            # Also save JSON version for programmatic access
            self.reporter.save_debate_transcript(
                technology=technology,
                agent_responses=agent_responses,
                debate_history=debate_history,
                final_consensus=final_consensus,
                file_format="json",
                timestamp=self.timestamp,
            )

            return filepath

        except Exception as e:
            logger.error("Error saving debate transcript: %s", e, exc_info=True)
            return None
