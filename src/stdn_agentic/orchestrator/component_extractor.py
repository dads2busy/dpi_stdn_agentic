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

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic_ai import RunUsage

from ..agents import ComponentList, ComponentWithConfidence, get_component_agent
from ..debate import MultiAgentDebater
from ..dependencies import STDNDependencies
from ..reporting import DebateReporter

# Initialize logger
logger = logging.getLogger(__name__)


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
    ):
        """
        Initialize component extractor.

        Args:
            deps: STDN dependencies
            model_name: Model name for agent
            debater: Optional MultiAgentDebater instance
            reporter: Optional DebateReporter instance
            timestamp: Optional timestamp for transcript filenames
        """
        self.deps = deps
        self.component_agent = get_component_agent(model_name=model_name)
        self.debater = debater
        self.reporter = reporter
        self.timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.debate_top_p = debate_top_p

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
                f"Error in simple component extraction for {technology}: {e}", exc_info=True
            )
            print(f"✗ Error extracting components: {e}")
            return None

    async def extract_components_with_debate(
        self, technology: str, role: str, usage: RunUsage, num_agents: int = 3
    ) -> Optional[ComponentList]:
        """
        Extract components using enhanced multi-agent debate with critique-driven convergence.

        Args:
            technology: Technology name
            role: Expert role context (from CSV)
            usage: RunUsage tracker
            num_agents: Number of agents to use in debate (default: 3)

        Returns:
            ComponentList with consensus components, or None if extraction fails
        """
        print(f"\n{'=' * 80}")
        print(f"DEBATE-BASED COMPONENT EXTRACTION: {technology}")
        print(f"{'=' * 80}\n")

        # Define different analytical perspectives for agents with the same role
        PERSPECTIVE_FOCUS = [
            "Focus on identifying major procurable subassemblies and modules with distinct supply chains",
            "Focus on structural components and physical assemblies required for construction",
            "Focus on distinguishing true manufactured components from raw materials and consumables",
        ]

        # Collect initial proposals from multiple agents
        print(f"📋 Collecting proposals from {num_agents} agents...\n")
        print(f"🎭 Role: {role}\n")

        agent_proposals = {}
        agent_responses_for_transcript = []
        technology_specification = technology  # Default to input
        technology_reasoning = ""

        for agent_num in range(1, num_agents + 1):
            agent_id = f"Agent_{agent_num}"

            # Get analytical perspective for this agent
            perspective = (
                PERSPECTIVE_FOCUS[agent_num - 1]
                if agent_num <= len(PERSPECTIVE_FOCUS)
                else "Focus on identifying essential subsystems and modules"
            )

            # Create structured prompt with role and perspective
            prompt = f"""You are a {role} expert analyzing the '{technology}' technology.
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

            try:
                # Create deps with very low Top-P for focused outputs
                from dataclasses import replace

                agent_deps = replace(self.deps, top_p=self.debate_top_p)

                # Run agent with explicit prompt
                result = await self.component_agent.run(prompt, deps=agent_deps)

                if not result or not result.output:
                    logger.warning(f"No response from {agent_id}")
                    continue

                # Extract the ComponentList
                component_list = result.output
                if not component_list or not component_list.component_list:
                    logger.warning(f"Empty component list from {agent_id}")
                    continue

                # Store technology specification and reasoning from first agent
                if agent_num == 1 and hasattr(component_list, "technology_specification"):
                    technology_specification = component_list.technology_specification
                    technology_reasoning = getattr(component_list, "technology_reasoning", "")

                # Convert ComponentWithConfidence objects to dict for storage
                components_data = []
                for comp in component_list.component_list:
                    components_data.append(
                        {
                            "name": comp.name,
                            "confidence": comp.confidence,
                            "reasoning": comp.reasoning,
                        }
                    )

                agent_proposals[agent_id] = components_data

                # Store for transcript
                agent_responses_for_transcript.append(
                    {
                        "agent_id": agent_id,
                        "components": components_data,
                        "technology_specification": technology_specification,
                        "technology_reasoning": technology_reasoning,
                    }
                )

                print(f"✓ {agent_id}: {len(components_data)} components proposed")

                # Accumulate usage
                if hasattr(result, "usage") and result.usage():
                    usage.incr(result.usage())

            except Exception as e:
                logger.error(f"Error in {agent_id}: {e}", exc_info=True)
                print(f"✗ {agent_id}: Error - {e}")
                continue

        if not agent_proposals:
            logger.error("No proposals collected from any agent")
            print("❌ No valid proposals from agents")
            return None

        if not self.debater:
            logger.error("Debater not initialized")
            print("❌ Debater not initialized")
            return None

        print(f"\n{'=' * 80}")
        print("RUNNING MULTI-AGENT DEBATE")
        print(f"{'=' * 80}\n")

        # Run debate to reach consensus
        debate_result = await self.debater.run_debate(
            technology=technology,
            initial_proposals=agent_proposals,
            component_agent=self.component_agent,
            deps=self.deps,
        )

        if not debate_result:
            logger.error("Debate failed to produce result")
            print("❌ Debate failed")
            return None

        # Extract consensus components
        final_component_names = debate_result.get("components", [])
        component_details = debate_result.get("component_details", {})

        # Store technology specification from debate result
        if "technology_specification" in debate_result:
            technology_specification = debate_result["technology_specification"]
        if "technology_reasoning" in debate_result:
            technology_reasoning = debate_result["technology_reasoning"]

        print(f"\n{'=' * 80}")
        print("CONSENSUS REACHED")
        print(f"{'=' * 80}\n")
        print(f"Technology Specification: {technology_specification}\n")
        print(f"Final Components ({len(final_component_names)}):")
        for i, comp_name in enumerate(final_component_names, 1):
            details = component_details.get(comp_name, {})
            conf = details.get("confidence", 0.0)
            print(f"  {i}. {comp_name} (confidence: {conf:.2f})")

        # Save debate transcript
        transcript_path = None
        if self.reporter:
            transcript_path = self._save_debate_transcript(
                technology, agent_responses_for_transcript, debate_result
            )
            if transcript_path:
                print(f"\n📄 Debate transcript saved to: {transcript_path}")

        # Create ComponentWithConfidence objects using debate-provided details
        final_components_with_confidence = []
        for norm_name in final_component_names:
            if norm_name in component_details:
                details = component_details[norm_name]
                final_components_with_confidence.append(
                    ComponentWithConfidence(
                        name=norm_name,
                        confidence=details["confidence"],
                        reasoning=details["reasoning"],
                    )
                )
            else:
                # Fallback (should never happen now that debate returns details)
                print(f"  ⚠️ No details found for '{norm_name}', using fallback")
                final_components_with_confidence.append(
                    ComponentWithConfidence(
                        name=norm_name.title(),
                        confidence=0.75,
                        reasoning="Consensus component from multi-agent debate",
                    )
                )

        print(f"✓ Created {len(final_components_with_confidence)} ComponentWithConfidence objects")

        print(f"\n🔍 ComponentList names (what will be saved):")
        for comp in final_components_with_confidence:
            print(f"   - {comp.name} (confidence: {comp.confidence:.2f})")

        return ComponentList(
            componentlist=final_components_with_confidence,
            technology_specification=technology_specification,
            technology_reasoning=technology_reasoning,
        )

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

            # Debug prints
            print(f"✓ Passing to reporter - Tech spec: {technology_specification}")
            print(
                f"✓ Passing to reporter - Tech reasoning: {technology_reasoning[:100] if technology_reasoning else 'None'}..."
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
            logger.error(f"Error saving debate transcript: {e}", exc_info=True)
            return None
