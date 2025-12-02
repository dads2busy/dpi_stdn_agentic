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
- Dynamic confidence scoring for all components
- Detailed logging and progress reporting
"""

import asyncio
import csv
import json
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
        enable_country_debate: bool = False,
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
            enable_material_debate: Use debate for materials extraction
            enable_country_debate: Use debate for country data
            max_debate_rounds: Max debate rounds
            convergence_threshold: Convergence threshold
            save_transcripts: Save debate transcripts
            debate_top_p: Top-p sampling parameter for debate
        """
        self.config = config

        os.environ["STDN_MODEL"] = config.model

        self.enable_checkpoints = enable_checkpoints
        self.use_debate = enable_debate
        self.use_material_debate = enable_material_debate
        self.use_country_debate = enable_country_debate
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

    def _validate_materials_extraction_inputs(
        self,
        componentlist: ComponentList,
        technology: str,
    ) -> tuple[bool, Optional[list[str]], Optional[str]]:
        """
        Validate inputs for materials extraction.

        Returns:
            Tuple of (is_valid, valid_component_names, error_message)
        """
        # Check component list exists
        if not componentlist or not hasattr(componentlist, "component_list"):
            logger.warning(f"No components to extract materials from for {technology}")
            print("🔍 No components to extract materials from")
            return (False, None, "No components")

        components = componentlist.component_list

        # Filter valid components and extract names
        # Components are now ComponentWithConfidence objects
        valid_component_names = [
            c.name for c in components if c and hasattr(c, "name") and c.name.strip()
        ]

        if not valid_component_names:
            logger.warning(f"All components were null/empty for {technology}")
            print("🔍 All components were null/empty")
            return (False, None, "All components null/empty")

        # Check ontology availability
        if not self.deps.material_ontology_list or len(self.deps.material_ontology_list) == 0:
            logger.error(f"Material ontology is empty - cannot extract materials for {technology}")
            print("❌ Material ontology is empty!")
            return (False, None, "Ontology empty")

        return (True, valid_component_names, None)

    async def extract_materials_safe(
        self,
        componentlist: ComponentList,
        technology: str,
        usage: RunUsage,
        max_retries: int = 5,
    ) -> Optional[ComponentMaterialsList]:
        """
        Safely extract materials with comprehensive error handling and retry logic.
        Materials are strictly constrained to the ontology list from hs_codes_and_usgs_names.csv
        """
        # Check ontology availability
        is_valid, valid_component_names, error_msg = (
            self._validate_materials_extraction_inputs(  # ✅ FIXED
                componentlist, technology
            )
        )
        if not is_valid:
            return ComponentMaterialsList.model_validate({"componentlist": []})

        assert valid_component_names, (
            "valid_component_names should be non-empty after successful validation"
        )

        component_str = "\n".join(f"- {comp}" for comp in valid_component_names)

        # Use FULL ontology for strict matching (not just 50 samples)
        ontology_str = "\n".join(f"  - {mat}" for mat in self.deps.material_ontology_list)

        # Stricter prompt - no "common variants" allowed
        materials_prompt = f"""Extract RAW MATERIALS for these components of a {technology}:

    {component_str}

    STRICT CONSTRAINT - You MUST ONLY select materials from this exact list:
    {ontology_str}

    RULES:
    1. Use ONLY material names from the above list (exact matches required)
    2. Do NOT use synonyms, abbreviations, or variations
    3. Do NOT invent new materials or use brand names
    4. Do NOT use manufactured products (e.g., "EVA", "PET film") - use base materials instead
    5. If unsure, choose the closest base material from the list

    EXAMPLES OF CORRECT USAGE:
    ✓ Use "Silicon" not "Monocrystalline silicon"
    ✓ Use "Aluminum" not "Aluminum alloy" or "6061 aluminum"
    ✓ Use "Polyethylene terephthalate" not "PET" or "Polyester film"
    ✓ Use "Glass" not "Borosilicate glass" (unless "Borosilicate glass" is in the list)
    ✓ Use "Copper" not "Copper wire"

    For each component, identify 2-8 key RAW MATERIALS from the list above.

    Return a JSON response with componentlist containing component and materials fields.
    Use ONLY materials from the provided list above.
    """

        logger.info(
            f"Extracting materials for {len(valid_component_names)} components of {technology}"
        )
        print(f"Extracting materials for {len(valid_component_names)} components...")

        for attempt in range(max_retries):
            try:
                result = await self.materials_agent.run(
                    materials_prompt, deps=self.deps
                )  # ✅ FIXED

                if not result or not result.output:
                    if attempt == max_retries - 1:
                        await asyncio.sleep(2**attempt)
                    continue
                    return ComponentMaterialsList.model_validate({"componentlist": []})

                materials_list = result.output

                if not materials_list.component_list:
                    if attempt == max_retries - 1:
                        await asyncio.sleep(2**attempt)
                    continue
                    return ComponentMaterialsList.model_validate({"componentlist": []})

                # Post-extraction filtering: Remove materials not in ontology
                ontology_set = set(self.deps.material_ontology_list)
                filtered_count = 0

                for comp_mat in materials_list.component_list:
                    filtered_materials = []
                    for mat in comp_mat.raw_materials:
                        if mat.name in ontology_set:
                            filtered_materials.append(mat)
                        else:
                            logger.warning(
                                f"Material '{mat.name}' for component '{comp_mat.component}' "
                                f"not in ontology, filtering out"
                            )
                            print(f"  ⚠️  Filtered out '{mat.name}' (not in ontology)")
                            filtered_count += 1
                    comp_mat.raw_materials = filtered_materials

                if filtered_count > 0:
                    print(f"  ℹ️  Filtered {filtered_count} materials not in ontology")

                num_materials = sum(len(cm.raw_materials) for cm in materials_list.component_list)
                logger.info(
                    f"Extracted {num_materials} materials for {len(materials_list.component_list)} components"
                )
                print(f"Extracted materials for {len(materials_list.component_list)} components")

                return materials_list

            except Exception as e:
                error_str = str(e)
                is_transient = "invalid message content type" in error_str or "400" in error_str
                if is_transient and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                    logger.warning(f"Transient error (attempt {attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Error extracting materials: {e}", exc_info=True)
                    return ComponentMaterialsList.model_validate({"componentlist": []})

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

            # Create short version for console output
            perspective_short = perspective.replace("Focus on ", "").replace("identifying ", "")

            try:
                # Create deps with very low Top-P for focused outputs
                from dataclasses import replace
                from typing import cast

                from ..agents.component_agent import ComponentWithConfidence

                agent_deps = replace(self.deps, top_p=self.debate_top_p)

                # Each agent uses the CSV role with their specific perspective
                result = await self.component_agent.run(
                    f"You are a {role} analyzing {technology}. "
                    f"{perspective}. "
                    f"Extract the primary manufacturing components from this analytical perspective.",
                    deps=agent_deps,
                )

                if result and result.output:
                    components = (
                        result.output.component_list
                        if hasattr(result.output, "component_list")
                        else result.output
                    )

                    # Capture tech spec from first agent
                    if agent_num == 1:
                        if hasattr(result.output, "technology_specification"):
                            technology_specification = result.output.technology_specification
                            print(f"✓ Captured tech spec: {technology_specification}")
                        if hasattr(result.output, "technology_reasoning"):
                            technology_reasoning = result.output.technology_reasoning
                            print(f"✓ Captured tech reasoning: {technology_reasoning[:100]}...")

                    # Cast to tell type checker this is a list of ComponentWithConfidence
                    components_typed = cast(list[ComponentWithConfidence], components)

                    # Extract dynamic confidence from ComponentWithConfidence objects
                    agent_proposals[agent_id] = [
                        {
                            "component": comp.name,
                            "confidence": comp.confidence,  # Dynamic from LLM
                            "reasoning": comp.reasoning,
                        }
                        for comp in components_typed
                    ]

                    # Calculate average confidence for reporting
                    avg_conf = sum(p["confidence"] for p in agent_proposals[agent_id]) / len(
                        agent_proposals[agent_id]
                    )

                    # Show role and component count
                    print(
                        f"  ✓ {agent_id} ({role}): {len(components_typed)} components proposed (avg confidence: {avg_conf:.2f})"
                    )
                    # Show actual perspective on next line
                    print(f"     → {perspective_short}")

                    # Store for transcript with role + perspective
                    agent_responses_for_transcript.append(
                        {
                            "agent_id": agent_id,
                            "components": agent_proposals[agent_id],
                            "persona": f"{role} - {perspective}",
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

        # Add tech spec to debate_result BEFORE saving transcript
        debate_result["technology_specification"] = technology_specification
        debate_result["technology_reasoning"] = technology_reasoning
        print(f"✓ Injected tech spec into debate_result: {technology_specification}")

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

        # Extract final components and details from debate result
        final_component_names = debate_result.get("components", [])
        component_details = debate_result.get("component_details", {})

        # Debug output
        print(f"\n🔍 Debug - Consensus type: {type(debate_result)}")
        print(f"🔍 Debug - Consensus keys: {list(debate_result.keys())}")
        print(f"📊 Final consensus components: {final_component_names}")

        print(f"\n🔍 Component details from debate:")
        for norm_name, details in component_details.items():
            print(f"  {norm_name} → {details['original_name']} (conf: {details['confidence']:.2f})")

        if not final_component_names:
            logger.warning(f"Debate produced no consensus components for {technology}")
            return None

        # Create ComponentWithConfidence objects using debate-provided details
        from ..agents import ComponentWithConfidence

        final_components_with_confidence = []
        for norm_name in final_component_names:
            if norm_name in component_details:
                details = component_details[norm_name]
                final_components_with_confidence.append(
                    ComponentWithConfidence(
                        name=details["original_name"],
                        confidence=details["confidence"],
                        reasoning=details["reasoning"],
                    )
                )
            else:
                # Fallback (should never happen now that debate returns details)
                print(f"  ⚠️  No details found for '{norm_name}', using fallback")
                final_components_with_confidence.append(
                    ComponentWithConfidence(
                        name=norm_name.title(),
                        confidence=0.75,
                        reasoning="Consensus component from multi-agent debate",
                    )
                )

        print(f"✓ Created {len(final_components_with_confidence)} ComponentWithConfidence objects")

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

            # ✅✅✅ EXTRACT TECH SPEC FROM debate_result ✅✅✅
            technology_specification = debate_result.get("technology_specification", technology)
            technology_reasoning = debate_result.get("technology_reasoning", "")

            # ✅ DEBUG PRINTS
            print(f"✓ Passing to reporter - Tech spec: {technology_specification}")
            print(
                f"✓ Passing to reporter - Tech reasoning: {technology_reasoning[:100] if technology_reasoning else 'None'}..."
            )

            # Build final consensus dict with proper metadata
            final_consensus = {
                "technology": technology,
                "technology_specification": technology_specification,  # ✅✅✅ ADD THIS
                "technology_reasoning": technology_reasoning,  # ✅✅✅ ADD THIS
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

    async def _extract_materials_for_technology(
        self,
        components: list[str],
        technology: str,
        usage: RunUsage,
    ) -> Optional[ComponentMaterialsList]:
        """
        Extract materials for components using debate or single-agent approach.

        Args:
            components: List of component names (already normalized strings)
            technology: Technology name
            usage: RunUsage tracker

        Returns:
            ComponentMaterialsList with MaterialWithConfidence objects, or None if extraction fails
        """
        if self.use_material_debate:
            from ..agents import ComponentMaterials, ComponentMaterialsList
            from ..agents.materials_agent import MaterialWithConfidence
            from ..debate import MaterialDebater

            print("Using multi-agent debate for materials...")
            material_debater = MaterialDebater(
                deps=self.deps,
                num_agents=3,
                max_rounds=self.max_debate_rounds,
                convergence_threshold=self.convergence_threshold,
                debate_top_p=self.debate_top_p,
            )

            debate_result = await material_debater.run_full_debate(components, technology, usage)

            # Convert debate consensus to ComponentMaterialsList format
            # consensus is now: {component: [{"name": ..., "confidence": ..., "reasoning": ...}]}
            consensus = debate_result["consensus"]

            # Build material confidence map from debate proposals
            material_confidence_map = {}

            if hasattr(material_debater, "debate_history") and material_debater.debate_history:
                # Get all proposals from all rounds (prioritize later rounds)
                all_proposals = []
                for debate_round in material_debater.debate_history:
                    all_proposals.extend(debate_round.proposals)

                # Build map: component|material -> confidence data
                for prop in all_proposals:
                    mat_key = f"{prop.normalizedcomponent}|{prop.normalizedmaterial}"
                    # Keep highest confidence for each material
                    if (
                        mat_key not in material_confidence_map
                        or prop.confidence > material_confidence_map[mat_key]["confidence"]
                    ):
                        material_confidence_map[mat_key] = {
                            "name": prop.material,  # Original name
                            "confidence": prop.confidence,
                            "reasoning": prop.reasoning,
                        }

            # Convert consensus dicts to MaterialWithConfidence objects
            materials_list_items = []

            for comp, material_dicts in consensus.items():
                # comp is already normalized from component phase
                material_objects = []

                for mat_dict in material_dicts:
                    # Extract data from dict
                    mat_name = mat_dict["name"]
                    mat_confidence = mat_dict.get("confidence", 0.75)
                    mat_reasoning = mat_dict.get(
                        "reasoning", "Consensus material from multi-agent debate"
                    )

                    # Normalize material name for lookup
                    mat_norm = material_debater.normalize_material_name(mat_name)
                    mat_key = f"{comp}|{mat_norm}"

                    # Look up confidence from debate proposals (may have higher confidence)
                    if mat_key in material_confidence_map:
                        mat_info = material_confidence_map[mat_key]
                        material_objects.append(
                            MaterialWithConfidence(
                                name=mat_info["name"],
                                confidence=mat_info["confidence"],
                                reasoning=mat_info["reasoning"],
                            )
                        )
                    else:
                        # Use confidence from consensus dict
                        material_objects.append(
                            MaterialWithConfidence(
                                name=mat_name,
                                confidence=mat_confidence,
                                reasoning=mat_reasoning,
                            )
                        )

                materials_list_items.append(
                    ComponentMaterials(component=comp, materials=material_objects)
                )

            materials_list = ComponentMaterialsList(componentlist=materials_list_items)

            # Save material debate transcript if enabled
            if self.save_transcripts and self.reporter:
                self._save_material_debate_transcript(
                    technology, components, material_debater.debate_history, consensus
                )

        else:
            # Single-agent extraction (already returns MaterialWithConfidence objects)
            from ..agents import ComponentList
            from ..agents.component_agent import ComponentWithConfidence

            # Convert string components to ComponentWithConfidence objects
            component_objects = [
                ComponentWithConfidence(
                    name=comp,
                    confidence=0.8,  # Default for single-agent
                    reasoning="Single-agent component extraction",
                )
                for comp in components
            ]

            materials_result = await self.extract_materials_safe(
                componentlist=ComponentList(
                    componentlist=component_objects,
                    technology_specification=technology,  # ← ADD THIS
                    technology_reasoning="Single-agent component extraction without debate",  # ← ADD THIS
                ),
                technology=technology,
                usage=usage,
            )

            if not materials_result or not materials_result.component_list:
                return None

            materials_list = materials_result

        return materials_list

    async def _enrich_with_country_data(
        self,
        materials_list: ComponentMaterialsList,
        technology: str,
        usage: RunUsage,
        transcript_path: Optional[Path] = None,
        component_confidence_map: Optional[dict] = None,
    ) -> list[dict[str, Any]]:
        """
        Enrich materials with country production data including confidence scores and reasoning.

        Args:
            materials_list: Materials for each component
            technology: Technology name
            usage: Usage tracker
            transcript_path: Optional transcript path
            component_confidence_map: Dict mapping component names to confidence/reasoning

        Returns:
            List of enriched data records with confidence and reasoning columns
        """
        enriched_data = []

        # Default to empty dict if not provided
        if component_confidence_map is None:
            component_confidence_map = {}

        for comp_mat in materials_list.component_list:
            component = comp_mat.component

            # Get component confidence and reasoning from the map
            comp_info = component_confidence_map.get(component, {})
            component_confidence = comp_info.get("confidence", 0.0)
            component_reasoning = comp_info.get("reasoning", "")

            # Access raw_materials - should be a list of MaterialWithConfidence objects
            raw_materials = comp_mat.raw_materials

            # Ensure it's a list (not an iterator or generator)
            if not isinstance(raw_materials, list):
                raw_materials = list(raw_materials)

            for material in raw_materials:
                # Extract material name, confidence, and reasoning based on type
                if hasattr(material, "name") and hasattr(material, "confidence"):
                    # It's a MaterialWithConfidence object
                    material_name = material.name
                    material_confidence = material.confidence
                    material_reasoning = getattr(material, "reasoning", "")
                elif isinstance(material, dict):
                    # It's a dictionary (shouldn't happen but handle it)
                    material_name = material.get("name", str(material))
                    material_confidence = material.get("confidence", 0.0)
                    material_reasoning = material.get("reasoning", "")
                elif isinstance(material, str):
                    # It's a plain string (legacy format)
                    material_name = material
                    material_confidence = 0.0
                    material_reasoning = ""
                else:
                    # Unknown type - convert to string and log warning
                    material_name = str(material)
                    material_confidence = 0.0
                    material_reasoning = ""
                    logger.warning(f"Unexpected material type for {component}: {type(material)}")

                # Skip empty material names
                if not material_name or not material_name.strip():
                    continue

                try:
                    # Query country data repository
                    country_data = await self.country_repo.get_country_data(
                        material=material_name,
                        src_year=getattr(self.config, "src_year", 2024),
                        meas_year=getattr(self.config, "meas_year", 2025),
                        usage=usage,
                        use_debate=self.use_country_debate,
                        transcript_path=transcript_path,
                    )

                    if country_data:
                        # We have country data - create records with confidence and reasoning
                        for country_info in country_data:
                            enriched_data.append(
                                {
                                    "technology": technology,
                                    "component": component,
                                    "component_confidence": round(component_confidence, 3),
                                    "component_reasoning": component_reasoning,  # ← ADDED
                                    "material": material_name,
                                    "material_confidence": round(material_confidence, 3),
                                    "material_reasoning": material_reasoning,  # ← ADDED
                                    "hs_code": country_info.get("hs_code"),
                                    "country": country_info.get("country", "Unknown"),
                                    "meas_unit": country_info.get("meas_unit", ""),
                                    "amount": country_info.get("amount", 0.0),
                                    "percentage": round(country_info.get("percentage", 0.0), 2),
                                    "country_confidence": round(
                                        country_info.get("confidence", 0.0), 3
                                    ),
                                    "country_reasoning": country_info.get(
                                        "reasoning", ""
                                    ),  # ← ADDED
                                }
                            )
                    elif self.write_nulls:
                        # No country data found - write null record if enabled
                        enriched_data.append(
                            {
                                "technology": technology,
                                "component": component,
                                "component_confidence": round(component_confidence, 3),
                                "component_reasoning": component_reasoning,  # ← ADDED
                                "material": material_name,
                                "material_confidence": round(material_confidence, 3),
                                "material_reasoning": material_reasoning,  # ← ADDED
                                "hs_code": None,
                                "country": None,
                                "meas_unit": None,
                                "amount": None,
                                "percentage": None,
                                "country_confidence": None,
                                "country_reasoning": None,  # ← ADDED
                            }
                        )
                    else:
                        # No data and not writing nulls - log it
                        logger.info(
                            f"No country data for {material_name}, skipping (write_nulls=False)"
                        )

                except Exception as e:
                    logger.error(
                        f"Error getting country data for {material_name} in {component}: {e}",
                        exc_info=True,
                    )
                    # Optionally write error record if write_nulls enabled
                    if self.write_nulls:
                        enriched_data.append(
                            {
                                "technology": technology,
                                "component": component,
                                "component_confidence": round(component_confidence, 3),
                                "component_reasoning": component_reasoning,  # ← ADDED
                                "material": material_name,
                                "material_confidence": round(material_confidence, 3),
                                "material_reasoning": material_reasoning,  # ← ADDED
                                "hs_code": None,
                                "country": None,
                                "meas_unit": None,
                                "amount": None,
                                "percentage": None,
                                "country_confidence": None,
                                "country_reasoning": None,  # ← ADDED
                            }
                        )

        return enriched_data

    async def process_technology(
        self,
        tech: str,
        role: str,
        domain: str,
        usage: RunUsage,
        use_material_debate: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Process a single technology through the complete STDN pipeline."""
        print("=" * 80)
        print(f"Processing: {tech}")
        print("=" * 80)

        try:
            # Phase 1: Extract components
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

            # Import for type checking
            from typing import cast

            from ..agents.component_agent import ComponentWithConfidence

            # Extract component names and preserve full objects for potential transcript use
            if hasattr(components_result, "component_list"):
                # components_result.component_list now contains ComponentWithConfidence objects
                # Use cast to tell type checker what type this is
                component_objects = cast(
                    list[ComponentWithConfidence], components_result.component_list
                )
                components: list[str] = [comp.name for comp in component_objects]

                # Build component confidence map for enrichment phase
                component_confidence_map: dict[str, dict[str, Any]] = {}
                for comp in component_objects:
                    component_confidence_map[comp.name] = {
                        "confidence": comp.confidence,
                        "reasoning": comp.reasoning,
                    }

                # Calculate and log average confidence
                if component_objects:
                    avg_confidence = sum(comp.confidence for comp in component_objects) / len(
                        component_objects
                    )
                    print(
                        f"✓ Extracted {len(components)} components (avg confidence: {avg_confidence:.2f})"
                    )
                else:
                    print(f"✓ Extracted {len(components)} components")
            elif isinstance(components_result, list):
                # Handle case where result is already a list
                if components_result and hasattr(components_result[0], "name"):
                    component_objects = cast(list[ComponentWithConfidence], components_result)
                    components = [comp.name for comp in component_objects]

                    component_confidence_map = {
                        comp.name: {"confidence": comp.confidence, "reasoning": comp.reasoning}
                        for comp in component_objects
                    }
                else:
                    component_objects = []
                    components = components_result
                    component_confidence_map = {}
                print(f"✓ Extracted {len(components)} components")
            else:
                components = []
                component_objects = []
                component_confidence_map = {}
                print(f"✓ Extracted {len(components)} components")

            # Phase 2: Extract materials
            materials_list = await self._extract_materials_for_technology(components, tech, usage)

            if not materials_list or not materials_list.component_list:
                logger.error(f"No materials extracted for {tech}")
                print(f"✗ No materials extracted for {tech}")
                return None

            print(f"✓ Extracted materials for {len(materials_list.component_list)} components")

            # Get transcript path AFTER materials are extracted (so transcript exists)
            transcript_path = None
            if self.save_transcripts and self.reporter:
                transcripts = list(self.reporter.output_dir.glob(f"{tech}_*.txt"))
                if transcripts:
                    transcript_path = max(transcripts, key=lambda p: p.stat().st_mtime)

            # Phase 3: Enrich with country data (pass component_confidence_map)
            enriched_data = await self._enrich_with_country_data(
                materials_list,
                tech,
                usage,
                transcript_path=transcript_path,
                component_confidence_map=component_confidence_map,  # ← PASS THIS
            )

            if self.save_transcripts and self.reporter and enriched_data:
                self._append_country_data_to_transcript(tech, enriched_data)

            return {
                "technology": tech,
                "components": components,
                "component_objects": component_objects,  # Preserve for transcript
                "materials": materials_list,
                "enriched_data": enriched_data,
            }

        except Exception as e:
            logger.error(f"Error processing technology {tech}: {e}", exc_info=True)
            print(f"✗ Error processing {tech}: {e}")
            return None

    def _build_material_transcript_content(
        self,
        components: list,  # Can accept ComponentWithConfidence or str
        debate_history: list,
        consensus: dict[str, list[dict]],  # list[dict] with name, confidence, reasoning
    ) -> str:
        """Build the materials debate transcript content with confidence and reasoning."""
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
            # Handle both ComponentWithConfidence objects and strings
            if hasattr(comp, "name"):
                content.append(f"  - {comp.name} (confidence: {comp.confidence:.2f})\n")
                if hasattr(comp, "reasoning") and comp.reasoning:
                    content.append(f"    → {comp.reasoning}\n")  # ✅ ADD COMPONENT REASONING
            else:
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

        # Phase 3: Final Consensus WITH REASONING
        content.append("=" * 80 + "\n")
        content.append("FINAL MATERIAL ASSIGNMENTS\n")
        content.append("=" * 80 + "\n\n")

        # Extract material names from dicts
        total_materials = sum(len(mats) for mats in consensus.values())
        unique_materials = len(
            {mat_dict["name"] for mats in consensus.values() for mat_dict in mats}
        )

        content.append(f"Components: {len(consensus)}\n")
        content.append(f"Unique Materials: {unique_materials}\n")
        content.append(f"Total Assignments: {total_materials}\n\n")

        content.append("Materials by Component:\n")
        content.append("-" * 80 + "\n\n")

        for component, material_dicts in sorted(consensus.items()):
            content.append(f"{component}:\n")

            # Sort materials by confidence (highest first), then by name
            sorted_materials = sorted(
                material_dicts,
                key=lambda m: (-m.get("confidence", 0.0), m.get("name", "")),
            )

            for mat_dict in sorted_materials:
                name = mat_dict.get("name", "Unknown")
                confidence = mat_dict.get("confidence", 0.0)
                reasoning = mat_dict.get("reasoning", "")

                # Material name and confidence
                content.append(f"  • {name} (confidence: {confidence:.2f})\n")

                # Material reasoning (indented)
                if reasoning:
                    content.append(f"    → {reasoning}\n")

            content.append("\n")  # Blank line between components

        content.append("=" * 80 + "\n")
        content.append("END OF COMBINED TRANSCRIPT\n")
        content.append("=" * 80 + "\n")

        return "".join(content)

    def _save_material_debate_transcript(
        self,
        technology: str,
        components: list,  # Can be strings or ComponentWithConfidence
        debate_history: list,
        consensus: dict[str, list[dict]],
    ) -> None:
        """Append material debate results to existing component transcript."""
        print(f"🔍 DEBUG: Attempting to save material transcript for {technology}")
        print(f"🔍 DEBUG: Components: {len(components)}, Consensus: {len(consensus)}")

        if not self.reporter:
            print("❌ Reporter is None, cannot save transcript")
            return

        try:
            output_dir = Path(self.reporter.output_dir)

            # ✅ FIX: Replace spaces with underscores to match filename format
            tech_filename = technology.replace(" ", "_")

            # Find most recent component transcript
            component_transcripts = list(output_dir.glob(f"{tech_filename}_*.txt"))  # ✅ FIXED
            component_transcripts = [f for f in component_transcripts if "_materials" not in f.name]

            print(f"🔍 DEBUG: Looking for: {tech_filename}_*.txt")  # ✅ ADD
            print(f"🔍 DEBUG: Found {len(component_transcripts)} component transcripts")  # ✅ ADD

            if not component_transcripts:
                logger.warning(f"No component transcript found for {technology}")
                print(f"❌ No component transcript found in {output_dir}")  # ✅ ADD
                return

            filepath = max(component_transcripts, key=lambda p: p.stat().st_mtime)
            print(f"🔍 DEBUG: Will append to: {filepath.name}")  # ✅ ADD

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

            traceback.print_exc()

    def _update_material_json(
        self,
        json_path: Path,
        debate_history: list,
        consensus: dict[str, list[dict]],
    ) -> None:
        """Update JSON transcript with materials data."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        total_materials = sum(len(mats) for mats in consensus.values())
        unique_materials = len({mat["name"] for mats in consensus.values() for mat in mats})

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

    def _append_country_data_to_transcript(
        self,
        technology: str,
        enriched_data: list[dict[str, Any]],
    ) -> None:
        """Append country production data to existing transcript."""

        if not self.reporter:
            print("❌ Reporter is None, cannot append country data")
            return

        if not enriched_data:
            print("⚠️  No enriched data to append")
            return

        try:
            output_dir = Path(self.reporter.output_dir)

            # Find most recent transcript for this technology
            tech_filename = technology.replace(" ", "_")
            transcripts = list(output_dir.glob(f"{tech_filename}_*.txt"))

            if not transcripts:
                logger.warning(f"No transcript found for {technology}")
                print(f"❌ No transcript found for {technology}")
                return

            filepath = max(transcripts, key=lambda p: p.stat().st_mtime)
            print(f"🔍 DEBUG: Appending country data to: {filepath.name}")

            # Build country data section
            content = []
            content.append("\n\n")
            content.append("=" * 80 + "\n")
            content.append("COUNTRY PRODUCTION DATA\n")
            content.append("=" * 80 + "\n\n")

            # Group by component -> material -> countries
            from collections import defaultdict

            comp_mat_countries = defaultdict(lambda: defaultdict(list))

            for row in enriched_data:
                comp = row.get("component", "")
                mat = row.get("material", "")
                country = row.get("country", "")
                if comp and mat and country:
                    comp_mat_countries[comp][mat].append(row)

            content.append(f"Total Components: {len(comp_mat_countries)}\n")
            total_materials = sum(len(mats) for mats in comp_mat_countries.values())
            content.append(f"Total Materials: {total_materials}\n")
            total_countries = len(enriched_data)
            content.append(f"Total Country Records: {total_countries}\n\n")

            content.append("Production Data by Component:\n")
            content.append("-" * 80 + "\n\n")

            # Write organized output
            for comp in sorted(comp_mat_countries.keys()):
                materials = comp_mat_countries[comp]
                content.append(f"{comp}:\n")

                for mat in sorted(materials.keys()):
                    countries = materials[mat]
                    content.append(f"  {mat}:\n")

                    # Sort countries by percentage (highest first)
                    countries_sorted = sorted(
                        countries, key=lambda x: x.get("percentage", 0.0), reverse=True
                    )

                    for country_data in countries_sorted:
                        country = country_data.get("country", "Unknown")
                        percentage = country_data.get("percentage", 0.0)
                        confidence = country_data.get("country_confidence", 0.0)
                        reasoning = country_data.get("country_reasoning", "")

                        content.append(f"    • {country}: {percentage:.1f}%")
                        if confidence:
                            content.append(f" (confidence: {confidence:.2f})")
                        content.append("\n")

                        if reasoning:
                            # Truncate long reasoning
                            reasoning_display = (
                                reasoning[:150] + "..." if len(reasoning) > 150 else reasoning
                            )
                            content.append(f"      → {reasoning_display}\n")

                    content.append("\n")

            content.append("=" * 80 + "\n")
            content.append("END OF STDN TRANSCRIPT\n")
            content.append("=" * 80 + "\n")

            # Append to file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("".join(content))
                f.flush()

            print(f"✓ Appended country data to: {filepath.name}")

        except Exception as e:
            logger.error(f"Error appending country data to transcript: {e}", exc_info=True)
            print(f"❌ Failed to append country data: {e}")

    # ========================================================================
    # Pipeline Execution
    # ========================================================================

    def _save_json_output(self) -> str:
        """
        Convert CSV output to JSON file.

        Returns:
            Path to saved JSON file
        """
        # Read the CSV file
        with open(self.output_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)

        # Create JSON filename from CSV filename
        json_filename = f"{self.config.output_csv_filename}.json"
        json_filepath = os.path.join(self.config.output_dir, json_filename)

        # Save as formatted JSON
        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return json_filepath

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

        # Write CSV header WITH CONFIDENCE AND REASONING COLUMNS
        with open(self.output_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "technology",
                    "component",
                    "component_confidence",
                    "component_reasoning",  # ← ADDED
                    "material",
                    "material_confidence",
                    "material_reasoning",  # ← ADDED
                    "hs_code",
                    "country",
                    "meas_unit",
                    "amount",
                    "percentage",
                    "country_confidence",
                    "country_reasoning",  # ← ADDED
                ],
            )
            writer.writeheader()

        # Process each technology
        for tech in technologies:
            result = await self.process_technology(
                tech, role, domain, usage, use_material_debate=self.use_material_debate
            )

            if result and result["enriched_data"]:
                # Write results to CSV WITH CONFIDENCE AND REASONING COLUMNS
                with open(self.output_file, "a", newline="") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "technology",
                            "component",
                            "component_confidence",
                            "component_reasoning",  # ← ADDED
                            "material",
                            "material_confidence",
                            "material_reasoning",  # ← ADDED
                            "hs_code",
                            "country",
                            "meas_unit",
                            "amount",
                            "percentage",
                            "country_confidence",
                            "country_reasoning",  # ← ADDED
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

        # Convert CSV to JSON
        json_path = self._save_json_output()
        print(f"✓ JSON output written to {json_path}")

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
