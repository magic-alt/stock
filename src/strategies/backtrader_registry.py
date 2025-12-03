"""
Backtrader策略注册中心
统一管理所有Backtrader策略的注册和访问
"""
from typing import Dict, Any, Type, Callable
import backtrader as bt

# 导入所有策略模块
from .ema_backtrader_strategy import EMAStrategy, _coerce_ema
from .macd_backtrader_strategy import (
    MACDStrategy, MACDZeroCrossStrategy, MACDHistogramStrategy, 
    MACD_EnhancedStrategy, MACD_RegimePullback, _coerce_macd
)
from .bollinger_backtrader_strategy import BollingerStrategy, Bollinger_EnhancedStrategy, _coerce_bb
from .rsi_backtrader_strategy import (
    RSIStrategy, RSIMaFilterStrategy, RSIDivergenceStrategy, _coerce_rsi
)
from .keltner_backtrader_strategy import KeltnerStrategy, _coerce_keltner
from .zscore_backtrader_strategy import ZScoreStrategy, _coerce_zscore
from .donchian_backtrader_strategy import DonchianStrategy, _coerce_donchian
from .triple_ma_backtrader_strategy import TripleMAStrategy, _coerce_tma
from .adx_backtrader_strategy import ADXTrendStrategy, _coerce_adx
from .sma_backtrader_strategy import SMACrossStrategy, _coerce_sma_cross
from .kama_backtrader_strategy import KAMAStrategy, _coerce_kama
from .futures_backtrader_strategy import (
    FuturesMACrossStrategy, FuturesGridStrategy, 
    FuturesMarketMakingStrategy, TurtleFuturesStrategy,
    _coerce_futures_ma, _coerce_futures_grid, _coerce_futures_mm, _coerce_turtle
)
from .auction_backtrader_strategy import AuctionOpenSelectionStrategy, _coerce_auction
from .intraday_backtrader_strategy import IntradayReversionStrategy, _coerce_intraday
from .multifactor_backtrader_strategy import (
    MultiFactorSelectionStrategy, IndexEnhancementStrategy, IndustryRotationStrategy,
    _coerce_multifactor, _coerce_index_enhancement, _coerce_industry_rotation
)

# V3.0.0: 优化策略（增加动态风控、趋势过滤、多指标确认）
from .optimized_strategies import (
    KAMAStrategy_Optimized, FuturesGrid_ATR_Optimized,
    IntradayReversion_Optimized, BollingerRSI_Optimized, DonchianATR_Optimized,
    _coerce_kama_optimized, _coerce_futures_grid_atr,
    _coerce_intraday_optimized, _coerce_bollinger_rsi, _coerce_donchian_atr,
    OPTIMIZED_STRATEGIES,
)

# V3.0.0: 趋势回调增强策略（机构级综合策略）
from .trend_pullback_enhanced import (
    TrendPullbackEnhanced, _coerce_trend_pullback, STRATEGY_CONFIG as TREND_PULLBACK_CONFIG
)

# V3.0.0-beta.4: 增强策略集合（专家级优化）
from .enhanced_strategies import (
    ZScoreEnhancedStrategy, RSITrendStrategy, KeltnerAdaptiveStrategy,
    TripleMA_ADX_Strategy, MACDImpulseStrategy, SMATrendFollowingStrategy,
    MultiFactorRobustStrategy,
    _coerce_zscore_enhanced, _coerce_rsi_trend, _coerce_keltner_adaptive,
    _coerce_triple_ma_adx, _coerce_macd_impulse, _coerce_sma_trend,
    _coerce_multifactor_robust,
    ENHANCED_STRATEGY_CONFIGS,
)

# V3.0.0-beta.4: ML 增强策略
from .ml_enhanced_strategy import (
    MLEnhancedStrategy, MLEnsembleStrategy,
    _coerce_ml_enhanced,
    ML_ENHANCED_CONFIG, ML_ENSEMBLE_CONFIG,
)


class StrategyModule:
    """策略模块配置容器"""
    def __init__(
        self,
        name: str,
        description: str,
        strategy_cls: Type[bt.Strategy],
        param_names: list,
        defaults: dict,
        grid_defaults: dict,
        coercer: Callable,
        multi_symbol: bool = False
    ):
        self.name = name
        self.description = description
        self.strategy_cls = strategy_cls
        self.param_names = param_names
        self.defaults = defaults
        self.grid_defaults = grid_defaults
        self.coercer = coercer
        self.multi_symbol = multi_symbol


# 注册所有策略
BACKTRADER_STRATEGY_REGISTRY: Dict[str, StrategyModule] = {}


def register_strategy(module: StrategyModule):
    """注册策略到注册表"""
    BACKTRADER_STRATEGY_REGISTRY[module.name] = module


# 指标策略
register_strategy(StrategyModule(
    name='ema',
    description='EMA crossover strategy',
    strategy_cls=EMAStrategy,
    param_names=['period'],
    defaults={'period': 20},
    grid_defaults={'period': list(range(5, 121, 5))},
    coercer=_coerce_ema,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='macd',
    description='MACD signal crossover',
    strategy_cls=MACDStrategy,
    param_names=['fast', 'slow', 'signal'],
    defaults={'fast': 12, 'slow': 26, 'signal': 9},
    grid_defaults={
        'fast': list(range(4, 21, 2)),
        'slow': list(range(10, 41, 5)),
        'signal': [9]
    },
    coercer=_coerce_macd,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='macd_e',
    description='MACD with trend filter, cooldown and SL/TP',
    strategy_cls=MACD_EnhancedStrategy,
    param_names=['fast', 'slow', 'signal', 'ema_trend_period', 'trend_filter', 
                 'cooldown', 'min_hold', 'stop_loss_pct', 'take_profit_pct'],
    defaults={
        'fast': 12, 'slow': 26, 'signal': 9,
        'ema_trend_period': 200, 'trend_filter': True,
        'cooldown': 5, 'min_hold': 3,
        'stop_loss_pct': 0.05, 'take_profit_pct': 0.10,
    },
    grid_defaults={
        'fast': [8, 12], 'slow': [20, 26, 32], 'signal': [9],
        'ema_trend_period': [100, 150, 200],
        'trend_filter': [True],
        'cooldown': [3, 5, 8],
        'min_hold': [2, 3, 5],
        'stop_loss_pct': [0.03, 0.05, 0.08],
        'take_profit_pct': [0.07, 0.10, 0.15],
    },
    coercer=_coerce_macd,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='bollinger',
    description='Bollinger band mean reversion with flexible entry/exit modes',
    strategy_cls=BollingerStrategy,
    param_names=['period', 'devfactor', 'entry_mode', 'below_pct', 'exit_mode'],
    defaults={
        'period': 20,
        'devfactor': 2.0,
        'entry_mode': 'pierce',
        'below_pct': 0.0,
        'exit_mode': 'mid'
    },
    grid_defaults={
        'period': list(range(10, 31, 2)),
        'devfactor': [1.5, 2.0, 2.5],
        'entry_mode': ['pierce'],
        'exit_mode': ['mid']
    },
    coercer=_coerce_bb,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='boll_e',
    description='BollingerBands Enhanced: ATR SL + multi-TP + pullback exit + warmup/cooldown (V2.8.4.1 relaxed)',
    strategy_cls=Bollinger_EnhancedStrategy,
    param_names=[
        'period', 'devfactor',
        'atr_period', 'atr_mult_sl',
        'tp1_pct', 'tp1_frac', 'tp2_pct', 'tp2_frac',
        'trail_drop_pct', 'min_hold', 'cooldown', 'warmup_bars',
        'rebound_lookback', 'max_hold',
        'trend_filter'
    ],
    defaults={
        'period': 20, 'devfactor': 2.0,
        'atr_period': 14, 'atr_mult_sl': 2.0,  # 放宽至2.0
        'tp1_pct': 0.03, 'tp1_frac': 0.5,
        'tp2_pct': 0.06, 'tp2_frac': 1.0,
        'trail_drop_pct': 0.04, 'min_hold': 2, 'cooldown': 3,  # 放宽
        'warmup_bars': None,  # 自动计算
        'rebound_lookback': 3,  # 最近3根
        'max_hold': 60,  # 最长持有60根
        'trend_filter': True,
    },
    grid_defaults={
        'period': [18, 20, 22],
        'devfactor': [1.8, 2.0, 2.2],
        'atr_period': [14, 20],
        'atr_mult_sl': [1.5, 2.0, 2.5],  # 放宽范围
        'tp1_pct': [0.02, 0.03, 0.04],
        'tp1_frac': [0.3, 0.5, 0.7],
        'tp2_pct': [0.05, 0.06, 0.08],
        'tp2_frac': [1.0],
        'trail_drop_pct': [0.03, 0.04, 0.05],
        'min_hold': [1, 2, 3],  # 放宽
        'cooldown': [2, 3, 5],  # 放宽
        'rebound_lookback': [2, 3, 5],
        'max_hold': [40, 60, 80],
        'trend_filter': [True, False],
    },
    coercer=_coerce_bb,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='macd_r',
    description='MACD Regime + Pullback + ATR Risk (V2.8.4.1 relaxed with trend_logic)',
    strategy_cls=MACD_RegimePullback,
    param_names=['fast','slow','signal','ema_trend_period','roc_period','trend_filter','trend_logic',
                 'ema_entry_period','pullback_k','max_lag',
                 'atr_period','atr_sl_mult','atr_trail_mult',
                 'min_hold','cooldown','tp1_R','tp1_frac','tp2_R'],
    defaults={
        'fast':12, 'slow':26, 'signal':9,
        'ema_trend_period':200, 'roc_period':100, 'trend_filter':True,
        'trend_logic':'or',  # 更宽松：EMA OR ROC
        'ema_entry_period':20, 'pullback_k':0.5, 'max_lag':7,  # 放宽至7
        'atr_period':14, 'atr_sl_mult':2.0, 'atr_trail_mult':1.8,  # 放宽
        'min_hold':2, 'cooldown':3,  # 放宽
        'tp1_R':0.8, 'tp1_frac':0.5, 'tp2_R':1.6,  # 放宽
    },
    grid_defaults={
        'pullback_k':[0.3,0.5,0.8],
        'max_lag':[5,7,10],  # 放宽
        'atr_sl_mult':[1.5,2.0,2.5],  # 放宽
        'atr_trail_mult':[1.5,1.8,2.0],
        'tp1_R':[0.6,0.8,1.0], 'tp1_frac':[0.3,0.5,0.7],
        'tp2_R':[1.2,1.6,2.0],  # 放宽
        'trend_logic':['or','and'],  # 新增参数
    },
    coercer=_coerce_macd,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='rsi',
    description='RSI threshold strategy',
    strategy_cls=RSIStrategy,
    param_names=['period', 'upper', 'lower'],
    defaults={'period': 14, 'upper': 70.0, 'lower': 30.0},
    grid_defaults={
        'period': list(range(10, 31, 2)),
        'upper': [65, 70, 75],
        'lower': [25, 30, 35]
    },
    coercer=_coerce_rsi,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='keltner',
    description='Keltner Channel mean reversion (EMA mid + ATR bands)',
    strategy_cls=KeltnerStrategy,
    param_names=['ema_period', 'atr_period', 'kc_mult', 'entry_mode', 'below_pct', 'exit_mode'],
    defaults={
        'ema_period': 20,
        'atr_period': 14,
        'kc_mult': 2.0,
        'entry_mode': 'pierce',
        'below_pct': 0.0,
        'exit_mode': 'mid'
    },
    grid_defaults={
        'ema_period': list(range(10, 25, 2)),
        'atr_period': [14],
        'kc_mult': [1.8, 2.0, 2.2],
        'entry_mode': ['pierce', 'close_below'],
        'exit_mode': ['mid']
    },
    coercer=_coerce_keltner,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='zscore',
    description='Rolling-mean z-score mean reversion',
    strategy_cls=ZScoreStrategy,
    param_names=['period', 'z_entry', 'z_exit'],
    defaults={'period': 20, 'z_entry': -2.0, 'z_exit': -0.5},
    grid_defaults={
        'period': [12, 16, 20, 24],
        'z_entry': [-1.8, -2.0, -2.2],
        'z_exit': [-0.7, -0.5]
    },
    coercer=_coerce_zscore,
    multi_symbol=False,
))

# 趋势策略
register_strategy(StrategyModule(
    name='donchian',
    description='Donchian channel breakout (N-high/M-low) with ATR sizing',
    strategy_cls=DonchianStrategy,
    param_names=['upper', 'lower'],
    defaults={'upper': 20, 'lower': 10},
    grid_defaults={
        'upper': [18, 20, 22, 24],
        'lower': [8, 10, 12]
    },
    coercer=_coerce_donchian,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='triple_ma',
    description='Triple moving average trend (fast>mid>slow) with ATR sizing',
    strategy_cls=TripleMAStrategy,
    param_names=['fast', 'mid', 'slow'],
    defaults={'fast': 5, 'mid': 20, 'slow': 60},
    grid_defaults={
        'fast': [5, 8],
        'mid': [18, 20, 22],
        'slow': [55, 60, 65]
    },
    coercer=_coerce_tma,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='adx_trend',
    description='ADX(+DI/-DI) trend filter with ATR sizing',
    strategy_cls=ADXTrendStrategy,
    param_names=['adx_period', 'adx_th'],
    defaults={'adx_period': 14, 'adx_th': 25.0},
    grid_defaults={
        'adx_period': [12, 14, 16],
        'adx_th': [20, 25, 30]
    },
    coercer=_coerce_adx,
    multi_symbol=False,
))

# SMA Cross strategy
register_strategy(StrategyModule(
    name='sma_cross',
    description='Simple moving average crossover with ATR sizing',
    strategy_cls=SMACrossStrategy,
    param_names=['fast_period', 'slow_period'],
    defaults={'fast_period': 10, 'slow_period': 30},
    grid_defaults={
        'fast_period': [5, 10, 15, 20],
        'slow_period': [20, 30, 40, 50, 60]
    },
    coercer=_coerce_sma_cross,
    multi_symbol=False,
))

# KAMA strategy
register_strategy(StrategyModule(
    name='kama',
    description='Kaufman Adaptive Moving Average crossover',
    strategy_cls=KAMAStrategy,
    param_names=['period', 'fast_ema', 'slow_ema'],
    defaults={'period': 10, 'fast_ema': 2, 'slow_ema': 30},
    grid_defaults={
        'period': [8, 10, 12, 14],
        'fast_ema': [2],
        'slow_ema': [25, 30, 35]
    },
    coercer=_coerce_kama,
    multi_symbol=False,
))

# MACD Zero Cross strategy
register_strategy(StrategyModule(
    name='macd_zero',
    description='MACD zero line crossover',
    strategy_cls=MACDZeroCrossStrategy,
    param_names=['fast', 'slow', 'signal'],
    defaults={'fast': 12, 'slow': 26, 'signal': 9},
    grid_defaults={
        'fast': [10, 12, 14],
        'slow': [24, 26, 28],
        'signal': [9]
    },
    coercer=_coerce_macd,
    multi_symbol=False,
))

# MACD Histogram strategy
register_strategy(StrategyModule(
    name='macd_hist',
    description='MACD histogram momentum strategy',
    strategy_cls=MACDHistogramStrategy,
    param_names=['fast', 'slow', 'signal', 'threshold'],
    defaults={'fast': 12, 'slow': 26, 'signal': 9, 'threshold': 0.0},
    grid_defaults={
        'fast': [10, 12, 14],
        'slow': [24, 26, 28],
        'signal': [9],
        'threshold': [0.0, 0.1, 0.2]
    },
    coercer=_coerce_macd,
    multi_symbol=False,
))

# RSI + MA Filter strategy
register_strategy(StrategyModule(
    name='rsi_ma_filter',
    description='RSI oversold + MA trend filter',
    strategy_cls=RSIMaFilterStrategy,
    param_names=['rsi_period', 'oversold', 'ma_period'],
    defaults={'rsi_period': 14, 'oversold': 30.0, 'ma_period': 200},
    grid_defaults={
        'rsi_period': [12, 14, 16],
        'oversold': [25, 30, 35],
        'ma_period': [100, 150, 200]
    },
    coercer=_coerce_rsi,
    multi_symbol=False,
))

# RSI Divergence strategy
register_strategy(StrategyModule(
    name='rsi_divergence',
    description='RSI divergence detection strategy',
    strategy_cls=RSIDivergenceStrategy,
    param_names=['period', 'lookback'],
    defaults={'period': 14, 'lookback': 5},
    grid_defaults={
        'period': [12, 14, 16],
        'lookback': [4, 5, 6, 7]
    },
    coercer=_coerce_rsi,
    multi_symbol=False,
))

# 期货策略
register_strategy(StrategyModule(
    name='futures_ma_cross',
    description='Futures EMA crossover strategy',
    strategy_cls=FuturesMACrossStrategy,
    param_names=['short_period', 'long_period'],
    defaults={'short_period': 9, 'long_period': 34},
    grid_defaults={
        'short_period': [5, 9, 13],
        'long_period': [21, 34, 55]
    },
    coercer=_coerce_futures_ma,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='futures_grid',
    description='Futures grid trading strategy',
    strategy_cls=FuturesGridStrategy,
    param_names=['grid_pct', 'layers', 'max_pos'],
    defaults={'grid_pct': 0.004, 'layers': 6, 'max_pos': 3},
    grid_defaults={
        'grid_pct': [0.003, 0.004, 0.005],
        'layers': [4, 6, 8],
        'max_pos': [2, 3, 4]
    },
    coercer=_coerce_futures_grid,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='futures_market_making',
    description='Futures market making strategy',
    strategy_cls=FuturesMarketMakingStrategy,
    param_names=['band_pct', 'inventory_limit', 'ma_period'],
    defaults={'band_pct': 0.003, 'inventory_limit': 2, 'ma_period': 50},
    grid_defaults={
        'band_pct': [0.002, 0.003, 0.004],
        'inventory_limit': [1, 2, 3],
        'ma_period': [40, 50, 60]
    },
    coercer=_coerce_futures_mm,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='turtle_futures',
    description='Turtle trading system for futures',
    strategy_cls=TurtleFuturesStrategy,
    param_names=['entry_period', 'exit_period'],
    defaults={'entry_period': 20, 'exit_period': 10},
    grid_defaults={
        'entry_period': [15, 20, 25],
        'exit_period': [8, 10, 12]
    },
    coercer=_coerce_turtle,
    multi_symbol=False,
))

# 特殊策略
register_strategy(StrategyModule(
    name='auction_open',
    description='Auction open selection with gap and volume filter',
    strategy_cls=AuctionOpenSelectionStrategy,
    param_names=['gap_min', 'vol_ratio_min'],
    defaults={'gap_min': 2.0, 'vol_ratio_min': 1.5},
    grid_defaults={
        'gap_min': [1.5, 2.0, 2.5, 3.0],
        'vol_ratio_min': [1.2, 1.5, 2.0]
    },
    coercer=_coerce_auction,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='intraday_reversion',
    description='Intraday mean reversion from open price',
    strategy_cls=IntradayReversionStrategy,
    param_names=['threshold_pct', 'allow_short'],
    defaults={'threshold_pct': 0.8, 'allow_short': False},
    grid_defaults={
        'threshold_pct': [0.5, 0.8, 1.0, 1.5],
        'allow_short': [False]
    },
    coercer=_coerce_intraday,
    multi_symbol=False,
))

# 多因子策略
register_strategy(StrategyModule(
    name='multifactor_selection',
    description='Multi-factor selection with momentum, volatility, and volume',
    strategy_cls=MultiFactorSelectionStrategy,
    param_names=['buy_threshold', 'score_window'],
    defaults={'buy_threshold': 0.0, 'score_window': 60},
    grid_defaults={
        'buy_threshold': [-0.5, 0.0, 0.5],
        'score_window': [40, 60, 80]
    },
    coercer=_coerce_multifactor,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='index_enhancement',
    description='Index enhancement with trend and momentum filter',
    strategy_cls=IndexEnhancementStrategy,
    param_names=['ma_period', 'mom_period'],
    defaults={'ma_period': 100, 'mom_period': 20},
    grid_defaults={
        'ma_period': [60, 100, 150, 200],
        'mom_period': [10, 20, 30]
    },
    coercer=_coerce_index_enhancement,
    multi_symbol=False,
))

register_strategy(StrategyModule(
    name='industry_rotation',
    description='Industry rotation based on relative strength',
    strategy_cls=IndustryRotationStrategy,
    param_names=['ma_period', 'momentum_period'],
    defaults={'ma_period': 60, 'momentum_period': 20},
    grid_defaults={
        'ma_period': [40, 60, 80],
        'momentum_period': [10, 20, 30]
    },
    coercer=_coerce_industry_rotation,
    multi_symbol=False,
))


# =============================================================================
# V3.0.0 优化策略（增加动态风控、趋势过滤、多指标确认）
# =============================================================================

# KAMA 优化版：SMA200 趋势过滤 + ATR 移动止损
register_strategy(StrategyModule(
    name='kama_opt',
    description='KAMA with SMA200 trend filter and ATR trailing stop',
    strategy_cls=KAMAStrategy_Optimized,
    param_names=['period', 'filter_period', 'atr_stop_mult', 'trail_atr_mult'],
    defaults={'period': 10, 'filter_period': 200, 'atr_stop_mult': 2.0, 'trail_atr_mult': 1.5},
    grid_defaults={
        'period': [8, 10, 12, 15],
        'filter_period': [100, 150, 200],
        'atr_stop_mult': [1.5, 2.0, 2.5],
    },
    coercer=_coerce_kama_optimized,
    multi_symbol=False,
))

# 期货网格优化版：ATR 动态间距 + 账户止损
register_strategy(StrategyModule(
    name='futures_grid_atr',
    description='ATR dynamic grid with account-level stop loss',
    strategy_cls=FuturesGrid_ATR_Optimized,
    param_names=['grid_atr_mult', 'layers', 'max_pos', 'stop_loss_pct'],
    defaults={'grid_atr_mult': 0.5, 'layers': 6, 'max_pos': 3, 'stop_loss_pct': 0.10},
    grid_defaults={
        'grid_atr_mult': [0.3, 0.5, 0.7, 1.0],
        'layers': [4, 6, 8],
        'max_pos': [2, 3, 4],
    },
    coercer=_coerce_futures_grid_atr,
    multi_symbol=False,
))

# 日内回转优化版：时间过滤 + ATR 动态阈值
register_strategy(StrategyModule(
    name='intraday_opt',
    description='Intraday reversion with time filter and ATR threshold',
    strategy_cls=IntradayReversion_Optimized,
    param_names=['entry_atr_mult', 'stop_atr_mult', 'max_hold_bars'],
    defaults={'entry_atr_mult': 1.0, 'stop_atr_mult': 2.0, 'max_hold_bars': 30},
    grid_defaults={
        'entry_atr_mult': [0.8, 1.0, 1.2, 1.5],
        'stop_atr_mult': [1.5, 2.0, 2.5],
    },
    coercer=_coerce_intraday_optimized,
    multi_symbol=False,
))

# 布林带优化版：RSI 超卖确认 + 分批止盈
register_strategy(StrategyModule(
    name='bollinger_rsi',
    description='Bollinger Bands with RSI confirmation filter',
    strategy_cls=BollingerRSI_Optimized,
    param_names=['period', 'devfactor', 'rsi_oversold', 'rsi_overbought'],
    defaults={'period': 20, 'devfactor': 2.0, 'rsi_oversold': 30, 'rsi_overbought': 70},
    grid_defaults={
        'period': [15, 20, 25],
        'devfactor': [1.8, 2.0, 2.2],
        'rsi_oversold': [25, 30, 35],
    },
    coercer=_coerce_bollinger_rsi,
    multi_symbol=False,
))

# 唐奇安通道优化版：ATR 波动率突破确认
register_strategy(StrategyModule(
    name='donchian_atr',
    description='Donchian breakout with ATR volatility confirmation',
    strategy_cls=DonchianATR_Optimized,
    param_names=['upper_period', 'lower_period', 'atr_stop_mult'],
    defaults={'upper_period': 20, 'lower_period': 10, 'atr_stop_mult': 2.0},
    grid_defaults={
        'upper_period': [15, 20, 25, 30],
        'lower_period': [8, 10, 12],
        'atr_stop_mult': [1.5, 2.0, 2.5],
    },
    coercer=_coerce_donchian_atr,
    multi_symbol=False,
))

# V3.0.0: 趋势回调增强版（机构级综合策略）
register_strategy(StrategyModule(
    name='trend_pullback_enhanced',
    description='Trend following with pullback entry, volatility sizing, and chandelier exit',
    strategy_cls=TrendPullbackEnhanced,
    param_names=TREND_PULLBACK_CONFIG['param_names'],
    defaults=TREND_PULLBACK_CONFIG['defaults'],
    grid_defaults=TREND_PULLBACK_CONFIG['grid_defaults'],
    coercer=_coerce_trend_pullback,
    multi_symbol=False,
))

# =============================================================================
# V3.0.0-beta.4: 增强策略集合 (专家级优化)
# =============================================================================

# Z-Score 均值回归增强版：RSI 共振 + ATR 止损
register_strategy(StrategyModule(
    name='zscore_enhanced',
    description='Z-Score Mean Reversion with RSI Filter and ATR Stop',
    strategy_cls=ZScoreEnhancedStrategy,
    param_names=ENHANCED_STRATEGY_CONFIGS['zscore_enhanced']['param_names'],
    defaults=ENHANCED_STRATEGY_CONFIGS['zscore_enhanced']['defaults'],
    grid_defaults=ENHANCED_STRATEGY_CONFIGS['zscore_enhanced']['grid_defaults'],
    coercer=_coerce_zscore_enhanced,
    multi_symbol=False,
))

# RSI 趋势顺势策略：钩头形态 + 趋势过滤
register_strategy(StrategyModule(
    name='rsi_trend',
    description='RSI Pullback Strategy in Uptrend with Hook Pattern',
    strategy_cls=RSITrendStrategy,
    param_names=ENHANCED_STRATEGY_CONFIGS['rsi_trend']['param_names'],
    defaults=ENHANCED_STRATEGY_CONFIGS['rsi_trend']['defaults'],
    grid_defaults=ENHANCED_STRATEGY_CONFIGS['rsi_trend']['grid_defaults'],
    coercer=_coerce_rsi_trend,
    multi_symbol=False,
))

# Keltner 自适应策略：波动率定仓 + 吊灯止损
register_strategy(StrategyModule(
    name='keltner_adaptive',
    description='Keltner Breakout with Volatility Sizing and Chandelier Exit',
    strategy_cls=KeltnerAdaptiveStrategy,
    param_names=ENHANCED_STRATEGY_CONFIGS['keltner_adaptive']['param_names'],
    defaults=ENHANCED_STRATEGY_CONFIGS['keltner_adaptive']['defaults'],
    grid_defaults=ENHANCED_STRATEGY_CONFIGS['keltner_adaptive']['grid_defaults'],
    coercer=_coerce_keltner_adaptive,
    multi_symbol=False,
))

# 三均线 ADX 过滤策略：趋势强度过滤
register_strategy(StrategyModule(
    name='triple_ma_adx',
    description='Triple EMA with ADX Trend Strength Filter',
    strategy_cls=TripleMA_ADX_Strategy,
    param_names=ENHANCED_STRATEGY_CONFIGS['triple_ma_adx']['param_names'],
    defaults=ENHANCED_STRATEGY_CONFIGS['triple_ma_adx']['defaults'],
    grid_defaults=ENHANCED_STRATEGY_CONFIGS['triple_ma_adx']['grid_defaults'],
    coercer=_coerce_triple_ma_adx,
    multi_symbol=False,
))

# MACD 脉冲策略：零轴偏离 + 动能确认
register_strategy(StrategyModule(
    name='macd_impulse',
    description='MACD Zero-Line Bias Strategy with Momentum Filter',
    strategy_cls=MACDImpulseStrategy,
    param_names=ENHANCED_STRATEGY_CONFIGS['macd_impulse']['param_names'],
    defaults=ENHANCED_STRATEGY_CONFIGS['macd_impulse']['defaults'],
    grid_defaults=ENHANCED_STRATEGY_CONFIGS['macd_impulse']['grid_defaults'],
    coercer=_coerce_macd_impulse,
    multi_symbol=False,
))

# SMA 趋势跟随策略：斜率确认
register_strategy(StrategyModule(
    name='sma_trend_following',
    description='SMA Cross with Slope Confirmation',
    strategy_cls=SMATrendFollowingStrategy,
    param_names=ENHANCED_STRATEGY_CONFIGS['sma_trend_following']['param_names'],
    defaults=ENHANCED_STRATEGY_CONFIGS['sma_trend_following']['defaults'],
    grid_defaults=ENHANCED_STRATEGY_CONFIGS['sma_trend_following']['grid_defaults'],
    coercer=_coerce_sma_trend,
    multi_symbol=False,
))

# 多因子稳健策略：大盘过滤 + 动量/波动率因子
register_strategy(StrategyModule(
    name='multifactor_robust',
    description='Trend-Filtered Multi-Factor with Regime Filter',
    strategy_cls=MultiFactorRobustStrategy,
    param_names=ENHANCED_STRATEGY_CONFIGS['multifactor_robust']['param_names'],
    defaults=ENHANCED_STRATEGY_CONFIGS['multifactor_robust']['defaults'],
    grid_defaults=ENHANCED_STRATEGY_CONFIGS['multifactor_robust']['grid_defaults'],
    coercer=_coerce_multifactor_robust,
    multi_symbol=False,
))


def list_backtrader_strategies() -> Dict[str, str]:
    """列出所有可用的Backtrader策略"""
    return {name: module.description for name, module in BACKTRADER_STRATEGY_REGISTRY.items()}


def get_backtrader_strategy(name: str) -> StrategyModule:
    """获取指定名称的策略模块"""
    if name not in BACKTRADER_STRATEGY_REGISTRY:
        available = ', '.join(BACKTRADER_STRATEGY_REGISTRY.keys())
        raise ValueError(f"Strategy '{name}' not found. Available: {available}")
    return BACKTRADER_STRATEGY_REGISTRY[name]


def create_backtrader_strategy(name: str, **params) -> Type[bt.Strategy]:
    """创建策略实例（返回策略类，由Backtrader实例化）"""
    module = get_backtrader_strategy(name)
    
    # 合并默认参数和用户参数
    final_params = module.defaults.copy()
    final_params.update(params)
    
    # 参数类型转换
    coerced_params = module.coercer(final_params)
    
    # 动态创建策略类的子类，设置参数
    class ConfiguredStrategy(module.strategy_cls):
        params = tuple((k, v) for k, v in coerced_params.items())
    
    return ConfiguredStrategy


__all__ = [
    'StrategyModule',
    'BACKTRADER_STRATEGY_REGISTRY',
    'register_strategy',
    'list_backtrader_strategies',
    'get_backtrader_strategy',
    'create_backtrader_strategy',
    # 基础策略类
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
    # 期货策略类
    'FuturesMACrossStrategy',
    'FuturesGridStrategy',
    'FuturesMarketMakingStrategy',
    'TurtleFuturesStrategy',
    # 特殊策略类
    'AuctionOpenSelectionStrategy',
    'IntradayReversionStrategy',
    # 多因子策略类
    'MultiFactorSelectionStrategy',
    'IndexEnhancementStrategy',
    'IndustryRotationStrategy',
    # V3.0.0 优化策略类
    'KAMAStrategy_Optimized',
    'FuturesGrid_ATR_Optimized',
    'IntradayReversion_Optimized',
    'BollingerRSI_Optimized',
    'DonchianATR_Optimized',
    'OPTIMIZED_STRATEGIES',
    # V3.0.0 机构级综合策略
    'TrendPullbackEnhanced',
    # V3.0.0-beta.4 增强策略集合
    'ZScoreEnhancedStrategy',
    'RSITrendStrategy',
    'KeltnerAdaptiveStrategy',
    'TripleMA_ADX_Strategy',
    'MACDImpulseStrategy',
    'SMATrendFollowingStrategy',
    'MultiFactorRobustStrategy',
    'ENHANCED_STRATEGY_CONFIGS',
    # V3.0.0-beta.4 ML 增强策略
    'MLEnhancedStrategy',
    'MLEnsembleStrategy',
    'ML_ENHANCED_CONFIG',
    'ML_ENSEMBLE_CONFIG',
]
