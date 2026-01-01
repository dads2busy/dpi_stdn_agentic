"""
LLM Fallback Cache for Country Repo Stage

This module provides persistent caching of successful LLM debate results
for material-country mappings. It sits between USGS database queries and
expensive LLM debates to dramatically speed up subsequent runs.

The cache stores successful debate results keyed by (hs_code, usgs_name,
src_year, meas_year) tuples with extended TTL (30 days) to preserve
hard-won LLM intelligence.
"""

import logging
from typing import Dict, List, Optional

from .cache import MaterialCache

# Initialize logger
logger = logging.getLogger(__name__)


# ============================================================================
# LLM Fallback Cache
# ============================================================================


class LLMFallbackCache(MaterialCache):
    """
    Specialized cache for successful LLM fallback debate results.

    This cache preserves successful multi-agent debate outcomes to avoid
    redundant expensive LLM calls on future pipeline runs. Each cached
    entry includes the consensus countries, confidence scores, and reasoning.

    The cache uses a 30-day TTL (vs. 24 hours for general material cache)
    to maximize reuse of successful debate results.

    Attributes:
        cache_dir: Directory for cache files (default: ./data/llm_fallback_cache)
        ttl_hours: Time-to-live in hours (default: 720 = 30 days)

    Example:
        >>> cache = LLMFallbackCache()
        >>>
        >>> # Check cache before running debate
        >>> cached = cache.get_countries(
        ...     hs_code="280519",
        ...     usgs_name="lithium",
        ...     src_year=2025,
        ...     meas_year=2024
        ... )
        >>>
        >>> if cached:
        ...     print(f"Cache hit! Using {len(cached)} countries")
        ... else:
        ...     # Run expensive debate
        ...     result = await debater.run_debate(...)
        ...     # Cache successful result
        ...     cache.set_countries(
        ...         hs_code="280519",
        ...         usgs_name="lithium",
        ...         src_year=2025,
        ...         meas_year=2024,
        ...         countries=result["consensus"],
        ...         confidence=0.85
        ...     )
    """

    def __init__(self, cache_dir: str = "./data/llm_fallback_cache", ttl_hours: int = 720):
        """
        Initialize LLM fallback cache.

        Args:
            cache_dir: Directory to store cache files (default: ./data/llm_fallback_cache)
            ttl_hours: Cache TTL in hours (default: 720 = 30 days)
        """
        super().__init__(cache_dir=cache_dir, ttl_hours=ttl_hours)
        logger.info(
            f"Initialized LLM fallback cache: {cache_dir} (TTL: {ttl_hours}h / {ttl_hours / 24:.1f} days)"
        )

    def make_key(self, hs_code: str, usgs_name: str, src_year: int, meas_year: int) -> str:
        """
        Create standardized cache key from material identifiers.

        Args:
            hs_code: HS code for the material
            usgs_name: USGS commodity name
            src_year: Source year of report
            meas_year: Measurement year for production data

        Returns:
            Standardized cache key string
        """
        # Normalize inputs for consistent keys
        hs_code = hs_code.strip().lower()
        usgs_name = usgs_name.strip().lower().replace(" ", "_")
        return f"llm_fallback_{hs_code}_{usgs_name}_{src_year}_{meas_year}"

    def get_countries(
        self, hs_code: str, usgs_name: str, src_year: int, meas_year: int
    ) -> Optional[List[Dict]]:
        """
        Get cached top countries from successful LLM fallback debate.

        Args:
            hs_code: HS code for the material
            usgs_name: USGS commodity name
            src_year: Source year of report
            meas_year: Measurement year for production data

        Returns:
            List of country data dicts with confidence and reasoning, or None if not cached
        """
        key = self.make_key(hs_code, usgs_name, src_year, meas_year)
        cached = self.get(key)

        if cached:
            countries = cached.get("countries", [])
            cache_confidence = cached.get("confidence", 0.0)
            logger.info(
                f"✓ LLM cache hit for {usgs_name} (HS: {hs_code}): "
                f"{len(countries)} countries, confidence={cache_confidence:.2f}"
            )
            return countries

        logger.debug(f"LLM cache miss for {usgs_name} (HS: {hs_code})")
        return None

    def set_countries(
        self,
        hs_code: str,
        usgs_name: str,
        src_year: int,
        meas_year: int,
        countries: List[Dict],
        confidence: float = 1.0,
        metadata: Optional[Dict] = None,
    ):
        """
        Cache successful LLM fallback debate result.

        Args:
            hs_code: HS code for the material
            usgs_name: USGS commodity name
            src_year: Source year of report
            meas_year: Measurement year for production data
            countries: List of country data dicts from debate consensus
            confidence: Overall confidence in this result (default: 1.0)
            meta Optional additional metadata (debate stats, model info, etc.)
        """
        key = self.make_key(hs_code, usgs_name, src_year, meas_year)

        value = {
            "hs_code": hs_code,
            "usgs_name": usgs_name,
            "src_year": src_year,
            "meas_year": meas_year,
            "countries": countries,
            "confidence": confidence,
            "source": "llm_fallback_debate",
            "num_countries": len(countries),
        }

        # Add optional metadata
        if metadata:
            value["metadata"] = metadata

        self.set(key, value)

        logger.info(
            f"✓ Cached LLM result for {usgs_name} (HS: {hs_code}): "
            f"{len(countries)} countries, confidence={confidence:.2f}"
        )

    def get_cache_summary(self) -> Dict:
        """
        Get detailed summary of LLM fallback cache.

        Returns:
            Dict with cache statistics and summary info
        """
        base_stats = self.get_stats()

        # Add LLM-specific summary
        summary = {
            **base_stats,
            "description": "LLM Fallback Debate Results Cache",
            "purpose": "Avoid redundant expensive LLM debates on repeat runs",
        }

        return summary


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "LLMFallbackCache",
]
