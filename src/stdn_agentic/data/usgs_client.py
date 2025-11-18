"""
USGS Database Client for STDN

This module provides a clean interface to the USGS Mineral Commodity Database.
It handles all database queries and connection management for material production data.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import duckdb
import pandas as pd

# Initialize logger
logger = logging.getLogger(__name__)

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
        """
        # Fixed: Most columns are UPPERCASE, but value_type is lowercase
        query = f"""
        SELECT COUNTRY, SUM(TRY_CAST(VALUE AS DOUBLE)) as total_production
        FROM world_mineral_commodity_report
        WHERE MEAS_YR = {meas_year}
          AND SRC_YR = {src_year}
          AND UPPER(COMMODITY) = '{material.upper()}'
          AND UPPER(COUNTRY) NOT LIKE '%WORLD%'
          AND value_type = 'Number'
          AND UPPER(MEAS_TYPE) = 'PRODUCTION'
          AND VALUE IS NOT NULL
          AND VALUE != ''
        GROUP BY COUNTRY
        HAVING SUM(TRY_CAST(VALUE AS DOUBLE)) IS NOT NULL
        ORDER BY total_production DESC
        LIMIT {self.top_n}
        """

        try:
            result = self.connection.sql(query).df()

            if result.empty:
                logger.debug(f"No USGS data found for {material} ({meas_year}/{src_year})")
                return None

            # Rename COUNTRY to country for consistency
            result = result.rename(columns={"COUNTRY": "country"})

            # Translate country names
            result["country"] = result["country"].apply(self._translate_country_name)

            # Keep only country column
            result_subset = result[["country"]].copy()

            # Type assertion for basedpyright
            assert isinstance(result_subset, pd.DataFrame)

            return result_subset

        except Exception as e:
            logger.error(f"Top countries query failed for {material}: {e}", exc_info=True)
            return None

    def query_world_totals(
        self, material: str, src_year: int, meas_year: int
    ) -> Optional[pd.DataFrame]:
        """
        Query world total production for a material.

        Args:
            material: Material name
            src_year: Source year of report
            meas_year: Measurement year for production data

        Returns:
            DataFrame with world totals, or None if no data found
        """
        # Fixed: Column is MEAS_UNIT not UNIT
        query = f"""
        SELECT VALUE, MEAS_UNIT, MEAS_TYPE
        FROM world_mineral_commodity_report
        WHERE MEAS_YR = {meas_year}
          AND SRC_YR = {src_year}
          AND UPPER(COMMODITY) = '{material.upper()}'
          AND UPPER(COUNTRY) LIKE '%WORLD%'
          AND value_type = 'Number'
          AND UPPER(MEAS_TYPE) = 'PRODUCTION'
        """

        try:
            result = self.connection.sql(query).df()

            if result.empty:
                logger.debug(f"No world totals found for {material} ({meas_year}/{src_year})")
                return None

            return result

        except Exception as e:
            logger.error(f"World totals query failed for {material}: {e}", exc_info=True)
            return None

    def query_country_details(
        self, material: str, country: str, src_year: int, meas_year: int
    ) -> Optional[pd.DataFrame]:
        """
        Query detailed production data for a specific country and material.

        Args:
            material: Material name
            country: Country name
            src_year: Source year of report
            meas_year: Measurement year for production data

        Returns:
            DataFrame with country details, or None if no data found
        """
        # Fixed: Column is MEAS_UNIT not UNIT
        query = f"""
        SELECT COUNTRY, VALUE, MEAS_UNIT, MEAS_TYPE, value_type
        FROM world_mineral_commodity_report
        WHERE MEAS_YR = {meas_year}
          AND SRC_YR = {src_year}
          AND UPPER(COMMODITY) = '{material.upper()}'
          AND UPPER(COUNTRY) = '{country.upper()}'
          AND value_type = 'Number'
          AND UPPER(MEAS_TYPE) = 'PRODUCTION'
        """

        try:
            result = self.connection.sql(query).df()

            if result.empty:
                logger.debug(f"No details found for {material}/{country} ({meas_year}/{src_year})")
                return None

            # Rename COUNTRY to country for consistency
            if "COUNTRY" in result.columns:
                result = result.rename(columns={"COUNTRY": "country"})

            return result

        except Exception as e:
            logger.error(
                f"Country details query failed for {material}/{country}: {e}", exc_info=True
            )
            return None

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
