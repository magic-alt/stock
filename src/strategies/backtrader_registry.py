"""
Backtrader策略注册中心
统一管理所有Backtrader策略的注册和访问
"""
from typing import Dict, Any, Type, Callable
import backtrader as bt

# 导入所有策略模块
from .ema_backtrader_strategy import EMAStrategy, _coerce_ema
from .macd_backtrader_strategy import MACDStrategy, _coerce_macd
from .bollinger_backtrader_strategy import BollingerStrategy, _coerce_bb
from .rsi_backtrader_strategy import RSIStrategy, _coerce_rsi
from .keltner_backtrader_strategy import KeltnerStrategy, _coerce_keltner
from .zscore_backtrader_strategy import ZScoreStrategy, _coerce_zscore
from .donchian_backtrader_strategy import DonchianStrategy, _coerce_donchian
from .triple_ma_backtrader_strategy import TripleMAStrategy, _coerce_tma
from .adx_backtrader_strategy import ADXTrendStrategy, _coerce_adx


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
    # 策略类
    'EMAStrategy',
    'MACDStrategy',
    'BollingerStrategy',
    'RSIStrategy',
    'KeltnerStrategy',
    'ZScoreStrategy',
    'DonchianStrategy',
    'TripleMAStrategy',
    'ADXTrendStrategy',
]
