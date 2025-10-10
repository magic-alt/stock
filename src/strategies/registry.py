# -*- coding: utf-8 -*-
"""
策略注册表 - 集中管理所有策略
提供统一的策略创建接口，避免硬编码
"""
from typing import Dict, Tuple, Any, Callable

# 引入现有策略类
from src.strategies.ma_strategies import (
    MACrossStrategy, TripleMACrossStrategy, EMACrossStrategy, KAMACrossStrategy
)
from src.strategies.macd_strategies import (
    MACDStrategy, MACDZeroCrossStrategy, MACDHistogramMomentum
)
from src.strategies.rsi_strategies import RSIStrategy, RSIMaFilterStrategy
from src.strategies.donchian_strategy import DonchianBreakoutStrategy
from src.strategies.ml_strategies import MLWalkForwardStrategy
from src.strategies.futures_strategies import FuturesMACrossStrategy, FuturesGridStrategy, FuturesMarketMakingStrategy, TurtleFuturesStrategy
from src.strategies.arbitrage_strategies import CrossCommodityArbStrategy, CalendarSpreadArbStrategy, AlphaHedgeStrategy
from src.strategies.auction_strategies import AuctionOpenSelectionStrategy
from src.strategies.multifactor_strategies import MultiFactorSelectionStrategy, IndexEnhancementStrategy, IndustryRotationOverlay
from src.strategies.intraday_strategies import IntradayReversionStrategy

# 策略注册表：{key: (class, default_params, description)}
_REGISTRY: Dict[str, Tuple[Callable[..., Any], Dict[str, Any], str]] = {
    "ma_cross": (MACrossStrategy, {"short_window": 5, "long_window": 20}, "双均线交叉"),
    "ma_triple": (TripleMACrossStrategy, {"fast": 5, "mid": 10, "slow": 20}, "三均线策略"),
    "rsi": (RSIStrategy, {"period": 14, "oversold": 30, "overbought": 70}, "RSI超买超卖"),
    "macd": (MACDStrategy, {"fast": 12, "slow": 26, "signal": 9}, "MACD信号"),
    "macd_zero": (MACDZeroCrossStrategy, {"fast": 12, "slow": 26, "signal": 9}, "MACD零轴"),
    "donchian": (DonchianBreakoutStrategy, {"n": 20, "exit_n": 10}, "唐奇安通道突破"),
    "ema_cross": (EMACrossStrategy, {"fast": 12, "slow": 26, "vol_filter": 0.0}, "EMA交叉+波动过滤"),
    "kama_cross": (KAMACrossStrategy, {"fast_ema": 2, "slow_ema": 30, "er_window": 10}, "KAMA自适应交叉"),
    "macd_hist": (MACDHistogramMomentum, {"fast": 12, "slow": 26, "signal": 9, "thresh": 0.0}, "MACD直方图动量"),
    "rsi_ma": (RSIMaFilterStrategy, {"period": 14, "oversold": 30, "ma": 200}, "RSI超跌+MA趋势过滤"),
    "donchian_atr": (DonchianBreakoutStrategy, {"n": 20, "exit_n": 10, "confirm": 2, "atr_stop": 2.0}, "Donchian+ATR止损"),
    "ml_walk": (MLWalkForwardStrategy, {"label_horizon": 1, "min_train": 200, "prob_threshold": 0.55, "model": "auto"}, "机器学习走步预测"),

    # —— 新增：期货 ——
    "fut_ma_cross": (FuturesMACrossStrategy, {"short_window": 9, "long_window": 34}, "双均线策略(期货)"),
    "fut_grid": (FuturesGridStrategy, {"grid_pct": 0.004, "layers": 6, "max_pos": 3}, "网格交易(期货)"),
    "fut_maker": (FuturesMarketMakingStrategy, {"band_pct": 0.003, "inventory_limit": 2}, "做市商交易(期货)"),
    "turtle": (TurtleFuturesStrategy, {"entry_n": 20, "exit_n": 10, "atr_mult": 2.0}, "海龟交易法(期货)"),

    # —— 新增：套利/对冲 ——
    "alpha_hedge": (AlphaHedgeStrategy, {"beta_window": 60, "hedge_col": "对冲收盘"}, "alpha对冲(股票+期货)"),
    "x_commodity_arb": (CrossCommodityArbStrategy, {"hedge_col": "对冲收盘", "z_window": 60, "z_entry": 1.5, "z_exit": 0.5}, "跨品种套利(期货)"),
    "calendar_spread": (CalendarSpreadArbStrategy, {"near_col": "近月收盘", "far_col": "远月收盘", "z_window": 60, "z_entry": 1.5, "z_exit": 0.5}, "跨期套利(期货)"),

    # —— 新增：选股/增强/轮动 ——
    "auction_open": (AuctionOpenSelectionStrategy, {"gap_min": 2.0, "vol_ratio_min": 1.5}, "集合竞价选股(股票)"),
    "multifactor": (MultiFactorSelectionStrategy, {"use_factors": None, "buy_thresh": 0.0}, "多因子选股(股票)"),
    "index_enhance": (IndexEnhancementStrategy, {"index_col": "指数收盘", "ma": 100}, "指数增强(股票)"),
    "rotation": (IndustryRotationOverlay, {"industry_col": "行业指数收盘", "lookback": 20}, "行业轮动(股票)"),

    # —— 新增：日内 ——
    "intraday_revert": (IntradayReversionStrategy, {"k": 0.8, "daily_reset": True}, "日内回转交易(股票)"),
}

def list_strategies() -> Dict[str, str]:
    """
    列出所有可用策略
    
    Returns:
        {key: description} 字典
    """
    return {k: v[2] for k, v in _REGISTRY.items()}

def strategy_keys() -> list:
    """返回可用策略键名列表，用于 CLI 帮助。"""
    return list(_REGISTRY.keys())

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
