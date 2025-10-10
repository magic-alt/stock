#!/usr/bin/env python3
"""
快速数据测试脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_sources.sina_source import SinaDataSource

def main():
    print("🔍 快速数据源测试")
    print("=" * 30)
    
    # 创建新浪数据源
    sina = SinaDataSource()
    
    # 测试股票
    test_codes = ['600519', '000001', '300750']
    
    for code in test_codes:
        print(f"\n📊 测试股票: {code}")
        data = sina.get_stock_realtime(code)
        
        if data:
            print(f"  ✅ {data.get('名称', 'N/A')}: {data.get('最新价', 'N/A')}")
            print(f"  📈 涨跌幅: {data.get('涨跌幅', 'N/A'):.2f}%")
        else:
            print(f"  ❌ 获取失败")

if __name__ == "__main__":
    main()
