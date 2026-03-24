"""
Country Data Enricher Module

This module handles country production data enrichment for materials.
It queries the country data repository and formats results for output,
including confidence scores and reasoning from the multi-agent debate system.

Features:
- Country production data enrichment from USGS database
- Optional multi-agent debate for country data validation
- Transcript appending for audit trails
- Null value handling based on configuration
- Comprehensive error handling and logging
"""

from pathlib import Path
from typing import Any, Optional

from pydantic_ai import RunUsage

from ..agents import ComponentMaterialsList
from ..data import CountryDataRepository
from ..logging_config import get_logger
from ..reporting import DebateReporter

logger = get_logger(__name__)


# ============================================================================
# Country Data Enricher
# ============================================================================


class CountryDataEnricher:
    """Handles country production data enrichment for materials"""

    def __init__(
        self,
        country_repo: CountryDataRepository,
        reporter: Optional[DebateReporter] = None,
        write_nulls: bool = True,
        use_debate: bool = False,
        num_agents: int = 3,
    ):
        """
        Initialize country data enricher.

        Args:
            country_repo: CountryDataRepository instance
            reporter: Optional DebateReporter instance for transcript management
            write_nulls: Whether to write records with null country data
            use_debate: Whether to use multi-agent debate for country data validation
            num_agents: Number of agents for country data voting (default: 3)
        """
        self.country_repo = country_repo
        self.reporter = reporter
        self.write_nulls = write_nulls
        self.use_debate = use_debate
        self.num_agents = num_agents

    # ========================================================================
    # Main Enrichment Logic
    # ========================================================================

    async def enrich_with_country_data(
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

            # ✅ FIX: Normalize the component name for lookup (match how map keys were created)
            normalized_component = component.lower().strip()

            # Get component confidence and reasoning from the map
            comp_info = component_confidence_map.get(normalized_component, {})
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
                    # Look up HS code for this material (for LLM cache key)
                    hs_code = self.country_repo.lookup_hs_code(material_name)

                    # Query country data repository
                    country_data = await self.country_repo.get_country_data(
                        material=material_name,
                        src_year=getattr(self.country_repo, "src_year", 2024),
                        meas_year=getattr(self.country_repo, "meas_year", 2023),
                        usage=usage,
                        use_debate=self.use_debate,
                        num_agents=self.num_agents,
                        transcript_path=transcript_path,
                        hs_code=hs_code,
                    )

                    if country_data:
                        # We have country data - create records with confidence and reasoning
                        for country_info in country_data:
                            enriched_data.append(
                                {
                                    "technology": technology,
                                    "component": component,
                                    "component_confidence": round(component_confidence, 3),
                                    "component_reasoning": component_reasoning,
                                    "material": material_name,
                                    "material_confidence": round(material_confidence, 3),
                                    "material_reasoning": material_reasoning,
                                    "hs_code": country_info.get("hs_code"),
                                    "country": country_info.get("country", "Unknown"),
                                    "meas_unit": country_info.get("meas_unit", ""),
                                    "amount": country_info.get("amount", 0.0),
                                    "percentage": round(country_info.get("percentage", 0.0), 2),
                                    "country_confidence": round(
                                        country_info.get("confidence", 0.0), 3
                                    ),
                                    "country_reasoning": country_info.get("reasoning", ""),
                                }
                            )
                    elif self.write_nulls:
                        # No country data found - write null record if enabled
                        enriched_data.append(
                            {
                                "technology": technology,
                                "component": component,
                                "component_confidence": round(component_confidence, 3),
                                "component_reasoning": component_reasoning,
                                "material": material_name,
                                "material_confidence": round(material_confidence, 3),
                                "material_reasoning": material_reasoning,
                                "hs_code": None,
                                "country": None,
                                "meas_unit": None,
                                "amount": None,
                                "percentage": None,
                                "country_confidence": None,
                                "country_reasoning": None,
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
                                "component_reasoning": component_reasoning,
                                "material": material_name,
                                "material_confidence": round(material_confidence, 3),
                                "material_reasoning": material_reasoning,
                                "hs_code": None,
                                "country": None,
                                "meas_unit": None,
                                "amount": None,
                                "percentage": None,
                                "country_confidence": None,
                                "country_reasoning": None,
                            }
                        )

        return enriched_data

    # ========================================================================
    # Process Consumables Enrichment
    # ========================================================================

    async def enrich_process_consumables(
        self,
        process_consumables,  # ProcessConsumablesResult
        technology: str,
        usage: RunUsage,
        transcript_path: Optional[Path] = None,
    ) -> list[dict[str, Any]]:
        """Enrich process consumables with country production data."""
        enriched_data = []
        for pc in process_consumables.materials:
            material_name = pc.name
            if not material_name or not material_name.strip():
                continue
            try:
                country_data = await self.country_repo.get_country_data(
                    material=material_name,
                    src_year=getattr(self.country_repo, "src_year", 2024),
                    meas_year=getattr(self.country_repo, "meas_year", 2023),
                    usage=usage,
                    use_debate=self.use_debate,
                    num_agents=self.num_agents,
                    transcript_path=transcript_path,
                    hs_code=None,  # Process consumables may not have HS codes
                )
                if country_data:
                    for country_info in country_data:
                        enriched_data.append({
                            "technology": technology,
                            "component": "",
                            "component_confidence": "",
                            "component_reasoning": "",
                            "material": material_name,
                            "material_confidence": round(pc.confidence, 3),
                            "material_reasoning": pc.reasoning,
                            "hs_code": country_info.get("hs_code"),
                            "country": country_info.get("country", "Unknown"),
                            "meas_unit": country_info.get("meas_unit", ""),
                            "amount": country_info.get("amount", 0.0),
                            "percentage": round(country_info.get("percentage", 0.0), 2),
                            "country_confidence": round(
                                country_info.get("confidence", 0.0), 3
                            ),
                            "country_reasoning": country_info.get("reasoning", ""),
                            "dependency_type": "process_consumable",
                            "extraction_provenance": pc.extraction_provenance,
                        })
                elif self.write_nulls:
                    enriched_data.append({
                        "technology": technology,
                        "component": "",
                        "component_confidence": "",
                        "component_reasoning": "",
                        "material": material_name,
                        "material_confidence": round(pc.confidence, 3),
                        "material_reasoning": pc.reasoning,
                        "hs_code": None,
                        "country": None,
                        "meas_unit": None,
                        "amount": None,
                        "percentage": None,
                        "country_confidence": None,
                        "country_reasoning": None,
                        "dependency_type": "process_consumable",
                        "extraction_provenance": pc.extraction_provenance,
                    })
            except Exception as e:
                logger.error(
                    f"Error getting country data for process consumable {material_name}: {e}",
                    exc_info=True,
                )
        return enriched_data

    # ========================================================================
    # Transcript Management
    # ========================================================================

    def append_country_data_to_transcript(
        self,
        technology: str,
        enriched_data: list[dict[str, Any]],
        transcript_path: Optional[Path] = None,
    ) -> None:
        """
        Append country production data to a transcript.

        If `transcript_path` is provided, append to that exact file (preferred; avoids
        cross-run contamination). Otherwise, fall back to selecting the most recent
        transcript for this technology by globbing.

        Args:
            technology: Technology name
            enriched_data: List of enriched data records
            transcript_path: Explicit transcript path to append to (recommended)
        """
        if not self.reporter:
            logger.warning("Reporter is None, cannot append country data")
            return

        if not enriched_data:
            logger.warning("No enriched data to append")
            return

        try:
            output_dir = Path(self.reporter.output_dir)

            # Prefer explicit path when provided
            if transcript_path is not None:
                filepath = Path(transcript_path)
                if not filepath.exists():
                    logger.warning("Provided transcript path does not exist: %s", filepath)
                    return
            else:
                # Replace spaces with underscores to match filename format
                tech_filename = technology.replace("/", "-").replace(" ", "_")

                # Find most recent transcript for this technology
                transcripts = list(output_dir.glob(f"{tech_filename}_*.txt"))
                if not transcripts:
                    logger.warning("No transcript found for %s", technology)
                    return

                # Get most recent transcript
                filepath = max(transcripts, key=lambda p: p.stat().st_mtime)

            # Build country data section
            content = []
            content.append("\n\n")
            content.append("=" * 80 + "\n")
            content.append("COUNTRY PRODUCTION DATA\n")
            content.append("=" * 80 + "\n\n")

            # Group by component
            components = {}
            for record in enriched_data:
                comp = record["component"]
                if comp not in components:
                    components[comp] = []
                components[comp].append(record)

            # Write data by component
            for component, records in sorted(components.items()):
                content.append(f"{component}:\n")
                content.append("-" * 80 + "\n")

                # Group by material
                materials = {}
                for record in records:
                    mat = record["material"]
                    if mat not in materials:
                        materials[mat] = []
                    materials[mat].append(record)

                for material, mat_records in sorted(materials.items()):
                    content.append(f"\n  Material: {material}\n")

                    # Show material confidence if available
                    if mat_records[0].get("material_confidence"):
                        mat_conf = mat_records[0]["material_confidence"]
                        content.append(f"  Confidence: {mat_conf:.3f}\n")

                    content.append(f"  Countries ({len(mat_records)}):\n")

                    for record in mat_records:
                        if record["country"]:
                            content.append(
                                f"    • {record['country']}: "
                                f"{record['amount']} {record['meas_unit']} "
                                f"({record['percentage']}%)\n"
                            )
                            if record.get("country_confidence"):
                                content.append(
                                    f"      Confidence: {record['country_confidence']:.3f}\n"
                                )
                        else:
                            content.append("    • No country data available\n")

                content.append("\n")

            # Summary statistics
            content.append("\n" + "=" * 80 + "\n")
            content.append("SUMMARY\n")
            content.append("=" * 80 + "\n")
            content.append(f"Total records: {len(enriched_data)}\n")
            content.append(f"Components: {len(components)}\n")

            unique_materials = len({r["material"] for r in enriched_data})
            content.append(f"Unique materials: {unique_materials}\n")

            countries_with_data = sum(1 for r in enriched_data if r["country"])
            content.append(f"Records with country  {countries_with_data}\n")

            if countries_with_data > 0:
                avg_confidence = (
                    sum(
                        r.get("country_confidence", 0)
                        for r in enriched_data
                        if r.get("country_confidence")
                    )
                    / countries_with_data
                )
                content.append(f"Average country confidence: {avg_confidence:.3f}\n")

            # Append to file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("".join(content))
                f.flush()

            logger.info("Appended country data to: %s", filepath.name)

        except Exception as e:
            logger.error("Error appending country data to transcript: %s", e, exc_info=True)

    def append_process_consumables_to_transcript(
        self,
        technology: str,
        enriched_data: list[dict[str, Any]],
        transcript_path: Optional[Path] = None,
    ) -> None:
        """
        Append process consumables country data to a transcript.

        Args:
            technology: Technology name
            enriched_data: List of enriched data records with dependency_type="process_consumable"
            transcript_path: Explicit transcript path to append to (recommended)
        """
        if not self.reporter:
            logger.warning("Reporter is None, cannot append process consumables data")
            return

        if not enriched_data:
            logger.warning("No process consumables data to append")
            return

        try:
            output_dir = Path(self.reporter.output_dir)

            # Prefer explicit path when provided
            if transcript_path is not None:
                filepath = Path(transcript_path)
                if not filepath.exists():
                    logger.warning("Provided transcript path does not exist: %s", filepath)
                    return
            else:
                tech_filename = technology.replace("/", "-").replace(" ", "_")
                transcripts = list(output_dir.glob(f"{tech_filename}_*.txt"))
                if not transcripts:
                    logger.warning("No transcript found for %s", technology)
                    return
                filepath = max(transcripts, key=lambda p: p.stat().st_mtime)

            # Build process consumables section
            content = []
            content.append("\n\n")
            content.append("=" * 80 + "\n")
            content.append("PROCESS CONSUMABLES (Stage 2b)\n")
            content.append("=" * 80 + "\n\n")

            for record in enriched_data:
                material = record["material"]
                content.append(f"  Material: {material}\n")

                if record.get("material_confidence"):
                    content.append(f"  Confidence: {record['material_confidence']:.3f}\n")

                provenance = record.get("extraction_provenance", "unknown")
                content.append(f"  Provenance: {provenance}\n")

                if record["country"]:
                    content.append(
                        f"    • {record['country']}: "
                        f"{record['amount']} {record['meas_unit']} "
                        f"({record['percentage']}%)\n"
                    )
                    if record.get("country_confidence"):
                        content.append(
                            f"      Confidence: {record['country_confidence']:.3f}\n"
                        )
                else:
                    content.append("    • No country data available\n")

                content.append("\n")

            # Summary statistics
            content.append("=" * 80 + "\n")
            content.append("SUMMARY\n")
            content.append("=" * 80 + "\n")
            content.append(f"Total records: {len(enriched_data)}\n")

            unique_materials = len({r["material"] for r in enriched_data})
            content.append(f"Unique materials: {unique_materials}\n")

            countries_with_data = sum(1 for r in enriched_data if r["country"])
            content.append(f"Records with country data: {countries_with_data}\n")

            if countries_with_data > 0:
                avg_confidence = (
                    sum(
                        r.get("country_confidence", 0)
                        for r in enriched_data
                        if r.get("country_confidence")
                    )
                    / countries_with_data
                )
                content.append(f"Average country confidence: {avg_confidence:.3f}\n")

            # Append to file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("".join(content))
                f.flush()

            logger.info("Appended process consumables data to: %s", filepath.name)

        except Exception as e:
            logger.error("Error appending process consumables to transcript: %s", e, exc_info=True)
