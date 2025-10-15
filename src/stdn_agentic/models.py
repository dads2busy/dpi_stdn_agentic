"""
Pydantic data models for STDN generation pipeline
"""

from pydantic import BaseModel, Field
from dataclasses import dataclass
from typing import Optional
import ollama


class ComponentList(BaseModel):
    """Structured output for technology components"""
    component_list: list[str] = Field(description="Primary technology components")


class ComponentMaterials(BaseModel):
    """Raw materials for a single component"""
    component: str
    raw_materials_list: list[str]


class ComponentMaterialsList(BaseModel):
    """Collection of components with their materials"""
    component_list: list[ComponentMaterials]


@dataclass
class STDNDependencies:
    """Dependencies passed to all agents"""
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
    materials_hs_codes_listing: str = '../data/hs_codes_and_usgs_names.csv'
    materials_top_countries_repository: str = '../data/material_top_countries_granite3.1-dense_8b.json'
    years_to_query: list[int] = [2023, 2024]
    write_nulls_to_output: bool = True
    topp: float = 0.000001
    materials_use_topp: bool = True
    materials_iteration_count: int = 10
    materials_count_threshold: int = 5
