# -*- coding: utf-8 -*-
"""
策略注册表 - 集中管理所有策略
提供统一的策略创建接口，避免硬编码
"""
from typing import Dict, Tuple, Any, Callable

# 引入现有策略类
from src.strategies.ma_strategies import MACrossStrategy, TripleMACrossStrategy
from src.strategies.macd_strategies import MACDStrategy, MACDZeroCrossStrategy
from src.strategies.rsi_strategies import RSIStrategy
from src.strategies.donchian_strategy import DonchianBreakoutStrategy

# 策略注册表：{key: (class, default_params, description)}
_REGISTRY: Dict[str, Tuple[Callable[..., Any], Dict[str, Any], str]] = {
    "ma_cross": (MACrossStrategy, {"short_window": 5, "long_window": 20}, "双均线交叉"),
    "ma_triple": (TripleMACrossStrategy, {"fast": 5, "mid": 10, "slow": 20}, "三均线策略"),
    "rsi": (RSIStrategy, {"period": 14, "oversold": 30, "overbought": 70}, "RSI超买超卖"),
    "macd": (MACDStrategy, {"fast": 12, "slow": 26, "signal": 9}, "MACD信号"),
    "macd_zero": (MACDZeroCrossStrategy, {"fast": 12, "slow": 26, "signal": 9}, "MACD零轴"),
    "donchian": (DonchianBreakoutStrategy, {"n": 20, "exit_n": 10}, "唐奇安通道突破"),
}

def list_strategies() -> Dict[str, str]:
    """
    列出所有可用策略
    
    Returns:
        {key: description} 字典
    """
    return {k: v[2] for k, v in _REGISTRY.items()}

def create_strategy(key: str, **overrides):
    """
    创建策略实例
    
    Args:
        key: 策略键名
        **overrides: 覆盖默认参数
    
    Returns:
        策略实例
    
    Raises:
        KeyError: 未知策略
    
    Examples:
        >>> strategy = create_strategy('ma_cross')
        >>> strategy = create_strategy('rsi', period=21, oversold=25)
    """
    if key not in _REGISTRY:
        available = ', '.join(_REGISTRY.keys())
        raise KeyError(f"未知策略: {key}。可用策略: {available}")
    
    cls, defaults, _ = _REGISTRY[key]
    params = {**defaults, **overrides}
    return cls(**params)

def register_strategy(key: str, strategy_class: Callable, 
                     default_params: Dict[str, Any], 
                     description: str):
    """
    注册新策略
    
    Args:
        key: 策略键名（唯一）
        strategy_class: 策略类
        default_params: 默认参数
        description: 策略描述
    
    Examples:
        >>> register_strategy(
        ...     'my_strategy',
        ...     MyStrategy,
        ...     {'param1': 10},
        ...     '我的自定义策略'
        ... )
    """
    if key in _REGISTRY:
        print(f"⚠ 警告：策略 '{key}' 已存在，将被覆盖")
    _REGISTRY[key] = (strategy_class, default_params, description)

def get_strategy_info(key: str) -> Dict[str, Any]:
    """
    获取策略详细信息
    
    Args:
        key: 策略键名
    
    Returns:
        策略信息字典
    """
    if key not in _REGISTRY:
        return {}
    
    cls, params, desc = _REGISTRY[key]
    return {
        'class': cls.__name__,
        'default_params': params.copy(),
        'description': desc
    }
