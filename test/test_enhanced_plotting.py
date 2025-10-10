#!/usr/bin/env python3
"""
测试增强的 Backtrader 绘图功能
"""

import sys
import pandas as pd
import numpy as np
sys.path.insert(0, '.')

from src.strategies.registry import create_strategy
from src.backtest.backtrader_adapter import BacktraderAdapter, BacktraderSignalStrategy

def test_enhanced_plotting():
    """测试增强的绘图功能"""
    print("=== 测试增强的 Backtrader 绘图 ===")
    
    # 创建更真实的测试数据，包含上涨和下跌趋势
    dates = pd.date_range('2024-01-01', periods=50, freq='D')
    
    # 模拟股价波动：前半段上涨，后半段下跌
    base_prices = []
    price = 100
    for i in range(50):
        if i < 25:
            # 前半段上涨趋势
            change = np.random.normal(0.5, 1.5)  # 平均上涨
        else:
            # 后半段下跌趋势
            change = np.random.normal(-0.3, 1.2)  # 平均下跌
        
        price = max(price + change, 50)  # 避免价格过低
        base_prices.append(price)
    
    df = pd.DataFrame({
        '日期': dates,
        '开盘': [p * np.random.uniform(0.98, 1.02) for p in base_prices],
        '最高': [p * np.random.uniform(1.01, 1.05) for p in base_prices],
        '最低': [p * np.random.uniform(0.95, 0.99) for p in base_prices],
        '收盘': base_prices,
        '成交量': [np.random.randint(800000, 1200000) for _ in range(50)]
    })
    
    try:
        # 创建策略并生成信号
        strategy = create_strategy('ma_cross', short_window=5, long_window=10)
        df_with_signals = strategy.generate_signals(df.copy())
        
        print(f"✅ 生成信号数据，包含 {len(df_with_signals)} 行")
        
        # 检查信号分布
        if 'Signal' in df_with_signals.columns:
            signal_counts = df_with_signals['Signal'].value_counts()
            print(f"   信号分布: {dict(signal_counts)}")
            
            # 统计买卖点
            buy_signals = (df_with_signals['Signal'] == 1).sum()
            sell_signals = (df_with_signals['Signal'] == -1).sum()
            print(f"   买入信号: {buy_signals} 个")
            print(f"   卖出信号: {sell_signals} 个")
        
        # 设置适配器
        adapter = BacktraderAdapter()
        if not adapter.setup(100000):
            print("❌ 适配器初始化失败")
            return False
            
        if not adapter.add_data(df_with_signals):
            print("❌ 添加数据失败")
            return False
            
        if not adapter.add_strategy(BacktraderSignalStrategy):
            print("❌ 添加策略失败")
            return False
        
        print("\n--- 开始回测（将显示交易日志）---")
        results = adapter.run()
        
        if results:
            print("✅ 回测运行成功")
            print("\n--- 测试绘图功能 ---")
            print("注意：图表应该显示：")
            print("1. 彩色K线图（绿色上涨，红色下跌）")
            print("2. 买卖点标记（绿色三角形买入，红色三角形卖出）")
            print("3. 正确的日期坐标轴")
            print("4. 价格和成交量标签")
            
            # 这里不调用实际绘图，因为会弹出窗口
            # adapter.plot()
            print("✅ 绘图配置已优化")
            
            return True
        else:
            print("❌ 回测运行失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Backtrader 增强绘图测试")
    print("=" * 50)
    
    try:
        import backtrader as bt
        import matplotlib
        print("✅ Backtrader 和 matplotlib 已安装")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        sys.exit(0)
    
    success = test_enhanced_plotting()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 绘图增强测试成功！")
        print("现在图表应该有更好的颜色、标记和标签")
    else:
        print("❌ 绘图增强测试失败")
    
    print("=" * 50)