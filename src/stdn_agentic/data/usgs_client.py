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

        # ========================================================================
        # DEBUG: Connection and table visibility check
        # ========================================================================
        print(f"\n🔍 DEBUG query_top_countries:")
        print(f"  Material: {material}")
        print(f"  Years: src_year={src_year}, meas_year={meas_year}")
        print(f"  Connection object: {self.connection}")
        print(f"  Database path: {self.database_path}")

        # Verify table is visible through this connection
        try:
            tables = self.connection.execute("SHOW TABLES").fetchall()
            print(f"  Tables visible: {tables}")

            if not tables:
                print(f"  ❌ WARNING: No tables visible in connection!")
                # Try to reconnect
                print(f"  Attempting to reconnect...")
                self.connection = duckdb.connect(str(self.database_path))
                tables = self.connection.execute("SHOW TABLES").fetchall()
                print(f"  After reconnect, tables: {tables}")

        except Exception as e:
            print(f"  ❌ ERROR: Can't see tables: {e}")
            print(f"  Attempting to reconnect...")
            try:
                self.connection = duckdb.connect(str(self.database_path))
                tables = self.connection.execute("SHOW TABLES").fetchall()
                print(f"  After reconnect, tables: {tables}")
            except Exception as e2:
                print(f"  ❌ Reconnect failed: {e2}")
                return None

        # ========================================================================
        # Main Query
        # ========================================================================
        query = f"""
            SELECT w.COUNTRY as country
            FROM world_mineral_commodity_report w
            WHERE w.MEAS_YR IS NOT NULL
                AND w.MEAS_YR = {meas_year}
                AND w.SRC_YR = {src_year}
                AND UPPER(w.COMMODITY) = '{material.upper()}'
                AND value_type = 'Number'
                AND UPPER(MEAS_TYPE) = 'PRODUCTION'
                AND UPPER(COUNTRY) NOT LIKE 'WORLD%'
                AND UPPER(COUNTRY) NOT LIKE 'OTHER%'
                AND UPPER(COUNTRY) NOT LIKE 'TOTAL%'
            ORDER BY CAST(w.VALUE AS NUMERIC) DESC
            LIMIT {self.top_n}
            """

        print(f"\n  SQL Query:")
        print(f"  {query}")

        try:
            result = self.connection.sql(query).df()
            print(f"  Query result: {len(result)} rows")
            if len(result) > 0:
                print(f"  Top countries: {result['country'].tolist()}")
            return result if len(result) > 0 else None

        except Exception as e:
            print(f"  ❌ USGS query failed for {material}: {e}")
            import traceback

            traceback.print_exc()
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
        """
        query = f"""
        SELECT meas_type, meas_unit, value
        FROM world_mineral_commodity_report
        WHERE meas_yr = {meas_year}
            AND src_yr = {src_year}    # ✅ FIXED - was src_year, should be src_yr
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
