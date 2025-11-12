"""
Data loading utilities for STDN

This module provides utilities for loading CSV, JSON, and other data formats
used throughout the STDN pipeline.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================================
# Data Loaders
# ============================================================================


class DataLoader:
    """
    Utilities for loading various data formats.

    Provides consistent interface for loading:
    - CSV files (material ontologies, component lists)
    - JSON files (configuration, cached data)
    - Text files (newline-delimited lists)

    Example:
        >>> loader = DataLoader()
        >>> materials = loader.load_csv("materials.csv", column="material_name")
        >>> config = loader.load_json("config.json")
        >>> tech_list = loader.load_text_list("technologies.txt")
    """

    @staticmethod
    def load_csv(
        file_path: str,
        column: Optional[str] = None,
        as_dict: bool = False,
    ) -> List[Any]:
        """
        Load data from CSV file.

        Args:
            file_path: Path to CSV file
            column: Specific column to extract (if None, returns full rows)
            as_dict: Return rows as dicts (True) or lists (False)

        Returns:
            List of values from column, or list of row dicts/lists

        Example:
            >>> # Load single column
            >>> materials = DataLoader.load_csv("materials.csv", column="name")
            >>>
            >>> # Load full rows as dicts
            >>> rows = DataLoader.load_csv("data.csv", as_dict=True)
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            if as_dict:
                reader = csv.DictReader(f)
                rows = list(reader)

                if column:
                    return [row.get(column) for row in rows if column in row]
                return rows
            else:
                reader = csv.reader(f)
                header = next(reader)  # Skip header
                rows = list(reader)

                if column:
                    # Find column index
                    try:
                        col_idx = header.index(column)
                        return [row[col_idx] for row in rows if len(row) > col_idx]
                    except ValueError:
                        raise ValueError(f"Column '{column}' not found in CSV")

                return rows

    @staticmethod
    def load_json(file_path: str) -> Dict[str, Any]:
        """
        Load data from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed JSON data as dict

        Example:
            >>> config = DataLoader.load_json("config.json")
            >>> model = config.get("model", "default")
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def load_text_list(file_path: str, strip: bool = True) -> List[str]:
        """
        Load newline-delimited text file as list.

        Args:
            file_path: Path to text file
            strip: Strip whitespace from each line

        Returns:
            List of lines

        Example:
            >>> technologies = DataLoader.load_text_list("tech_list.txt")
            >>> for tech in technologies:
            ...     process_technology(tech)
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

            if strip:
                lines = [line.strip() for line in lines]

            # Filter out empty lines
            return [line for line in lines if line]

    @staticmethod
    def save_json(data: Dict[str, Any], file_path: str, indent: int = 2):
        """
        Save data to JSON file.

        Args:
            data: Data to save
            file_path: Output file path
            indent: JSON indentation (default: 2)

        Example:
            >>> results = {"technology": "smartphone", "components": [...]}
            >>> DataLoader.save_json(results, "output.json")
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, default=str)

    @staticmethod
    def save_csv(
        data: List[Dict[str, Any]],
        file_path: str,
        fieldnames: Optional[List[str]] = None,
    ):
        """
        Save data to CSV file.

        Args:
            data: List of row dicts
            file_path: Output file path
            fieldnames: Column names (inferred from first row if None)

        Example:
            >>> countries = [
            ...     {"country": "China", "percentage": 65.5},
            ...     {"country": "Australia", "percentage": 27.3},
            ... ]
            >>> DataLoader.save_csv(countries, "countries.csv")
        """
        if not data:
            return

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if fieldnames is None:
            fieldnames = list(data[0].keys())

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "DataLoader",
]
