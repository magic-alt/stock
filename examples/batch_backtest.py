#!/usr/bin/env python3
"""
Batch Backtest Example - 批量回测示例

演示如何批量测试多个股票和多个策略。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine


def main():
    """批量回测示例"""
    print("="*60)
    print("批量回测示例 - 多股票 × 多策略")
    print("="*60)
    
    # 创建引擎
    engine = BacktestEngine(source="akshare", cache_dir="./cache")
    
    # 定义测试参数
    symbols = [
        "600519.SH",  # 贵州茅台
        "601318.SH",  # 中国平安
        "600036.SH",  # 招商银行
    ]
    
    strategies = ["macd", "ema", "bollinger"]
    
    # 运行自动化流程
    print(f"\n开始测试 {len(symbols)} 只股票 × {len(strategies)} 个策略...")
    
    results = engine.auto_pipeline(
        strategies=strategies,
        symbols=symbols,
        start="2023-01-01",
        end="2024-12-31",
        cash=100000,
        adj="qfq",
        hot_only=True,  # 只保留Top 5
        top_n=5,
        workers=2,  # 并行工作进程
        out_dir="./output/batch_test",
    )
    
    print("\n" + "="*60)
    print("✓ 批量回测完成！")
    print(f"  - 结果保存在: ./output/batch_test/")
    print(f"  - 找到 {len(results)} 个优秀策略组合")
    print("="*60)


if __name__ == "__main__":
    main()
