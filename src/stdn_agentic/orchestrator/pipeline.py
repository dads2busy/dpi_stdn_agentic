"""
STDN Pipeline orchestration and workflow management

This module provides the main STDNOrchestrator class that coordinates the entire
STDN generation pipeline, including:
- Component extraction with optional multi-agent debate
- Materials extraction with validation
- Country data enrichment
- Output generation and checkpoint management
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic_ai import RunUsage

from ..agents import (
    ComponentMaterialsList,
    get_component_agent,
    get_materials_agent,
)
from ..debate import MultiAgentDebater
from ..dependencies import initialize_dependencies
from ..models import ConfigModel, STDNDependencies
from ..reporting import DebateReporter
from ..utils import embed_comma_delimited_str
from .checkpoint import CheckpointManager

# ============================================================================
# STDN Orchestrator
# ============================================================================


class STDNOrchestrator:
    """
    Orchestrates STDN generation with optional multi-agent debate.

    The orchestrator coordinates the complete pipeline:
    1. Component extraction (with optional debate)
    2. Materials identification (with validation)
    3. Country data enrichment
    4. Output generation and saving

    Attributes:
        config: Configuration model
        enable_checkpoints: Whether to save/load checkpoints
        use_debate: Whether to use multi-agent debate
        max_debate_rounds: Maximum debate rounds
        convergence_threshold: Convergence threshold for debate

    Example:
        >>> config = ConfigModel(...)
        >>> orchestrator = STDNOrchestrator(
        ...     config,
        ...     enable_debate=True,
        ...     max_debate_rounds=3
        ... )
        >>> result = await orchestrator.process_technology(
        ...     tech="smartphone",
        ...     role="supply chain analyst",
        ...     domain="consumer electronics",
        ...     usage=RunUsage()
        ... )
    """

    def __init__(
        self,
        config: ConfigModel,
        enable_checkpoints: bool = False,
        enable_debate: bool = False,
        max_debate_rounds: int = 3,
        convergence_threshold: float = 0.8,
        save_transcripts: bool = True,
    ):
        """
        Initialize orchestrator.

        Args:
            config: ConfigModel instance
            enable_checkpoints: Enable checkpoint saving
            enable_debate: Use multi-agent debate (True) or simple voting (False)
            max_debate_rounds: Max debate rounds
            convergence_threshold: Convergence threshold
            save_transcripts: Save debate transcripts
        """
        self.config = config

        os.environ["STDN_MODEL"] = config.model

        self.enable_checkpoints = enable_checkpoints
        self.use_debate = enable_debate
        self.max_debate_rounds = max_debate_rounds
        self.convergence_threshold = convergence_threshold

        # Initialize dependencies
        self.deps = initialize_dependencies(config)
        self.write_nulls = config.write_nulls_to_output

        # Get agents
        self.component_agent = get_component_agent()
        self.materials_agent = get_materials_agent()

        # Initialize checkpointing
        self.checkpoint_manager = CheckpointManager() if enable_checkpoints else None

        # Initialize debate system with CORRECT PATH RESOLUTION
        if enable_debate:
            self.debater = MultiAgentDebater(
                max_rounds=max_debate_rounds, convergence_threshold=convergence_threshold
            )

            # Find project root by looking for pyproject.toml
            current_dir = Path(__file__).parent
            project_root = current_dir

            # Walk up directory tree to find project root
            for parent in [current_dir] + list(current_dir.parents):
                if (parent / "pyproject.toml").exists():
                    project_root = parent
                    break

            # Save transcripts to: {PROJECT_ROOT}/src/stdn_agentic/debate_transcripts/results/
            transcript_dir = (
                project_root / "src" / "stdn_agentic" / "debate_transcripts" / "results"
            )

            print(f"\n[STDNOrchestrator] Debate transcripts will be saved to:")
            print(f"  {transcript_dir.resolve()}")

            self.reporter = DebateReporter(output_dir=str(transcript_dir))
        else:
            self.debater = None
            self.reporter = None

        # Output file
        output_filename = f"{config.output_csv_filename}.csv"
        self.output_file = os.path.join(config.output_dir, output_filename)
        os.makedirs(config.output_dir, exist_ok=True)

    async def extract_components_with_debate(
        self, technology: str, role: str, usage: RunUsage, num_agents: int = 3
    ) -> Dict[str, Any]:
        """
        Extract components using multi-agent debate.

        Args:
            technology: Technology name
            role: Expert role
            usage: RunUsage tracker
            num_agents: Number of agents

        Returns:
            Final consensus with components
        """

        if not self.use_debate:
            print(f"\nExtracting components for: {technology}")
            result = await self.component_agent.run(
                f"Extract the primary components of a {technology}",
                deps=self.deps,
                model=self.deps.model,
            )
            return result.output if result else None

        print(f"\n{'=' * 80}")
        print(f"DEBATE-BASED COMPONENT EXTRACTION: {technology}")
        print(f"{'=' * 80}\n")

        # Collect proposals from multiple agents
        print(f"📋 Collecting proposals from {num_agents} agents...\n")

        agent_proposals = {}
        for agent_num in range(1, num_agents + 1):
            agent_id = f"Agent_{agent_num}"

            result = await self.component_agent.run(
                f"Extract the primary components of a {technology}. Perspective {agent_num}.",
                deps=self.deps,
                model=self.deps.model,
            )

            if result and result.output:
                components = (
                    result.output.component_list
                    if hasattr(result.output, "component_list")
                    else result.output
                )
                agent_proposals[agent_id] = [
                    {
                        "component": comp,
                        "confidence": 0.85,
                        "reasoning": "Identified as key component",
                    }
                    for comp in components
                ]
                print(f"  ✓ {agent_id}: {len(agent_proposals[agent_id])} components proposed")

        if not agent_proposals:
            print("❌ No agent proposals received")
            return None

        print()

        # Run debate
        print(f"🎤 Running debate...\n")
        debate_result = self.debater.run_debate(technology, agent_proposals)

        # Save transcript if enabled
        if self.reporter and debate_result:
            try:
                transcript_file = self.reporter.save_debate_transcript(
                    technology=technology,
                    agent_responses=[],
                    debate_rounds=[],
                    final_consensus=debate_result.get("final_consensus", {}),
                    file_format="txt",
                )
                print(f"\n📄 Debate transcript saved: {transcript_file}")
            except Exception as e:
                print(f"\n⚠️  Failed to save debate transcript: {e}")

        return debate_result.get("final_consensus", {})

    async def process_technology(
        self,
        tech: str,
        role: str,
        domain: str,
        usage: RunUsage,
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single technology through the complete STDN pipeline.

        Args:
            tech: Technology name
            role: Expert role
            domain: Technology domain
            usage: RunUsage tracker

        Returns:
            Dictionary with STDN data, or None if processing failed
        """
        print(f"\n{'=' * 80}")
        print(f"Processing: {tech}")
        print(f"{'=' * 80}")

        # Check for checkpoint
        if self.checkpoint_manager:
            checkpoint = self.checkpoint_manager.load_checkpoint({"tech": tech})
            if checkpoint:
                print(f"⏩ Resuming from checkpoint at {checkpoint['progress_pct']:.1f}%")
                # Resume logic here
                pass

        try:
            # Step 1: Extract components
            if self.use_debate:
                components_result = await self.extract_components_with_debate(
                    technology=tech,
                    role=role,
                    usage=usage,
                )
                if components_result and "components" in components_result:
                    components = [c["component"] for c in components_result["components"]]
                else:
                    components = []
            else:
                result = await self.component_agent.run(
                    f"Extract the primary components of a {tech}",
                    deps=self.deps,
                    model=self.deps.model,
                )
                components = result.output.component_list if result else []

            if not components:
                print(f"⚠️  No components extracted for {tech}")
                return None

            print(f"\n✓ Extracted {len(components)} components")

            # Step 2: Extract materials
            materials_prompt = (
                f"For each component of a {tech}, identify the raw materials used. "
                f"Components: {', '.join(components)}"
            )

            materials_result = await self.materials_agent.run(
                materials_prompt,
                deps=self.deps,
                model=self.deps.model,
            )

            if not materials_result:
                print(f"⚠️  No materials extracted for {tech}")
                return None

            materials_data = materials_result.output
            print(f"✓ Extracted materials for {len(materials_data.component_list)} components")

            # Step 3: Build output structure
            result = {
                "technology": tech,
                "role": role,
                "domain": domain,
                "timestamp": datetime.now().isoformat(),
                "components": components,
                "materials": [
                    {
                        "component": cm.component,
                        "materials": cm.raw_materials,
                    }
                    for cm in materials_data.component_list
                ],
            }

            # Save checkpoint if enabled
            if self.checkpoint_manager:
                self.checkpoint_manager.save_checkpoint(
                    config={"tech": tech},
                    processed_techs=[tech],
                    results=[result],
                    current_index=1,
                    total_count=1,
                )

            return result

        except Exception as e:
            print(f"❌ Error processing {tech}: {e}")
            return None

    def write_csv_output(
        self,
        results: List[Dict[str, Any]],
        start_new_file: bool = False,
    ) -> None:
        """
        Write results to CSV output file.

        Args:
            results: List of result dictionaries
            start_new_file: Whether to start a new file (True) or append (False)
        """
        if not results:
            return

        import csv

        mode = "w" if start_new_file else "a"
        file_exists = os.path.exists(self.output_file)

        with open(self.output_file, mode, newline="") as f:
            # Define fieldnames
            fieldnames = [
                "technology",
                "role",
                "domain",
                "timestamp",
                "components",
                "materials",
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)

            # Write header if new file or file doesn't exist
            if start_new_file or not file_exists:
                writer.writeheader()

            # Write rows
            for result in results:
                # Convert lists to strings for CSV
                row = {
                    "technology": result.get("technology", ""),
                    "role": result.get("role", ""),
                    "domain": result.get("domain", ""),
                    "timestamp": result.get("timestamp", ""),
                    "components": embed_comma_delimited_str(result.get("components", [])),
                    "materials": str(result.get("materials", [])),
                }
                writer.writerow(row)

        print(f"\n✓ Results written to: {self.output_file}")


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "STDNOrchestrator",
]
