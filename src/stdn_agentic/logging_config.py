"""
Logging configuration for STDN Agentic.

Provides structured logging with appropriate levels for different contexts:
- DEBUG: Detailed trace info (hidden by default)
- INFO: Key milestones (visible during normal run)
- WARNING: Issues that don't stop execution
- ERROR: Failures

Usage:
    from stdn_agentic.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("Processing technology: %s", tech_name)
    logger.debug("Agent proposal: %s", proposal)
"""

import logging
import sys
from typing import Optional

# Custom log level for pipeline progress (between INFO and WARNING)
PROGRESS = 25
logging.addLevelName(PROGRESS, "PROGRESS")


class STDNFormatter(logging.Formatter):
    """Custom formatter with context-aware formatting."""

    # Format strings for different levels
    FORMATS = {
        logging.DEBUG: "  %(message)s",
        logging.INFO: "%(message)s",
        PROGRESS: "%(message)s",
        logging.WARNING: "⚠ %(message)s",
        logging.ERROR: "✗ %(message)s",
        logging.CRITICAL: "✗✗ %(message)s",
    }

    def format(self, record):
        # Select format based on level
        log_fmt = self.FORMATS.get(record.levelno, "%(message)s")
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class TranscriptHandler(logging.Handler):
    """Handler that captures log messages for transcript generation."""

    def __init__(self):
        super().__init__()
        self.records = []
        self.setLevel(logging.DEBUG)

    def emit(self, record):
        self.records.append(record)

    def get_records(self, level: Optional[int] = None) -> list:
        """Get captured records, optionally filtered by level."""
        if level is None:
            return self.records.copy()
        return [r for r in self.records if r.levelno >= level]

    def clear(self):
        """Clear captured records."""
        self.records.clear()


# Global transcript handler for capturing debate logs
_transcript_handler: Optional[TranscriptHandler] = None


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger configured for STDN.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Console handler - shows INFO and above
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(STDNFormatter())
        logger.addHandler(console_handler)

        # Add transcript handler if active
        if _transcript_handler is not None:
            logger.addHandler(_transcript_handler)

    return logger


def set_verbosity(verbose: bool = False, quiet: bool = False):
    """
    Set global verbosity level.

    Args:
        verbose: If True, show DEBUG messages
        quiet: If True, only show WARNING and above
    """
    root_logger = logging.getLogger("stdn_agentic")

    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            if quiet:
                handler.setLevel(logging.WARNING)
            elif verbose:
                handler.setLevel(logging.DEBUG)
            else:
                handler.setLevel(logging.INFO)


def enable_transcript_capture() -> TranscriptHandler:
    """
    Enable capturing of log messages for transcript generation.

    Returns:
        TranscriptHandler that captures all log messages
    """
    global _transcript_handler
    _transcript_handler = TranscriptHandler()
    return _transcript_handler


def disable_transcript_capture():
    """Disable transcript capture."""
    global _transcript_handler
    _transcript_handler = None


def get_transcript_handler() -> Optional[TranscriptHandler]:
    """Get the current transcript handler if active."""
    return _transcript_handler


# Convenience functions for common log patterns
def log_stage_start(logger: logging.Logger, stage: str, tech: str):
    """Log the start of a pipeline stage."""
    logger.log(PROGRESS, "=" * 80)
    logger.log(PROGRESS, "STAGE: %s - %s", stage, tech)
    logger.log(PROGRESS, "=" * 80)


def log_stage_complete(logger: logging.Logger, stage: str, item_count: int):
    """Log completion of a pipeline stage."""
    logger.info("✓ %s complete: %d items", stage, item_count)


def log_round_start(logger: logging.Logger, round_num: int, max_rounds: int):
    """Log the start of a debate round."""
    logger.info("Round %d/%d:", round_num, max_rounds)


def log_convergence(logger: logging.Logger, score: float, threshold: float):
    """Log convergence score."""
    status = "✓ Threshold reached" if score >= threshold else "→ Continuing"
    logger.info(
        "  Convergence: %.1f%% (threshold: %.1f%%) %s", score * 100, threshold * 100, status
    )


def log_agent_proposal(logger: logging.Logger, agent_id: str, item_count: int):
    """Log an agent proposal."""
    logger.debug("  %s: %d items proposed", agent_id, item_count)


def log_consensus(
    logger: logging.Logger, item_name: str, support: int, total: int, confidence: float
):
    """Log a consensus item."""
    if support == total:
        logger.debug(
            "  ✓ %s: %d/%d agents (%.2f confidence) - CONSENSUS",
            item_name,
            support,
            total,
            confidence,
        )
    elif support > total / 2:
        logger.debug(
            "  ◐ %s: %d/%d agents (%.2f confidence) - MAJORITY",
            item_name,
            support,
            total,
            confidence,
        )
    else:
        logger.debug(
            "  ⚠ %s: %d/%d agents (%.2f confidence) - ISOLATED",
            item_name,
            support,
            total,
            confidence,
        )
