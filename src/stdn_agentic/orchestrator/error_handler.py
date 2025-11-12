"""
Error handling and recovery for STDN pipeline

This module provides centralized error handling, logging, and recovery
strategies for the STDN pipeline orchestration.
"""

import logging
import traceback
from enum import Enum
from typing import Any, Callable, Dict, Optional

# ============================================================================
# Error Types
# ============================================================================


class ErrorSeverity(Enum):
    """Error severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ============================================================================
# Error Handler
# ============================================================================


class ErrorHandler:
    """
    Centralized error handling for STDN pipeline.

    Provides:
    - Error logging and tracking
    - Retry logic for transient failures
    - Error recovery strategies
    - Error aggregation and reporting

    Attributes:
        errors: List of recorded errors
        max_retries: Maximum retry attempts
        logger: Python logger instance

    Example:
        >>> handler = ErrorHandler(max_retries=3)
        >>>
        >>> @handler.with_retry
        >>> async def risky_operation():
        ...     # This will be retried up to 3 times on failure
        ...     await some_api_call()
    """

    def __init__(self, max_retries: int = 3, log_level: str = "INFO"):
        """
        Initialize error handler.

        Args:
            max_retries: Maximum retry attempts for recoverable errors
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.max_retries = max_retries
        self.errors: list[Dict[str, Any]] = []

        # Setup logger
        self.logger = logging.getLogger("stdn_agentic.orchestrator")
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Add console handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def record_error(
        self,
        error: Exception,
        context: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Record an error with context.

        Args:
            error: Exception that occurred
            context: Description of where/when error occurred
            severity: Error severity level
            metadata: Additional error metadata

        Example:
            >>> handler = ErrorHandler()
            >>> try:
            ...     risky_operation()
            ... except Exception as e:
            ...     handler.record_error(
            ...         e,
            ...         context="Processing technology: smartphone",
            ...         severity=ErrorSeverity.ERROR,
            ...         metadata={"tech": "smartphone", "stage": "component_extraction"}
            ...     )
        """
        error_record = {
            "error": str(error),
            "error_type": type(error).__name__,
            "context": context,
            "severity": severity.value,
            "traceback": traceback.format_exc(),
            "metadata": metadata or {},
        }

        self.errors.append(error_record)

        # Log based on severity
        log_message = f"{context}: {error}"

        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, exc_info=True)
        elif severity == ErrorSeverity.ERROR:
            self.logger.error(log_message, exc_info=True)
        elif severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    async def with_retry(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Function positional arguments
            max_retries: Override default max retries
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail

        Example:
            >>> handler = ErrorHandler(max_retries=3)
            >>> result = await handler.with_retry(
            ...     some_async_function,
            ...     arg1, arg2,
            ...     max_retries=5
            ... )
        """
        retries = max_retries if max_retries is not None else self.max_retries
        last_error = None

        for attempt in range(retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt < retries:
                    self.logger.warning(
                        f"Attempt {attempt + 1}/{retries + 1} failed: {e}. Retrying..."
                    )
                else:
                    self.record_error(
                        e,
                        context=f"Failed after {retries + 1} attempts",
                        severity=ErrorSeverity.ERROR,
                    )

        # All retries failed
        raise last_error

    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get summary of all recorded errors.

        Returns:
            Dict with error counts by severity and type

        Example:
            >>> handler = ErrorHandler()
            >>> # ... errors occur ...
            >>> summary = handler.get_error_summary()
            >>> print(f"Total errors: {summary['total_errors']}")
        """
        severity_counts = {}
        type_counts = {}

        for error in self.errors:
            severity = error["severity"]
            error_type = error["error_type"]

            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            type_counts[error_type] = type_counts.get(error_type, 0) + 1

        return {
            "total_errors": len(self.errors),
            "by_severity": severity_counts,
            "by_type": type_counts,
            "errors": self.errors,
        }

    def clear_errors(self):
        """Clear all recorded errors"""
        self.errors = []


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "ErrorHandler",
    "ErrorSeverity",
]
