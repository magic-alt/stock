#!/usr/bin/env python3
"""
测试AKShare多数据源自动切换功能
"""

import sys
import os
import time
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_sources.akshare_source import AKShareDataSource, DataSourceType

def test_data_source():
    """测试数据源功能"""
    print("=" * 60)
    print("🧪 AKShare多数据源自动切换功能测试")
    print("=" * 60)
    
    # 创建数据源实例
    ds = AKShareDataSource()
    
    # 1. 测试所有数据源连接状态
    print("\n1️⃣ 测试所有数据源连接状态:")
    print("-" * 40)
    source_results = ds.test_all_sources()
    for source, available in source_results.items():
        status = "✅ 可用" if available else "❌ 不可用"
        print(f"  {source}: {status}")
    
    # 2. 显示当前数据源信息
    print(f"\n2️⃣ 当前数据源信息:")
    print("-" * 40)
    info = ds.get_data_source_info()
    print(f"  当前数据源: {info['current_source']}")
    print(f"  可用数据源: {info['available_sources']}")
    
    # 3. 测试股票数据获取
    print(f"\n3️⃣ 测试股票数据获取:")
    print("-" * 40)
    test_stocks = ['000001', '000002', '600519', '300750']
    
    for stock_code in test_stocks:
        print(f"\n📈 获取股票 {stock_code} 数据:")
        start_time = time.time()
        
        data = ds.get_stock_realtime(stock_code)
        
        elapsed = time.time() - start_time
        
        if data:
            print(f"  ✅ 成功 ({elapsed:.2f}秒)")
            print(f"  名称: {data['名称']}")
            print(f"  最新价: {data['最新价']}")
            print(f"  涨跌幅: {data['涨跌幅']}%")
            print(f"  成交额: {data['成交额']:,.0f}元")
            print(f"  数据源: {data['数据源']}")
        else:
            print(f"  ❌ 失败 ({elapsed:.2f}秒)")
    
    # 4. 测试指数数据获取
    print(f"\n4️⃣ 测试指数数据获取:")
    print("-" * 40)
    test_indices = ['000001', '399001', '399006']
    
    for index_code in test_indices:
        print(f"\n📊 获取指数 {index_code} 数据:")
        start_time = time.time()
        
        data = ds.get_index_realtime(index_code)
        
        elapsed = time.time() - start_time
        
        if data:
            print(f"  ✅ 成功 ({elapsed:.2f}秒)")
            print(f"  名称: {data['名称']}")
            print(f"  最新价: {data['最新价']}")
            print(f"  涨跌幅: {data['涨跌幅']}%")
            print(f"  成交额: {data['成交额']:,.0f}元")
            print(f"  数据源: {data['数据源']}")
        else:
            print(f"  ❌ 失败 ({elapsed:.2f}秒)")
    
    # 5. 测试数据源切换
    print(f"\n5️⃣ 测试数据源切换:")
    print("-" * 40)
    
    current_source = ds.get_current_source()
    print(f"当前数据源: {current_source}")
    
    # 尝试切换到新浪财经
    if DataSourceType.SINA in source_results and source_results[DataSourceType.SINA]:
        print(f"\n尝试切换到新浪财经...")
        ds.force_switch_source(DataSourceType.SINA)
        
        # 测试切换后的数据获取
        print(f"切换后测试获取上证指数数据:")
        data = ds.get_index_realtime('000001')
        if data:
            print(f"  ✅ 成功获取数据，数据源: {data['数据源']}")
            print(f"  上证指数: {data['最新价']} ({data['涨跌幅']}%)")
        else:
            print(f"  ❌ 获取数据失败")
    else:
        print(f"新浪财经数据源不可用，跳过切换测试")
    
    # 6. 显示最终状态
    print(f"\n6️⃣ 最终数据源状态:")
    print("-" * 40)
    final_info = ds.get_data_source_info()
    print(f"  当前数据源: {final_info['current_source']}")
    
    cache_age = final_info['cache_age_seconds']
    if cache_age is not None:
        print(f"  缓存年龄: {cache_age:.1f}秒")
    
    print(f"\n📊 各数据源详细状态:")
    for source, status in final_info['source_status'].items():
        available = "✅" if status.get('available', True) else "❌"
        failures = status.get('consecutive_failures', 0)
        last_success = status.get('last_success')
        success_time = last_success.strftime('%H:%M:%S') if last_success else "无"
        
        print(f"  {available} {source}:")
        print(f"    连续失败: {failures}次")
        print(f"    最后成功: {success_time}")
    
    print("\n" + "=" * 60)
    print("🎉 测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_data_source()
    except KeyboardInterrupt:
        print("\n\n⚠ 用户中断测试")
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()