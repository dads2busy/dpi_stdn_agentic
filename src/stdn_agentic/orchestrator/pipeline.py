"""
STDN Pipeline Orchestrator

This module coordinates the end-to-end STDN generation workflow:
1. Component extraction (with optional multi-agent debate)
2. Materials identification for each component
3. Country production data enrichment
4. CSV output generation

The orchestrator manages agents, debate systems, checkpoint management,
and reporting for large-scale STDN generation from technology lists.

Enhanced features:
- Robust materials extraction with comprehensive error handling
- Enhanced multi-agent debate with critique-driven convergence
- Adaptive consensus building based on convergence scores
- Detailed logging and progress reporting
"""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic_ai import RunUsage

from ..agents import (
    ComponentList,
    ComponentMaterialsList,
    get_component_agent,
    get_materials_agent,
)
from ..data import CountryDataRepository
from ..debate import MultiAgentDebater
from ..dependencies import initialize_dependencies
from ..models import ConfigModel, STDNDependencies
from ..reporting import DebateReporter
from ..utils import embed_comma_delimited_str
from .checkpoint import CheckpointManager

# Initialize logger
logger = logging.getLogger(__name__)


# ============================================================================
# STDN Orchestrator
# ============================================================================


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
        Initialize orchestrator with enhanced debate and error handling.

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
        self.save_transcripts = save_transcripts

        # Initialize dependencies
        self.deps = initialize_dependencies(config)
        self.write_nulls = config.write_nulls_to_output

        # Get agents
        self.component_agent = get_component_agent()
        self.materials_agent = get_materials_agent()

        # Initialize checkpointing
        self.checkpoint_manager = CheckpointManager() if enable_checkpoints else None

        # Initialize debate system with enhanced parameters
        if enable_debate:
            self.debater = MultiAgentDebater(
                max_rounds=max_debate_rounds,
                convergence_threshold=convergence_threshold,
                confidence_weight=0.3,  # Weight for confidence in voting
                peer_support_boost=0.15,  # Boost per supporting agent
            )

            # Find project root for transcript output
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

        # Initialize country data repository with validation
        if not config.usgs_database:
            raise ValueError(
                "USGS database path is required. Please set 'usgs_database' in your config.json"
            )

        self.country_repo = CountryDataRepository(
            database_path=config.usgs_database,
            deps=self.deps,
            top_n=5,
            use_llm_fallback=True,
        )

        # Output file
        output_filename = f"{config.output_csv_filename}.csv"
        self.output_file = os.path.join(config.output_dir, output_filename)
        os.makedirs(config.output_dir, exist_ok=True)

    # ========================================================================
    # Safe Materials Extraction with Comprehensive Validation
    # ========================================================================

    async def extract_materials_safe(
        self, component_list: ComponentList, technology: str, usage: RunUsage
    ) -> Optional[ComponentMaterialsList]:
        """
        Safely extract materials with comprehensive error handling.

        This method prevents 400 errors by validating inputs at every step:
        - Validates component list is not null/empty
        - Filters out invalid components
        - Checks ontology availability
        - Validates prompt generation
        - Handles LLM errors gracefully

        Args:
            component_list: List of components
            technology: Technology name (for error reporting)
            usage: RunUsage tracker

        Returns:
            ComponentMaterialsList or None if extraction fails
        """
        try:
            # VALIDATION 1: Check component list exists
            if not component_list or not hasattr(component_list, "component_list"):
                logger.warning(f"No components to extract materials from for {technology}")
                print(f"  ⚠️  No components to extract materials from")
                return ComponentMaterialsList(component_list=[])

            components = component_list.component_list

            # VALIDATION 2: Filter valid components (non-null, non-empty strings)
            valid_components = [c for c in components if c and isinstance(c, str) and c.strip()]

            if not valid_components:
                logger.warning(f"All components were null/empty for {technology}")
                print(f"  ⚠️  All components were null/empty")
                return ComponentMaterialsList(component_list=[])

            # VALIDATION 3: Check ontology availability
            if not self.deps.material_ontology_list or len(self.deps.material_ontology_list) == 0:
                logger.error(
                    f"Material ontology is empty - cannot extract materials for {technology}"
                )
                print(f"  ❌  Material ontology is empty!")
                return ComponentMaterialsList(component_list=[])

            # Build prompt with validated data
            component_str = "\n".join([f"- {comp}" for comp in valid_components])

            # Limit ontology size to avoid token overflow (keep most common materials)
            ontology_sample = self.deps.material_ontology_list[:100]
            ontology_str = ", ".join(ontology_sample)

            materials_prompt = f"""Extract RAW MATERIALS (NOT components or subassemblies) for these components of a {technology}:

            {component_str}

            AVAILABLE RAW MATERIALS (use exact names or common variants):
            {ontology_str}

            CRITICAL INSTRUCTIONS:
            - For each component, identify 2-8 key RAW MATERIALS (metals, minerals, elements, compounds)
            - Do NOT return component names, subassemblies, or finished parts
            - Return only basic materials like: Aluminum, Copper, Silicon, Lithium, Glass, Steel, Rare Earth Elements
            - Use standard material names or their common variants

            EXAMPLES:
            - Battery Pack → Lithium, Cobalt, Nickel, Copper, Aluminum, Graphite
            - Display Module → Glass, Indium, Rare Earth Elements, Plastic
            - Processor Unit → Silicon, Copper, Gold, Tantalum, Ceramic"""

            # VALIDATION 4: Check prompt is valid
            if not materials_prompt or len(materials_prompt.strip()) < 20:
                logger.error(f"Generated materials prompt is too short for {technology}")
                print(f"  ❌  Generated materials prompt is too short")
                return ComponentMaterialsList(component_list=[])

            logger.info(
                f"Extracting materials for {len(valid_components)} components of {technology}"
            )
            print(f"  🔍 Extracting materials for {len(valid_components)} components...")

            # Call materials agent with validated inputs
            result = await self.materials_agent.run(
                materials_prompt, deps=self.deps, model=self.deps.model
            )

            # VALIDATION 5: Check result validity
            if not result or not result.output:
                logger.warning(f"Materials agent returned empty result for {technology}")
                print(f"  ⚠️  Materials agent returned empty result")
                return ComponentMaterialsList(component_list=[])

            materials_list = result.output

            # VALIDATION 6: Check materials list has content
            if not materials_list.component_list:
                logger.warning(f"Materials list is empty for {technology}")
                print(f"  ⚠️  Materials list is empty")
                return ComponentMaterialsList(component_list=[])

            num_materials = sum(len(cm.raw_materials) for cm in materials_list.component_list)
            logger.info(
                f"✓ Extracted {num_materials} materials for {len(materials_list.component_list)} components of {technology}"
            )
            print(f"  ✓ Extracted materials for {len(materials_list.component_list)} components")

            return materials_list

        except Exception as e:
            logger.error(f"Error extracting materials for {technology}: {e}", exc_info=True)
            print(f"  ❌  Error extracting materials for {technology}: {e}")

            # Return empty list rather than crashing entire pipeline
            return ComponentMaterialsList(component_list=[])

    # ========================================================================
    # Component Extraction with Enhanced Debate
    # ========================================================================

    async def extract_components_with_debate(
        self, technology: str, role: str, usage: RunUsage, num_agents: int = 3
    ) -> Optional[ComponentList]:
        """
        Extract components using enhanced multi-agent debate with critique-driven convergence.

        Args:
            technology: Technology name
            role: Expert role context
            usage: RunUsage tracker
            num_agents: Number of agents to use in debate (default: 3)

        Returns:
            ComponentList with consensus components, or None if extraction fails
        """

        print(f"\n{'=' * 80}")
        print(f"DEBATE-BASED COMPONENT EXTRACTION: {technology}")
        print(f"{'=' * 80}\n")

        # Collect initial proposals from multiple agents
        print(f"📋 Collecting proposals from {num_agents} agents...\n")

        agent_proposals = {}
        agent_responses_for_transcript = []

        for agent_num in range(1, num_agents + 1):
            agent_id = f"Agent_{agent_num}"

            try:
                # Each agent gets a slightly different perspective prompt
                result = await self.component_agent.run(
                    f"Extract the primary components of a {technology}. "
                    f"Perspective #{agent_num}: Focus on identifying essential subsystems and modules.",
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

                    print(f"  ✓ {agent_id}: {len(components)} components proposed")

                    # Store for transcript
                    agent_responses_for_transcript.append(
                        {
                            "agent_id": agent_id,
                            "components": agent_proposals[agent_id],
                            "persona": f"Component extraction perspective #{agent_num}",
                        }
                    )

            except Exception as e:
                logger.error(f"Error in {agent_id} proposal generation for {technology}: {e}")
                print(f"  ✗ {agent_id}: Failed to generate proposal")

        if not agent_proposals:
            logger.error(f"No agent proposals received for {technology}")
            print("❌ No agent proposals received")
            return None

        print(f"\n🎤 Running debate...\n")

        # Run enhanced debate with critique-driven convergence
        try:
            debate_result = await self.debater.run_debate(
                technology=technology,
                initial_proposals=agent_proposals,
                component_agent=self.component_agent,
                deps=self.deps,
            )
        except Exception as e:
            logger.error(f"Error during debate for {technology}: {e}", exc_info=True)
            print(f"❌ Debate failed: {e}")
            return None

        # Save transcript if enabled
        if self.save_transcripts and self.reporter:
            try:
                transcript_path = self._save_debate_transcript(
                    technology, agent_responses_for_transcript, debate_result
                )
                print(f"\n📄 Transcript saved: {transcript_path}")
            except Exception as e:
                logger.error(f"Error saving debate transcript: {e}")
                print(f"⚠️  Failed to save transcript: {e}")

        # Extract final components from debate result
        final_components = debate_result.get("components", [])

        # Debug output
        print(f"\n🔍 Debug - Consensus type: {type(debate_result)}")
        print(f"🔍 Debug - Consensus keys: {list(debate_result.keys())}")
        print(f"📊 Final components extracted: {final_components}")

        if final_components:
            return ComponentList(component_list=final_components)
        else:
            logger.warning(f"Debate produced no consensus components for {technology}")
            return None

    def _save_debate_transcript(
        self, technology: str, agent_responses: List[Dict], debate_result: Dict
    ) -> Optional[Path]:
        """
        Save debate transcript in both text and JSON formats.

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

            # Extract round count from debate_result
            num_rounds = debate_result.get("rounds", 0)
            confidence = debate_result.get("confidence", 0.0)

            # Build final consensus dict with proper metadata
            final_consensus = {
                "technology": technology,
                "components": debate_result.get("components", []),
                "confidence": confidence,
                "rounds": num_rounds,  # ✅ Include rounds count
                "convergence_score": confidence,
            }

            # Save text version
            filepath = self.reporter.save_debate_transcript(
                technology=technology,
                agent_responses=agent_responses,
                debate_rounds=[],  # TODO: Could be enhanced with full round history
                final_consensus=final_consensus,  # ✅ Now includes rounds
                file_format="txt",
            )

            # Also save JSON version for programmatic access
            self.reporter.save_debate_transcript(
                technology=technology,
                agent_responses=agent_responses,
                debate_rounds=[],
                final_consensus=final_consensus,  # ✅ Now includes rounds
                file_format="json",
            )

            return filepath

        except Exception as e:
            logger.error(f"Error saving debate transcript: {e}", exc_info=True)
            return None

    # ========================================================================
    # Main Processing Pipeline
    # ========================================================================

    async def process_technology(
        self, tech: str, role: str, domain: str, usage: RunUsage
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single technology through the complete STDN pipeline.

        Pipeline stages:
        1. Component extraction (with debate if enabled)
        2. Materials extraction (with enhanced matching)
        3. Country data enrichment (USGS + LLM fallback)
        4. Data aggregation and formatting

        Args:
            tech: Technology name
            role: Expert role context
            domain: Domain context
            usage: RunUsage tracker

        Returns:
            Dictionary with components, materials, and enriched country data,
            or None if processing fails
        """
        print(f"\n{'=' * 80}")
        print(f"Processing: {tech}")
        print(f"{'=' * 80}\n")

        try:
            # ================================================================
            # STAGE 1: Extract Components
            # ================================================================
            if self.use_debate:
                components_result = await self.extract_components_with_debate(tech, role, usage)
            else:
                # Simple single-agent extraction
                result = await self.component_agent.run(
                    f"Extract the primary components of a {tech}",
                    deps=self.deps,
                    model=self.deps.model,
                )
                components_result = result.output if result else None

            if not components_result:
                logger.error(f"No components extracted for {tech}")
                print(f"❌ No components extracted for {tech}")
                return None

            components = (
                components_result.component_list
                if hasattr(components_result, "component_list")
                else components_result
            )

            print(f"✓ Extracted {len(components)} components")

            # ================================================================
            # STAGE 2: Extract Materials (with safe error handling)
            # ================================================================
            materials_result = await self.extract_materials_safe(
                component_list=ComponentList(component_list=components),
                technology=tech,
                usage=usage,
            )

            if not materials_result or not materials_result.component_list:
                logger.error(f"No materials extracted for {tech}")
                print(f"❌ No materials extracted for {tech}")
                return None

            materials_list = materials_result.component_list

            # ================================================================
            # STAGE 3: Enrich with Country Production Data
            # ================================================================
            enriched_data = []

            for comp_mat in materials_list:
                component = comp_mat.component
                materials = comp_mat.raw_materials

                for material in materials:
                    # Query country data from USGS database + LLM fallback
                    try:
                        country_data = await self.country_repo.get_country_data(
                            material=material,
                            src_year=getattr(self.config, "src_year", 2024),  # Safe fallback
                            meas_year=getattr(self.config, "meas_year", 2025),  # Safe fallback
                            usage=usage,
                        )

                        if country_data:
                            for country_info in country_data:
                                enriched_data.append(
                                    {
                                        "technology": tech,
                                        "component": component,
                                        "material": material,
                                        "country": country_info["country"],
                                        "meas_unit": country_info["meas_unit"],
                                        "amount": country_info["amount"],
                                        "percentage": country_info["percentage"],
                                    }
                                )
                        elif self.write_nulls:
                            # Write row with nulls if no data found
                            enriched_data.append(
                                {
                                    "technology": tech,
                                    "component": component,
                                    "material": material,
                                    "country": None,
                                    "meas_unit": None,
                                    "amount": None,
                                    "percentage": None,
                                }
                            )
                    except Exception as e:
                        logger.error(f"Error getting country data for {material}: {e}")
                        # Continue processing other materials

            return {
                "technology": tech,
                "components": components,
                "materials": materials_list,
                "enriched_data": enriched_data,
            }

        except Exception as e:
            logger.error(f"Error processing technology {tech}: {e}", exc_info=True)
            print(f"❌ Error processing {tech}: {e}")
            return None

    # ========================================================================
    # Pipeline Execution
    # ========================================================================

    async def run_pipeline(
        self,
        technologies: List[str],
        role: str = "supply chain analyst",
        domain: str = "technology",
    ) -> Dict[str, Any]:
        """
        Run complete STDN pipeline for multiple technologies.

        Args:
            technologies: List of technology names
            role: Expert role context
            domain: Domain context

        Returns:
            Dict with results and statistics
        """
        usage = RunUsage()

        print(f"\n{'=' * 80}")
        print(f"STDN Generation Started: {datetime.now()}")
        print(f"{'=' * 80}\n")

        if self.use_debate:
            print(f"🎤 Multi-agent debate ENABLED:")
            print(f"   Max rounds: {self.max_debate_rounds}")
            print(f"   Convergence threshold: {self.convergence_threshold}")
            print(f"   Save transcripts: {self.save_transcripts}")

        print(f"\nLoaded {len(technologies)} technologies from {self.config.tech_list_path}\n")

        successful = 0
        failed = 0

        # Write CSV header
        with open(self.output_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "technology",
                    "component",
                    "material",
                    "country",
                    "meas_unit",
                    "amount",
                    "percentage",
                ],
            )
            writer.writeheader()

        # Process each technology
        for tech in technologies:
            result = await self.process_technology(tech, role, domain, usage)

            if result and result["enriched_data"]:
                # Write results to CSV
                with open(self.output_file, "a", newline="") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "technology",
                            "component",
                            "material",
                            "country",
                            "meas_unit",
                            "amount",
                            "percentage",
                        ],
                    )

                    for row in result["enriched_data"]:
                        writer.writerow(row)

                print(f"\n✓ Output written to: {self.output_file}")
                print(f"✓ Successfully processed: {tech}")
                successful += 1
            else:
                print(f"✗ Failed to process: {tech}")
                failed += 1

        print(f"\n{'=' * 80}")
        print(f"STDN Generation Completed: {datetime.now()}")
        print(f"{'=' * 80}\n")
        print(f"Successfully processed: {successful}/{len(technologies)} technologies\n")
        print(f"✓ Output saved to: {self.output_file}")

        if self.use_debate and self.reporter:
            print(f"✓ Debate transcripts saved to: {self.reporter.output_dir}\n")

        print(f"Usage: {usage}\n")

        if successful > 0:
            print(f"✓ Successfully processed {successful} technologies")

        return {
            "successful": successful,
            "failed": failed,
            "total": len(technologies),
            "output_file": self.output_file,
        }


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "STDNOrchestrator",
]
