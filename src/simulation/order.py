"""
Order Management Module

Defines order, trade, and status enumerations for simulation matching engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"          # 挂单中
    PARTIAL = "partial"          # 部分成交
    FILLED = "filled"            # 完全成交
    CANCELLED = "cancelled"      # 已撤单
    REJECTED = "rejected"        # 已拒绝


class OrderType(Enum):
    """订单类型枚举"""
    MARKET = "market"            # 市价单
    LIMIT = "limit"              # 限价单
    STOP = "stop"                # 止损单


class OrderDirection(Enum):
    """订单方向枚举"""
    BUY = "buy"                  # 买入
    SELL = "sell"                # 卖出


@dataclass
class Order:
    """
    订单对象
    
    Attributes:
        order_id: 唯一订单ID
        symbol: 标的代码（如 "600519.SH"）
        direction: 买卖方向
        order_type: 订单类型
        quantity: 订单数量
        price: 限价单价格（市价单为 None）
        stop_price: 止损触发价格（止损单专用）
        status: 订单状态
        filled_qty: 已成交数量
        avg_fill_price: 平均成交价
        timestamp: 订单创建时间
        strategy_id: 策略标识（可选）
        fees: 累计手续费
    """
    order_id: str
    symbol: str
    direction: OrderDirection
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    
    # 状态字段
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 元数据
    strategy_id: Optional[str] = None
    fees: float = 0.0
    
    @property
    def remaining_qty(self) -> float:
        """剩余未成交数量"""
        return self.quantity - self.filled_qty
    
    @property
    def is_buy(self) -> bool:
        """是否为买单"""
        return self.direction == OrderDirection.BUY
    
    @property
    def is_sell(self) -> bool:
        """是否为卖单"""
        return self.direction == OrderDirection.SELL
    
    @property
    def is_market(self) -> bool:
        """是否为市价单"""
        return self.order_type == OrderType.MARKET
    
    @property
    def is_limit(self) -> bool:
        """是否为限价单"""
        return self.order_type == OrderType.LIMIT
    
    @property
    def is_stop(self) -> bool:
        """是否为止损单"""
        return self.order_type == OrderType.STOP
    
    @property
    def is_active(self) -> bool:
        """订单是否仍活跃（未完全成交或撤单）"""
        return self.status in (OrderStatus.PENDING, OrderStatus.PARTIAL)
    
    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"Order(id={self.order_id}, {self.symbol}, "
            f"{self.direction.value} {self.order_type.value}, "
            f"qty={self.quantity}, price={self.price}, "
            f"status={self.status.value}, filled={self.filled_qty})"
        )


@dataclass
class Trade:
    """
    成交记录
    
    Attributes:
        trade_id: 唯一成交ID
        order_id: 关联订单ID
        symbol: 标的代码
        direction: 买卖方向
        quantity: 成交数量
        price: 成交价格
        timestamp: 成交时间
        fees: 本次成交手续费
        strategy_id: 策略标识（可选）
    """
    trade_id: str
    order_id: str
    symbol: str
    direction: OrderDirection
    quantity: float
    price: float
    timestamp: datetime = field(default_factory=datetime.now)
    fees: float = 0.0
    strategy_id: Optional[str] = None
    
    @property
    def value(self) -> float:
        """成交金额（不含手续费）"""
        return self.quantity * self.price
    
    @property
    def total_cost(self) -> float:
        """总成本（含手续费）"""
        return self.value + self.fees
    
    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"Trade(id={self.trade_id}, order={self.order_id}, "
            f"{self.symbol}, {self.direction.value}, "
            f"qty={self.quantity}, price={self.price:.4f}, "
            f"value={self.value:.2f})"
        )
