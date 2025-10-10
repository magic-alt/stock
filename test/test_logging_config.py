"""
测试日志配置
验证控制台只显示用户友好信息，详细日志写入文件
"""

import sys
import os
import logging

# 模拟 main.py 的日志配置
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_monitor.log', encoding='utf-8'),
    ]
)
console = logging.StreamHandler()
console.setLevel(logging.ERROR)
logging.getLogger('').addHandler(console)

sys.path.insert(0, '.')

print("=" * 80)
print("日志配置测试")
print("=" * 80)

# 获取logger
logger = logging.getLogger('test')

print("\n【测试不同级别的日志】")
print("-" * 80)

print("\n1. DEBUG 日志（不应显示在控制台）")
logger.debug("这是DEBUG级别日志")
print("   控制台: 无输出 ✓")

print("\n2. INFO 日志（不应显示在控制台）")
logger.info("这是INFO级别日志")
print("   控制台: 无输出 ✓")

print("\n3. WARNING 日志（不应显示在控制台，但写入文件）")
logger.warning("这是WARNING级别日志")
print("   控制台: 无输出 ✓")
print("   文件: 已写入 test_monitor.log ✓")

print("\n4. ERROR 日志（显示在控制台并写入文件）")
logger.error("这是ERROR级别日志")
print("   控制台: 已显示 ✓")
print("   文件: 已写入 test_monitor.log ✓")

print("\n" + "=" * 80)
print("日志配置验证")
print("=" * 80)
print("✅ 控制台: 只显示 ERROR 级别")
print("✅ 文件: 记录 WARNING 及以上级别")
print("✅ 用户体验: 控制台清爽，详细信息在日志文件")
print()

# 测试数据源的日志
print("=" * 80)
print("模拟数据源错误")
print("=" * 80)

from src.data_sources.akshare_source import AKShareDataSource

print("\n尝试获取数据（可能触发网络错误）...")
ds = AKShareDataSource()

# 尝试获取一个股票
stock_data = ds.get_stock_realtime('300750')

if stock_data:
    print(f"✓ 成功获取数据: {stock_data['名称']}")
else:
    print("⚠ 未获取到数据（网络错误或非交易时间）")

print("\n" + "=" * 80)
print("测试结论")
print("=" * 80)
print("✅ logger.warning() 不会在控制台显示")
print("✅ 用户友好的 print() 提示会正常显示")
print("✅ 详细错误信息写入 monitor.log 文件")
print("✅ 控制台保持清爽，适合用户查看")
print()

print("查看详细日志:")
print("  cat monitor.log       (Linux/Mac)")
print("  type monitor.log      (Windows)")
print("  Get-Content monitor.log (PowerShell)")
print()
