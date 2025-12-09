from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field
from pydantic_ai import Agent


def normalize_component_name(name: str) -> str:
    """Normalize component name using a rule-based approach."""
    if not name:
        return ""

    normalized = name.lower().strip()
    normalized = normalized.replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())

    qualifiers = [
        "system",
        "module",
        "unit",
        "assembly",
        "component",
        "subsystem",
        "package",
        "chipset",
    ]
    words = normalized.split()
    while len(words) > 1 and words[-1] in qualifiers:
        words.pop()

    return " ".join(words)


async def normalize_components_with_llm(
    component_names: List[str],
    component_agent: Any,
    deps: Any,
) -> Dict[str, str]:
    """
    Use LLM to normalize component names semantically.

    Falls back to rule-based normalization if the LLM call fails.
    """
    unique_names = list(set(component_names))
    if len(unique_names) <= 1:
        return {name: normalize_component_name(name) for name in unique_names}

    class ComponentMapping(BaseModel):
        mappings: Dict[str, str] = Field(description="Component name mappings")

    names_list = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(unique_names))
    prompt = (
        "Map duplicate/similar component names to canonical names.\n\n"
        "CRITICAL: All output must be in English only. If any input names are in other\n"
        "languages, translate them to English equivalents before mapping.\n\n"
        "AVOID OVERLY GENERIC NAMES:\n"
        '- Do NOT use vague terms like "Chip", "Module", "Component", "Part", "Unit"\n'
        '- Use SPECIFIC names like "Memory Chip", "Power IC", "Display Module"'
    )

    mapping_agent = Agent(
        model=deps.model,
        output_type=ComponentMapping,
        system_prompt=prompt,
    )
    result = await mapping_agent.run(names_list, deps=deps)

    if not result or not result.output:
        return {name: normalize_component_name(name) for name in unique_names}

    return {
        name: normalize_component_name(canonical)
        for name, canonical in result.output.mappings.items()
    }
