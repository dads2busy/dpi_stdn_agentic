"""
Component extraction agent for STDN (Supply Technology Dependency Network)

This module provides the agent responsible for extracting primary manufacturing
components from technologies using LLM analysis.

The component agent identifies major subassemblies, functional modules, and
structural components while excluding raw materials, tools, and consumables.
"""

import os
from typing import List

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from ..models import STDNDependencies

# ============================================================================
# Data Models
# ============================================================================


class ComponentList(BaseModel):
    """Structured output for technology components"""

    component_list: List[str] = Field(
        description="Primary technology components (major subassemblies, "
        "functional modules, structural elements)"
    )


# ============================================================================
# Component Extraction Agent
# ============================================================================

COMPONENT_SYSTEM_PROMPT = """You are an expert supply chain analyst specializing in component identification and technology decomposition.

Your task is to identify PRIMARY MANUFACTURING COMPONENTS for a given technology product.

INCLUDE in your component list:
- Major subassemblies (e.g., display module, power module, processing unit)
- Functional modules with distinct supply chains
- Structural components that form the product architecture
- Procurable, separately-manufactured parts

EXCLUDE from your component list:
- Raw materials (metals, plastics, chemicals, elements)
- Manufacturing tools and equipment
- Consumables (adhesives, fasteners, solvents, lubricants)
- Generic supplies or utilities
- Manufacturing processes or services

When identifying components:
1. Think about how the product is designed and manufactured
2. Consider which parts have separate supply chains
3. Identify parts that could be sourced from different suppliers
4. Look at the assembly hierarchy from subassemblies down to major parts

Return a JSON response with a list of component names.
Focus on accuracy over completeness - better to miss a component than to
incorrectly classify a raw material or tool as a component.

Be specific: "lithium-ion battery pack" not "battery"
Be clear: "aluminum chassis" not just "frame"
Be strategic: Include only items that represent distinct procurement challenges"""


def _get_configured_model() -> str:
    """Get model from config or environment"""
    model = os.environ.get("STDN_MODEL")
    if model:
        return model
    return os.environ.get("OLLAMA_MODEL", "ollama:qwen2:7b")


# Initialize the component extraction agent
component_agent = Agent(
    _get_configured_model(),
    output_type=ComponentList,  # ✓ Changed from result_type
    deps_type=STDNDependencies,  # ✓ Added deps_type
    system_prompt=COMPONENT_SYSTEM_PROMPT,
)


# ============================================================================
# Public API
# ============================================================================


def get_component_agent() -> Agent[STDNDependencies, ComponentList]:
    """
    Get the component extraction agent.

    Returns:
        Agent configured for component extraction from technologies.
        The agent takes technology descriptions and returns a ComponentList
        of primary manufacturing components.

    Example:
        >>> agent = get_component_agent()
        >>> result = await agent.run(
        ...     "smartphone with 5G, high-resolution display, and advanced camera",
        ...     deps=STDNDependencies(...)
        ... )
        >>> print(result.data.component_list)
        ["display_module", "processor_unit", "battery_pack", ...]
    """
    return component_agent
