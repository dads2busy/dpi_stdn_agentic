"""
Country Data Repository for STDN

This module provides the CountryDataRepository class that coordinates data
retrieval from USGS database and LLM fallback for material-country mappings
with confidence scoring.
"""

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic_ai import RunUsage

from ..agents import get_country_data_agent
from ..models import STDNDependencies
from .usgs_client import USGSClient

logger = logging.getLogger(__name__)


class CountryDataRepository:
    """
    Manages country production data retrieval with USGS + LLM fallback.

    This class coordinates data retrieval with confidence scoring:
    1. First tries USGS database (primary source, high confidence)
    2. Falls back to LLM agent if USGS has no data (variable confidence)
    3. Optionally uses multi-agent debate for LLM fallback
    4. Caches results to avoid redundant queries

    All returned data includes confidence scores and reasoning.

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
        ...     meas_year=2024,
        ...     use_debate=True
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
            deps: STDN dependencies for LLM access
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
        use_debate: bool = False,
        transcript_path: Optional[Path] = None,
    ) -> List[Dict]:
        """
        Get country production data for a material with confidence scoring.

        Tries USGS database first, falls back to LLM if enabled.
        Can use multi-agent debate for LLM fallback.

        Args:
            material: Material name
            src_year: Source year of report
            meas_year: Measurement year for production data
            usage: Optional usage tracker
            use_debate: Use multi-agent debate for LLM fallback
            transcript_path: Optional path to append results

        Returns:
            List of country data dicts with keys:
                - country: Country name
                - meas_unit: Measurement unit
                - amount: Production amount
                - percentage: Percentage of global production
                - hs_code: HS code if available
                - confidence: Confidence score (0.0-1.0)
                - reasoning: Explanation of data source and confidence
        """
        # Check cache first
        cache_key = f"{material}_{src_year}_{meas_year}"
        if cache_key in self.cache:
            print(f"✓ Cache hit for {material}")
            return self.cache[cache_key]

        # Try USGS database
        print(f"Querying USGS for {material} (year {src_year}/{meas_year})")
        usgs_data = self.query_usgs(material, src_year, meas_year)

        if usgs_data:
            print(f"✓ USGS returned {len(usgs_data)} countries")

            # Add HS code, confidence, and reasoning to USGS data
            hs_code = self.lookup_hs_code(material)
            for country in usgs_data:
                country["hs_code"] = hs_code
                # USGS data gets high confidence (authoritative source)
                country["confidence"] = 0.95
                country["reasoning"] = (
                    f"USGS Mineral Commodity Summaries {src_year}/{meas_year} - "
                    f"authoritative U.S. government production data with global coverage"
                )

            self.cache[cache_key] = usgs_data

            # Save to transcript if provided
            if transcript_path:
                self.append_country_data_to_transcript(
                    transcript_path, material, usgs_data, source="USGS Database"
                )

            return usgs_data

        # Fall back to LLM if enabled
        if self.use_llm_fallback and self.country_agent:
            print("No USGS data found, using LLM fallback...")

            # Use debate or single-agent LLM
            if use_debate:
                llm_data = await self.query_llm_with_debate(material, meas_year, usage)
            else:
                llm_data = await self.query_llm(material, meas_year, usage)

            if llm_data:
                print(f"✓ LLM returned {len(llm_data)} countries")

                # Add HS code to LLM data (confidence and reasoning should already be from agent)
                hs_code = self.lookup_hs_code(material)
                for country in llm_data:
                    country["hs_code"] = hs_code

                    # Ensure reasoning field exists (fallback if LLM didn't provide it)
                    if "reasoning" not in country or not country["reasoning"]:
                        source = "multi-agent debate consensus" if use_debate else "LLM estimate"
                        country["reasoning"] = (
                            f"LLM-generated estimate from {source} - "
                            f"no USGS data available for {material} in {meas_year}"
                        )

                self.cache[cache_key] = llm_data

                # Save to transcript if provided
                source = "Multi-Agent Debate" if use_debate else "LLM Fallback"
                if transcript_path:
                    self.append_country_data_to_transcript(
                        transcript_path, material, llm_data, source=source
                    )

                return llm_data

        print(f"✗ No data found for {material}")
        return []

    def lookup_hs_code(self, material: str) -> Optional[str]:
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
            df = pd.read_csv("./data/hs_codes_and_usgs_names.csv")

            # Verify column exists
            if "HS Code" not in df.columns:
                return None

            # Clean the material name
            material_clean = material.lower().strip()

            # Try exact match first
            match = df[df["Elements/Compounds"].str.lower().str.strip() == material_clean]
            if not match.empty:
                hs_code_value = match.iloc[0]["HS Code"]
                # Check if value is not NaN and not empty
                if pd.notna(hs_code_value) and str(hs_code_value).strip():
                    return str(int(hs_code_value))  # Convert to int first to remove .0

            # Try partial match if exact failed
            match = df[
                df["Elements/Compounds"]
                .str.lower()
                .str.contains(material_clean, na=False, regex=False)
            ]
            if not match.empty:
                hs_code_value = match.iloc[0]["HS Code"]
                if pd.notna(hs_code_value) and str(hs_code_value).strip():
                    return str(int(hs_code_value))

        except Exception as e:
            print(f"HS lookup error for {material}: {e}")
            return None

        return None

    def query_usgs(
        self,
        material: str,
        src_year: int,
        meas_year: int,
    ) -> List[Dict]:
        """
        Query USGS database for country data with confidence scoring.

        Args:
            material: Material name
            src_year: Source year
            meas_year: Measurement year

        Returns:
            List of country data dicts with confidence and reasoning
        """
        try:
            # Get top countries
            countries_df = self.usgs_client.query_top_countries(material, src_year, meas_year)
            if countries_df is None or len(countries_df) == 0:
                return []

            # Get world totals (returns DataFrame)
            world_totals_df = self.usgs_client.query_world_totals(material, src_year, meas_year)
            if world_totals_df is None or world_totals_df.empty:
                logger.warning(f"No world totals data for {material}")
                return []

            # Extract production value from DataFrame
            try:
                value_col = pd.Series(world_totals_df["VALUE"])  # type: ignore[assignment]
                numeric_series = pd.Series(pd.to_numeric(value_col, errors="coerce"))  # type: ignore[assignment]
                world_production_sum = numeric_series.sum()
                world_production = (
                    float(world_production_sum) if pd.notna(world_production_sum) else 0.0
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"Could not extract world production for {material}: {e}")
                return []

            if world_production == 0:
                logger.warning(f"No world production data for {material}")
                return []

            # Build country data with confidence
            country_data = []
            for country_name in countries_df["country"]:
                details_df = self.usgs_client.query_country_details(
                    material, country_name, src_year, meas_year
                )
                if details_df is None or details_df.empty:
                    continue

                for _, row in details_df.iterrows():
                    try:
                        if str(row.get("MEAS_TYPE", "")).upper() == "PRODUCTION":
                            value_raw = row.get("VALUE", 0)
                            amount_numeric = pd.to_numeric(value_raw, errors="coerce")
                            amount = float(amount_numeric)  # type: ignore[arg-type]

                            if math.isnan(amount):
                                continue

                            percentage = (
                                (amount / world_production * 100) if world_production > 0 else 0.0
                            )

                            country_data.append(
                                {
                                    "country": country_name,
                                    "meas_unit": row.get("MEAS_UNIT", ""),
                                    "amount": amount,
                                    "percentage": percentage,
                                    # USGS confidence added by caller
                                }
                            )
                            break  # Only take production data
                    except (ValueError, TypeError, KeyError) as e:
                        logger.debug(f"Error processing row for {country_name}: {e}")
                        continue

            return country_data

        except Exception as e:
            logger.error(f"Error in query_usgs for {material}: {e}", exc_info=True)
            return []

    async def query_llm(
        self,
        material: str,
        year: int,
        usage: Optional[RunUsage] = None,
    ) -> List[Dict]:
        """
        Query LLM agent for country data (single-agent fallback) with confidence.

        Args:
            material: Material name
            year: Year for production data
            usage: Optional RunUsage tracker

        Returns:
            List of country data dicts with LLM-provided confidence and reasoning
        """
        if not self.country_agent:
            return []

        prompt = (
            f"Return the top {self.top_n} countries that produced {material} in {year}, "
            f"with production amounts (numeric values with units) and percentage of global supply. "
            f"Use the most recent data available (preferably {year} or within 2-3 years). "
            f"Ensure percentages sum to a reasonable total and amounts are specific numbers, not estimates. "
            f"IMPORTANT: Provide confidence score (0.0-1.0) and reasoning for each country estimate."
        )

        try:
            result = await self.country_agent.run(
                prompt,
                deps=self.deps,
                model=self.deps.model,
            )

            if result and result.output:
                country_list = result.output

                # Extract data with confidence from CountryPercentage objects
                country_data = [
                    {
                        "country": cp.country,
                        "meas_unit": cp.measurement_unit or "metric tons",
                        "amount": 0.0,  # LLM may not always provide amount
                        "percentage": cp.percentage,
                        "confidence": cp.confidence,  # LLM-provided confidence
                        "reasoning": cp.reasoning or "LLM estimate",
                    }
                    for cp in country_list.country_list
                ]

                return country_data

        except Exception as e:
            print(f"LLM query failed for {material}: {e}")
            return []

        return []

    async def query_llm_with_debate(
        self,
        material: str,
        year: int,
        usage: Optional[RunUsage] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query LLM with multi-agent debate for country data with confidence.

        Args:
            material: Material name
            year: Year for production data
            usage: Optional RunUsage tracker

        Returns:
            List of country data dicts with debate-weighted confidence and reasoning
        """
        from ..debate import MaterialCountryDebater

        debater = MaterialCountryDebater(
            deps=self.deps,
            num_agents=3,
            top_n_proposed=10,
            top_n_consensus=self.top_n,
            debate_top_p=0.0001,
        )

        debate_result = await debater.run_debate(material, year, usage)

        # Store debate info for transcript
        self.last_debate_result = debate_result
        self.last_debater = debater

        # Normalize debate consensus to standard format with reasoning
        consensus_items = debate_result.get("consensus", [])

        country_data = []
        for item in consensus_items:
            # Handle both CountryPercentage objects and dicts
            if hasattr(item, "country"):
                # It's a CountryPercentage object
                country_data.append(
                    {
                        "country": item.country,
                        "meas_unit": item.measurement_unit or "metric tons",
                        "amount": item.amount or 0.0,
                        "percentage": item.percentage,
                        "confidence": item.confidence,
                        "reasoning": item.reasoning
                        or "Multi-agent debate consensus",  # ✅ EXTRACT REASONING
                    }
                )
            elif isinstance(item, dict):
                # It's already a dict - ensure reasoning exists
                country_data.append(
                    {
                        "country": item.get("country", "Unknown"),
                        "meas_unit": item.get("meas_unit")
                        or item.get("measurement_unit")
                        or "metric tons",
                        "amount": item.get("amount", 0.0),
                        "percentage": item.get("percentage", 0.0),
                        "confidence": item.get("confidence", 0.75),
                        "reasoning": item.get("reasoning")
                        or "Multi-agent debate consensus",  # ✅ ENSURE REASONING
                    }
                )

        return country_data

    def append_country_data_to_transcript(
        self,
        transcript_path: Path,
        material: str,
        country_data: List[Dict[str, Any]],
        source: str = "Database",
    ) -> None:
        """
        Append country production data to existing transcript with confidence.

        Args:
            transcript_path: Path to transcript file
            material: Material name
            country_data: List of country data dicts with confidence
            source: Data source description
        """
        try:
            # If we have debate info, use detailed format
            if source == "Multi-Agent Debate" and hasattr(self, "last_debater"):
                debate_result = getattr(self, "last_debate_result", None)
                debater = getattr(self, "last_debater", None)

                if debater and debate_result:
                    formatted = debater.format_debate_for_transcript(material, debate_result)
                    with open(transcript_path, "a", encoding="utf-8") as f:
                        f.write(formatted)
                        f.flush()
                    logger.info(f"Appended full debate for {material} to transcript")
                    return

            # Otherwise use simple format (USGS or simple LLM)
            lines = []
            lines.append("\n\n")
            lines.append("=" * 60 + "\n")
            lines.append(f"TOP PRODUCING COUNTRIES: {material}\n")
            lines.append(f"Data Source: {source}\n")
            lines.append("=" * 60 + "\n")

            if not country_data:
                lines.append("  No country data available\n")
            else:
                for idx, country_info in enumerate(country_data, 1):
                    country = country_info.get("country", "Unknown")
                    percentage = country_info.get("percentage", 0.0)
                    amount = country_info.get("amount", 0.0)
                    unit = country_info.get("meas_unit", "")
                    confidence = country_info.get("confidence", 0.0)
                    reasoning = country_info.get("reasoning", "")

                    lines.append(f"{idx}. {country}\n")
                    lines.append(f"   Production: {amount:,.2f} {unit}\n")
                    lines.append(f"   Global Share: {percentage:.1f}%\n")
                    lines.append(f"   Confidence: {confidence:.2f}\n")
                    if reasoning:
                        lines.append(f"   Reasoning: {reasoning}\n")

            lines.append("=" * 60 + "\n")

            with open(transcript_path, "a", encoding="utf-8") as f:
                f.write("".join(lines))
                f.flush()

            logger.info(f"Appended country data for {material} to transcript")

        except Exception as e:
            logger.error(f"Error appending country data to transcript: {e}")

    def clear_cache(self):
        """Clear the country data cache."""
        self.cache.clear()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cached_materials": len(self.cache),
            "materials": list(self.cache.keys()),
        }

    def close(self):
        """Close database connections."""
        if self.usgs_client:
            self.usgs_client.close()


__all__ = ["CountryDataRepository"]
