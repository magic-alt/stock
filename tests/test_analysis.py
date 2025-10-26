"""
测试 src/backtest/analysis.py 模块
"""
import pytest
import pandas as pd
import numpy as np
import tempfile
import os


from src.backtest.analysis import (
    pareto_front,
    save_heatmap
)


class TestParetoFront:
    """测试Pareto前沿分析"""
    
    def test_pareto_front_basic(self):
        """测试基本的Pareto前沿识别"""
        # 创建测试数据
        data = {
            'strategy': ['A', 'B', 'C', 'D', 'E'],
            'sharpe_ratio': [1.5, 2.0, 1.0, 1.8, 0.5],
            'total_return': [10.0, 15.0, 8.0, 12.0, 5.0],
            'max_drawdown': [-5.0, -8.0, -3.0, -6.0, -2.0]
        }
        df = pd.DataFrame(data)
        
        # 计算Pareto前沿（最大化sharpe_ratio和total_return，最小化max_drawdown）
        pareto_df = pareto_front(df, objectives=['sharpe_ratio', 'total_return'])
        
        # 验证结果
        assert isinstance(pareto_df, pd.DataFrame)
        assert len(pareto_df) > 0
        assert len(pareto_df) <= len(df)
        
        # 策略B应该在Pareto前沿上（最高的sharpe和return）
        assert 'B' in pareto_df['strategy'].values
    
    def test_pareto_front_empty(self):
        """测试空数据集"""
        df = pd.DataFrame(columns=['strategy', 'sharpe_ratio', 'total_return'])
        
        result = pareto_front(df, objectives=['sharpe_ratio', 'total_return'])
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
    
    def test_pareto_front_single_objective(self):
        """测试单个目标"""
        data = {
            'strategy': ['A', 'B', 'C'],
            'sharpe_ratio': [1.5, 2.0, 1.0]
        }
        df = pd.DataFrame(data)
        
        result = pareto_front(df, objectives=['sharpe_ratio'])
        
        # 单目标应该返回最大值
        assert len(result) == 1
        assert result.iloc[0]['strategy'] == 'B'
    
    def test_pareto_front_with_nan(self):
        """测试包含NaN值的数据"""
        data = {
            'strategy': ['A', 'B', 'C', 'D'],
            'sharpe_ratio': [1.5, np.nan, 1.0, 2.0],
            'total_return': [10.0, 15.0, np.nan, 12.0]
        }
        df = pd.DataFrame(data)
        
        # 应该正确处理NaN
        result = pareto_front(df, objectives=['sharpe_ratio', 'total_return'])
        
        assert isinstance(result, pd.DataFrame)
        # NaN值应该被过滤或处理
        assert not result.isnull().any().any()


class TestSaveHeatmap:
    """测试热力图保存功能"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_save_heatmap_basic(self):
        """测试基本的热力图保存"""
        # 创建测试数据
        data = {
            'param1': [10, 20, 10, 20, 10, 20],
            'param2': [1, 1, 2, 2, 3, 3],
            'sharpe_ratio': [1.5, 2.0, 1.2, 1.8, 0.9, 1.1]
        }
        df = pd.DataFrame(data)
        
        out_file = os.path.join(self.test_dir, 'heatmap.png')
        
        # 保存热力图
        save_heatmap(
            df=df,
            x_col='param1',
            y_col='param2',
            value_col='sharpe_ratio',
            out_file=out_file,
            title='Test Heatmap'
        )
        
        # 验证文件已创建
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 0
    
    def test_save_heatmap_missing_values(self):
        """测试包含缺失值的热力图"""
        data = {
            'param1': [10, 20, 10],
            'param2': [1, 1, 2],
            'sharpe_ratio': [1.5, 2.0, np.nan]
        }
        df = pd.DataFrame(data)
        
        out_file = os.path.join(self.test_dir, 'heatmap_nan.png')
        
        # 应该能处理NaN
        save_heatmap(
            df=df,
            x_col='param1',
            y_col='param2',
            value_col='sharpe_ratio',
            out_file=out_file
        )
        
        assert os.path.exists(out_file)


class TestAnalysisHelpers:
    """测试分析辅助函数"""
    
    def test_calculate_metrics(self):
        """测试指标计算"""
        # 创建模拟的收益率序列
        returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.015])
        
        # 计算累计收益
        cumulative_return = (1 + returns).prod() - 1
        
        # 验证计算
        assert cumulative_return > 0
        assert abs(cumulative_return - 0.0296) < 0.001
    
    def test_max_drawdown_calculation(self):
        """测试最大回撤计算"""
        # 创建模拟的净值曲线
        nav = pd.Series([1.0, 1.1, 1.05, 0.95, 1.0, 1.15])
        
        # 计算最大回撤
        cummax = nav.cummax()
        drawdown = (nav - cummax) / cummax
        max_dd = drawdown.min()
        
        # 验证
        assert max_dd < 0
        assert abs(max_dd - (-0.136)) < 0.01


@pytest.mark.integration
class TestAnalysisIntegration:
    """集成测试：测试完整的分析流程"""
    
    def test_full_analysis_pipeline(self):
        """测试完整的分析管道"""
        # 创建更复杂的测试数据
        np.random.seed(42)
        n_strategies = 20
        
        data = {
            'strategy': [f'Strategy_{i}' for i in range(n_strategies)],
            'sharpe_ratio': np.random.normal(1.0, 0.5, n_strategies),
            'total_return': np.random.normal(10.0, 5.0, n_strategies),
            'max_drawdown': -np.abs(np.random.normal(5.0, 2.0, n_strategies)),
            'win_rate': np.random.uniform(0.4, 0.7, n_strategies) * 100
        }
        df = pd.DataFrame(data)
        
        # 执行Pareto分析
        pareto_df = pareto_front(
            df,
            objectives=['sharpe_ratio', 'total_return', 'win_rate']
        )
        
        # 验证结果
        assert len(pareto_df) > 0
        assert len(pareto_df) <= len(df)
        
        # Pareto前沿上的策略应该是"好"的
        # 至少在某些目标上表现突出
        for _, row in pareto_df.iterrows():
            # 检查是否至少有一个指标高于平均值
            assert (
                row['sharpe_ratio'] > df['sharpe_ratio'].median() or
                row['total_return'] > df['total_return'].median() or
                row['win_rate'] > df['win_rate'].median()
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
