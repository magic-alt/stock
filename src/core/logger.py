"""
Logger Module

Configures structured logging for the quantitative trading platform.
Replaces print statements with proper observability infrastructure.

Features:
- Structured logging with context (symbol, price, order_id, etc.)
- JSON format for production (ELK/Splunk integration)
- Colored console output for development
- Standard library logging integration

Usage:
    >>> from src.core.logger import configure_logging, get_logger
    >>> 
    >>> # Configure at startup
    >>> configure_logging(level="DEBUG", json_format=False)
    >>> 
    >>> # Get logger
    >>> logger = get_logger("strategy")
    >>> logger.info("Signal generated", symbol="600519.SH", price=1850.0, action="buy")
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

# Check if structlog is available
try:
    import structlog
    from structlog.stdlib import BoundLogger
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    structlog = None
    BoundLogger = None


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure structured logging for the platform.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output JSON (for production/ELK), else colored text
        log_file: Optional file path for logging output
    
    Example:
        >>> configure_logging(level="DEBUG")  # Development
        >>> configure_logging(level="INFO", json_format=True)  # Production
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    if STRUCTLOG_AVAILABLE:
        _configure_structlog(log_level, json_format, log_file)
    else:
        _configure_stdlib(log_level, log_file)


def _configure_structlog(log_level: int, json_format: bool, log_file: Optional[str]) -> None:
    """Configure structlog with processors."""
    
    # Shared processors for both JSON and console output
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_format:
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        # Colored console output for development
        processors = shared_processors + [
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True, pad_event=30),
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True, pad_event=30),
            foreign_pre_chain=shared_processors,
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def _configure_stdlib(log_level: int, log_file: Optional[str]) -> None:
    """Fallback configuration using standard library logging."""
    
    # Format string
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt))
    handlers.append(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt, datefmt))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )


def get_logger(name: str = "quant"):
    """
    Get a logger instance.
    
    Args:
        name: Logger name (e.g., "strategy", "gateway", "engine")
    
    Returns:
        Logger instance (structlog.BoundLogger or logging.Logger)
    
    Example:
        >>> logger = get_logger("strategy")
        >>> logger.info("Order submitted", order_id="O001", symbol="600519.SH")
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name)


# Module-level logger for convenience
logger = get_logger("quant")


# Context manager for adding temporary context
class LogContext:
    """
    Context manager for adding temporary logging context.
    
    Usage:
        >>> with LogContext(symbol="600519.SH", strategy="EMA"):
        ...     logger.info("Processing bar")  # Includes symbol and strategy
    """
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self._token = None
    
    def __enter__(self):
        if STRUCTLOG_AVAILABLE:
            self._token = structlog.contextvars.bind_contextvars(**self.context)
        return self
    
    def __exit__(self, *args):
        if STRUCTLOG_AVAILABLE and self._token:
            structlog.contextvars.unbind_contextvars(*self.context.keys())


# Convenience functions for common log patterns
def log_order(logger, action: str, **kwargs):
    """Log order-related events with standard fields."""
    logger.info(f"Order {action}", event_type="order", **kwargs)


def log_trade(logger, **kwargs):
    """Log trade execution with standard fields."""
    logger.info("Trade executed", event_type="trade", **kwargs)


def log_signal(logger, signal: str, **kwargs):
    """Log trading signal with standard fields."""
    logger.info(f"Signal: {signal}", event_type="signal", **kwargs)


def log_error(logger, error: str, **kwargs):
    """Log error with standard fields."""
    logger.error(error, event_type="error", **kwargs)
