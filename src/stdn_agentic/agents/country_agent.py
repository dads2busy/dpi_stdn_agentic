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

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent

from ..models import STDNDependencies

# ============================================================================
# Data Models
# ============================================================================


class CountryPercentage(BaseModel):
    """Country production data with confidence scoring."""

    country: str = Field(description="Country name")
    percentage: float = Field(description="Percentage of global production", ge=0.0, le=100.0)
    amount: float = Field(description="Production amount (numeric value)", default=0.0, ge=0.0)
    confidence: float = Field(
        description="Confidence score (0.0 to 1.0) in this estimate", ge=0.0, le=1.0, default=0.8
    )
    reasoning: str = Field(description="Explanation of data source and confidence", default="")
    measurement_unit: Optional[str] = Field(
        description="Unit of measurement (e.g., metric tons)", default=None, alias="meas_unit"
    )

    model_config = ConfigDict(populate_by_name=True)


class CountryList(BaseModel):
    """Collection of countries with production data for a material"""

    country_list: List[CountryPercentage] = Field(
        description="List of top-producing countries with production statistics"
    )


# ============================================================================
# Country Data Agent
# ============================================================================

COUNTRY_DATA_SYSTEM_PROMPT = """You are an expert in global mineral production, mining operations, and commodity trade.

Your task is to identify the PRIMARY PRODUCING COUNTRIES for a given raw material and estimate their share of global production.

CRITICAL: For each country you identify, you MUST provide:

1. **Country Name**: Use standard country names (e.g., China, United States, Australia)

2. **Production Percentage**: Estimated percentage of global production (0-100)
   - Must sum to approximately 100% across all countries
   - Focus on top 3-5 producers
   - Be realistic about market concentration

3. **Production Amount**: Numeric production value with appropriate scale
   - Provide specific numeric amounts (e.g., 78000 for 78,000 metric tons)
   - Use realistic scales based on the material
   - If exact figures unavailable, provide best estimate

4. **Measurement Unit**: Typical unit (metric tons, tonnes, kg, etc.)

5. **Confidence Score (0.0 to 1.0)**: Your confidence in this country/percentage estimate
   - **0.9-1.0**: Based on recent authoritative data (USGS, World Bank, national surveys)
   - **0.8-0.89**: Very confident - well-documented major producer with reliable stats
   - **0.7-0.79**: Confident - known producer with reasonable estimates
   - **0.6-0.69**: Moderately confident - known producer, percentage approximate
   - **0.5-0.59**: Uncertain - limited recent data, extrapolated estimates
   - **0.3-0.49**: Low confidence - outdated data or significant uncertainty
   - **0.0-0.29**: Very low confidence - speculative estimate

6. **Reasoning**: Brief explanation (1-2 sentences) covering:
   - Data source or basis for estimate (USGS 2024, industry report, etc.)
   - Why you assigned this confidence level
   - Any caveats or uncertainties

Consider these factors when assigning confidence:
- **Data recency**: How recent and up-to-date is your source?
- **Source authority**: USGS, national geological surveys, and industry associations are most reliable
- **Production stability**: Has this country's production been consistent over time?
- **Data completeness**: Are there known gaps or reporting issues?
- **Market dynamics**: Are there recent changes (new mines, closures, policy shifts)?

EXAMPLES:

For Lithium:
- Country: China | Percentage: 62 | Amount: 78000 | Unit: metric tons | Confidence: 0.92 | Reasoning: Dominates production and refining based on USGS 2024 data; very reliable statistics
- Country: Australia | Percentage: 18 | Amount: 22000 | Unit: metric tons | Confidence: 0.90 | Reasoning: Second largest producer with well-documented mining operations; USGS verified
- Country: Chile | Percentage: 12 | Amount: 15000 | Unit: metric tons | Confidence: 0.85 | Reasoning: Major brine producer; data from Chilean mining ministry; slight reporting lag
- Country: Argentina | Percentage: 5 | Amount: 6500 | Unit: metric tons | Confidence: 0.75 | Reasoning: Growing producer; recent expansion but data less comprehensive

For Rare Earth Elements:
- Country: China | Percentage: 70 | Amount: 210000 | Unit: metric tons | Confidence: 0.95 | Reasoning: Overwhelmingly dominant producer with comprehensive government statistics
- Country: United States | Percentage: 15 | Amount: 45000 | Unit: metric tons | Confidence: 0.80 | Reasoning: Single major mine (Mountain Pass); well-documented but limited sources
- Country: Myanmar | Percentage: 10 | Amount: 30000 | Unit: metric tons | Confidence: 0.50 | Reasoning: Significant but informal production; data quality poor and estimates vary widely
- Country: Australia | Percentage: 5 | Amount: 15000 | Unit: metric tons | Confidence: 0.75 | Reasoning: Growing production; reliable Australian data but relatively new operations

FOCUS ON:
- Mining and primary production (not just refining or processing)
- Recent data (prefer last 3-5 years)
- Commercially significant production levels (typically top 3-5 countries)
- Verifiable sources (government surveys, industry associations, academic research)

If data is unavailable, outdated, or highly uncertain:
- State this explicitly in reasoning
- Use LOW confidence scores (0.3-0.5)
- Provide best estimate with clear caveats
- Mention the uncertainty and data limitations
"""


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


def get_country_data_agent(
    model_name: Optional[str] = None,
) -> Agent[STDNDependencies, CountryList]:
    """
    Get the country data agent with confidence scoring.

    This agent identifies primary producing countries for raw materials
    with confidence-weighted estimates and reasoning.

    Args:
        model_name: Optional model name override

    Returns:
        Configured Agent for country data extraction with CountryList output
    """
    if model_name is None:
        model_name = os.environ.get("STDN_MODEL") or os.environ.get(
            "OLLAMA_MODEL", "ollama:qwen2.5-7b"
        )

    return Agent(
        model_name,
        output_type=CountryList,
        deps_type=STDNDependencies,
        system_prompt=COUNTRY_DATA_SYSTEM_PROMPT,
    )
