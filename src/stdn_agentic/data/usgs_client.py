"""
USGS Database Client for STDN

This module provides a clean interface to the USGS Mineral Commodity Database.
It handles all database queries and connection management for material production data.
"""

from pathlib import Path
from typing import Dict, List, Optional

import duckdb
import pandas as pd

# ============================================================================
# USGS Database Client
# ============================================================================


class USGSClient:
    """
    Client for querying USGS Mineral Commodity Reports database.

    Provides methods to query top-producing countries, world totals, and
    detailed production metrics from the USGS database.

    Attributes:
        database_path: Path to DuckDB database file
        top_n: Number of top countries to return
        connection: DuckDB connection

    Example:
        >>> with USGSClient("./data/usgs.db", top_n=5) as client:
        ...     countries = client.query_top_countries("lithium", 2025, 2024)
        ...     if countries is not None:
        ...         print(f"Top producers: {countries['country'].tolist()}")
    """

    def __init__(self, database_path: str, top_n: int = 5):
        """
        Initialize USGS database client.

        Args:
            database_path: Path to USGS DuckDB database
            top_n: Number of top countries to return (default: 5)
        """
        self.database_path = Path(database_path)
        self.top_n = top_n
        self.connection = duckdb.connect(str(self.database_path))

        # Verify connection
        tables = self.connection.execute("SHOW TABLES").fetchall()
        print(f"✓ Connected to USGS database: {len(tables)} tables")

    def query_top_countries(
        self, material: str, src_year: int, meas_year: int
    ) -> Optional[pd.DataFrame]:
        """
        Query USGS database for top producing countries.

        Args:
            material: Material name (e.g., "Lithium")
            src_year: Source year of report
            meas_year: Measurement year for production data

        Returns:
            DataFrame with top countries, or None if no data found

        Example:
            >>> client = USGSClient("./data/usgs.db")
            >>> countries = client.query_top_countries("Lithium", 2025, 2024)
            >>> if countries is not None:
            ...     print(countries['country'].tolist())
        """
        query = f"""
        SELECT w.country
        FROM world_mineral_commodity_report w
        WHERE w.meas_yr IS NOT NULL
            AND w.meas_yr = {meas_year}
            AND w.src_yr = {src_year}
            AND UPPER(w.commodity) = '{material.upper()}'
            AND value_type = 'Number'
            AND UPPER(meas_type) = 'PRODUCTION'
            AND UPPER(country) NOT LIKE 'WORLD%'
            AND UPPER(country) NOT LIKE 'OTHER%'
            AND UPPER(country) NOT LIKE 'TOTAL%'
        ORDER BY CAST(w.value AS NUMERIC) DESC
        LIMIT {self.top_n}
        """

        try:
            result = self.connection.sql(query).df()
            return result if len(result) > 0 else None
        except Exception as e:
            print(f"USGS query failed for {material}: {e}")
            return None

    def query_world_totals(self, material: str, src_year: int, meas_year: int) -> Dict[str, float]:
        """
        Query world production totals by measure type.

        Args:
            material: Material name
            src_year: Source year of report
            meas_year: Measurement year

        Returns:
            Dict mapping meas_type -> total production value

        Example:
            >>> totals = client.query_world_totals("Lithium", 2025, 2024)
            >>> print(f"World production: {totals.get('PRODUCTION', 0)}")
        """
        query = f"""
        SELECT meas_type, value, meas_unit
        FROM world_mineral_commodity_report
        WHERE meas_yr = {meas_year}
            AND src_yr = {src_year}
            AND UPPER(commodity) = '{material.upper()}'
            AND UPPER(country) = 'WORLD'
            AND value_type = 'Number'
        """

        try:
            result = self.connection.sql(query).df()
            totals = {}
            for _, row in result.iterrows():
                meas_type = row["meas_type"].upper()
                try:
                    totals[meas_type] = float(row["value"])
                except (ValueError, TypeError):
                    continue
            return totals
        except Exception as e:
            print(f"World totals query failed for {material}: {e}")
            return {}

    def query_country_details(
        self, material: str, country: str, src_year: int, meas_year: int
    ) -> List[Dict]:
        """
        Query production details for a specific country.

        Args:
            material: Material name
            country: Country name
            src_year: Source year
            meas_year: Measurement year

        Returns:
            List of production records with meas_type, meas_unit, value

        Example:
            >>> details = client.query_country_details("Lithium", "Chile", 2025, 2024)
            >>> for record in details:
            ...     print(f"{record['meas_type']}: {record['value']} {record['meas_unit']}")
        """
        query = f"""
        SELECT meas_type, meas_unit, value
        FROM world_mineral_commodity_report
        WHERE meas_yr = {meas_year}
            AND src_year = {src_year}
            AND UPPER(commodity) = '{material.upper()}'
            AND UPPER(country) = '{country.upper()}'
            AND value_type = 'Number'
            AND UPPER(meas_type) IN ('PRODUCTION', 'RESERVES', 'RESERVE BASE')
        """

        try:
            result = self.connection.sql(query).df()
            records = []
            for _, row in result.iterrows():
                try:
                    records.append(
                        {
                            "meas_type": row["meas_type"],
                            "meas_unit": row["meas_unit"],
                            "value": float(row["value"]),
                        }
                    )
                except (ValueError, TypeError):
                    continue
            return records
        except Exception as e:
            print(f"Country details query failed for {material}/{country}: {e}")
            return []

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, *args):
        """Context manager exit"""
        self.close()


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "USGSClient",
]
