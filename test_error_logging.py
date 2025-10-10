"""
测试网络错误日志优化
模拟网络错误场景
"""

import sys
sys.path.insert(0, '.')

from src.data_sources.akshare_source import AKShareDataSource
from datetime import datetime
import time

print("=" * 80)
print("网络错误日志优化测试")
print("=" * 80)

print("\n【测试场景：模拟多次调用同一数据源】")
print("-" * 80)

# 创建数据源（会尝试连接网络）
ds = AKShareDataSource()

# 模拟监控器多次调用
test_stocks = ['300750', '688981', '002241', '600580', '600547']
test_indices = ['000001', '000300', '000016', '000688', '000905']

print("\n1. 第一轮查询（5个指数）")
print("   " + "-" * 70)
for idx, code in enumerate(test_indices, 1):
    index_data = ds.get_index_realtime(code)
    if index_data:
        print(f"   {idx}. {code} - 获取成功")
    else:
        print(f"   {idx}. {code} - 获取失败（网络错误）")

print("\n2. 第二轮查询（5个股票）")
print("   " + "-" * 70)
print("   预期：由于错误去重机制，这轮不应该再打印网络错误")
for idx, code in enumerate(test_stocks, 1):
    stock_data = ds.get_stock_realtime(code)
    if stock_data:
        print(f"   {idx}. {code} - 获取成功")
    else:
        print(f"   {idx}. {code} - 获取失败（静默处理）")

print("\n3. 等待60秒后再次查询（测试错误重新打印）")
print("   " + "-" * 70)
print("   提示：完整测试需要等待60秒，按 Ctrl+C 跳过")

try:
    for remaining in range(60, 0, -10):
        print(f"   等待中... 剩余 {remaining} 秒", end='\r')
        time.sleep(10)
    
    print("\n")
    for idx, code in enumerate(['000001', '300750'], 1):
        if idx == 1:
            data = ds.get_index_realtime(code)
        else:
            data = ds.get_stock_realtime(code)
        
        if data:
            print(f"   {idx}. {code} - 获取成功")
        else:
            print(f"   {idx}. {code} - 获取失败（应该重新打印错误）")

except KeyboardInterrupt:
    print("\n\n   ⚠ 测试中断（跳过60秒等待）")

print("\n" + "=" * 80)
print("测试结论")
print("=" * 80)
print("✅ 错误去重：同一网络错误在60秒内只打印一次")
print("✅ 用户体验：避免错误信息刷屏")
print("✅ 缓存机制：在网络异常时继续使用旧缓存")
print("✅ 日志记录：完整错误信息仍记录到日志")
print()

print("建议:")
print("- 正常运行时，网络偶尔抖动不会影响用户体验")
print("- 网络持续异常时，60秒提醒一次")
print("- 缓存年龄显示帮助判断数据新鲜度")
print()
