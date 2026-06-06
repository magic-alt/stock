"""
测试回测模块 (src/backtest/*)
覆盖: engine, plotting, analysis, strategy_modules
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

from src.backtest.engine import BacktestEngine, _compute_metrics_vectorized
from src.backtest.analysis import pareto_front, save_heatmap
from src.backtest.plotting import (
    generate_backtest_report, plot_backtest_with_indicators
)
from src.backtest.strategy_modules import STRATEGY_REGISTRY


class TestBacktestEngine:
    """测试回测引擎"""
    
    def setup_method(self):
        """初始化回测引擎"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir) / "output"
        self.output_dir.mkdir(exist_ok=True)
    
    def teardown_method(self):
        """清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_engine_creation(self):
        """测试引擎创建"""
        engine = BacktestEngine(
            source="akshare",
            cache_dir=str(self.temp_dir)
        )
        assert engine is not None
        assert engine.source == "akshare"
    
    def test_engine_has_gateway(self):
        """测试引擎拥有数据网关"""
        engine = BacktestEngine(
            source="akshare",
            cache_dir=str(self.temp_dir)
        )
        assert engine.gw is not None
        assert hasattr(engine, 'run_strategy')
    
    def test_engine_metrics_cache(self):
        """测试引擎指标缓存"""
        engine = BacktestEngine(
            source="akshare",
            cache_dir=str(self.temp_dir)
        )
        assert isinstance(engine._metrics_cache, dict)
    
    def test_compute_metrics_vectorized_basic(self):
        """测试向量化指标计算"""
        nav = pd.Series([1.0, 1.05, 1.10, 0.95, 1.0, 1.15, 1.20])
        metrics = _compute_metrics_vectorized(nav)
        
        assert isinstance(metrics, dict)
        assert "sharpe" in metrics
        assert "sortino" in metrics
        assert "max_drawdown" in metrics
        assert "cagr" in metrics
        assert "var_95" in metrics
        assert "es_95" in metrics
        assert "vol" in metrics
    
    def test_compute_metrics_vectorized_drawdown(self):
        """测试向量化最大回撤计算"""
        # Known drawdown: peak=1.2, trough=0.9, mdd=0.25
        nav = pd.Series([1.0, 1.1, 1.2, 0.9, 1.0])
        metrics = _compute_metrics_vectorized(nav)
        assert metrics["max_drawdown"] == pytest.approx(0.25, abs=0.01)
    
    def test_compute_metrics_vectorized_empty(self):
        """测试空NAV的指标计算"""
        metrics = _compute_metrics_vectorized(pd.Series(dtype=float))
        assert isinstance(metrics, dict)
        assert np.isnan(metrics["sharpe"])
    
    def test_compute_metrics_vectorized_short(self):
        """测试单值NAV的指标计算"""
        metrics = _compute_metrics_vectorized(pd.Series([1.0]))
        assert np.isnan(metrics["sharpe"])


class TestAnalysis:
    """测试分析模块"""
    
    def test_pareto_front(self):
        """测试帕累托前沿"""
        df = pd.DataFrame({
            'sharpe': [0.1, 0.15, 0.12, 0.08, 0.2],
            'cum_return': [0.05, 0.08, 0.06, 0.04, 0.12],
            'mdd': [0.1, 0.15, 0.12, 0.08, 0.2]
        })
        
        pareto_df = pareto_front(df)
        
        assert pareto_df is not None
        assert len(pareto_df) > 0
        # The best sharpe+return point should be in the Pareto front
        assert any(pareto_df["sharpe"] >= 0.15)
    
    def test_pareto_front_empty(self):
        """测试空数据的帕累托前沿"""
        df = pd.DataFrame({'sharpe': [], 'cum_return': [], 'mdd': []})
        pareto_df = pareto_front(df)
        assert len(pareto_df) == 0
    
    def test_save_heatmap(self):
        """测试保存热力图"""
        pytest.importorskip("matplotlib")
        temp_dir = tempfile.mkdtemp()
        
        try:
            # 创建测试数据
            df = pd.DataFrame({
                'fast': [5, 10, 15],
                'slow': [20, 30, 40],
                'cum_return': [0.1, 0.15, 0.2]
            })
            
            # 创建mock module
            module = type('Module', (), {'name': 'test'})()
            
            save_heatmap(module, df, temp_dir)
            
            # 验证输出目录存在
            assert Path(temp_dir).exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestPlotting:
    """测试绘图模块"""
    
    def setup_method(self):
        """初始化"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_generate_backtest_report_callable(self):
        """测试generate_backtest_report函数可调用"""
        assert callable(generate_backtest_report)
        # Verify the function signature accepts the expected parameters
        import inspect
        sig = inspect.signature(generate_backtest_report)
        params = list(sig.parameters.keys())
        assert "cerebro" in params
        assert "strategy_name" in params
        assert "metrics" in params
        assert "report_dir" in params
    
    def test_plot_backtest_with_indicators_callable(self):
        """测试plot_backtest_with_indicators函数可调用"""
        assert callable(plot_backtest_with_indicators)


class TestStrategyModules:
    """测试策略模块"""
    
    def test_strategy_registry(self):
        """测试策略注册表"""
        assert isinstance(STRATEGY_REGISTRY, dict)
        assert len(STRATEGY_REGISTRY) > 0
    
    def test_strategy_registry_contains_modules(self):
        """测试策略注册表包含StrategyModule对象"""
        for name, module in STRATEGY_REGISTRY.items():
            assert isinstance(name, str)
            assert module is not None
            # Each module should have a name attribute
            assert hasattr(module, 'name')
            assert module.name == name
    
    def test_strategy_registry_has_known_strategies(self):
        """测试策略注册表包含已知策略"""
        # At minimum, ema and macd should be registered
        known = {"ema", "macd", "bollinger", "rsi"}
        found = known & set(STRATEGY_REGISTRY.keys())
        assert len(found) >= 2, f"Expected at least 2 of {known}, found {found}"


class TestBacktestIntegration:
    """回测模块集成测试"""
    
    def setup_method(self):
        """初始化"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir) / "output"
        self.output_dir.mkdir(exist_ok=True)
    
    def teardown_method(self):
        """清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_engine_strategy_registry_access(self):
        """测试引擎可以访问策略注册表"""
        engine = BacktestEngine(
            source="akshare",
            cache_dir=str(self.temp_dir)
        )
        assert engine is not None
        
        # Verify strategy registry is accessible
        from src.backtest.strategy_modules import STRATEGY_REGISTRY
        assert len(STRATEGY_REGISTRY) > 0
        
        # Verify at least one strategy has required attributes
        for name, module in list(STRATEGY_REGISTRY.items())[:1]:
            assert hasattr(module, 'coerce')
            assert hasattr(module, 'param_names')
            assert hasattr(module, 'grid_defaults')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
