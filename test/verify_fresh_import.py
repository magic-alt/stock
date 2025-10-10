"""
完整验证：清理缓存并重新测试
"""

import sys
import os

# 清理已导入的模块
modules_to_remove = [k for k in sys.modules.keys() if k.startswith('src.')]
for mod in modules_to_remove:
    del sys.modules[mod]

print("=" * 80)
print("清理模块缓存并重新测试")
print("=" * 80)

# 重新导入
sys.path.insert(0, '.')
from src.data_sources.akshare_source import AKShareDataSource
from src.utils.formatters import format_amount

print("\n✅ 模块已重新加载")

# 模拟数据测试
print("\n【模拟真实数据流】")
print("-" * 80)

# 模拟 AKShare 返回的数据（万元）
mock_stock_amount_wan = 119819.25  # 宁德时代实际成交额（万元）
mock_index_amount_yi = 7121.34     # 上证指数实际成交额（亿元）

print(f"1. AKShare 个股原始数据: {mock_stock_amount_wan:,.2f} 万元")
print(f"2. AKShare 指数原始数据: {mock_index_amount_yi:,.2f} 亿元")

# 模拟数据源转换
from src.data_sources.akshare_source import _to_yuan, AMOUNT_UNIT_STOCK, AMOUNT_UNIT_INDEX

stock_yuan = _to_yuan(mock_stock_amount_wan, AMOUNT_UNIT_STOCK)
index_yuan = _to_yuan(mock_index_amount_yi, AMOUNT_UNIT_INDEX)

print(f"\n3. 数据源转换为元:")
print(f"   个股: {stock_yuan:,.0f} 元")
print(f"   指数: {index_yuan:,.0f} 元")

# 模拟格式化显示
stock_display = format_amount(stock_yuan)
index_display = format_amount(index_yuan)

print(f"\n4. 格式化显示:")
print(f"   个股: {stock_display}")
print(f"   指数: {index_display}")

print(f"\n5. 验证:")
expected_stock = "11.98亿"
expected_index = "7121.34亿"

stock_ok = stock_display == expected_stock
index_ok = index_display == expected_index

print(f"   个股: {'✅ 正确' if stock_ok else f'❌ 错误 (期望 {expected_stock})'}")
print(f"   指数: {'✅ 正确' if index_ok else f'❌ 错误 (期望 {expected_index})'}")

if stock_ok and index_ok:
    print("\n" + "=" * 80)
    print("✅ 所有测试通过！")
    print("=" * 80)
    print("\n如果 main.py 仍显示错误，请:")
    print("1. 完全退出当前运行的 main.py 进程（Ctrl+C）")
    print("2. 关闭终端窗口")
    print("3. 打开新终端窗口")
    print("4. 重新运行: python main.py")
    print("\n原因: Python 进程会缓存已导入的模块，必须重启进程才能加载新代码")
else:
    print("\n" + "=" * 80)
    print("❌ 测试失败！请检查代码")
    print("=" * 80)
