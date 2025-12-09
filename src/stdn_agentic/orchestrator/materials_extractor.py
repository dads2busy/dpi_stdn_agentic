"""
Materials Extractor Module

This module handles materials extraction from components using either
single-agent extraction or multi-agent debate with convergence.

Features:
- Safe materials extraction with retry logic and validation
- Multi-agent debate system for material consensus
- Strict ontology constraint enforcement
- Debate transcript generation
- Comprehensive error handling
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic_ai import RunUsage

from ..agents import (
    ComponentList,
    ComponentMaterials,
    ComponentMaterialsList,
    ComponentWithConfidence,
    get_materials_agent,
)
from ..agents.materials_agent import MaterialWithConfidence
from ..debate import MaterialDebater
from ..dependencies import STDNDependencies
from ..reporting import DebateReporter

# Initialize logger
logger = logging.getLogger(__name__)


# ============================================================================
# Materials Extractor
# ============================================================================


class MaterialsExtractor:
    """Handles materials extraction with optional multi-agent debate"""

    def __init__(
        self,
        deps: STDNDependencies,
        model_name: str,
        reporter: Optional[DebateReporter] = None,
        timestamp: Optional[str] = None,
        use_debate: bool = False,
        max_retries: int = 5,
        debate_max_rounds: int = 3,
        debate_convergence_threshold: float = 0.8,
        debate_top_p: float = 0.0001,
    ):
        """
        Initialize materials extractor.

        Args:
            deps: STDN dependencies
            model_name: Model name for agent
            reporter: Optional DebateReporter instance
            timestamp: Optional timestamp for transcript filenames
            use_debate: Use multi-agent debate for materials extraction
            max_retries: Maximum retry attempts for extraction
            debate_max_rounds: Maximum debate rounds
            debate_convergence_threshold: Convergence threshold for debate
            debate_top_p: Top-p sampling parameter for debate
        """
        self.deps = deps
        self.materials_agent = get_materials_agent(model_name=model_name)
        self.reporter = reporter
        self.timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.use_debate = use_debate
        self.max_retries = max_retries

        # Initialize material debater if using debate
        self.material_debater = None
        if use_debate:
            self.material_debater = MaterialDebater(
                deps=deps,
                num_agents=3,
                max_rounds=debate_max_rounds,
                convergence_threshold=debate_convergence_threshold,
                debate_top_p=debate_top_p,
            )

    # ========================================================================
    # Validation
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

    # ========================================================================
    # Safe Single-Agent Extraction
    # ========================================================================

    async def extract_materials_safe(
        self,
        componentlist: ComponentList,
        technology: str,
        usage: RunUsage,
    ) -> Optional[ComponentMaterialsList]:
        """
        Safely extract materials with comprehensive error handling and retry logic.
        Materials are strictly constrained to the ontology list from hs_codes_and_usgs_names.csv
        """
        # Check ontology availability
        is_valid, valid_component_names, error_msg = self._validate_materials_extraction_inputs(
            componentlist, technology
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
        materials_prompt = f"""Extract RAW MATERIALS for this component of a {technology}:

        COMPONENT NAME (use EXACTLY as written, do not modify):
        "{component_str}"

        CRITICAL REQUIREMENT:
        - When returning results, use the EXACT component name: "{component_str}"
        - Do NOT add qualifiers like "(NAND Flash)", "(OLED)", or any other descriptors
        - Do NOT rename, rephrase, or modify the component name in any way
        - The component field in your response MUST be exactly: "{component_str}"

        MATERIAL CONSTRAINT - You MUST ONLY select materials from this exact list:

        {ontology_str}

        RULES:
        1. Use ONLY material names from the above list (exact matches required)
        2. Do NOT use synonyms, abbreviations, or variations
        3. Do NOT invent new materials or use brand names
        4. Do NOT use manufactured products (e.g., "EVA", "PET film") - use base materials instead
        5. If unsure, choose the closest base material from the list
        6. Component name in response must match exactly: "{component_str}"

        EXAMPLES OF CORRECT USAGE:
        ✓ Use "Silicon" not "Monocrystalline silicon"
        ✓ Use "Aluminum" not "Aluminum alloy" or "6061 aluminum"
        ✓ Use "Polyethylene terephthalate" not "PET" or "Polyester film"
        ✓ Use "Glass" not "Borosilicate glass" (unless "Borosilicate glass" is in the list)
        ✓ Use "Copper" not "Copper wire"

        COMPONENT NAME TO USE IN RESPONSE:
        "{component_str}"

        For this component, identify 2-8 key RAW MATERIALS from the list above.
        Return a JSON response with the component field set to exactly "{component_str}"
        and materials field containing only materials from the provided list.
        """

        logger.info(
            f"Extracting materials for {len(valid_component_names)} components of {technology}"
        )
        print(f"Extracting materials for {len(valid_component_names)} components...")

        for attempt in range(self.max_retries):
            try:
                result = await self.materials_agent.run(materials_prompt, deps=self.deps)

                if not result or not result.output:
                    if attempt == self.max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    return ComponentMaterialsList.model_validate({"componentlist": []})

                materials_list = result.output

                # Force component name correction
                for comp_mat in materials_list.component_list:
                    # valid_component_names is the list of expected names
                    # Check if LLM changed the component name
                    if comp_mat.component not in valid_component_names:
                        # Try to find matching component (case-insensitive)
                        matched = None
                        comp_lower = comp_mat.component.lower().strip()

                        for expected in valid_component_names:
                            if expected.lower().strip() == comp_lower:
                                matched = expected
                                break

                        if matched:
                            logger.warning(
                                f"LLM changed component name from '{matched}' to '{comp_mat.component}', correcting..."
                            )
                            print(
                                f"  ⚠️ Correcting component name: '{comp_mat.component}' → '{matched}'"
                            )
                            comp_mat.component = matched
                        else:
                            logger.warning(
                                f"Unknown component '{comp_mat.component}' not in expected list: {valid_component_names}"
                            )
                            print(f"  ⚠️ Unknown component: '{comp_mat.component}'")

                if not materials_list.component_list:
                    if attempt == self.max_retries - 1:
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
                            print(f"  ⚠️ Filtered out '{mat.name}' (not in ontology)")
                            filtered_count += 1
                    comp_mat.raw_materials = filtered_materials

                if filtered_count > 0:
                    print(f"  ℹ️ Filtered {filtered_count} materials not in ontology")

                num_materials = sum(len(cm.raw_materials) for cm in materials_list.component_list)
                logger.info(
                    f"Extracted {num_materials} materials for {len(materials_list.component_list)} components"
                )
                print(f"Extracted materials for {len(materials_list.component_list)} components")

                # Accumulate usage
                if hasattr(result, "usage") and result.usage():
                    usage.incr(result.usage())

                return materials_list

            except Exception as e:
                error_str = str(e)
                is_transient = "invalid message content type" in error_str or "400" in error_str

                if is_transient and attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                    logger.warning(
                        f"Transient error (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Error extracting materials: {e}", exc_info=True)
                    return ComponentMaterialsList.model_validate({"componentlist": []})

        return ComponentMaterialsList.model_validate({"componentlist": []})

    # ========================================================================
    # Multi-Agent Debate Extraction
    # ========================================================================

    async def extract_materials_with_debate(
        self,
        components: list[str],
        technology: str,
        usage: RunUsage,
    ) -> Optional[ComponentMaterialsList]:
        """
        Extract materials using multi-agent debate.

        Args:
            components: List of component names (normalized strings)
            technology: Technology name
            usage: RunUsage tracker

        Returns:
            ComponentMaterialsList with MaterialWithConfidence objects, or None if extraction fails
        """
        if not self.material_debater:
            logger.error("Material debater not initialized but debate was requested")
            print("❌ Material debater not initialized")
            return None

        print("Using multi-agent debate for materials...")

        debate_result = await self.material_debater.run_full_debate(components, technology, usage)

        # Convert debate consensus to ComponentMaterialsList format
        # consensus is now: {component: [{"name": ..., "confidence": ..., "reasoning": ...}]}
        consensus = debate_result["consensus"]

        # Build material confidence map from debate proposals
        material_confidence_map = {}
        if (
            hasattr(self.material_debater, "debate_history")
            and self.material_debater.debate_history
        ):
            # Get all proposals from all rounds (prioritize later rounds)
            all_proposals = []
            for debate_round in self.material_debater.debate_history:
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
                mat_norm = self.material_debater.normalize_material_name(mat_name)
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

        # ========================================================================
        # VALIDATION SECTION - Fix component names and filter invalid materials
        # ========================================================================

        # STEP 1: Fix component names to match input components
        print("\n🔍 Validating component names...")
        print(f"  Expected components: {components}")
        print(f"  Materials list has {len(materials_list_items)} items")

        # Build case-insensitive lookup map: lowercase -> correct name
        component_lookup = {comp.lower().strip(): comp for comp in components}

        for i, comp_mat in enumerate(materials_list_items):
            comp_lower = comp_mat.component.lower().strip()

            # Remove any qualifiers like "(amoled)" or "(32mp sensor)"
            # Extract base name before first parenthesis
            base_name_lower = comp_lower.split("(")[0].strip()

            print(f"  [{i}] Component from debate: '{comp_mat.component}'")
            print(f"      Base name (lowercase): '{base_name_lower}'")

            # Try exact match first
            if comp_lower in component_lookup:
                expected = component_lookup[comp_lower]
                if comp_mat.component != expected:
                    print(
                        f"    ⚠️ Case mismatch - correcting: '{comp_mat.component}' → '{expected}'"
                    )
                    comp_mat.component = expected
                else:
                    print(f"    ✓ Component name matches expected input")

            # Try base name match (without qualifiers)
            elif base_name_lower in component_lookup:
                expected = component_lookup[base_name_lower]
                print(f"    ⚠️ Qualifier added - correcting: '{comp_mat.component}' → '{expected}'")
                comp_mat.component = expected

            # Unknown component
            else:
                logger.warning(
                    f"Materials debate introduced unknown component '{comp_mat.component}' "
                    f"not in input: {components}"
                )
                print("    ❌ Unknown component - no match found!")
                print(f"       Available: {list(component_lookup.keys())}")

        # STEP 2: Filter invalid materials not in ontology
        print("\n🔍 Filtering materials against ontology...")
        ontology_set = set(self.deps.material_ontology_list)
        print(f"  Ontology has {len(ontology_set)} materials")

        filtered_count = 0

        for comp_mat in materials_list_items:
            print(f"\n  Checking materials for '{comp_mat.component}':")
            valid_materials = []

            for mat in comp_mat.raw_materials:  # ✅ Use raw_materials
                # Check if material name is in ontology
                if mat.name in ontology_set:
                    valid_materials.append(mat)
                    print(f"    ✓ '{mat.name}' - valid (in ontology)")
                else:
                    logger.warning(
                        f"Rejecting invalid material '{mat.name}' for '{comp_mat.component}' "
                        f"(not in ontology)"
                    )
                    print(f"    ✗ '{mat.name}' - NOT IN ONTOLOGY, filtering out")
                    filtered_count += 1

            # Update with only valid materials
            comp_mat.raw_materials = valid_materials  # ✅ Use raw_materials

        if filtered_count > 0:
            print(f"\n  ℹ️ Total filtered: {filtered_count} invalid materials")
        else:
            print("\n  ✓ All materials validated successfully")

        # ========================================================================
        # END VALIDATION SECTION
        # ========================================================================

        materials_list = ComponentMaterialsList(componentlist=materials_list_items)

        # Save material debate transcript if enabled
        if self.reporter:
            self._save_material_debate_transcript(
                technology, components, self.material_debater.debate_history, consensus
            )

        # Final summary
        total_materials = sum(
            len(cm.raw_materials) for cm in materials_list.component_list
        )  # ✅ Use raw_materials
        print(
            f"\n✓ Final result: {len(materials_list.component_list)} components, {total_materials} materials"
        )

        return materials_list

    # ========================================================================
    # Main Entry Point
    # ========================================================================

    async def extract_materials_for_technology(
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
        if self.use_debate:
            return await self.extract_materials_with_debate(components, technology, usage)
        else:
            # Single-agent extraction (already returns MaterialWithConfidence objects)
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
                    technology_specification=technology,
                    technology_reasoning="Single-agent component extraction without debate",
                ),
                technology=technology,
                usage=usage,
            )

            if not materials_result or not materials_result.component_list:
                return None

            return materials_result

    # ========================================================================
    # Transcript Management
    # ========================================================================

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
                    content.append(f"    → {comp.reasoning}\n")
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

            # Replace spaces with underscores to match filename format
            tech_filename = technology.replace(" ", "_")

            # Find most recent component transcript
            component_transcripts = list(output_dir.glob(f"{tech_filename}_*.txt"))
            component_transcripts = [f for f in component_transcripts if "_materials" not in f.name]

            print(f"🔍 DEBUG: Looking for: {tech_filename}_*.txt")
            print(f"🔍 DEBUG: Found {len(component_transcripts)} component transcripts")

            if not component_transcripts:
                logger.warning(f"No component transcript found for {technology}")
                print(f"❌ No component transcript found in {output_dir}")
                return

            filepath = max(component_transcripts, key=lambda p: p.stat().st_mtime)
            print(f"🔍 DEBUG: Will append to: {filepath.name}")

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
