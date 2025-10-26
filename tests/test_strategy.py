"""
测试策略模块 (src/strategy/*)
覆盖: template (策略模板基类)
"""
import pytest
from datetime import datetime
import pandas as pd
import numpy as np

from src.strategy.template import (
    StrategyTemplate, Context, BacktraderContext,
    Position, Account, build_bt_strategy
)
from src.core.objects import Direction, OrderType, BarData


class TestStrategyComponents:
    """测试策略组件"""
    
    def test_strategy_template_protocol_exists(self):
        """测试StrategyTemplate协议存在"""
        assert StrategyTemplate is not None
    
    def test_context_protocol_exists(self):
        """测试Context协议存在"""
        assert Context is not None
    
    def test_backtrader_context_exists(self):
        """测试BacktraderContext类存在"""
        assert BacktraderContext is not None
    
    def test_position_class_exists(self):
        """测试Position类存在"""
        assert Position is not None
    
    def test_account_class_exists(self):
        """测试Account类存在"""
        assert Account is not None
    
    def test_build_bt_strategy_exists(self):
        """测试build_bt_strategy函数存在"""
        assert callable(build_bt_strategy)


class TestPositionClass:
    """测试Position类"""
    
    def test_position_creation(self):
        """测试Position创建"""
        position = Position(
            symbol="600519.SH",
            size=100.0,  # 使用size而不是direction和volume
            avg_price=1000.0
        )
        
        assert position.symbol == "600519.SH"
        assert position.size == 100.0
        assert position.avg_price == 1000.0


class TestAccountClass:
    """测试Account类"""
    
    def test_account_creation(self):
        """测试Account创建"""
        account = Account(
            cash=100000.0,
            total_value=100000.0  # 使用total_value而不是frozen
        )
        
        assert account.cash == 100000.0
        assert account.total_value == 100000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
