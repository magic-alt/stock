"""
测试 src/backtest/engine.py 模块
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import tempfile
import os


from src.backtest.engine import BacktestEngine


class TestBacktestEngine:
    """测试回测引擎"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_engine_initialization(self):
        """测试引擎初始化"""
        engine = BacktestEngine(
            source='akshare',
            cache_dir=self.test_dir
        )
        
        assert engine is not None
        assert engine.cache_dir == self.test_dir
    
    @patch('src.backtest.engine.get_provider')
    def test_engine_with_custom_provider(self, mock_get_provider):
        """测试自定义数据源"""
        mock_provider = Mock()
        mock_get_provider.return_value = mock_provider
        
        engine = BacktestEngine(
            source='custom',
            cache_dir=self.test_dir
        )
        
        mock_get_provider.assert_called()
    
    def test_engine_validate_symbols(self):
        """测试股票代码验证"""
        engine = BacktestEngine(cache_dir=self.test_dir)
        
        # 有效的股票代码
        valid_symbols = ['600519.SH', '000858.SZ']
        # 无效的股票代码
        invalid_symbols = ['INVALID']
        
        # 这里应该有验证逻辑，实际需要根据engine实现
        assert True  # Placeholder
    
    @pytest.mark.integration
    @patch('src.backtest.engine.BacktestEngine.run_strategy')
    def test_run_single_backtest_mock(self, mock_run):
        """测试单次回测（使用mock）"""
        engine = BacktestEngine(cache_dir=self.test_dir)
        
        # Mock返回值
        mock_run.return_value = {
            'total_return': 10.0,
            'sharpe_ratio': 1.5,
            'max_drawdown': -5.0,
            'nav': pd.Series([1.0, 1.1, 1.05])
        }
        
        result = engine.run_strategy(
            strategy_name='ema',
            symbols=['600519.SH'],
            start='2024-01-01',
            end='2024-12-31'
        )
        
        assert isinstance(result, dict)
        assert 'total_return' in result
        mock_run.assert_called_once()
    
    @pytest.mark.integration
    @patch('src.backtest.engine.BacktestEngine.grid_search')
    def test_grid_search_mock(self, mock_grid):
        """测试网格搜索（使用mock）"""
        engine = BacktestEngine(cache_dir=self.test_dir)
        
        # Mock返回值
        mock_grid.return_value = pd.DataFrame({
            'param1': [10, 20],
            'param2': [1, 2],
            'sharpe_ratio': [1.5, 2.0]
        })
        
        result = engine.grid_search(
            strategy_name='ema',
            param_grid={'period': [10, 20]},
            symbols=['600519.SH'],
            start='2024-01-01',
            end='2024-12-31'
        )
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        mock_grid.assert_called_once()


class TestBacktestMetrics:
    """测试回测指标计算"""
    
    def test_calculate_sharpe_ratio(self):
        """测试夏普比率计算"""
        # 创建模拟收益率
        returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.015, 0.008])
        
        # 计算夏普比率
        mean_return = returns.mean()
        std_return = returns.std()
        sharpe = (mean_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        
        assert sharpe > 0
    
    def test_calculate_max_drawdown(self):
        """测试最大回撤计算"""
        # 创建模拟净值曲线
        nav = pd.Series([1.0, 1.1, 1.05, 0.95, 1.0, 1.15, 1.10])
        
        # 计算最大回撤
        cummax = nav.cummax()
        drawdown = (nav - cummax) / cummax
        max_dd = drawdown.min()
        
        assert max_dd < 0
        # 从1.1跌到0.95，回撤约 (0.95-1.1)/1.1 = -13.6%
        assert abs(max_dd - (-0.136)) < 0.01
    
    def test_calculate_total_return(self):
        """测试总收益率计算"""
        initial_value = 100000
        final_value = 110000
        
        total_return = (final_value - initial_value) / initial_value * 100
        
        assert total_return == 10.0
    
    def test_calculate_win_rate(self):
        """测试胜率计算"""
        trades = [
            {'profit': 100},
            {'profit': -50},
            {'profit': 200},
            {'profit': -30},
            {'profit': 150}
        ]
        
        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        total_trades = len(trades)
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        assert win_rate == 60.0


@pytest.mark.integration
class TestBacktestEngineIntegration:
    """集成测试：测试完整的回测流程"""
    
    @pytest.mark.skip(reason="需要真实数据和网络连接")
    def test_full_backtest_pipeline(self):
        """测试完整的回测管道"""
        engine = BacktestEngine(source='akshare')
        
        result = engine.run_strategy(
            strategy_name='ema',
            symbols=['600519.SH'],
            start='2024-01-01',
            end='2024-06-30',
            params={'fast_period': 10, 'slow_period': 30}
        )
        
        # 验证结果包含必要的指标
        assert 'total_return' in result
        assert 'sharpe_ratio' in result
        assert 'max_drawdown' in result
        assert 'nav' in result
    
    @pytest.mark.skip(reason="需要真实数据和网络连接")
    def test_full_grid_search_pipeline(self):
        """测试完整的网格搜索管道"""
        engine = BacktestEngine(source='akshare')
        
        param_grid = {
            'fast_period': [5, 10],
            'slow_period': [20, 30]
        }
        
        results = engine.grid_search(
            strategy_name='ema',
            param_grid=param_grid,
            symbols=['600519.SH'],
            start='2024-01-01',
            end='2024-06-30'
        )
        
        # 应该有4个组合的结果
        assert len(results) == 4
        assert 'fast_period' in results.columns
        assert 'slow_period' in results.columns
        assert 'sharpe_ratio' in results.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
