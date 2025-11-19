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

import asyncio
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
from ..models import ConfigModel
from ..reporting import DebateReporter
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
        enable_material_debate: bool = False,
        max_debate_rounds: int = 3,
        convergence_threshold: float = 0.8,
        save_transcripts: bool = True,
        debate_top_p: float = 0.0001,
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
        self.use_material_debate = enable_material_debate
        self.max_debate_rounds = max_debate_rounds
        self.convergence_threshold = convergence_threshold
        self.save_transcripts = save_transcripts
        self.debate_top_p = debate_top_p

        # Initialize dependencies
        self.deps = initialize_dependencies(config)
        self.write_nulls = config.write_nulls_to_output

        # Get agents
        self.component_agent = get_component_agent(model_name=self.deps.model)
        self.materials_agent = get_materials_agent(model_name=self.deps.model)

        # Initialize checkpointing
        self.checkpoint_manager = CheckpointManager() if enable_checkpoints else None

        # Initialize debate system with enhanced parameters
        if enable_debate:
            self.debater = MultiAgentDebater(
                max_rounds=max_debate_rounds,
                convergence_threshold=convergence_threshold,
                confidence_weight=0.3,  # Weight for confidence in voting
                peer_support_boost=0.15,  # Boost per supporting agent
                debate_top_p=debate_top_p,
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

            print("\n[STDNOrchestrator] Debate transcripts will be saved to:")
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
        self,
        componentlist: ComponentList,
        technology: str,
        usage: RunUsage,
        max_retries: int = 3,
    ) -> Optional[ComponentMaterialsList]:
        """
        Safely extract materials with comprehensive error handling and retry logic.

        Args:
            componentlist: ComponentList object containing components
            technology: Technology name
            usage: RunUsage tracker
            max_retries: Maximum number of retry attempts on transient errors

        Returns:
            ComponentMaterialsList with extracted materials, or empty list on error
        """
        # VALIDATION 1: Check component list exists
        if not componentlist or not hasattr(componentlist, "component_list"):
            logger.warning(f"No components to extract materials from for {technology}")
            print("🔍 No components to extract materials from")
            return ComponentMaterialsList.model_validate({"componentlist": []})

        components = componentlist.component_list  # Access component_list field

        # VALIDATION 2: Filter valid components
        valid_components = [c for c in components if c and isinstance(c, str) and c.strip()]
        if not valid_components:
            logger.warning(f"All components were null/empty for {technology}")
            print("🔍 All components were null/empty")
            return ComponentMaterialsList.model_validate({"componentlist": []})

        # VALIDATION 3: Check ontology availability
        if not self.deps.material_ontology_list or len(self.deps.material_ontology_list) == 0:
            logger.error(f"Material ontology is empty - cannot extract materials for {technology}")
            print("❌ Material ontology is empty!")
            return ComponentMaterialsList.model_validate({"componentlist": []})

        # Build prompt with validated data
        component_str = "\n".join(f"- {comp}" for comp in valid_components)
        # Reduced ontology sample size for stability (from 100 to 50)
        ontology_sample = self.deps.material_ontology_list[:50]
        ontology_str = ", ".join(ontology_sample)

        # CRITICAL FIX: Ensure all prompt parts are non-None strings
        materials_prompt = f"""Extract RAW MATERIALS (NOT components or subassemblies) for these components of a {technology}:

    {component_str}

    AVAILABLE RAW MATERIALS (use exact names or common variants):
    {ontology_str}

    CRITICAL INSTRUCTIONS:
    - For each component, identify 2-8 key RAW MATERIALS (metals, minerals, elements, compounds)
    - Do NOT return component names, subassemblies, or finished parts
    - Return only basic materials like Aluminum, Copper, Silicon, Lithium, Glass, Steel, Rare Earth Elements
    - Use standard material names or their common variants

    EXAMPLES:
    - Battery Pack: Lithium, Cobalt, Nickel, Copper, Aluminum, Graphite
    - Display Module: Glass, Indium, Rare Earth Elements, Plastic
    - Processor Unit: Silicon, Copper, Gold, Tantalum, Ceramic

    Return a JSON response with componentlist containing component and materials fields."""

        # VALIDATION 4: Check prompt is valid and non-empty
        if (
            not materials_prompt
            or not isinstance(materials_prompt, str)
            or len(materials_prompt.strip()) < 50
        ):
            logger.error(f"Generated materials prompt is invalid for {technology}")
            print("❌ Generated materials prompt is too short or None")
            print(f"🔍 Prompt length: {len(materials_prompt) if materials_prompt else 0}")
            return ComponentMaterialsList.model_validate({"componentlist": []})

        # VALIDATION 5: Ensure deps and model are valid
        if not self.deps or not self.deps.model:
            logger.error(f"Dependencies or model not configured for {technology}")
            print("❌ Dependencies not properly configured")
            return ComponentMaterialsList.model_validate({"componentlist": []})

        logger.info(
            f"📋 Extracting materials for {len(valid_components)} components of {technology}"
        )
        print(f"  🔍 Extracting materials for {len(valid_components)} components...")
        print(f"  🔍 Using model: {self.deps.model}")
        print(f"  🔍 Prompt length: {len(materials_prompt)} chars")

        # RETRY LOGIC: Handle transient Ollama/model errors
        for attempt in range(max_retries):
            try:
                # Call materials agent with validated inputs
                result = await self.materials_agent.run(
                    materials_prompt,
                    deps=self.deps,
                )

                # VALIDATION 6: Check result validity
                if not result or not result.output:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Materials agent returned empty result for {technology} "
                            f"(attempt {attempt + 1}/{max_retries}), retrying..."
                        )
                        await asyncio.sleep(2**attempt)  # Exponential backoff: 1s, 2s, 4s
                        continue
                    else:
                        logger.warning(
                            f"Materials agent returned empty result for {technology} after all retries"
                        )
                        print(
                            f"⚠️  Materials agent returned empty result after {max_retries} attempts"
                        )
                        return ComponentMaterialsList.model_validate({"componentlist": []})

                materials_list = result.output

                # VALIDATION 7: Check materials list has content
                if not materials_list.component_list:  # Use component_list field
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Materials list is empty for {technology} "
                            f"(attempt {attempt + 1}/{max_retries}), retrying..."
                        )
                        await asyncio.sleep(2**attempt)
                        continue
                    else:
                        logger.warning(
                            f"Materials list is empty for {technology} after all retries"
                        )
                        print(f"⚠️  Materials list is empty after {max_retries} attempts")
                        return ComponentMaterialsList.model_validate({"componentlist": []})

                # SUCCESS - Access raw_materials field (not rawmaterials)
                num_materials = sum(len(cm.raw_materials) for cm in materials_list.component_list)
                logger.info(
                    f"✅ Extracted {num_materials} materials for {len(materials_list.component_list)} "
                    f"components of {technology}"
                )
                print(
                    f"  ✅ Extracted materials for {len(materials_list.component_list)} components"
                )

                return materials_list

            except Exception as e:
                # Check if this is a transient error worth retrying
                error_str = str(e)
                is_transient = (
                    "invalid message content type" in error_str
                    or "400" in error_str
                    or "BadRequestError" in error_str
                )

                if is_transient and attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Transient error extracting materials for {technology} "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    logger.info(f"Retrying in {wait_time} seconds...")
                    print(f"  ⚠️  Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed or non-transient error
                    logger.error(
                        f"Error extracting materials for {technology} after "
                        f"{attempt + 1} attempt(s): {e}",
                        exc_info=True,
                    )
                    print(f"  ❌  Error extracting materials for {technology}: {e}")
                    return ComponentMaterialsList.model_validate({"componentlist": []})

        # Should not reach here, but just in case
        logger.error(f"Exhausted all retries for {technology}")
        return ComponentMaterialsList.model_validate({"componentlist": []})

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
                # Create deps with very low Top-P for focused outputs
                from dataclasses import replace

                agent_deps = replace(self.deps, top_p=self.debate_top_p)

                # Each agent gets a slightly different perspective prompt
                result = await self.component_agent.run(
                    f"Extract the primary components of a {technology}. "
                    f"Perspective #{agent_num}: Focus on identifying essential subsystems and modules.",
                    deps=agent_deps,
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

                    print(
                        f"  ✓ {agent_id} (top_p={self.debate_top_p}): {len(components)} components proposed"
                    )

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

        print("\n🎤 Running debate...\n")

        # Run enhanced debate with critique-driven convergence
        if not self.debater:
            logger.error(f"Debater not initialized for {technology}")
            print("❌ Debater not initialized")
            return None

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
            return ComponentList(componentlist=final_components)
        else:
            logger.warning(f"Debate produced no consensus components for {technology}")
            return None

    def _save_debate_transcript(
        self, technology: str, agent_responses: List[Dict], debate_result: Dict
    ) -> Optional[Path]:
        """
        Save comprehensive debate transcript including materials assignment.

        Args:
            technology: Technology name
            agent_responses: Agent proposals and reasoning
            debate_result: Final debate consensus with rounds metadata
            materials_info: Optional materials extraction/debate information

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

            # Build final consensus dict with proper metadata
            final_consensus = {
                "technology": technology,
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
            )

            # Also save JSON version for programmatic access
            self.reporter.save_debate_transcript(
                technology=technology,
                agent_responses=agent_responses,
                debate_history=debate_history,
                final_consensus=final_consensus,
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
        self,
        tech: str,
        role: str,
        domain: str,
        usage: RunUsage,
        use_material_debate: bool = False,  # NEW PARAMETER
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single technology through the complete STDN pipeline.

        Pipeline stages:
        1. Component extraction (with debate if enabled)
        2. Materials extraction (with debate if use_material_debate=True)
        3. Country data enrichment (USGS + LLM fallback)
        4. Data aggregation and formatting

        Args:
            tech: Technology name
            role: Expert role context
            domain: Domain context
            usage: RunUsage tracker
            use_material_debate: Use multi-agent debate for materials (default False)

        Returns:
            Dictionary with components, materials, and enriched country data,
            or None if processing fails
        """
        print("=" * 80)
        print(f"Processing: {tech}")
        print("=" * 80)

        try:
            # Phase 1: Extract components (existing logic - with debate if enabled)
            if self.use_debate:
                components_result = await self.extract_components_with_debate(tech, role, usage)
            else:
                result = await self.component_agent.run(
                    f"Extract the primary components of a {tech}",
                    deps=self.deps,
                )
                components_result = result.output if result else None

            if not components_result:
                logger.error(f"No components extracted for {tech}")
                print(f"✗ No components extracted for {tech}")
                return None

            # Extract component list - ENSURE it's List[str], not ComponentList
            if hasattr(components_result, "component_list"):
                components: list[str] = (
                    components_result.component_list
                )  # Type annotation ONLY on first assignment
            elif isinstance(components_result, list):
                components = components_result  # No type annotation
            else:
                components = []  # No type annotation

            print(f"✓ Extracted {len(components)} components")

            # Phase 2: Extract materials - NEW debate integration
            if use_material_debate:
                from ..debate import MaterialDebater

                print("Using multi-agent debate for materials...")
                material_debater = MaterialDebater(
                    deps=self.deps,
                    num_agents=3,
                    max_rounds=self.max_debate_rounds,
                    convergence_threshold=self.convergence_threshold,
                    debate_top_p=self.debate_top_p,
                )

                debate_result = await material_debater.run_full_debate(components, tech, usage)

                # Convert debate consensus to ComponentMaterialsList format
                from ..agents import ComponentMaterials, ComponentMaterialsList

                consensus = debate_result["consensus"]  # Dict[str, List[str]]

                # Build ComponentMaterialsList using ALIASES in constructor
                materials_list = ComponentMaterialsList(
                    componentlist=[  # Use alias (NO underscore) for constructor
                        ComponentMaterials(
                            component=comp,
                            materials=mats,  # Use alias "materials" (NO underscore)
                        )
                        for comp, mats in consensus.items()
                    ]
                )

                # Save material debate transcript if enabled
                if self.save_transcripts and self.reporter:
                    self._save_material_debate_transcript(
                        tech, components, material_debater.debate_history, consensus
                    )
            else:
                # Existing single-agent extraction
                from ..agents import ComponentList

                if isinstance(components, ComponentList):
                    components_list = components.component_list
                else:
                    components_list = components

                materials_result = await self.extract_materials_safe(
                    componentlist=ComponentList(
                        componentlist=components_list
                    ),  # Now definitely List[str]
                    technology=tech,
                    usage=usage,
                )

                if (
                    not materials_result or not materials_result.component_list
                ):  # Use field name for access
                    logger.error(f"No materials extracted for {tech}")
                    print(f"✗ No materials extracted for {tech}")
                    return None

                materials_list = materials_result

            if not materials_list or not materials_list.component_list:  # Use field name for access
                logger.error(f"No materials extracted for {tech}")
                print(f"✗ No materials extracted for {tech}")
                return None

            print(f"✓ Extracted materials for {len(materials_list.component_list)} components")

            # Phase 3: Enrich with country data (existing logic continues unchanged)
            enriched_data = []

            for comp_mat in materials_list.component_list:  # Use field name for access
                component = comp_mat.component

                for material in comp_mat.raw_materials:  # Use field name for access
                    try:
                        country_data = await self.country_repo.get_country_data(
                            material=material,
                            src_year=getattr(self.config, "src_year", 2024),
                            meas_year=getattr(self.config, "meas_year", 2025),
                            usage=usage,
                        )

                        if country_data:
                            for country_info in country_data:
                                enriched_data.append(
                                    {
                                        "technology": tech,
                                        "component": component,
                                        "material": material,
                                        "hs_code": country_info.get("hs_code"),
                                        "country": country_info.get(
                                            "country", "Unknown"
                                        ),  # Use .get() for safety
                                        "meas_unit": country_info.get(
                                            "meas_unit", ""
                                        ),  # Use .get() for safety
                                        "amount": country_info.get(
                                            "amount", 0.0
                                        ),  # Use .get() for safety
                                        "percentage": country_info.get(
                                            "percentage", 0.0
                                        ),  # Use .get() for safety
                                    }
                                )
                        elif self.write_nulls:
                            enriched_data.append(
                                {
                                    "technology": tech,
                                    "component": component,
                                    "material": material,
                                    "hs_code": None,  # WITH underscore ✓
                                    "country": None,
                                    "meas_unit": None,  # WITH underscore ✓
                                    "amount": None,
                                    "percentage": None,
                                }
                            )

                    except Exception as e:
                        logger.error(f"Error getting country data for {material}: {e}")

            return {
                "technology": tech,
                "components": components,
                "materials": materials_list,
                "enriched_data": enriched_data,
            }

        except Exception as e:
            logger.error(f"Error processing technology {tech}: {e}", exc_info=True)
            print(f"✗ Error processing {tech}: {e}")
            return None

    def _build_material_transcript_content(
        self,
        components: list[str],
        debate_history: list,
        consensus: dict[str, list[str]],
    ) -> str:
        """Build the materials debate transcript content."""
        content = []

        content.append("\n\n")
        content.append("=" * 80 + "\n")
        content.append("MATERIALS EXTRACTION DEBATE\n")
        content.append("=" * 80 + "\n\n")

        # Phase 1: Components
        content.append("COMPONENTS PROCESSED:\n")
        content.append("-" * 80 + "\n")
        content.append(f"Total Components: {len(components)}\n")
        for comp in components:
            content.append(f"  - {comp}\n")
        content.append("\n")

        # Phase 2: Debate Rounds
        content.append("=" * 80 + "\n")
        content.append("MATERIAL DEBATE ROUNDS\n")
        content.append("=" * 80 + "\n\n")

        for round_data in debate_history:
            content.append(f"ROUND {round_data.roundnumber}:\n")
            content.append(f"  Convergence: {round_data.convergencescore:.1%}\n")

            if round_data.critiques:
                content.append(f"  Critiques ({len(round_data.critiques)} total):\n")
                # critiques is a dict, so iterate over values
                critique_list = (
                    list(round_data.critiques.values())
                    if isinstance(round_data.critiques, dict)
                    else round_data.critiques
                )
                # Show first 3 critiques
                for critique in critique_list[:3]:
                    content.append(f"    - {critique}\n")
                if len(critique_list) > 3:
                    content.append(f"    ... and {len(critique_list) - 3} more\n")

            if round_data.consensussofar:
                content.append(f"  Consensus materials: {len(round_data.consensussofar)}\n")

            content.append("\n")

        # Phase 3: Final Consensus
        content.append("=" * 80 + "\n")
        content.append("FINAL MATERIAL ASSIGNMENTS\n")
        content.append("=" * 80 + "\n\n")

        total_materials = sum(len(mats) for mats in consensus.values())
        unique_materials = len({mat for mats in consensus.values() for mat in mats})

        content.append(f"Components: {len(consensus)}\n")
        content.append(f"Unique Materials: {unique_materials}\n")
        content.append(f"Total Assignments: {total_materials}\n\n")

        content.append("Materials by Component:\n")
        content.append("-" * 80 + "\n")

        for component, materials in sorted(consensus.items()):
            mat_list = ", ".join(sorted(materials))
            content.append(f"  ✓ {component}: {mat_list}\n")

        content.append("\n" + "=" * 80 + "\n")
        content.append("END OF COMBINED TRANSCRIPT\n")
        content.append("=" * 80 + "\n")

        return "".join(content)

    def _save_material_debate_transcript(
        self,
        technology: str,
        components: list[str],
        debate_history: list,
        consensus: dict[str, list[str]],
    ) -> None:
        """Append material debate results to existing component transcript."""
        print(f"🔍 DEBUG: Attempting to save material transcript for {technology}")
        print(f"🔍 DEBUG: Components: {len(components)}, Consensus: {len(consensus)}")

        if not self.reporter:
            print("❌ Reporter is None, cannot save transcript")
            return

        try:
            output_dir = Path(self.reporter.output_dir)

            # Find most recent component transcript
            component_transcripts = list(output_dir.glob(f"{technology}_*.txt"))
            component_transcripts = [f for f in component_transcripts if "_materials" not in f.name]

            if not component_transcripts:
                logger.warning(f"No component transcript found for {technology}")
                return

            filepath = max(component_transcripts, key=lambda p: p.stat().st_mtime)

            # Build and write content
            materials_content = self._build_material_transcript_content(
                components, debate_history, consensus
            )

            with open(filepath, "a", encoding="utf-8") as f:
                f.write(materials_content)
                f.flush()

            # Update JSON
            json_path = filepath.with_suffix(".json")
            if json_path.exists():
                self._update_material_json(json_path, debate_history, consensus)

            print(f"✓ Appended material debate to: {filepath.name}")

        except Exception as e:
            logger.error(f"Error appending material debate transcript: {e}", exc_info=True)
            print(f"❌ EXCEPTION appending materials transcript: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()  # Print full stack trace

    def _update_material_json(
        self,
        json_path: Path,
        debate_history: list,
        consensus: dict[str, list[str]],
    ) -> None:
        """Update JSON transcript with materials data."""
        import json

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        total_materials = sum(len(mats) for mats in consensus.values())
        unique_materials = len({mat for mats in consensus.values() for mat in mats})

        data["materials_debate"] = {
            "debate_rounds": [
                {
                    "round_number": r.roundnumber,
                    "convergence_score": r.convergencescore,
                    "num_critiques": len(r.critiques),
                }
                for r in debate_history
            ],
            "final_consensus": {
                "components": len(consensus),
                "unique_materials": unique_materials,
                "total_assignments": total_materials,
                "materials_by_component": consensus,
            },
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()

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
            print("🎤 Multi-agent debate ENABLED:")
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
                    "hs_code",
                    "country",
                    "meas_unit",
                    "amount",
                    "percentage",
                ],
            )
            writer.writeheader()

        # Process each technology
        for tech in technologies:
            result = await self.process_technology(
                tech, role, domain, usage, use_material_debate=self.use_material_debate
            )

            if result and result["enriched_data"]:
                # Write results to CSV
                with open(self.output_file, "a", newline="") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "technology",
                            "component",
                            "material",
                            "hs_code",
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
