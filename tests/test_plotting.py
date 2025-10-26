"""
测试 src/backtest/plotting.py 模块
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import datetime


# 尝试导入backtrader，如果失败则跳过测试
try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False
    bt = None

from src.backtest.plotting import (
    generate_backtest_report,
    plot_backtest_with_indicators
)


class TestGenerateBacktestReport:
    """测试回测报告生成功能"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    @pytest.mark.skipif(not BACKTRADER_AVAILABLE, reason="backtrader not installed")
    def test_generate_report_basic(self):
        """测试基本的报告生成"""
        # 创建模拟的cerebro对象
        cerebro = Mock()
        cerebro.broker.startingcash = 100000
        cerebro.broker.getvalue.return_value = 110000
        
        # 创建模拟的策略
        strat = Mock()
        strat.params._getkeys.return_value = ['period', 'deviation']
        strat.params.period = 20
        strat.params.deviation = 2.0
        strat.analyzers.trades.get_analysis.return_value = {
            'total': {'total': 10, 'open': 0, 'closed': 10},
            'won': {'total': 6, 'pnl': {'average': 500, 'max': 1000}},
            'lost': {'total': 4, 'pnl': {'average': -300, 'max': -500}}
        }
        
        cerebro.runstrats = [[strat]]
        
        # 测试指标
        metrics = {
            'total_return': 10.0,
            'annual_return': 15.0,
            'sharpe_ratio': 1.5,
            'max_drawdown': -5.0,
            'win_rate': 60.0,
            'profit_factor': 2.0,
            'total_trades': 10
        }
        
        # 生成报告
        generate_backtest_report(
            cerebro=cerebro,
            strategy_name='test_strategy',
            symbols=['600519.SH'],
            metrics=metrics,
            report_dir=self.test_dir
        )
        
        # 验证文件已创建
        assert os.path.exists(os.path.join(self.test_dir, 'backtest_report.md'))
        assert os.path.exists(os.path.join(self.test_dir, 'backtest_summary.json'))
        
        # 读取并验证报告内容
        with open(os.path.join(self.test_dir, 'backtest_report.md'), 'r', encoding='utf-8') as f:
            report_content = f.read()
            assert '# 回测分析报告' in report_content
            assert 'test_strategy' in report_content
            assert '600519.SH' in report_content
            assert '10.00%' in report_content  # total_return
    
    @pytest.mark.skipif(not BACKTRADER_AVAILABLE, reason="backtrader not installed")
    def test_generate_report_no_trades(self):
        """测试没有交易记录的情况"""
        cerebro = Mock()
        cerebro.broker.startingcash = 100000
        cerebro.broker.getvalue.return_value = 100000
        
        strat = Mock()
        strat.params._getkeys.return_value = []
        # 没有analyzers
        delattr(strat, 'analyzers')
        
        cerebro.runstrats = [[strat]]
        
        metrics = {'total_return': 0.0}
        
        # 应该不会抛出异常
        generate_backtest_report(
            cerebro=cerebro,
            strategy_name='test_strategy',
            symbols=['600519.SH'],
            metrics=metrics,
            report_dir=self.test_dir
        )
        
        assert os.path.exists(os.path.join(self.test_dir, 'backtest_report.md'))


class TestPlotBacktestWithIndicators:
    """测试回测可视化功能"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    @pytest.mark.skipif(not BACKTRADER_AVAILABLE, reason="backtrader not installed")
    @patch('src.backtest.plotting.plt')
    def test_plot_with_auto_save(self, mock_plt):
        """测试自动保存模式"""
        # 创建模拟的cerebro
        cerebro = Mock()
        cerebro.broker.startingcash = 100000
        cerebro.broker.getvalue.return_value = 110000
        cerebro.datas = []
        
        strat = Mock()
        strat.params._getkeys.return_value = []
        cerebro.runstrats = [[strat]]
        
        # 模拟plot返回
        mock_fig = Mock()
        cerebro.plot.return_value = [[mock_fig]]
        
        # 模拟plt.gcf()
        mock_plt.gcf.return_value = mock_fig
        mock_plt.get_fignums.return_value = [1]
        mock_plt.isinteractive.return_value = False
        
        metrics = {'total_return': 10.0}
        
        # 调用plot函数
        result = plot_backtest_with_indicators(
            cerebro=cerebro,
            auto_save=True,
            strategy_name='test_strategy',
            symbols=['600519.SH'],
            metrics=metrics
        )
        
        # 验证返回了报告目录
        assert result is not None
        assert os.path.exists(result)
        assert 'report' in result
        assert '600519' in result
        assert 'test_strategy' in result


@pytest.mark.integration
class TestPlottingIntegration:
    """集成测试：测试完整的绘图流程"""
    
    @pytest.mark.skipif(not BACKTRADER_AVAILABLE, reason="backtrader not installed")
    def test_full_plotting_pipeline(self):
        """测试完整的绘图管道（需要真实数据）"""
        # 这个测试需要真实的backtest结果
        # 可以跳过或使用fixtures
        pytest.skip("需要真实回测数据")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
