"""
Paper Trading Gateway (V3.0.0 - Cleaned)

Event-driven simulated order matching for strategy testing.
Exclusively uses MatchingEngine for realistic simulation.

V3.0.0 Changes:
- Removed V2 legacy code (simple next-bar-open matching)
- MatchingEngine is now mandatory (no backward compatibility mode)
- Cleaner interface with better type hints
- Integrated with unified interfaces

Features:
- Realistic intrabar order matching with price-time priority
- Configurable slippage models
- Support for market/limit/stop orders
- Order book depth tracking
- Event-driven trade notifications
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import pandas as pd
import logging

from src.core.events import Event, EventEngine, EventType
from src.core.interfaces import (
    TradeGateway, PositionInfo, AccountInfo, OrderInfo, TradeInfo,
    Side, OrderTypeEnum, OrderStatusEnum
)

# Simulation components
try:
    from src.simulation.matching_engine import MatchingEngine
    from src.simulation.order import Order as SimOrder, OrderDirection, OrderType as SimOrderType, Trade as SimTrade
    from src.simulation.slippage import FixedSlippage, SlippageModel
    _SIMULATION_AVAILABLE = True
except ImportError:
    _SIMULATION_AVAILABLE = False

# Risk manager (optional, avoids circular dependency via try/except)
try:
    from src.core.risk_manager_v2 import RiskManagerV2 as _RiskManagerV2
    _RISK_MANAGER_AVAILABLE = True
except ImportError:
    _RISK_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _Position:
    """Internal position state."""
    size: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0


class PaperGateway(TradeGateway):
    """
    Paper trading gateway with event-driven matching engine.
    
    V3.0.0 - Exclusively uses MatchingEngine for realistic order simulation.
    
    Features:
    - Realistic intrabar matching with slippage
    - Support for market/limit/stop orders
    - Configurable slippage models
    - Order book depth tracking
    - Price-time priority matching
    - Event-driven trade notifications
    
    Usage:
        >>> events = EventEngine()
        >>> events.start()
        >>> 
        >>> # Initialize with slippage model
        >>> from src.simulation.slippage import FixedSlippage
        >>> gw = PaperGateway(
        ...     events, 
        ...     initial_cash=200_000,
        ...     slippage_model=FixedSlippage(slippage_ticks=1, tick_size=0.01)
        ... )
        >>> 
        >>> # Submit order
        >>> order_id = gw.send_order("600519.SH", "buy", 100, order_type="limit", price=1850.0)
        >>> 
        >>> # Inject market data (triggers matching)
        >>> bar = pd.Series({"open": 1850, "high": 1860, "low": 1840, "close": 1850, "volume": 10000})
        >>> gw.on_bar("600519.SH", bar)
        >>> 
        >>> # Query state
        >>> account = gw.query_account()
        >>> position = gw.query_position("600519.SH")
    
    Note:
        Requires simulation module: `pip install sortedcontainers`
    """
    
    def __init__(
        self,
        events: EventEngine,
        initial_cash: float = 200_000.0,
        slippage_model: Optional["SlippageModel"] = None,
        commission_rate: float = 0.0003,
        risk_manager: Optional[Any] = None,
    ):
        """
        Initialize paper trading gateway.

        Args:
            events: EventEngine for order/trade event publishing
            initial_cash: Starting cash balance
            slippage_model: Slippage model (default: FixedSlippage(1, 0.01))
            commission_rate: Commission rate (default: 0.03%)
            risk_manager: Optional RiskManagerV2 instance for pre-order risk checks.
                          When provided, every send_order call is validated against
                          the risk manager before being submitted to the matching engine.

        Raises:
            ImportError: If simulation module is not available
        """
        if not _SIMULATION_AVAILABLE:
            raise ImportError(
                "Simulation module not available. "
                "Please ensure src.simulation package is properly installed. "
                "Required: pip install sortedcontainers"
            )
        
        self.events = events
        self._initial_cash = initial_cash
        self._cash = initial_cash
        self._positions: Dict[str, _Position] = {}
        self._orders: Dict[str, OrderInfo] = {}
        self._trades: List[TradeInfo] = []
        self._last_prices: Dict[str, float] = {}
        self._oid_counter = 0
        self._tid_counter = 0
        self._commission_rate = commission_rate
        self._risk_manager = risk_manager
        
        # Initialize Matching Engine with slippage
        if slippage_model is None:
            slippage_model = FixedSlippage(slippage_ticks=1, tick_size=0.01)
        
        self.matching_engine = MatchingEngine(
            slippage_model=slippage_model,
            event_engine=events,
        )
        
        # Register for trade events from matching engine
        events.register(EventType.TRADE, self._on_trade)
        
        logger.info(f"PaperGateway initialized: cash={initial_cash}, commission={commission_rate}")
    
    def _next_order_id(self) -> str:
        """Generate next order ID."""
        self._oid_counter += 1
        return f"PAPER-{self._oid_counter:08d}"
    
    def _next_trade_id(self) -> str:
        """Generate next trade ID."""
        self._tid_counter += 1
        return f"TRADE-{self._tid_counter:08d}"
    
    # ---------------------------------------------------------------------------
    # Market Data Interface
    # ---------------------------------------------------------------------------
    
    def on_bar(self, symbol: str, bar: pd.Series) -> None:
        """
        Inject market data and trigger order matching.
        
        This method should be called for each bar to:
        1. Update last known prices
        2. Trigger limit order matching
        3. Check stop order triggers
        
        Args:
            symbol: Symbol identifier
            bar: Bar data with OHLCV fields (open, high, low, close, volume)
        
        Example:
            >>> bar = pd.Series({
            ...     "open": 1850, "high": 1860, "low": 1840, 
            ...     "close": 1850, "volume": 10000
            ... })
            >>> gw.on_bar("600519.SH", bar)
        """
        # Update last price
        self._last_prices[symbol] = float(bar.get("close", bar.get("Close", 0)))
        
        # Forward to matching engine
        self.matching_engine.on_bar(symbol, bar)
    
    def on_tick(self, symbol: str, price: float, volume: float = 0) -> None:
        """
        Inject tick data (for future tick-level simulation).
        
        Args:
            symbol: Symbol identifier
            price: Current price
            volume: Trade volume (optional)
        """
        self._last_prices[symbol] = price
        # Future: self.matching_engine.on_tick(symbol, price, volume)
    
    def mark_price(self, symbol: str, price: float) -> None:
        """
        Update last known price for equity calculation.
        
        Args:
            symbol: Symbol identifier
            price: Current price
        """
        self._last_prices[symbol] = price
    
    # ---------------------------------------------------------------------------
    # Order Management
    # ---------------------------------------------------------------------------
    
    def send_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> str:
        """
        Submit a new order.
        
        Args:
            symbol: Symbol identifier (e.g., "600519.SH")
            side: Order side ("buy" or "sell")
            size: Order size (positive number)
            price: Limit/stop price (required for limit/stop orders)
            order_type: Order type ("market", "limit", or "stop")
        
        Returns:
            Order ID string
        
        Raises:
            ValueError: If invalid parameters provided
        
        Example:
            >>> # Market order
            >>> oid = gw.send_order("600519.SH", "buy", 100)
            >>> 
            >>> # Limit order
            >>> oid = gw.send_order("600519.SH", "buy", 100, price=1850.0, order_type="limit")
            >>> 
            >>> # Stop order
            >>> oid = gw.send_order("600519.SH", "sell", 100, price=1800.0, order_type="stop")
        """
        # Validate inputs
        size = abs(float(size))
        if size <= 0:
            raise ValueError("Order size must be positive")
        
        side_enum = Side.BUY if side.lower() == "buy" else Side.SELL
        order_type_lower = order_type.lower()
        
        if order_type_lower == "limit" and price is None:
            raise ValueError("Limit orders require a price")
        if order_type_lower == "stop" and price is None:
            raise ValueError("Stop orders require a price")

        # Risk pre-check (executed before order ID generation so rejected orders
        # never enter the order book or affect state)
        if self._risk_manager is not None:
            acc_dict = self.query_account()
            account_info = AccountInfo(
                account_id=acc_dict.get("account_id", "PAPER"),
                cash=acc_dict.get("balance", 0.0),
                total_value=acc_dict.get("equity", 0.0),
                available=acc_dict.get("available", 0.0),
                unrealized_pnl=acc_dict.get("unrealized_pnl", 0.0),
                realized_pnl=acc_dict.get("realized_pnl", 0.0),
            )
            positions_info: Dict[str, PositionInfo] = {}
            for sym, pos in self._positions.items():
                if pos.size != 0:
                    market_price = self._last_prices.get(sym, pos.avg_price)
                    positions_info[sym] = PositionInfo(
                        symbol=sym,
                        size=pos.size,
                        avg_price=pos.avg_price,
                        market_value=pos.size * market_price,
                        unrealized_pnl=pos.size * (market_price - pos.avg_price),
                        realized_pnl=pos.realized_pnl,
                    )

            order_price = price if price is not None else self._last_prices.get(symbol, 0.0)
            risk_result = self._risk_manager.check_order(
                symbol=symbol,
                side=side_enum,
                quantity=size,
                price=order_price,
                account=account_info,
                positions=positions_info,
            )
            if not risk_result:
                self.events.put(Event(EventType.RISK_WARNING, {
                    "symbol": symbol,
                    "reason": risk_result.reason,
                    "rule": risk_result.rule_name,
                }))
                raise ValueError(
                    f"Order rejected by risk check [{risk_result.rule_name}]: {risk_result.reason}"
                )

        # Generate order ID
        oid = self._next_order_id()
        
        # Create local order tracking
        otype = OrderTypeEnum.MARKET
        if order_type_lower == "limit":
            otype = OrderTypeEnum.LIMIT
        elif order_type_lower == "stop":
            otype = OrderTypeEnum.STOP
        
        local_order = OrderInfo(
            order_id=oid,
            symbol=symbol,
            side=side_enum,
            order_type=otype,
            price=price,
            quantity=size,
            status=OrderStatusEnum.SUBMITTED,
            create_time=pd.Timestamp.now(),
        )
        self._orders[oid] = local_order
        
        # Emit order sent event
        self.events.put(Event(EventType.ORDER_SENT, local_order))
        
        # Convert to simulation order format
        sim_direction = OrderDirection.BUY if side_enum == Side.BUY else OrderDirection.SELL
        
        if order_type_lower == "market":
            sim_type = SimOrderType.MARKET
        elif order_type_lower == "stop":
            sim_type = SimOrderType.STOP
        else:
            sim_type = SimOrderType.LIMIT
        
        sim_order = SimOrder(
            order_id=oid,
            symbol=symbol,
            direction=sim_direction,
            order_type=sim_type,
            quantity=size,
            price=price,
            stop_price=price if sim_type == SimOrderType.STOP else None,
        )
        
        # Submit to matching engine
        self.matching_engine.submit_order(sim_order)
        
        logger.debug(f"Order submitted: {oid} {side} {size} {symbol} @ {price} ({order_type})")
        
        return oid
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancellation was submitted
        
        Note:
            Orders that are already filled cannot be cancelled.
        """
        if order_id not in self._orders:
            logger.warning(f"Order not found: {order_id}")
            return False
        
        order = self._orders[order_id]
        
        if not order.is_active:
            logger.warning(f"Order not active: {order_id} (status={order.status})")
            return False
        
        # Update order status
        order.status = OrderStatusEnum.CANCELLED
        order.update_time = pd.Timestamp.now()
        
        # Try to cancel in matching engine (if it supports cancellation)
        if hasattr(self.matching_engine, 'cancel_order'):
            self.matching_engine.cancel_order(order_id)
        
        # Emit cancelled event
        self.events.put(Event(EventType.ORDER_CANCELLED, order))
        
        logger.debug(f"Order cancelled: {order_id}")
        
        return True
    
    def query_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query orders.
        
        Args:
            symbol: Filter by symbol (None for all)
        
        Returns:
            List of order dictionaries
        """
        result = []
        for order in self._orders.values():
            if symbol is None or order.symbol == symbol:
                result.append({
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "order_type": order.order_type.value,
                    "price": order.price,
                    "quantity": order.quantity,
                    "filled_quantity": order.filled_quantity,
                    "status": order.status.value,
                    "create_time": order.create_time,
                })
        return result
    
    # ---------------------------------------------------------------------------
    # Trade Handling
    # ---------------------------------------------------------------------------
    
    def _on_trade(self, event: Event) -> None:
        """
        Handle trade events from matching engine.
        
        Updates positions and cash based on executed trades.
        
        Args:
            event: Trade event from matching engine
        """
        trade: SimTrade = event.data
        
        # Find corresponding order
        order = self._orders.get(trade.order_id)
        if order:
            # Update order status
            order.filled_quantity += trade.quantity
            order.avg_fill_price = (
                (order.avg_fill_price * (order.filled_quantity - trade.quantity) + 
                 trade.price * trade.quantity) / order.filled_quantity
            )
            order.update_time = pd.Timestamp.now()
            
            if order.filled_quantity >= order.quantity:
                order.status = OrderStatusEnum.FILLED
            else:
                order.status = OrderStatusEnum.PARTIAL
            
            # Emit order filled event
            self.events.put(Event(EventType.ORDER_FILLED, order))
        
        # Calculate commission
        trade_value = trade.price * trade.quantity
        commission = trade_value * self._commission_rate
        
        # Update position and cash
        self._update_position(trade, commission)
        
        # Create trade record
        tid = self._next_trade_id()
        trade_info = TradeInfo(
            trade_id=tid,
            order_id=trade.order_id,
            symbol=trade.symbol,
            side=Side.BUY if trade.direction == OrderDirection.BUY else Side.SELL,
            price=trade.price,
            quantity=trade.quantity,
            commission=commission,
            timestamp=pd.Timestamp.now(),
        )
        self._trades.append(trade_info)
        
        # Update last price
        self._last_prices[trade.symbol] = trade.price
        
        logger.debug(
            f"Trade executed: {tid} {trade.direction.name} {trade.quantity} "
            f"{trade.symbol} @ {trade.price:.2f} (commission={commission:.2f})"
        )
    
    def _update_position(self, trade: SimTrade, commission: float) -> None:
        """
        Update position and cash based on trade.
        
        Args:
            trade: Executed trade
            commission: Trade commission
        """
        pos = self._positions.setdefault(trade.symbol, _Position())
        trade_value = trade.price * trade.quantity
        
        if trade.direction == OrderDirection.BUY:
            # Buy: increase position, decrease cash
            new_size = pos.size + trade.quantity
            if new_size != 0:
                # Update average price
                pos.avg_price = (
                    (pos.avg_price * pos.size + trade.price * trade.quantity) / new_size
                )
            pos.size = new_size
            self._cash -= (trade_value + commission)
        
        else:  # SELL
            # Sell: decrease position, increase cash
            # Calculate realized PnL
            if pos.size > 0:
                realized_pnl = (trade.price - pos.avg_price) * min(trade.quantity, pos.size)
                pos.realized_pnl += realized_pnl
            
            pos.size = max(0, pos.size - trade.quantity)
            self._cash += (trade_value - commission)
            
            # Reset avg_price if position closed
            if pos.size == 0:
                pos.avg_price = 0.0
    
    # ---------------------------------------------------------------------------
    # Account Queries
    # ---------------------------------------------------------------------------
    
    def query_account(self) -> Dict[str, Any]:
        """
        Query account balance and equity.
        
        Returns:
            Dictionary with account information:
            - balance: Cash balance
            - equity: Total equity (cash + positions value)
            - positions_value: Total position market value
            - unrealized_pnl: Unrealized profit/loss
            - realized_pnl: Realized profit/loss
            - available: Available cash for trading
        
        Example:
            >>> account = gw.query_account()
            >>> print(f"Equity: ${account['equity']:.2f}")
        """
        positions_value = 0.0
        unrealized_pnl = 0.0
        realized_pnl = 0.0
        
        for sym, pos in self._positions.items():
            if pos.size != 0:
                price = self._last_prices.get(sym, pos.avg_price)
                market_value = pos.size * price
                positions_value += market_value
                unrealized_pnl += pos.size * (price - pos.avg_price)
            realized_pnl += pos.realized_pnl
        
        equity = self._cash + positions_value
        
        return {
            "account_id": "PAPER",
            "balance": self._cash,
            "equity": equity,
            "positions_value": positions_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "available": self._cash,
            "initial_cash": self._initial_cash,
            "return_pct": (equity - self._initial_cash) / self._initial_cash * 100,
        }
    
    def query_position(self, symbol: str) -> Dict[str, Any]:
        """
        Query position for a symbol.
        
        Args:
            symbol: Symbol identifier
        
        Returns:
            Dictionary with position information:
            - symbol: Symbol identifier
            - size: Position size (0 if no position)
            - avg_price: Average entry price
            - market_value: Current market value
            - unrealized_pnl: Unrealized profit/loss
            - realized_pnl: Realized profit/loss
        
        Example:
            >>> pos = gw.query_position("600519.SH")
            >>> print(f"Size: {pos['size']}, PnL: ${pos['unrealized_pnl']:.2f}")
        """
        pos = self._positions.get(symbol, _Position())
        market_price = self._last_prices.get(symbol, pos.avg_price)
        market_value = pos.size * market_price
        unrealized_pnl = pos.size * (market_price - pos.avg_price) if pos.size != 0 else 0
        
        return {
            "symbol": symbol,
            "size": pos.size,
            "avg_price": pos.avg_price,
            "market_price": market_price,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": pos.realized_pnl,
        }
    
    def query_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Query all positions.
        
        Returns:
            Dictionary mapping symbol to position info
        """
        return {sym: self.query_position(sym) for sym in self._positions}
    
    def query_trades(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query trade history.
        
        Args:
            symbol: Filter by symbol (None for all)
        
        Returns:
            List of trade dictionaries
        """
        result = []
        for trade in self._trades:
            if symbol is None or trade.symbol == symbol:
                result.append({
                    "trade_id": trade.trade_id,
                    "order_id": trade.order_id,
                    "symbol": trade.symbol,
                    "side": trade.side.value,
                    "price": trade.price,
                    "quantity": trade.quantity,
                    "value": trade.value,
                    "commission": trade.commission,
                    "timestamp": trade.timestamp,
                })
        return result
    
    # ---------------------------------------------------------------------------
    # State Management
    # ---------------------------------------------------------------------------
    
    def reset(self, initial_cash: Optional[float] = None) -> None:
        """
        Reset gateway state (for multiple backtest runs).
        
        Args:
            initial_cash: New initial cash (uses previous if None)
        """
        if initial_cash is not None:
            self._initial_cash = initial_cash
        
        self._cash = self._initial_cash
        self._positions.clear()
        self._orders.clear()
        self._trades.clear()
        self._last_prices.clear()
        self._oid_counter = 0
        self._tid_counter = 0
        
        # Reset matching engine if it supports it
        if hasattr(self.matching_engine, 'reset'):
            self.matching_engine.reset()
        
        logger.info(f"PaperGateway reset: cash={self._initial_cash}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get trading statistics summary.
        
        Returns:
            Dictionary with trading statistics
        """
        account = self.query_account()
        
        total_trades = len(self._trades)
        buy_trades = sum(1 for t in self._trades if t.side == Side.BUY)
        sell_trades = total_trades - buy_trades
        
        total_commission = sum(t.commission for t in self._trades)
        total_volume = sum(t.value for t in self._trades)
        
        return {
            "account": account,
            "total_trades": total_trades,
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "total_orders": len(self._orders),
            "filled_orders": sum(1 for o in self._orders.values() if o.status == OrderStatusEnum.FILLED),
            "cancelled_orders": sum(1 for o in self._orders.values() if o.status == OrderStatusEnum.CANCELLED),
            "total_commission": total_commission,
            "total_volume": total_volume,
        }
