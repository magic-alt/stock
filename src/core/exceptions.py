"""
Unified Exception Definitions

Centralized exception hierarchy for the quantitative trading platform.
All custom exceptions are defined here for consistency and maintainability.

V3.1.0: Initial release - unified exception handling system

Exception Hierarchy:
    QuantBaseError (base)
    ├── ConfigurationError - Configuration and setup issues
    ├── DataError - Data-related errors
    │   ├── DataProviderError - Data provider failures
    │   ├── DataValidationError - Data validation failures
    │   └── DataNotFoundError - Missing data
    ├── StrategyError - Strategy-related errors
    │   ├── StrategyNotFoundError - Strategy not registered
    │   ├── StrategyInitializationError - Strategy init failures
    │   └── StrategyExecutionError - Runtime execution failures
    ├── OrderError - Order-related errors
    │   ├── OrderValidationError - Order validation failures
    │   ├── OrderRejectedError - Order rejected by gateway
    │   └── InsufficientFundsError - Not enough funds/margin
    ├── GatewayError - Gateway-related errors
    │   ├── GatewayConnectionError - Connection failures
    │   ├── GatewayTimeoutError - Timeout errors
    │   └── GatewayAuthError - Authentication failures
    ├── RiskError - Risk management errors
    │   ├── RiskLimitExceeded - Risk limit exceeded
    │   └── PositionLimitExceeded - Position limit exceeded
    └── BacktestError - Backtest-specific errors

Usage:
    >>> from src.core.exceptions import DataNotFoundError, StrategyError
    >>> 
    >>> # Raise specific exceptions
    >>> raise DataNotFoundError("600519.SH", "2024-01-01", "2024-12-31")
    >>> 
    >>> # Catch by category
    >>> try:
    ...     run_backtest()
    ... except DataError as e:
    ...     logger.error(f"Data error: {e}")
    ... except StrategyError as e:
    ...     logger.error(f"Strategy error: {e}")
"""
from __future__ import annotations

from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Base Exception
# ---------------------------------------------------------------------------

class QuantBaseError(Exception):
    """
    Base exception for all quantitative trading platform errors.
    
    Provides:
    - Error code for programmatic handling
    - Timestamp for logging/debugging
    - Context dict for additional information
    - User-friendly message formatting
    """
    
    error_code: str = "QUANT_ERROR"
    
    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        self.message = message
        self.error_code = error_code or self.__class__.error_code
        self.context = context or {}
        self.cause = cause
        self.timestamp = datetime.now()
        
        # Build full message
        full_message = f"[{self.error_code}] {message}"
        if context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in context.items())
            full_message += f" ({ctx_str})"
        
        super().__init__(full_message)
        
        # Chain exception if cause provided
        if cause:
            self.__cause__ = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "type": self.__class__.__name__,
        }


# ---------------------------------------------------------------------------
# Configuration Errors
# ---------------------------------------------------------------------------

class ConfigurationError(QuantBaseError):
    """Configuration or setup related errors."""
    error_code = "CONFIG_ERROR"


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""
    error_code = "CONFIG_MISSING"
    
    def __init__(self, config_key: str, description: str = ""):
        message = f"Missing required configuration: {config_key}"
        if description:
            message += f" - {description}"
        super().__init__(message, context={"config_key": config_key})


class InvalidConfigError(ConfigurationError):
    """Configuration value is invalid."""
    error_code = "CONFIG_INVALID"
    
    def __init__(self, config_key: str, value: Any, expected: str):
        message = f"Invalid configuration for '{config_key}': got {value!r}, expected {expected}"
        super().__init__(
            message,
            context={"config_key": config_key, "value": str(value), "expected": expected}
        )


# ---------------------------------------------------------------------------
# Data Errors
# ---------------------------------------------------------------------------

class DataError(QuantBaseError):
    """Base class for data-related errors."""
    error_code = "DATA_ERROR"


class DataProviderError(DataError):
    """Data provider failed to fetch data."""
    error_code = "DATA_PROVIDER_ERROR"
    
    def __init__(self, provider: str, message: str, **context):
        super().__init__(
            f"[{provider}] {message}",
            context={"provider": provider, **context}
        )


class DataValidationError(DataError):
    """Data validation failed."""
    error_code = "DATA_VALIDATION_ERROR"
    
    def __init__(self, message: str, field: Optional[str] = None, **context):
        ctx = {"field": field, **context} if field else context
        super().__init__(message, context=ctx)


class DataNotFoundError(DataError):
    """Requested data not found."""
    error_code = "DATA_NOT_FOUND"
    
    def __init__(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **context
    ):
        message = f"No data found for symbol '{symbol}'"
        if start_date and end_date:
            message += f" from {start_date} to {end_date}"
        super().__init__(
            message,
            context={"symbol": symbol, "start_date": start_date, "end_date": end_date, **context}
        )


class InsufficientDataError(DataError):
    """Not enough data points for analysis."""
    error_code = "DATA_INSUFFICIENT"
    
    def __init__(self, symbol: str, required: int, available: int):
        message = f"Insufficient data for '{symbol}': need {required} bars, got {available}"
        super().__init__(
            message,
            context={"symbol": symbol, "required": required, "available": available}
        )


# ---------------------------------------------------------------------------
# Strategy Errors
# ---------------------------------------------------------------------------

class StrategyError(QuantBaseError):
    """Base class for strategy-related errors."""
    error_code = "STRATEGY_ERROR"


class StrategyNotFoundError(StrategyError):
    """Strategy not found in registry."""
    error_code = "STRATEGY_NOT_FOUND"
    
    def __init__(self, strategy_name: str, available: Optional[List[str]] = None):
        message = f"Strategy '{strategy_name}' not found in registry"
        ctx = {"strategy_name": strategy_name}
        if available:
            ctx["available_strategies"] = ", ".join(available[:10])
            message += f". Available: {ctx['available_strategies']}"
        super().__init__(message, context=ctx)


class StrategyInitializationError(StrategyError):
    """Strategy failed to initialize."""
    error_code = "STRATEGY_INIT_ERROR"
    
    def __init__(self, strategy_name: str, reason: str, **context):
        message = f"Failed to initialize strategy '{strategy_name}': {reason}"
        super().__init__(message, context={"strategy_name": strategy_name, **context})


class StrategyExecutionError(StrategyError):
    """Strategy execution failed at runtime."""
    error_code = "STRATEGY_EXEC_ERROR"
    
    def __init__(self, strategy_name: str, bar_index: int, reason: str, **context):
        message = f"Strategy '{strategy_name}' failed at bar {bar_index}: {reason}"
        super().__init__(
            message,
            context={"strategy_name": strategy_name, "bar_index": bar_index, **context}
        )


class StrategyValidationError(StrategyError):
    """Strategy parameter validation failed."""
    error_code = "STRATEGY_VALIDATION_ERROR"
    
    def __init__(self, strategy_name: str, param: str, value: Any, reason: str):
        message = f"Invalid parameter '{param}={value}' for strategy '{strategy_name}': {reason}"
        super().__init__(
            message,
            context={"strategy_name": strategy_name, "param": param, "value": str(value)}
        )


# ---------------------------------------------------------------------------
# Order Errors
# ---------------------------------------------------------------------------

class OrderError(QuantBaseError):
    """Base class for order-related errors."""
    error_code = "ORDER_ERROR"


class OrderValidationError(OrderError):
    """Order validation failed."""
    error_code = "ORDER_VALIDATION_ERROR"
    
    def __init__(self, order_id: Optional[str], reason: str, **context):
        message = f"Order validation failed: {reason}"
        if order_id:
            message = f"Order {order_id} validation failed: {reason}"
        super().__init__(message, context={"order_id": order_id, **context})


class OrderRejectedError(OrderError):
    """Order rejected by gateway or exchange."""
    error_code = "ORDER_REJECTED"
    
    def __init__(self, order_id: str, reason: str, **context):
        message = f"Order {order_id} rejected: {reason}"
        super().__init__(message, context={"order_id": order_id, **context})


class InsufficientFundsError(OrderError):
    """Insufficient funds or margin for order."""
    error_code = "INSUFFICIENT_FUNDS"
    
    def __init__(self, required: float, available: float, symbol: Optional[str] = None):
        message = f"Insufficient funds: required {required:.2f}, available {available:.2f}"
        if symbol:
            message = f"Insufficient funds for {symbol}: required {required:.2f}, available {available:.2f}"
        super().__init__(
            message,
            context={"required": required, "available": available, "symbol": symbol}
        )


class DuplicateOrderError(OrderError):
    """Duplicate order ID detected."""
    error_code = "ORDER_DUPLICATE"
    
    def __init__(self, order_id: str):
        message = f"Duplicate order ID: {order_id}"
        super().__init__(message, context={"order_id": order_id})


# ---------------------------------------------------------------------------
# Gateway Errors
# ---------------------------------------------------------------------------

class GatewayError(QuantBaseError):
    """Base class for gateway-related errors."""
    error_code = "GATEWAY_ERROR"


class GatewayConnectionError(GatewayError):
    """Failed to connect to gateway."""
    error_code = "GATEWAY_CONNECTION_ERROR"
    
    def __init__(self, gateway_name: str, reason: str):
        message = f"Failed to connect to gateway '{gateway_name}': {reason}"
        super().__init__(message, context={"gateway_name": gateway_name})


class GatewayTimeoutError(GatewayError):
    """Gateway operation timed out."""
    error_code = "GATEWAY_TIMEOUT"
    
    def __init__(self, gateway_name: str, operation: str, timeout_seconds: float):
        message = f"Gateway '{gateway_name}' timed out during {operation} (timeout: {timeout_seconds}s)"
        super().__init__(
            message,
            context={"gateway_name": gateway_name, "operation": operation, "timeout": timeout_seconds}
        )


class GatewayAuthError(GatewayError):
    """Gateway authentication failed."""
    error_code = "GATEWAY_AUTH_ERROR"
    
    def __init__(self, gateway_name: str, reason: str = "Authentication failed"):
        message = f"Gateway '{gateway_name}' authentication failed: {reason}"
        super().__init__(message, context={"gateway_name": gateway_name})


class GatewayNotReadyError(GatewayError):
    """Gateway is not ready for operations."""
    error_code = "GATEWAY_NOT_READY"
    
    def __init__(self, gateway_name: str, current_state: str):
        message = f"Gateway '{gateway_name}' is not ready (state: {current_state})"
        super().__init__(
            message,
            context={"gateway_name": gateway_name, "state": current_state}
        )


# ---------------------------------------------------------------------------
# Risk Management Errors
# ---------------------------------------------------------------------------

class RiskError(QuantBaseError):
    """Base class for risk management errors."""
    error_code = "RISK_ERROR"


class RiskLimitExceeded(RiskError):
    """Risk limit has been exceeded."""
    error_code = "RISK_LIMIT_EXCEEDED"
    
    def __init__(self, limit_type: str, current: float, limit: float, **context):
        message = f"Risk limit exceeded: {limit_type} is {current:.2f}, limit is {limit:.2f}"
        super().__init__(
            message,
            context={"limit_type": limit_type, "current": current, "limit": limit, **context}
        )


class PositionLimitExceeded(RiskError):
    """Position limit has been exceeded."""
    error_code = "POSITION_LIMIT_EXCEEDED"
    
    def __init__(self, symbol: str, requested: float, limit: float):
        message = f"Position limit exceeded for '{symbol}': requested {requested:.0f}, limit {limit:.0f}"
        super().__init__(
            message,
            context={"symbol": symbol, "requested": requested, "limit": limit}
        )


class DrawdownLimitExceeded(RiskError):
    """Drawdown limit has been exceeded."""
    error_code = "DRAWDOWN_LIMIT_EXCEEDED"
    
    def __init__(self, current_drawdown: float, max_drawdown: float):
        message = f"Drawdown limit exceeded: current {current_drawdown:.2%}, limit {max_drawdown:.2%}"
        super().__init__(
            message,
            context={"current_drawdown": current_drawdown, "max_drawdown": max_drawdown}
        )


# ---------------------------------------------------------------------------
# Backtest Errors
# ---------------------------------------------------------------------------

class BacktestError(QuantBaseError):
    """Base class for backtest-specific errors."""
    error_code = "BACKTEST_ERROR"


class BacktestConfigError(BacktestError):
    """Backtest configuration error."""
    error_code = "BACKTEST_CONFIG_ERROR"


class NoTradesError(BacktestError):
    """Backtest produced no trades."""
    error_code = "BACKTEST_NO_TRADES"
    
    def __init__(self, strategy_name: str, symbol: str):
        message = f"Backtest '{strategy_name}' on '{symbol}' produced no trades"
        super().__init__(
            message,
            context={"strategy_name": strategy_name, "symbol": symbol}
        )


class EmptyDataError(BacktestError):
    """No data available for backtest."""
    error_code = "BACKTEST_EMPTY_DATA"
    
    def __init__(self, symbols: List[str], date_range: str):
        message = f"No data available for backtest: symbols={symbols}, range={date_range}"
        super().__init__(
            message,
            context={"symbols": symbols, "date_range": date_range}
        )


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def classify_exception(exc: Exception) -> str:
    """
    Classify an exception into a category.
    
    Returns:
        Category string: 'data', 'strategy', 'order', 'gateway', 'risk', 'config', 'unknown'
    """
    if isinstance(exc, DataError):
        return "data"
    elif isinstance(exc, StrategyError):
        return "strategy"
    elif isinstance(exc, OrderError):
        return "order"
    elif isinstance(exc, GatewayError):
        return "gateway"
    elif isinstance(exc, RiskError):
        return "risk"
    elif isinstance(exc, ConfigurationError):
        return "config"
    elif isinstance(exc, BacktestError):
        return "backtest"
    elif isinstance(exc, QuantBaseError):
        return "quant"
    else:
        return "unknown"


def wrap_exception(exc: Exception, wrapper_class: type = QuantBaseError) -> QuantBaseError:
    """
    Wrap a standard exception in a QuantBaseError.
    
    Args:
        exc: Original exception
        wrapper_class: Wrapper class to use
    
    Returns:
        Wrapped exception
    """
    if isinstance(exc, QuantBaseError):
        return exc
    
    return wrapper_class(
        str(exc),
        cause=exc,
        context={"original_type": type(exc).__name__}
    )


# ---------------------------------------------------------------------------
# Exception Registry for Error Codes
# ---------------------------------------------------------------------------

ERROR_CODE_MAP: Dict[str, type] = {
    cls.error_code: cls
    for name, cls in globals().items()
    if isinstance(cls, type) and issubclass(cls, QuantBaseError) and cls is not QuantBaseError
}


def get_exception_by_code(error_code: str) -> Optional[type]:
    """Get exception class by error code."""
    return ERROR_CODE_MAP.get(error_code)
