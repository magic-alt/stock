#!/usr/bin/env python3
"""
Quick Start Example - 快速开始示例

演示如何使用统一回测框架进行基本的策略回测。
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine
from src.backtest.strategy_modules import STRATEGY_REGISTRY


def main():
    """快速开始示例"""
    print("="*60)
    print("快速开始示例 - 单策略回测")
    print("="*60)
    
    # 1. 创建回测引擎
    engine = BacktestEngine(
        source="akshare",  # 数据源
        cache_dir="./cache",  # 缓存目录
    )
    
    # 2. 运行单次回测
    print("\n正在运行MACD策略回测...")
    metrics = engine.run_single(
        strategy_name="macd",
        symbols=["600519.SH"],  # 贵州茅台
        start="2023-01-01",
        end="2024-12-31",
        cash=100000,  # 10万初始资金
        commission=0.001,  # 0.1%手续费
        adj="qfq",  # 前复权
    )
    
    # 3. 打印结果
    print("\n" + "="*60)
    print("回测结果")
    print("="*60)
    print(f"总收益率: {metrics.get('total_return', 0):.2f}%")
    print(f"年化收益率: {metrics.get('annual_return', 0):.2f}%")
    print(f"夏普比率: {metrics.get('sharpe_ratio', 0):.4f}")
    print(f"最大回撤: {metrics.get('max_drawdown', 0):.2f}%")
    print(f"胜率: {metrics.get('win_rate', 0):.2f}%")
    print("="*60)
    
    print("\n✓ 快速开始示例完成！")
    print("\n提示:")
    print("  - 查看更多示例: examples/")
    print("  - 查看完整文档: docs/")
    print("  - 运行GUI界面: python scripts/backtest_gui.py")


if __name__ == "__main__":
    main()
