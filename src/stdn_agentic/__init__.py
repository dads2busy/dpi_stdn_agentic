"""
STDN Agentic - Supply Technology Dependency Network generation using Pydantic AI

This package provides tools for analyzing technology dependencies and materials:
- Component extraction from technologies
- Material identification for components
- Multi-agent debate system for improved consensus
- Country production data aggregation
- Supply chain risk analysis
"""

from dotenv import load_dotenv

# Load environment variables FIRST, before importing agents
load_dotenv()

# Core models
# Agent imports (all re-exported for backward compatibility)
from .agents import (
    AgentFactory,
    ComponentList,
    ComponentMaterials,
    ComponentMaterialsList,
    CountryList,
    CountryPercentage,
    get_component_agent,
    get_country_data_agent,
    get_materials_agent,
)
from .models import ConfigModel, STDNDependencies

# Orchestration imports (from orchestrator_legacy.py after renaming)
from .orchestrator import (
    CheckpointManager,
    DebateReporter,
    MultiAgentDebater,
    STDNOrchestrator,
)

__version__ = "0.1.0"

__all__ = [
    # Version info
    "__version__",
    # Models
    "STDNDependencies",
    "ConfigModel",
    # Agents - Component extraction
    "get_component_agent",
    "ComponentList",
    # Agents - Materials extraction
    "get_materials_agent",
    "ComponentMaterials",
    "ComponentMaterialsList",
    # Agents - Country data
    "get_country_data_agent",
    "CountryPercentage",
    "CountryList",
    # Agent factory
    "AgentFactory",
    # Orchestration
    "STDNOrchestrator",
    "CheckpointManager",
    "MultiAgentDebater",
    "DebateReporter",
]
