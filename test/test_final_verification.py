"""最终验证脚本 - 测试所有修复"""
import sys
sys.path.insert(0, 'src')

from src.strategies.registry import list_strategies, _REGISTRY
from src.backtest.backtrader_adapter import run_backtrader_backtest
import pandas as pd
from datetime import datetime

def create_test_data(days=100):
    """创建测试数据"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    return pd.DataFrame({
        '日期': dates,
        '开盘': 100 + (pd.Series(range(days)) * 0.1),
        '最高': 102 + (pd.Series(range(days)) * 0.1),
        '最低': 98 + (pd.Series(range(days)) * 0.1),
        '收盘': 100 + (pd.Series(range(days)) * 0.1),
        '成交量': 1000000
    })

print("=" * 80)
print("最终验证测试")
print("=" * 80)

df = create_test_data(100)
print(f"OK 测试数据准备完成: {len(df)} 条\n")

# 测试1: 传入字符串键（正常情况）
print("测试 1: 传入字符串键 'ma_triple'")
print("-" * 80)
try:
    result = run_backtrader_backtest(df, 'ma_triple', initial_capital=100000)
    if result and isinstance(result, tuple):
        print("OK 测试1通过: 字符串键正常工作\n")
    else:
        print("FAIL 测试1失败: 返回值异常\n")
except Exception as e:
    print(f"FAIL 测试1失败: {e}\n")

# 测试2: 传入 (key, params) 元组
print("测试 2: 传入元组 ('ma_triple', {'fast': 3, 'mid': 7, 'slow': 15})")
print("-" * 80)
try:
    result = run_backtrader_backtest(
        df, 
        ('ma_triple', {'fast': 3, 'mid': 7, 'slow': 15}), 
        initial_capital=100000
    )
    if result and isinstance(result, tuple):
        print("OK 测试2通过: (key, params) 元组正常工作\n")
    else:
        print("FAIL 测试2失败: 返回值异常\n")
except Exception as e:
    print(f"FAIL 测试2失败: {e}\n")

# 测试3: 传入注册表三元组（模拟错误传参）
print("测试 3: 传入注册表三元组 (Class, defaults, desc)")
print("-" * 80)
try:
    registry_entry = _REGISTRY['ma_triple']  # (Class, defaults, desc)
    result = run_backtrader_backtest(df, registry_entry, initial_capital=100000)
    if result and isinstance(result, tuple):
        print("OK 测试3通过: 注册表三元组正常工作\n")
    else:
        print("FAIL 测试3失败: 返回值异常\n")
except Exception as e:
    print(f"FAIL 测试3失败: {e}\n")

# 测试4: 错误的键（应该优雅失败）
print("测试 4: 传入不存在的键 'non_existent'")
print("-" * 80)
try:
    result = run_backtrader_backtest(df, 'non_existent', initial_capital=100000)
    if result is None:
        print("OK 测试4通过: 错误键被正确处理\n")
    else:
        print("FAIL 测试4失败: 应该返回 None\n")
except Exception as e:
    print(f"OK 测试4通过: 错误被正确捕获 ({type(e).__name__})\n")

print("=" * 80)
print("所有测试完成!")
print("=" * 80)
