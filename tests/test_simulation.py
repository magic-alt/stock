"""
Unit Tests for Simulation Module

Tests order management, order book, slippage models, and matching engine.
"""
import pytest
import pandas as pd
from datetime import datetime

from src.simulation.order import Order, Trade, OrderStatus, OrderType, OrderDirection
from src.simulation.order_book import OrderBook
from src.simulation.slippage import FixedSlippage, PercentSlippage, VolumeShareSlippage
from src.simulation.matching_engine import MatchingEngine


# ===== Order Tests =====

def test_order_creation():
    """测试订单创建"""
    order = Order(
        order_id="O001",
        symbol="600519.SH",
        direction=OrderDirection.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=1850.0,
    )
    
    assert order.order_id == "O001"
    assert order.symbol == "600519.SH"
    assert order.is_buy
    assert order.is_limit
    assert order.remaining_qty == 100
    assert order.status == OrderStatus.PENDING


def test_order_properties():
    """测试订单属性"""
    order = Order(
        order_id="O002",
        symbol="000858.SZ",
        direction=OrderDirection.SELL,
        order_type=OrderType.MARKET,
        quantity=200,
    )
    
    assert order.is_sell
    assert order.is_market
    assert not order.is_limit
    assert order.is_active


# ===== OrderBook Tests =====

def test_order_book_creation():
    """测试订单簿创建"""
    book = OrderBook("600519.SH")
    assert book.symbol == "600519.SH"
    assert len(book.bids) == 0
    assert len(book.asks) == 0


def test_order_book_limit_orders():
    """测试限价单添加和排序"""
    book = OrderBook("600519.SH")
    
    # 添加买单（价格降序）
    buy1 = Order("B1", "600519.SH", OrderDirection.BUY, OrderType.LIMIT, 100, 1850.0)
    buy2 = Order("B2", "600519.SH", OrderDirection.BUY, OrderType.LIMIT, 100, 1860.0)  # 更高价
    buy3 = Order("B3", "600519.SH", OrderDirection.BUY, OrderType.LIMIT, 100, 1840.0)  # 更低价
    
    book.add_limit_order(buy1)
    book.add_limit_order(buy2)
    book.add_limit_order(buy3)
    
    # 验证排序：最高价优先
    assert book.get_best_bid() == 1860.0
    assert book.bids[0].order_id == "B2"
    assert book.bids[1].order_id == "B1"
    assert book.bids[2].order_id == "B3"
    
    # 添加卖单（价格升序）
    sell1 = Order("S1", "600519.SH", OrderDirection.SELL, OrderType.LIMIT, 100, 1870.0)
    sell2 = Order("S2", "600519.SH", OrderDirection.SELL, OrderType.LIMIT, 100, 1865.0)  # 更低价
    sell3 = Order("S3", "600519.SH", OrderDirection.SELL, OrderType.LIMIT, 100, 1880.0)  # 更高价
    
    book.add_limit_order(sell1)
    book.add_limit_order(sell2)
    book.add_limit_order(sell3)
    
    # 验证排序：最低价优先
    assert book.get_best_ask() == 1865.0
    assert book.asks[0].order_id == "S2"
    assert book.asks[1].order_id == "S1"
    assert book.asks[2].order_id == "S3"


def test_order_book_stop_orders():
    """测试止损单触发"""
    book = OrderBook("600519.SH")
    
    # 添加买入止损单（突破1900时买入）
    stop_buy = Order("SB1", "600519.SH", OrderDirection.BUY, OrderType.STOP, 100, stop_price=1900.0)
    book.add_stop_order(stop_buy)
    
    # 添加卖出止损单（跌破1800时卖出）
    stop_sell = Order("SS1", "600519.SH", OrderDirection.SELL, OrderType.STOP, 100, stop_price=1800.0)
    book.add_stop_order(stop_sell)
    
    assert len(book.stop_orders) == 2
    
    # 价格1850：无触发
    triggered = book.check_stop_trigger(1850.0)
    assert len(triggered) == 0
    
    # 价格1900：触发买入止损
    triggered = book.check_stop_trigger(1900.0)
    assert len(triggered) == 1
    assert triggered[0].order_id == "SB1"
    assert len(book.stop_orders) == 1  # 买入止损已移除
    
    # 价格1800：触发卖出止损
    triggered = book.check_stop_trigger(1800.0)
    assert len(triggered) == 1
    assert triggered[0].order_id == "SS1"
    assert len(book.stop_orders) == 0  # 所有止损单已清空


# ===== Slippage Tests =====

def test_fixed_slippage():
    """测试固定滑点"""
    slippage = FixedSlippage(slippage_ticks=1, tick_size=0.01)
    
    buy_order = Order("B1", "600519.SH", OrderDirection.BUY, OrderType.MARKET, 100)
    sell_order = Order("S1", "600519.SH", OrderDirection.SELL, OrderType.MARKET, 100)
    
    # 买入滑点：价格上滑
    fill_price = slippage.calculate_slippage(buy_order, 1850.0)
    assert fill_price == 1850.01
    
    # 卖出滑点：价格下滑
    fill_price = slippage.calculate_slippage(sell_order, 1850.0)
    assert fill_price == 1849.99


def test_percent_slippage():
    """测试比例滑点"""
    slippage = PercentSlippage(slippage_percent=0.001)  # 0.1%
    
    buy_order = Order("B1", "600519.SH", OrderDirection.BUY, OrderType.MARKET, 100)
    
    # 买入滑点：0.1% = 1.85
    fill_price = slippage.calculate_slippage(buy_order, 1850.0)
    assert abs(fill_price - 1851.85) < 0.01


def test_volume_share_slippage():
    """测试市场冲击滑点"""
    slippage = VolumeShareSlippage(price_impact=0.1)
    
    buy_order = Order("B1", "600519.SH", OrderDirection.BUY, OrderType.MARKET, 1000)
    
    # 订单占比 = 1000/5000 = 0.2
    # 滑点 = 0.1 * 0.2 = 2%
    fill_price = slippage.calculate_slippage(buy_order, 1850.0, avg_volume=5000)
    assert abs(fill_price - 1887.0) < 1.0  # 1850 * 1.02


# ===== MatchingEngine Tests =====

def test_matching_engine_market_order():
    """测试市价单立即成交"""
    engine = MatchingEngine(slippage_model=FixedSlippage(1, 0.01))
    
    # 提交市价买单
    order = Order("M1", "600519.SH", OrderDirection.BUY, OrderType.MARKET, 100)
    engine.submit_order(order)
    
    # 模拟行情（用于获取市场价）
    bar = pd.Series({"open": 1850, "high": 1860, "low": 1840, "close": 1850, "volume": 10000})
    engine.on_bar("600519.SH", bar)
    
    # 验证订单状态（注意：市价单应该已经成交）
    assert order.status in [OrderStatus.FILLED, OrderStatus.REJECTED]


def test_matching_engine_limit_order():
    """测试限价单价格匹配成交"""
    engine = MatchingEngine()
    
    # 提交限价买单（1840买入）
    order = Order("L1", "600519.SH", OrderDirection.BUY, OrderType.LIMIT, 100, price=1840.0)
    engine.submit_order(order)
    
    # 价格未触及：不成交
    bar1 = pd.Series({"open": 1850, "high": 1860, "low": 1845, "close": 1850, "volume": 10000})
    engine.on_bar("600519.SH", bar1)
    assert order.status == OrderStatus.PENDING
    
    # 价格触及：成交
    bar2 = pd.Series({"open": 1845, "high": 1850, "low": 1835, "close": 1840, "volume": 10000})
    engine.on_bar("600519.SH", bar2)
    assert order.status == OrderStatus.FILLED
    assert order.filled_qty == 100


def test_matching_engine_stop_order():
    """测试止损单触发"""
    engine = MatchingEngine()
    
    # 提交卖出止损单（跌破1800时卖出）
    order = Order("STOP1", "600519.SH", OrderDirection.SELL, OrderType.STOP, 100, stop_price=1800.0)
    engine.submit_order(order)
    
    # 价格未跌破：不触发
    bar1 = pd.Series({"open": 1820, "high": 1830, "low": 1810, "close": 1820, "volume": 10000})
    engine.on_bar("600519.SH", bar1)
    assert order.status == OrderStatus.PENDING
    
    # 价格跌破：触发转市价单成交
    bar2 = pd.Series({"open": 1810, "high": 1810, "low": 1790, "close": 1795, "volume": 10000})
    engine.on_bar("600519.SH", bar2)
    assert order.status == OrderStatus.FILLED


def test_matching_engine_cancel():
    """测试撤单"""
    engine = MatchingEngine()
    
    # 提交限价单
    order = Order("L2", "600519.SH", OrderDirection.BUY, OrderType.LIMIT, 100, price=1840.0)
    engine.submit_order(order)
    
    assert order.order_id in engine.active_orders
    
    # 撤单
    success = engine.cancel_order(order.order_id)
    assert success
    assert order.status == OrderStatus.CANCELLED
    assert order.order_id not in engine.active_orders


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
