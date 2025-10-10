#!/usr/bin/env python3
"""
测试新浪数据源的监控器
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.monitors.realtime_monitor import StockMonitor

def test_sina_monitor():
    """测试新浪数据源监控器"""
    
    # 测试股票列表
    watchlist = {
        '600519': '贵州茅台',
        '000001': '平安银行', 
        '300750': '宁德时代'
    }
    
    # 测试指数
    indices = {
        '000001': '上证指数',
        '399001': '深证成指'
    }
    
    print("🔍 测试新浪数据源监控器")
    print("=" * 40)
    
    try:
        # 创建监控器（使用新浪数据源）
        monitor = StockMonitor(
            watchlist=watchlist,
            indices=indices,
            refresh_interval=30,
            data_source='sina'
        )
        
        print("✅ 监控器创建成功")
        
        # 测试显示指数
        print("\n📊 测试指数显示:")
        monitor.display_indices()
        
        # 测试显示股票
        print("\n📈 测试股票显示:")
        monitor.display_stocks()
        
        print("\n✅ 新浪数据源监控器测试成功！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sina_monitor()