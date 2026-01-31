"""
Slippage Models Module

Provides various slippage calculation models for realistic order execution simulation.
"""
from __future__ import annotations

from typing import Protocol
import pandas as pd

from .order import Order, OrderDirection


class SlippageModel(Protocol):
    """
    滑点模型协议
    
    所有滑点模型必须实现 calculate_slippage 方法。
    """
    
    def calculate_slippage(self, order: Order, market_price: float, **kwargs) -> float:
        """
        计算滑点后的实际成交价格
        
        Args:
            order: 订单对象
            market_price: 当前市场价格
            **kwargs: 额外参数（如成交量数据）
            
        Returns:
            考虑滑点后的实际成交价格
        """
        ...


class FixedSlippage:
    """
    固定滑点模型（适用于高流动性标的）
    
    买入时价格上滑，卖出时价格下滑固定跳数。
    
    Example:
        >>> slippage = FixedSlippage(slippage_ticks=1, tick_size=0.01)
        >>> # 买入100元股票，滑点1跳(0.01元)，实际成交100.01元
        >>> slippage.calculate_slippage(buy_order, 100.0)
        100.01
    """
    
    def __init__(self, slippage_ticks: int = 1, tick_size: float = 0.01):
        """
        初始化固定滑点模型
        
        Args:
            slippage_ticks: 滑点跳数（默认1跳）
            tick_size: 最小价格变动单位（默认0.01元，适用于A股）
        """
        self.slippage_ticks = slippage_ticks
        self.tick_size = tick_size
    
    def calculate_slippage(self, order: Order, market_price: float, **kwargs) -> float:
        """
        计算固定滑点后的成交价格
        
        Args:
            order: 订单对象
            market_price: 当前市场价格
            
        Returns:
            滑点后的成交价格
        """
        slippage = self.slippage_ticks * self.tick_size
        
        if order.direction == OrderDirection.BUY:
            # 买入价格上滑（不利）
            return market_price + slippage
        else:
            # 卖出价格下滑（不利）
            return market_price - slippage


class PercentSlippage:
    """
    比例滑点模型（适用于一般流动性标的）
    
    按成交价格的固定百分比计算滑点。
    
    Example:
        >>> slippage = PercentSlippage(slippage_percent=0.001)  # 0.1%
        >>> # 买入100元股票，滑点0.1%，实际成交100.10元
        >>> slippage.calculate_slippage(buy_order, 100.0)
        100.10
    """
    
    def __init__(self, slippage_percent: float = 0.001):
        """
        初始化比例滑点模型
        
        Args:
            slippage_percent: 滑点百分比（默认0.001 = 0.1%）
        """
        self.slippage_percent = slippage_percent
    
    def calculate_slippage(self, order: Order, market_price: float, **kwargs) -> float:
        """
        计算比例滑点后的成交价格
        
        Args:
            order: 订单对象
            market_price: 当前市场价格
            
        Returns:
            滑点后的成交价格
        """
        slippage = market_price * self.slippage_percent
        
        if order.direction == OrderDirection.BUY:
            return market_price + slippage
        else:
            return market_price - slippage


class VolumeShareSlippage:
    """
    市场冲击模型（适用于大单交易）
    
    基于 Almgren-Chriss 线性市场冲击模型：
    滑点 = price_impact * (order_qty / avg_volume)
    
    订单量越大，占成交量比例越高，市场冲击越大。
    
    Example:
        >>> slippage = VolumeShareSlippage(price_impact=0.1)
        >>> # 买入1000手，平均成交量5000手
        >>> # 订单占比 = 1000/5000 = 0.2
        >>> # 滑点 = 0.1 * 0.2 = 2%
        >>> slippage.calculate_slippage(buy_order, 100.0, avg_volume=5000)
        102.0
    """
    
    def __init__(self, price_impact: float = 0.1):
        """
        初始化市场冲击模型
        
        Args:
            price_impact: 价格冲击系数（默认0.1）
                         建议范围：0.05-0.2
                         - 0.05: 高流动性市场（沪深300成分股）
                         - 0.1:  一般流动性市场（中盘股）
                         - 0.2:  低流动性市场（小盘股）
        """
        self.price_impact = price_impact
    
    def calculate_slippage(self, order: Order, market_price: float, **kwargs) -> float:
        """
        计算市场冲击滑点后的成交价格
        
        Args:
            order: 订单对象
            market_price: 当前市场价格
            **kwargs: 必须包含 'avg_volume' (平均成交量)
            
        Returns:
            滑点后的成交价格
            
        Raises:
            ValueError: 如果未提供 avg_volume 参数
        """
        avg_volume = kwargs.get("avg_volume")
        if avg_volume is None:
            raise ValueError("VolumeShareSlippage requires 'avg_volume' parameter")
        
        if avg_volume <= 0:
            # 避免除零错误，默认使用5%滑点
            slippage_percent = 0.05
        else:
            # 计算订单占成交量比例
            volume_share = order.quantity / avg_volume
            # 限制最大冲击为20%（避免极端情况）
            volume_share = min(volume_share, 1.0)
            # 线性冲击模型
            slippage_percent = self.price_impact * volume_share
        
        slippage = market_price * slippage_percent
        
        if order.direction == OrderDirection.BUY:
            return market_price + slippage
        else:
            return market_price - slippage


class SquareRootImpactSlippage:
    """
    Square-root market impact model.

    slippage_percent = impact_coef * sqrt(order_qty / avg_volume)
    """

    def __init__(self, impact_coef: float = 0.1):
        self.impact_coef = impact_coef

    def calculate_slippage(self, order: Order, market_price: float, **kwargs) -> float:
        avg_volume = kwargs.get("avg_volume")
        if avg_volume is None:
            raise ValueError("SquareRootImpactSlippage requires 'avg_volume' parameter")
        if avg_volume <= 0:
            slippage_percent = 0.05
        else:
            volume_share = order.quantity / avg_volume
            volume_share = min(max(volume_share, 0.0), 1.0)
            slippage_percent = self.impact_coef * (volume_share ** 0.5)
        slippage = market_price * slippage_percent
        if order.direction == OrderDirection.BUY:
            return market_price + slippage
        else:
            return market_price - slippage


class NoSlippage:
    """
    零滑点模型（理想化场景，用于测试）
    
    直接按市场价格成交，无滑点。
    """
    
    def calculate_slippage(self, order: Order, market_price: float, **kwargs) -> float:
        """返回原始市场价格（无滑点）"""
        return market_price
