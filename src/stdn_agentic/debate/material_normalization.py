from __future__ import annotations


def normalize_component_name(name: str) -> str:
    """Normalize component name for comparison.

    Mirrors the logic used by MaterialDebater for consistent matching.
    """
    if not name:
        return ""

    # Lowercase and strip
    normalized = name.lower().strip()

    # Remove hyphens, underscores
    normalized = normalized.replace("-", " ").replace("_", " ")

    # Collapse whitespace
    normalized = " ".join(normalized.split())

    # Remove trailing qualifiers
    qualifiers = [
        "module",
        "system",
        "unit",
        "assembly",
        "component",
        "subsystem",
        "device",
        "apparatus",
        "mechanism",
        "pack",
    ]
    for qualifier in qualifiers:
        if normalized.endswith(f" {qualifier}"):
            normalized = normalized[: -len(qualifier) - 1].strip()

    return normalized


def normalize_material_name(name: str) -> str:
    """Normalize material name for comparison.

    Shared helper so all agents and phases use the same mapping.
    """
    if not name:
        return ""

    normalized = name.lower().strip()
    normalized = normalized.replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())

    # Handle common variations
    material_variants = {
        "lithium ion": "lithium",
        "li-ion": "lithium",
        "rare earth elements": "rare earth",
        "ree": "rare earth",
        "stainless steel": "steel",
    }

    return material_variants.get(normalized, normalized)
