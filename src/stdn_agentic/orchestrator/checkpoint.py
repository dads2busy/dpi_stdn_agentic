"""
Checkpoint management for STDN pipeline

This module provides checkpoint/resume functionality for long-running STDN
generation processes. Critical for government work where:
- Long-running analyses must be resumable
- Audit trails require saved intermediate states
- Processing failures should not lose hours of work
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================================
# Checkpoint Manager
# ============================================================================


class CheckpointManager:
    """
    Manages debate/processing checkpoints for resumable pipelines.

    Provides checkpoint save/load/resume functionality to handle:
    - Long-running batch processes
    - Pipeline failures and restarts
    - Progress tracking and monitoring
    - Audit trails for compliance

    Attributes:
        checkpoint_dir: Directory where checkpoints are saved

    Example:
        >>> manager = CheckpointManager(checkpoint_dir="./checkpoints")
        >>> manager.save_checkpoint(
        ...     config={"model": "gpt-4", "mode": "full"},
        ...     processed_techs=["smartphone", "laptop"],
        ...     results=[...],
        ...     current_index=2,
        ...     total_count=10
        ... )
        >>>
        >>> # Later, resume from checkpoint
        >>> checkpoint = manager.load_checkpoint(config)
        >>> if checkpoint:
        ...     resume_from = checkpoint["current_index"]
    """

    def __init__(self, checkpoint_dir: str = "./checkpoints"):
        """
        Initialize the checkpoint manager.

        Args:
            checkpoint_dir: Directory to save checkpoints (created if doesn't exist)
        """
        self.checkpoint_dir = Path(checkpoint_dir).resolve()
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        config: Dict[str, Any],
        processed_techs: List[str],
        results: List[Dict[str, Any]],
        current_index: int,
        total_count: int,
    ) -> Path:
        """
        Save pipeline checkpoint to disk.

        Args:
            config: Configuration dictionary for this run
            processed_techs: List of already-processed technologies
            results: Accumulated results so far
            current_index: Current processing index
            total_count: Total items to process

        Returns:
            Path to saved checkpoint file

        Example:
            >>> manager = CheckpointManager()
            >>> checkpoint_file = manager.save_checkpoint(
            ...     config={"model": "gpt-4"},
            ...     processed_techs=["smartphone"],
            ...     results=[{"tech": "smartphone", "components": [...]}],
            ...     current_index=1,
            ...     total_count=5
            ... )
        """
        checkpoint_file = self._get_checkpoint_file(config)

        checkpoint_data = {
            "timestamp": datetime.now().isoformat(),
            "config": config,
            "processed_techs": processed_techs,
            "results": results,
            "current_index": current_index,
            "total_count": total_count,
            "progress_pct": (current_index / total_count * 100) if total_count > 0 else 0,
        }

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

        return checkpoint_file

    def load_checkpoint(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint from disk if it exists.

        Args:
            config: Configuration dictionary (used to identify checkpoint)

        Returns:
            Checkpoint data dict if found, None otherwise

        Example:
            >>> manager = CheckpointManager()
            >>> checkpoint = manager.load_checkpoint(config={"model": "gpt-4"})
            >>> if checkpoint:
            ...     print(f"Found checkpoint at {checkpoint['progress_pct']:.1f}%")
            ...     resume_from = checkpoint["current_index"]
        """
        checkpoint_file = self._get_checkpoint_file(config)

        if checkpoint_file.exists():
            with open(checkpoint_file, "r") as f:
                return json.load(f)
        return None

    def delete_checkpoint(self, config: Dict[str, Any]) -> bool:
        """
        Delete checkpoint file.

        Args:
            config: Configuration dictionary (used to identify checkpoint)

        Returns:
            True if checkpoint was deleted, False if it didn't exist

        Example:
            >>> manager = CheckpointManager()
            >>> # After successful completion, clean up
            >>> manager.delete_checkpoint(config={"model": "gpt-4"})
        """
        checkpoint_file = self._get_checkpoint_file(config)
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            return True
        return False

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        List all available checkpoints.

        Returns:
            List of checkpoint metadata dicts

        Example:
            >>> manager = CheckpointManager()
            >>> checkpoints = manager.list_checkpoints()
            >>> for cp in checkpoints:
            ...     print(f"{cp['file']}: {cp['progress_pct']:.1f}% complete")
        """
        checkpoints = []

        for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                with open(checkpoint_file, "r") as f:
                    data = json.load(f)

                checkpoints.append(
                    {
                        "file": checkpoint_file.name,
                        "path": str(checkpoint_file),
                        "timestamp": data.get("timestamp"),
                        "progress_pct": data.get("progress_pct", 0),
                        "current_index": data.get("current_index", 0),
                        "total_count": data.get("total_count", 0),
                    }
                )
            except Exception:
                continue

        # Sort by timestamp (most recent first)
        checkpoints.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return checkpoints

    def _get_checkpoint_file(self, config: Dict[str, Any]) -> Path:
        """
        Get checkpoint file path based on config hash.

        Args:
            config: Configuration dictionary

        Returns:
            Path to checkpoint file (deterministic based on config)
        """
        # Create deterministic hash from config
        config_hash = hash(str(sorted(config.items()))) % 10000
        return self.checkpoint_dir / f"checkpoint_{config_hash}.json"


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "CheckpointManager",
]
