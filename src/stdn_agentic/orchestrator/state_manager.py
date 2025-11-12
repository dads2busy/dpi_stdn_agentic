"""
State management for STDN pipeline workflows

This module provides state tracking and transition management for the STDN
pipeline orchestration. It helps coordinate pipeline stages and maintain
consistent state across long-running processes.
"""

from enum import Enum
from typing import Any, Dict, Optional

# ============================================================================
# Pipeline State Definitions
# ============================================================================


class PipelineState(Enum):
    """Pipeline execution states"""

    INITIALIZED = "initialized"
    EXTRACTING_COMPONENTS = "extracting_components"
    RUNNING_DEBATE = "running_debate"
    EXTRACTING_MATERIALS = "extracting_materials"
    ENRICHING_COUNTRY_DATA = "enriching_country_data"
    AGGREGATING_RESULTS = "aggregating_results"
    WRITING_OUTPUT = "writing_output"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


# ============================================================================
# State Manager
# ============================================================================


class StateManager:
    """
    Manages pipeline state transitions and tracking.

    Provides:
    - State transition validation
    - State history tracking
    - Progress monitoring
    - Error state handling

    Attributes:
        current_state: Current pipeline state
        state_history: List of previous states
        metadata: Additional state metadata

    Example:
        >>> manager = StateManager()
        >>> manager.transition_to(PipelineState.EXTRACTING_COMPONENTS)
        >>> print(manager.current_state)
        PipelineState.EXTRACTING_COMPONENTS
        >>> print(manager.get_progress_pct())
        25.0
    """

    def __init__(self):
        """Initialize state manager"""
        self.current_state: PipelineState = PipelineState.INITIALIZED
        self.state_history: list[PipelineState] = [PipelineState.INITIALIZED]
        self.metadata: Dict[str, Any] = {}

    def transition_to(self, new_state: PipelineState, metadata: Optional[Dict[str, Any]] = None):
        """
        Transition to new state.

        Args:
            new_state: Target state
            metadata: Optional metadata about the transition

        Example:
            >>> manager = StateManager()
            >>> manager.transition_to(
            ...     PipelineState.RUNNING_DEBATE,
            ...     metadata={"round": 1, "agents": 3}
            ... )
        """
        # Validate transition (add custom logic here if needed)
        if not self._is_valid_transition(self.current_state, new_state):
            raise ValueError(f"Invalid state transition: {self.current_state} -> {new_state}")

        # Record state change
        self.state_history.append(new_state)
        self.current_state = new_state

        # Update metadata
        if metadata:
            self.metadata.update(metadata)

    def _is_valid_transition(self, from_state: PipelineState, to_state: PipelineState) -> bool:
        """
        Validate state transition.

        Args:
            from_state: Current state
            to_state: Target state

        Returns:
            True if transition is valid
        """
        # Allow any transition to FAILED or PAUSED
        if to_state in [PipelineState.FAILED, PipelineState.PAUSED]:
            return True

        # Allow resuming from PAUSED to any state
        if from_state == PipelineState.PAUSED:
            return True

        # Define valid transitions
        valid_transitions = {
            PipelineState.INITIALIZED: [PipelineState.EXTRACTING_COMPONENTS],
            PipelineState.EXTRACTING_COMPONENTS: [
                PipelineState.RUNNING_DEBATE,
                PipelineState.EXTRACTING_MATERIALS,
            ],
            PipelineState.RUNNING_DEBATE: [PipelineState.EXTRACTING_MATERIALS],
            PipelineState.EXTRACTING_MATERIALS: [
                PipelineState.ENRICHING_COUNTRY_DATA,
                PipelineState.AGGREGATING_RESULTS,
            ],
            PipelineState.ENRICHING_COUNTRY_DATA: [PipelineState.AGGREGATING_RESULTS],
            PipelineState.AGGREGATING_RESULTS: [PipelineState.WRITING_OUTPUT],
            PipelineState.WRITING_OUTPUT: [PipelineState.COMPLETED],
        }

        return to_state in valid_transitions.get(from_state, [])

    def get_progress_pct(self) -> float:
        """
        Calculate progress percentage based on current state.

        Returns:
            Progress percentage (0-100)
        """
        # Map states to progress percentages
        progress_map = {
            PipelineState.INITIALIZED: 0.0,
            PipelineState.EXTRACTING_COMPONENTS: 20.0,
            PipelineState.RUNNING_DEBATE: 30.0,
            PipelineState.EXTRACTING_MATERIALS: 50.0,
            PipelineState.ENRICHING_COUNTRY_DATA: 70.0,
            PipelineState.AGGREGATING_RESULTS: 85.0,
            PipelineState.WRITING_OUTPUT: 95.0,
            PipelineState.COMPLETED: 100.0,
            PipelineState.FAILED: 0.0,
            PipelineState.PAUSED: 0.0,
        }

        return progress_map.get(self.current_state, 0.0)

    def is_completed(self) -> bool:
        """Check if pipeline is completed"""
        return self.current_state == PipelineState.COMPLETED

    def is_failed(self) -> bool:
        """Check if pipeline has failed"""
        return self.current_state == PipelineState.FAILED

    def reset(self):
        """Reset state manager to initial state"""
        self.current_state = PipelineState.INITIALIZED
        self.state_history = [PipelineState.INITIALIZED]
        self.metadata = {}


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "StateManager",
    "PipelineState",
]
