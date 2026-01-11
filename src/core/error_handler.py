"""
Global Exception Handler

Provides centralized exception handling, error recovery, and error reporting
for the quantitative trading platform.

V3.1.0: Initial release - global exception handling system

Features:
- Decorator-based exception handling for functions
- Context manager for scoped exception handling
- Automatic error logging with structured context
- Error recovery mechanisms
- Error statistics and reporting

Usage:
    >>> from src.core.error_handler import handle_errors, ErrorHandler
    >>> 
    >>> # Decorator usage
    >>> @handle_errors(default_return=None, reraise=False)
    ... def risky_function():
    ...     raise ValueError("Something went wrong")
    >>> 
    >>> # Context manager usage
    >>> with ErrorHandler(operation="data_load"):
    ...     load_data()
    >>> 
    >>> # Get error statistics
    >>> stats = ErrorHandler.get_statistics()
"""
from __future__ import annotations

import functools
import sys
import threading
import traceback
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from .exceptions import (
    QuantBaseError,
    DataError,
    StrategyError,
    OrderError,
    GatewayError,
    RiskError,
    ConfigurationError,
    BacktestError,
    classify_exception,
    wrap_exception,
)
from .logger import get_logger

logger = get_logger("error_handler")

# Type variable for generic function return type
T = TypeVar("T")


# ---------------------------------------------------------------------------
# Error Statistics
# ---------------------------------------------------------------------------

@dataclass
class ErrorRecord:
    """Record of a single error occurrence."""
    error_code: str
    error_type: str
    message: str
    timestamp: datetime
    context: Dict[str, Any]
    traceback: str
    operation: Optional[str] = None
    recovered: bool = False


class ErrorStatistics:
    """
    Thread-safe error statistics collector.
    
    Tracks error occurrences, categorizes them, and provides reporting.
    """
    
    def __init__(self, max_records: int = 1000):
        self._lock = threading.Lock()
        self._records: List[ErrorRecord] = []
        self._counts: Dict[str, int] = defaultdict(int)
        self._max_records = max_records
    
    def record(self, error: ErrorRecord) -> None:
        """Record an error occurrence."""
        with self._lock:
            self._records.append(error)
            self._counts[error.error_code] += 1
            self._counts[f"category:{classify_exception(Exception(error.message))}"] += 1
            
            # Trim old records if needed
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
    
    def get_count(self, error_code: Optional[str] = None) -> int:
        """Get error count, optionally filtered by error code."""
        with self._lock:
            if error_code:
                return self._counts.get(error_code, 0)
            return sum(v for k, v in self._counts.items() if not k.startswith("category:"))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error statistics summary."""
        with self._lock:
            return {
                "total_errors": self.get_count(),
                "by_code": {k: v for k, v in self._counts.items() if not k.startswith("category:")},
                "by_category": {k.split(":")[1]: v for k, v in self._counts.items() if k.startswith("category:")},
                "recent_errors": [
                    {
                        "error_code": r.error_code,
                        "message": r.message[:100],
                        "timestamp": r.timestamp.isoformat(),
                        "recovered": r.recovered,
                    }
                    for r in self._records[-10:]
                ],
            }
    
    def clear(self) -> None:
        """Clear all statistics."""
        with self._lock:
            self._records.clear()
            self._counts.clear()
    
    def get_recent(self, count: int = 10) -> List[ErrorRecord]:
        """Get most recent error records."""
        with self._lock:
            return self._records[-count:]


# Global statistics instance
_global_stats = ErrorStatistics()


# ---------------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------------

class ErrorHandler:
    """
    Context manager for scoped exception handling.
    
    Features:
    - Automatic error logging
    - Error wrapping in QuantBaseError
    - Optional error suppression
    - Recovery callback support
    - Statistics tracking
    
    Usage:
        >>> with ErrorHandler(operation="load_data", reraise=True):
        ...     data = load_data()
        
        >>> # With recovery callback
        >>> def recover_from_data_error():
        ...     return get_cached_data()
        >>> 
        >>> with ErrorHandler(operation="load_data", recovery={DataError: recover_from_data_error}):
        ...     data = load_data()
    """
    
    def __init__(
        self,
        operation: str = "unknown",
        reraise: bool = True,
        suppress: bool = False,
        log_level: str = "error",
        context: Optional[Dict[str, Any]] = None,
        recovery: Optional[Dict[Type[Exception], Callable]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Initialize error handler.
        
        Args:
            operation: Name of the operation being performed
            reraise: Whether to re-raise exceptions after handling
            suppress: Whether to suppress all exceptions
            log_level: Log level for error messages
            context: Additional context to include in error logs
            recovery: Dict mapping exception types to recovery callbacks
            on_error: Callback to invoke on any error
        """
        self.operation = operation
        self.reraise = reraise
        self.suppress = suppress
        self.log_level = log_level
        self.context = context or {}
        self.recovery = recovery or {}
        self.on_error = on_error
        self.error: Optional[Exception] = None
        self.recovered = False
    
    def __enter__(self) -> "ErrorHandler":
        return self
    
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        if exc_val is None:
            return False
        
        # Store the error
        self.error = exc_val
        
        # Get traceback string
        tb_str = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        
        # Create error record
        error_code = exc_val.error_code if isinstance(exc_val, QuantBaseError) else "UNKNOWN"
        record = ErrorRecord(
            error_code=error_code,
            error_type=exc_type.__name__ if exc_type else "Unknown",
            message=str(exc_val),
            timestamp=datetime.now(),
            context={**self.context, "operation": self.operation},
            traceback=tb_str,
            operation=self.operation,
        )
        
        # Try recovery
        for error_type, recovery_func in self.recovery.items():
            if isinstance(exc_val, error_type):
                try:
                    recovery_func()
                    self.recovered = True
                    record.recovered = True
                    logger.info(
                        f"Recovered from error in {self.operation}",
                        error_type=exc_type.__name__,
                        recovery="success",
                    )
                    break
                except Exception as recovery_error:
                    logger.warning(
                        f"Recovery failed in {self.operation}",
                        original_error=str(exc_val),
                        recovery_error=str(recovery_error),
                    )
        
        # Record statistics
        _global_stats.record(record)
        
        # Log the error
        log_func = getattr(logger, self.log_level, logger.error)
        log_func(
            f"Error in {self.operation}: {exc_val}",
            error_code=error_code,
            error_type=exc_type.__name__ if exc_type else "Unknown",
            **self.context,
        )
        
        # Call error callback
        if self.on_error:
            try:
                self.on_error(exc_val)
            except Exception as callback_error:
                logger.warning(f"Error callback failed: {callback_error}")
        
        # Determine whether to suppress
        if self.suppress or self.recovered:
            return True
        
        if not self.reraise:
            return True
        
        # Re-raise wrapped exception if not already a QuantBaseError
        if not isinstance(exc_val, QuantBaseError):
            wrapped = wrap_exception(exc_val)
            raise wrapped from exc_val
        
        return False
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get global error statistics."""
        return _global_stats.get_summary()
    
    @staticmethod
    def clear_statistics() -> None:
        """Clear global error statistics."""
        _global_stats.clear()
    
    @staticmethod
    def get_recent_errors(count: int = 10) -> List[ErrorRecord]:
        """Get recent error records."""
        return _global_stats.get_recent(count)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def handle_errors(
    default_return: T = None,
    reraise: bool = False,
    suppress_types: Optional[List[Type[Exception]]] = None,
    wrap_exceptions: bool = True,
    operation: Optional[str] = None,
    log_level: str = "error",
    recovery: Optional[Dict[Type[Exception], Callable]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for automatic exception handling.
    
    Args:
        default_return: Value to return when exception is caught (if not reraising)
        reraise: Whether to re-raise exceptions after handling
        suppress_types: List of exception types to suppress
        wrap_exceptions: Whether to wrap non-QuantBaseError exceptions
        operation: Operation name for logging (defaults to function name)
        log_level: Log level for error messages
        recovery: Dict mapping exception types to recovery callbacks
    
    Returns:
        Decorated function
    
    Usage:
        >>> @handle_errors(default_return=[], reraise=False)
        ... def get_data():
        ...     raise DataError("Failed to fetch")
        >>> 
        >>> result = get_data()  # Returns []
        
        >>> @handle_errors(reraise=True, suppress_types=[DataNotFoundError])
        ... def get_data_or_none():
        ...     raise DataNotFoundError("600519.SH")
        >>> 
        >>> result = get_data_or_none()  # Returns None, doesn't raise
    """
    suppress_types = suppress_types or []
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        op_name = operation or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            with ErrorHandler(
                operation=op_name,
                reraise=reraise,
                suppress=False,
                log_level=log_level,
                recovery=recovery,
            ) as handler:
                try:
                    return func(*args, **kwargs)
                except tuple(suppress_types) as e:
                    logger.debug(f"Suppressed {type(e).__name__} in {op_name}")
                    return default_return
                except Exception as e:
                    if not reraise:
                        return default_return
                    
                    # Wrap if needed
                    if wrap_exceptions and not isinstance(e, QuantBaseError):
                        raise wrap_exception(e) from e
                    raise
        
        return wrapper
    
    return decorator


# ---------------------------------------------------------------------------
# Async Support
# ---------------------------------------------------------------------------

def handle_errors_async(
    default_return: T = None,
    reraise: bool = False,
    suppress_types: Optional[List[Type[Exception]]] = None,
    wrap_exceptions: bool = True,
    operation: Optional[str] = None,
    log_level: str = "error",
) -> Callable:
    """
    Async version of handle_errors decorator.
    
    Usage:
        >>> @handle_errors_async(default_return=[])
        ... async def fetch_data():
        ...     raise DataError("Failed")
    """
    suppress_types = suppress_types or []
    
    def decorator(func: Callable) -> Callable:
        import asyncio
        
        op_name = operation or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            try:
                return await func(*args, **kwargs)
            except tuple(suppress_types):
                return default_return
            except Exception as e:
                # Record error
                error_code = e.error_code if isinstance(e, QuantBaseError) else "UNKNOWN"
                record = ErrorRecord(
                    error_code=error_code,
                    error_type=type(e).__name__,
                    message=str(e),
                    timestamp=datetime.now(),
                    context={"operation": op_name},
                    traceback=traceback.format_exc(),
                    operation=op_name,
                )
                _global_stats.record(record)
                
                # Log
                log_func = getattr(logger, log_level, logger.error)
                log_func(f"Async error in {op_name}: {e}", error_code=error_code)
                
                if not reraise:
                    return default_return
                
                if wrap_exceptions and not isinstance(e, QuantBaseError):
                    raise wrap_exception(e) from e
                raise
        
        return wrapper
    
    return decorator


# ---------------------------------------------------------------------------
# Error Recovery Utilities
# ---------------------------------------------------------------------------

class RetryPolicy:
    """
    Retry policy for recoverable errors.
    
    Usage:
        >>> policy = RetryPolicy(max_retries=3, delay=1.0, backoff=2.0)
        >>> 
        >>> @policy.wrap
        ... def flaky_operation():
        ...     # May fail sometimes
        ...     pass
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        max_delay: float = 30.0,
        retry_on: Optional[List[Type[Exception]]] = None,
    ):
        """
        Initialize retry policy.
        
        Args:
            max_retries: Maximum number of retry attempts
            delay: Initial delay between retries (seconds)
            backoff: Backoff multiplier for delay
            max_delay: Maximum delay between retries
            retry_on: List of exception types to retry on (default: all)
        """
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
        self.max_delay = max_delay
        self.retry_on = retry_on
    
    def should_retry(self, exc: Exception, attempt: int) -> bool:
        """Check if operation should be retried."""
        if attempt >= self.max_retries:
            return False
        
        if self.retry_on is None:
            return True
        
        return isinstance(exc, tuple(self.retry_on))
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        delay = self.delay * (self.backoff ** attempt)
        return min(delay, self.max_delay)
    
    def wrap(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to apply retry policy to a function."""
        import time
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Optional[Exception] = None
            
            for attempt in range(self.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    if not self.should_retry(e, attempt):
                        raise
                    
                    delay = self.get_delay(attempt)
                    logger.warning(
                        f"Retrying {func.__name__} after error",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)
            
            # Should not reach here, but just in case
            if last_error:
                raise last_error
            return None
        
        return wrapper


# ---------------------------------------------------------------------------
# Global Exception Hook
# ---------------------------------------------------------------------------

_original_excepthook = sys.excepthook


def _quant_excepthook(exc_type, exc_val, exc_tb):
    """Global exception hook for unhandled exceptions."""
    # Record the error
    tb_str = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
    error_code = exc_val.error_code if isinstance(exc_val, QuantBaseError) else "UNHANDLED"
    
    record = ErrorRecord(
        error_code=error_code,
        error_type=exc_type.__name__,
        message=str(exc_val),
        timestamp=datetime.now(),
        context={"unhandled": True},
        traceback=tb_str,
        operation="global",
    )
    _global_stats.record(record)
    
    # Log critical error
    logger.critical(
        f"Unhandled exception: {exc_val}",
        error_code=error_code,
        error_type=exc_type.__name__,
    )
    
    # Call original hook
    _original_excepthook(exc_type, exc_val, exc_tb)


def install_global_handler() -> None:
    """Install global exception handler."""
    sys.excepthook = _quant_excepthook
    logger.info("Global exception handler installed")


def uninstall_global_handler() -> None:
    """Uninstall global exception handler."""
    sys.excepthook = _original_excepthook
    logger.info("Global exception handler uninstalled")


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def safe_call(
    func: Callable[..., T],
    *args: Any,
    default: T = None,
    **kwargs: Any,
) -> T:
    """
    Safely call a function, returning default on error.
    
    Usage:
        >>> result = safe_call(risky_function, arg1, arg2, default=[])
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.debug(f"safe_call caught {type(e).__name__}: {e}")
        return default


@contextmanager
def suppress_errors(*exception_types: Type[Exception]):
    """
    Context manager to suppress specific exception types.
    
    Usage:
        >>> with suppress_errors(DataNotFoundError, ValueError):
        ...     data = load_data()  # Won't raise these types
    """
    try:
        yield
    except exception_types:
        pass
