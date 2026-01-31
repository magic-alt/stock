"""
Order Management System (OMS) - 订单管理系统

负责订单的完整生命周期管理:
- 订单创建、提交、执行、取消
- 订单状态追踪和历史记录
- 批量订单操作
- 订单事件发布

V3.1.0: Initial release

Usage:
    >>> from src.core.order_manager import OrderManager
    >>> 
    >>> oms = OrderManager(gateway)
    >>> 
    >>> # 创建并提交订单
    >>> order = oms.create_order("600519.SH", Side.BUY, 100, price=1800.0)
    >>> oms.submit_order(order.order_id)
    >>> 
    >>> # 批量操作
    >>> oms.cancel_all_orders("600519.SH")
    >>> 
    >>> # 查询
    >>> active = oms.get_active_orders()
    >>> history = oms.get_order_history()
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from src.core.interfaces import (
    OrderInfo, TradeInfo, Side, OrderTypeEnum, OrderStatusEnum
)
from src.core.events import EventEngine, Event
from src.core.audit import AuditLogger, audit_event
from src.core.auth import Authorizer, Permission, ResourceScope, Subject
from src.core.logger import get_logger

logger = get_logger("order_manager")


# ---------------------------------------------------------------------------
# Order Events
# ---------------------------------------------------------------------------

class OrderEvent(str, Enum):
    """Order lifecycle events."""
    CREATED = "order.created"
    SUBMITTED = "order.submitted"
    ACCEPTED = "order.accepted"
    PARTIAL_FILL = "order.partial_fill"
    FILLED = "order.filled"
    CANCELLED = "order.cancelled"
    REJECTED = "order.rejected"
    EXPIRED = "order.expired"
    ERROR = "order.error"


# ---------------------------------------------------------------------------
# Extended Order Info
# ---------------------------------------------------------------------------

@dataclass
class ManagedOrder:
    """
    Extended order information with management metadata.
    """
    # Core order info
    order_id: str
    symbol: str
    side: Side
    order_type: OrderTypeEnum
    price: Optional[float]
    quantity: float
    
    # Execution info
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: OrderStatusEnum = OrderStatusEnum.PENDING
    
    # Timestamps
    create_time: datetime = field(default_factory=datetime.now)
    submit_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    fill_time: Optional[datetime] = None
    
    # Management metadata
    strategy_id: str = ""
    tenant_id: str = ""
    parent_order_id: str = ""  # For split orders
    child_order_ids: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    
    # Risk info
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Execution info
    broker_order_id: str = ""
    reject_reason: str = ""
    
    @property
    def is_active(self) -> bool:
        return self.status in (
            OrderStatusEnum.PENDING,
            OrderStatusEnum.SUBMITTED,
            OrderStatusEnum.PARTIAL
        )
    
    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatusEnum.FILLED
    
    @property
    def remaining(self) -> float:
        return self.quantity - self.filled_quantity
    
    @property
    def fill_rate(self) -> float:
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity
    
    @property
    def value(self) -> float:
        """Order value at limit price or fill price."""
        price = self.avg_fill_price or self.price or 0
        return price * self.quantity
    
    @property
    def filled_value(self) -> float:
        """Filled value."""
        return self.avg_fill_price * self.filled_quantity
    
    def to_order_info(self) -> OrderInfo:
        """Convert to basic OrderInfo."""
        return OrderInfo(
            order_id=self.order_id,
            symbol=self.symbol,
            side=self.side,
            order_type=self.order_type,
            price=self.price,
            quantity=self.quantity,
            filled_quantity=self.filled_quantity,
            avg_fill_price=self.avg_fill_price,
            status=self.status,
            create_time=self.create_time,
            update_time=self.update_time
        )


# ---------------------------------------------------------------------------
# Order Manager
# ---------------------------------------------------------------------------

class OrderManager:
    """
    订单管理系统 - 管理订单的完整生命周期
    
    Features:
    - 订单创建和验证
    - 订单提交和状态追踪
    - 批量订单操作
    - 订单历史记录
    - 策略级订单分组
    - 订单事件发布
    
    Usage:
        >>> oms = OrderManager(gateway)
        >>> 
        >>> # 创建订单
        >>> order = oms.create_order("600519.SH", Side.BUY, 100, price=1800.0)
        >>> 
        >>> # 提交订单
        >>> oms.submit_order(order.order_id)
        >>> 
        >>> # 查询订单
        >>> active = oms.get_active_orders()
        >>> filled = oms.get_filled_orders()
        >>> 
        >>> # 批量取消
        >>> oms.cancel_all_orders("600519.SH")
    """
    
    def __init__(
        self,
        gateway = None,
        event_engine: Optional[EventEngine] = None,
        max_orders_per_symbol: int = 100,
        order_timeout_minutes: int = 60,
        tenant_id: str = "",
        allowed_strategies: Optional[Set[str]] = None,
        authorizer: Optional[Authorizer] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize order manager.
        
        Args:
            gateway: Trading gateway for order execution
            event_engine: Event engine for publishing events
            max_orders_per_symbol: Maximum active orders per symbol
            order_timeout_minutes: Auto-cancel timeout for orders
        """
        self.gateway = gateway
        self.event_engine = event_engine
        self.max_orders_per_symbol = max_orders_per_symbol
        self.order_timeout = timedelta(minutes=order_timeout_minutes)
        self.tenant_id = tenant_id
        self.allowed_strategies = allowed_strategies
        self.authorizer = authorizer
        self.audit_logger = audit_logger
        
        # Order storage
        self._orders: Dict[str, ManagedOrder] = {}
        self._order_seq = 0
        
        # Indexes for fast lookup
        self._orders_by_symbol: Dict[str, Set[str]] = defaultdict(set)
        self._orders_by_strategy: Dict[str, Set[str]] = defaultdict(set)
        self._orders_by_status: Dict[OrderStatusEnum, Set[str]] = defaultdict(set)
        
        # Trade records
        self._trades: List[TradeInfo] = []
        self._trades_by_order: Dict[str, List[TradeInfo]] = defaultdict(list)
        
        # Callbacks
        self._order_callbacks: List[Callable[[ManagedOrder, OrderEvent], None]] = []
        self._trade_callbacks: List[Callable[[TradeInfo], None]] = []
    
    # ---------------------------------------------------------------------------
    # Order Creation
    # ---------------------------------------------------------------------------
    
    def create_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderTypeEnum = OrderTypeEnum.LIMIT,
        strategy_id: str = "",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None,
        tenant_id: str = "",
        subject: Optional[Subject] = None,
    ) -> ManagedOrder:
        """
        Create a new order (not submitted yet).
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Order quantity
            price: Limit price (None for market orders)
            order_type: Order type
            strategy_id: Associated strategy ID
            stop_loss: Stop loss price
            take_profit: Take profit price
            tags: Custom tags
            
        Returns:
            ManagedOrder instance
        """
        # Validate
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if order_type == OrderTypeEnum.LIMIT and price is None:
            raise ValueError("Limit order requires price")
        
        # Authorization & isolation
        scope = ResourceScope(tenant_id=tenant_id or self.tenant_id, strategy_id=strategy_id)
        self._authorize(Permission.ORDER_CREATE, subject, scope)
        self._check_isolation(strategy_id, tenant_id)

        # Check order limit
        active_count = len([
            oid for oid in self._orders_by_symbol[symbol]
            if self._orders[oid].is_active
        ])
        if active_count >= self.max_orders_per_symbol:
            raise ValueError(f"Max orders reached for {symbol}: {active_count}")
        
        # Generate order ID
        self._order_seq += 1
        order_id = f"OMS-{self._order_seq:08d}"
        
        # Create order
        order = ManagedOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            strategy_id=strategy_id,
            tenant_id=tenant_id or self.tenant_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
            tags=tags or {}
        )
        
        # Store and index
        self._orders[order_id] = order
        self._orders_by_symbol[symbol].add(order_id)
        self._orders_by_status[OrderStatusEnum.PENDING].add(order_id)
        if strategy_id:
            self._orders_by_strategy[strategy_id].add(order_id)
        
        logger.info(
            "Order created",
            order_id=order_id,
            symbol=symbol,
            side=side.value,
            quantity=quantity,
            price=price
        )
        self._audit("order.create", order, result="ok", subject=subject)
        
        self._publish_order_event(order, OrderEvent.CREATED)
        return order
    
    def create_bracket_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        strategy_id: str = "",
        tenant_id: str = "",
        subject: Optional[Subject] = None,
    ) -> List[ManagedOrder]:
        """
        Create bracket order (entry + stop loss + take profit).
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Order quantity
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            strategy_id: Associated strategy ID
            
        Returns:
            List of [entry_order, stop_loss_order, take_profit_order]
        """
        # Entry order
        entry = self.create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=entry_price,
            order_type=OrderTypeEnum.LIMIT,
            strategy_id=strategy_id,
            tags={"bracket": "entry"},
            tenant_id=tenant_id,
            subject=subject,
        )
        
        # Stop loss order (opposite side)
        sl_side = Side.SELL if side == Side.BUY else Side.BUY
        sl_order = self.create_order(
            symbol=symbol,
            side=sl_side,
            quantity=quantity,
            price=stop_loss,
            order_type=OrderTypeEnum.STOP,
            strategy_id=strategy_id,
            tags={"bracket": "stop_loss", "parent": entry.order_id},
            tenant_id=tenant_id,
            subject=subject,
        )
        sl_order.parent_order_id = entry.order_id
        entry.child_order_ids.append(sl_order.order_id)
        
        # Take profit order (opposite side)
        tp_order = self.create_order(
            symbol=symbol,
            side=sl_side,
            quantity=quantity,
            price=take_profit,
            order_type=OrderTypeEnum.LIMIT,
            strategy_id=strategy_id,
            tags={"bracket": "take_profit", "parent": entry.order_id},
            tenant_id=tenant_id,
            subject=subject,
        )
        tp_order.parent_order_id = entry.order_id
        entry.child_order_ids.append(tp_order.order_id)
        
        return [entry, sl_order, tp_order]
    
    # ---------------------------------------------------------------------------
    # Order Submission
    # ---------------------------------------------------------------------------
    
    def submit_order(self, order_id: str, subject: Optional[Subject] = None) -> bool:
        """
        Submit order to gateway.
        
        Args:
            order_id: Order ID to submit
            
        Returns:
            True if submitted successfully
        """
        order = self._orders.get(order_id)
        if not order:
            logger.error("Order not found", order_id=order_id)
            return False
        
        if order.status != OrderStatusEnum.PENDING:
            logger.error("Order already submitted", order_id=order_id, status=order.status.value)
            return False
        
        try:
            self._authorize(Permission.ORDER_SUBMIT, subject, ResourceScope(
                tenant_id=order.tenant_id, strategy_id=order.strategy_id
            ))
            # Submit to gateway
            if self.gateway:
                broker_id = self.gateway._adapter.submit_order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=order.price,
                    order_type=order.order_type
                )
                order.broker_order_id = broker_id
            
            # Update status
            self._update_order_status(order, OrderStatusEnum.SUBMITTED)
            order.submit_time = datetime.now()
            
            logger.info("Order submitted", order_id=order_id)
            self._publish_order_event(order, OrderEvent.SUBMITTED)
            self._audit("order.submit", order, result="ok", subject=subject)
            return True
            
        except Exception as e:
            order.reject_reason = str(e)
            self._update_order_status(order, OrderStatusEnum.REJECTED)
            logger.error("Order submission failed", order_id=order_id, error=str(e))
            self._publish_order_event(order, OrderEvent.REJECTED)
            self._audit("order.submit", order, result="error", subject=subject, details={"error": str(e)})
            return False
    
    def submit_all_pending(self, symbol: Optional[str] = None, subject: Optional[Subject] = None) -> int:
        """
        Submit all pending orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            Number of orders submitted
        """
        count = 0
        for order_id in list(self._orders_by_status[OrderStatusEnum.PENDING]):
            order = self._orders[order_id]
            if symbol is None or order.symbol == symbol:
                if self.submit_order(order_id, subject=subject):
                    count += 1
        return count
    
    # ---------------------------------------------------------------------------
    # Order Cancellation
    # ---------------------------------------------------------------------------
    
    def cancel_order(self, order_id: str, reason: str = "", subject: Optional[Subject] = None) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID to cancel
            reason: Cancellation reason
            
        Returns:
            True if cancellation submitted
        """
        order = self._orders.get(order_id)
        if not order:
            logger.error("Order not found", order_id=order_id)
            return False
        
        if not order.is_active:
            logger.warning("Order not active", order_id=order_id, status=order.status.value)
            return False
        
        try:
            self._authorize(Permission.ORDER_CANCEL, subject, ResourceScope(
                tenant_id=order.tenant_id, strategy_id=order.strategy_id
            ))
            # Cancel via gateway
            if self.gateway and order.broker_order_id:
                self.gateway.cancel(order.broker_order_id)
            
            # Update status
            self._update_order_status(order, OrderStatusEnum.CANCELLED)
            order.reject_reason = reason
            
            # Cancel child orders
            for child_id in order.child_order_ids:
                self.cancel_order(child_id, "Parent cancelled")
            
            logger.info("Order cancelled", order_id=order_id, reason=reason)
            self._publish_order_event(order, OrderEvent.CANCELLED)
            self._audit("order.cancel", order, result="ok", subject=subject, details={"reason": reason})
            return True
            
        except Exception as e:
            logger.error("Order cancellation failed", order_id=order_id, error=str(e))
            self._audit("order.cancel", order, result="error", subject=subject, details={"error": str(e)})
            return False
    
    def cancel_all_orders(
        self,
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None,
        subject: Optional[Subject] = None,
    ) -> int:
        """
        Cancel all active orders.
        
        Args:
            symbol: Optional symbol filter
            strategy_id: Optional strategy filter
            
        Returns:
            Number of orders cancelled
        """
        count = 0
        
        # Get active orders
        active_ids = set()
        for status in (OrderStatusEnum.PENDING, OrderStatusEnum.SUBMITTED, OrderStatusEnum.PARTIAL):
            active_ids.update(self._orders_by_status[status])
        
        for order_id in active_ids:
            order = self._orders[order_id]
            
            # Apply filters
            if symbol and order.symbol != symbol:
                continue
            if strategy_id and order.strategy_id != strategy_id:
                continue
            
            if self.cancel_order(order_id, "Batch cancel", subject=subject):
                count += 1
        
        logger.info("Batch cancel completed", count=count, symbol=symbol, strategy_id=strategy_id)
        return count
    
    # ---------------------------------------------------------------------------
    # Order Updates
    # ---------------------------------------------------------------------------
    
    def on_order_fill(
        self,
        order_id: str,
        fill_price: float,
        fill_quantity: float,
        trade_id: str = ""
    ) -> None:
        """
        Handle order fill event.
        
        Args:
            order_id: Order ID
            fill_price: Fill price
            fill_quantity: Fill quantity
            trade_id: Trade ID from broker
        """
        order = self._orders.get(order_id)
        if not order:
            logger.warning("Fill for unknown order", order_id=order_id)
            return
        
        # Update fill info
        old_filled = order.filled_quantity
        total_value = old_filled * order.avg_fill_price + fill_quantity * fill_price
        order.filled_quantity += fill_quantity
        order.avg_fill_price = total_value / order.filled_quantity if order.filled_quantity > 0 else 0
        order.update_time = datetime.now()
        
        # Create trade record
        trade = TradeInfo(
            trade_id=trade_id or f"TRD-{len(self._trades)+1:08d}",
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=fill_quantity,
            timestamp=datetime.now()
        )
        self._trades.append(trade)
        self._trades_by_order[order_id].append(trade)
        
        # Invoke trade callbacks
        for callback in self._trade_callbacks:
            try:
                callback(trade)
            except Exception as e:
                logger.error("Trade callback error", error=str(e))
        
        # Update status
        if order.filled_quantity >= order.quantity:
            self._update_order_status(order, OrderStatusEnum.FILLED)
            order.fill_time = datetime.now()
            self._publish_order_event(order, OrderEvent.FILLED)
            self._audit("order.fill", order, result="filled", details={"trade_id": trade.trade_id})
            logger.info(
                "Order filled",
                order_id=order_id,
                symbol=order.symbol,
                quantity=order.quantity,
                avg_price=order.avg_fill_price
            )
        else:
            self._update_order_status(order, OrderStatusEnum.PARTIAL)
            self._publish_order_event(order, OrderEvent.PARTIAL_FILL)
            self._audit("order.fill.partial", order, result="partial", details={"trade_id": trade.trade_id})
            logger.info(
                "Order partially filled",
                order_id=order_id,
                filled=order.filled_quantity,
                remaining=order.remaining
            )
    
    def _update_order_status(self, order: ManagedOrder, new_status: OrderStatusEnum) -> None:
        """Update order status and indexes."""
        old_status = order.status
        
        # Update indexes
        self._orders_by_status[old_status].discard(order.order_id)
        self._orders_by_status[new_status].add(order.order_id)
        
        order.status = new_status
        order.update_time = datetime.now()
    
    # ---------------------------------------------------------------------------
    # Queries
    # ---------------------------------------------------------------------------
    
    def get_order(self, order_id: str) -> Optional[ManagedOrder]:
        """Get order by ID."""
        return self._orders.get(order_id)
    
    def get_orders(
        self,
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None,
        status: Optional[OrderStatusEnum] = None,
        side: Optional[Side] = None
    ) -> List[ManagedOrder]:
        """
        Get orders with optional filters.
        
        Args:
            symbol: Filter by symbol
            strategy_id: Filter by strategy
            status: Filter by status
            side: Filter by side
            
        Returns:
            List of matching orders
        """
        result = []
        
        # Start with appropriate index
        if status:
            order_ids = self._orders_by_status[status]
        elif symbol:
            order_ids = self._orders_by_symbol[symbol]
        elif strategy_id:
            order_ids = self._orders_by_strategy[strategy_id]
        else:
            order_ids = self._orders.keys()
        
        for order_id in order_ids:
            order = self._orders.get(order_id)
            if not order:
                continue
            
            # Apply filters
            if symbol and order.symbol != symbol:
                continue
            if strategy_id and order.strategy_id != strategy_id:
                continue
            if status and order.status != status:
                continue
            if side and order.side != side:
                continue
            
            result.append(order)
        
        return result
    
    def get_active_orders(self, symbol: Optional[str] = None) -> List[ManagedOrder]:
        """Get all active orders."""
        active = []
        for status in (OrderStatusEnum.PENDING, OrderStatusEnum.SUBMITTED, OrderStatusEnum.PARTIAL):
            active.extend(self.get_orders(symbol=symbol, status=status))
        return active
    
    def get_filled_orders(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[ManagedOrder]:
        """Get filled orders with optional time filter."""
        orders = self.get_orders(symbol=symbol, status=OrderStatusEnum.FILLED)
        
        if start_time:
            orders = [o for o in orders if o.fill_time and o.fill_time >= start_time]
        if end_time:
            orders = [o for o in orders if o.fill_time and o.fill_time <= end_time]
        
        return orders
    
    def get_order_history(self, limit: int = 100) -> List[ManagedOrder]:
        """Get recent order history."""
        orders = sorted(
            self._orders.values(),
            key=lambda o: o.create_time,
            reverse=True
        )
        return orders[:limit]
    
    def get_trades(
        self,
        order_id: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> List[TradeInfo]:
        """Get trades with optional filters."""
        if order_id:
            return self._trades_by_order.get(order_id, [])
        
        if symbol:
            return [t for t in self._trades if t.symbol == symbol]
        
        return self._trades.copy()
    
    # ---------------------------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get order statistics."""
        stats = {
            "total_orders": len(self._orders),
            "total_trades": len(self._trades),
            "by_status": {},
            "by_symbol": {},
            "by_side": {"buy": 0, "sell": 0},
            "total_value": 0.0,
            "filled_value": 0.0
        }
        
        for status in OrderStatusEnum:
            stats["by_status"][status.value] = len(self._orders_by_status[status])
        
        for symbol, order_ids in self._orders_by_symbol.items():
            stats["by_symbol"][symbol] = len(order_ids)
        
        for order in self._orders.values():
            stats["by_side"][order.side.value] += 1
            stats["total_value"] += order.value
            stats["filled_value"] += order.filled_value
        
        return stats
    
    # ---------------------------------------------------------------------------
    # Callbacks & Events
    # ---------------------------------------------------------------------------
    
    def on_order_update(self, callback: Callable[[ManagedOrder, OrderEvent], None]) -> None:
        """Register order update callback."""
        self._order_callbacks.append(callback)
    
    def on_trade(self, callback: Callable[[TradeInfo], None]) -> None:
        """Register trade callback."""
        self._trade_callbacks.append(callback)
    
    def _publish_order_event(self, order: ManagedOrder, event_type: OrderEvent) -> None:
        """Publish order event."""
        # Invoke callbacks
        for callback in self._order_callbacks:
            try:
                callback(order, event_type)
            except Exception as e:
                logger.error("Order callback error", error=str(e))
        
        # Publish to event engine
        if self.event_engine:
            self.event_engine.put(Event(
                event_type.value,
                {
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "status": order.status.value,
                    "quantity": order.quantity,
                    "filled": order.filled_quantity
                }
            ))

    def _authorize(self, permission: str, subject: Optional[Subject], scope: ResourceScope) -> None:
        if self.authorizer:
            self.authorizer.require(permission, subject, scope)

    def _check_isolation(self, strategy_id: str, tenant_id: str) -> None:
        if self.tenant_id and tenant_id and tenant_id != self.tenant_id:
            raise PermissionError("Tenant isolation violation")
        if self.allowed_strategies and strategy_id and strategy_id not in self.allowed_strategies:
            raise PermissionError("Strategy isolation violation")

    def _audit(
        self,
        action: str,
        order: ManagedOrder,
        *,
        result: str,
        subject: Optional[Subject] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        actor = subject.subject_id if subject else "system"
        audit_event(
            self.audit_logger,
            actor=actor,
            action=action,
            resource=f"order:{order.order_id}",
            result=result,
            details={
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": order.quantity,
                "status": order.status.value,
                **(details or {}),
            },
        )
    
    # ---------------------------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------------------------
    
    def check_timeouts(self) -> int:
        """
        Check and cancel timed out orders.
        
        Returns:
            Number of orders cancelled
        """
        now = datetime.now()
        count = 0
        
        for order_id in list(self._orders_by_status[OrderStatusEnum.SUBMITTED]):
            order = self._orders[order_id]
            if order.submit_time and (now - order.submit_time) > self.order_timeout:
                if self.cancel_order(order_id, "Timeout"):
                    count += 1
        
        return count
    
    def clear_history(self, before: datetime) -> int:
        """
        Clear old order history.
        
        Args:
            before: Clear orders created before this time
            
        Returns:
            Number of orders cleared
        """
        count = 0
        orders_to_remove = []
        
        for order_id, order in self._orders.items():
            if order.create_time < before and not order.is_active:
                orders_to_remove.append(order_id)
        
        for order_id in orders_to_remove:
            order = self._orders[order_id]
            
            # Remove from indexes
            self._orders_by_symbol[order.symbol].discard(order_id)
            self._orders_by_status[order.status].discard(order_id)
            if order.strategy_id:
                self._orders_by_strategy[order.strategy_id].discard(order_id)
            
            # Remove trades
            if order_id in self._trades_by_order:
                del self._trades_by_order[order_id]
            
            del self._orders[order_id]
            count += 1
        
        logger.info("Order history cleared", count=count)
        return count

    # ---------------------------------------------------------------------------
    # Snapshot / Restore
    # ---------------------------------------------------------------------------

    def snapshot_state(self) -> Dict[str, Any]:
        """Snapshot OMS state for disaster recovery."""
        return {
            "order_seq": self._order_seq,
            "tenant_id": self.tenant_id,
            "orders": [self._serialize_order(o) for o in self._orders.values()],
            "trades": [self._serialize_trade(t) for t in self._trades],
        }

    def restore_state(self, payload: Dict[str, Any]) -> None:
        """Restore OMS state from snapshot."""
        self._orders.clear()
        self._orders_by_symbol.clear()
        self._orders_by_strategy.clear()
        self._orders_by_status.clear()
        self._trades.clear()
        self._trades_by_order.clear()

        self._order_seq = int(payload.get("order_seq", 0))
        self.tenant_id = payload.get("tenant_id", self.tenant_id)

        for data in payload.get("orders", []):
            order = self._deserialize_order(data)
            self._orders[order.order_id] = order
            self._orders_by_symbol[order.symbol].add(order.order_id)
            if order.strategy_id:
                self._orders_by_strategy[order.strategy_id].add(order.order_id)
            self._orders_by_status[order.status].add(order.order_id)

        for data in payload.get("trades", []):
            trade = self._deserialize_trade(data)
            self._trades.append(trade)
            self._trades_by_order[trade.order_id].append(trade)

    @staticmethod
    def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    def _serialize_order(self, order: ManagedOrder) -> Dict[str, Any]:
        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "price": order.price,
            "quantity": order.quantity,
            "filled_quantity": order.filled_quantity,
            "avg_fill_price": order.avg_fill_price,
            "status": order.status.value,
            "create_time": self._serialize_datetime(order.create_time),
            "submit_time": self._serialize_datetime(order.submit_time),
            "update_time": self._serialize_datetime(order.update_time),
            "fill_time": self._serialize_datetime(order.fill_time),
            "strategy_id": order.strategy_id,
            "tenant_id": order.tenant_id,
            "parent_order_id": order.parent_order_id,
            "child_order_ids": list(order.child_order_ids),
            "tags": dict(order.tags),
            "stop_loss": order.stop_loss,
            "take_profit": order.take_profit,
            "broker_order_id": order.broker_order_id,
            "reject_reason": order.reject_reason,
        }

    def _deserialize_order(self, data: Dict[str, Any]) -> ManagedOrder:
        order = ManagedOrder(
            order_id=data["order_id"],
            symbol=data["symbol"],
            side=Side(data["side"]),
            order_type=OrderTypeEnum(data["order_type"]),
            price=data.get("price"),
            quantity=float(data.get("quantity", 0)),
            filled_quantity=float(data.get("filled_quantity", 0)),
            avg_fill_price=float(data.get("avg_fill_price", 0)),
            status=OrderStatusEnum(data.get("status", OrderStatusEnum.PENDING.value)),
            strategy_id=data.get("strategy_id", ""),
            tenant_id=data.get("tenant_id", ""),
            parent_order_id=data.get("parent_order_id", ""),
            child_order_ids=list(data.get("child_order_ids", [])),
            tags=dict(data.get("tags", {})),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            broker_order_id=data.get("broker_order_id", ""),
            reject_reason=data.get("reject_reason", ""),
        )
        order.create_time = self._parse_dt(data.get("create_time"))
        order.submit_time = self._parse_dt(data.get("submit_time"))
        order.update_time = self._parse_dt(data.get("update_time"))
        order.fill_time = self._parse_dt(data.get("fill_time"))
        return order

    def _serialize_trade(self, trade: TradeInfo) -> Dict[str, Any]:
        return {
            "trade_id": trade.trade_id,
            "order_id": trade.order_id,
            "symbol": trade.symbol,
            "side": trade.side.value,
            "price": trade.price,
            "quantity": trade.quantity,
            "commission": trade.commission,
            "timestamp": self._serialize_datetime(trade.timestamp),
        }

    def _deserialize_trade(self, data: Dict[str, Any]) -> TradeInfo:
        trade = TradeInfo(
            trade_id=data["trade_id"],
            order_id=data["order_id"],
            symbol=data["symbol"],
            side=Side(data["side"]),
            price=float(data.get("price", 0)),
            quantity=float(data.get("quantity", 0)),
            commission=float(data.get("commission", 0)),
            timestamp=self._parse_dt(data.get("timestamp")),
        )
        return trade

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", ""))
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    'OrderManager',
    'ManagedOrder',
    'OrderEvent',
]
