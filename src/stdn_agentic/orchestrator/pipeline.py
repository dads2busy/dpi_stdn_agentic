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
)
from ..data import CountryDataRepository
from ..debate import MultiAgentDebater
from ..dependencies import initialize_dependencies
from ..models import ConfigModel
from ..reporting import DebateReporter
from .component_extractor import ComponentExtractor
from .country_data_enricher import CountryDataEnricher
from .materials_extractor import MaterialsExtractor

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

        # Output file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.timestamp = timestamp  # Store for JSON output
        output_filename = f"{config.output_csv_filename}_{timestamp}.csv"
        self.output_file = os.path.join(config.output_dir, output_filename)
        os.makedirs(config.output_dir, exist_ok=True)

        # Initialize component extractor
        self.component_extractor = ComponentExtractor(
            deps=self.deps,
            model_name=self.deps.model,
            debater=self.debater,
            reporter=self.reporter,
            timestamp=self.timestamp,
            debate_top_p=self.debate_top_p,
        )

        # Initialize materials extractor
        self.materials_extractor = MaterialsExtractor(
            deps=self.deps,
            model_name=self.deps.model,
            reporter=self.reporter,
            timestamp=self.timestamp,
            use_debate=self.use_material_debate,
            max_retries=5,
            debate_max_rounds=self.max_debate_rounds,
            debate_convergence_threshold=self.convergence_threshold,
            debate_top_p=self.debate_top_p,
        )

        # Initialize country data enricher
        self.country_enricher = CountryDataEnricher(
            country_repo=self.country_repo,
            reporter=self.reporter,
            write_nulls=self.write_nulls,
            use_debate=self.use_country_debate,
        )

    async def extract_components_with_debate(
        self, technology: str, role: str, usage: RunUsage, num_agents: int = 3
    ):
        """Delegate to ComponentExtractor for component extraction."""
        return await self.component_extractor.extract_components_with_debate(
            technology=technology, role=role, usage=usage, num_agents=num_agents
        )

    async def _extract_materials_for_technology(
        self, components: list[str], technology: str, usage: RunUsage
    ) -> Optional[ComponentMaterialsList]:
        """Delegate to MaterialsExtractor."""
        return await self.materials_extractor.extract_materials_for_technology(
            components=components,
            technology=technology,
            usage=usage,
        )

    async def _enrich_with_country_data(
        self,
        materials_list: ComponentMaterialsList,
        technology: str,
        usage: RunUsage,
        transcript_path: Optional[Path] = None,
        component_confidence_map: Optional[dict] = None,
    ) -> list[dict[str, Any]]:
        """Delegate to CountryDataEnricher."""
        return await self.country_enricher.enrich_with_country_data(
            materials_list=materials_list,
            technology=technology,
            usage=usage,
            transcript_path=transcript_path,
            component_confidence_map=component_confidence_map,
        )

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
                components_result = await self.component_extractor.extract_components_simple(
                    tech, usage
                )

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
                # ✅ FIX: Normalize keys to match materials list
                component_confidence_map: dict[str, dict[str, Any]] = {}
                for comp in component_objects:
                    normalized_name = comp.name.lower().strip()
                    component_confidence_map[normalized_name] = {
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

                    # ✅ FIX: Normalize keys to match materials list
                    component_confidence_map = {
                        comp.name.lower().strip(): {
                            "confidence": comp.confidence,
                            "reasoning": comp.reasoning,
                        }
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

    def _append_country_data_to_transcript(
        self, technology: str, enriched_data: list[dict[str, Any]]
    ) -> None:
        """Delegate to CountryDataEnricher."""
        self.country_enricher.append_country_data_to_transcript(technology, enriched_data)

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

        # Create JSON filename from CSV filename with timestamp
        json_filename = f"{self.config.output_csv_filename}_{self.timestamp}.json"
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
        tech_roles: Optional[Dict[str, str]] = None,  # ← NEW
        tech_domains: Optional[Dict[str, str]] = None,  # ← NEW
    ) -> Dict[str, Any]:
        """Run complete STDN pipeline for multiple technologies.

        Args:
            technologies: List of technology names
            role: Default expert role context
            domain: Default domain context
            tech_roles: Optional mapping of technology -> specific role
            tech_domains: Optional mapping of technology -> specific domain

        Returns:
            Dict with results and statistics
        """

        usage = RunUsage()

        print("=" * 80)
        print(f"STDN Generation Started: {datetime.now()}")
        print("=" * 80)
        if self.use_debate:
            print("✓ Multi-agent debate ENABLED")
            print(f"  Max rounds: {self.max_debate_rounds}")
            print(f"  Convergence threshold: {self.convergence_threshold}")
            print(f"  Save transcripts: {self.save_transcripts}")
        print(f"✓ {len(technologies)} technologies from {self.config.tech_list_path}")

        successful = 0
        failed = 0

        # Initialize CSV file with headers
        with open(self.output_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "technology",
                    "component",
                    "component_confidence",
                    "component_reasoning",
                    "material",
                    "material_confidence",
                    "material_reasoning",
                    "hs_code",
                    "country",
                    "meas_unit",
                    "amount",
                    "percentage",
                    "country_confidence",
                    "country_reasoning",
                ],
            )
            writer.writeheader()

        # Process each technology
        for tech in technologies:
            # Use tech-specific role/domain if provided, otherwise use defaults
            tech_role = tech_roles.get(tech, role) if tech_roles else role
            tech_domain = tech_domains.get(tech, domain) if tech_domains else domain

            result = await self.process_technology(
                tech,
                tech_role,  # ← Use tech-specific role
                tech_domain,  # ← Use tech-specific domain
                usage,
                use_material_debate=self.use_material_debate,
            )

            if result and result["enriched_data"]:
                # Append to CSV (use 'a' mode to append)
                with open(self.output_file, "a", newline="") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "technology",
                            "component",
                            "component_confidence",
                            "component_reasoning",
                            "material",
                            "material_confidence",
                            "material_reasoning",
                            "hs_code",
                            "country",
                            "meas_unit",
                            "amount",
                            "percentage",
                            "country_confidence",
                            "country_reasoning",
                        ],
                    )
                    for row in result["enriched_data"]:
                        writer.writerow(row)

                print(f"✓ Output written to {self.output_file}")
                print(f"✓ Successfully processed: {tech}")
                successful += 1
            else:
                print(f"✗ Failed to process: {tech}")
                failed += 1

        print("=" * 80)
        print(f"STDN Generation Completed: {datetime.now()}")
        print("=" * 80)
        print(f"Successfully processed: {successful}/{len(technologies)} technologies")
        print(f"✓ Output saved to: {self.output_file}")
        if self.use_debate and self.reporter:
            print(f"✓ Debate transcripts saved to: {self.reporter.output_dir}")

        print(f"\nUsage: {usage}")

        if successful > 0:
            # Convert CSV to JSON
            json_path = self._save_json_output
            print(f"✓ JSON output written to: {json_path}")

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
