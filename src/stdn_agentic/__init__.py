"""
STDN Agentic - Supply Technology Dependency Network generation using Pydantic AI
"""

# Load environment variables FIRST, before anything else
from dotenv import load_dotenv
load_dotenv()

__version__ = "0.1.0"

# Expose main components for easier imports
from .models import STDNDependencies, ConfigModel
from .agents import ComponentList, ComponentMaterials  # Changed: import from agents
from .orchestrator import STDNOrchestrator

__all__ = [
    "ComponentList",
    "ComponentMaterials",
    "STDNDependencies",
    "ConfigModel",
    "STDNOrchestrator",
]
