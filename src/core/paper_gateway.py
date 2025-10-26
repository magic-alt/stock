"""
Paper Trading Gateway

Event-driven simulated order matching for strategy testing.
Implements TradeGateway protocol with next-bar-open execution model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import pandas as pd

from src.core.events import Event, EventEngine, EventType
from src.core.gateway import TradeGateway


@dataclass(slots=True)
class _Position:
    """Internal position state."""
    size: int = 0
    avg_price: float = 0.0


class PaperGateway(TradeGateway):
    """
    Paper trading gateway with event-driven order matching.
    
    Features:
    - Next-bar-open fill execution
    - Event publishing (order.sent/filled/cancelled)
    - In-memory account/position tracking
    - Configurable slippage
    - Cash and equity management
    
    Matching Model:
    - Orders submitted on bar N
    - Matched at open price of bar N+1
    - Fill price = open * (1 + slippage)
    
    Usage:
        >>> events = EventEngine()
        >>> events.start()
        >>> gw = PaperGateway(events, slippage=0.001)
        >>> 
        >>> # Submit order
        >>> order_id = gw.send_order("600519.SH", "buy", 100, order_type="market")
        >>> 
        >>> # Match on next bar's open
        >>> gw.match_on_open("600519.SH", open_price=150.0)
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
    ):
        """
        Initialize paper trading gateway.
        
        Args:
            events: EventEngine for order/trade event publishing
            slippage: Slippage rate (e.g., 0.001 = 0.1%)
            initial_cash: Starting cash balance
        """
        self.events = events
        self.slippage = slippage
        self._cash = initial_cash
        self._positions: Dict[str, _Position] = {}
        self._oid = 0
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._last_prices: Dict[str, float] = {}
    
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
            price: Limit price (ignored for market orders)
            order_type: Order type ("market" or "limit", only "market" supported)
        
        Returns:
            Order ID (integer)
        
        Emits:
            EventType.ORDER_SENT with order details
        
        Example:
            >>> order_id = gw.send_order("600519.SH", "buy", 100)
            >>> # Order will be matched at next bar's open
        """
        oid = self._next_oid()
        order = {
            "id": oid,
            "symbol": symbol,
            "side": side.lower(),
            "size": abs(size),  # Ensure positive
            "type": order_type,
            "price": price,
            "status": "pending",
        }
        self._pending[oid] = order
        
        # Publish order sent event
        self.events.put(Event(EventType.ORDER_SENT, order.copy()))
        
        return oid
    
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
