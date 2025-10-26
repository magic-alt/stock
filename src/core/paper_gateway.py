"""
Paper Trading Gateway

Event-driven simulated order matching for strategy testing.
Implements TradeGateway protocol with next-bar-open execution model.

V3.0.0: Integrated with MatchingEngine for realistic order matching simulation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import pandas as pd

from src.core.events import Event, EventEngine, EventType
from src.core.gateway import TradeGateway

# V3.0.0: Import simulation matching engine
try:
    from src.simulation.matching_engine import MatchingEngine
    from src.simulation.order import Order, OrderDirection, OrderType, OrderStatus
    from src.simulation.slippage import FixedSlippage, SlippageModel
    _SIMULATION_AVAILABLE = True
except ImportError:
    _SIMULATION_AVAILABLE = False


@dataclass(slots=True)
class _Position:
    """Internal position state."""
    size: int = 0
    avg_price: float = 0.0


class PaperGateway(TradeGateway):
    """
    Paper trading gateway with event-driven order matching.
    
    V3.0.0 Features:
    - Integrated MatchingEngine for realistic order simulation
    - Support for market/limit/stop orders
    - Configurable slippage models
    - Order book depth tracking
    - Price-time priority matching
    
    V2.x Features (Legacy):
    - Next-bar-open fill execution
    - Event publishing (order.sent/filled/cancelled)
    - In-memory account/position tracking
    - Cash and equity management
    
    Matching Models:
    - V3.0 (use_matching_engine=True): Realistic intrabar matching with slippage
    - V2.x (use_matching_engine=False): Simple next-bar-open execution
    
    Usage:
        >>> events = EventEngine()
        >>> events.start()
        >>> 
        >>> # V3.0: Use matching engine
        >>> from src.simulation.slippage import FixedSlippage
        >>> gw = PaperGateway(events, use_matching_engine=True, 
        ...                   slippage_model=FixedSlippage(1, 0.01))
        >>> 
        >>> # Submit order
        >>> order_id = gw.send_order("600519.SH", "buy", 100, order_type="limit", price=1850.0)
        >>> 
        >>> # Match on bar update
        >>> bar = pd.Series({"open": 1850, "high": 1860, "low": 1840, "close": 1850, "volume": 10000})
        >>> gw.on_bar("600519.SH", bar)
        >>> 
        >>> # Query state
        >>> account = gw.query_account()
        >>> position = gw.query_position("600519.SH")
    """
    
    def __init__(
        self,
        events: EventEngine,
        slippage: float = 0.0,
        initial_cash: float = 200_000.0,
        use_matching_engine: bool = False,
        slippage_model: Optional[SlippageModel] = None,
    ):
        """
        Initialize paper trading gateway.
        
        Args:
            events: EventEngine for order/trade event publishing
            slippage: Legacy slippage rate (V2.x mode, e.g., 0.001 = 0.1%)
            initial_cash: Starting cash balance
            use_matching_engine: Use V3.0 MatchingEngine (default False for backward compatibility)
            slippage_model: Custom slippage model for V3.0 (default FixedSlippage(1, 0.01))
        
        Note:
            V3.0 mode requires `pip install sortedcontainers`
        """
        self.events = events
        self.slippage = slippage
        self._cash = initial_cash
        self._positions: Dict[str, _Position] = {}
        self._oid = 0
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._last_prices: Dict[str, float] = {}
        
        # V3.0: Matching engine integration
        self.use_matching_engine = use_matching_engine and _SIMULATION_AVAILABLE
        if self.use_matching_engine:
            if slippage_model is None:
                slippage_model = FixedSlippage(slippage_ticks=1, tick_size=0.01)
            self.matching_engine = MatchingEngine(
                slippage_model=slippage_model,
                event_engine=events,
            )
            # Subscribe to trade events from matching engine
            events.register(EventType.TRADE, self._on_matching_engine_trade)
        else:
            self.matching_engine = None
    
    def _next_oid(self) -> int:
        """Generate next order ID."""
        self._oid += 1
        return self._oid
    
    def mark_price(self, symbol: str, price: float) -> None:
        """
        Update last known price for symbol.
        
        Used for equity calculation when position exists but no recent fill.
        
        Args:
            symbol: Symbol identifier
            price: Current price (typically close price)
        """
        self._last_prices[symbol] = price
    
    def send_order(
        self,
        symbol: str,
        side: str,
        size: int,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> Any:
        """
        Submit order (queued for next bar matching).
        
        Args:
            symbol: Symbol identifier (e.g., "600519.SH")
            side: Order side ("buy" or "sell")
            size: Order size in shares (must be positive)
            price: Limit price (required for limit orders)
            order_type: Order type ("market", "limit", or "stop")
        
        Returns:
            Order ID (integer in V2.x mode, string in V3.0 mode)
        
        Emits:
            EventType.ORDER_SENT with order details
        
        Example:
            >>> # V2.x mode: Next-bar matching
            >>> order_id = gw.send_order("600519.SH", "buy", 100)
            >>> 
            >>> # V3.0 mode: Intrabar matching
            >>> order_id = gw.send_order("600519.SH", "buy", 100, price=1850.0, order_type="limit")
        """
        if self.use_matching_engine:
            # V3.0: Use matching engine
            return self._send_order_v3(symbol, side, size, price, order_type)
        else:
            # V2.x: Legacy mode
            return self._send_order_v2(symbol, side, size, price, order_type)
    
    def _send_order_v2(self, symbol: str, side: str, size: int, 
                       price: Optional[float], order_type: str) -> int:
        """Legacy order submission (V2.x)"""
        oid = self._next_oid()
        order = {
            "id": oid,
            "symbol": symbol,
            "side": side.lower(),
            "size": abs(size),
            "type": order_type,
            "price": price,
            "status": "pending",
        }
        self._pending[oid] = order
        self.events.put(Event(EventType.ORDER_SENT, order.copy()))
        return oid
    
    def _send_order_v3(self, symbol: str, side: str, size: int,
                       price: Optional[float], order_type: str) -> str:
        """V3.0 order submission using MatchingEngine"""
        oid = f"O{self._next_oid():08d}"
        
        # Convert to simulation Order object
        direction = OrderDirection.BUY if side.lower() == "buy" else OrderDirection.SELL
        otype = OrderType.MARKET if order_type.lower() == "market" else (
            OrderType.STOP if order_type.lower() == "stop" else OrderType.LIMIT
        )
        
        order = Order(
            order_id=oid,
            symbol=symbol,
            direction=direction,
            order_type=otype,
            quantity=abs(size),
            price=price,
            stop_price=price if otype == OrderType.STOP else None,
        )
        
        # Submit to matching engine
        self.matching_engine.submit_order(order)
        
        # Also track in legacy pending dict for compatibility
        self._pending[int(oid[1:])] = {
            "id": oid,
            "symbol": symbol,
            "side": side.lower(),
            "size": abs(size),
            "type": order_type,
            "price": price,
            "status": "pending",
        }
        
        return oid
    
    def on_bar(self, symbol: str, bar: pd.Series) -> None:
        """
        V3.0: Update matching engine with new bar data.
        
        This triggers limit order matching and stop order checking.
        
        Args:
            symbol: Symbol identifier
            bar: Bar data with OHLCV fields
        
        Example:
            >>> bar = pd.Series({
            ...     "open": 1850, "high": 1860, "low": 1840, 
            ...     "close": 1850, "volume": 10000
            ... })
            >>> gw.on_bar("600519.SH", bar)
        """
        if self.use_matching_engine:
            self.matching_engine.on_bar(symbol, bar)
            self.mark_price(symbol, bar['close'])
    
    def _on_matching_engine_trade(self, event: Event) -> None:
        """
        V3.0: Handle trade events from matching engine.
        
        Updates cash and positions based on executed trades.
        
        Args:
            event: Trade event from matching engine
        """
        from src.simulation.order import Trade
        trade: Trade = event.data
        
        # Get or create position
        pos = self._positions.setdefault(trade.symbol, _Position())
        
        # Calculate value
        value = trade.value
        
        if trade.direction == OrderDirection.BUY:
            # Buy: subtract cash, increase position
            self._cash -= value + trade.fees
            
            # Update avg_price
            new_size = pos.size + trade.quantity
            if new_size > 0:
                pos.avg_price = (
                    (pos.avg_price * pos.size + trade.price * trade.quantity) / new_size
                )
            pos.size = new_size
        
        elif trade.direction == OrderDirection.SELL:
            # Sell: add cash, decrease position
            actual_size = min(trade.quantity, pos.size)
            self._cash += value - trade.fees
            pos.size = max(0, pos.size - actual_size)
            
            # Reset avg_price if position closed
            if pos.size == 0:
                pos.avg_price = 0.0
        
        # Update last price
        self._last_prices[trade.symbol] = trade.price
        
        # Remove from pending (if exists)
        try:
            order_num = int(trade.order_id[1:])  # Remove 'O' prefix
            self._pending.pop(order_num, None)
        except (ValueError, IndexError):
            pass
    
    def cancel_order(self, order_id: Any) -> None:
        """
        Cancel pending order.
        
        Args:
            order_id: Order ID to cancel
        
        Emits:
            EventType.ORDER_CANCELLED if order exists
        
        Note:
            Cannot cancel orders that have already been filled.
        """
        if order_id in self._pending:
            order = self._pending.pop(order_id)
            order["status"] = "cancelled"
            self.events.put(Event(EventType.ORDER_CANCELLED, order))
    
    def query_account(self) -> Dict[str, Any]:
        """
        Query account balance and equity.
        
        Returns:
            Dict with keys:
            - balance: Cash balance
            - equity: Total equity (cash + position values)
            - positions_value: Total position market value
        
        Example:
            >>> account = gw.query_account()
            >>> print(f"Equity: {account['equity']:.2f}")
        """
        positions_value = 0.0
        for sym, pos in self._positions.items():
            if pos.size > 0:
                px = self._last_prices.get(sym, pos.avg_price)
                positions_value += pos.size * px
        
        equity = self._cash + positions_value
        
        return {
            "balance": self._cash,
            "equity": equity,
            "positions_value": positions_value,
        }
    
    def query_position(self, symbol: str) -> Dict[str, Any]:
        """
        Query position for symbol.
        
        Args:
            symbol: Symbol identifier
        
        Returns:
            Dict with keys:
            - symbol: Symbol identifier
            - size: Position size (0 if no position)
            - avg_price: Average entry price
            - market_value: Current market value
        
        Example:
            >>> pos = gw.query_position("600519.SH")
            >>> print(f"Size: {pos['size']}, Avg Price: {pos['avg_price']:.2f}")
        """
        pos = self._positions.get(symbol, _Position())
        market_price = self._last_prices.get(symbol, pos.avg_price)
        market_value = pos.size * market_price
        
        return {
            "symbol": symbol,
            "size": pos.size,
            "avg_price": pos.avg_price,
            "market_value": market_value,
        }
    
    def match_on_open(self, symbol: str, open_price: float) -> None:
        """
        Match all pending orders for symbol at bar's open price.
        
        Matching logic:
        1. Calculate fill price: open_price * (1 + slippage)
        2. For each pending order for this symbol:
           - Update cash (buy: subtract, sell: add)
           - Update position (size and avg_price)
           - Publish ORDER_FILLED event
        3. Remove matched orders from pending queue
        
        Called by PaperRunner before strategy sees the bar.
        
        Args:
            symbol: Symbol identifier
            open_price: Open price of current bar
        
        Emits:
            EventType.ORDER_FILLED for each matched order
        
        Example:
            >>> # Bar N: Strategy submits buy order
            >>> gw.send_order("600519.SH", "buy", 100)
            >>> 
            >>> # Bar N+1: Runner calls match before strategy sees bar
            >>> gw.match_on_open("600519.SH", open_price=150.0)
            >>> # Order filled at 150.0 * (1 + slippage)
        """
        # Calculate fill price with slippage
        fill_price = open_price * (1 + self.slippage)
        self._last_prices[symbol] = fill_price
        
        # Find all pending orders for this symbol
        to_fill = [
            od for od in self._pending.values()
            if od["symbol"] == symbol
        ]
        
        # Match each order
        for order in to_fill:
            self._pending.pop(order["id"], None)
            
            side = order["side"]
            size = order["size"]
            value = fill_price * size
            
            # Get or create position
            pos = self._positions.setdefault(symbol, _Position())
            
            if side == "buy":
                # Buy: subtract cash, increase position
                self._cash -= value
                
                # Update avg_price using weighted average
                new_size = pos.size + size
                if new_size > 0:
                    pos.avg_price = (
                        (pos.avg_price * pos.size + fill_price * size) / new_size
                    )
                pos.size = new_size
            
            elif side == "sell":
                # Sell: add cash, decrease position
                actual_size = min(size, pos.size)  # Can't sell more than we have
                self._cash += fill_price * actual_size
                pos.size = max(0, pos.size - actual_size)
                
                # Reset avg_price if position closed
                if pos.size == 0:
                    pos.avg_price = 0.0
            
            # Publish order filled event
            fill_event = {
                "id": order["id"],
                "symbol": symbol,
                "side": side,
                "size": size,
                "price": fill_price,
                "value": value,
                "timestamp": pd.Timestamp.now(),  # Could be passed from runner
            }
            self.events.put(Event(EventType.ORDER_FILLED, fill_event))
    
    def reset(self, cash: float = 200_000.0) -> None:
        """
        Reset gateway state (for testing/multiple runs).
        
        Args:
            cash: Initial cash balance
        """
        self._cash = cash
        self._positions.clear()
        self._pending.clear()
        self._last_prices.clear()
        self._oid = 0
