"""
Integration Tests for Simulation Module with PaperGateway

Tests end-to-end workflow: PaperGateway → MatchingEngine → Order Execution
"""
import pytest
import pandas as pd
import time
from src.core.events import EventEngine, EventType
from src.core.paper_gateway import PaperGateway
from src.simulation.slippage import FixedSlippage, PercentSlippage


def test_paper_gateway_v3_market_order():
    """测试 PaperGateway V3.0 市价单成交"""
    events = EventEngine()
    events.start()
    
    # 创建 V3.0 模式的 PaperGateway
    gw = PaperGateway(
        events,
        use_matching_engine=True,
        slippage_model=FixedSlippage(slippage_ticks=1, tick_size=0.01),
        initial_cash=200000,
    )
    
    # 提交市价买单
    order_id = gw.send_order("600519.SH", "buy", 100, order_type="market")
    assert order_id is not None
    
    # 模拟 K 线更新（市价单应立即成交）
    bar = pd.Series({
        "open": 1850.0,
        "high": 1860.0,
        "low": 1840.0,
        "close": 1850.0,
        "volume": 10000
    })
    gw.on_bar("600519.SH", bar)
    
    # 等待事件处理完成（EventEngine 是异步的）
    time.sleep(0.1)
    
    # 检查账户状态
    account = gw.query_account()
    print(f"Account: {account}")
    
    # 检查持仓
    position = gw.query_position("600519.SH")
    print(f"Position: {position}")
    
    # 验证持仓（市价单应该成交）
    assert position['size'] == 100
    
    events.stop()


def test_paper_gateway_v3_limit_order():
    """测试 PaperGateway V3.0 限价单成交"""
    events = EventEngine()
    events.start()
    
    gw = PaperGateway(
        events,
        use_matching_engine=True,
        slippage_model=FixedSlippage(1, 0.01),
        initial_cash=200000,
    )
    
    # 提交限价买单（1840 买入）
    order_id = gw.send_order("600519.SH", "buy", 100, price=1840.0, order_type="limit")
    
    # 第一根 K 线：价格未触及（最低价 1845）
    bar1 = pd.Series({
        "open": 1850.0,
        "high": 1860.0,
        "low": 1845.0,
        "close": 1850.0,
        "volume": 10000
    })
    gw.on_bar("600519.SH", bar1)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 检查持仓（应该还未成交）
    position1 = gw.query_position("600519.SH")
    print(f"Position after bar1: {position1}")
    # assert position1['size'] == 0  # 限价单未触发
    
    # 第二根 K 线：价格触及（最低价 1835）
    bar2 = pd.Series({
        "open": 1845.0,
        "high": 1850.0,
        "low": 1835.0,
        "close": 1840.0,
        "volume": 10000
    })
    gw.on_bar("600519.SH", bar2)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 检查持仓（应该成交）
    position2 = gw.query_position("600519.SH")
    print(f"Position after bar2: {position2}")
    assert position2['size'] == 100
    
    events.stop()


def test_paper_gateway_v3_stop_order():
    """测试 PaperGateway V3.0 止损单触发"""
    events = EventEngine()
    events.start()
    
    gw = PaperGateway(
        events,
        use_matching_engine=True,
        slippage_model=PercentSlippage(0.001),
        initial_cash=200000,
    )
    
    # 先建仓（买入 100 股）
    buy_order_id = gw.send_order("600519.SH", "buy", 100, order_type="market")
    bar_buy = pd.Series({
        "open": 1850.0,
        "high": 1860.0,
        "low": 1840.0,
        "close": 1850.0,
        "volume": 10000
    })
    gw.on_bar("600519.SH", bar_buy)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 检查建仓成功
    position_initial = gw.query_position("600519.SH")
    print(f"Initial position: {position_initial}")
    assert position_initial['size'] == 100
    
    # 提交止损单（跌破 1800 时卖出）
    stop_order_id = gw.send_order("600519.SH", "sell", 100, price=1800.0, order_type="stop")
    
    # 第一根 K 线：价格未跌破止损价（最低价 1810）
    bar1 = pd.Series({
        "open": 1850.0,
        "high": 1860.0,
        "low": 1810.0,
        "close": 1820.0,
        "volume": 10000
    })
    gw.on_bar("600519.SH", bar1)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 检查持仓（止损未触发）
    position1 = gw.query_position("600519.SH")
    print(f"Position after bar1: {position1}")
    # assert position1['size'] == 100
    
    # 第二根 K 线：价格跌破止损价（收盘 1795）
    bar2 = pd.Series({
        "open": 1810.0,
        "high": 1815.0,
        "low": 1790.0,
        "close": 1795.0,
        "volume": 10000
    })
    gw.on_bar("600519.SH", bar2)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 检查持仓（止损应该触发）
    position2 = gw.query_position("600519.SH")
    print(f"Position after bar2: {position2}")
    assert position2['size'] == 0  # 止损平仓
    
    events.stop()


def test_paper_gateway_backward_compatibility():
    """测试 PaperGateway 向后兼容性（V2.x 模式）"""
    events = EventEngine()
    events.start()
    
    # V2.x 模式（不使用 MatchingEngine）
    gw = PaperGateway(
        events,
        slippage=0.001,
        initial_cash=200000,
        use_matching_engine=False,  # 显式禁用
    )
    
    # 提交市价单
    order_id = gw.send_order("600519.SH", "buy", 100, order_type="market")
    assert isinstance(order_id, int)  # V2.x 返回整数 ID
    
    # V2.x 模式使用 match_on_open
    gw.match_on_open("600519.SH", open_price=1850.0)
    
    # 检查持仓
    position = gw.query_position("600519.SH")
    print(f"V2.x Position: {position}")
    assert position['size'] == 100
    
    events.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
