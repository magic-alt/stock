"""
测试策略模块 (src/core/strategy_base.py)
覆盖: BaseStrategy (统一策略基类)

V3.1.0 更新: 使用 core/strategy_base.py 替代废弃的 strategy/template.py
"""
import pytest
from datetime import datetime
import pandas as pd
import numpy as np

# V3.1.0: 使用统一的策略基类和接口
from src.core.strategy_base import BaseStrategy, BacktraderStrategyAdapter
from src.core.interfaces import (
    BarData, PositionInfo, AccountInfo, StrategyContext,
    Side, OrderTypeEnum
)
from src.core.objects import Direction, OrderType


class TestStrategyComponents:
    """测试策略组件"""
    
    def test_base_strategy_exists(self):
        """测试BaseStrategy基类存在"""
        assert BaseStrategy is not None
    
    def test_strategy_context_exists(self):
        """测试StrategyContext接口存在"""
        assert StrategyContext is not None
    
    def test_backtrader_adapter_exists(self):
        """测试BacktraderStrategyAdapter类存在"""
        assert BacktraderStrategyAdapter is not None
    
    def test_position_info_exists(self):
        """测试PositionInfo类存在"""
        assert PositionInfo is not None
    
    def test_account_info_exists(self):
        """测试AccountInfo类存在"""
        assert AccountInfo is not None
    
    def test_bar_data_exists(self):
        """测试BarData类存在"""
        assert BarData is not None


class TestPositionInfo:
    """测试PositionInfo类"""
    
    def test_position_creation(self):
        """测试PositionInfo创建"""
        position = PositionInfo(
            symbol="600519.SH",
            size=100.0,
            avg_price=1000.0
        )
        
        assert position.symbol == "600519.SH"
        assert position.size == 100.0
        assert position.avg_price == 1000.0
    
    def test_position_is_long(self):
        """测试多头仓位判断"""
        position = PositionInfo(symbol="600519.SH", size=100.0, avg_price=1000.0)
        assert position.is_long == True
        assert position.is_short == False
        assert position.is_flat == False
    
    def test_position_is_short(self):
        """测试空头仓位判断"""
        position = PositionInfo(symbol="600519.SH", size=-100.0, avg_price=1000.0)
        assert position.is_long == False
        assert position.is_short == True
        assert position.is_flat == False
    
    def test_position_is_flat(self):
        """测试空仓判断"""
        position = PositionInfo(symbol="600519.SH", size=0.0, avg_price=1000.0)
        assert position.is_long == False
        assert position.is_short == False
        assert position.is_flat == True


class TestAccountInfo:
    """测试AccountInfo类"""
    
    def test_account_creation(self):
        """测试AccountInfo创建"""
        account = AccountInfo(
            cash=100000.0,
            total_value=100000.0
        )
        
        assert account.cash == 100000.0
        assert account.total_value == 100000.0


class TestBarData:
    """测试BarData类"""
    
    def test_bar_data_creation(self):
        """测试BarData创建"""
        bar = BarData(
            symbol="600519.SH",
            timestamp=datetime(2024, 1, 1),
            open=100.0,
            high=110.0,
            low=95.0,
            close=105.0,
            volume=1000000.0
        )
        
        assert bar.symbol == "600519.SH"
        assert bar.open == 100.0
        assert bar.high == 110.0
        assert bar.low == 95.0
        assert bar.close == 105.0
        assert bar.volume == 1000000.0


class TestBaseStrategy:
    """测试BaseStrategy基类"""
    
    def test_strategy_params(self):
        """测试策略参数"""
        # 创建一个简单的测试策略
        class TestStrategy(BaseStrategy):
            params = {"period": 20, "multiplier": 2.0}
            
            def on_init(self, ctx):
                pass
            
            def on_bar(self, ctx, bar):
                pass
        
        strategy = TestStrategy()
        assert strategy.params["period"] == 20
        assert strategy.params["multiplier"] == 2.0
    
    def test_strategy_params_override(self):
        """测试策略参数覆盖"""
        class TestStrategy(BaseStrategy):
            params = {"period": 20}
            
            def on_init(self, ctx):
                pass
            
            def on_bar(self, ctx, bar):
                pass
        
        strategy = TestStrategy(period=30)
        assert strategy.params["period"] == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
