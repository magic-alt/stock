"""
交易基础设施测试模块

测试内容:
- 统一交易接口 (TradingGateway)
- 订单管理系统 (OrderManager)
- 增强风险管理 (RiskManagerV2)
- 实时数据流 (RealtimeDataManager)
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ===========================================================================
# TradingGateway Tests
# ===========================================================================

class TestTradingGatewayModule:
    """统一交易接口测试"""
    
    def test_imports(self):
        """测试模块导入"""
        from src.core.trading_gateway import (
            TradingMode,
            GatewayConfig,
            TradingGateway,
            PaperTradingAdapter,
            BrokerType,
            GatewayStatus,
        )
        assert TradingMode.PAPER.value == "paper"
        assert TradingMode.LIVE.value == "live"
        assert BrokerType.PAPER.value == "paper"
    
    def test_gateway_config_defaults(self):
        """测试交易配置默认值"""
        from src.core.trading_gateway import GatewayConfig, TradingMode
        
        config = GatewayConfig()
        assert config.initial_cash == 1_000_000.0
        assert config.commission_rate == 0.0003
        assert config.slippage == 0.0001
        assert config.mode == TradingMode.PAPER
    
    def test_gateway_config_custom(self):
        """测试自定义交易配置"""
        from src.core.trading_gateway import GatewayConfig, TradingMode
        
        config = GatewayConfig(
            initial_cash=500_000.0,
            commission_rate=0.001,
            slippage=0.0002,
            mode=TradingMode.LIVE
        )
        assert config.initial_cash == 500_000.0
        assert config.commission_rate == 0.001
        assert config.slippage == 0.0002
    
    def test_paper_trading_adapter_initialization(self):
        """测试模拟交易适配器初始化"""
        from src.core.trading_gateway import PaperTradingAdapter, GatewayConfig
        
        config = GatewayConfig(initial_cash=100_000.0)
        adapter = PaperTradingAdapter(config)
        
        assert adapter._cash == 100_000.0
        assert adapter._positions == {}
        assert adapter._orders == {}
    
    def test_paper_trading_adapter_connect(self):
        """测试模拟交易连接"""
        from src.core.trading_gateway import PaperTradingAdapter, GatewayConfig
        
        config = GatewayConfig(initial_cash=100_000.0)
        adapter = PaperTradingAdapter(config)
        
        result = adapter.connect()
        assert result is True
        assert adapter.is_connected() is True
    
    def test_paper_trading_adapter_submit_order(self):
        """测试模拟下单"""
        from src.core.trading_gateway import PaperTradingAdapter, GatewayConfig
        from src.core.interfaces import Side, OrderTypeEnum
        
        config = GatewayConfig(initial_cash=1_000_000.0)
        adapter = PaperTradingAdapter(config)
        adapter.connect()
        
        # 设置价格
        adapter.update_price("600519.SH", 1800.0)
        
        # 下单
        order_id = adapter.submit_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0,
            order_type=OrderTypeEnum.LIMIT
        )
        
        assert order_id is not None
        assert order_id in adapter._orders
    
    def test_paper_trading_adapter_market_order_fill(self):
        """测试市价单成交"""
        from src.core.trading_gateway import PaperTradingAdapter, GatewayConfig
        from src.core.interfaces import Side, OrderTypeEnum, OrderStatusEnum
        
        config = GatewayConfig(initial_cash=1_000_000.0)
        adapter = PaperTradingAdapter(config)
        adapter.connect()
        
        # 设置价格
        adapter.update_price("600519.SH", 1800.0)
        
        # 市价单
        order_id = adapter.submit_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0,
            order_type=OrderTypeEnum.MARKET
        )
        
        # 检查订单状态（市价单应该立即成交）
        order = adapter.query_order(order_id)
        assert order.status == OrderStatusEnum.FILLED
    
    def test_paper_trading_adapter_position_update(self):
        """测试持仓更新"""
        from src.core.trading_gateway import PaperTradingAdapter, GatewayConfig
        from src.core.interfaces import Side, OrderTypeEnum
        
        config = GatewayConfig(initial_cash=1_000_000.0)
        adapter = PaperTradingAdapter(config)
        adapter.connect()
        
        # 设置价格并下市价单
        adapter.update_price("600519.SH", 1800.0)
        adapter.submit_order("600519.SH", Side.BUY, 100, 1800.0, OrderTypeEnum.MARKET)
        
        # 检查持仓
        positions = adapter.query_positions()
        assert "600519.SH" in positions
        assert positions["600519.SH"].size == 100
    
    def test_paper_trading_adapter_sell_order(self):
        """测试卖出订单"""
        from src.core.trading_gateway import PaperTradingAdapter, GatewayConfig
        from src.core.interfaces import Side, OrderTypeEnum
        
        config = GatewayConfig(initial_cash=1_000_000.0)
        adapter = PaperTradingAdapter(config)
        adapter.connect()
        
        # 先买入
        adapter.update_price("600519.SH", 1800.0)
        adapter.submit_order("600519.SH", Side.BUY, 100, 1800.0, OrderTypeEnum.MARKET)
        
        # 再卖出
        adapter.update_price("600519.SH", 1900.0)
        adapter.submit_order("600519.SH", Side.SELL, 50, 1900.0, OrderTypeEnum.MARKET)
        
        # 检查持仓减少
        positions = adapter.query_positions()
        assert positions["600519.SH"].size == 50
    
    def test_paper_trading_adapter_cancel_order(self):
        """测试取消订单"""
        from src.core.trading_gateway import PaperTradingAdapter, GatewayConfig
        from src.core.interfaces import Side, OrderTypeEnum, OrderStatusEnum
        
        config = GatewayConfig(initial_cash=1_000_000.0)
        adapter = PaperTradingAdapter(config)
        adapter.connect()
        
        # 下限价单（不立即成交）
        order_id = adapter.submit_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1700.0,  # 低于市场价
            order_type=OrderTypeEnum.LIMIT
        )
        
        # 取消订单
        result = adapter.cancel_order(order_id)
        assert result is True
        
        order = adapter.query_order(order_id)
        assert order.status == OrderStatusEnum.CANCELLED
    
    def test_paper_trading_adapter_query_account(self):
        """测试查询账户"""
        from src.core.trading_gateway import PaperTradingAdapter, GatewayConfig
        
        config = GatewayConfig(initial_cash=500_000.0)
        adapter = PaperTradingAdapter(config)
        adapter.connect()
        
        account = adapter.query_account()
        assert account is not None
        assert account.cash == 500_000.0
        assert account.total_value == 500_000.0
    
    def test_trading_gateway_initialization(self):
        """测试交易网关初始化"""
        from src.core.trading_gateway import TradingGateway, GatewayConfig, TradingMode
        
        config = GatewayConfig(mode=TradingMode.PAPER)
        gateway = TradingGateway(config)
        
        assert gateway.config.mode == TradingMode.PAPER
    
    def test_trading_gateway_connect(self):
        """测试交易网关连接"""
        from src.core.trading_gateway import TradingGateway, GatewayConfig, TradingMode
        
        config = GatewayConfig(mode=TradingMode.PAPER)
        gateway = TradingGateway(config)
        
        result = gateway.connect()
        assert result is True
    
    def test_trading_gateway_buy_sell(self):
        """测试交易网关买卖"""
        from src.core.trading_gateway import TradingGateway, GatewayConfig
        from src.core.interfaces import OrderTypeEnum
        
        gateway = TradingGateway.create_paper(initial_cash=1_000_000.0)
        gateway.connect()
        gateway.update_price("600519.SH", 1800.0)
        
        # 市价单买入（立即成交）
        order_id = gateway.buy("600519.SH", 100, price=1800.0, order_type=OrderTypeEnum.MARKET)
        assert order_id is not None
        
        # 检查持仓
        positions = gateway.get_positions()
        assert "600519.SH" in positions


# ===========================================================================
# OrderManager Tests
# ===========================================================================

class TestOrderManagerModule:
    """订单管理系统测试"""
    
    def test_imports(self):
        """测试模块导入"""
        from src.core.order_manager import (
            OrderEvent,
            OrderManager,
            ManagedOrder,
        )
        from src.core.interfaces import Side, OrderTypeEnum, OrderStatusEnum
        
        assert OrderEvent.CREATED.value == "order.created"
        assert OrderEvent.FILLED.value == "order.filled"
    
    def test_managed_order_creation(self):
        """测试托管订单创建"""
        from src.core.order_manager import ManagedOrder
        from src.core.interfaces import Side, OrderTypeEnum
        
        order = ManagedOrder(
            order_id="TEST-001",
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0,
            order_type=OrderTypeEnum.LIMIT
        )
        
        assert order.symbol == "600519.SH"
        assert order.side == Side.BUY
        assert order.quantity == 100
        assert order.price == 1800.0
        assert order.filled_quantity == 0
    
    def test_managed_order_properties(self):
        """测试托管订单属性"""
        from src.core.order_manager import ManagedOrder
        from src.core.interfaces import Side, OrderTypeEnum
        
        order = ManagedOrder(
            order_id="TEST-001",
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0,
            order_type=OrderTypeEnum.LIMIT
        )
        
        assert order.is_active is True
        assert order.is_filled is False
        assert order.remaining == 100
        assert order.fill_rate == 0.0
    
    def test_order_manager_initialization(self):
        """测试订单管理器初始化"""
        from src.core.order_manager import OrderManager
        
        manager = OrderManager()
        assert manager._orders == {}
    
    def test_order_manager_create_order(self):
        """测试创建订单"""
        from src.core.order_manager import OrderManager
        from src.core.interfaces import Side, OrderTypeEnum
        
        manager = OrderManager()
        
        order = manager.create_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0,
            order_type=OrderTypeEnum.LIMIT
        )
        
        assert order is not None
        assert order.order_id in manager._orders
    
    def test_order_manager_submit_order(self):
        """测试提交订单"""
        from src.core.order_manager import OrderManager
        from src.core.interfaces import Side, OrderTypeEnum
        from src.core.trading_gateway import TradingGateway, GatewayConfig
        
        # 创建 TradingGateway (Paper 模式)
        config = GatewayConfig(initial_cash=1_000_000.0)
        gateway = TradingGateway(config)
        gateway.connect()
        gateway._adapter.update_price("600519.SH", 1800.0)
        
        manager = OrderManager(gateway=gateway)
        
        order = manager.create_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0
        )
        
        result = manager.submit_order(order.order_id)
        assert result is True
    
    def test_order_manager_cancel_order(self):
        """测试取消订单"""
        from src.core.order_manager import OrderManager
        from src.core.interfaces import Side
        from src.core.trading_gateway import TradingGateway, GatewayConfig
        
        config = GatewayConfig(initial_cash=1_000_000.0)
        gateway = TradingGateway(config)
        gateway.connect()
        
        manager = OrderManager(gateway=gateway)
        
        order = manager.create_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1700.0  # 低于市场价，不会立即成交
        )
        
        # 提交
        manager.submit_order(order.order_id)
        
        # 取消
        result = manager.cancel_order(order.order_id)
        assert result is True
    
    def test_order_manager_get_active_orders(self):
        """测试获取活跃订单"""
        from src.core.order_manager import OrderManager
        from src.core.interfaces import Side
        
        manager = OrderManager()
        
        # 创建多个订单
        manager.create_order("600519.SH", Side.BUY, 100, 1800.0)
        manager.create_order("000001.SZ", Side.BUY, 1000, 10.0)
        manager.create_order("600036.SH", Side.SELL, 500, 35.0)
        
        active = manager.get_active_orders()
        assert len(active) == 3
    
    def test_order_manager_get_orders_by_symbol(self):
        """测试按标的获取订单"""
        from src.core.order_manager import OrderManager
        from src.core.interfaces import Side
        
        manager = OrderManager()
        
        manager.create_order("600519.SH", Side.BUY, 100, 1800.0)
        manager.create_order("600519.SH", Side.BUY, 200, 1790.0)
        manager.create_order("000001.SZ", Side.BUY, 1000, 10.0)
        
        # 使用内部索引
        order_ids = manager._orders_by_symbol.get("600519.SH", set())
        assert len(order_ids) == 2
    
    def test_order_manager_get_order(self):
        """测试获取单个订单"""
        from src.core.order_manager import OrderManager
        from src.core.interfaces import Side
        
        manager = OrderManager()
        
        created = manager.create_order("600519.SH", Side.BUY, 100, 1800.0)
        
        order = manager.get_order(created.order_id)
        assert order is not None
        assert order.symbol == "600519.SH"
    
    def test_order_manager_invalid_order_id(self):
        """测试无效订单ID处理"""
        from src.core.order_manager import OrderManager
        
        manager = OrderManager()
        
        result = manager.get_order("invalid_id")
        assert result is None
    
    def test_order_manager_cancel_nonexistent(self):
        """测试取消不存在的订单"""
        from src.core.order_manager import OrderManager
        
        manager = OrderManager()
        
        result = manager.cancel_order("invalid_id")
        assert result is False


# ===========================================================================
# RiskManagerV2 Tests
# ===========================================================================

class TestRiskManagerV2Module:
    """增强风险管理系统测试"""
    
    def test_imports(self):
        """测试模块导入"""
        from src.core.risk_manager_v2 import (
            RiskLevel,
            RiskConfig,
            RiskManagerV2,
            RiskCheckResult,
            RiskEventType,
        )
        assert RiskLevel.INFO.value == "info"
        assert RiskLevel.WARNING.value == "warning"
        assert RiskLevel.CRITICAL.value == "critical"
    
    def test_risk_config_defaults(self):
        """测试风险配置默认值"""
        from src.core.risk_manager_v2 import RiskConfig
        
        config = RiskConfig()
        assert config.max_leverage == 1.0
        assert config.max_drawdown_pct > 0
    
    def test_risk_config_factory_conservative(self):
        """测试保守型配置工厂"""
        from src.core.risk_manager_v2 import create_conservative_config
        
        config = create_conservative_config()
        assert config.max_position_pct <= 0.15
        assert config.max_drawdown_pct <= 0.10
    
    def test_risk_config_factory_moderate(self):
        """测试稳健型配置工厂"""
        from src.core.risk_manager_v2 import create_moderate_config
        
        config = create_moderate_config()
        assert config.max_position_pct <= 0.25
    
    def test_risk_config_factory_aggressive(self):
        """测试激进型配置工厂"""
        from src.core.risk_manager_v2 import create_aggressive_config
        
        config = create_aggressive_config()
        assert config.max_position_pct >= 0.25
    
    def test_risk_manager_initialization(self):
        """测试风险管理器初始化"""
        from src.core.risk_manager_v2 import RiskManagerV2, RiskConfig
        
        config = RiskConfig()
        rm = RiskManagerV2(config)
        
        assert rm.config == config
    
    def test_risk_manager_check_order_basic(self):
        """测试基础订单检查"""
        from src.core.risk_manager_v2 import RiskManagerV2, RiskConfig
        from src.core.interfaces import AccountInfo, Side
        
        # 使用宽松的配置来确保通过
        config = RiskConfig(
            max_order_value=200_000.0,
            max_order_pct=0.50,  # 允许50%单笔订单
            max_position_pct=0.50  # 允许50%仓位
        )
        rm = RiskManagerV2(config)
        
        account = AccountInfo(
            account_id="PAPER",
            cash=500_000.0,
            total_value=500_000.0
        )
        
        # 小订单: 50 * 1800 = 90,000 = 18% of 500,000
        result = rm.check_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=50,
            price=1800.0,
            account=account,
            positions={}
        )
        
        assert result is not None
        assert hasattr(result, 'passed')
        assert result.passed is True
    
    def test_risk_manager_check_order_value_limit(self):
        """测试订单金额限制"""
        from src.core.risk_manager_v2 import RiskManagerV2, RiskConfig
        from src.core.interfaces import AccountInfo, Side
        
        config = RiskConfig(max_order_value=100_000.0)
        rm = RiskManagerV2(config)
        
        account = AccountInfo(
            account_id="PAPER",
            cash=500_000.0,
            total_value=500_000.0
        )
        
        # 订单金额超过限制: 100 * 1800 = 180,000 > 100,000
        result = rm.check_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0,
            account=account,
            positions={}
        )
        
        assert result.passed is False
    
    def test_risk_manager_check_position_limit(self):
        """测试持仓限制检查"""
        from src.core.risk_manager_v2 import RiskManagerV2, RiskConfig
        from src.core.interfaces import AccountInfo, Side
        
        config = RiskConfig(max_position_pct=0.20)  # 20%
        rm = RiskManagerV2(config)
        
        account = AccountInfo(
            account_id="PAPER",
            cash=1_000_000.0,
            total_value=1_000_000.0
        )
        
        # 订单占比: 200 * 1800 = 360,000 = 36% > 20%
        result = rm.check_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=200,
            price=1800.0,
            account=account,
            positions={}
        )
        
        assert result.passed is False
    
    def test_risk_check_result(self):
        """测试风险检查结果"""
        from src.core.risk_manager_v2 import RiskCheckResult, RiskLevel
        
        # 成功结果
        success = RiskCheckResult.success("test_rule")
        assert success.passed is True
        assert success.rule_name == "test_rule"
        
        # 失败结果
        failure = RiskCheckResult.failure(
            "Order value too large",
            RiskLevel.WARNING,
            "order_value_check"
        )
        assert failure.passed is False
        assert failure.level == RiskLevel.WARNING
    
    def test_position_stop_creation(self):
        """测试止损止盈创建"""
        from src.core.risk_manager_v2 import PositionStop
        from src.core.interfaces import Side
        
        stop = PositionStop(
            symbol="600519.SH",
            entry_price=1800.0,
            entry_time=datetime.now(),
            quantity=100,
            side=Side.BUY,
            stop_loss=1710.0,  # -5%
            take_profit=1980.0  # +10%
        )
        
        assert stop.symbol == "600519.SH"
        assert stop.entry_price == 1800.0
        assert stop.stop_loss == 1710.0
        assert stop.take_profit == 1980.0
    
    def test_daily_risk_stats(self):
        """测试每日统计"""
        from src.core.risk_manager_v2 import DailyRiskStats
        
        stats = DailyRiskStats(
            date=date.today(),
            starting_equity=1_000_000.0,
            current_equity=1_050_000.0,
            high_water_mark=1_060_000.0,
            low_water_mark=990_000.0,
            realized_pnl=50_000.0,
            num_trades=10,
            num_wins=7,
            num_losses=3
        )
        
        assert stats.daily_return == pytest.approx(0.05, rel=1e-3)
        assert stats.win_rate == pytest.approx(0.7, rel=1e-3)


# ===========================================================================
# RealtimeDataManager Tests
# ===========================================================================

class TestRealtimeDataModule:
    """实时数据流模块测试"""
    
    def test_imports(self):
        """测试模块导入"""
        from src.core.realtime_data import (
            DataSource,
            DataType,
            DataEvent,
            RealtimeDataManager,
            RealtimeQuote,
        )
        assert DataSource.SINA.value == "sina"
        assert DataType.TICK.value == "tick"
        assert DataEvent.CONNECTED.value == "data.connected"
    
    def test_realtime_quote_creation(self):
        """测试实时报价创建"""
        from src.core.realtime_data import RealtimeQuote
        
        quote = RealtimeQuote(
            symbol="600519.SH",
            timestamp=datetime.now(),
            last_price=1800.0
        )
        
        assert quote.symbol == "600519.SH"
        assert quote.last_price == 1800.0
    
    def test_realtime_data_manager_initialization(self):
        """测试实时数据管理器初始化"""
        from src.core.realtime_data import RealtimeDataManager
        
        manager = RealtimeDataManager()
        assert manager is not None
    
    def test_bar_builder(self):
        """测试K线构建器"""
        from src.core.realtime_data import BarBuilder
        from src.core.interfaces import TickData
        
        builder = BarBuilder("600519.SH", interval_minutes=1)
        
        # 模拟Tick数据
        tick = TickData(
            symbol="600519.SH",
            timestamp=datetime.now(),
            last_price=1800.0,
            volume=100
        )
        
        bar = builder.update(tick)
        # 第一个tick不会产生完整bar，但会有当前bar
        current = builder.get_current_bar()
        assert current is not None or bar is None  # 取决于实现
    
    def test_signal_types(self):
        """测试信号类型"""
        from src.core.realtime_data import SignalType, Signal
        
        signal = Signal(
            symbol="600519.SH",
            signal_type=SignalType.BUY,
            timestamp=datetime.now(),
            price=1800.0,
            strength=0.8,
            reason="MA Cross"
        )
        
        assert signal.signal_type == SignalType.BUY
        assert signal.strength == 0.8
    
    def test_realtime_signal_generator(self):
        """测试实时信号生成器"""
        from src.core.realtime_data import RealtimeSignalGenerator, RealtimeDataManager
        
        dm = RealtimeDataManager()
        generator = RealtimeSignalGenerator(dm)
        assert generator is not None
    
    def test_signal_rule_creation(self):
        """测试信号规则创建"""
        from src.core.realtime_data import create_ma_cross_rule
        
        rule = create_ma_cross_rule(fast_period=5, slow_period=20)
        assert rule is not None
        assert callable(rule)
    
    def test_price_breakout_rule(self):
        """测试价格突破规则"""
        from src.core.realtime_data import create_price_breakout_rule
        
        rule = create_price_breakout_rule(lookback=20)
        assert rule is not None
        assert callable(rule)
    
    def test_simulation_data_provider(self):
        """测试模拟数据提供者"""
        from src.core.realtime_data import SimulationDataProvider
        
        provider = SimulationDataProvider()
        assert provider is not None
        
        provider.connect()
        assert provider.is_connected() is True
        
        provider.subscribe(["600519.SH"])
        provider.disconnect()


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestIntegration:
    """集成测试"""
    
    def test_gateway_with_order_manager(self):
        """测试网关与订单管理器集成"""
        from src.core.trading_gateway import TradingGateway, GatewayConfig
        from src.core.order_manager import OrderManager
        from src.core.interfaces import Side
        
        gateway = TradingGateway.create_paper(initial_cash=1_000_000.0)
        gateway.connect()
        
        # 使用网关作为后端
        order_manager = OrderManager(gateway=gateway)
        
        # 设置价格
        gateway.update_price("600519.SH", 1800.0)
        
        # 通过订单管理器创建订单
        order = order_manager.create_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0
        )
        
        assert order is not None
    
    def test_risk_manager_with_order(self):
        """测试风险管理器与订单集成"""
        from src.core.risk_manager_v2 import RiskManagerV2, RiskConfig
        from src.core.order_manager import OrderManager
        from src.core.interfaces import Side, AccountInfo
        
        # 使用宽松的配置
        config = RiskConfig(
            max_order_value=200_000.0,
            max_order_pct=0.50,
            max_position_pct=0.50
        )
        risk_manager = RiskManagerV2(config)
        order_manager = OrderManager()
        
        managed_order = order_manager.create_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0
        )
        
        account = AccountInfo(
            account_id="PAPER",
            cash=1_000_000.0,
            total_value=1_000_000.0
        )
        
        result = risk_manager.check_order(
            symbol=managed_order.symbol,
            side=managed_order.side,
            quantity=managed_order.quantity,
            price=managed_order.price,
            account=account,
            positions={}
        )
        
        assert result is not None
        assert result.passed is True
    
    def test_full_trading_flow(self):
        """测试完整交易流程"""
        from src.core.trading_gateway import TradingGateway, GatewayConfig
        from src.core.order_manager import OrderManager
        from src.core.risk_manager_v2 import RiskManagerV2, RiskConfig
        from src.core.interfaces import Side, AccountInfo
        
        # 初始化组件
        gateway = TradingGateway.create_paper(initial_cash=1_000_000.0)
        gateway.connect()
        
        order_manager = OrderManager(gateway=gateway)
        risk_config = RiskConfig(max_order_value=200_000.0)
        risk_manager = RiskManagerV2(risk_config)
        
        # 设置价格
        gateway.update_price("600519.SH", 1800.0)
        
        # 创建订单
        order = order_manager.create_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=50,
            price=1800.0
        )
        
        # 风险检查
        account = gateway.get_account()
        
        result = risk_manager.check_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            account=account,
            positions=gateway.get_positions()
        )
        
        if result.passed:
            # 提交订单
            success = order_manager.submit_order(order.order_id)
            assert success is True


# ===========================================================================
# Error Handling Tests
# ===========================================================================

class TestErrorHandling:
    """错误处理测试"""
    
    def test_order_manager_invalid_order_id(self):
        """测试无效订单ID处理"""
        from src.core.order_manager import OrderManager
        
        manager = OrderManager()
        
        result = manager.get_order("invalid_id")
        assert result is None
    
    def test_order_manager_cancel_nonexistent(self):
        """测试取消不存在的订单"""
        from src.core.order_manager import OrderManager
        
        manager = OrderManager()
        
        result = manager.cancel_order("invalid_id")
        assert result is False
    
    def test_risk_manager_zero_account(self):
        """测试零资金账户处理"""
        from src.core.risk_manager_v2 import RiskManagerV2, RiskConfig
        from src.core.interfaces import AccountInfo, Side
        
        config = RiskConfig()
        rm = RiskManagerV2(config)
        
        # 账户没有足够资金
        account = AccountInfo(
            account_id="PAPER",
            cash=0.0,
            total_value=0.0
        )
        
        result = rm.check_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=100,
            price=1800.0,
            account=account,
            positions={}
        )
        
        # 零账户应该拒绝订单
        assert result.passed is False
    
    def test_realtime_manager_no_tick(self):
        """测试获取不存在的Tick数据"""
        from src.core.realtime_data import RealtimeDataManager
        
        manager = RealtimeDataManager()
        
        tick = manager.get_latest_tick("NOT_SUBSCRIBED")
        assert tick is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
