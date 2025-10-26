"""
Order Book Module

Manages pending orders with price-time priority using SortedList.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from sortedcontainers import SortedList

from .order import Order, OrderDirection, OrderType


class OrderBook:
    """
    订单簿管理
    
    使用 SortedList 实现价格-时间优先级排序：
    - 买单队列：按价格降序（最高价优先），相同价格按时间升序
    - 卖单队列：按价格升序（最低价优先），相同价格按时间升序
    
    Attributes:
        symbol: 标的代码
        bids: 买单队列（SortedList）
        asks: 卖单队列（SortedList）
        stop_orders: 止损单字典（order_id -> Order）
    """
    
    def __init__(self, symbol: str):
        """
        初始化订单簿
        
        Args:
            symbol: 标的代码（如 "600519.SH"）
        """
        self.symbol = symbol
        
        # 买单队列：价格降序（-price），时间升序
        # 例如: [100.5, 100.0, 99.5] 最高价100.5优先
        self.bids: SortedList[Order] = SortedList(key=lambda o: (-o.price, o.timestamp))
        
        # 卖单队列：价格升序（price），时间升序
        # 例如: [100.0, 100.5, 101.0] 最低价100.0优先
        self.asks: SortedList[Order] = SortedList(key=lambda o: (o.price, o.timestamp))
        
        # 止损单单独管理（未激活状态）
        self.stop_orders: Dict[str, Order] = {}
    
    def add_limit_order(self, order: Order) -> None:
        """
        添加限价单到订单簿
        
        Args:
            order: 限价订单对象
            
        Raises:
            ValueError: 如果订单类型不是限价单或价格为空
        """
        if order.order_type != OrderType.LIMIT:
            raise ValueError(f"Only LIMIT orders allowed, got {order.order_type}")
        if order.price is None:
            raise ValueError("LIMIT order must have a price")
        
        if order.direction == OrderDirection.BUY:
            self.bids.add(order)
        else:
            self.asks.add(order)
    
    def remove_limit_order(self, order: Order) -> bool:
        """
        从订单簿移除限价单
        
        Args:
            order: 要移除的订单
            
        Returns:
            是否成功移除
        """
        try:
            if order.direction == OrderDirection.BUY:
                self.bids.discard(order)
            else:
                self.asks.discard(order)
            return True
        except (ValueError, KeyError):
            return False
    
    def add_stop_order(self, order: Order) -> None:
        """
        添加止损单（挂起状态，不进入买卖队列）
        
        Args:
            order: 止损订单对象
            
        Raises:
            ValueError: 如果订单类型不是止损单或止损价为空
        """
        if order.order_type != OrderType.STOP:
            raise ValueError(f"Only STOP orders allowed, got {order.order_type}")
        if order.stop_price is None:
            raise ValueError("STOP order must have a stop_price")
        
        self.stop_orders[order.order_id] = order
    
    def remove_stop_order(self, order_id: str) -> Optional[Order]:
        """
        移除止损单
        
        Args:
            order_id: 订单ID
            
        Returns:
            被移除的订单，如果不存在返回 None
        """
        return self.stop_orders.pop(order_id, None)
    
    def check_stop_trigger(self, current_price: float) -> List[Order]:
        """
        检查止损单是否触发
        
        触发规则：
        - 买单止损：当前价 >= 止损价（突破上行）
        - 卖单止损：当前价 <= 止损价（跌破下行）
        
        Args:
            current_price: 当前市场价格
            
        Returns:
            触发的止损单列表
        """
        triggered: List[Order] = []
        
        for order_id, order in list(self.stop_orders.items()):
            should_trigger = False
            
            if order.direction == OrderDirection.BUY and current_price >= order.stop_price:
                # 买入止损单：价格突破止损价
                should_trigger = True
            elif order.direction == OrderDirection.SELL and current_price <= order.stop_price:
                # 卖出止损单：价格跌破止损价
                should_trigger = True
            
            if should_trigger:
                triggered.append(order)
                del self.stop_orders[order_id]
        
        return triggered
    
    def get_best_bid(self) -> Optional[float]:
        """
        获取最高买价（买一价）
        
        Returns:
            最高买价，如果买单队列为空返回 None
        """
        return self.bids[0].price if self.bids else None
    
    def get_best_ask(self) -> Optional[float]:
        """
        获取最低卖价（卖一价）
        
        Returns:
            最低卖价，如果卖单队列为空返回 None
        """
        return self.asks[0].price if self.asks else None
    
    def get_spread(self) -> Optional[float]:
        """
        获取买卖价差
        
        Returns:
            价差（ask - bid），如果任一侧为空返回 None
        """
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        if bid is not None and ask is not None:
            return ask - bid
        return None
    
    def get_mid_price(self) -> Optional[float]:
        """
        获取中间价（买一卖一的平均）
        
        Returns:
            中间价，如果任一侧为空返回 None
        """
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        if bid is not None and ask is not None:
            return (bid + ask) / 2.0
        return None
    
    def get_depth(self, levels: int = 5) -> Dict[str, List[tuple]]:
        """
        获取订单簿深度（盘口数据）
        
        Args:
            levels: 显示档位数量
            
        Returns:
            字典包含 'bids' 和 'asks'，每个是 [(price, qty), ...] 列表
        """
        bids_depth = [(o.price, o.remaining_qty) for o in self.bids[:levels]]
        asks_depth = [(o.price, o.remaining_qty) for o in self.asks[:levels]]
        
        return {
            "bids": bids_depth,
            "asks": asks_depth,
        }
    
    def clear(self) -> None:
        """清空订单簿（用于测试或重置）"""
        self.bids.clear()
        self.asks.clear()
        self.stop_orders.clear()
    
    def __repr__(self) -> str:
        """字符串表示"""
        bid = self.get_best_bid()
        ask = self.get_best_ask()
        return (
            f"OrderBook({self.symbol}, "
            f"bid={bid:.4f if bid else 'N/A'}, "
            f"ask={ask:.4f if ask else 'N/A'}, "
            f"bids={len(self.bids)}, asks={len(self.asks)}, "
            f"stops={len(self.stop_orders)})"
        )
