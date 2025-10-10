"""
调试脚本：追踪成交额数据流
"""

import sys
sys.path.insert(0, '.')

from src.data_sources.akshare_source import AKShareDataSource, _to_yuan, AMOUNT_UNIT_STOCK, AMOUNT_UNIT_INDEX
from src.utils.formatters import format_amount

print("=" * 80)
print("成交额数据流调试")
print("=" * 80)

# 创建数据源
ds = AKShareDataSource()

# 测试个股
print("\n【测试个股 - 宁德时代 300750】")
print("-" * 80)

stock_data = ds.get_stock_realtime('300750')
if stock_data:
    print(f"1. 返回的成交额原始值: {stock_data['成交额']}")
    print(f"   类型: {type(stock_data['成交额'])}")
    
    formatted = format_amount(stock_data['成交额'])
    print(f"2. 格式化后显示: {formatted}")
    
    # 反推原始值
    if '亿' in formatted:
        value = float(formatted.replace('亿', ''))
        original = value * 1e8
    else:
        value = float(formatted.replace('万', ''))
        original = value * 1e4
    
    print(f"3. 反推显示对应的元值: {original:,.0f} 元")
    print(f"4. 预期显示: 应该在100-200亿之间（正常大盘股）")
else:
    print("未获取到数据")

# 测试指数
print("\n【测试指数 - 上证指数 000001】")
print("-" * 80)

index_data = ds.get_index_realtime('000001')
if index_data:
    print(f"1. 返回的成交额原始值: {index_data['成交额']}")
    print(f"   类型: {type(index_data['成交额'])}")
    
    formatted = format_amount(index_data['成交额'])
    print(f"2. 格式化后显示: {formatted}")
    
    # 反推原始值
    if '亿' in formatted:
        value = float(formatted.replace('亿', ''))
        original = value * 1e8
    else:
        value = float(formatted.replace('万', ''))
        original = value * 1e4
    
    print(f"3. 反推显示对应的元值: {original:,.0f} 元")
    print(f"4. 预期显示: 应该在5000-10000亿之间（正常沪市规模）")
else:
    print("未获取到数据")

# 测试转换函数
print("\n【测试单位转换函数】")
print("-" * 80)

test_cases = [
    (119819.25, AMOUNT_UNIT_STOCK, "宁德时代原始值（万元）"),
    (7121.34, AMOUNT_UNIT_INDEX, "上证指数原始值（亿元）"),
]

for raw, unit, desc in test_cases:
    converted = _to_yuan(raw, unit)
    formatted = format_amount(converted)
    print(f"{desc}")
    print(f"  原始: {raw:,.2f} ({unit})")
    print(f"  转换: {converted:,.0f} 元")
    print(f"  显示: {formatted}")
    print()
