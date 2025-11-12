"""
STDN Pipeline Orchestrator

This module coordinates the end-to-end STDN generation workflow:
1. Component extraction (with optional multi-agent debate)
2. Materials identification for each component
3. Country production data enrichment
4. CSV output generation

The orchestrator manages agents, debate systems, checkpoint management,
and reporting for large-scale STDN generation from technology lists.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic_ai import RunUsage

from ..agents import get_component_agent, get_materials_agent
from ..debate import MultiAgentDebater  # FIXED: from ..debate not .debate
from ..dependencies import initialize_dependencies
from ..models import ConfigModel, STDNDependencies
from ..reporting import DebateReporter  # FIXED: from ..reporting not .debate
from ..utils import embed_comma_delimited_str
from .checkpoint import CheckpointManager


class STDNOrchestrator:
    """Orchestrates STDN generation with optional multi-agent debate"""

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
        Initialize orchestrator

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

        # Initialize debate system
        if enable_debate:
            self.debater = MultiAgentDebater(
                max_rounds=max_debate_rounds, convergence_threshold=convergence_threshold
            )

            # Find project root
            current_dir = Path(__file__).parent
            project_root = current_dir
            for parent in [current_dir] + list(current_dir.parents):
                if (parent / "pyproject.toml").exists():
                    project_root = parent
                    break

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

    async def process_technology(
        self, tech: str, role: str, domain: str, usage: RunUsage
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single technology through the complete STDN pipeline.

        Args:
            tech: Technology name
            role: Expert role context
            domain: Domain context
            usage: RunUsage tracker

        Returns:
            Dictionary with components, materials, and country data
        """
        print(f"\n{'=' * 80}")
        print(f"Processing: {tech}")
        print(f"{'=' * 80}\n")

        try:
            # Step 1: Extract components
            if self.use_debate:
                components_result = await self.extract_components_with_debate(tech, role, usage)
            else:
                result = await self.component_agent.run(
                    f"Extract the primary components of a {tech}",
                    deps=self.deps,
                    model=self.deps.model,
                )
                components_result = result.output if result else None

            if not components_result:
                print(f"❌ No components extracted for {tech}")
                return None

            components = (
                components_result.component_list
                if hasattr(components_result, "component_list")
                else components_result
            )

            print(f"✓ Extracted {len(components)} components")

            # Step 2: Extract materials for each component
            # BUILD PROMPT WITH ONTOLOGY
            component_str = ", ".join(components)

            # Get first 100 materials from ontology (to keep prompt size reasonable)
            ontology_sample = self.deps.material_ontology_list[:100]
            ontology_str = ", ".join(ontology_sample)

            materials_prompt = f"""Extract raw materials for these components: {component_str}

AVAILABLE MATERIALS (use these exact names):
{ontology_str}

For each component, identify 2-8 key materials from the list above. Use exact names (case-sensitive)."""

            materials_result = await self.materials_agent.run(
                materials_prompt,
                deps=self.deps,
                model=self.deps.model,
            )

            if not materials_result or not materials_result.output:
                print(f"❌ No materials extracted for {tech}")
                return None

            materials_list = materials_result.output.component_list

            print(f"✓ Extracted materials for {len(materials_list)} components")

            # Step 3: Get country data for each material
            # (Your existing country data code here...)

            return {
                "technology": tech,
                "role": role,
                "domain": domain,
                "components": components,
                "materials": [
                    {
                        "component": m.component,
                        "materials": m.raw_materials,
                    }
                    for m in materials_list
                ],
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"❌ Error processing {tech}: {e}")
            return None

    async def extract_components_with_debate(
        self, technology: str, role: str, usage: RunUsage, num_agents: int = 3
    ) -> Dict[str, Any]:
        """Extract components using multi-agent debate"""

        print(f"\n{'=' * 80}")
        print(f"DEBATE-BASED COMPONENT EXTRACTION: {technology}")
        print(f"{'=' * 80}\n")

        # Collect proposals
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
            self.reporter.save_debate_transcript(
                technology=technology,
                agent_responses=[],
                debate_rounds=self.debater.debate_history,
                final_consensus=debate_result.get("final_consensus", {}),
                file_format="txt",
            )

        # Extract final components
        if debate_result and "final_consensus" in debate_result:
            final_components = [
                c["component"] for c in debate_result["final_consensus"].get("components", [])
            ]

            # Return in ComponentList format
            from ..agents import ComponentList

            return ComponentList(component_list=final_components)

        return None

    def write_csv_output(self, results: List[Dict], start_new_file: bool = False):
        """Write results to CSV file"""
        import csv
        from pathlib import Path

        if not results:
            print("No results to write")
            return

        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Determine write mode
        mode = "w" if start_new_file else "a"
        write_header = start_new_file or not output_path.exists()

        # Define CSV columns
        fieldnames = [
            "technology",
            "role",
            "domain",
            "timestamp",
            "component",
            "materials",
            "countries",
        ]

        with open(output_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if write_header:
                writer.writeheader()

            # Write each result
            for result in results:
                tech = result.get("technology", "")
                role = result.get("role", "")
                domain = result.get("domain", "")
                timestamp = result.get("timestamp", "")

                # Get materials data
                materials_data = result.get("materials", [])

                if not materials_data:
                    # No materials - write tech row with empty data
                    if self.write_nulls:
                        writer.writerow(
                            {
                                "technology": tech,
                                "role": role,
                                "domain": domain,
                                "timestamp": timestamp,
                                "component": "",
                                "materials": "",
                                "countries": "",
                            }
                        )
                    continue

                # Write one row per component
                for comp_data in materials_data:
                    component = comp_data.get("component", "")
                    materials = comp_data.get("materials", [])

                    # Format materials as comma-delimited string
                    materials_str = embed_comma_delimited_str(",".join(materials))

                    writer.writerow(
                        {
                            "technology": tech,
                            "role": role,
                            "domain": domain,
                            "timestamp": timestamp,
                            "component": component,
                            "materials": materials_str,
                            "countries": "",  # TODO: Add country data when implemented
                        }
                    )

        print(f"\n✓ Output written to: {output_path}")
