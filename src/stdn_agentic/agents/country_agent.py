"""
Country data agent for STDN (Supply Technology Dependency Network)

This module provides the agent responsible for identifying top-producing countries
for raw materials when USGS database data is unavailable. It serves as a fallback
mechanism for material-to-country mapping.

The country agent uses LLM-based reasoning to estimate production data, including
production amounts, units of measure, and percentage of global supply for each
producing country.
"""

import os
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ..models import STDNDependencies

# ============================================================================
# Data Models
# ============================================================================


class CountryPercentage(BaseModel):
    country: str
    meas_unit: str
    amount: float
    percentage: float = Field(ge=0.0, le=100.0)
    hs_code: Optional[str] = None  # ADD THIS LINE


class CountryList(BaseModel):
    """Collection of countries with production data for a material"""

    country_list: List[CountryPercentage] = Field(
        description="List of top-producing countries with production statistics"
    )


# ============================================================================
# Country Data Agent
# ============================================================================

COUNTRY_DATA_SYSTEM_PROMPT = """You are an expert supply chain analyst specializing in global mineral and material production statistics.

Your task is to provide the top-producing countries for a given raw material, along with production statistics.

PROVIDE for each country:
1. Country name or internationally recognized code
2. Approximate amount produced (specific number with units)
3. Unit of measure (metric tons, kilograms, tonnes, etc.)
4. Percentage of global supply that this country produces

FOCUS on:
- Major producing nations (responsible for 80%+ of global supply)
- Strategic producers in geopolitically important regions
- Countries with documented supply chain vulnerabilities
- Producers with export restrictions or sanctions considerations

DATA QUALITY:
- Use most recent publicly available data (within 2-3 years when possible)
- Be specific about measurement units (metric tons ≠ kg ≠ ounces)
- Ensure percentages sum to reasonable total (may be >100% if counting all producers)
- Flag any known supply chain disruptions or constraints

EXCLUDE:
- Informal or unverified producers
- Countries with minimal production (<0.5% global supply)
- Speculative or theoretical production potential

Return a JSON response with a list of countries and their production data.
Be accurate in percentages and amounts - policy decisions depend on this data.
Include confidence indicators if any data points are estimates vs. verified.

For example response format:
{
  "country_list": [
    {"country": "China", "meas_unit": "metric tons", "amount": 10000000, "percentage": 75.5},
    {"country": "Vietnam", "meas_unit": "metric tons", "amount": 1500000, "percentage": 12.3},
    ...
  ]
}"""


def _get_configured_model() -> str:
    """Get model from config or environment"""
    model = os.environ.get("STDN_MODEL")
    if model:
        return model
    return os.environ.get("OLLAMA_MODEL", "ollama:qwen2.5:7b")


# Initialize the country data agent
country_data_agent = Agent(
    _get_configured_model(),
    output_type=CountryList,  # ✓ Changed from result_type
    deps_type=STDNDependencies,  # ✓ Added deps_type
    system_prompt=COUNTRY_DATA_SYSTEM_PROMPT,
)


# ============================================================================
# Public API
# ============================================================================


def get_country_data_agent(model_name: Optional[str] = None) -> Agent[STDNDependencies, CountryList]:
    """
    Get the country data extraction agent.

    This agent is used as a fallback when USGS database queries don't return
    results. It uses LLM reasoning to estimate top-producing countries and
    their production statistics for a given material.

    Returns:
        Agent configured for extracting country production data.
        The agent takes a material name and year, and returns CountryList
        with top-producing countries and their production statistics.

    Example:
        >>> agent = get_country_data_agent()
        >>> result = await agent.run(
        ...     "Return the top 5 countries that produced lithium in 2024, "
        ...     "with production amounts and percentage of global supply.",
        ...     deps=STDNDependencies(...)
        ... )
        >>> print(result.data.country_list)
        [
            CountryPercentage(country="China", meas_unit="metric tons", amount=100000, percentage=65.5),
            CountryPercentage(country="Australia", meas_unit="metric tons", amount=42000, percentage=27.3),
            ...
        ]

    Notes:
        - This agent is typically called by CountryDataGenerator in data/repository.py
        - It serves as a fallback when USGS database queries are empty
        - Results are cached to avoid redundant LLM calls
        - For policy work, USGS data is preferred over LLM estimates
    """
    return country_data_agent