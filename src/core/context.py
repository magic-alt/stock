"""
Strategy Execution Context

Bridges the Strategy with the execution engine (Paper or Live).
Provides a unified interface for market data access, order management,
and position tracking across different execution environments.

V3.0.0: Initial implementation - EventEngineContext for Paper/Live trading.

Usage:
    >>> from src.core.context import EventEngineContext
    >>> from src.core.paper_gateway_v3 import PaperGateway
    >>> 
    >>> # Create context with gateway and data
    >>> ctx = EventEngineContext(gateway=gateway, data_map={"600519.SH": df})
    >>> 
    >>> # Use in strategy
    >>> hist = ctx.history("600519.SH", 20)
    >>> ctx.buy("600519.SH", 100, price=1850.0)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from src.core.interfaces import (
    PositionInfo, AccountInfo, BarData, StrategyContext,
    Side, OrderTypeEnum
)
from src.core.logger import get_logger

if TYPE_CHECKING:
    from src.core.paper_gateway_v3 import PaperGateway

logger = get_logger("context")


class EventEngineContext(StrategyContext):
    """
    Context implementation for EventEngine-based execution.
    
    Works with PaperGateway (simulation) or LiveGateway (real trading).
    Provides the StrategyContext interface that BaseStrategy expects.
    
    Features:
    - Historical data access via history()
    - Current price queries
    - Order submission (buy/sell)
    - Position and account tracking
    - Structured logging
    
    Attributes:
        gateway: Trading gateway (Paper or Live)
        data_map: Historical data for all symbols (symbol -> DataFrame)
        
    Example:
        >>> ctx = EventEngineContext(gateway, data_map)
        >>> ctx.set_datetime(datetime(2024, 1, 15))
        >>> 
        >>> # Access data
        >>> hist = ctx.history("600519.SH", ["close"], 20)
        >>> price = ctx.current_price("600519.SH")
        >>> 
        >>> # Trading
        >>> ctx.buy("600519.SH", 100)
    """
    
    def __init__(
        self,
        gateway: "PaperGateway",
        data_map: Optional[Dict[str, pd.DataFrame]] = None,
        symbols: Optional[List[str]] = None,
    ):
        """
        Initialize execution context.
        
        Args:
            gateway: Trading gateway instance
            data_map: Historical data map (symbol -> OHLCV DataFrame)
            symbols: List of tradeable symbols
        """
        self.gateway = gateway
        self._data_map = data_map or {}
        self._symbols = symbols or list(self._data_map.keys())
        self._current_dt: Optional[datetime] = None
        self._current_bars: Dict[str, BarData] = {}
    
    # ---------------------------------------------------------------------------
    # Time Management (Called by Runner)
    # ---------------------------------------------------------------------------
    
    def set_datetime(self, dt: datetime) -> None:
        """
        Update current simulation/trading time.
        
        Called by the runner before each bar is processed.
        
        Args:
            dt: Current bar datetime
        """
        self._current_dt = dt
    
    def set_current_bar(self, symbol: str, bar: BarData) -> None:
        """
        Set the current bar for a symbol.
        
        Called by the runner when processing each bar.
        
        Args:
            symbol: Symbol identifier
            bar: Current bar data
        """
        self._current_bars[symbol] = bar
    
    # ---------------------------------------------------------------------------
    # StrategyContext Protocol Implementation
    # ---------------------------------------------------------------------------
    
    @property
    def account(self) -> AccountInfo:
        """Get current account information."""
        acc_dict = self.gateway.query_account()
        return AccountInfo(
            account_id=acc_dict.get("account_id", "PAPER"),
            cash=acc_dict.get("balance", 0),
            total_value=acc_dict.get("equity", 0),
            available=acc_dict.get("available", 0),
            unrealized_pnl=acc_dict.get("unrealized_pnl", 0),
            realized_pnl=acc_dict.get("realized_pnl", 0),
        )
    
    @property
    def positions(self) -> Dict[str, PositionInfo]:
        """Get all current positions."""
        result = {}
        
        # Query all positions from gateway
        if hasattr(self.gateway, 'query_all_positions'):
            all_pos = self.gateway.query_all_positions()
            for symbol, pos_dict in all_pos.items():
                if pos_dict.get("size", 0) != 0:
                    result[symbol] = PositionInfo(
                        symbol=symbol,
                        size=pos_dict.get("size", 0),
                        avg_price=pos_dict.get("avg_price", 0),
                        market_value=pos_dict.get("market_value", 0),
                        unrealized_pnl=pos_dict.get("unrealized_pnl", 0),
                        realized_pnl=pos_dict.get("realized_pnl", 0),
                    )
        else:
            # Fallback: query each symbol individually
            for symbol in self._symbols:
                pos_dict = self.gateway.query_position(symbol)
                if pos_dict.get("size", 0) != 0:
                    result[symbol] = PositionInfo(
                        symbol=symbol,
                        size=pos_dict.get("size", 0),
                        avg_price=pos_dict.get("avg_price", 0),
                        market_value=pos_dict.get("market_value", 0),
                        unrealized_pnl=pos_dict.get("unrealized_pnl", 0),
                    )
        
        return result
    
    def current_price(self, symbol: str, field: str = "close") -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Symbol identifier
            field: Price field (open, high, low, close)
            
        Returns:
            Current price or None if not available
        """
        bar = self._current_bars.get(symbol)
        if bar:
            return getattr(bar, field.lower(), None)
        
        # Fallback: try to get from historical data
        if symbol in self._data_map and self._current_dt:
            df = self._data_map[symbol]
            if self._current_dt in df.index:
                row = df.loc[self._current_dt]
                return float(row.get(field, row.get(field.capitalize(), 0)))
        
        return None
    
    def get_bar(self, symbol: str) -> Optional[BarData]:
        """
        Get current bar data for a symbol.
        
        Args:
            symbol: Symbol identifier
            
        Returns:
            Current BarData or None
        """
        return self._current_bars.get(symbol)
    
    def history(
        self,
        symbol: str,
        fields: List[str],
        periods: int,
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """
        Get historical data up to current time.
        
        Args:
            symbol: Symbol identifier
            fields: List of fields to retrieve (open, high, low, close, volume)
            periods: Number of periods to look back
            frequency: Data frequency (currently only "1d" supported)
            
        Returns:
            DataFrame with requested fields
        
        Example:
            >>> hist = ctx.history("600519.SH", ["close", "volume"], 20)
            >>> ma20 = hist["close"].mean()
        """
        if symbol not in self._data_map:
            logger.warning("Symbol not in data map", symbol=symbol)
            return pd.DataFrame()
        
        df = self._data_map[symbol]
        
        # Slice data up to (but not including) current time
        if self._current_dt:
            # Include current bar or not? Usually we want data BEFORE current bar for indicators
            mask = df.index < self._current_dt
            current_slice = df[mask]
        else:
            current_slice = df
        
        # Get last N periods
        result_df = current_slice.tail(periods)
        
        # Select requested fields (case-insensitive)
        available_cols = result_df.columns.tolist()
        selected_cols = []
        for field in fields:
            # Try exact match first
            if field in available_cols:
                selected_cols.append(field)
            # Try lowercase
            elif field.lower() in available_cols:
                selected_cols.append(field.lower())
            # Try capitalized
            elif field.capitalize() in available_cols:
                selected_cols.append(field.capitalize())
        
        if selected_cols:
            return result_df[selected_cols].copy()
        return result_df.copy()
    
    # ---------------------------------------------------------------------------
    # Order Management
    # ---------------------------------------------------------------------------
    
    def buy(
        self,
        symbol: str,
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Submit a buy order.
        
        Args:
            symbol: Symbol to buy
            size: Order size (None for auto-sizing)
            price: Limit price (None for market order)
            order_type: Order type ("market" or "limit")
            
        Returns:
            Order ID string
        """
        if size is None:
            # Auto-size: 10% of available cash
            size = self._calculate_auto_size(symbol, "buy")
        
        if size <= 0:
            logger.warning("Invalid order size", symbol=symbol, size=size)
            return ""
        
        otype = "market" if price is None else order_type
        
        logger.info(
            "Submitting buy order",
            symbol=symbol,
            size=size,
            price=price,
            order_type=otype,
            dt=self._current_dt
        )
        
        return self.gateway.send_order(symbol, "buy", size, price, otype)
    
    def sell(
        self,
        symbol: str,
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Submit a sell order.
        
        Args:
            symbol: Symbol to sell
            size: Order size (None for full position)
            price: Limit price (None for market order)
            order_type: Order type ("market" or "limit")
            
        Returns:
            Order ID string
        """
        if size is None:
            # Auto-size: full position
            pos = self.positions.get(symbol)
            size = pos.size if pos else 0
        
        if size <= 0:
            logger.warning("No position to sell", symbol=symbol)
            return ""
        
        otype = "market" if price is None else order_type
        
        logger.info(
            "Submitting sell order",
            symbol=symbol,
            size=size,
            price=price,
            order_type=otype,
            dt=self._current_dt
        )
        
        return self.gateway.send_order(symbol, "sell", size, price, otype)
    
    def cancel(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation submitted
        """
        return self.gateway.cancel_order(order_id)
    
    # ---------------------------------------------------------------------------
    # Utility Methods
    # ---------------------------------------------------------------------------
    
    def log(self, message: str, level: str = "info") -> None:
        """
        Log a message with current context.
        
        Args:
            message: Log message
            level: Log level (debug, info, warning, error)
        """
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(message, dt=self._current_dt)
    
    def get_datetime(self) -> datetime:
        """Get current bar datetime."""
        return self._current_dt or datetime.now()
    
    def _calculate_auto_size(self, symbol: str, side: str) -> float:
        """
        Calculate automatic position size.
        
        Default: 10% of available cash.
        
        Args:
            symbol: Symbol to trade
            side: Order side
            
        Returns:
            Position size
        """
        account = self.account
        price = self.current_price(symbol)
        
        if not price or price <= 0:
            return 0
        
        # 10% of available cash
        target_value = account.available * 0.1
        size = int(target_value / price)
        
        # Round to lot size (100 for A-shares)
        size = (size // 100) * 100
        
        return max(0, size)


class BacktestContext(EventEngineContext):
    """
    Context optimized for backtesting.
    
    Extends EventEngineContext with backtest-specific features:
    - Pre-loaded data access (no data service calls)
    - Deterministic time progression
    - Performance metrics tracking
    """
    
    def __init__(
        self,
        gateway: "PaperGateway",
        data_map: Dict[str, pd.DataFrame],
        **kwargs
    ):
        super().__init__(gateway, data_map, **kwargs)
        self._bar_count = 0
        self._trade_count = 0
    
    def on_bar_start(self):
        """Called at the start of each bar processing."""
        self._bar_count += 1
    
    def on_trade(self):
        """Called when a trade is executed."""
        self._trade_count += 1
    
    @property
    def bar_count(self) -> int:
        """Number of bars processed."""
        return self._bar_count
    
    @property
    def trade_count(self) -> int:
        """Number of trades executed."""
        return self._trade_count
