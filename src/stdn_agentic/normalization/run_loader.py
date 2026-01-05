"""
Run Loader for STDN Normalization.

This module loads and parses existing STDN run files (CSV/JSON) from the output
directory, converting them into structured Python objects for normalization.

Key Features:
- Load individual CSV run files
- Load individual JSON run files
- Load all runs from a directory
- Extract components with their materials
- Generate unique run IDs from filenames
- Handle various date formats and file naming conventions
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================================
# Data Structures
# ============================================================================


class RunComponent:
    """
    Represents a component from a single run.

    This is an intermediate representation before normalization.
    Each component includes the technology it belongs to, its name,
    associated materials, and confidence scores.
    """

    def __init__(
        self,
        technology: str,
        component: str,
        component_confidence: float,
        component_reasoning: str,
        materials: List[Dict[str, Any]],
    ):
        self.technology = technology
        self.component = component
        self.component_confidence = component_confidence
        self.component_reasoning = component_reasoning
        self.materials = materials  # List of material dicts with country data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "technology": self.technology,
            "component": self.component,
            "component_confidence": self.component_confidence,
            "component_reasoning": self.component_reasoning,
            "materials": self.materials,
        }


class RunData:
    """
    Complete data from a single STDN run.

    Contains all components identified in the run, along with
    metadata about when and how the run was executed.
    """

    def __init__(
        self,
        run_id: str,
        timestamp: datetime,
        file_path: Path,
        components: List[RunComponent],
    ):
        self.run_id = run_id
        self.timestamp = timestamp
        self.file_path = file_path
        self.components = components

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "file_path": str(self.file_path),
            "components": [comp.to_dict() for comp in self.components],
            "component_count": len(self.components),
        }


# ============================================================================
# Run Loader Class
# ============================================================================


class RunLoader:
    """
    Loads STDN run files from disk.

    Supports both CSV and JSON formats. Extracts run metadata from
    filenames and organizes component data for normalization.

    Attributes:
        output_dir: Directory containing run files
        runs_pattern: Glob pattern for finding run files
    """

    def __init__(self, output_dir: str = "./output"):
        """
        Initialize the run loader.

        Args:
            output_dir: Path to directory containing STDN run files
        """
        self.output_dir = Path(output_dir)
        if not self.output_dir.exists():
            raise FileNotFoundError(f"Output directory not found: {output_dir}")

    # ========================================================================
    # Run ID and Timestamp Extraction
    # ========================================================================

    def _extract_run_info(self, file_path: Path) -> tuple[str, datetime]:
        """
        Extract run ID and timestamp from filename.

        Expected filename format: stdns_output_YYYYMMDD_HHMMSS.csv
        Example: stdns_output_20260101_093731.csv

        Args:
            file_path: Path to run file

        Returns:
            Tuple of (run_id, timestamp)
        """
        filename = file_path.stem  # Removes extension

        # Extract timestamp from filename
        # Format: stdns_output_20260101_093731
        parts = filename.split("_")

        if len(parts) >= 4:
            date_str = parts[2]  # YYYYMMDD
            time_str = parts[3]  # HHMMSS

            # Parse timestamp
            try:
                timestamp = datetime.strptime(
                    f"{date_str}_{time_str}", "%Y%m%d_%H%M%S"
                )
            except ValueError:
                # Fallback to file modification time
                timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
        else:
            # Fallback to file modification time
            timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)

        # Generate run_id from filename
        run_id = filename

        return run_id, timestamp

    # ========================================================================
    # CSV Loading
    # ========================================================================

    def load_csv_run(self, file_path: Path) -> RunData:
        """
        Load a single CSV run file.

        The CSV format includes columns:
        - technology, component, component_confidence, component_reasoning
        - material, material_confidence, material_reasoning
        - hs_code, country, meas_unit, amount, percentage
        - country_confidence, country_reasoning

        Args:
            file_path: Path to CSV file

        Returns:
            RunData object with all components
        """
        run_id, timestamp = self._extract_run_info(file_path)

        # Read CSV file
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Group by (technology, component) to consolidate materials
        component_map: Dict[tuple, Dict[str, Any]] = {}

        for row in rows:
            tech = row["technology"].strip()
            comp = row["component"].strip()
            key = (tech, comp)

            if key not in component_map:
                # First occurrence of this component
                component_map[key] = {
                    "technology": tech,
                    "component": comp,
                    "component_confidence": float(row["component_confidence"]),
                    "component_reasoning": row["component_reasoning"].strip(),
                    "materials": [],
                }

            # Add material data
            material_entry = {
                "material": row["material"].strip(),
                "material_confidence": float(row["material_confidence"]),
                "material_reasoning": row["material_reasoning"].strip(),
                "hs_code": row["hs_code"].strip() if row["hs_code"] else None,
                "country": row["country"].strip() if row["country"] else None,
                "meas_unit": row["meas_unit"].strip() if row["meas_unit"] else None,
                "amount": (
                    float(row["amount"]) if row["amount"] and row["amount"].strip() else None
                ),
                "percentage": (
                    float(row["percentage"])
                    if row["percentage"] and row["percentage"].strip()
                    else None
                ),
                "country_confidence": (
                    float(row["country_confidence"])
                    if row["country_confidence"] and row["country_confidence"].strip()
                    else None
                ),
                "country_reasoning": (
                    row["country_reasoning"].strip() if row["country_reasoning"] else None
                ),
            }

            component_map[key]["materials"].append(material_entry)

        # Convert to RunComponent objects
        components = [
            RunComponent(
                technology=data["technology"],
                component=data["component"],
                component_confidence=data["component_confidence"],
                component_reasoning=data["component_reasoning"],
                materials=data["materials"],
            )
            for data in component_map.values()
        ]

        return RunData(
            run_id=run_id,
            timestamp=timestamp,
            file_path=file_path,
            components=components,
        )

    # ========================================================================
    # JSON Loading (for future compatibility)
    # ========================================================================

    def load_json_run(self, file_path: Path) -> RunData:
        """
        Load a single JSON run file.

        Args:
            file_path: Path to JSON file

        Returns:
            RunData object with all components
        """
        run_id, timestamp = self._extract_run_info(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Parse JSON structure (adapt based on actual JSON format)
        components = []
        for comp_data in data.get("components", []):
            component = RunComponent(
                technology=comp_data["technology"],
                component=comp_data["component"],
                component_confidence=comp_data["component_confidence"],
                component_reasoning=comp_data["component_reasoning"],
                materials=comp_data.get("materials", []),
            )
            components.append(component)

        return RunData(
            run_id=run_id,
            timestamp=timestamp,
            file_path=file_path,
            components=components,
        )

    # ========================================================================
    # Batch Loading
    # ========================================================================

    def load_all_runs(self, pattern: str = "stdns_output_*.csv") -> List[RunData]:
        """
        Load all run files matching the pattern.

        Args:
            pattern: Glob pattern for finding run files (default: "stdns_output_*.csv")

        Returns:
            List of RunData objects, sorted by timestamp
        """
        run_files = sorted(self.output_dir.glob(pattern))

        if not run_files:
            print(f"Warning: No run files found in {self.output_dir} matching '{pattern}'")
            return []

        runs = []
        for file_path in run_files:
            try:
                if file_path.suffix == ".csv":
                    run = self.load_csv_run(file_path)
                elif file_path.suffix == ".json":
                    run = self.load_json_run(file_path)
                else:
                    print(f"Skipping unsupported file type: {file_path}")
                    continue

                runs.append(run)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                continue

        # Sort by timestamp
        runs.sort(key=lambda r: r.timestamp)

        return runs

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_run_summary(self, runs: List[RunData]) -> Dict[str, Any]:
        """
        Generate summary statistics for loaded runs.

        Args:
            runs: List of RunData objects

        Returns:
            Dictionary with summary statistics
        """
        if not runs:
            return {
                "total_runs": 0,
                "total_components": 0,
                "date_range": None,
            }

        total_components = sum(len(run.components) for run in runs)
        timestamps = [run.timestamp for run in runs]

        return {
            "total_runs": len(runs),
            "total_components": total_components,
            "avg_components_per_run": total_components / len(runs) if runs else 0,
            "date_range": {
                "earliest": min(timestamps).isoformat(),
                "latest": max(timestamps).isoformat(),
            },
            "run_ids": [run.run_id for run in runs],
        }

    def get_unique_technologies(self, runs: List[RunData]) -> List[str]:
        """
        Extract all unique technologies across runs.

        Args:
            runs: List of RunData objects

        Returns:
            Sorted list of unique technology names
        """
        technologies = set()
        for run in runs:
            for component in run.components:
                technologies.add(component.technology)

        return sorted(technologies)

    def get_unique_components(self, runs: List[RunData]) -> List[str]:
        """
        Extract all unique component names across runs.

        Args:
            runs: List of RunData objects

        Returns:
            Sorted list of unique component names
        """
        components = set()
        for run in runs:
            for component in run.components:
                components.add(component.component)

        return sorted(components)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "RunLoader",
    "RunData",
    "RunComponent",
]
