# -*- coding: utf-8 -*-
"""
Donchian 策略回测示例
对比不同参数下的策略表现
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.data_sources.akshare_source import AKShareDataSource
from src.strategies.registry import create_strategy
from src.backtest.simple_engine import SimpleBacktestEngine
from datetime import datetime, timedelta

print("=" * 90)
print("Donchian 策略回测示例")
print("=" * 90)

# 配置
STOCK_CODE = "600519"  # 贵州茅台
STOCK_NAME = "贵州茅台"
DAYS = 365

# 获取数据
print(f"\n正在获取 {STOCK_NAME}({STOCK_CODE}) 最近 {DAYS} 天数据...")
ds = AKShareDataSource()
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=DAYS + 60)).strftime('%Y%m%d')
df = ds.get_stock_history(STOCK_CODE, start_date, end_date)

if df.empty:
    print("❌ 获取数据失败")
    exit(1)

print(f"✅ 获取到 {len(df)} 条数据")

# 测试不同参数
params_list = [
    {'n': 20, 'exit_n': 10, 'name': '标准参数'},
    {'n': 30, 'exit_n': 15, 'name': '长周期'},
    {'n': 10, 'exit_n': 5, 'name': '短周期'},
]

results = []

for params in params_list:
    print(f"\n{'=' * 90}")
    print(f"测试：{params['name']} (n={params['n']}, exit_n={params['exit_n']})")
    print("=" * 90)
    
    # 创建策略
    strategy = create_strategy('donchian', n=params['n'], exit_n=params['exit_n'])
    
    # 回测引擎
    engine = SimpleBacktestEngine(
        initial_capital=100000,
        commission=0.0003,
        stamp_duty=0.001,
        slippage=0.0001
    )
    
    # 运行回测
    result = engine.run(df, strategy)
    results.append({
        'name': params['name'],
        'params': f"n={params['n']}, exit_n={params['exit_n']}",
        **result
    })
    
    # 显示结果
    print(f"初始资金: {result['initial_capital']:,.2f} 元")
    print(f"最终资金: {result['final_capital']:,.2f} 元")
    print(f"总收益率: {result['total_return']:+.2f}%")
    print(f"买入持有收益率: {result['buy_hold_return']:+.2f}%")
    print(f"相对收益: {result['total_return'] - result['buy_hold_return']:+.2f}%")
    print(f"最大回撤: {result['max_drawdown']:.2f}%")
    print(f"夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate']:.2f}%")
    print(f"平均盈利: {result['avg_profit']:,.2f} 元 ({result['avg_profit_pct']:.2f}%)")

# 对比总结
print(f"\n{'=' * 90}")
print("参数对比总结")
print("=" * 90)
print(f"{'参数':<20s} {'收益率':<12s} {'最大回撤':<12s} {'夏普':<10s} {'胜率':<10s} {'交易次数':<10s}")
print("-" * 90)

for r in results:
    print(f"{r['name']:<20s} "
          f"{r['total_return']:>10.2f}%  "
          f"{r['max_drawdown']:>10.2f}%  "
          f"{r['sharpe_ratio']:>8.2f}  "
          f"{r['win_rate']:>8.2f}%  "
          f"{r['total_trades']:>8d}")

# 推荐参数
best = max(results, key=lambda x: x['total_return'])
print(f"\n🏆 最佳参数: {best['name']} ({best['params']})")
print(f"   收益率: {best['total_return']:+.2f}%")

print("\n" + "=" * 90)
print("✅ 测试完成")
print("=" * 90)
