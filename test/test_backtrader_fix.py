#!/usr/bin/env python3
"""
测试 Backtrader 修复：验证信号驱动的回测流程
"""

import sys
import pandas as pd
sys.path.insert(0, '.')

from src.strategies.registry import create_strategy
from src.backtest.backtrader_adapter import BacktraderAdapter, BacktraderSignalStrategy, run_backtrader_backtest

def test_signal_generation():
    """测试信号生成"""
    print("=== 测试信号生成 ===")
    
    # 创建测试数据
    dates = pd.date_range('2024-01-01', periods=50, freq='D')
    df = pd.DataFrame({
        '日期': dates,
        '开盘': [100 + i for i in range(50)],
        '最高': [105 + i for i in range(50)],
        '最低': [95 + i for i in range(50)],
        '收盘': [100 + i for i in range(50)],
        '成交量': [1000000] * 50
    })
    
    # 创建策略并生成信号
    try:
        strategy = create_strategy('ma_cross')
        df_with_signals = strategy.generate_signals(df.copy())
        
        print(f"✅ 成功生成 {len(df_with_signals)} 行数据")
        print(f"   包含列: {list(df_with_signals.columns)}")
        
        if 'Signal' in df_with_signals.columns:
            signal_counts = df_with_signals['Signal'].value_counts()
            print(f"   信号分布: {dict(signal_counts)}")
            return df_with_signals
        else:
            print("❌ 未找到 Signal 列")
            return None
            
    except Exception as e:
        print(f"❌ 信号生成失败: {e}")
        return None

def test_backtrader_adapter():
    """测试 Backtrader 适配器"""
    print("\n=== 测试 Backtrader 适配器 ===")
    
    df_sig = test_signal_generation()
    if df_sig is None:
        return False
    
    try:
        # 测试适配器
        adapter = BacktraderAdapter()
        if not adapter.setup(100000):
            print("❌ 适配器初始化失败")
            return False
            
        if not adapter.add_data(df_sig):
            print("❌ 添加数据失败")
            return False
            
        if not adapter.add_strategy(BacktraderSignalStrategy):
            print("❌ 添加策略失败")
            return False
            
        print("✅ Backtrader 适配器配置成功")
        
        # 运行回测（简化版，不打印太多输出）
        results = adapter.run()
        if results:
            print("✅ 回测运行成功")
            return True
        else:
            print("❌ 回测运行失败")
            return False
            
    except Exception as e:
        print(f"❌ Backtrader 适配器测试失败: {e}")
        return False

def test_run_backtrader_backtest():
    """测试完整的 run_backtrader_backtest 函数"""
    print("\n=== 测试完整回测函数 ===")
    
    # 创建测试数据
    dates = pd.date_range('2024-01-01', periods=30, freq='D')
    df = pd.DataFrame({
        '日期': dates,
        '开盘': [100 + i for i in range(30)],
        '最高': [105 + i for i in range(30)],
        '最低': [95 + i for i in range(30)],
        '收盘': [100 + i for i in range(30)],
        '成交量': [1000000] * 30
    })
    
    try:
        results = run_backtrader_backtest(
            df=df,
            strategy_key='ma_cross',
            initial_capital=100000
        )
        
        if results:
            print("✅ 完整回测函数运行成功")
            return True
        else:
            print("❌ 完整回测函数运行失败")
            return False
            
    except Exception as e:
        print(f"❌ 完整回测函数测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Backtrader 修复验证测试")
    print("=" * 50)
    
    try:
        import backtrader as bt
        print("✅ Backtrader 已安装")
    except ImportError:
        print("❌ Backtrader 未安装，跳过测试")
        sys.exit(0)
    
    success = True
    success &= test_signal_generation() is not None
    success &= test_backtrader_adapter()
    success &= test_run_backtrader_backtest()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 所有测试通过！修复成功")
    else:
        print("❌ 部分测试失败")
    
    print("=" * 50)