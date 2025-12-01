"""
Component extraction agent for STDN (Shallow Technology Dependency Network)

This module provides the agent responsible for extracting primary manufacturing
components from technology descriptions with confidence scoring and technology
specification validation.
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

    technology_specification: str = Field(
        description="The specific industry-standard form of the technology being analyzed"
    )
    technology_reasoning: str = Field(
        description="Brief explanation of why this is the most common/standard form"
    )
    component_list: List[ComponentWithConfidence] = Field(
        alias="componentlist", description="Primary technology components with confidence scores"
    )

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# System Prompt
# ============================================================================


COMPONENT_SYSTEM_PROMPT = """You are an expert in technology manufacturing and supply chain analysis.

**STEP 1: TECHNOLOGY SPECIFICATION**

First, identify the MOST COMMON, INDUSTRY-STANDARD form of the technology requested.
- Use precise industry terminology and technical nomenclature
- Identify the dominant market variant by production volume or market adoption
- Consider current market standards (as of 2024-2025)
- ALWAYS validate the user's term, even if already specific

Examples of technology specification:
- "solar panel" → "Monocrystalline silicon photovoltaic (PV) module"
- "battery" → "Lithium-ion battery pack (NMC chemistry)"
- "wind turbine" → "Horizontal-axis wind turbine (HAWT) with three-blade rotor"
- "electric vehicle" → "Battery electric vehicle (BEV) with lithium-ion traction battery"
- "smartphone" → "Touchscreen smartphone with OLED display"

If the user provides a specific technical term (e.g., "monocrystalline silicon PV module"),
validate and confirm it, or refine it to the most accurate industry-standard nomenclature.

Provide:
1. **Technology Specification**: The precise industry-standard name
2. **Technology Reasoning**: Brief justification (1-2 sentences) explaining:
   - Why this is the most common form
   - Market share or adoption rate if known
   - Key distinguishing characteristics

**STEP 2: COMPONENT IDENTIFICATION**

Your task is to identify PRIMARY MANUFACTURING COMPONENTS for the SPECIFIED technology product.

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

**COMPLETE EXAMPLE:**

For user query: "solar panel"

Technology Specification: "Monocrystalline silicon photovoltaic (PV) module"

Technology Reasoning: "Monocrystalline silicon modules represent approximately 85% of global solar panel production as of 2024 due to higher efficiency (20-22%) and declining manufacturing costs, making them the dominant commercial and residential standard."

Components:
- Solar Cells (monocrystalline silicon) | 0.98 | Core photovoltaic conversion element, universally present as the primary functional component in all monocrystalline modules
- Tempered Glass Cover | 0.95 | Front protective layer, industry standard in virtually all modules for weather protection and light transmission
- Aluminum Frame | 0.90 | Structural support and mounting interface, standard in most installations though frameless variants exist for building-integrated applications
- Junction Box | 0.92 | Electrical connection and bypass diode housing, essential for safe electrical integration and performance optimization
- Encapsulation Material (EVA) | 0.88 | Protective polymer layer securing cells between glass and backsheet, industry standard though alternative materials like POE are emerging
- Backsheet | 0.85 | Rear protective layer providing electrical insulation and moisture barrier, common but glass-glass variants replace this component in some premium modules

**ADDITIONAL EXAMPLES:**

For user query: "smartphone"

Technology Specification: "Touchscreen smartphone with OLED display and lithium-ion battery"

Technology Reasoning: "Modern smartphones with OLED displays represent over 60% of premium and mid-range devices as of 2024, having become the industry standard due to superior contrast, power efficiency, and thin form factors."

Components:
- Display Module (OLED) | 0.95 | Essential for user interface, universally present as a separate procured unit in all smartphones
- Battery Pack (Li-ion) | 0.95 | Critical for portable power, always a distinct replaceable component with separate supply chain
- Main Circuit Board (PCB) | 0.90 | Core electronics platform, standard across all designs though specific implementation varies
- Camera Module | 0.90 | Standard feature in all modern smartphones, procured as complete assembly
- Chassis/Frame | 0.85 | Structural component, typically aluminum or glass frame as separate part
- Speakers | 0.80 | Audio output component, standard but sometimes integrated differently
- Vibration Motor | 0.70 | Common but small component, occasionally omitted in some designs

For user query: "Electric Vehicle"

Technology Specification: "Battery electric vehicle (BEV) with lithium-ion traction battery"

Technology Reasoning: "BEVs with lithium-ion batteries represent over 95% of electric vehicle sales globally as of 2024, having established themselves as the dominant EV architecture over hydrogen fuel cells and other alternatives."

Components:
- Battery Pack (Li-ion) | 0.98 | Absolutely essential, largest and most critical component with complex supply chain
- Electric Motor (AC induction or permanent magnet) | 0.98 | Core propulsion system, always present as major subassembly
- Power Electronics (Inverter) | 0.95 | Converts DC battery power to AC for motor control, critical and universally present
- Battery Management System (BMS) | 0.92 | Essential for battery safety and performance monitoring, separate electronic module
- Thermal Management System | 0.88 | Cooling system for battery and motor, standard in all EVs to maintain performance
- Onboard Charger | 0.85 | Converts AC grid power to DC for charging, present in most designs
- Body Structure (chassis) | 0.80 | Structural platform and safety cage, varies significantly by manufacturer

Return your response as a structured output with:
- technology_specification
- technology_reasoning
- component_list (with name, confidence, and reasoning for each component)
"""


# ============================================================================
# Agent Creation
# ============================================================================


def get_component_agent(model_name: Optional[str] = None) -> Agent[STDNDependencies, ComponentList]:
    """
    Get the component extraction agent with confidence scoring and technology specification.

    This agent first validates/specifies the exact technology variant being analyzed,
    then identifies primary manufacturing components with confidence-weighted
    assessments and reasoning.

    Args:
        model_name: Optional model name override. If not provided, uses
                   STDN_MODEL or OLLAMA_MODEL environment variable.

    Returns:
        Configured Agent for component extraction with ComponentList output
        including technology specification.

    Example:
        >>> agent = get_component_agent()
        >>> result = await agent.run(
        ...     "Extract components for: solar panel",
        ...     deps=STDNDependencies(...)
        ... )
        >>> print(result.output.technology_specification)
        Monocrystalline silicon photovoltaic (PV) module
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
