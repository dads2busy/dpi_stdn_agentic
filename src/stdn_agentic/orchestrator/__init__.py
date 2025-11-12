"""
Pipeline orchestration and state management for STDN generation
"""

# Import from new modules
# These are now in debate/ and reporting/ but we keep them here for backward compatibility
from ..debate import MultiAgentDebater
from ..reporting import DebateReporter
from .checkpoint import CheckpointManager
from .error_handler import ErrorHandler, ErrorSeverity
from .pipeline import STDNOrchestrator
from .state_manager import PipelineState, StateManager

__all__ = [
    # Main orchestrator
    "STDNOrchestrator",
    # Support classes
    "CheckpointManager",
    "StateManager",
    "PipelineState",
    "ErrorHandler",
    "ErrorSeverity",
    # Backward compatibility (deprecated, use from debate/reporting directly)
    "MultiAgentDebater",
    "DebateReporter",
]
