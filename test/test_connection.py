"""
测试脚本 - 验证akshare库和基本功能
"""

import akshare as ak
import pandas as pd
from datetime import datetime

print("=" * 80)
print("测试A股数据获取功能")
print("=" * 80)

# 测试1: 获取指数数据
print("\n[测试1] 获取指数实时数据...")
try:
    df = ak.stock_zh_index_spot_em()
    print("✓ 成功获取指数数据")
    print(f"  数据条数: {len(df)}")
    
    # 显示上证指数
    sh_index = df[df['代码'] == '000001']
    if not sh_index.empty:
        print(f"  上证指数: {sh_index.iloc[0]['最新价']}")
except Exception as e:
    print(f"✗ 失败: {e}")

# 测试2: 获取股票实时数据
print("\n[测试2] 获取股票实时数据...")
try:
    df = ak.stock_zh_a_spot_em()
    print("✓ 成功获取股票数据")
    print(f"  数据条数: {len(df)}")
    
    # 查找贵州茅台
    maotai = df[df['代码'] == '600519']
    if not maotai.empty:
        info = maotai.iloc[0]
        print(f"  贵州茅台: {info['名称']}")
        print(f"    最新价: {info['最新价']}")
        print(f"    涨跌幅: {info['涨跌幅']}%")
except Exception as e:
    print(f"✗ 失败: {e}")

# 测试3: 获取历史数据
print("\n[测试3] 获取历史数据...")
try:
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = '20241001'
    
    df = ak.stock_zh_a_hist(symbol='600519', period="daily", 
                           start_date=start_date, end_date=end_date, adjust="qfq")
    print("✓ 成功获取历史数据")
    print(f"  数据条数: {len(df)}")
    if not df.empty:
        print(f"  最新日期: {df.iloc[-1]['日期']}")
        print(f"  最新收盘价: {df.iloc[-1]['收盘']}")
except Exception as e:
    print(f"✗ 失败: {e}")

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
print("\n如果所有测试都通过，你可以运行主程序：")
print("  python stock_monitor.py")
