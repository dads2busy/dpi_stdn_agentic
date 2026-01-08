"""
Tests for materials_agent.py to validate refactoring
"""

from unittest.mock import Mock

import pytest
from pydantic_ai import ModelRetry, RunContext

from stdn_agentic.agents.materials_agent import (
    _check_empty_materials,
    _filter_valid_materials,
    _handle_mapping_results,
    _map_materials_to_ontology,
    _validate_materials_input,
    enhanced_material_match,
    validate_materials,
)
from stdn_agentic.models import STDNDependencies

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_context():
    """Create a mock RunContext with dependencies"""
    ctx = Mock(spec=RunContext)
    ctx.retry = 0

    # Mock dependencies with sample ontology
    deps = Mock(spec=STDNDependencies)
    deps.material_ontology_list = [
        "Lithium",
        "Cobalt",
        "Nickel",
        "Copper",
        "Aluminum",
        "Steel",
        "Silicon",
        "Graphite",
        "Plastic",
        "Glass",
        "Rare Earth Elements",
    ]
    ctx.deps = deps

    return ctx


# ============================================================================
# Test Helper Functions
# ============================================================================


def test_validate_materials_input_with_none(mock_context):
    """Test that None input raises ModelRetry on first attempt"""
    with pytest.raises(ModelRetry, match="Materials list is None"):
        _validate_materials_input(None, mock_context)


def test_validate_materials_input_with_non_list(mock_context):
    """Test that non-list input raises ModelRetry"""
    with pytest.raises(ModelRetry, match="Expected a list of materials"):
        _validate_materials_input("not a list", mock_context)


def test_validate_materials_input_with_valid_list(mock_context):
    """Test that valid list input passes validation"""
    # Should not raise any exception
    _validate_materials_input(["Lithium", "Cobalt"], mock_context)


def test_filter_valid_materials():
    """Test filtering of valid materials"""
    materials = [
        "Lithium",
        None,
        "Cobalt",
        "",
        "  ",
        123,  # non-string
        "Copper",
    ]

    result = _filter_valid_materials(materials)

    assert result == ["Lithium", "Cobalt", "Copper"]


def test_filter_valid_materials_empty():
    """Test filtering when all materials are invalid"""
    materials = [None, "", "  ", 123]

    result = _filter_valid_materials(materials)

    assert result == []


def test_check_empty_materials_with_empty_list(mock_context):
    """Test that empty list after filtering raises ModelRetry"""
    with pytest.raises(ModelRetry, match="All provided materials were empty"):
        _check_empty_materials([], mock_context)


def test_check_empty_materials_with_valid_list(mock_context):
    """Test that non-empty list passes check"""
    # Should not raise any exception
    _check_empty_materials(["Lithium"], mock_context)


def test_map_materials_to_ontology(mock_context):
    """Test mapping materials to ontology"""
    materials = ["Lithium", "Cobalt", "Unknown Material"]
    ontology = mock_context.deps.material_ontology_list

    validated, unmapped = _map_materials_to_ontology(materials, ontology)

    assert "Lithium" in validated
    assert "Cobalt" in validated
    assert "Unknown Material" in unmapped


def test_map_materials_to_ontology_with_variants(mock_context):
    """Test mapping with variant names"""
    materials = ["lithium-ion", "aluminium", "li"]
    ontology = mock_context.deps.material_ontology_list

    validated, unmapped = _map_materials_to_ontology(materials, ontology)

    # These should be mapped to standard names
    assert "Lithium" in validated
    assert "Aluminum" in validated


def test_handle_mapping_results_with_validated(mock_context):
    """Test handling when materials are successfully validated"""
    validated = ["Lithium", "Cobalt"]
    unmapped = []
    valid_materials = ["Lithium", "Cobalt"]

    result = _handle_mapping_results(validated, unmapped, valid_materials, mock_context)

    assert result == validated


def test_handle_mapping_results_with_unmapped(mock_context):
    """Test handling when some materials are unmapped"""
    validated = ["Lithium"]
    unmapped = ["Unknown"]
    valid_materials = ["Lithium", "Unknown"]

    result = _handle_mapping_results(validated, unmapped, valid_materials, mock_context)

    assert result == validated


def test_handle_mapping_results_none_validated(mock_context):
    """Test handling when no materials are validated"""
    validated = []
    unmapped = ["Unknown1", "Unknown2"]
    valid_materials = ["Unknown1", "Unknown2"]

    with pytest.raises(ModelRetry, match="Could not map any materials to ontology"):
        _handle_mapping_results(validated, unmapped, valid_materials, mock_context)


# ============================================================================
# Test Main validate_materials Function
# ============================================================================


@pytest.mark.asyncio
async def test_validate_materials_with_valid_materials(mock_context):
    """Test validate_materials with valid material names"""
    materials = ["Lithium", "Cobalt", "Nickel"]

    result = await validate_materials(mock_context, materials)

    assert len(result) == 3
    assert "Lithium" in result
    assert "Cobalt" in result
    assert "Nickel" in result


@pytest.mark.asyncio
async def test_validate_materials_with_none(mock_context):
    """Test validate_materials with None input"""
    with pytest.raises(ModelRetry):
        await validate_materials(mock_context, None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_validate_materials_with_empty_list(mock_context):
    """Test validate_materials with empty list"""
    with pytest.raises(ModelRetry, match="All provided materials were empty"):
        await validate_materials(mock_context, [])


@pytest.mark.asyncio
async def test_validate_materials_with_mixed_valid_invalid(mock_context):
    """Test validate_materials with mix of valid and invalid entries"""
    materials = ["Lithium", None, "", "Cobalt", "  ", 123]

    result = await validate_materials(mock_context, materials)

    assert "Lithium" in result
    assert "Cobalt" in result
    assert len(result) == 2


@pytest.mark.asyncio
async def test_validate_materials_with_variants(mock_context):
    """Test validate_materials with variant material names"""
    materials = ["lithium-ion", "aluminium", "copper wire"]

    result = await validate_materials(mock_context, materials)

    # Should map to standard names
    assert "Lithium" in result
    assert "Aluminum" in result
    assert "Copper" in result


@pytest.mark.asyncio
async def test_validate_materials_with_retry_exhausted(mock_context):
    """Test validate_materials behavior when retries are exhausted"""
    mock_context.retry = 2  # Exhausted retries

    # With exhausted retries, should return empty list instead of raising
    result = await validate_materials(mock_context, None)  # type: ignore[arg-type]

    assert result == []


@pytest.mark.asyncio
async def test_validate_materials_with_all_invalid_exhausted_retry(mock_context):
    """Test validate_materials with all invalid and exhausted retry"""
    mock_context.retry = 2
    materials = [None, "", "  "]

    result = await validate_materials(mock_context, materials)

    assert result == []


# ============================================================================
# Test Enhanced Material Matching
# ============================================================================


def test_enhanced_material_match_exact(mock_context):
    """Test exact material match"""
    ontology = mock_context.deps.material_ontology_list

    result = enhanced_material_match("Lithium", ontology)

    assert result == "Lithium"


def test_enhanced_material_match_case_insensitive(mock_context):
    """Test case-insensitive match"""
    ontology = mock_context.deps.material_ontology_list

    result = enhanced_material_match("lithium", ontology)

    assert result == "Lithium"


def test_enhanced_material_match_variant(mock_context):
    """Test variant mapping"""
    ontology = mock_context.deps.material_ontology_list

    result = enhanced_material_match("lithium-ion", ontology)

    assert result == "Lithium"


def test_enhanced_material_match_chemical_symbol(mock_context):
    """Test chemical symbol matching"""
    ontology = mock_context.deps.material_ontology_list

    result = enhanced_material_match("Li", ontology)

    assert result == "Lithium"


def test_enhanced_material_match_no_match(mock_context):
    """Test when no match is found"""
    ontology = mock_context.deps.material_ontology_list

    result = enhanced_material_match("Unobtainium", ontology)

    # Should return original when no match
    assert result == "Unobtainium"


def test_enhanced_material_match_partial(mock_context):
    """Test partial substring matching"""
    ontology = mock_context.deps.material_ontology_list

    result = enhanced_material_match("silicon wafer", ontology)

    assert result == "Silicon"


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_validate_materials_integration(mock_context):
    """Integration test with realistic input"""
    materials = [
        "Lithium",  # Exact match
        "lithium-ion",  # Variant
        "Li",  # Chemical symbol
        None,  # Invalid
        "",  # Empty
        "Cobalt",  # Exact match
        "Unknown Material",  # Won't match
    ]

    result = await validate_materials(mock_context, materials)

    # Should successfully map the valid ones
    assert "Lithium" in result
    assert "Cobalt" in result
    # Unknown materials should not break the process
    assert len(result) >= 2
