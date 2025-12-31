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
    - Model configuration

    Attributes:
        material_ontology: Comma-separated string of material names
        material_ontology_dict: Material name to ID mapping
        material_ontology_list: List of material names for validation
        materials_top_countries_dict: Top producer countries per material
        years_to_query: List of years for historical data queries
        client: Ollama client for LLM inference
        model: Model identifier (e.g., "qwen2.5:7b")
        top_p: Top-p sampling parameter for generation
    """

    material_ontology: str
    material_ontology_dict: dict
    material_ontology_list: list[str]
    materials_top_countries_dict: dict
    years_to_query: list[int]
    client: ollama.Client
    model: str
    top_p: float


# ============================================================================
# Configuration Model
# ============================================================================


class ConfigModel(BaseModel):
    """
    Configuration validation model for STDN generation.
    """

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
    materials_top_countries_repository: str = Field(
        default="./data/material_top_countries_granite3.1-dense.8b.json",
        description="Path to JSON with top producing countries per material",
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

    topp: float = Field(
        default=0.000001,
        ge=0.0,
        le=1.0,
        description="Top-p (nucleus) sampling parameter for generation",
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
