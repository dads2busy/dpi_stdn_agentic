"""
Component extraction agent for STDN (Shallow Technology Dependency Network)

This module provides the agent responsible for extracting primary manufacturing
components from technology descriptions with confidence scoring.
"""

import os
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent

from ..models import STDNDependencies

# ============================================================================
# Pydantic Models for Components with Confidence
# ============================================================================


class ComponentWithConfidence(BaseModel):
    """A single component proposal with confidence and reasoning."""

    name: str = Field(description="Component name")
    confidence: float = Field(
        description="Confidence score (0.0 to 1.0) that this is a primary component", ge=0.0, le=1.0
    )
    reasoning: str = Field(description="Brief justification for this component")


class ComponentList(BaseModel):
    """Structured output for technology components with confidence scores."""

    component_list: List[ComponentWithConfidence] = Field(
        alias="componentlist", description="Primary technology components with confidence scores"
    )

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# System Prompt
# ============================================================================


COMPONENT_SYSTEM_PROMPT = """You are an expert in technology manufacturing and supply chain analysis.

Your task is to identify PRIMARY MANUFACTURING COMPONENTS for a technology product.

PRIMARY COMPONENTS are major subassemblies or modules that:
- Are procured or manufactured separately
- Have distinct supply chains
- Form the core functional or structural architecture
- Are typically purchased as complete units

INCLUDE:
- Major functional modules (e.g., display, battery, processor)
- Structural assemblies (e.g., chassis, enclosure)
- Key subassemblies with separate suppliers
- Electronic boards and subsystems

EXCLUDE:
- Raw materials (metals, plastics, chemicals) - these are inputs TO components
- Manufacturing tools and equipment
- Consumables (adhesives, fasteners, solvents, lubricants)
- Generic supplies and packaging materials

CRITICAL: For each component you identify, you MUST provide:

1. **Component Name**: The specific name of the component

2. **Confidence Score (0.0 to 1.0)**: Your confidence that this is truly a PRIMARY component
   - **0.9-1.0**: Absolutely certain - universal standard, always present
   - **0.8-0.89**: Very confident - industry standard, nearly universal
   - **0.7-0.79**: Confident - common in most designs
   - **0.6-0.69**: Moderately confident - common but may vary by design
   - **0.5-0.59**: Uncertain - depends on specific implementation
   - **0.3-0.49**: Low confidence - sometimes integrated differently
   - **0.0-0.29**: Very low confidence - rarely a separate component

3. **Reasoning**: Brief explanation justifying why this is a primary component and your confidence level

Consider these factors when assigning confidence:
- How universally is this component present in the technology?
- Is it typically procured as a separate unit?
- How standardized is this component across manufacturers?
- Are there alternative designs that omit or integrate this component?

Your response will be used for supply chain risk analysis and policy decisions, so accuracy and justified confidence are critical.

EXAMPLES:

For a Smartphone:
- Display Module | 0.95 | Essential for user interface, universally present as a separate procured unit in all smartphones
- Battery Pack | 0.95 | Critical for portable power, always a distinct replaceable component with separate supply chain
- Main Circuit Board | 0.90 | Core electronics platform, standard across all designs though specific implementation varies
- Camera Module | 0.90 | Standard feature in all modern smartphones, procured as complete assembly
- Chassis/Frame | 0.85 | Structural component, typically aluminum or steel frame as separate part
- Speakers | 0.80 | Audio output component, standard but sometimes integrated differently
- Vibration Motor | 0.70 | Common but small component, occasionally omitted in some designs

For an Electric Vehicle:
- Battery Pack | 0.98 | Absolutely essential, largest and most critical component with complex supply chain
- Electric Motor | 0.98 | Core propulsion system, always present as major subassembly
- Power Electronics | 0.95 | Inverter and control systems, critical and universally present
- Battery Management System | 0.92 | Essential for battery safety and performance, separate electronic module
- Thermal Management System | 0.88 | Cooling system for battery and motor, standard in all EVs
- Onboard Charger | 0.85 | Converts AC to DC for charging, present in most designs
- Body Structure | 0.80 | Chassis and frame, varies significantly by manufacturer

Return your response as a structured list with name, confidence, and reasoning for each component.
"""


# ============================================================================
# Agent Creation
# ============================================================================


def get_component_agent(model_name: Optional[str] = None) -> Agent[STDNDependencies, ComponentList]:
    """
    Get the component extraction agent with confidence scoring.

    This agent identifies primary manufacturing components for technologies
    with confidence-weighted assessments and reasoning.

    Args:
        model_name: Optional model name override. If not provided, uses
                   STDN_MODEL or OLLAMA_MODEL environment variable.

    Returns:
        Configured Agent for component extraction with ComponentList output.

    Example:
        >>> agent = get_component_agent()
        >>> result = await agent.run(
        ...     "Extract components for: Smartphone",
        ...     deps=STDNDependencies(...)
        ... )
        >>> for comp in result.output.component_list:
        ...     print(f"{comp.name}: {comp.confidence:.2f}")
    """
    if model_name is None:
        model_name = os.environ.get("STDN_MODEL") or os.environ.get(
            "OLLAMA_MODEL", "ollama:qwen2.5-7b"
        )

    return Agent(
        model_name,
        output_type=ComponentList,
        deps_type=STDNDependencies,
        system_prompt=COMPONENT_SYSTEM_PROMPT,
    )


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "ComponentWithConfidence",
    "ComponentList",
    "get_component_agent",
]
