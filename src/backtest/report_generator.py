"""
回测报告生成模块
提供统一的报告生成、指标计算、图表绘制功能
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 延迟导入 matplotlib（可能未安装）
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # 无GUI后端
    PLT_AVAILABLE = True
except ImportError:
    PLT_AVAILABLE = False
    logger.warning("matplotlib 未安装，图表功能不可用")


class BacktestMetrics:
    """回测指标计算器"""
    
    @staticmethod
    def calculate_returns(nav_series: pd.Series) -> pd.Series:
        """计算收益率序列"""
        return nav_series.pct_change().fillna(0.0)
    
    @staticmethod
    def calculate_cumulative_return(nav_series: pd.Series) -> float:
        """计算累计收益率"""
        if len(nav_series) < 2:
            return 0.0
        return (nav_series.iloc[-1] / nav_series.iloc[0] - 1.0) * 100
    
    @staticmethod
    def calculate_annualized_return(nav_series: pd.Series, days: int = None) -> float:
        """计算年化收益率"""
        if len(nav_series) < 2:
            return 0.0
        
        cumulative = nav_series.iloc[-1] / nav_series.iloc[0] - 1.0
        
        if days is None:
            days = len(nav_series)
        
        years = days / 252  # 交易日年化
        if years <= 0:
            return 0.0
        
        return ((1 + cumulative) ** (1 / years) - 1) * 100
    
    @staticmethod
    def calculate_volatility(nav_series: pd.Series, annualized: bool = True) -> float:
        """计算波动率"""
        returns = BacktestMetrics.calculate_returns(nav_series)
        vol = returns.std()
        
        if annualized:
            vol = vol * np.sqrt(252)
        
        return vol * 100
    
    @staticmethod
    def calculate_sharpe_ratio(nav_series: pd.Series, risk_free_rate: float = 0.03) -> float:
        """计算夏普比率"""
        returns = BacktestMetrics.calculate_returns(nav_series)
        
        if returns.std() == 0:
            return 0.0
        
        excess_return = returns.mean() - risk_free_rate / 252
        sharpe = excess_return / returns.std() * np.sqrt(252)
        
        return sharpe
    
    @staticmethod
    def calculate_max_drawdown(nav_series: pd.Series) -> Tuple[float, int, int]:
        """
        计算最大回撤
        
        返回:
            (最大回撤百分比, 开始索引, 结束索引)
        """
        cummax = nav_series.cummax()
        drawdown = (nav_series - cummax) / cummax
        
        max_dd = drawdown.min()
        max_dd_idx = drawdown.idxmin()
        
        # 找到回撤开始位置
        start_idx = nav_series[:max_dd_idx].idxmax()
        
        return abs(max_dd) * 100, start_idx, max_dd_idx
    
    @staticmethod
    def calculate_win_rate(trades: List[Dict]) -> float:
        """计算胜率"""
        if not trades:
            return 0.0
        
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        return wins / len(trades) * 100
    
    @staticmethod
    def calculate_profit_loss_ratio(trades: List[Dict]) -> float:
        """计算盈亏比"""
        if not trades:
            return 0.0
        
        profits = [t['pnl'] for t in trades if t.get('pnl', 0) > 0]
        losses = [abs(t['pnl']) for t in trades if t.get('pnl', 0) < 0]
        
        if not profits or not losses:
            return 0.0
        
        avg_profit = np.mean(profits)
        avg_loss = np.mean(losses)
        
        return avg_profit / avg_loss if avg_loss > 0 else 0.0
    
    @staticmethod
    def calculate_all_metrics(nav_series: pd.Series, benchmark_series: pd.Series = None, 
                             trades: List[Dict] = None) -> Dict:
        """计算所有指标"""
        metrics = {
            'total_return': BacktestMetrics.calculate_cumulative_return(nav_series),
            'annual_return': BacktestMetrics.calculate_annualized_return(nav_series),
            'volatility': BacktestMetrics.calculate_volatility(nav_series),
            'sharpe_ratio': BacktestMetrics.calculate_sharpe_ratio(nav_series),
            'max_drawdown': BacktestMetrics.calculate_max_drawdown(nav_series)[0],
            'total_trades': len(trades) if trades else 0,
        }
        
        if trades:
            metrics['win_rate'] = BacktestMetrics.calculate_win_rate(trades)
            metrics['profit_loss_ratio'] = BacktestMetrics.calculate_profit_loss_ratio(trades)
        
        if benchmark_series is not None and len(benchmark_series) > 0:
            metrics['benchmark_return'] = BacktestMetrics.calculate_cumulative_return(benchmark_series)
            metrics['excess_return'] = metrics['total_return'] - metrics['benchmark_return']
        
        return metrics


class ReportGenerator:
    """回测报告生成器"""
    
    def __init__(self, output_dir: str = './reports'):
        """
        初始化报告生成器
        
        参数:
            output_dir: 报告输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"报告生成器已初始化，输出目录: {output_dir}")
    
    def generate_summary_report(
        self,
        strategy_name: str,
        params: Dict,
        metrics: Dict,
        save_json: bool = True
    ) -> str:
        """
        生成汇总报告（文本+JSON）
        
        参数:
            strategy_name: 策略名称
            params: 策略参数
            metrics: 性能指标字典
            save_json: 是否保存JSON文件
        
        返回:
            报告文本内容
        """
        report_lines = [
            "=" * 80,
            f"回测报告 - {strategy_name}",
            "=" * 80,
            "",
            "策略参数:",
            "-" * 40,
        ]
        
        for key, value in params.items():
            report_lines.append(f"  {key}: {value}")
        
        report_lines.extend([
            "",
            "性能指标:",
            "-" * 40,
        ])
        
        metric_labels = {
            'total_return': '累计收益率',
            'annual_return': '年化收益率',
            'volatility': '年化波动率',
            'sharpe_ratio': '夏普比率',
            'max_drawdown': '最大回撤',
            'total_trades': '交易次数',
            'win_rate': '胜率',
            'profit_loss_ratio': '盈亏比',
            'benchmark_return': '基准收益率',
            'excess_return': '超额收益',
        }
        
        for key, label in metric_labels.items():
            if key in metrics:
                value = metrics[key]
                if isinstance(value, float):
                    if key in ['sharpe_ratio', 'profit_loss_ratio']:
                        report_lines.append(f"  {label}: {value:.2f}")
                    else:
                        report_lines.append(f"  {label}: {value:.2f}%")
                else:
                    report_lines.append(f"  {label}: {value}")
        
        report_lines.extend([
            "",
            "=" * 80,
        ])
        
        report_text = "\n".join(report_lines)
        
        # 保存文本报告
        txt_file = os.path.join(self.output_dir, f"{strategy_name}_report.txt")
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"文本报告已保存: {txt_file}")
        
        # 保存JSON报告
        if save_json:
            json_data = {
                'strategy_name': strategy_name,
                'params': params,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat(),
            }
            json_file = os.path.join(self.output_dir, f"{strategy_name}_report.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            logger.info(f"JSON报告已保存: {json_file}")
        
        return report_text
    
    def plot_nav_comparison(
        self,
        nav_dict: Dict[str, pd.Series],
        title: str = "净值曲线对比",
        filename: str = "nav_comparison.png"
    ) -> Optional[str]:
        """
        绘制多条净值曲线对比图
        
        参数:
            nav_dict: {标签: 净值序列} 字典
            title: 图表标题
            filename: 输出文件名
        
        返回:
            图片文件路径（失败返回None）
        """
        if not PLT_AVAILABLE:
            logger.warning("matplotlib 不可用，无法绘制图表")
            return None
        
        try:
            plt.figure(figsize=(14, 7))
            
            for label, nav_series in nav_dict.items():
                plt.plot(nav_series.index, nav_series.values, label=label, linewidth=2)
            
            plt.title(title, fontsize=16, fontproperties='SimHei')
            plt.xlabel('日期', fontsize=12, fontproperties='SimHei')
            plt.ylabel('净值', fontsize=12, fontproperties='SimHei')
            plt.legend(prop={'family': 'SimHei', 'size': 10})
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            output_path = os.path.join(self.output_dir, filename)
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"净值对比图已保存: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"绘制净值对比图失败: {e}")
            return None
    
    def plot_drawdown(
        self,
        nav_series: pd.Series,
        title: str = "回撤曲线",
        filename: str = "drawdown.png"
    ) -> Optional[str]:
        """
        绘制回撤曲线
        
        参数:
            nav_series: 净值序列
            title: 图表标题
            filename: 输出文件名
        
        返回:
            图片文件路径
        """
        if not PLT_AVAILABLE:
            return None
        
        try:
            cummax = nav_series.cummax()
            drawdown = (nav_series - cummax) / cummax * 100
            
            plt.figure(figsize=(14, 5))
            plt.fill_between(drawdown.index, drawdown.values, 0, 
                           color='red', alpha=0.3)
            plt.plot(drawdown.index, drawdown.values, 
                    color='red', linewidth=1.5)
            
            plt.title(title, fontsize=16, fontproperties='SimHei')
            plt.xlabel('日期', fontsize=12, fontproperties='SimHei')
            plt.ylabel('回撤 (%)', fontsize=12, fontproperties='SimHei')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            output_path = os.path.join(self.output_dir, filename)
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"回撤曲线图已保存: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"绘制回撤曲线失败: {e}")
            return None
    
    def plot_returns_distribution(
        self,
        nav_series: pd.Series,
        title: str = "收益率分布",
        filename: str = "returns_dist.png"
    ) -> Optional[str]:
        """
        绘制收益率分布直方图
        
        参数:
            nav_series: 净值序列
            title: 图表标题
            filename: 输出文件名
        
        返回:
            图片文件路径
        """
        if not PLT_AVAILABLE:
            return None
        
        try:
            returns = BacktestMetrics.calculate_returns(nav_series) * 100
            
            plt.figure(figsize=(12, 6))
            plt.hist(returns, bins=50, color='blue', alpha=0.7, edgecolor='black')
            plt.axvline(returns.mean(), color='red', linestyle='--', 
                       linewidth=2, label=f'均值: {returns.mean():.2f}%')
            
            plt.title(title, fontsize=16, fontproperties='SimHei')
            plt.xlabel('日收益率 (%)', fontsize=12, fontproperties='SimHei')
            plt.ylabel('频数', fontsize=12, fontproperties='SimHei')
            plt.legend(prop={'family': 'SimHei', 'size': 10})
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            output_path = os.path.join(self.output_dir, filename)
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"收益率分布图已保存: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"绘制收益率分布图失败: {e}")
            return None
    
    def generate_complete_report(
        self,
        strategy_name: str,
        params: Dict,
        nav_series: pd.Series,
        benchmark_series: pd.Series = None,
        trades: List[Dict] = None
    ) -> Dict[str, str]:
        """
        生成完整报告（包含所有图表和指标）
        
        参数:
            strategy_name: 策略名称
            params: 策略参数
            nav_series: 策略净值序列
            benchmark_series: 基准净值序列
            trades: 交易记录列表
        
        返回:
            {'summary': 文本路径, 'nav_plot': 图片路径, ...}
        """
        # 计算指标
        metrics = BacktestMetrics.calculate_all_metrics(
            nav_series,
            benchmark_series,
            trades
        )
        
        # 生成文本报告
        summary = self.generate_summary_report(
            strategy_name,
            params,
            metrics
        )
        
        # 生成图表
        results = {'summary_text': summary}
        
        # 净值对比图
        nav_dict = {strategy_name: nav_series}
        if benchmark_series is not None:
            nav_dict['基准'] = benchmark_series
        
        nav_plot = self.plot_nav_comparison(
            nav_dict,
            title=f"{strategy_name} - 净值曲线",
            filename=f"{strategy_name}_nav.png"
        )
        if nav_plot:
            results['nav_plot'] = nav_plot
        
        # 回撤图
        dd_plot = self.plot_drawdown(
            nav_series,
            title=f"{strategy_name} - 回撤曲线",
            filename=f"{strategy_name}_drawdown.png"
        )
        if dd_plot:
            results['drawdown_plot'] = dd_plot
        
        # 收益率分布
        ret_plot = self.plot_returns_distribution(
            nav_series,
            title=f"{strategy_name} - 收益率分布",
            filename=f"{strategy_name}_returns_dist.png"
        )
        if ret_plot:
            results['returns_dist_plot'] = ret_plot
        
        logger.info(f"完整报告已生成: {len(results)} 个文件")
        return results
    
    def save_nav_to_csv(
        self,
        nav_series: pd.Series,
        filename: str = "nav.csv"
    ) -> str:
        """
        保存净值序列到CSV
        
        参数:
            nav_series: 净值序列
            filename: 文件名
        
        返回:
            文件路径
        """
        output_path = os.path.join(self.output_dir, filename)
        
        df = pd.DataFrame({
            '日期': nav_series.index,
            '净值': nav_series.values
        })
        
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"净值数据已保存: {output_path}")
        
        return output_path


# 便捷函数
def quick_report(
    strategy_name: str,
    nav_series: pd.Series,
    benchmark_series: pd.Series = None,
    output_dir: str = './reports'
) -> Dict:
    """
    快速生成报告
    
    参数:
        strategy_name: 策略名称
        nav_series: 策略净值
        benchmark_series: 基准净值
        output_dir: 输出目录
    
    返回:
        包含指标和文件路径的字典
    """
    generator = ReportGenerator(output_dir)
    
    # 计算指标
    metrics = BacktestMetrics.calculate_all_metrics(nav_series, benchmark_series)
    
    # 生成报告
    results = generator.generate_complete_report(
        strategy_name,
        {},
        nav_series,
        benchmark_series
    )
    
    results['metrics'] = metrics
    return results
