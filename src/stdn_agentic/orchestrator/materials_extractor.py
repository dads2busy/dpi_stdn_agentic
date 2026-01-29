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
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

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
from ..debate.material_normalization import normalize_material_name
from ..dependencies import STDNDependencies
from ..logging_config import get_logger
from ..reporting import DebateReporter

logger = get_logger(__name__)


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
        num_agents: int = 3,
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
            num_agents: Number of agents for material debate (default: 3)
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
        self.num_agents = num_agents
        self.max_retries = max_retries

        # Initialize material debater if using debate
        self.material_debater = None
        if use_debate:
            self.material_debater = MaterialDebater(
                deps=deps,
                num_agents=num_agents,
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
            logger.warning("No components to extract materials from for %s", technology)
            return (False, None, "No components")

        components = componentlist.component_list

        # Filter valid components and extract names
        # Components are now ComponentWithConfidence objects
        valid_component_names = [
            c.name for c in components if c and hasattr(c, "name") and c.name.strip()
        ]

        if not valid_component_names:
            logger.warning("All components were null/empty for %s", technology)
            return (False, None, "All components null/empty")

        # Check ontology availability
        if not self.deps.material_ontology_list or len(self.deps.material_ontology_list) == 0:
            logger.error("Material ontology is empty - cannot extract materials for %s", technology)
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
        is_valid, valid_component_names, error_msg = self._validate_materials_extraction_inputs(
            componentlist, technology
        )

        if not is_valid:
            return ComponentMaterialsList.model_validate({"componentlist": []})

        assert valid_component_names, (
            "valid_component_names should be non-empty after successful validation"
        )

        materials_prompt = self._build_materials_prompt(valid_component_names, technology)

        logger.info(
            "Extracting materials for %d components of %s",
            len(valid_component_names),
            technology,
        )

        result = await self._run_materials_agent_with_retries(materials_prompt)
        if not result or not result.output:
            return ComponentMaterialsList.model_validate({"componentlist": []})

        materials_list = result.output

        # Force component name correction (in-place)
        self._correct_component_names_in_place(materials_list, valid_component_names)

        if not materials_list.component_list:
            return ComponentMaterialsList.model_validate({"componentlist": []})

        # Post-extraction filtering: Remove materials not in ontology
        ontology_set = set(self.deps.material_ontology_list)
        filtered_count = self._filter_materials_not_in_ontology(materials_list, ontology_set)

        if filtered_count > 0:
            logger.info("Filtered %d materials not in ontology", filtered_count)

        num_materials = sum(len(cm.raw_materials) for cm in materials_list.component_list)
        logger.info(
            "Extracted %d materials for %d components",
            num_materials,
            len(materials_list.component_list),
        )

        # Accumulate usage
        if hasattr(result, "usage") and result.usage():
            usage.incr(result.usage())

        return materials_list

    async def _run_materials_agent_with_retries(
        self,
        materials_prompt: str,
    ) -> Optional[Any]:
        for attempt in range(self.max_retries):
            try:
                result = await self.materials_agent.run(materials_prompt, deps=self.deps)

                if not result or not result.output:
                    if attempt == self.max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    return None

                return result

            except Exception as e:
                error_str = str(e)
                is_transient = "invalid message content type" in error_str or "400" in error_str

                if is_transient and attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                    logger.warning(
                        "Transient error (attempt %d/%d): %s",
                        attempt + 1,
                        self.max_retries,
                        e,
                    )
                    await asyncio.sleep(wait_time)
                    continue

                logger.error("Error extracting materials: %s", e, exc_info=True)
                return None

        return None

    def _build_materials_prompt(
        self,
        valid_component_names: list[str],
        technology: str,
    ) -> str:
        component_str = "\n".join(f"  - {comp}" for comp in valid_component_names)

        # Use FULL ontology for strict matching (not just 50 samples)
        ontology_str = "\n".join(f"  - {mat}" for mat in self.deps.material_ontology_list)

        materials_prompt = f"""Extract RAW MATERIALS for EACH component of a {technology}.

        COMPONENTS TO ANALYZE (extract materials for EACH one separately):
{component_str}

        CRITICAL REQUIREMENTS:
        - Return a separate entry for EACH component listed above
        - Use the EXACT component names as written above (do not modify them)
        - Do NOT add qualifiers like "(NAND Flash)", "(OLED)", or any other descriptors
        - Do NOT rename, rephrase, or modify the component names in any way

        MATERIAL CONSTRAINT - You MUST ONLY select materials from this exact list:

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

        For EACH component, identify 2-8 key RAW MATERIALS from the list above.
        Return a JSON response with componentlist containing an entry for each component,
        where each entry has a component field (exact name from above) and materials field
        containing only materials from the provided list.
        """
        return materials_prompt

    def _correct_component_names_in_place(
        self,
        materials_list: ComponentMaterialsList,
        valid_component_names: list[str],
    ) -> None:
        for comp_mat in materials_list.component_list:
            if comp_mat.component not in valid_component_names:
                matched = None
                comp_lower = comp_mat.component.lower().strip()

                for expected in valid_component_names:
                    if expected.lower().strip() == comp_lower:
                        matched = expected
                        break

                if matched:
                    logger.warning(
                        "LLM changed component name from '%s' to '%s', correcting...",
                        matched,
                        comp_mat.component,
                    )
                    comp_mat.component = matched
                else:
                    logger.warning(
                        "Unknown component '%s' not in expected list: %s",
                        comp_mat.component,
                        valid_component_names,
                    )

    def _filter_materials_not_in_ontology(
        self,
        materials_list: ComponentMaterialsList,
        ontology_set: set[str],
    ) -> int:
        filtered_count = 0

        for comp_mat in materials_list.component_list:
            filtered_materials = []
            for mat in comp_mat.raw_materials:
                if mat.name in ontology_set:
                    filtered_materials.append(mat)
                else:
                    logger.warning(
                        "Material '%s' for component '%s' not in ontology, filtering out",
                        mat.name,
                        comp_mat.component,
                    )
                    filtered_count += 1
            comp_mat.raw_materials = filtered_materials

        return filtered_count

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
            return None

        logger.info("Using multi-agent debate for materials...")

        debate_result = await self.material_debater.run_full_debate(components, technology, usage)

        # consensus is: {component: [{"name": ..., "confidence": ..., "reasoning": ...}]}
        consensus = debate_result["consensus"]

        material_confidence_map = self._build_material_confidence_map()
        materials_list_items = self._build_materials_list_from_consensus(
            consensus,
            material_confidence_map,
        )

        self._validate_and_fix_components_and_materials(
            components,
            materials_list_items,
        )

        materials_list = ComponentMaterialsList(componentlist=materials_list_items)

        # Save material debate transcript if enabled
        if self.reporter:
            self._save_material_debate_transcript(
                technology,
                components,
                self.material_debater.debate_history,
                consensus,
            )

        total_materials = sum(len(cm.raw_materials) for cm in materials_list.component_list)
        logger.info(
            "Final result: %d components, %d materials",
            len(materials_list.component_list),
            total_materials,
        )

        return materials_list

    def _build_material_confidence_map(self) -> dict[str, dict]:
        """Build map: 'component|material' -> best confidence proposal."""
        material_confidence_map: dict[str, dict] = {}

        # Explicit None / attribute guards so type checkers are happy
        if self.material_debater is None:
            return material_confidence_map

        if not hasattr(self.material_debater, "debate_history"):
            return material_confidence_map

        if not self.material_debater.debate_history:
            return material_confidence_map

        all_proposals = []
        for debate_round in self.material_debater.debate_history:
            all_proposals.extend(debate_round.proposals)

        for prop in all_proposals:
            mat_key = f"{prop.normalizedcomponent}|{prop.normalizedmaterial}"
            if (
                mat_key not in material_confidence_map
                or prop.confidence > material_confidence_map[mat_key]["confidence"]
            ):
                material_confidence_map[mat_key] = {
                    "name": prop.material,
                    "confidence": prop.confidence,
                    "reasoning": prop.reasoning,
                }

        return material_confidence_map

    def _build_materials_list_from_consensus(
        self,
        consensus: dict[str, list[dict]],
        material_confidence_map: dict[str, dict],
    ) -> list[ComponentMaterials]:
        """Convert consensus dicts into ComponentMaterials items."""
        materials_list_items: list[ComponentMaterials] = []

        for comp, material_dicts in consensus.items():
            material_objects: list[MaterialWithConfidence] = []

            for mat_dict in material_dicts:
                mat_name = mat_dict["name"]
                mat_confidence = mat_dict.get("confidence", 0.75)
                mat_reasoning = mat_dict.get(
                    "reasoning",
                    "Consensus material from multi-agent debate",
                )

                mat_norm = normalize_material_name(mat_name)
                mat_key = f"{comp}|{mat_norm}"

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

        return materials_list_items

    def _validate_and_fix_components_and_materials(
        self,
        components: list[str],
        materials_list_items: list[ComponentMaterials],
    ) -> None:
        """Fix component names and filter invalid materials in-place."""
        logger.debug("Validating component names...")
        logger.debug("  Expected components: %s", components)
        logger.debug("  Materials list has %d items", len(materials_list_items))

        component_lookup = {comp.lower().strip(): comp for comp in components}

        for i, comp_mat in enumerate(materials_list_items):
            comp_lower = comp_mat.component.lower().strip()
            base_name_lower = comp_lower.split("(")[0].strip()

            logger.debug("  [%d] Component from debate: '%s'", i, comp_mat.component)

            if comp_lower in component_lookup:
                expected = component_lookup[comp_lower]
                if comp_mat.component != expected:
                    logger.debug(
                        "    Case mismatch - correcting: '%s' -> '%s'",
                        comp_mat.component,
                        expected,
                    )
                    comp_mat.component = expected
            elif base_name_lower in component_lookup:
                expected = component_lookup[base_name_lower]
                logger.debug(
                    "    Qualifier added - correcting: '%s' -> '%s'",
                    comp_mat.component,
                    expected,
                )
                comp_mat.component = expected
            else:
                logger.warning(
                    "Materials debate introduced unknown component '%s' not in input: %s",
                    comp_mat.component,
                    components,
                )

        logger.debug("Filtering materials against ontology...")
        ontology_set = set(self.deps.material_ontology_list)
        logger.debug("  Ontology has %d materials", len(ontology_set))

        filtered_count = 0

        for comp_mat in materials_list_items:
            valid_materials = []

            for mat in comp_mat.raw_materials:
                if mat.name in ontology_set:
                    valid_materials.append(mat)
                else:
                    logger.warning(
                        "Rejecting invalid material '%s' for '%s' (not in ontology)",
                        mat.name,
                        comp_mat.component,
                    )
                    filtered_count += 1

            comp_mat.raw_materials = valid_materials

        if filtered_count > 0:
            logger.info("Total filtered: %d invalid materials", filtered_count)
        else:
            logger.debug("All materials validated successfully")

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
        content: list[str] = []

        content.append("\n\n")
        content.append("=" * 80 + "\n")
        content.append("MATERIALS EXTRACTION DEBATE\n")
        content.append("=" * 80 + "\n\n")

        self._append_material_transcript_components_section(content, components)
        self._append_material_transcript_debate_rounds_section(content, debate_history)
        self._append_material_transcript_final_consensus_section(content, consensus)

        content.append("=" * 80 + "\n")
        content.append("END OF COMBINED TRANSCRIPT\n")
        content.append("=" * 80 + "\n")

        return "".join(content)

    def _append_material_transcript_components_section(
        self,
        content: list[str],
        components: list,
    ) -> None:
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

    def _append_material_transcript_debate_rounds_section(
        self,
        content: list[str],
        debate_history: list,
    ) -> None:
        content.append("=" * 80 + "\n")
        content.append("MATERIAL DEBATE ROUNDS\n")
        content.append("=" * 80 + "\n\n")

        for round_data in debate_history:
            content.append(f"ROUND {round_data.roundnumber}:\n")
            content.append(f"  Convergence: {round_data.convergencescore:.1%}\n")

            if round_data.critiques:
                content.append(f"  Critiques ({len(round_data.critiques)} total):\n")
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

    def _append_material_transcript_final_consensus_section(
        self,
        content: list[str],
        consensus: dict[str, list[dict]],
    ) -> None:
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

    def _save_material_debate_transcript(
        self,
        technology: str,
        components: list,  # Can be strings or ComponentWithConfidence
        debate_history: list,
        consensus: dict[str, list[dict]],
    ) -> None:
        """Append material debate results to existing component transcript."""
        logger.debug(
            "Attempting to save material transcript for %s: %d components, %d consensus items",
            technology,
            len(components),
            len(consensus),
        )

        if not self.reporter:
            logger.warning("Reporter is None, cannot save transcript")
            return

        try:
            output_dir = Path(self.reporter.output_dir)

            # Replace spaces with underscores to match filename format
            tech_filename = technology.replace(" ", "_")

            # Find most recent component transcript
            component_transcripts = list(output_dir.glob(f"{tech_filename}_*.txt"))
            component_transcripts = [f for f in component_transcripts if "_materials" not in f.name]

            logger.debug("Looking for: %s_*.txt", tech_filename)
            logger.debug("Found %d component transcripts", len(component_transcripts))

            if not component_transcripts:
                logger.warning("No component transcript found for %s", technology)
                return

            filepath = max(component_transcripts, key=lambda p: p.stat().st_mtime)
            logger.debug("Will append to: %s", filepath.name)

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

            logger.info("Appended material debate to: %s", filepath.name)

        except Exception as e:
            logger.error("Error appending material debate transcript: %s", e, exc_info=True)

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
