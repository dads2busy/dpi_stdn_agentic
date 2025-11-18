"""
Country Data Repository for STDN

This module provides the CountryDataRepository class that coordinates data
retrieval from USGS database and LLM fallback for material-country mappings.
"""

import asyncio
import logging
from typing import Dict, List, Optional

import pandas as pd
from pydantic_ai import RunUsage

from ..agents import CountryList, get_country_data_agent
from ..models import STDNDependencies
from .usgs_client import USGSClient

# Initialize logger
logger = logging.getLogger(__name__)

# ============================================================================
# Country Data Repository
# ============================================================================


class CountryDataRepository:
    """
    Manages country production data retrieval with USGS + LLM fallback.

    This class coordinates data retrieval:
    1. First tries USGS database (primary source)
    2. Falls back to LLM agent if USGS has no data
    3. Caches results to avoid redundant queries

    Attributes:
        database_path: Path to USGS database
        top_n: Number of top countries to return
        deps: STDN dependencies
        use_llm_fallback: Whether to use LLM when USGS has no data
        cache: Material-country cache

    Example:
        >>> repo = CountryDataRepository(
        ...     database_path="./data/usgs.db",
        ...     deps=deps,
        ...     use_llm_fallback=True
        ... )
        >>> countries = await repo.get_country_data(
        ...     material="lithium",
        ...     src_year=2025,
        ...     meas_year=2024
        ... )
    """

    def __init__(
        self,
        database_path: str,
        deps: STDNDependencies,
        top_n: int = 5,
        use_llm_fallback: bool = True,
    ):
        """
        Initialize country data repository.

        Args:
            database_path: Path to USGS DuckDB database
            deps: STDN dependencies (for LLM access)
            top_n: Number of top countries to return
            use_llm_fallback: Use LLM when USGS has no data
        """
        self.database_path = database_path
        self.top_n = top_n
        self.deps = deps
        self.use_llm_fallback = use_llm_fallback

        # Initialize USGS client
        self.usgs_client = USGSClient(database_path, top_n=top_n)

        # Initialize LLM agent if fallback enabled
        self.country_agent = get_country_data_agent() if use_llm_fallback else None

        # Cache for material-country mappings
        self.cache: Dict[str, List[Dict]] = {}

    async def get_country_data(
        self,
        material: str,
        src_year: int,
        meas_year: int,
        usage: Optional[RunUsage] = None,
    ) -> List[Dict]:
        """
        Get country production data for a material.

        Tries USGS database first, falls back to LLM if enabled.
        """
        # Check cache first
        cache_key = f"{material}_{src_year}_{meas_year}"
        if cache_key in self.cache:
            print(f"✓ Cache hit for {material}")
            return self.cache[cache_key]

        # Try USGS database
        print(f"Querying USGS for {material} (year {src_year}/{meas_year})")
        usgs_data = self._query_usgs(material, src_year, meas_year)

        if usgs_data:
            print(f"✓ USGS returned {len(usgs_data)} countries")
            # ADD HS CODE HERE (NEW)
            hs_code = self._lookup_hs_code(material)
            for country in usgs_data:
                country["hs_code"] = hs_code
            # END NEW CODE
            self.cache[cache_key] = usgs_data
            return usgs_data

        # Fall back to LLM if enabled
        if self.use_llm_fallback and self.country_agent:
            print(f"⚠ No USGS data found, using LLM fallback...")
            llm_data = await self._query_llm(material, meas_year, usage)
            if llm_data:
                print(f"✓ LLM returned {len(llm_data)} countries")
                # ADD HS CODE HERE (NEW)
                hs_code = self._lookup_hs_code(material)
                for country in llm_data:
                    country["hs_code"] = hs_code
                # END NEW CODE
                self.cache[cache_key] = llm_data
                return llm_data

        print(f"✗ No data found for {material}")
        return []

    def _lookup_hs_code(self, material: str) -> Optional[str]:
        """
        Look up HS code for a material from the materials ontology CSV.

        Handles:
        - Exact case-insensitive matching
        - Whitespace trimming
        - Partial matching (e.g., "Gold" matches "Gold, mine")
        - NaN values in CSV
        - Integer HS codes (removes .0 decimal)

        Args:
            material: Material name (e.g., "Gold", "Lithium")

        Returns:
            HS code as string (e.g., "710812"), or None if not found
        """
        try:
            import pandas as pd

            df = pd.read_csv("./data/hs_codes_and_usgs_names.csv")

            # Verify column exists
            if "HS_Code" not in df.columns:
                return None

            # Clean the material name
            material_clean = material.lower().strip()

            # Try exact match first
            match = df[df["Elements_Compounds"].str.lower().str.strip() == material_clean]

            if not match.empty:
                hs_code_value = match.iloc[0]["HS_Code"]
                # Check if value is not NaN and not empty
                if pd.notna(hs_code_value) and str(hs_code_value).strip():
                    return str(int(hs_code_value))  # Convert to int first to remove .0

            # Try partial match if exact failed
            match = df[
                df["Elements_Compounds"]
                .str.lower()
                .str.contains(material_clean, na=False, regex=False)
            ]
            if not match.empty:
                hs_code_value = match.iloc[0]["HS_Code"]
                if pd.notna(hs_code_value) and str(hs_code_value).strip():
                    return str(int(hs_code_value))

        except Exception as e:
            print(f"HS lookup error for {material}: {e}")

        return None

    def _query_usgs(
        self,
        material: str,
        src_year: int,
        meas_year: int,
    ) -> List[Dict]:
        """
        Query USGS database for country data.

        Args:
            material: Material name
            src_year: Source year
            meas_year: Measurement year

        Returns:
            List of country data dicts
        """
        try:
            # Get top countries
            countries_df = self.usgs_client.query_top_countries(material, src_year, meas_year)

            if countries_df is None or len(countries_df) == 0:
                return []

            # Get world totals (returns DataFrame)
            world_totals_df = self.usgs_client.query_world_totals(material, src_year, meas_year)

            # FIXED: Handle DataFrame properly
            if world_totals_df is None or world_totals_df.empty:
                logger.warning(f"No world totals data for {material}")
                return []

            # Extract production value from DataFrame
            # Convert VALUE column to numeric and sum
            try:
                world_production = pd.to_numeric(world_totals_df["VALUE"], errors="coerce").sum()
            except (KeyError, ValueError) as e:
                logger.warning(f"Could not extract world production for {material}: {e}")
                return []

            if world_production == 0 or pd.isna(world_production):
                logger.warning(f"No world production data for {material}")
                return []

            # Build country data
            country_data = []
            for country_name in countries_df["country"]:
                details_df = self.usgs_client.query_country_details(
                    material, country_name, src_year, meas_year
                )

                # FIXED: Handle DataFrame properly
                if details_df is None or details_df.empty:
                    continue

                # Iterate through DataFrame rows
                for _, row in details_df.iterrows():
                    try:
                        if str(row.get("MEAS_TYPE", "")).upper() == "PRODUCTION":
                            amount = pd.to_numeric(row.get("VALUE", 0), errors="coerce")

                            if pd.isna(amount):
                                continue

                            percentage = (
                                (amount / world_production * 100) if world_production > 0 else 0
                            )

                            country_data.append(
                                {
                                    "country": country_name,
                                    "meas_unit": row.get("MEAS_UNIT", ""),
                                    "amount": float(amount),
                                    "percentage": float(percentage),
                                }
                            )
                            break  # Only take production data
                    except (ValueError, TypeError, KeyError) as e:
                        logger.debug(f"Error processing row for {country_name}: {e}")
                        continue

            return country_data

        except Exception as e:
            logger.error(f"Error in _query_usgs for {material}: {e}", exc_info=True)
            return []

    async def _query_llm(
        self,
        material: str,
        year: int,
        usage: Optional[RunUsage] = None,
    ) -> List[Dict]:
        """
        Query LLM agent for country data (fallback).

        Args:
            material: Material name
            year: Year for production data
            usage: Optional RunUsage tracker

        Returns:
            List of country data dicts
        """
        if not self.country_agent:
            return []

        prompt = (
            f"Return the top {self.top_n} countries that produced {material} in {year}, "
            f"with production amounts (numeric values with units) and percentage of global supply. "
            f"Use the most recent data available (preferably {year} or within 2-3 years). "
            f"Ensure percentages sum to a reasonable total and amounts are specific numbers, not estimates."
        )

        try:
            result = await self.country_agent.run(
                prompt,
                deps=self.deps,
                model=self.deps.model,
            )

            if result and result.output:
                country_list = result.output

                # Convert to standard format
                country_data = [
                    {
                        "country": cp.country,
                        "meas_unit": cp.meas_unit,
                        "amount": cp.amount,
                        "percentage": cp.percentage,
                    }
                    for cp in country_list.country_list
                ]

                return country_data

        except Exception as e:
            print(f"LLM query failed for {material}: {e}")
            return []

        return []

    def clear_cache(self):
        """Clear the country data cache"""
        self.cache.clear()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cached_materials": len(self.cache),
            "materials": list(self.cache.keys()),
        }

    def close(self):
        """Close database connections"""
        if self.usgs_client:
            self.usgs_client.close()


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "CountryDataRepository",
]
