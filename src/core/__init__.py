"""
Core Module for Quantitative Trading Platform

Provides:
- Event-driven architecture (EventEngine, Event, EventType)
- Gateway protocols and implementations (TradeGateway, HistoryGateway)
- Unified strategy interface (BaseStrategy, StrategyContext)
- Unified data types (BarData, PositionInfo, AccountInfo)
- Structured logging (configure_logging, get_logger)
- EventEngineContext (strategy-gateway bridge)

V3.0.0: Added unified interfaces and strategy base class.
V3.0.0-beta: Added logging, context, paper_runner_v3.
"""

from .events import Event, EventEngine, EventType, Handler
from .gateway import (
    HistoryGateway,
    TradeGateway,
    BacktestGateway,
    LiveGateway,
)

# V3.0.0: Unified interfaces
from .interfaces import (
    BarData,
    TickData,
    PositionInfo,
    AccountInfo,
    OrderInfo,
    TradeInfo,
    Side,
    OrderTypeEnum,
    OrderStatusEnum,
    StrategyContext,
    BaseStrategyProtocol,
    EventEngineProtocol,
    RiskManagerProtocol,
)

# V3.0.0: Unified strategy base class
from .strategy_base import (
    BaseStrategy,
    BacktraderStrategyAdapter,
    ExampleDualMAStrategy,
)

# V3.0.0: PaperGateway - exclusively from paper_gateway_v3.py
from .paper_gateway_v3 import PaperGateway

# Alias for backward compatibility
PaperGatewayV3 = PaperGateway

# V3.0.0-beta: Structured logging
from .logger import configure_logging, get_logger, LogContext

# V3.0.0-beta: EventEngineContext (strategy-gateway bridge)
from .context import EventEngineContext, BacktestContext

# V3.0.0-beta: Paper runner V3
from .paper_runner_v3 import (
    run_paper_v3,
    run_paper_with_nav,
    run_paper_legacy,
    SimpleBuyHoldStrategy,
    SimpleMovingAverageStrategy,
)

# V3.1.0: Unified exception handling
from .exceptions import (
    QuantBaseError,
    ConfigurationError,
    DataError,
    DataProviderError,
    DataNotFoundError,
    DataValidationError,
    StrategyError,
    StrategyNotFoundError,
    StrategyExecutionError,
    OrderError,
    OrderValidationError,
    InsufficientFundsError,
    GatewayError,
    RiskError,
    RiskLimitExceeded,
    BacktestError,
)

# V3.1.0: Global exception handler
from .error_handler import (
    ErrorHandler,
    handle_errors,
    handle_errors_async,
    RetryPolicy,
    safe_call,
    suppress_errors,
)

# V3.1.0: Performance optimization
from .performance import (
    TTLCache,
    cached,
    profile,
    profile_block,
    get_profile_summary,
    batch_process,
    parallel_map,
    MemoryManager,
    memory_guard,
    optimize_dataframe,
    timed,
    RateLimiter,
)

# Monitoring utilities
from .monitoring import (
    SystemMonitor,
    start_monitoring,
    stop_monitoring,
    HeartbeatEmitter,
    HeartbeatMonitor,
    run_with_heartbeat_monitor,
)

__all__ = [
    # Events
    "Event",
    "EventEngine",
    "EventType",
    "Handler",
    "EventEngineProtocol",
    
    # Gateways
    "HistoryGateway",
    "TradeGateway",
    "BacktestGateway",
    "PaperGateway",      # V2 compatible (legacy)
    "PaperGatewayV3",    # V3.0 clean version
    "LiveGateway",
    
    # Unified Data Types
    "BarData",
    "TickData",
    "PositionInfo",
    "AccountInfo",
    "OrderInfo",
    "TradeInfo",
    "Side",
    "OrderTypeEnum",
    "OrderStatusEnum",
    
    # Strategy
    "BaseStrategy",
    "BacktraderStrategyAdapter",
    "ExampleDualMAStrategy",
    "StrategyContext",
    "BaseStrategyProtocol",
    
    # Context (V3.0.0-beta)
    "EventEngineContext",
    "BacktestContext",
    
    # Logging (V3.0.0-beta)
    "configure_logging",
    "get_logger",
    "LogContext",
    
    # Paper Runner V3 (V3.0.0-beta)
    "run_paper_v3",
    "run_paper_with_nav",
    "run_paper_legacy",
    "SimpleBuyHoldStrategy",
    "SimpleMovingAverageStrategy",
    
    # Risk
    "RiskManagerProtocol",
    
    # V3.1.0: Exceptions
    "QuantBaseError",
    "ConfigurationError",
    "DataError",
    "DataProviderError",
    "DataNotFoundError",
    "DataValidationError",
    "StrategyError",
    "StrategyNotFoundError",
    "StrategyExecutionError",
    "OrderError",
    "OrderValidationError",
    "InsufficientFundsError",
    "GatewayError",
    "RiskError",
    "RiskLimitExceeded",
    "BacktestError",
    
    # V3.1.0: Error Handler
    "ErrorHandler",
    "handle_errors",
    "handle_errors_async",
    "RetryPolicy",
    "safe_call",
    "suppress_errors",
    
    # V3.1.0: Performance
    "TTLCache",
    "cached",
    "profile",
    "profile_block",
    "get_profile_summary",
    "batch_process",
    "parallel_map",
    "MemoryManager",
    "memory_guard",
    "optimize_dataframe",
    "timed",
    "RateLimiter",

    # Monitoring
    "SystemMonitor",
    "start_monitoring",
    "stop_monitoring",
    "HeartbeatEmitter",
    "HeartbeatMonitor",
    "run_with_heartbeat_monitor",
]
