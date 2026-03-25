"""
Pydantic data models for STDN generation pipeline

This module defines the configuration and dependency models used throughout
the STDN generation system:
- STDNDependencies: Runtime dependencies passed to agents
- ConfigModel: Configuration file validation and settings

The ConfigModel includes computed properties for backward compatibility
with code expecting different field names.
"""

from dataclasses import dataclass
from typing import Literal, Optional

import ollama
from pydantic import BaseModel, ConfigDict, Field, computed_field

# ============================================================================
# Runtime Dependencies
# ============================================================================


@dataclass
class STDNDependencies:
    """
    Dependencies passed to STDN agents during execution.

    This dataclass provides runtime context to agents including:
    - Material ontology data (various formats)
    - Country production data
    - Database client connections
    - Model configuration (default and per-agent)

    Attributes:
        material_ontology: Comma-separated string of material names
        material_ontology_dict: Material name to ID mapping
        material_ontology_list: List of material names for validation
        years_to_query: List of years for historical data queries
        client: Ollama client for LLM inference
        model: Default model identifier (e.g., "qwen2.5:7b")
        component_model: Model for component extraction (defaults to model)
        materials_model: Model for materials extraction (defaults to model)
        country_model: Model for country data (defaults to model)
        top_p: Top-p sampling parameter for generation
    """

    material_ontology: str
    material_ontology_dict: dict
    material_ontology_list: list[str]
    years_to_query: list[int]
    client: ollama.Client
    model: str
    top_p: float
    temperature: Optional[float] = None
    # Per-agent models (default to self.model if not specified)
    component_model: Optional[str] = None
    materials_model: Optional[str] = None
    country_model: Optional[str] = None
    process_consumables_model: Optional[str] = None

    # Model specifically for semantic component-name normalization mappings
    component_normalization_model: Optional[str] = None

    def get_component_model(self) -> str:
        """Get the model to use for component extraction."""
        return self.component_model or self.model

    def get_component_normalization_model(self) -> str:
        """
        Get the model to use for semantic component-name normalization mappings.

        Preference order:
        1) component_normalization_model
        2) component_model
        3) model
        """
        return self.component_normalization_model or self.get_component_model()

    def get_materials_model(self) -> str:
        """Get the model to use for materials extraction."""
        return self.materials_model or self.model

    def get_country_model(self) -> str:
        """Get the model to use for country data."""
        return self.country_model or self.model

    def get_process_consumables_model(self) -> str:
        """Get the model to use for process consumables extraction."""
        return self.process_consumables_model or self.model


# ============================================================================
# Configuration Model
# ============================================================================


class ConfigModel(BaseModel):
    """
    Configuration validation model for STDN generation.
    """

    # ========================================================================
    # Agent Runtime / Reliability Settings
    # ========================================================================

    agent_retries: int = Field(
        default=5,
        ge=0,
        description=(
            "Default number of retries for pydantic_ai Agent output validation / tool-call recovery. "
            "Used when agent construction code reads this field."
        ),
    )

    # ========================================================================
    # Required Fields
    # ========================================================================

    import_tech_list: str = Field(
        description="Path to CSV file containing technology list (column: 'tech')"
    )
    model: str = Field(description="Model identifier (e.g., 'ollama:qwen2.5:7b', 'openai:gpt-4')")
    output_dir: str = Field(default="./output", description="Directory path for output files")
    output_csv_filename: str = Field(
        default="stdns_output", description="Output CSV filename (without .csv extension)"
    )

    # ========================================================================
    # Post-Processing / Output Control (useful for parallel child runs)
    # ========================================================================

    # ========================================================================
    # Checkpointing / Resume Control
    # ========================================================================

    keep_checkpoints_on_success: bool = Field(
        default=False,
        description=(
            "If false (default), delete the run's checkpoint file after a successful completion so subsequent runs "
            "start fresh. If true, retain checkpoints even on success (useful for audit/debugging)."
        ),
    )

    skip_postprocess_normalization: bool = Field(
        default=False,
        description=(
            "Skip post-processing component name normalization at the end of a run. "
            "Recommended for parallel child runs; run scripts/normalize_outputs.py once after all runs finish."
        ),
    )
    skip_json_output: bool = Field(
        default=False,
        description=(
            "Skip JSON output generation at the end of a run. "
            "Recommended for parallel child runs when JSON should be generated from normalized CSVs."
        ),
    )

    # ========================================================================
    # Per-Agent Model Configuration
    # ========================================================================

    component_model: Optional[str] = Field(
        default=None,
        description="Model for component extraction (defaults to 'model' if not set)",
    )
    materials_model: Optional[str] = Field(
        default=None,
        description="Model for materials extraction (defaults to 'model' if not set)",
    )
    country_model: Optional[str] = Field(
        default=None,
        description="Model for country data (defaults to 'model' if not set)",
    )
    process_consumables_model: Optional[str] = Field(
        default=None,
        description="Model for process consumables extraction (defaults to 'model' if not set)",
    )
    enable_process_consumables: bool = Field(
        default=False,
        description="Enable Stage 2b: process consumables extraction",
    )
    parallel_technologies: bool = Field(
        default=False,
        description="Enable parallel processing of technologies within a single run",
    )
    max_concurrent_technologies: int = Field(
        default=10,
        ge=1,
        le=200,
        description="Max concurrent technologies when parallel_technologies is enabled",
    )

    # ========================================================================
    # Normalization Model Configuration
    # ========================================================================

    component_normalization_model: Optional[str] = Field(
        default=None,
        description=(
            "Model for semantic component-name normalization mapping (defaults to "
            "'component_model' then 'model' if not set)."
        ),
    )

    # ========================================================================
    # Material Ontology Settings
    # ========================================================================

    materials_hs_codes_listing: str = Field(
        default="./data/hs_codes_and_usgs_names.csv",
        description="Path to CSV mapping HS codes to USGS material names",
    )
    materials_column_name: str = Field(
        default="Elements_Compounds",
        description="Column name in HS codes file containing material names",
    )

    # ========================================================================
    # Country Data Settings
    # ========================================================================

    usgs_database: Optional[str] = Field(
        default="./data/world_mineral_commodity_reports_2022-2025_v8.db",
        description="Path to USGS mineral commodities SQLite database",
    )
    top_n_countries: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top producing countries to include per material",
    )
    enable_llm_fallback_cache: bool = Field(
        default=True,
        description="Enable persistent caching of successful LLM fallback debates",
    )
    llm_fallback_cache_dir: str = Field(
        default="./data/llm_fallback_cache",
        description="Directory path for LLM fallback cache files",
    )
    llm_fallback_cache_ttl_hours: int = Field(
        default=720,
        ge=1,
        description="Time-to-live for LLM cache entries in hours (default: 720 = 30 days)",
    )
    generate_country_data: bool = Field(
        default=False, description="Whether to generate country production data"
    )
    country_data_mode: Literal["full", "incremental", "update"] = Field(
        default="full", description="Mode for country data generation (full/incremental/update)"
    )
    materials_to_update: Optional[list[str]] = Field(
        default=None, description="Specific materials to update (for incremental/update modes)"
    )

    # ========================================================================
    # Query and Processing Settings
    # ========================================================================

    years_to_query: list[int] = Field(
        default=[2023, 2024], description="Years to query for historical production data"
    )
    write_nulls_to_output: bool = Field(
        default=True, description="Whether to write rows with null country data to output CSV"
    )

    # ========================================================================
    # LLM Generation Settings
    # ========================================================================

    component_debate_use_personas: bool = Field(
        default=False,
        description=(
            "If true, multi-agent component debate uses per-agent personas/perspectives. "
            "If false, debate agents use the same single-agent prompt."
        ),
    )
    component_debate_top_p: float = Field(
        default=0.0001,
        ge=0.0,
        le=1.0,
        description="Top-p for component debate (multi-agent)",
    )
    component_no_debate_top_p: float = Field(
        default=0.000001,
        ge=0.0,
        le=1.0,
        description="Top-p for component extraction (single-agent)",
    )
    component_debate_temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperature for component debate (multi-agent)",
    )
    component_no_debate_temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperature for component extraction (single-agent)",
    )
    material_debate_top_p: float = Field(
        default=0.0001,
        ge=0.0,
        le=1.0,
        description="Top-p for materials debate (multi-agent)",
    )
    material_no_debate_top_p: float = Field(
        default=0.000001,
        ge=0.0,
        le=1.0,
        description="Top-p for materials extraction (single-agent)",
    )
    material_debate_temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperature for materials debate (multi-agent)",
    )
    material_no_debate_temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperature for materials extraction (single-agent)",
    )
    country_debate_top_p: float = Field(
        default=0.0001,
        ge=0.0,
        le=1.0,
        description="Top-p for country debate/voting (multi-agent fallback)",
    )
    country_no_debate_top_p: float = Field(
        default=0.000001,
        ge=0.0,
        le=1.0,
        description="Top-p for country extraction (single-agent fallback)",
    )
    country_debate_temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperature for country debate/voting (multi-agent fallback)",
    )
    country_no_debate_temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperature for country extraction (single-agent fallback)",
    )
    materials_use_topp: bool = Field(
        default=True, description="Whether to use top-p sampling for materials extraction"
    )
    materials_iteration_count: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of iterations for materials extraction consensus",
    )
    materials_count_threshold: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Threshold for material count consensus across iterations",
    )

    # ========================================================================
    # Pydantic v2 Configuration (FIXED)
    # ========================================================================

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for extensibility
        validate_assignment=True,  # Validate on attribute assignment
    )

    # ========================================================================
    # Computed Properties (Backward Compatibility)
    # ========================================================================

    @computed_field
    @property
    def tech_list_path(self) -> str:
        """Alias for import_tech_list (for pipeline compatibility)."""
        return self.import_tech_list

    @computed_field
    @property
    def src_year(self) -> int:
        """Source year for country data queries."""
        return self.years_to_query[0] if self.years_to_query else 2023

    @computed_field
    @property
    def meas_year(self) -> int:
        """Measurement year for country data queries."""
        return self.years_to_query[-1] if self.years_to_query else 2024
