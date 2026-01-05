"""
Unit tests for normalization data models.

These tests verify that the Pydantic models are correctly defined
and can be instantiated with valid data.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from stdn_agentic.normalization.models import (
    ConsolidatedNormalizedSTDN,
    NormalizedComponent,
    NormalizedDependency,
    SemanticGroup,
)


# ============================================================================
# NormalizedComponent Tests
# ============================================================================


def test_normalized_component_creation():
    """Test creating a normalized component with valid data."""
    comp = NormalizedComponent(
        # Original identity
        original_id="comp_001",
        original_name="LCD",
        source_run="run_20260105_100823",
        source_technology="smartphone",
        # Normalized fields
        normalized_name="Liquid Crystal Display",
        normalized_type="hardware_component",
        normalized_description="Electronic visual display using liquid crystals",
        normalized_purpose="Provide visual output for user interaction",
        normalized_characteristics=["electronic", "display", "visual_output"],
        # Semantic grouping
        semantic_group_id="group_0001",
        # Original values
        original_type="hardware",
        original_description="Display component",
        original_purpose="Output",
        original_characteristics=["display"],
        # Metadata
        confidence=0.85,
        timestamp=datetime.now(),
    )

    assert comp.original_name == "LCD"
    assert comp.normalized_name == "Liquid Crystal Display"
    assert comp.semantic_group_id == "group_0001"
    assert comp.source_run == "run_20260105_100823"
    assert comp.confidence == 0.85

    print("✓ NormalizedComponent model works correctly")


def test_normalized_component_with_materials():
    """Test creating a normalized component with optional material data."""
    comp = NormalizedComponent(
        original_id="comp_002",
        original_name="Display Panel",
        source_run="run_20260105_103456",
        source_technology="laptop",
        normalized_name="Liquid Crystal Display",
        normalized_type="hardware_component",
        normalized_description="Electronic visual display",
        normalized_purpose="Visual output",
        normalized_characteristics=["electronic", "display"],
        semantic_group_id="group_0001",
        original_type="component",
        original_description="Display",
        original_purpose="Output",
        original_characteristics=["display"],
        confidence=0.92,
        timestamp=datetime.now(),
        # Optional fields
        materials=["Silicon", "Gallium"],
        hs_codes=["8528", "8542"],
    )

    assert comp.materials == ["Silicon", "Gallium"]
    assert comp.hs_codes == ["8528", "8542"]
    assert comp.normalized_name == "Liquid Crystal Display"

    print("✓ NormalizedComponent with materials works correctly")


def test_normalized_component_validation_confidence():
    """Test that confidence field is properly validated (0.0 to 1.0)."""
    # Valid confidence
    comp = NormalizedComponent(
        original_id="comp_003",
        original_name="Test",
        source_run="run_001",
        source_technology="test",
        normalized_name="Test Component",
        normalized_type="test",
        normalized_description="Test",
        normalized_purpose="Test",
        normalized_characteristics=[],
        semantic_group_id="group_0001",
        original_type="test",
        original_description="Test",
        original_purpose="Test",
        original_characteristics=[],
        confidence=0.5,
        timestamp=datetime.now(),
    )
    assert comp.confidence == 0.5

    # Invalid confidence (> 1.0)
    with pytest.raises(ValidationError):
        NormalizedComponent(
            original_id="comp_004",
            original_name="Test",
            source_run="run_001",
            source_technology="test",
            normalized_name="Test",
            normalized_type="test",
            normalized_description="Test",
            normalized_purpose="Test",
            normalized_characteristics=[],
            semantic_group_id="group_0001",
            original_type="test",
            original_description="Test",
            original_purpose="Test",
            original_characteristics=[],
            confidence=1.5,  # Invalid!
            timestamp=datetime.now(),
        )

    print("✓ Confidence validation works correctly")


# ============================================================================
# NormalizedDependency Tests
# ============================================================================


def test_normalized_dependency_creation():
    """Test creating a normalized dependency."""
    dep = NormalizedDependency(
        original_id="dep_001",
        source_run="run_20260105_100823",
        source="group_0001",
        target="group_0042",
        dependency_type="requires",
        original_source="LCD",
        original_target="GPU",
        confidence=0.88,
        timestamp=datetime.now(),
    )

    assert dep.source == "group_0001"
    assert dep.target == "group_0042"
    assert dep.dependency_type == "requires"
    assert dep.original_source == "LCD"
    assert dep.original_target == "GPU"

    print("✓ NormalizedDependency model works correctly")


# ============================================================================
# SemanticGroup Tests
# ============================================================================


def test_semantic_group_creation():
    """Test creating a semantic group with valid data."""
    group = SemanticGroup(
        group_id="group_0001",
        canonical_name="Liquid Crystal Display",
        canonical_type="hardware_component",
        canonical_description="Electronic visual display using liquid crystal technology",
        canonical_purpose="Provide visual output for user interaction",
        canonical_characteristics=["electronic", "display", "visual_output", "lcd_technology"],
        member_count=3,
        member_runs=["run_20260105_100823", "run_20260105_103456", "run_20260105_104521"],
        member_component_ids=["comp_run1_005", "comp_run2_003", "comp_run3_007"],
        confidence_avg=0.88,
        confidence_min=0.85,
        confidence_max=0.92,
    )

    assert group.group_id == "group_0001"
    assert group.canonical_name == "Liquid Crystal Display"
    assert group.member_count == 3
    assert len(group.member_runs) == 3
    assert len(group.member_component_ids) == 3
    assert group.confidence_avg == 0.88
    assert group.confidence_min <= group.confidence_avg <= group.confidence_max

    print("✓ SemanticGroup model works correctly")


def test_semantic_group_single_member():
    """Test semantic group with only one member (singleton)."""
    group = SemanticGroup(
        group_id="group_0042",
        canonical_name="Graphics Processing Unit",
        canonical_type="hardware_component",
        canonical_description="Specialized processor for graphics",
        canonical_purpose="Process graphical computations",
        canonical_characteristics=["processor", "graphics", "computation"],
        member_count=1,
        member_runs=["run_20260105_100823"],
        member_component_ids=["comp_run1_042"],
        confidence_avg=0.95,
        confidence_min=0.95,
        confidence_max=0.95,
    )

    assert group.member_count == 1
    assert len(group.member_runs) == 1
    assert group.confidence_min == group.confidence_avg == group.confidence_max

    print("✓ SemanticGroup with single member works correctly")


def test_semantic_group_validation_member_count():
    """Test that member_count must be >= 1."""
    # Valid (member_count = 1)
    group = SemanticGroup(
        group_id="group_0001",
        canonical_name="Test",
        canonical_type="test",
        canonical_description="Test",
        canonical_purpose="Test",
        canonical_characteristics=[],
        member_count=1,
        member_runs=["run_001"],
        member_component_ids=["comp_001"],
        confidence_avg=0.5,
        confidence_min=0.5,
        confidence_max=0.5,
    )
    assert group.member_count == 1

    # Invalid (member_count = 0)
    with pytest.raises(ValidationError):
        SemanticGroup(
            group_id="group_0002",
            canonical_name="Test",
            canonical_type="test",
            canonical_description="Test",
            canonical_purpose="Test",
            canonical_characteristics=[],
            member_count=0,  # Invalid!
            member_runs=[],
            member_component_ids=[],
            confidence_avg=0.5,
            confidence_min=0.5,
            confidence_max=0.5,
        )

    print("✓ Member count validation works correctly")


# ============================================================================
# ConsolidatedNormalizedSTDN Tests
# ============================================================================


def test_consolidated_normalized_stdn_creation():
    """Test creating a complete consolidated normalized STDN."""
    # Create sample components
    comp1 = NormalizedComponent(
        original_id="comp_001",
        original_name="LCD",
        source_run="run_001",
        source_technology="smartphone",
        normalized_name="Liquid Crystal Display",
        normalized_type="hardware_component",
        normalized_description="Display",
        normalized_purpose="Visual output",
        normalized_characteristics=["display"],
        semantic_group_id="group_0001",
        original_type="hardware",
        original_description="Display",
        original_purpose="Output",
        original_characteristics=["display"],
        confidence=0.85,
        timestamp=datetime.now(),
    )

    comp2 = NormalizedComponent(
        original_id="comp_002",
        original_name="Liquid Crystal Display",
        source_run="run_002",
        source_technology="laptop",
        normalized_name="Liquid Crystal Display",
        normalized_type="hardware_component",
        normalized_description="Display",
        normalized_purpose="Visual output",
        normalized_characteristics=["display"],
        semantic_group_id="group_0001",
        original_type="display_hardware",
        original_description="LCD screen",
        original_purpose="Visual output",
        original_characteristics=["display", "lcd"],
        confidence=0.92,
        timestamp=datetime.now(),
    )

    # Create semantic group
    group = SemanticGroup(
        group_id="group_0001",
        canonical_name="Liquid Crystal Display",
        canonical_type="hardware_component",
        canonical_description="Electronic visual display",
        canonical_purpose="Visual output",
        canonical_characteristics=["display", "electronic"],
        member_count=2,
        member_runs=["run_001", "run_002"],
        member_component_ids=["comp_001", "comp_002"],
        confidence_avg=0.885,
        confidence_min=0.85,
        confidence_max=0.92,
    )

    # Create consolidated output
    consolidated = ConsolidatedNormalizedSTDN(
        components=[comp1, comp2],
        semantic_groups=[group],
        dependencies=[],
        normalization_metadata={
            "total_runs": 2,
            "total_components": 2,
            "semantic_groups": 1,
            "avg_group_size": 2.0,
            "reduction_ratio": 0.5,
            "normalization_timestamp": datetime.now().isoformat(),
            "similarity_threshold": 0.88,
        },
    )

    assert len(consolidated.components) == 2
    assert len(consolidated.semantic_groups) == 1
    assert consolidated.normalization_metadata["total_runs"] == 2
    assert consolidated.normalization_metadata["semantic_groups"] == 1

    print("✓ ConsolidatedNormalizedSTDN model works correctly")


def test_consolidated_normalized_stdn_json_serialization():
    """Test that consolidated STDN can be serialized to JSON."""
    comp = NormalizedComponent(
        original_id="comp_001",
        original_name="Test",
        source_run="run_001",
        source_technology="test",
        normalized_name="Test Component",
        normalized_type="test",
        normalized_description="Test",
        normalized_purpose="Test",
        normalized_characteristics=[],
        semantic_group_id="group_0001",
        original_type="test",
        original_description="Test",
        original_purpose="Test",
        original_characteristics=[],
        confidence=0.5,
        timestamp=datetime.now(),
    )

    group = SemanticGroup(
        group_id="group_0001",
        canonical_name="Test",
        canonical_type="test",
        canonical_description="Test",
        canonical_purpose="Test",
        canonical_characteristics=[],
        member_count=1,
        member_runs=["run_001"],
        member_component_ids=["comp_001"],
        confidence_avg=0.5,
        confidence_min=0.5,
        confidence_max=0.5,
    )

    consolidated = ConsolidatedNormalizedSTDN(
        components=[comp],
        semantic_groups=[group],
        normalization_metadata={"total_runs": 1},
    )

    # Test JSON serialization
    json_data = consolidated.model_dump(mode="json")
    assert "components" in json_data
    assert "semantic_groups" in json_data
    assert "normalization_metadata" in json_data

    # Test JSON string
    json_str = consolidated.model_dump_json()
    assert isinstance(json_str, str)
    assert "components" in json_str

    print("✓ JSON serialization works correctly")


# ============================================================================
# Integration Test
# ============================================================================


def test_full_model_integration():
    """Test creating a complete normalized STDN with all model types."""
    # Create multiple normalized components
    components = [
        NormalizedComponent(
            original_id=f"comp_{i:03d}",
            original_name=f"Component {i}",
            source_run=f"run_{i % 2 + 1:03d}",
            source_technology="test_tech",
            normalized_name="Normalized Component",
            normalized_type="test_type",
            normalized_description="Test description",
            normalized_purpose="Test purpose",
            normalized_characteristics=["test"],
            semantic_group_id="group_0001",
            original_type="original_type",
            original_description="Original description",
            original_purpose="Original purpose",
            original_characteristics=["original"],
            confidence=0.85 + (i * 0.01),
            timestamp=datetime.now(),
        )
        for i in range(5)
    ]

    # Create dependency
    dependency = NormalizedDependency(
        original_id="dep_001",
        source_run="run_001",
        source="group_0001",
        target="group_0002",
        dependency_type="requires",
        original_source="Component 0",
        original_target="Component 1",
        confidence=0.9,
        timestamp=datetime.now(),
    )

    # Create semantic group
    group = SemanticGroup(
        group_id="group_0001",
        canonical_name="Normalized Component",
        canonical_type="test_type",
        canonical_description="Test description",
        canonical_purpose="Test purpose",
        canonical_characteristics=["test"],
        member_count=5,
        member_runs=["run_001", "run_002"],
        member_component_ids=[f"comp_{i:03d}" for i in range(5)],
        confidence_avg=0.87,
        confidence_min=0.85,
        confidence_max=0.89,
    )

    # Create consolidated output
    consolidated = ConsolidatedNormalizedSTDN(
        components=components,
        semantic_groups=[group],
        dependencies=[dependency],
        normalization_metadata={
            "total_runs": 2,
            "total_components": 5,
            "semantic_groups": 1,
            "avg_group_size": 5.0,
        },
    )

    assert len(consolidated.components) == 5
    assert len(consolidated.semantic_groups) == 1
    assert len(consolidated.dependencies) == 1
    assert all(comp.semantic_group_id == "group_0001" for comp in consolidated.components)

    print("✓ Full model integration works correctly")


# ============================================================================
# Main Test Runner
# ============================================================================


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Testing STDN Normalization Models")
    print("=" * 80 + "\n")

    print("[1/11] Testing NormalizedComponent creation...")
    test_normalized_component_creation()

    print("\n[2/11] Testing NormalizedComponent with materials...")
    test_normalized_component_with_materials()

    print("\n[3/11] Testing NormalizedComponent validation...")
    test_normalized_component_validation_confidence()

    print("\n[4/11] Testing NormalizedDependency creation...")
    test_normalized_dependency_creation()

    print("\n[5/11] Testing SemanticGroup creation...")
    test_semantic_group_creation()

    print("\n[6/11] Testing SemanticGroup with single member...")
    test_semantic_group_single_member()

    print("\n[7/11] Testing SemanticGroup validation...")
    test_semantic_group_validation_member_count()

    print("\n[8/11] Testing ConsolidatedNormalizedSTDN creation...")
    test_consolidated_normalized_stdn_creation()

    print("\n[9/11] Testing JSON serialization...")
    test_consolidated_normalized_stdn_json_serialization()

    print("\n[10/11] Testing full model integration...")
    test_full_model_integration()

    print("\n" + "=" * 80)
    print("✓ All tests passed!")
    print("=" * 80 + "\n")
