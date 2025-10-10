#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试新策略CLI功能
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.strategies.registry import list_strategies, create_strategy

def test_new_strategies():
    """测试新增策略"""
    print("=== 测试新增策略 ===")
    
    new_strategies = [
        'ema_cross', 'kama_cross', 'macd_hist', 'rsi_ma', 'donchian_atr'
    ]
    
    for strategy_key in new_strategies:
        try:
            strategy = create_strategy(strategy_key)
            print(f"✅ {strategy_key:<15}: {strategy.name}")
        except Exception as e:
            print(f"❌ {strategy_key:<15}: {e}")
    
    print(f"\n总计策略数: {len(list_strategies())}")

def test_ml_strategy():
    """测试机器学习策略（可能需要sklearn）"""
    print("\n=== 测试机器学习策略 ===")
    try:
        strategy = create_strategy('ml_walk', min_train=50, prob_threshold=0.6)
        print(f"✅ ml_walk: {strategy.name}")
        print("   注意：需要sklearn支持完整功能")
    except Exception as e:
        print(f"⚠️ ml_walk: {e}")
        print("   提示：如需使用请安装: pip install scikit-learn")

if __name__ == "__main__":
    test_new_strategies()
    test_ml_strategy()
    print("\n=== 策略测试完成 ===")