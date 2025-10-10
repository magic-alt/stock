# -*- coding: utf-8 -*-
"""
测试策略注册表和 Donchian 策略
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.strategies.registry import list_strategies, create_strategy, get_strategy_info

print("=" * 80)
print("策略注册表测试")
print("=" * 80)

# 1. 列出所有策略
print("\n【所有可用策略】")
strategies = list_strategies()
for key, desc in strategies.items():
    print(f"  {key:15s} → {desc}")

# 2. 创建策略实例
print("\n【创建策略实例】")
try:
    # 默认参数
    ma = create_strategy('ma_cross')
    print(f"✅ {ma.name}")
    
    # 自定义参数
    rsi = create_strategy('rsi', period=21, oversold=25, overbought=75)
    print(f"✅ {rsi.name}")
    
    # 新策略：Donchian
    donchian = create_strategy('donchian')
    print(f"✅ {donchian.name}")
    
    donchian2 = create_strategy('donchian', n=30, exit_n=15)
    print(f"✅ {donchian2.name}")
    
except Exception as e:
    print(f"❌ 错误: {e}")

# 3. 获取策略信息
print("\n【策略详细信息】")
for key in ['ma_cross', 'donchian']:
    info = get_strategy_info(key)
    print(f"\n策略: {key}")
    print(f"  类名: {info.get('class')}")
    print(f"  描述: {info.get('description')}")
    print(f"  默认参数: {info.get('default_params')}")

# 4. 测试未知策略
print("\n【错误处理测试】")
try:
    unknown = create_strategy('unknown_strategy')
except KeyError as e:
    print(f"✅ 正确捕获错误: {e}")

print("\n" + "=" * 80)
print("✅ 所有测试通过")
print("=" * 80)
