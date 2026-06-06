"""
策略模块 - Backtrader专业回测系统
包含所有用于 unified_backtest_framework 的 Backtrader 策略
"""

# 策略基类（用于扩展）
from .base import BaseStrategy

# Backtrader策略注册系统（主要使用）
try:
    from .backtrader_registry import (  # noqa: F401
        StrategyModule,
        BACKTRADER_STRATEGY_REGISTRY,
        list_backtrader_strategies,
        get_backtrader_strategy,
        create_backtrader_strategy,
        # 基础策略类
        EMAStrategy,
        MACDStrategy,
        MACDZeroCrossStrategy,
        MACDHistogramStrategy,
        BollingerStrategy,
        RSIStrategy,
        RSIMaFilterStrategy,
        RSIDivergenceStrategy,
        KeltnerStrategy,
        ZScoreStrategy,
        DonchianStrategy,
        TripleMAStrategy,
        ADXTrendStrategy,
        SMACrossStrategy,
        KAMAStrategy,
        # 期货策略类
        FuturesMACrossStrategy,
        FuturesGridStrategy,
        FuturesMarketMakingStrategy,
        TurtleFuturesStrategy,
        # 特殊策略类
        AuctionOpenSelectionStrategy,
        IntradayReversionStrategy,
        # 多因子策略类
        MultiFactorSelectionStrategy,
        IndexEnhancementStrategy,
        IndustryRotationStrategy,
        QlibRegistrySignalStrategy,
    )
    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False

# 特殊策略（套利、ML等 - 保留用于未来扩展）
# 这些策略继承 BaseStrategy，需要单独的回测引擎或多数据源支持
try:
    from .ml_strategies import MLWalkForwardStrategy  # noqa: F401
    from .ml_strategies import (  # noqa: F401
        DeepSequenceStrategy,
        ReinforcementLearningSignalStrategy,
        FeatureSelectionStrategy,
        EnsembleVotingStrategy,
    )
    from .arbitrage_strategies import (  # noqa: F401
        AlphaHedgeStrategy, CrossCommodityArbStrategy, CalendarSpreadArbStrategy
    )
    
    SPECIAL_STRATEGIES_AVAILABLE = True
except ImportError:
    SPECIAL_STRATEGIES_AVAILABLE = False

__all__ = [
    # 基类
    'BaseStrategy',
    'BACKTRADER_AVAILABLE',
]

# 如果Backtrader可用，导出所有策略类
if BACKTRADER_AVAILABLE:
    __all__.extend([
        # Backtrader注册系统（主要使用）
        'StrategyModule',
        'BACKTRADER_STRATEGY_REGISTRY',
        'list_backtrader_strategies',
        'get_backtrader_strategy',
        'create_backtrader_strategy',
        # Backtrader策略类（用于 unified_backtest_framework）
        'EMAStrategy',
        'MACDStrategy',
        'MACDZeroCrossStrategy',
        'MACDHistogramStrategy',
        'BollingerStrategy',
        'RSIStrategy',
        'RSIMaFilterStrategy',
        'RSIDivergenceStrategy',
        'KeltnerStrategy',
        'ZScoreStrategy',
        'DonchianStrategy',
        'TripleMAStrategy',
        'ADXTrendStrategy',
        'SMACrossStrategy',
        'KAMAStrategy',
        # 期货策略
        'FuturesMACrossStrategy',
        'FuturesGridStrategy',
        'FuturesMarketMakingStrategy',
        'TurtleFuturesStrategy',
        # 特殊策略
        'AuctionOpenSelectionStrategy',
        'IntradayReversionStrategy',
        # 多因子策略
        'MultiFactorSelectionStrategy',
        'IndexEnhancementStrategy',
        'IndustryRotationStrategy',
        'QlibRegistrySignalStrategy',
    ])

# 如果特殊策略可用，添加到 __all__
if SPECIAL_STRATEGIES_AVAILABLE:
    __all__.extend([
        'MLWalkForwardStrategy',
        'DeepSequenceStrategy',
        'ReinforcementLearningSignalStrategy',
        'FeatureSelectionStrategy',
        'EnsembleVotingStrategy',
        'AlphaHedgeStrategy',
        'CrossCommodityArbStrategy',
        'CalendarSpreadArbStrategy',
    ])
