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
from .llm_fallback_cache import LLMFallbackCache
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
        enable_llm_cache: bool = True,
        llm_cache_dir: str = "./data/llm_fallback_cache",
        llm_cache_ttl_hours: int = 720,
    ):
        """
        Initialize country data repository.

        Args:
            database_path: Path to USGS DuckDB database
            deps: STDN dependencies for LLM access
            top_n: Number of top countries to return
            use_llm_fallback: Use LLM when USGS has no data
            enable_llm_cache: Use LLM fallback cache
            llm_cache_dir: Directory for LLM cache files
            llm_cache_ttl_hours: Cache TTL in hours
        """
        self.database_path = database_path
        self.top_n = top_n
        self.deps = deps
        self.use_llm_fallback = use_llm_fallback
        self.enable_llm_cache = enable_llm_cache

        # Initialize USGS client
        self.usgs_client = USGSClient(database_path, top_n=top_n)

        # Initialize LLM agent if fallback enabled
        self.country_agent = get_country_data_agent() if use_llm_fallback else None

        # Initialize LLM fallback cache
        self.llm_cache = None
        if enable_llm_cache and use_llm_fallback:
            self.llm_cache = LLMFallbackCache(
                cache_dir=llm_cache_dir, ttl_hours=llm_cache_ttl_hours
            )
            logger.info(f"✓ LLM fallback cache enabled: {llm_cache_dir}")

        # Cache for material-country mappings
        self.cache: Dict[str, List[Dict]] = {}

    async def get_country_data(
        self,
        material: str,
        src_year: int,
        meas_year: int,
        usage: Optional[RunUsage] = None,
        use_debate: bool = False,
        num_agents: int = 3,
        transcript_path: Optional[Path] = None,
        hs_code: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get country production data for a material with confidence scoring.

        Query order:
        1. Memory cache (fastest)
        2. USGS database (high confidence)
        3. LLM fallback cache (previously successful debates)
        4. LLM debate (expensive, cached for future)
        """
        # Check memory cache
        cache_key = f"{material}_{src_year}_{meas_year}"
        if cache_key in self.cache:
            logger.info(f"✓ Memory cache hit for {material}")
            return self.cache[cache_key]

        # Try USGS database first
        logger.info(f"Querying USGS for {material} ({src_year}/{meas_year})...")
        usgs_data = self.query_usgs(material, src_year, meas_year)

        if usgs_data:
            return self._process_usgs_data(
                material, usgs_data, src_year, meas_year, cache_key, transcript_path
            )

        # USGS has no data - check LLM fallback cache
        if self.enable_llm_cache and self.llm_cache and hs_code:
            logger.info(f"USGS miss - checking LLM fallback cache for {material}...")
            cached_llm_data = self.llm_cache.get_countries(
                hs_code=hs_code, usgs_name=material, src_year=src_year, meas_year=meas_year
            )

            if cached_llm_data:
                # Cache hit! Update reasoning to reflect it's from cache
                for country_dict in cached_llm_data:
                    country_dict["reasoning"] = (
                        f"LLM fallback cache (previously computed) - "
                        f"no USGS data available for {material}"
                    )

                self.cache[cache_key] = cached_llm_data

                if transcript_path:
                    self.append_country_data_to_transcript(
                        transcript_path, material, cached_llm_data, source="LLM Fallback Cache"
                    )

                logger.info(f"✓ LLM cache hit for {material}: {len(cached_llm_data)} countries")
                return cached_llm_data

        # No USGS, no cache - use LLM fallback
        if not self.use_llm_fallback:
            logger.warning(f"No USGS data for {material} and LLM fallback disabled")
            return []

        logger.info(f"Running LLM fallback for {material}...")
        llm_data = await self._process_llm_fallback(
            material, meas_year, usage, use_debate, num_agents, cache_key, transcript_path
        )

        # Cache successful LLM result in persistent cache for future runs
        if llm_data and self.enable_llm_cache and self.llm_cache:
            if not hs_code:
                hs_code = self.lookup_hs_code(material)

            if hs_code:
                avg_confidence = sum(c.get("confidence", 0.0) for c in llm_data) / len(llm_data)
                self.llm_cache.set_countries(
                    hs_code=hs_code,
                    usgs_name=material,
                    src_year=src_year,
                    meas_year=meas_year,
                    countries=llm_data,
                    confidence=avg_confidence,
                    metadata={"debate_used": use_debate, "num_countries": len(llm_data)},
                )
                logger.info(f"✓ Cached LLM result for future runs: {material}")

        return llm_data if llm_data else []  # ← CORRECT!

    def _process_usgs_data(
        self,
        material: str,
        usgs_data: List[Dict],
        src_year: int,
        meas_year: int,
        cache_key: str,
        transcript_path: Optional[Path],
    ) -> List[Dict]:
        """Process and cache USGS data with metadata."""
        print(f"✓ USGS returned {len(usgs_data)} countries")

        hs_code = self.lookup_hs_code(material)

        for country_dict in usgs_data:
            country_dict["hs_code"] = hs_code
            country_dict["confidence"] = 0.95
            country_dict["reasoning"] = (
                f"USGS Mineral Commodity Summaries {src_year}/{meas_year} - "
                f"authoritative U.S. government production data with global coverage"
            )

        self.cache[cache_key] = usgs_data

        if transcript_path:
            self.append_country_data_to_transcript(
                transcript_path, material, usgs_data, source="USGS Database"
            )

        return usgs_data

    async def _process_llm_fallback(
        self,
        material: str,
        meas_year: int,
        usage: Optional[RunUsage],
        use_debate: bool,
        num_agents: int,
        cache_key: str,
        transcript_path: Optional[Path],
    ) -> List[Dict]:
        """Process LLM fallback data with metadata."""
        print("No USGS data found, using LLM fallback...")

        if use_debate:
            llm_data = await self.query_llm_with_debate(
                material, meas_year, usage, num_agents=num_agents
            )
        else:
            llm_data = await self.query_llm(material, meas_year, usage)

        if not llm_data:
            return []

        print(f"✓ LLM returned {len(llm_data)} countries")

        hs_code = self.lookup_hs_code(material)
        source_description = "multi-agent debate consensus" if use_debate else "LLM estimate"

        for country_dict in llm_data:
            country_dict["hs_code"] = hs_code
            if "reasoning" not in country_dict or not country_dict["reasoning"]:
                country_dict["reasoning"] = (
                    f"LLM-generated estimate from {source_description} - "
                    f"no USGS data available for {material} in {meas_year}"
                )

        self.cache[cache_key] = llm_data

        if transcript_path:
            source_label = "Multi-Agent Debate" if use_debate else "LLM Fallback"
            self.append_country_data_to_transcript(
                transcript_path, material, llm_data, source=source_label
            )

        return llm_data

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

            # ✅ ADD DEBUG
            print(f"🔍 Looking up HS code for: '{material}'")
            print(f"   CSV has {len(df)} rows")

            if "HS_Code" not in df.columns:
                print("   ❌ 'HS_Code' column not found in CSV")
                return None

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

            # ✅ ADD: Show what didn't match
            print(f"   ❌ No match found for '{material}'")
            print(
                f"   Available materials (first 10): {df['Elements_Compounds'].head(10).tolist()}"
            )

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
            countries_df = self.usgs_client.query_top_countries(material, src_year, meas_year)
            if countries_df is None or len(countries_df) == 0:
                return []

            world_production = self._extract_world_production_total(material, src_year, meas_year)
            if world_production == 0:
                return []

            return self._build_country_data_from_usgs(
                material, countries_df, world_production, src_year, meas_year
            )

        except Exception as e:
            logger.error(f"Error in query_usgs for {material}: {e}", exc_info=True)
            return []

    def _extract_world_production_total(
        self, material: str, src_year: int, meas_year: int
    ) -> float:
        """Extract world production total value from USGS data."""
        world_totals_df = self.usgs_client.query_world_totals(material, src_year, meas_year)
        if world_totals_df is None or world_totals_df.empty:
            logger.warning(f"No world totals data for {material}")
            return 0.0

        try:
            value_column = pd.Series(world_totals_df["VALUE"])  # type: ignore[assignment]
            numeric_series = pd.Series(pd.to_numeric(value_column, errors="coerce"))  # type: ignore[assignment]
            world_production_sum = numeric_series.sum()
            world_production = (
                float(world_production_sum) if pd.notna(world_production_sum) else 0.0
            )
            return world_production
        except (KeyError, ValueError) as e:
            logger.warning(f"Could not extract world production for {material}: {e}")
            return 0.0

    def _build_country_data_from_usgs(
        self,
        material: str,
        countries_df: pd.DataFrame,
        world_production: float,
        src_year: int,
        meas_year: int,
    ) -> List[Dict]:
        """Build country data list with production percentages from USGS."""
        country_data_list = []

        for country_name in countries_df["country"]:
            country_entry = self._get_country_production_entry(
                material,
                str(country_name),
                world_production,
                src_year,
                meas_year,  # <-- FIX HERE
            )
            if country_entry:
                country_data_list.append(country_entry)

        return country_data_list

    def _get_country_production_entry(
        self,
        material: str,
        country_name: str,
        world_production: float,
        src_year: int,
        meas_year: int,
    ) -> Optional[Dict]:
        """Get production data entry for a single country from USGS."""
        details_df = self.usgs_client.query_country_details(
            material, country_name, src_year, meas_year
        )
        if details_df is None or details_df.empty:
            return None

        for _, row_data in details_df.iterrows():
            row_data = pd.Series(row_data)  # Explicit cast to help type checker
            production_entry = self._extract_production_from_row(
                row_data, str(country_name), world_production
            )
            if production_entry:
                return production_entry

        return None

    def _extract_production_from_row(
        self, row_data: pd.Series, country_name: str, world_production: float
    ) -> Optional[Dict]:
        """Extract production data from a single USGS database row."""
        try:
            if str(row_data.get("MEAS_TYPE", "")).upper() != "PRODUCTION":
                return None

            value_raw = row_data.get("VALUE", 0)
            amount_numeric = pd.to_numeric(value_raw, errors="coerce")
            amount = float(amount_numeric)  # type: ignore[arg-type]

            if math.isnan(amount):
                return None

            percentage = (amount / world_production * 100) if world_production > 0 else 0.0

            return {
                "country": country_name,
                "meas_unit": row_data.get("MEAS_UNIT", ""),
                "amount": amount,
                "percentage": percentage,
                # USGS confidence added by caller
            }

        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"Error processing row for {country_name}: {e}")
            return None

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
                model=self.deps.get_country_model(),
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
        num_agents: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Query LLM with multi-agent debate for country data with confidence.

        Args:
            material: Material name
            year: Year for production data
            usage: Optional RunUsage tracker
            num_agents: Number of agents for voting (default: 3)

        Returns:
            List of country data dicts with debate-weighted confidence and reasoning
        """
        from ..debate import MaterialCountryDebater

        debater = MaterialCountryDebater(
            deps=self.deps,
            num_agents=num_agents,
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
