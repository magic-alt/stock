"""
Tests for Standardized Data Objects

Validates data object creation, validation, and serialization.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "e:/work/Project/stock")

import pytest
from datetime import datetime

from src.core.objects import (
    BarData, TickData, OrderData, TradeData, PositionData, AccountData,
    Direction, OrderType, OrderStatus, Exchange,
    parse_symbol, format_symbol, to_json
)


class TestEnums:
    """Test enum definitions."""
    
    def test_direction(self):
        """Test Direction enum."""
        assert Direction.LONG == "long"
        assert Direction.SHORT == "short"
        assert str(Direction.LONG) == "long"
    
    def test_order_type(self):
        """Test OrderType enum."""
        assert OrderType.MARKET == "market"
        assert OrderType.LIMIT == "limit"
    
    def test_order_status(self):
        """Test OrderStatus enum."""
        assert OrderStatus.PENDING == "pending"
        assert OrderStatus.FILLED == "filled"
    
    def test_exchange(self):
        """Test Exchange enum."""
        assert Exchange.SSE == "SSE"
        assert Exchange.SZSE == "SZSE"


class TestBarData:
    """Test BarData class."""
    
    def test_creation(self):
        """Test BarData creation."""
        bar = BarData(
            symbol="600519.SH",
            datetime=datetime(2024, 1, 1, 9, 30),
            exchange=Exchange.SSE,
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000000
        )
        
        assert bar.symbol == "600519.SH"
        assert bar.open == 100.0
        assert bar.high == 105.0
        assert bar.low == 98.0
        assert bar.close == 103.0
        assert bar.volume == 1000000
    
    def test_validation(self):
        """Test BarData validation."""
        # Should raise error if high < low
        with pytest.raises(ValueError):
            BarData(
                symbol="TEST",
                datetime=datetime.now(),
                open=100,
                high=95,  # Invalid: high < low
                low=98,
                close=97
            )
    
    def test_auto_correction(self):
        """Test automatic correction of invalid high/low."""
        bar = BarData(
            symbol="TEST",
            datetime=datetime.now(),
            open=100,
            high=99,  # Invalid: high < close
            low=95,
            close=102
        )
        
        # Should auto-correct high to >= close
        assert bar.high >= bar.close
        assert bar.low <= bar.close
    
    def test_serialization(self):
        """Test BarData serialization."""
        bar = BarData(
            symbol="600519.SH",
            datetime=datetime(2024, 1, 1),
            open=100.0,
            close=101.0,
            high=102.0,
            low=99.0,
            volume=1000000
        )
        
        # To dict
        data = bar.to_dict()
        assert data["symbol"] == "600519.SH"
        assert data["open"] == 100.0
        
        # From dict
        bar2 = BarData.from_dict(data)
        assert bar2.symbol == bar.symbol
        assert bar2.open == bar.open


class TestTickData:
    """Test TickData class."""
    
    def test_creation(self):
        """Test TickData creation."""
        tick = TickData(
            symbol="600519.SH",
            datetime=datetime.now(),
            last_price=100.0,
            bid_price_1=99.9,
            bid_volume_1=1000,
            ask_price_1=100.1,
            ask_volume_1=1000
        )
        
        assert tick.symbol == "600519.SH"
        assert tick.last_price == 100.0
        assert tick.bid_price_1 == 99.9
        assert tick.ask_price_1 == 100.1
    
    def test_mid_price(self):
        """Test mid price calculation."""
        tick = TickData(
            symbol="TEST",
            datetime=datetime.now(),
            last_price=100.0,
            bid_price_1=99.5,
            ask_price_1=100.5
        )
        
        assert tick.mid_price == 100.0
    
    def test_spread(self):
        """Test spread calculation."""
        tick = TickData(
            symbol="TEST",
            datetime=datetime.now(),
            bid_price_1=99.5,
            ask_price_1=100.5
        )
        
        assert tick.spread == 1.0


class TestOrderData:
    """Test OrderData class."""
    
    def test_creation(self):
        """Test OrderData creation."""
        order = OrderData(
            symbol="600519.SH",
            order_id="ORDER_001",
            direction=Direction.LONG,
            order_type=OrderType.LIMIT,
            price=100.0,
            volume=1000,
            status=OrderStatus.SUBMITTED
        )
        
        assert order.symbol == "600519.SH"
        assert order.direction == Direction.LONG
        assert order.volume == 1000
        assert order.remaining == 1000
    
    def test_remaining_calculation(self):
        """Test remaining quantity calculation."""
        order = OrderData(
            symbol="TEST",
            volume=1000,
            traded=300
        )
        
        assert order.remaining == 700
    
    def test_is_active(self):
        """Test is_active property."""
        order = OrderData(symbol="TEST", status=OrderStatus.SUBMITTED)
        assert order.is_active is True
        
        order.status = OrderStatus.FILLED
        assert order.is_active is False
        
        order.status = OrderStatus.CANCELLED
        assert order.is_active is False
    
    def test_serialization(self):
        """Test OrderData serialization."""
        order = OrderData(
            symbol="600519.SH",
            order_id="ORDER_001",
            direction=Direction.LONG,
            volume=1000
        )
        
        data = order.to_dict()
        assert data["symbol"] == "600519.SH"
        assert data["order_id"] == "ORDER_001"
        assert data["direction"] == "long"


class TestTradeData:
    """Test TradeData class."""
    
    def test_creation(self):
        """Test TradeData creation."""
        trade = TradeData(
            symbol="600519.SH",
            trade_id="TRADE_001",
            order_id="ORDER_001",
            direction=Direction.LONG,
            price=100.0,
            volume=500
        )
        
        assert trade.symbol == "600519.SH"
        assert trade.trade_id == "TRADE_001"
        assert trade.order_id == "ORDER_001"
        assert trade.volume == 500
    
    def test_serialization(self):
        """Test TradeData serialization."""
        trade = TradeData(
            symbol="TEST",
            trade_id="TRADE_001",
            direction=Direction.LONG,
            volume=100
        )
        
        data = trade.to_dict()
        assert data["trade_id"] == "TRADE_001"
        assert data["direction"] == "long"


class TestPositionData:
    """Test PositionData class."""
    
    def test_creation(self):
        """Test PositionData creation."""
        pos = PositionData(
            symbol="600519.SH",
            direction=Direction.LONG,
            volume=1000,
            frozen=200,
            price=100.0,
            cost=100500.0
        )
        
        assert pos.symbol == "600519.SH"
        assert pos.volume == 1000
        assert pos.available == 800
    
    def test_available_calculation(self):
        """Test available quantity calculation."""
        pos = PositionData(
            symbol="TEST",
            volume=1000,
            frozen=300
        )
        
        assert pos.available == 700


class TestAccountData:
    """Test AccountData class."""
    
    def test_creation(self):
        """Test AccountData creation."""
        account = AccountData(
            account_id="ACC_001",
            balance=100000.0,
            available=80000.0,
            frozen=20000.0,
            realized_pnl=5000.0,
            unrealized_pnl=2000.0
        )
        
        assert account.balance == 100000.0
        assert account.available == 80000.0
        assert account.total_value == 102000.0
    
    def test_total_value(self):
        """Test total value calculation."""
        account = AccountData(
            balance=100000.0,
            unrealized_pnl=5000.0
        )
        
        assert account.total_value == 105000.0
    
    def test_risk_ratio(self):
        """Test risk ratio calculation."""
        account = AccountData(
            balance=100000.0,
            frozen=20000.0,
            margin=10000.0
        )
        
        assert account.risk_ratio == 0.3  # (20000 + 10000) / 100000


class TestUtilities:
    """Test utility functions."""
    
    def test_parse_symbol(self):
        """Test parse_symbol function."""
        code, exchange = parse_symbol("600519.SH")
        assert code == "600519"
        assert exchange == Exchange.SSE
        
        code, exchange = parse_symbol("000001.SZ")
        assert code == "000001"
        assert exchange == Exchange.SZSE
        
        code, exchange = parse_symbol("600519")
        assert code == "600519"
        assert exchange is None
    
    def test_format_symbol(self):
        """Test format_symbol function."""
        symbol = format_symbol("600519", Exchange.SSE)
        assert symbol == "600519.SH"
        
        symbol = format_symbol("000001", Exchange.SZSE)
        assert symbol == "000001.SZ"
        
        symbol = format_symbol("600519", None)
        assert symbol == "600519"
    
    def test_json_serialization(self):
        """Test JSON serialization."""
        bar = BarData(
            symbol="600519.SH",
            datetime=datetime(2024, 1, 1),
            open=100.0,
            close=101.0,
            high=102.0,
            low=99.0,
            volume=1000000
        )
        
        json_str = to_json(bar)
        assert "600519.SH" in json_str
        assert "100.0" in json_str


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
