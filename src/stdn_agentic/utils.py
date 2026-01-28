"""
Utility functions for STDN processing
"""

import json

import pandas as pd


def read_json_to_dict(filepath: str) -> dict:
    """Read JSON configuration file"""
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Error: The file {filepath} was not found.") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Error: Could not decode JSON from {filepath}.") from e


def create_ontology(df: pd.DataFrame, key: str) -> list[str]:
    """Create ontology list from dataframe"""
    return df[key].tolist()


def create_ontology_dict(df: pd.DataFrame, key: str) -> dict:
    """Create ontology dictionary with HS codes"""
    df = df.set_index(key)
    df = df.fillna("NA")
    return df.to_dict("index")


def intersect_lists(list1: list, list2: list) -> list:
    """Return intersection of two lists"""
    return list(set(list1) & set(list2))


def embed_comma_delimited_str(strval: str) -> str:
    """Wrap strings with commas in quotes for CSV"""
    if "," in strval:
        return f'"{strval}"'
    return strval


def validate_config(config_data: dict) -> dict:
    """Validate and populate configuration with defaults"""
    required_keys = ["import_tech_list", "model", "output_dir", "output_csv_filename"]

    if not all(key in config_data for key in required_keys):
        raise ValueError(f"Required parameters missing: {required_keys}")

    defaults = {
        "write_nulls_to_output": True,
        "topp": 0.000001,
        "materials_use_topp": True,
        "materials_iteration_count": 10,
        "materials_count_threshold": 5,
        "materials_hs_codes_listing": "../../data/hs_codes_and_usgs_names.csv",
        "years_to_query": [2023, 2024],
    }

    for key, value in defaults.items():
        config_data.setdefault(key, value)

    return config_data
