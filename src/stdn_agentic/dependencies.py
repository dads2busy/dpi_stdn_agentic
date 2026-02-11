"""
Initialize dependencies for STDN agents
"""

import ollama
import pandas as pd

from stdn_agentic.models import ConfigModel, STDNDependencies
from stdn_agentic.utils import create_ontology, create_ontology_dict


def initialize_dependencies(config: ConfigModel) -> STDNDependencies:
    """Initialize agent dependencies from configuration"""

    # Initialize Ollama client
    client = ollama.Client()

    # Load material ontology
    df = pd.read_csv(config.materials_hs_codes_listing)
    material_list = create_ontology(df, config.materials_column_name)
    material_ontology = ", ".join(material_list)
    material_dict = create_ontology_dict(df, config.materials_column_name)

    return STDNDependencies(
        material_ontology=material_ontology,
        material_ontology_dict=material_dict,
        material_ontology_list=material_list,
        years_to_query=config.years_to_query,
        client=client,
        model=config.model,
        top_p=config.topp,
        # Per-agent models (fallback to config.model if not set)
        component_model=config.component_model,
        materials_model=config.materials_model,
        country_model=config.country_model,
        # Normalization model configuration
        component_normalization_model=config.component_normalization_model,
    )
