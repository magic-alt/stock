"""
策略模块
包含简单策略（用于SimpleBacktestEngine）和Backtrader策略（用于专业回测）
"""

# 简单策略（用于SimpleBacktestEngine）
from .base import BaseStrategy
from .ma_strategies import MACrossStrategy, TripleMACrossStrategy
from .rsi_strategies import RSIStrategy, RSIDivergenceStrategy
from .macd_strategies import MACDStrategy, MACDZeroCrossStrategy

# Backtrader策略（用于专业回测）
from .backtrader_registry import (
    StrategyModule,
    BACKTRADER_STRATEGY_REGISTRY,
    list_backtrader_strategies,
    get_backtrader_strategy,
    create_backtrader_strategy,
    # 策略类
    EMAStrategy as BTEMAStrategy,
    MACDStrategy as BTMACDStrategy,
    BollingerStrategy,
    RSIStrategy as BTRSIStrategy,
    KeltnerStrategy,
    ZScoreStrategy,
    DonchianStrategy,
    TripleMAStrategy,
    ADXTrendStrategy,
)

__all__ = [
    # 简单策略
    'BaseStrategy',
    'MACrossStrategy',
    'TripleMACrossStrategy',
    'RSIStrategy',
    'RSIDivergenceStrategy',
    'MACDStrategy',
    'MACDZeroCrossStrategy',
    
    # Backtrader注册器
    'StrategyModule',
    'BACKTRADER_STRATEGY_REGISTRY',
    'list_backtrader_strategies',
    'get_backtrader_strategy',
    'create_backtrader_strategy',
    
    # Backtrader策略类
    'BTEMAStrategy',
    'BTMACDStrategy',
    'BollingerStrategy',
    'BTRSIStrategy',
    'KeltnerStrategy',
    'ZScoreStrategy',
    'DonchianStrategy',
    'TripleMAStrategy',
    'ADXTrendStrategy',
]
