"""
Pydantic data models for STDN semantic normalization.

This module defines models for normalizing STDN components across multiple runs
without deduplication. Each run's records are preserved with their original values
while adding normalized fields for semantic consistency.

Key Models:
- NormalizedComponent: Individual component with both original and normalized fields
- NormalizedDependency: Dependency relationship with normalized component references
- SemanticGroup: Group of semantically similar components with canonical representation
- ConsolidatedNormalizedSTDN: Complete normalized output containing all runs
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Normalized Component Model
# ============================================================================


class NormalizedComponent(BaseModel):
    """
    Component with normalized fields while preserving original values.

    Each component retains its original identity and provenance from a specific
    run, while also containing normalized fields that match semantically similar
    components across different runs.

    Example:
        Run 1 has "LCD" → normalized to "Liquid Crystal Display"
        Run 2 has "Liquid Crystal Display" → stays "Liquid Crystal Display"
        Run 3 has "LCD Panel" → normalized to "Liquid Crystal Display"

        All three records are kept separately, but all have the same
        normalized_name, allowing them to be grouped and compared.

    Attributes:
        original_id: Original component identifier from source run
        original_name: Original component name as it appeared in the run
        source_run: Run identifier (e.g., "run_20260105_100823")
        source_technology: Technology this component belongs to

        normalized_name: Canonical name determined by semantic reconciliation
        normalized_type: Canonical type (e.g., "hardware_component")
        normalized_description: Synthesized canonical description
        normalized_purpose: Synthesized canonical purpose
        normalized_characteristics: Union of relevant characteristics

        semantic_group_id: Links to SemanticGroup (e.g., "group_0001")

        original_type: Original type field from source run
        original_description: Original description from source run
        original_purpose: Original purpose from source run
        original_characteristics: Original characteristics list from source run

        confidence: Confidence score from original run
        timestamp: When this run was executed
    """

    # ========================================================================
    # Original Identity and Provenance
    # ========================================================================

    original_id: str = Field(
        description="Original component ID from source run",
        examples=["comp_001", "component_lcd_run1_005"],
    )

    original_name: str = Field(
        description="Original component name as it appeared in source run",
        examples=["LCD", "Liquid Crystal Display", "LCD Panel"],
    )

    source_run: str = Field(
        description="Identifier of the run that generated this component",
        examples=["run_20260105_100823", "stdns_output_20260101_093731"],
    )

    source_technology: str = Field(
        description="Technology this component belongs to",
        examples=["smartphone", "laptop", "electric vehicle"],
    )

    # ========================================================================
    # Normalized Fields (Canonical Representation)
    # ========================================================================

    normalized_name: str = Field(
        description="Canonical component name determined by semantic reconciliation",
        examples=["Liquid Crystal Display", "Central Processing Unit"],
    )

    normalized_type: str = Field(
        description="Canonical component type",
        examples=["hardware_component", "electronic_component", "software_module"],
    )

    normalized_description: str = Field(
        description="Synthesized canonical description from all similar components"
    )

    normalized_purpose: str = Field(description="Synthesized canonical purpose statement")

    normalized_characteristics: List[str] = Field(
        default_factory=list,
        description="Union of characteristics from all similar components",
        examples=[["electronic", "display", "visual_output", "lcd_technology"]],
    )

    # ========================================================================
    # Semantic Grouping
    # ========================================================================

    semantic_group_id: str = Field(
        description="Identifier linking to SemanticGroup of similar components",
        examples=["group_0001", "group_0042"],
    )

    # ========================================================================
    # Original Values (Preserved for Traceability)
    # ========================================================================

    original_type: str = Field(
        description="Original type field from source run (may differ from normalized)",
        examples=["hardware", "display_hardware", "component"],
    )

    original_description: str = Field(description="Original description text from source run")

    original_purpose: str = Field(description="Original purpose statement from source run")

    original_characteristics: List[str] = Field(
        default_factory=list,
        description="Original characteristics list from source run",
    )

    # ========================================================================
    # Metadata
    # ========================================================================

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from original run",
        examples=[0.85, 0.92],
    )

    timestamp: datetime = Field(description="Timestamp when the source run was executed")

    # ========================================================================
    # Optional Material Information (from STDN context)
    # ========================================================================

    materials: Optional[List[str]] = Field(
        default=None,
        description="Materials associated with this component (if available)",
    )

    hs_codes: Optional[List[str]] = Field(
        default=None,
        description="HS codes for materials (if available)",
    )


# ============================================================================
# Normalized Dependency Model
# ============================================================================


class NormalizedDependency(BaseModel):
    """
    Dependency relationship with normalized component references.

    Dependencies are also normalized to use canonical component identifiers,
    allowing relationships to be traced across runs even when component names
    differ.

    Attributes:
        original_id: Original dependency ID from source run
        source_run: Run identifier where this dependency was identified
        source: Normalized component ID (source of dependency)
        target: Normalized component ID (target of dependency)
        dependency_type: Type of dependency relationship
        original_source: Original source component name from run
        original_target: Original target component name from run
        confidence: Confidence score for this dependency
        timestamp: When this was identified
    """

    original_id: str = Field(description="Original dependency ID from source run")

    source_run: str = Field(description="Identifier of the run that generated this dependency")

    # Normalized references (using semantic_group_id or normalized names)
    source: str = Field(
        description="Normalized source component identifier",
        examples=["group_0001", "Liquid Crystal Display"],
    )

    target: str = Field(
        description="Normalized target component identifier",
        examples=["group_0042", "Graphics Processing Unit"],
    )

    dependency_type: str = Field(
        description="Type of dependency relationship",
        examples=["requires", "uses", "contains", "connects_to"],
    )

    # Original values
    original_source: str = Field(
        description="Original source component name from run",
        examples=["LCD", "Display Component"],
    )

    original_target: str = Field(
        description="Original target component name from run",
        examples=["GPU", "Graphics Card"],
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this dependency",
    )

    timestamp: datetime = Field(description="Timestamp when this dependency was identified")


# ============================================================================
# Semantic Group Model
# ============================================================================


class SemanticGroup(BaseModel):
    """
    Group of semantically similar components with canonical representation.

    Each semantic group represents a "concept" that appears across multiple
    runs with different names or descriptions. The group maintains the
    canonical (best) representation along with metadata about all members.

    Example:
        Group "group_0012" might contain:
        - "LCD" (from run 1)
        - "Liquid Crystal Display" (from run 2)
        - "LCD Panel" (from run 3)

        Canonical representation: "Liquid Crystal Display"

    Attributes:
        group_id: Unique identifier for this semantic group
        canonical_name: Best representative name for this concept
        canonical_type: Best representative type
        canonical_description: Synthesized description from all members
        canonical_purpose: Synthesized purpose statement
        canonical_characteristics: Union of all member characteristics
        member_count: Number of components in this group
        member_runs: List of run IDs that contributed components
        member_component_ids: Original component IDs of all members
        confidence_avg: Average confidence across all members
        confidence_min: Minimum confidence among members
        confidence_max: Maximum confidence among members
    """

    group_id: str = Field(
        description="Unique identifier for this semantic group",
        examples=["group_0001", "group_0042"],
    )

    # ========================================================================
    # Canonical Representation
    # ========================================================================

    canonical_name: str = Field(
        description="Best representative name for this concept",
        examples=["Liquid Crystal Display", "Central Processing Unit"],
    )

    canonical_type: str = Field(
        description="Best representative type",
        examples=["hardware_component", "electronic_component"],
    )

    canonical_description: str = Field(
        description="Synthesized description from all member components"
    )

    canonical_purpose: str = Field(description="Synthesized purpose statement from all members")

    canonical_characteristics: List[str] = Field(
        default_factory=list,
        description="Union of characteristics from all member components",
    )

    # ========================================================================
    # Member Metadata
    # ========================================================================

    member_count: int = Field(
        ge=1,
        description="Number of components in this semantic group",
        examples=[3, 5, 1],
    )

    member_runs: List[str] = Field(
        description="List of run IDs that contributed components to this group",
        examples=[["run_20260105_100823", "run_20260105_103456"]],
    )

    member_component_ids: List[str] = Field(
        default_factory=list,
        description="Original component IDs of all members in this group",
        examples=[["comp_run1_005", "comp_run2_003", "comp_run3_007"]],
    )

    # ========================================================================
    # Confidence Statistics
    # ========================================================================

    confidence_avg: float = Field(
        ge=0.0,
        le=1.0,
        description="Average confidence score across all members",
    )

    confidence_min: float = Field(
        ge=0.0,
        le=1.0,
        description="Minimum confidence score among members",
    )

    confidence_max: float = Field(
        ge=0.0,
        le=1.0,
        description="Maximum confidence score among members",
    )


# ============================================================================
# Consolidated Normalized STDN
# ============================================================================


class ConsolidatedNormalizedSTDN(BaseModel):
    """
    Complete normalized STDN output containing all runs.

    This is the final output of the normalization process. It contains:
    1. All components from all runs (no deduplication)
    2. Each component with both original and normalized fields
    3. Semantic groups defining the canonical representations
    4. Dependencies with normalized references
    5. Metadata about the normalization process

    Attributes:
        components: All components from all runs, with normalized fields
        semantic_groups: Semantic groupings with canonical representations
        dependencies: Dependencies with normalized component references
        normalization_meta Statistics and info about the normalization
    """

    components: List[NormalizedComponent] = Field(
        description="All components from all runs, each with normalized fields"
    )

    semantic_groups: List[SemanticGroup] = Field(
        description="Semantic groupings with canonical representations"
    )

    dependencies: Optional[List[NormalizedDependency]] = Field(
        default_factory=list,
        description="Dependencies with normalized component references",
    )

    normalization_metadata: Dict[str, Any] = Field(
        description="Metadata about the normalization process",
        examples=[
            {
                "total_runs": 3,
                "total_components": 45,
                "semantic_groups": 30,
                "avg_group_size": 1.5,
                "reduction_ratio": 0.67,
                "normalization_timestamp": "2026-01-05T10:54:00",
                "similarity_threshold": 0.88,
                "embedding_model": "text-embedding-3-large",
            }
        ],
    )


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "NormalizedComponent",
    "NormalizedDependency",
    "SemanticGroup",
    "ConsolidatedNormalizedSTDN",
]
