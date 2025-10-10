"""交互式测试脚本 - 模拟 main.py 的完整流程"""
import sys
sys.path.insert(0, 'src')

from src.strategies.registry import list_strategies
from src.backtest.backtrader_adapter import run_backtrader_backtest
from src.data_sources import DataSourceFactory
from src.config import BACKTEST_CONFIG
from datetime import datetime, timedelta

print("=" * 80)
print("模拟完整交互流程")
print("=" * 80)

# 1. 模拟策略选择（完全按照 main.py 的逻辑）
all_strats = list_strategies()
keys = list(all_strats.keys())

print("\n选择回测策略（来自注册表）:")
for i, k in enumerate(keys, 1):
    print(f"{i:2d}. {k:18s} - {all_strats[k]}")

# 自动选择 ma_triple (索引 2)
idx = 2
strategy_key = keys[idx - 1]

print(f"\n[自动选择] 策略 {idx}: {strategy_key}")
print(f"[DEBUG main.py] strategy_key type: {type(strategy_key)}")
print(f"[DEBUG main.py] strategy_key repr: {repr(strategy_key)}")

# 2. 获取数据（使用 AKShare）
stock_code = "603986"
stock_name = "兆易创新"
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=150)).strftime('%Y%m%d')

print(f"\n正在获取 {stock_name}({stock_code}) 的历史数据...")
print(f"时间范围: {start_date} 至 {end_date}")

try:
    from src.data_sources import DataSourceFactory
    data_source = DataSourceFactory.create('akshare')
    df = data_source.get_stock_history(stock_code, start_date, end_date)
    
    if df.empty:
        print("获取数据失败，使用模拟数据")
        import pandas as pd
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        df = pd.DataFrame({
            '日期': dates,
            '开盘': 100 + (pd.Series(range(100)) * 0.1),
            '最高': 102 + (pd.Series(range(100)) * 0.1),
            '最低': 98 + (pd.Series(range(100)) * 0.1),
            '收盘': 100 + (pd.Series(range(100)) * 0.1),
            '成交量': 1000000
        })
    
    print(f"获取到 {len(df)} 条数据")
    
except Exception as e:
    print(f"数据获取异常: {e}")
    import pandas as pd
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    df = pd.DataFrame({
        '日期': dates,
        '开盘': 100 + (pd.Series(range(100)) * 0.1),
        '最高': 102 + (pd.Series(range(100)) * 0.1),
        '最低': 98 + (pd.Series(range(100)) * 0.1),
        '收盘': 100 + (pd.Series(range(100)) * 0.1),
        '成交量': 1000000
    })
    print(f"使用模拟数据: {len(df)} 条")

# 3. 运行回测（完全按照 main.py 的逻辑）
print(f"\n使用策略 {strategy_key} 进行回测（Backtrader）...")
print(f"[DEBUG before call] Passing strategy_key: {repr(strategy_key)}")

result_tuple = run_backtrader_backtest(
    df=df,
    strategy_key=strategy_key,
    initial_capital=BACKTEST_CONFIG['initial_capital']
)

# run_backtrader_backtest 现在返回 (results, adapter)
results = None
adapter = None
if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
    results, adapter = result_tuple
else:
    results = result_tuple

if results:
    print("\n✅ 回测完成！")
else:
    print("\n❌ 回测失败")
