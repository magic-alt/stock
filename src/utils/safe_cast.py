"""
安全类型转换工具
处理 NaN、None、异常值等边界情况
"""

import pandas as pd
import numpy as np
from typing import Union, Any, Optional


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    安全转换为浮点数
    
    处理：NaN、None、异常值
    
    Args:
        value: 待转换的值
        default: 默认值（转换失败时返回）
    
    Returns:
        转换后的浮点数
    
    Examples:
        >>> safe_float(123.45)
        123.45
        >>> safe_float('123.45')
        123.45
        >>> safe_float(float('nan'))
        0.0
        >>> safe_float(None)
        0.0
        >>> safe_float('invalid', 999.0)
        999.0
    """
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    安全转换为整数
    
    处理：NaN、None、异常值
    
    Args:
        value: 待转换的值
        default: 默认值（转换失败时返回）
    
    Returns:
        转换后的整数
    
    Examples:
        >>> safe_int(123.45)
        123
        >>> safe_int('123')
        123
        >>> safe_int(float('nan'))
        0
        >>> safe_int(None)
        0
    """
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return int(float(value))  # 先转float再转int，处理'123.45'这种情况
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = '') -> str:
    """
    安全转换为字符串
    
    Args:
        value: 待转换的值
        default: 默认值
    
    Returns:
        转换后的字符串
    """
    try:
        if value is None or pd.isna(value):
            return default
        return str(value)
    except Exception:
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """
    安全转换为布尔值
    
    Args:
        value: 待转换的值
        default: 默认值
    
    Returns:
        转换后的布尔值
    """
    try:
        if value is None or pd.isna(value):
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 't', 'y')
        return bool(value)
    except Exception:
        return default


def safe_divide(numerator: float, denominator: float, 
                default: float = 0.0) -> float:
    """
    安全除法（处理除零）
    
    Args:
        numerator: 分子
        denominator: 分母
        default: 除零时的默认值
    
    Returns:
        计算结果
    
    Examples:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0.0
        >>> safe_divide(10, 0, float('inf'))
        inf
    """
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except Exception:
        return default


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    将值限制在指定范围内
    
    Args:
        value: 输入值
        min_val: 最小值
        max_val: 最大值
    
    Returns:
        限制后的值
    
    Examples:
        >>> clamp(50, 0, 100)
        50
        >>> clamp(-10, 0, 100)
        0
        >>> clamp(150, 0, 100)
        100
    """
    return max(min_val, min(value, max_val))


def is_valid_number(value: Any) -> bool:
    """
    检查是否为有效数字（非 NaN、非 None、非无穷）
    
    Args:
        value: 待检查的值
    
    Returns:
        是否为有效数字
    """
    try:
        if value is None:
            return False
        if pd.isna(value):
            return False
        f_val = float(value)
        if np.isinf(f_val):
            return False
        return True
    except (ValueError, TypeError):
        return False


def normalize_percentage(value: float, is_decimal: bool = False) -> float:
    """
    标准化百分比值
    
    Args:
        value: 输入值
        is_decimal: 是否已经是小数形式（0.05 表示 5%）
    
    Returns:
        标准化后的百分比值（统一为数值形式，如 5.23 表示 5.23%）
    
    Examples:
        >>> normalize_percentage(5.23)
        5.23
        >>> normalize_percentage(0.0523, is_decimal=True)
        5.23
    """
    if is_decimal:
        return value * 100
    return value
