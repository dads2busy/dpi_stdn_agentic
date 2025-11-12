"""
Pydantic data models for STDN generation pipeline
"""

from dataclasses import dataclass
from typing import Literal, Optional

import ollama
from pydantic import BaseModel, Field


@dataclass
class STDNDependencies:
    """Dependencies passed to STDN agents"""

    material_ontology: str
    material_ontology_dict: dict
    material_ontology_list: list[str]
    materials_top_countries_dict: dict
    years_to_query: list[int]
    client: ollama.Client
    model: str
    topp: float


class ConfigModel(BaseModel):
    """Configuration validation model"""

    import_tech_list: str
    model: str
    output_dir: str
    output_csv_filename: str
    materials_hs_codes_listing: str = "./data/hs_codes_and_usgs_names.csv"
    materials_column_name: str = "Elements_Compounds"
    materials_top_countries_repository: str = (
        "./data/material_top_countries_granite3.1-dense.8b.json"
    )

    # Country data generation settings (optional)
    usgs_database: Optional[str] = "./data/world_mineral_commodity_reports_2022-2025_v8.db"
    top_n_countries: int = 5
    generate_country_data: bool = False
    country_data_mode: Literal["full", "incremental", "update"] = "full"  # New option
    materials_to_update: Optional[list[str]] = None  # Specific materials to update/add

    years_to_query: list[int] = [2023, 2024]
    write_nulls_to_output: bool = True
    topp: float = 0.000001
    materials_use_topp: bool = True
    materials_iteration_count: int = 10
    materials_count_threshold: int = 5
