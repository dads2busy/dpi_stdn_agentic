"""
Shared pytest configuration and fixtures for STDN tests

This file contains common test fixtures and configuration that are
automatically available to all test files in the tests/ directory.
"""

from unittest.mock import Mock

import pytest
from pydantic_ai import RunContext

from stdn_agentic.models import STDNDependencies


@pytest.fixture
def sample_ontology():
    """Standard material ontology for testing"""
    return [
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
        "Indium",
        "Gallium",
        "Titanium",
        "Tungsten",
    ]


@pytest.fixture
def sample_components():
    """Standard component list for testing"""
    return [
        "Battery Pack",
        "Display Module",
        "Processor",
        "Memory Chips",
        "Camera Module",
        "Circuit Board",
    ]


@pytest.fixture
def mock_stdn_dependencies(sample_ontology):
    """Mock STDNDependencies for testing"""
    deps = Mock(spec=STDNDependencies)
    deps.material_ontology_list = sample_ontology
    deps.material_ontology_dict = {mat: {"hs_code": "0000"} for mat in sample_ontology}
    deps.component_agent = Mock()
    deps.materials_agent = Mock()
    deps.country_agent = Mock()
    return deps


@pytest.fixture
def mock_run_context(mock_stdn_dependencies):
    """Mock RunContext for agent testing"""
    ctx = Mock(spec=RunContext)
    ctx.retry = 0
    ctx.deps = mock_stdn_dependencies
    return ctx


# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "requires_api: marks tests that require API access")
