"""
Phase 4 Integration Tests

Validates all Phase 4 components working together:
- Strategy Template + Context
- Standardized Data Objects
- DataPortal
- Pipeline Factor Engine
- Risk Manager
- Configuration System
"""
import sys
sys.path.insert(0, "e:/work/Project/stock")

import pytest
from datetime import datetime

from src.strategy.template import StrategyTemplate, Context, build_bt_strategy
from src.core.objects import BarData, OrderData, AccountData, PositionData, Direction, OrderStatus
from src.data_sources.data_portal import create_portal
from src.pipeline.factor_engine import Pipeline, Momentum, RSI, SMA, alpha_pipeline
from src.core.risk_manager import create_moderate_risk_manager, RiskCheckResult
from src.core.config import ConfigManager, GlobalConfig


class TestPhase4Integration:
    """Integration tests for Phase 4 components."""
    
    def test_data_objects_creation(self):
        """Test creating all standard data objects."""
        # BarData
        bar = BarData(
            symbol="600519.SH",
            datetime=datetime(2024, 1, 1),
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000000
        )
        assert bar.close == 103.0
        
        # OrderData
        order = OrderData(
            symbol="600519.SH",
            order_id="ORDER_001",
            direction=Direction.LONG,
            volume=100,
            price=100.0,
            status=OrderStatus.PENDING
        )
        assert order.remaining == 100
        
        # AccountData
        account = AccountData(
            balance=100000.0,
            available=80000.0,
            frozen=20000.0
        )
        assert account.total_value == 100000.0
        
        print("✓ Data objects creation successful")
    
    def test_data_portal_integration(self):
        """Test DataPortal with real data."""
        portal = create_portal("akshare", "./cache")
        
        # Load data
        data_map = portal.load_data(["600519.SH"], "2024-01-01", "2024-01-10")
        assert "600519.SH" in data_map
        
        # Get current price
        price = portal.current("600519.SH", "close")
        assert price > 0
        
        # Get history
        hist = portal.history("600519.SH", "close", 5)
        assert len(hist) > 0
        
        print(f"✓ DataPortal loaded {len(data_map['600519.SH'])} bars")
        print(f"✓ Current price: {price}")
    
    def test_pipeline_factor_computation(self):
        """Test Pipeline factor engine."""
        # Create portal and load data
        portal = create_portal("akshare", "./cache")
        data_map = portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        # Create pipeline
        pipeline = Pipeline()
        pipeline.add("momentum_20", Momentum(20))
        pipeline.add("rsi_14", RSI(14))
        pipeline.add("sma_20", SMA(20))
        
        # Run pipeline
        results = pipeline.run(data_map)
        
        assert not results.empty
        assert "momentum_20" in results.columns or len(pipeline.factors) == len(results.columns)
        
        print(f"✓ Pipeline computed {len(pipeline.factors)} factors")
        print(f"✓ Results shape: {results.shape}")
    
    def test_risk_manager_checks(self):
        """Test RiskManager with various orders."""
        risk_mgr = create_moderate_risk_manager()
        
        # Create test data
        account = AccountData(
            balance=100000.0,
            available=80000.0
        )
        
        positions = {}
        
        # Test 1: Valid order (smaller size to pass position limit)
        order = OrderData(
            symbol="600519.SH",
            direction=Direction.LONG,
            volume=20,  # 20 * 1000 = 20000 (within 30% position limit of 100k)
            price=1000.0
        )
        
        result = risk_mgr.check_order(order, account, positions, 1000.0)
        assert result.passed
        print("✓ Valid order passed risk checks")
        
        # Test 2: Insufficient cash
        large_order = OrderData(
            symbol="600519.SH",
            direction=Direction.LONG,
            volume=1000,  # 1000 * 1000 = 1M (exceeds available)
            price=1000.0
        )
        
        result = risk_mgr.check_order(large_order, account, positions, 1000.0)
        assert not result.passed
        print(f"✓ Large order rejected: {result.reason}")
    
    def test_config_system(self):
        """Test configuration system."""
        # Create config
        config = ConfigManager()
        
        # Check defaults
        assert config.backtest.initial_cash == 100000.0
        assert config.data.provider == "akshare"
        
        # Update config
        config.update(backtest={"initial_cash": 200000.0})
        assert config.backtest.initial_cash == 200000.0
        
        # Save and load
        config.save_to_file("test_config.yaml")
        config2 = ConfigManager.load_from_file("test_config.yaml")
        assert config2.backtest.initial_cash == 200000.0
        
        print("✓ Configuration system working")
        
        # Cleanup
        import os
        if os.path.exists("test_config.yaml"):
            os.remove("test_config.yaml")
    
    def test_full_integration_workflow(self):
        """Test complete workflow with all components."""
        print("\n=== Full Integration Test ===")
        
        # 1. Load configuration
        config = ConfigManager()
        config.update(
            backtest={"initial_cash": 100000.0, "commission": 0.001},
            data={"provider": "akshare", "cache_dir": "./cache"}
        )
        print("✓ Configuration loaded")
        
        # 2. Create DataPortal
        portal = create_portal(
            config.data.provider,
            config.data.cache_dir
        )
        data_map = portal.load_data(["600519.SH"], "2024-01-01", "2024-01-10")
        print(f"✓ Data loaded: {len(data_map['600519.SH'])} bars")
        
        # 3. Compute factors
        pipeline = alpha_pipeline()
        factors = pipeline.run(data_map)
        print(f"✓ Factors computed: {factors.shape}")
        
        # 4. Risk checks
        risk_mgr = create_moderate_risk_manager()
        account = AccountData(
            balance=config.backtest.initial_cash,
            available=config.backtest.initial_cash
        )
        
        order = OrderData(
            symbol="600519.SH",
            direction=Direction.LONG,
            volume=50,
            price=portal.current("600519.SH")
        )
        
        risk_result = risk_mgr.check_order(order, account, {}, portal.current("600519.SH"))
        print(f"✓ Risk check: {'PASSED' if risk_result.passed else 'FAILED'}")
        
        # 5. Create standard data objects
        bar = portal.current_bar("600519.SH")
        assert isinstance(bar, BarData)
        print(f"✓ Current bar: {bar.datetime}, close={bar.close}")
        
        print("\n=== All Phase 4 Components Working! ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
