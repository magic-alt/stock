"""
测试分析模块
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from src.backtest.analysis import pareto_front, save_heatmap


class TestParetoFront(unittest.TestCase):
    """测试帕累托前沿计算"""
    
    def test_pareto_front_basic(self):
        """测试基本的帕累托前沿计算"""
        # 创建测试数据（使用实际的列名：sharpe, cum_return, mdd）
        df = pd.DataFrame({
            'strategy': ['A', 'B', 'C', 'D'],
            'sharpe': [1.5, 2.0, 1.0, 2.5],
            'cum_return': [0.15, 0.20, 0.10, 0.25],
            'mdd': [0.10, 0.15, 0.08, 0.12]
        })
        
        # 计算帕累托前沿
        pareto_df = pareto_front(df)
        
        # 验证结果
        self.assertIsInstance(pareto_df, pd.DataFrame)
        self.assertGreater(len(pareto_df), 0)
        self.assertLessEqual(len(pareto_df), len(df))
    
    def test_pareto_front_empty(self):
        """测试空数据集"""
        df = pd.DataFrame({
            'sharpe': [],
            'cum_return': [],
            'mdd': []
        })
        
        result = pareto_front(df)
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 0)
    
    def test_pareto_front_single_best(self):
        """测试单个最佳策略"""
        df = pd.DataFrame({
            'strategy': ['A', 'B'],
            'sharpe': [1.5, 2.0],
            'cum_return': [0.10, 0.15],
            'mdd': [0.15, 0.10]
        })
        
        result = pareto_front(df)
        
        # B dominates A (higher sharpe, higher return, lower drawdown)
        self.assertEqual(len(result), 1)
        self.assertEqual(result['sharpe'].iloc[0], 2.0)
    
    def test_pareto_front_with_nan(self):
        """测试包含NaN值的数据"""
        df = pd.DataFrame({
            'strategy': ['A', 'B', 'C'],
            'sharpe': [1.5, np.nan, 2.0],
            'cum_return': [0.15, 0.20, np.nan],
            'mdd': [0.10, 0.15, 0.12]
        })
        
        result = pareto_front(df)
        
        # 应该处理NaN值（NaN比较总是False，所以不会被支配也不会支配别人）
        self.assertIsInstance(result, pd.DataFrame)
        # 验证没有抛出异常


class TestSaveHeatmap(unittest.TestCase):
    """测试热力图保存功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.test_dir)
    
    def test_save_heatmap_macd(self):
        """测试MACD策略热力图保存"""
        # 创建mock策略模块
        module = type('Module', (), {'name': 'macd'})()
        
        # 创建测试数据
        df = pd.DataFrame({
            'fast': [5, 10, 15, 5, 10, 15],
            'slow': [20, 20, 20, 30, 30, 30],
            'cum_return': [0.10, 0.15, 0.20, 0.08, 0.12, 0.18],
            'trades': [10, 15, 20, 8, 12, 18]
        })
        
        # 保存热力图
        save_heatmap(module, df, self.test_dir)
        
        # 验证文件已创建
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'heat_macd.png')))
    
    def test_save_heatmap_ema(self):
        """测试EMA策略热力图保存"""
        # 创建mock策略模块
        module = type('Module', (), {'name': 'ema'})()
        
        # 创建包含缺失值的数据
        df = pd.DataFrame({
            'period': [10, 20, 30],
            'cum_return': [0.10, np.nan, 0.20],
            'trades': [10, 0, 20]
        })
        
        # 保存热力图
        save_heatmap(module, df, self.test_dir)
        
        # 验证文件已创建
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'heat_ema.png')))


class TestAnalysisHelpers(unittest.TestCase):
    """测试辅助函数"""
    
    def test_calculate_metrics(self):
        """测试指标计算"""
        # 创建测试数据
        returns = pd.Series([0.01, 0.02, -0.01, 0.03, -0.02])
        
        # 计算夏普比率
        mean_return = returns.mean()
        std_return = returns.std()
        sharpe = mean_return / std_return if std_return != 0 else 0
        
        # 验证计算
        self.assertIsInstance(sharpe, float)
    
    def test_max_drawdown_calculation(self):
        """测试最大回撤计算"""
        # 创建测试数据
        cumulative_returns = pd.Series([1.0, 1.1, 1.05, 1.2, 1.15, 1.3])
        
        # 计算最大回撤
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        max_dd = drawdown.min()
        
        # 验证结果
        self.assertLessEqual(max_dd, 0)
        self.assertIsInstance(max_dd, (float, np.floating))


@pytest.mark.integration
class TestAnalysisIntegration(unittest.TestCase):
    """测试完整分析流程"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.test_dir)
    
    def test_full_analysis_pipeline(self):
        """测试完整的分析流程"""
        # 生成模拟的优化结果
        np.random.seed(42)
        n_configs = 20
        
        strategies = []
        for i in range(n_configs):
            strategies.append({
                'config': f'config_{i}',
                'sharpe': np.random.uniform(0.5, 3.0),
                'cum_return': np.random.uniform(0.05, 0.30),
                'mdd': np.random.uniform(0.05, 0.25),
                'win_rate': np.random.uniform(0.40, 0.70),
                'fast': np.random.choice([5, 10, 15]),
                'slow': np.random.choice([20, 30, 40]),
                'trades': np.random.randint(10, 50)
            })
        
        df = pd.DataFrame(strategies)
        
        # 1. 计算帕累托前沿
        pareto_df = pareto_front(df)
        
        self.assertGreater(len(pareto_df), 0)
        self.assertLessEqual(len(pareto_df), len(df))
        
        # 2. 保存热力图（使用MACD策略）
        module = type('Module', (), {'name': 'macd'})()
        save_heatmap(module, df, self.test_dir)
        
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, 'heat_macd.png')))


if __name__ == '__main__':
    unittest.main()
