"""
测试格式化工具函数
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.formatters import (
    format_amount, format_percent, format_change,
    format_price, format_volume, format_shares,
    format_large_number
)
from src.utils.safe_cast import (
    safe_float, safe_int, safe_str, safe_divide,
    is_valid_number
)
from src.utils.timebox import (
    is_trading_session, get_trading_status, get_trading_hint
)
import pandas as pd
from datetime import datetime, time


def test_formatters():
    """测试格式化函数"""
    print("=" * 80)
    print("测试格式化工具函数")
    print("=" * 80)
    
    print("\n1. 成交额格式化（format_amount）- 输入单位：元")
    print("-" * 80)
    test_cases = [
        (690275671200, "6902.76亿"),    # 上证指数典型成交额（亿元级别）
        (11483977500, "114.84亿"),      # 宁德时代典型成交额（百亿级）
        (1500000000, "15.00亿"),        # 15亿元
        (500000000, "5.00亿"),          # 5亿元
        (50000000, "5000.00万"),        # 5千万元
        (0, "0.00万"),                  # 0元
    ]
    
    for amount, expected in test_cases:
        result = format_amount(amount)
        status = "✓" if result == expected else "✗"
        print(f"{status} {amount:15.0f}元 -> {result:15s} (预期: {expected})")
    
    print("\n2. 涨跌幅格式化（format_change）")
    print("-" * 80)
    test_cases = [
        (5.23, "+5.23% ↑"),
        (-3.12, "-3.12% ↓"),
        (0, "0.00% -"),
    ]
    
    for value, expected in test_cases:
        result = format_change(value)
        status = "✓" if result == expected else "✗"
        print(f"{status} {value:6.2f} -> {result:15s} (预期: {expected})")
    
    print("\n3. 股数格式化（format_shares）")
    print("-" * 80)
    test_cases = [
        (300, "300股 (3手)"),
        (10000, "10000股 (100手)"),
        (100, "100股 (1手)"),
    ]
    
    for shares, expected in test_cases:
        result = format_shares(shares)
        status = "✓" if result == expected else "✗"
        print(f"{status} {shares:5d} -> {result:20s} (预期: {expected})")
    
    print("\n4. 成交量格式化（format_volume）")
    print("-" * 80)
    test_cases = [
        (1234567890, "1.23亿手"),
        (12345678, "123.46万手"),
        (5000, "5000手"),
    ]
    
    for volume, expected in test_cases:
        result = format_volume(volume)
        print(f"  {volume:12d} -> {result:15s} (预期: {expected})")


def test_safe_cast():
    """测试安全转换函数"""
    print("\n" + "=" * 80)
    print("测试安全转换函数")
    print("=" * 80)
    
    print("\n1. safe_float")
    print("-" * 80)
    test_cases = [
        (123.45, 123.45),
        ('123.45', 123.45),
        (float('nan'), 0.0),
        (None, 0.0),
        ('invalid', 0.0),
    ]
    
    for value, expected in test_cases:
        result = safe_float(value)
        status = "✓" if result == expected else "✗"
        print(f"{status} safe_float({repr(value):20s}) = {result:8.2f} (预期: {expected})")
    
    print("\n2. safe_int")
    print("-" * 80)
    test_cases = [
        (123.45, 123),
        ('123', 123),
        (float('nan'), 0),
        (None, 0),
    ]
    
    for value, expected in test_cases:
        result = safe_int(value)
        status = "✓" if result == expected else "✗"
        print(f"{status} safe_int({repr(value):20s}) = {result:5d} (预期: {expected})")
    
    print("\n3. safe_divide")
    print("-" * 80)
    test_cases = [
        (10, 2, 5.0),
        (10, 0, 0.0),
        (10, 0, float('inf'), float('inf')),  # 自定义默认值
    ]
    
    for *args, expected in test_cases:
        if len(args) == 3:
            result = safe_divide(args[0], args[1], args[2])
        else:
            result = safe_divide(args[0], args[1])
        status = "✓" if result == expected else "✗"
        print(f"{status} safe_divide{tuple(args)} = {result} (预期: {expected})")
    
    print("\n4. is_valid_number")
    print("-" * 80)
    test_cases = [
        (123.45, True),
        (0, True),
        (float('nan'), False),
        (None, False),
        (float('inf'), False),
    ]
    
    for value, expected in test_cases:
        result = is_valid_number(value)
        status = "✓" if result == expected else "✗"
        print(f"{status} is_valid_number({repr(value):20s}) = {result} (预期: {expected})")


def test_timebox():
    """测试交易时间函数"""
    print("\n" + "=" * 80)
    print("测试交易时间函数")
    print("=" * 80)
    
    # 测试不同时间点
    test_times = [
        (datetime(2025, 10, 10, 10, 30), "交易中", "周五上午交易"),
        (datetime(2025, 10, 10, 12, 30), "午间休市", "周五午休"),
        (datetime(2025, 10, 10, 14, 30), "交易中", "周五下午交易"),
        (datetime(2025, 10, 10, 18, 30), "盘后", "周五盘后"),
        (datetime(2025, 10, 11, 10, 30), "周末", "周六"),
        (datetime(2025, 10, 12, 10, 30), "周末", "周日"),
        (datetime(2025, 10, 10, 9, 20), "集合竞价", "集合竞价"),
    ]
    
    print("\n交易状态判定:")
    print("-" * 80)
    for dt, expected, desc in test_times:
        result = get_trading_status(dt)
        status = "✓" if result == expected else "✗"
        print(f"{status} {dt.strftime('%Y-%m-%d %H:%M')} | {result:10s} | {desc}")
    
    print("\n当前交易提示:")
    print("-" * 80)
    current_hint = get_trading_hint()
    print(current_hint)


def test_integration():
    """集成测试：模拟实际使用场景"""
    print("\n" + "=" * 80)
    print("集成测试")
    print("=" * 80)
    
    print("\n模拟股票数据处理:")
    print("-" * 80)
    
    # 模拟数据（包含NaN）
    mock_data = {
        '最新价': 282.50,
        '涨跌幅': 5.23,
        '成交额': 3500000,  # 350亿
        '成交量': 123456789,
        '换手率': float('nan'),  # NaN值
    }
    
    print(f"原始数据: {mock_data}")
    print(f"\n处理后:")
    print(f"  最新价: {safe_float(mock_data['最新价'])} 元")
    print(f"  涨跌幅: {format_change(safe_float(mock_data['涨跌幅']))}")
    print(f"  成交额: {format_amount(safe_float(mock_data['成交额']))}")
    print(f"  成交量: {format_volume(safe_int(mock_data['成交量']))}")
    print(f"  换手率: {safe_float(mock_data['换手率']):.2f}% (NaN->0)")


def main():
    """运行所有测试"""
    print("\n")
    print("*" * 80)
    print("工具函数测试套件")
    print("*" * 80)
    
    test_formatters()
    test_safe_cast()
    test_timebox()
    test_integration()
    
    print("\n" + "*" * 80)
    print("✅ 所有工具函数测试完成！")
    print("*" * 80)
    print()


if __name__ == "__main__":
    main()
