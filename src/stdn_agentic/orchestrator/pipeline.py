"""
STDN Pipeline Orchestrator

This module coordinates the end-to-end STDN generation workflow:
1. Component extraction (with optional multi-agent debate)
2. Materials identification for each component
3. Country production data enrichment
4. CSV output generation
5. Component name normalization (post-processing)

The orchestrator manages agents, debate systems, checkpoint management,
and reporting for large-scale STDN generation from technology lists.

Enhanced features:
- Robust materials extraction with comprehensive error handling
- Enhanced multi-agent debate with critique-driven convergence
- Adaptive consensus building based on convergence scores
- Dynamic confidence scoring for all components
- Detailed logging and progress reporting
- Post-run component normalization with persistent vocabulary

Checkpoint/resume:
- When enabled via config (`enable_checkpoints`), the orchestrator writes a checkpoint
  after every N technologies (`checkpoint_interval`) and resumes from the most recent
  checkpoint on restart (for the same effective run configuration).
"""

import asyncio
import contextvars
import csv
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic_ai import RunUsage

from ..agents import (
    ComponentMaterialsList,
)
from ..data import CountryDataRepository
from ..debate.component_debater import MultiAgentDebater
from ..dependencies import initialize_dependencies
from ..logging_config import get_logger
from ..models import ConfigModel, STDNDependencies
from ..normalization.canonical_vocab import CanonicalVocab
from ..reporting import DebateReporter
from .checkpoint import CheckpointManager
from .component_extractor import ComponentExtractor
from .country_data_enricher import CountryDataEnricher
from .materials_extractor import MaterialsExtractor
from .technology_context import TechnologyContext

logger = get_logger(__name__)

_current_technology: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_technology", default=""
)


class _TechnologyLogFilter(logging.Filter):
    """Only passes log records matching the handler's technology."""

    def __init__(self, tech_name: str):
        super().__init__()
        self.tech_name = tech_name

    def filter(self, record):
        return _current_technology.get("") == self.tech_name


# ============================================================================
# Public helpers
# ============================================================================


def build_structured_json(csv_path: str) -> dict:
    """Build structured JSON with typed dependency sections from flat CSV.

    Returns dict keyed by technology name, each containing:
    - constituent_dependencies: {components: [{name, confidence, materials: [{name, confidence, countries: [...]}]}]}
    - process_consumables:
        - assembly_consumables: [{name, confidence, extraction_provenance, rationale, countries: [...]}]
        - component_consumables: [{component, materials: [{name, confidence, extraction_provenance, rationale, countries: [...]}]}]
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    techs: dict = {}
    for row in rows:
        tech_name = row["technology"]
        if tech_name not in techs:
            techs[tech_name] = {
                "constituent_dependencies": {"components": []},
                "process_consumables": {
                    "assembly_consumables": [],
                    "component_consumables": [],
                },
            }
        tech = techs[tech_name]
        dep_type = row.get("dependency_type", "constituent")

        country_conf = row.get("country_confidence", "0") or "0"
        country_entry = {
            "name": row.get("country", ""),
            "confidence": float(country_conf) if country_conf else None,
            "source": "authoritative" if float(country_conf) >= 0.95 else "inferred",
        }

        if dep_type == "process_consumable":
            pc_component = row.get("component", "").strip()

            if not pc_component:
                # Assembly-level consumable
                pc_mats = tech["process_consumables"]["assembly_consumables"]
                existing = next((m for m in pc_mats if m["name"] == row["material"]), None)
                if existing is None:
                    mat_conf = row.get("material_confidence", "") or ""
                    existing = {
                        "name": row["material"],
                        "confidence": float(mat_conf) if mat_conf else None,
                        "extraction_provenance": row.get("extraction_provenance", "extractor"),
                        "rationale": row.get("material_reasoning", ""),
                        "countries": [],
                    }
                    pc_mats.append(existing)
                if row.get("country"):
                    existing["countries"].append(country_entry)
            else:
                # Component-level consumable
                comp_list = tech["process_consumables"]["component_consumables"]
                existing_comp = next((c for c in comp_list if c["component"] == pc_component), None)
                if existing_comp is None:
                    existing_comp = {"component": pc_component, "materials": []}
                    comp_list.append(existing_comp)
                existing_mat = next((m for m in existing_comp["materials"] if m["name"] == row["material"]), None)
                if existing_mat is None:
                    mat_conf = row.get("material_confidence", "") or ""
                    existing_mat = {
                        "name": row["material"],
                        "confidence": float(mat_conf) if mat_conf else None,
                        "extraction_provenance": row.get("extraction_provenance", "extractor"),
                        "rationale": row.get("material_reasoning", ""),
                        "countries": [],
                    }
                    existing_comp["materials"].append(existing_mat)
                if row.get("country"):
                    existing_mat["countries"].append(country_entry)
        else:
            comp_name = row.get("component", "")
            comp_list = tech["constituent_dependencies"]["components"]
            existing_comp = next((c for c in comp_list if c["name"] == comp_name), None)
            if existing_comp is None:
                comp_conf = row.get("component_confidence", "") or ""
                existing_comp = {
                    "name": comp_name,
                    "confidence": float(comp_conf) if comp_conf else None,
                    "materials": [],
                }
                comp_list.append(existing_comp)
            mat_list = existing_comp["materials"]
            existing_mat = next((m for m in mat_list if m["name"] == row["material"]), None)
            if existing_mat is None:
                mat_conf = row.get("material_confidence", "") or ""
                existing_mat = {
                    "name": row["material"],
                    "confidence": float(mat_conf) if mat_conf else None,
                    "countries": [],
                }
                mat_list.append(existing_mat)
            if row.get("country"):
                existing_mat["countries"].append(country_entry)

    return techs


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
        num_agents_component: int = 3,
        num_agents_material: int = 3,
        num_agents_country: int = 3,
        max_debate_rounds: int = 3,
        convergence_threshold: float = 0.8,
        save_transcripts: bool = True,
    ):
        """
        Initialize orchestrator with enhanced debate and error handling.

        Args:
            config: ConfigModel instance
            enable_debate: Use multi-agent debate (True) or simple voting (False)
            enable_material_debate: Use debate for materials extraction
            enable_country_debate: Use debate for country data
            num_agents_component: Number of agents for component extraction (default: 3)
            num_agents_material: Number of agents for material extraction (default: 3)
            num_agents_country: Number of agents for country data (default: 3)
            max_debate_rounds: Max debate rounds
            convergence_threshold: Convergence threshold
            save_transcripts: Save debate transcripts
        """
        self.config = config

        os.environ["STDN_MODEL"] = config.model

        self.use_debate = enable_debate
        self.use_material_debate = enable_material_debate
        self.use_country_debate = enable_country_debate
        self.num_agents_component = num_agents_component
        self.num_agents_material = num_agents_material
        self.num_agents_country = num_agents_country
        self.max_debate_rounds = max_debate_rounds
        self.convergence_threshold = convergence_threshold
        self.save_transcripts = save_transcripts
        self.component_debate_top_p = config.component_debate_top_p
        self.component_no_debate_top_p = config.component_no_debate_top_p
        self.component_debate_temperature = config.component_debate_temperature
        self.component_no_debate_temperature = config.component_no_debate_temperature
        self.material_debate_top_p = config.material_debate_top_p
        self.material_no_debate_top_p = config.material_no_debate_top_p
        self.material_debate_temperature = config.material_debate_temperature
        self.material_no_debate_temperature = config.material_no_debate_temperature
        self.country_debate_top_p = config.country_debate_top_p
        self.country_no_debate_top_p = config.country_no_debate_top_p
        self.country_debate_temperature = config.country_debate_temperature
        self.country_no_debate_temperature = config.country_no_debate_temperature

        # Checkpointing (config-controlled)
        self.enable_checkpoints = bool(getattr(config, "enable_checkpoints", False))
        self.checkpoint_interval = int(getattr(config, "checkpoint_interval", 5) or 5)
        self.checkpoint_manager: Optional[CheckpointManager] = (
            CheckpointManager(checkpoint_dir=".checkpoints") if self.enable_checkpoints else None
        )

        # Initialize dependencies
        self.deps = initialize_dependencies(config)
        self.write_nulls = config.write_nulls_to_output

        # Transcripts should be saveable regardless of whether component debate is enabled.
        # So: decouple reporter creation (controlled by save_transcripts) from debater creation
        # (controlled by enable_debate).
        if save_transcripts:
            # Find project root for transcript output
            current_dir = Path(__file__).parent
            project_root = current_dir
            for parent in [current_dir] + list(current_dir.parents):
                if (parent / "pyproject.toml").exists():
                    project_root = parent
                    break

            transcript_dir = project_root / "output" / "transcripts"

            logger.info("Debate transcripts will be saved to: %s", transcript_dir.resolve())
            self.reporter = DebateReporter(output_dir=str(transcript_dir))
        else:
            self.reporter = None

        # Initialize debate system with enhanced parameters (components only)
        if enable_debate:
            self.debater = MultiAgentDebater(
                max_rounds=max_debate_rounds,
                convergence_threshold=convergence_threshold,
                confidence_weight=0.3,  # Weight for confidence in voting
                peer_support_boost=0.15,  # Boost per supporting agent
                debate_top_p=self.component_debate_top_p,
                debate_temperature=self.component_debate_temperature,
            )
        else:
            self.debater = None

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
            enable_llm_cache=config.enable_llm_fallback_cache,
            llm_cache_dir=config.llm_fallback_cache_dir,
            llm_cache_ttl_hours=config.llm_fallback_cache_ttl_hours,
            country_no_debate_top_p=self.country_no_debate_top_p,
            country_debate_top_p=self.country_debate_top_p,
            country_no_debate_temperature=self.country_no_debate_temperature,
            country_debate_temperature=self.country_debate_temperature,
        )

        # Output directories: raw and normalized
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.timestamp = timestamp  # Store for JSON output

        # Track the per-run configuration string (e.g., v1v1v1, d3d3v3) so transcripts can include it.
        self.debate_config_str = self._build_debate_config_string()

        output_base = config.output_csv_filename
        if self.debate_config_str not in output_base:
            output_base = f"{output_base}_{self.debate_config_str}"
        output_filename = f"{output_base}_{timestamp}.csv"

        # Set up output directory structure
        self.raw_output_dir = os.path.join(config.output_dir, "raw")
        self.normalized_output_dir = os.path.join(config.output_dir, "normalized")
        os.makedirs(self.raw_output_dir, exist_ok=True)
        os.makedirs(self.normalized_output_dir, exist_ok=True)

        # Raw output file (written during pipeline)
        self.output_file = os.path.join(self.raw_output_dir, output_filename)

        # Normalized output file (written after pipeline)
        self.normalized_output_file = os.path.join(self.normalized_output_dir, output_filename)

        # Canonical vocabulary for component normalization (stored in data/ as reference data)
        self.canonical_vocab = CanonicalVocab(vocab_path="data/component_canonical_vocab.json")

        # Initialize component extractor (use component-specific model)
        self.component_extractor = ComponentExtractor(
            deps=self.deps,
            model_name=self.deps.get_component_model(),
            debater=self.debater,
            reporter=self.reporter,
            timestamp=self.timestamp,
            debate_top_p=self.component_debate_top_p,
            debate_temperature=self.component_debate_temperature,
            component_no_debate_top_p=self.component_no_debate_top_p,
            component_no_debate_temperature=self.component_no_debate_temperature,
            canonical_vocab=self.canonical_vocab,
            use_component_personas=config.component_debate_use_personas,
        )

        # Plumb the transcript config tag through to the component extractor so transcript filenames
        # can include the per-run configuration string (e.g., Smartphone_v1v1v1_YYYYMMDD_HHMMSS.txt).
        self.component_extractor.transcript_config_tag = self.debate_config_str

        # Initialize materials extractor (use materials-specific model)
        self.materials_extractor = MaterialsExtractor(
            deps=self.deps,
            model_name=self.deps.get_materials_model(),
            reporter=self.reporter,
            timestamp=self.timestamp,
            use_debate=self.use_material_debate,
            num_agents=self.num_agents_material,
            max_retries=5,
            debate_max_rounds=self.max_debate_rounds,
            debate_convergence_threshold=self.convergence_threshold,
            debate_top_p=self.material_debate_top_p,
            debate_temperature=self.material_debate_temperature,
            material_no_debate_top_p=self.material_no_debate_top_p,
            material_no_debate_temperature=self.material_no_debate_temperature,
        )

        # Initialize country data enricher
        self.country_enricher = CountryDataEnricher(
            country_repo=self.country_repo,
            reporter=self.reporter,
            write_nulls=self.write_nulls,
            use_debate=self.use_country_debate,
            num_agents=self.num_agents_country,
        )

        # Stage 2b: Process Consumables (optional)
        self.enable_process_consumables = getattr(config, 'enable_process_consumables', False)
        if self.enable_process_consumables:
            from ..orchestrator.process_consumables_extractor import ProcessConsumablesExtractor
            pc_model = getattr(config, 'process_consumables_model', None) or config.model
            self.process_consumables_extractor = ProcessConsumablesExtractor(
                deps=self.deps,
                model_name=pc_model,
            )

    def _build_debate_config_string(self) -> str:
        """
        Build a compact string encoding the debate configuration for each phase.

        Format: {component}{material}{country} where each is:
        - 'd{n}' for debate with n agents
        - 'v{n}' for voting/single-agent with n agents

        Examples:
        - 'd3d3v3' = debate(3) for components, debate(3) for materials, voting(3) for country
        - 'v1v1v1' = single agent throughout
        - 'd3v1v3' = debate(3) for components, single for materials, voting(3) for country
        """
        # Component phase: d = debate enabled, v = voting/single
        comp_prefix = "d" if self.use_debate else "v"
        comp_agents = self.num_agents_component if self.use_debate else 1
        comp_str = f"{comp_prefix}{comp_agents}"

        # Material phase: d = debate enabled, v = voting/single
        mat_prefix = "d" if self.use_material_debate else "v"
        mat_agents = self.num_agents_material if self.use_material_debate else 1
        mat_str = f"{mat_prefix}{mat_agents}"

        # Country phase: v = voting (country always uses voting, not iterative debate)
        # Always use num_agents_country directly — even when country debate is disabled,
        # the agent count is meaningful for the config type string (e.g., d3d3v3 means
        # 3 country agents doing voting).
        country_str = f"v{self.num_agents_country}"

        return f"{comp_str}{mat_str}{country_str}"

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
        enricher: Optional[CountryDataEnricher] = None,
    ) -> list[dict[str, Any]]:
        """Delegate to CountryDataEnricher.

        Args:
            enricher: Optional enricher override. When provided (e.g. in parallel mode
                      each technology task passes its own isolated enricher), this is
                      used instead of ``self.country_enricher``.
        """
        active_enricher = enricher if enricher is not None else self.country_enricher
        return await active_enricher.enrich_with_country_data(
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
        ctx: TechnologyContext,
        use_material_debate: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Process a single technology through the complete STDN pipeline."""
        logger.info("=" * 60)
        logger.info("Processing: %s", tech)
        logger.info("=" * 60)

        try:
            components_result = await self._run_component_extraction(tech, role, ctx.usage)
            if not components_result:
                logger.error("No components extracted for %s", tech)
                return None

            # Capture the transcript path written during component extraction.
            ctx.transcript_path = getattr(self.component_extractor, "last_transcript_path", None)

            (
                components,
                component_objects,
                component_confidence_map,
            ) = self._prepare_components_and_confidence(components_result)

            # Run Stage 2 (constituent materials) and Stage 2b (process consumables) in parallel
            # — both depend only on Stage 1 output (components), not on each other.
            import asyncio

            materials_task = asyncio.ensure_future(
                self._extract_materials_for_technology(components, tech, ctx.usage)
            )

            process_consumables_result = None
            if self.enable_process_consumables:
                pc_task = asyncio.ensure_future(
                    self.process_consumables_extractor.extract_process_consumables(
                        technology=tech,
                        components=components,
                        usage=ctx.usage,
                    )
                )
                materials_list, process_consumables_result = await asyncio.gather(
                    materials_task, pc_task
                )
            else:
                materials_list = await materials_task

            if not materials_list or not materials_list.component_list:
                logger.error("No materials extracted for %s", tech)
                return None

            logger.info("Extracted materials for %d components", len(materials_list.component_list))

            # Prefer the explicit transcript path captured from component extraction.
            # Fall back to globbing only if extraction didn't produce a path.
            transcript_path = ctx.transcript_path
            if not transcript_path:
                transcript_path = self._get_latest_transcript_path(tech)

            # Append materials section to the same transcript for THIS run BEFORE any country enrichment/append.
            if self.save_transcripts and self.reporter and transcript_path is not None:
                try:
                    consensus: dict[str, list[dict]] = {}
                    for cm in materials_list.component_list:
                        mats_out: list[dict] = []

                        # ComponentMaterials uses `raw_materials` with alias "materials".
                        # Depending on how the object was constructed, the attribute may be present as either.
                        raw_mats = []
                        if hasattr(cm, "raw_materials") and cm.raw_materials is not None:
                            raw_mats = cm.raw_materials or []
                        elif hasattr(cm, "materials") and cm.materials is not None:
                            raw_mats = cm.materials or []

                        for m in raw_mats:
                            mats_out.append(
                                {
                                    "name": m.name,
                                    "confidence": float(m.confidence),
                                    "reasoning": m.reasoning,
                                }
                            )

                        consensus[cm.component] = mats_out

                    # In non-debate mode, we have no debate_history/initial_proposals; append a concise materials section.
                    self.materials_extractor._append_materials_to_transcript(
                        technology=tech,
                        components=components,
                        debate_history=[],
                        consensus=consensus,
                        initial_proposals=None,
                        transcript_path=transcript_path,
                    )
                except Exception as e:
                    logger.error(
                        "Error appending materials section to transcript for %s: %s",
                        tech,
                        e,
                        exc_info=True,
                    )

            enriched_data = await self._enrich_with_country_data(
                materials_list,
                tech,
                ctx.usage,
                transcript_path=transcript_path,
                component_confidence_map=component_confidence_map,
                enricher=ctx.country_enricher,
            )

            # Stage 3 for process consumables
            pc_enriched_data = []
            if process_consumables_result and process_consumables_result.materials:
                pc_enriched_data = await ctx.country_enricher.enrich_process_consumables(
                    process_consumables=process_consumables_result,
                    technology=tech,
                    usage=ctx.usage,
                    transcript_path=transcript_path,
                )

            if self.save_transcripts and self.reporter and pc_enriched_data and transcript_path is not None:
                ctx.country_enricher.append_process_consumables_to_transcript(
                    technology=tech,
                    enriched_data=pc_enriched_data,
                    transcript_path=transcript_path,
                )

            if self.save_transcripts and self.reporter and enriched_data:
                # Prefer explicit transcript path (if known) to avoid cross-run contamination.
                if transcript_path is not None:
                    ctx.country_enricher.append_country_data_to_transcript(
                        tech, enriched_data, transcript_path=transcript_path
                    )
                else:
                    self._append_country_data_to_transcript(tech, enriched_data)

            return {
                "technology": tech,
                "components": components,
                "component_objects": component_objects,
                "materials": materials_list,
                "enriched_data": enriched_data,
                "pc_enriched_data": pc_enriched_data,
                "transcript_path": ctx.transcript_path,
            }

        except Exception as e:
            logger.error("Error processing technology %s: %s", tech, e, exc_info=True)
            return None

    async def _run_component_extraction(
        self,
        tech: str,
        role: str,
        usage: RunUsage,
    ):
        if self.use_debate:
            return await self.extract_components_with_debate(
                tech, role, usage, num_agents=self.num_agents_component
            )
        return await self.component_extractor.extract_components_simple(tech, usage)

    def _prepare_components_and_confidence(
        self,
        components_result,
    ) -> tuple[list[str], list[Any], dict[str, Dict[str, Any]]]:
        from typing import cast

        from ..agents.component_agent import ComponentWithConfidence

        if hasattr(components_result, "component_list"):
            component_objects = cast(
                list[ComponentWithConfidence],
                components_result.component_list,
            )
            components: list[str] = [comp.name for comp in component_objects]

            component_confidence_map: dict[str, Dict[str, Any]] = {}
            for comp in component_objects:
                normalized_name = comp.name.lower().strip()
                component_confidence_map[normalized_name] = {
                    "confidence": comp.confidence,
                    "reasoning": comp.reasoning,
                }

            if component_objects:
                avg_confidence = sum(comp.confidence for comp in component_objects) / len(
                    component_objects
                )
                logger.info(
                    "Extracted %d components (avg confidence: %.2f)",
                    len(components),
                    avg_confidence,
                )
            else:
                logger.info("Extracted %d components", len(components))

            return components, component_objects, component_confidence_map

        if isinstance(components_result, list):
            if components_result and hasattr(components_result[0], "name"):
                component_objects = cast(list[ComponentWithConfidence], components_result)
                components = [comp.name for comp in component_objects]
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

            logger.info("Extracted %d components", len(components))
            return components, component_objects, component_confidence_map

        components = []
        component_objects = []
        component_confidence_map = {}
        logger.info("Extracted %d components", len(components))
        return components, component_objects, component_confidence_map

    def _get_latest_transcript_path(self, tech: str) -> Optional[Path]:
        if not (self.save_transcripts and self.reporter):
            return None

        transcripts = list(self.reporter.output_dir.glob(f"{tech}_*.txt"))
        if not transcripts:
            return None

        return max(transcripts, key=lambda p: p.stat().st_mtime)

    def _append_country_data_to_transcript(
        self, technology: str, enriched_data: list[dict[str, Any]]
    ) -> None:
        """Delegate to CountryDataEnricher."""
        self.country_enricher.append_country_data_to_transcript(technology, enriched_data)

    # ========================================================================
    # Pipeline Execution
    # ========================================================================

    def _save_json_output(self, csv_path: str | None = None) -> str:
        """
        Convert a CSV output file to a JSON file.

        By default, converts the raw output CSV for this run. Callers may pass a CSV path
        explicitly (e.g., a normalized CSV) so JSON contains normalized components.

        If JSON is derived from a normalized CSV (i.e., the CSV lives under output/normalized),
        the JSON will be written alongside it in output/normalized as well.

        Args:
            csv_path: Path to CSV to convert. If None, uses this run's raw CSV output.

        Returns:
            Path to saved JSON file
        """
        source_csv = csv_path or self.output_file

        # Build structured JSON with typed dependency sections
        data = build_structured_json(source_csv)

        # Create JSON filename from the source CSV basename
        # Example:
        #   stdns_output_d3d1v1_YYYYMMDD_HHMMSS.csv -> stdns_output_d3d1v1_YYYYMMDD_HHMMSS.json
        base = os.path.splitext(os.path.basename(source_csv))[0]
        json_filename = f"{base}.json"

        # Write JSON next to the normalized CSV when converting normalized output,
        # otherwise write to the base output dir.
        source_csv_norm = os.path.normpath(source_csv)
        normalized_dir_norm = os.path.normpath(self.normalized_output_dir)
        if os.path.commonpath([source_csv_norm, normalized_dir_norm]) == normalized_dir_norm:
            json_filepath = os.path.join(self.normalized_output_dir, json_filename)
        else:
            json_filepath = os.path.join(self.config.output_dir, json_filename)

        # Save as formatted JSON
        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return json_filepath

    async def _normalize_output(self) -> str:
        """
        Normalize component and material names for all raw CSVs with the same debate configuration.

        This method:
        1. Finds all raw CSV files matching the current debate config (e.g., d3d3v3)
        2. Extracts unique component names across ALL matching files
        3. Normalizes unknown component names via LLM and updates the vocabulary
        4. Normalizes process consumable material names (strip parenthetical qualifiers)
        5. Normalizes material name casing across all rows
        6. Re-normalizes ALL matching files with the complete vocabulary

        This ensures consistency across all runs with the same configuration,
        even when new component names are discovered in later runs.

        Returns:
            Path to normalized output file for the current run
        """
        import re
        from glob import glob

        import pandas as pd

        logger.info("=" * 60)
        logger.info("Post-Processing: Component Name Normalization")
        logger.info("=" * 60)

        # Find all raw CSV files with the same debate configuration
        debate_config_str = self._build_debate_config_string()
        raw_pattern = os.path.join(
            self.raw_output_dir, f"{self.config.output_csv_filename}_{debate_config_str}_*.csv"
        )
        matching_files = sorted(glob(raw_pattern))

        if not matching_files:
            logger.warning("No files found matching pattern: %s", raw_pattern)
            return self.output_file

        logger.info("Found %d files with config '%s'", len(matching_files), debate_config_str)

        # Extract unique component names from ALL matching files
        all_unique_components: set = set()
        for csv_path in matching_files:
            try:
                df = pd.read_csv(csv_path)
                if "component" in df.columns:
                    components = df["component"].dropna().unique()
                    all_unique_components.update(components)
            except Exception as e:
                logger.warning(f"Error reading {csv_path}: {e}")

        unique_components = list(all_unique_components)
        logger.info("Found %d unique component names across all files", len(unique_components))

        # Check vocab for cached mappings
        cached, unknown = self.canonical_vocab.lookup_batch(unique_components)
        logger.info("  %d already in vocabulary", len(cached))
        logger.info("  %d need LLM normalization", len(unknown))

        # Normalize unknown names with LLM
        if unknown:
            new_mappings = await self._normalize_components_with_llm(unknown)
            self.canonical_vocab.add_mappings(new_mappings)
            self.canonical_vocab.save()
            logger.info("  Added %d new mappings to vocabulary", len(new_mappings))

        # Build complete mapping from vocabulary (use all known mappings)
        all_mappings = dict(self.canonical_vocab.mappings)

        # Create lowercase lookup for case-insensitive matching
        lower_mappings = {k.lower(): v for k, v in all_mappings.items()}

        # Re-normalize ALL matching files
        logger.info("Re-normalizing %d files...", len(matching_files))
        for csv_path in matching_files:
            try:
                df = pd.read_csv(csv_path)
                if "component" not in df.columns:
                    continue

                # Apply component normalization
                # NOTE: Process consumable rows have empty component fields;
                # the pd.notna(x) check below ensures they pass through untouched.
                original_components = df["component"].copy()
                df["component"] = df["component"].apply(
                    lambda x: lower_mappings.get(str(x).lower(), x) if pd.notna(x) else x
                )

                # Normalize process consumable material names:
                # 1. Strip parenthetical qualifiers (e.g., "Helium (for leak testing)" → "Helium")
                # 2. Merge physical-form variants into base material
                if "dependency_type" in df.columns and "material" in df.columns:
                    pc_mask = df["dependency_type"] == "process_consumable"
                    original_materials = df["material"].copy()
                    df.loc[pc_mask, "material"] = (
                        df.loc[pc_mask, "material"]
                        .apply(lambda x: re.sub(r"\s*\(.*\)\s*$", "", str(x)).strip() if pd.notna(x) else x)
                    )
                    # Merge physical-form variants into base materials
                    form_mappings = {
                        "Liquid Helium": "Helium",
                        "Liquid Nitrogen": "Nitrogen",
                        "Cryogenic liquid nitrogen": "Nitrogen",
                        "Cryogenic liquids": "Nitrogen",
                        "Compressed Nitrogen or Air": "Nitrogen",
                    }
                    df.loc[pc_mask, "material"] = (
                        df.loc[pc_mask, "material"].replace(form_mappings)
                    )

                    # Split compound gas materials into separate rows
                    gas_splits = {
                        "Helium and Nitrogen gases": ["Helium", "Nitrogen"],
                        "Argon and Nitrogen": ["Argon", "Nitrogen"],
                        "Nitrogen and Argon": ["Argon", "Nitrogen"],
                        "Nitrogen and Argon gases": ["Argon", "Nitrogen"],
                        "Gases such as nitrogen and argon": ["Argon", "Nitrogen"],
                        "High purity nitrogen and argon": ["Argon", "Nitrogen"],
                        "Cooling gases": ["Helium", "Nitrogen"],
                    }
                    split_rows = []
                    split_mask = pc_mask & df["material"].isin(gas_splits)
                    for idx, row in df[split_mask].iterrows():
                        targets = gas_splits[row["material"]]
                        for target in targets:
                            new_row = row.copy()
                            new_row["material"] = target
                            split_rows.append(new_row)
                    if split_rows:
                        df = df[~split_mask]
                        df = pd.concat([df, pd.DataFrame(split_rows)], ignore_index=True)
                        pc_mask = df["dependency_type"] == "process_consumable"

                    # Merge compound material names into canonical base materials
                    compound_mappings = {
                        "Acetone and IPA": "Cleaning solvents",
                        "Acetone and Isopropyl alcohol": "Cleaning solvents",
                        "Cleaning Solvents and Detergents": "Cleaning solvents",
                        "Cleaning acids and bases": "Cleaning solvents",
                        "Cleaning detergents and surfactants": "Cleaning solvents",
                        "Surface cleaning detergents and solvents": "Cleaning solvents",
                        "Solvents for cleaning and degreasing": "Cleaning solvents",
                        "Protective film and cleaning solvents": "Cleaning solvents",
                        "Flux Removers and Degreasers": "Cleaning solvents",
                        "Photoresist and developers": "Photoresists and developers",
                        "Photoresist and Developer Chemicals": "Photoresists and developers",
                        "Cutting fluids and coolants": "Cutting fluids",
                        "Cutting fluids and lubricants": "Cutting fluids",
                        "Metal cutting fluids and lubricants": "Cutting fluids",
                        "Cutting and machining lubricants": "Cutting fluids",
                        "Lubricants and cutting fluids": "Lubricants",
                        "Lubricants and greases": "Lubricants",
                        "Lubricants and release agents": "Lubricants",
                        "Lubricants and anti-seize compounds": "Lubricants",
                        "Lubricants and anti-seize agents": "Lubricants",
                        "Anti-seize and lubricants": "Lubricants",
                        "Anti-seize compounds and lubricants": "Lubricants",
                        "Lubricants and hydraulic fluids": "Lubricants",
                        "Lubricants and vacuum pump oils": "Lubricants",
                        "Lubricants for fan motors and bearings": "Lubricants",
                        "Lubricants for fans and pumps": "Lubricants",
                        "Etchants and cleaning acids": "Etchants",
                        "Etchants and cleaning chemicals": "Etchants",
                        "Etch acids and gases": "Etchants",
                        "Etch chemistries and cleaning acids": "Etchants",
                        "Flux and solder paste": "Flux",
                        "Flux and solder pastes": "Flux",
                        "Flux and soldering materials": "Flux",
                        "Flux and adhesives": "Flux",
                        "Adhesives and Epoxy": "Adhesives",
                        "Adhesives and bonding agents": "Adhesives",
                        "Adhesives and encapsulants": "Adhesives",
                        "Adhesives and epoxy resins": "Adhesives",
                        "Adhesives and glue consumables": "Adhesives",
                        "Adhesives and release agents": "Adhesives",
                        "Adhesives and sealants": "Adhesives",
                        "Adhesives and surface primers": "Adhesives",
                        "Epoxy and Adhesives": "Adhesives",
                        "Sealants and adhesives": "Adhesives",
                        "Potting compounds and adhesives": "Adhesives",
                        "Paints and coatings": "Paints and surface coatings",
                        "Paints and Surface Coatings": "Paints and surface coatings",
                        "Paints and coating chemicals": "Paints and surface coatings",
                        "Paints and surface preparation chemicals": "Paints and surface coatings",
                        "Paints and surface treatment chemicals": "Paints and surface coatings",
                        "Painting and coating chemicals": "Paints and surface coatings",
                        "Painting and coating materials": "Paints and surface coatings",
                        "Paint and coating materials": "Paints and surface coatings",
                        "Paint solvents and coatings": "Paints and surface coatings",
                    }
                    df.loc[pc_mask, "material"] = (
                        df.loc[pc_mask, "material"].replace(compound_mappings)
                    )
                    # Normalize material name casing (first-seen wins)
                    mat_canonical: dict[str, str] = {}
                    for mat in df["material"].dropna().unique():
                        key = str(mat).lower()
                        if key not in mat_canonical:
                            mat_canonical[key] = mat
                    df["material"] = df["material"].apply(
                        lambda x: mat_canonical.get(str(x).lower(), x) if pd.notna(x) else x
                    )
                    # Count changes (use len difference + value changes on shared index)
                    rows_added = len(df) - len(original_materials)
                    shared = original_materials.index.intersection(df.index)
                    mat_changes = int((original_materials.loc[shared] != df["material"].loc[shared]).sum()) + abs(rows_added)
                else:
                    mat_changes = 0

                # Count changes
                shared_comp = original_components.index.intersection(df.index)
                comp_changes = int((original_components.loc[shared_comp] != df["component"].loc[shared_comp]).sum())

                # Save to normalized directory
                normalized_path = os.path.join(
                    self.normalized_output_dir, os.path.basename(csv_path)
                )
                df.to_csv(normalized_path, index=False)
                logger.info(
                    f"  {os.path.basename(csv_path)}: "
                    f"{comp_changes} components, {mat_changes} materials normalized"
                )

            except Exception as e:
                logger.error("Error normalizing %s: %s", csv_path, e)

        logger.info("Normalized outputs saved to: %s", self.normalized_output_dir)

        return self.normalized_output_file

    async def _normalize_components_with_llm(self, unknown_names: List[str]) -> Dict[str, str]:
        """
        Use LLM to normalize unknown component names.

        Args:
            unknown_names: List of component names not in vocabulary

        Returns:
            Dict mapping raw names to canonical names
        """
        from pydantic import BaseModel, Field
        from pydantic_ai import Agent

        if not unknown_names:
            return {}

        logger.info("Sending %d unknown names to LLM for normalization", len(unknown_names))

        class ComponentMapping(BaseModel):
            mappings: Dict[str, str] = Field(
                description="Dict mapping each input component name to its canonical form"
            )

        system_prompt = """You are a component name normalizer for supply chain analysis.

Your task is to map raw component names to canonical forms while preserving material-relevant specificity.

RULES:
1. Consolidate naming variations to a single canonical form
   - "Li-ion Battery", "Lithium Ion Battery", "Battery Pack (Li-ion)" → "Lithium-ion Battery"
   - "LCD Panel", "LCD Display", "Liquid Crystal Display" → "LCD Display"
   - "CPU", "Central Processing Unit", "Processor" → "CPU"

2. PRESERVE material-relevant distinctions - these affect supply chain materials:
   - Battery chemistry: Lithium-ion, Lead-acid, NiMH, LFP, Solid-state
   - Display technology: OLED, LCD, LED, Mini-LED, Micro-LED
   - Semiconductor type: Silicon, GaN, SiC when specified
   - Memory type: DRAM, NAND Flash, NOR Flash, SRAM

3. AVOID overly generic names:
   - Do NOT use just "Battery" - specify chemistry if known
   - Do NOT use just "Display" - specify technology if known
   - Do NOT use just "Chip" - specify function (Memory Chip, Power IC, etc.)

4. Use Title Case for canonical names (e.g., "Lithium-ion Battery", "OLED Display")

5. Output must be in English only. Translate non-English names.

For each input name, output the canonical form it should map to."""

        names_list = "\n".join(f"- {name}" for name in unknown_names)
        prompt = f"Normalize these component names to canonical forms:\n\n{names_list}"

        # Use a dedicated, more reliable model for schema-valid normalization mappings.
        #
        # Preference order:
        # 1) Config-driven dependency model (self.deps.get_component_normalization_model)
        # 2) Environment override (STDN_COMPONENT_NORMALIZATION_MODEL)
        # 3) Hard default (openai:gpt-4.1)
        normalization_model = None
        if hasattr(self.deps, "get_component_normalization_model"):
            try:
                normalization_model = self.deps.get_component_normalization_model()
            except Exception:
                normalization_model = None

        if not normalization_model or not str(normalization_model).strip():
            normalization_model = (
                os.environ.get("STDN_COMPONENT_NORMALIZATION_MODEL", "openai:gpt-4.1").strip()
                or "openai:gpt-4.1"
            )

        # pydantic_ai defaults retries=1; raise this to reduce premature failures.
        retries_env = os.environ.get("STDN_AGENT_RETRIES")
        retries = 5
        if retries_env is not None:
            try:
                retries = int(retries_env)
            except ValueError:
                retries = 5

        agent = Agent(
            model=normalization_model,
            output_type=ComponentMapping,
            deps_type=STDNDependencies,
            system_prompt=system_prompt,
            retries=retries,
            output_retries=retries,
        )

        try:
            result = await agent.run(prompt, deps=self.deps)
            if result and result.output:
                mappings = result.output.mappings
                logger.info("LLM returned %d mappings", len(mappings))
                return mappings
        except Exception as e:
            logger.error("LLM normalization failed: %s", e)

        # Fallback: return names as-is with basic cleanup
        logger.warning("Falling back to basic normalization")
        return {name: name.strip().title() for name in unknown_names}

    def _write_usage_json(
        self,
        contexts: "list[TechnologyContext]",
        total_usage: RunUsage,
    ) -> None:
        """Write a per-technology + aggregate usage JSON sidecar file.

        Non-fatal: logs a warning and returns if any error occurs.

        Args:
            contexts: Per-technology TechnologyContext objects (each with .tech_name and .usage).
                      Pass an empty list when per-tech breakdown is not available.
            total_usage: Aggregated RunUsage for the full run.
        """
        try:
            usage_log_dir = Path(self.config.output_dir) / "usage_logs"
            usage_log_dir.mkdir(parents=True, exist_ok=True)

            usage_file = usage_log_dir / f"usage_{self.debate_config_str}_{self.timestamp}.json"

            def _usage_dict(u: RunUsage) -> dict:
                return {
                    "input_tokens": u.input_tokens or 0,
                    "output_tokens": u.output_tokens or 0,
                    "total_tokens": u.total_tokens or 0,
                    "requests": u.requests or 0,
                    "cache_read_tokens": getattr(u, "cache_read_tokens", None) or 0,
                    "cache_write_tokens": getattr(u, "cache_write_tokens", None) or 0,
                }

            per_technology = {
                ctx.tech_name: _usage_dict(ctx.usage)
                for ctx in contexts
                if ctx.tech_name is not None
            }

            payload = {
                "run_metadata": {
                    "config_marker": self.debate_config_str,
                    "timestamp": self.timestamp,
                    "model": self.config.model,
                    "output_file": str(self.output_file),
                },
                "per_technology": per_technology,
                "aggregate": _usage_dict(total_usage),
            }

            usage_file.write_text(json.dumps(payload, indent=2))
            logger.info("Usage log written to: %s", usage_file)

        except Exception as exc:
            logger.warning("Failed to write usage log (non-fatal): %s", exc)

    async def _run_parallel(
        self,
        technologies: List[str],
        role: str,
        domain: str,
        tech_roles: Optional[Dict[str, str]],
        tech_domains: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Process technologies concurrently with semaphore-based throttling.

        Each technology gets its own CountryDataRepository and CountryDataEnricher
        to avoid shared-state races. Results are written to CSV in the original
        technology list order for deterministic output.
        """

        CSV_FIELDNAMES = [
            "technology", "component", "component_confidence", "component_reasoning",
            "material", "material_confidence", "material_reasoning", "hs_code",
            "country", "meas_unit", "amount", "percentage",
            "country_confidence", "country_reasoning", "dependency_type", "extraction_provenance",
        ]

        semaphore = asyncio.Semaphore(self.config.max_concurrent_technologies)
        checkpoint_lock = asyncio.Lock()

        # Checkpoint-based resume
        checkpoint_path = Path(self.raw_output_dir) / "parallel_checkpoint.json"
        completed_techs: set[str] = set()
        if checkpoint_path.exists():
            data = json.loads(checkpoint_path.read_text())
            completed_techs = set(data.get("completed_technologies", []))
            logger.info(
                "Resuming parallel run: %d completed, %d remaining",
                len(completed_techs),
                len([t for t in technologies if t not in completed_techs]),
            )

        remaining_technologies = [t for t in technologies if t not in completed_techs]

        # Collect results and failures keyed by technology name
        all_results: Dict[str, Dict[str, Any]] = {}
        failed_technologies: Dict[str, str] = {}
        contexts: list[TechnologyContext] = []
        successful = 0
        failed = 0

        async def _process_one(tech: str) -> None:
            nonlocal successful, failed

            _current_technology.set(tech)

            tech_role = tech_roles.get(tech, role) if tech_roles else role
            tech_domain = tech_domains.get(tech, domain) if tech_domains else domain

            # Per-technology isolated state
            tech_repo = CountryDataRepository(
                database_path=self.config.usgs_database,
                deps=self.deps,
                top_n=5,
                use_llm_fallback=True,
                enable_llm_cache=self.config.enable_llm_fallback_cache,
                llm_cache_dir=self.config.llm_fallback_cache_dir,
                llm_cache_ttl_hours=self.config.llm_fallback_cache_ttl_hours,
                country_no_debate_top_p=self.country_no_debate_top_p,
                country_debate_top_p=self.country_debate_top_p,
                country_no_debate_temperature=self.country_no_debate_temperature,
                country_debate_temperature=self.country_debate_temperature,
            )
            tech_enricher = CountryDataEnricher(
                country_repo=tech_repo,
                reporter=self.reporter,
                write_nulls=self.write_nulls,
                use_debate=self.use_country_debate,
                num_agents=self.num_agents_country,
            )
            ctx = TechnologyContext(
                country_repo=tech_repo,
                country_enricher=tech_enricher,
                tech_name=tech,
            )
            contexts.append(ctx)

            # Set up per-technology log file
            tech_log_dir = Path("logs/technologies")
            tech_log_dir.mkdir(parents=True, exist_ok=True)
            safe_name = tech.replace("/", "_").replace(" ", "_")
            tech_handler = logging.FileHandler(tech_log_dir / f"{safe_name}.log")
            tech_handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            tech_handler.addFilter(_TechnologyLogFilter(tech))
            root_logger = logging.getLogger()
            root_logger.addHandler(tech_handler)

            t0 = time.monotonic()
            try:
                async with semaphore:
                    result = await self.process_technology(
                        tech,
                        tech_role,
                        tech_domain,
                        ctx,
                        use_material_debate=self.use_material_debate,
                    )

                if result and result["enriched_data"]:
                    all_results[tech] = result
                    successful += 1
                    elapsed = time.monotonic() - t0
                    logger.info(
                        "[%d/%d] %s completed (%.1fs)",
                        successful + failed, len(remaining_technologies), tech, elapsed,
                    )

                    # Checkpoint under lock
                    async with checkpoint_lock:
                        completed_techs.add(tech)
                        checkpoint_data = {
                            "completed_technologies": sorted(completed_techs),
                            "timestamp": datetime.now().isoformat(),
                        }
                        tmp = checkpoint_path.with_suffix(".tmp")
                        tmp.write_text(json.dumps(checkpoint_data, indent=2))
                        tmp.rename(checkpoint_path)
                else:
                    failed += 1
                    failed_technologies[tech] = "No enriched data returned"
                    logger.warning("Failed to process: %s", tech)

            except Exception as e:
                failed += 1
                failed_technologies[tech] = str(e)
                logger.error("Error processing %s: %s", tech, e, exc_info=True)
            finally:
                root_logger.removeHandler(tech_handler)
                tech_handler.close()

        # Run all technologies concurrently (semaphore limits actual concurrency)
        await asyncio.gather(*[_process_one(tech) for tech in remaining_technologies])

        # Write combined CSV in original technology list order for determinism
        with open(self.output_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for tech in technologies:  # original order (including previously completed)
                result = all_results.get(tech)
                if not result:
                    continue
                for row in result["enriched_data"]:
                    row["dependency_type"] = "constituent"
                    row["extraction_provenance"] = ""
                    writer.writerow(row)
                for row in result.get("pc_enriched_data", []):
                    writer.writerow(row)

        # Aggregate usage from all per-technology contexts
        total_usage = RunUsage()
        for ctx in contexts:
            total_usage.incr(ctx.usage)

        logger.info("=" * 60)
        logger.info("Parallel STDN Generation Completed: %s", datetime.now())
        logger.info("=" * 60)
        logger.info("Successfully processed: %d/%d technologies", successful, len(technologies))
        logger.info("Raw output saved to: %s", self.output_file)
        logger.debug("Aggregated usage: %s", total_usage)

        # Write per-technology usage JSON sidecar (non-fatal)
        self._write_usage_json(contexts, total_usage)

        # Clean up checkpoint on full success
        if checkpoint_path.exists():
            checkpoint_path.unlink()

        return {
            "successful": successful,
            "failed": failed,
            "total": len(technologies),
            "output_file": self.output_file,
            "failed_technologies": failed_technologies,
        }

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

        logger.info("=" * 60)
        logger.info("STDN Generation Started: %s", datetime.now())
        logger.info("=" * 60)
        if self.use_debate:
            logger.info("Multi-agent debate ENABLED")
            logger.info("  Max rounds: %d", self.max_debate_rounds)
            logger.info("  Convergence threshold: %.2f", self.convergence_threshold)
            logger.info("  Save transcripts: %s", self.save_transcripts)
        logger.info("%d technologies from %s", len(technologies), self.config.tech_list_path)

        successful = 0
        failed = 0

        # Checkpoint/resume setup
        resume_index = 0
        processed_techs: list[str] = []
        checkpoint_config: Optional[dict[str, Any]] = None
        if self.enable_checkpoints and self.checkpoint_manager:
            # Use a small, deterministic config signature so restarts can find the same checkpoint.
            checkpoint_config = {
                "import_tech_list": self.config.tech_list_path,
                "debate_config": getattr(self, "debate_config_str", None),
                "output_file": self.output_file,
            }
            checkpoint = self.checkpoint_manager.load_checkpoint(checkpoint_config)
            if checkpoint:
                resume_index = int(checkpoint.get("current_index", 0) or 0)
                processed_techs = list(checkpoint.get("processed_techs", []) or [])
                logger.info(
                    "Resuming from checkpoint: index=%d (%.1f%%) processed=%d/%d",
                    resume_index,
                    float(checkpoint.get("progress_pct", 0.0) or 0.0),
                    resume_index,
                    len(technologies),
                )

        # Initialize CSV file with headers
        # - Fresh run (no checkpoint): start a new file
        # - Resume run (checkpoint present): keep existing file and continue appending
        csv_mode = "a" if resume_index > 0 else "w"
        if resume_index == 0:
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
                        "dependency_type",
                        "extraction_provenance",
                    ],
                )
                writer.writeheader()

        # Parallel technology processing branch
        if self.config.parallel_technologies:
            logger.info(
                "Parallel mode enabled (max_concurrent=%d)",
                self.config.max_concurrent_technologies,
            )
            parallel_result = await self._run_parallel(
                technologies, role, domain, tech_roles, tech_domains,
            )

            # Post-processing: normalization and JSON output
            normalized_file = None
            if parallel_result["successful"] > 0:
                skip_norm_env = os.getenv("SKIP_POSTPROCESS_NORMALIZATION", "").strip().lower()
                skip_postprocess_norm_env = skip_norm_env in ("1", "true", "yes", "y", "on")
                skip_postprocess_norm = (
                    bool(getattr(self.config, "skip_postprocess_normalization", False))
                    or skip_postprocess_norm_env
                )

                if skip_postprocess_norm:
                    logger.info("Skipping post-processing normalization (parallel mode)")
                else:
                    normalized_file = await self._normalize_output()

                skip_json = bool(getattr(self.config, "skip_json_output", False))
                if skip_json:
                    logger.info("Skipping JSON output (parallel mode)")
                else:
                    json_source_csv = normalized_file or self.output_file
                    json_path = self._save_json_output(csv_path=json_source_csv)
                    logger.info("JSON output written to: %s", json_path)

            parallel_result["normalized_output_file"] = normalized_file
            return parallel_result

        # Process each technology (with optional resume)
        for idx, tech in enumerate(technologies):
            if idx < resume_index:
                continue

            # Use tech-specific role/domain if provided, otherwise use defaults
            tech_role = tech_roles.get(tech, role) if tech_roles else role
            tech_domain = tech_domains.get(tech, domain) if tech_domains else domain

            ctx = TechnologyContext(
                country_repo=self.country_repo,
                country_enricher=self.country_enricher,
                usage=usage,
            )
            result = await self.process_technology(
                tech,
                tech_role,  # ← Use tech-specific role
                tech_domain,  # ← Use tech-specific domain
                ctx,
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
                            "dependency_type",
                            "extraction_provenance",
                        ],
                    )
                    for row in result["enriched_data"]:
                        row["dependency_type"] = "constituent"
                        row["extraction_provenance"] = ""
                        writer.writerow(row)
                    for row in result.get("pc_enriched_data", []):
                        writer.writerow(row)  # already has dependency_type and extraction_provenance

                logger.info("Output written to %s", self.output_file)
                logger.info("Successfully processed: %s", tech)
                successful += 1
                processed_techs.append(tech)
            else:
                logger.warning("Failed to process: %s", tech)
                failed += 1

            # Save checkpoint periodically (after completing a technology)
            if self.enable_checkpoints and self.checkpoint_manager:
                if (idx + 1) % max(1, self.checkpoint_interval) == 0:
                    try:
                        # Reuse the precomputed checkpoint_config so the checkpoint key remains stable.
                        if checkpoint_config is None:
                            checkpoint_config = {
                                "import_tech_list": self.config.tech_list_path,
                                "debate_config": getattr(self, "debate_config_str", None),
                                "output_file": self.output_file,
                            }
                        self.checkpoint_manager.save_checkpoint(
                            config=checkpoint_config,
                            processed_techs=processed_techs,
                            results=[],
                            current_index=idx + 1,
                            total_count=len(technologies),
                        )
                        logger.info(
                            "Saved checkpoint (%d/%d) to %s",
                            idx + 1,
                            len(technologies),
                            self.checkpoint_manager._get_checkpoint_file(checkpoint_config),
                        )
                    except Exception as e:
                        logger.warning("Failed to save checkpoint: %s", e)

        logger.info("=" * 60)
        logger.info("STDN Generation Completed: %s", datetime.now())
        logger.info("=" * 60)
        logger.info("Successfully processed: %d/%d technologies", successful, len(technologies))
        logger.info("Raw output saved to: %s", self.output_file)
        if self.use_debate and self.reporter:
            logger.info("Debate transcripts saved to: %s", self.reporter.output_dir)

        # On successful completion, delete the checkpoint so subsequent runs start fresh
        # (and only resume if interrupted), unless config.keep_checkpoints_on_success is true.
        keep_on_success = bool(getattr(self.config, "keep_checkpoints_on_success", False))
        if (
            self.enable_checkpoints
            and self.checkpoint_manager
            and checkpoint_config is not None
            and failed == 0
            and successful == len(technologies)
        ):
            if keep_on_success:
                logger.info(
                    "Keeping checkpoint after successful completion (config.keep_checkpoints_on_success=True)."
                )
            else:
                try:
                    deleted = self.checkpoint_manager.delete_checkpoint(checkpoint_config)
                    if deleted:
                        logger.info("Deleted checkpoint after successful completion.")
                except Exception as e:
                    logger.warning("Failed to delete checkpoint after completion: %s", e)

        logger.debug("Usage: %s", usage)

        # Write aggregate usage JSON sidecar (non-fatal).
        # Sequential path shares a single RunUsage across all techs, so only aggregate is available.
        self._write_usage_json([], usage)

        normalized_file = None
        if successful > 0:
            # Parallel runs should avoid per-process post-processing and JSON.
            # Prefer config flags (set by parallel runner) with env var as a backstop.
            skip_norm_env = os.getenv("SKIP_POSTPROCESS_NORMALIZATION", "").strip().lower()
            skip_postprocess_norm_env = skip_norm_env in ("1", "true", "yes", "y", "on")
            skip_postprocess_norm = (
                bool(getattr(self.config, "skip_postprocess_normalization", False))
                or skip_postprocess_norm_env
            )

            if skip_postprocess_norm:
                logger.info(
                    "Skipping post-processing normalization (config.skip_postprocess_normalization=%s, SKIP_POSTPROCESS_NORMALIZATION=%s)",
                    getattr(self.config, "skip_postprocess_normalization", False),
                    skip_norm_env,
                )
            else:
                # Run component name normalization
                normalized_file = await self._normalize_output()

            # JSON should contain normalized components. In parallel mode, JSON generation
            # should be deferred until a shared normalization pass completes.
            skip_json = bool(getattr(self.config, "skip_json_output", False))
            if skip_json:
                logger.info(
                    "Skipping JSON output generation due to config.skip_json_output=%s",
                    getattr(self.config, "skip_json_output", False),
                )
            else:
                # Convert CSV to JSON (JSON contains normalized components when available)
                json_source_csv = normalized_file or self.output_file
                json_path = self._save_json_output(csv_path=json_source_csv)
                logger.info("JSON output written to: %s", json_path)

        return {
            "successful": successful,
            "failed": failed,
            "total": len(technologies),
            "output_file": self.output_file,
            "normalized_output_file": normalized_file,
        }


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "STDNOrchestrator",
]
