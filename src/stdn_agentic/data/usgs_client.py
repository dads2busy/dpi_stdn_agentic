"""
USGS Database Client for STDN

This module provides a clean interface to the USGS Mineral Commodity Database.
It handles all database queries and connection management for material production data.
"""

from pathlib import Path
from typing import Dict, List, Optional

import duckdb
import pandas as pd

# Country name translations (Chinese to English)
COUNTRY_TRANSLATIONS = {
    "智利": "Chile",
    "美国": "United States",
    "巴西": "Brazil",
    "澳大利亚": "Australia",
    "俄罗斯": "Russia",
    "加拿大": "Canada",
    "印度": "India",
    "日本": "Japan",
    "韩国": "South Korea",
    "墨西哥": "Mexico",
    "秘鲁": "Peru",
    "刚果民主共和国": "Democratic Republic of the Congo",
    "赞比亚": "Zambia",
    "南非": "South Africa",
    "印度尼西亚": "Indonesia",
    "土耳其": "Turkey",
    "波兰": "Poland",
    "哈萨克斯坦": "Kazakhstan",
    "乌克兰": "Ukraine",
    "伊朗": "Iran",
    "沙特阿拉伯": "Saudi Arabia",
    "阿根廷": "Argentina",
    "玻利维亚": "Bolivia",
}


class USGSClient:
    """
    Client for querying USGS Mineral Commodity Reports database.

    Provides methods to query top-producing countries, world totals, and detailed
    production metrics from the USGS database.

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

    def _translate_country_name(self, country_name: str) -> str:
        """Translate Chinese country names to English"""
        return COUNTRY_TRANSLATIONS.get(country_name, country_name)

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
        SELECT DISTINCT country
        FROM world_mineral_commodity_report
        WHERE meas_yr = {meas_year}
          AND src_yr = {src_year}
          AND UPPER(commodity) = '{material.upper()}'
          AND UPPER(country) NOT LIKE '%WORLD%'
          AND value_type = 'Number'
          AND UPPER(meas_type) = 'PRODUCTION'
        ORDER BY value DESC
        LIMIT {self.top_n}
        """

        try:
            result = self.connection.sql(query).df()
            if result.empty:
                return None

            # Translate country names
            result["country"] = result["country"].apply(self._translate_country_name)
            return result
        except Exception as e:
            print(f"Top countries query failed for {material}: {e}")
            return None

    def query_world_totals(self, material: str, src_year: int, meas_year: int) -> Dict[str, float]:
        """
        Query world total production for a material.

        Args:
            material: Material name
            src_year: Source year
            meas_year: Measurement year

        Returns:
            Dict with meas_type -> value mappings

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
          AND UPPER(country) LIKE '%WORLD%'
          AND value_type = 'Number'
        """

        try:
            result = self.connection.sql(query).df()
            totals = {}
            for _, row in result.iterrows():
                meas_type = str(row["meas_type"]).upper()  # ← Fixed type issue
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
          AND src_yr = {src_year}
          AND UPPER(commodity) = '{material.upper()}'
          AND UPPER(country) = '{country.upper()}'
          AND value_type = 'Number'
          AND UPPER(meas_type) IN ('PRODUCTION', 'RESERVES', 'RESERVE BASE')
        """

        try:
            result = self.connection.sql(query).df()
            details = []
            for _, row in result.iterrows():
                details.append(
                    {
                        "meas_type": str(row["meas_type"]),  # ← Fixed type issue
                        "meas_unit": row["meas_unit"],
                        "value": float(row["value"]),
                    }
                )
            return details
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "USGSClient",
]
