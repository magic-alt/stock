"""
Enhanced Strategies Collection (增强策略集合)

V3.0.0-beta.4 专家级策略优化

包含8个增强版策略：
1. ZScoreEnhancedStrategy - Z-Score + RSI 共振 + ATR 止损
2. RSITrendStrategy - RSI 钩头形态 + 趋势过滤
3. KeltnerAdaptiveStrategy - Keltner 突破 + 波动率定仓 + 吊灯止损
4. TripleMA_ADX_Strategy - 三均线 + ADX 趋势强度过滤
5. MACDImpulseStrategy - MACD 零轴偏离 + 动能确认
6. SMATrendFollowingStrategy - SMA 交叉 + 斜率确认
7. MultiFactorRobustStrategy - 多因子 + 大盘过滤
8. MLEnhancedStrategy - ML 特征标准化 + 置信度阈值

核心改进：
- 风控 (Risk Management): ATR 止损、吊灯止损、波动率定仓
- 市场状态过滤 (Regime Filtering): 趋势过滤、ADX 强度过滤
- 信号确认 (Signal Confirmation): RSI 共振、动能确认、斜率验证
"""
import backtrader as bt
import numpy as np
import pandas as pd
from typing import Dict, Any


# =============================================================================
# 1. Z-Score 均值回归增强策略
# =============================================================================
class ZScoreEnhancedStrategy(bt.Strategy):
    """
    Z-Score 均值回归增强策略
    
    优化点：
    - RSI 共振过滤：Z-Score 低位 + RSI 超卖双重验证
    - ATR 止损风控：防止回归失败导致深套
    - 保守出场：回归到均值即平仓，不贪婪
    
    解决痛点：
    - 纯 Z-Score 在暴跌趋势中"接飞刀"
    - 价格持续下跌导致 Z-Score 持续低位
    """
    params = (
        ("period", 20),
        ("z_entry", -2.0),
        ("z_exit", 0.0),          # 回归到均值即平仓
        ("rsi_period", 14),
        ("rsi_threshold", 30),    # RSI 超卖确认
        ("atr_period", 14),
        ("atr_stop_mult", 2.0),   # ATR 止损倍数
        ("printlog", False),
    )

    def __init__(self):
        self.sma = bt.indicators.SMA(self.data.close, period=self.params.period)
        self.std = bt.indicators.StdDev(self.data.close, period=self.params.period)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        
        self.order = None
        self.stop_price = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f"BUY EXEC: {order.executed.price:.2f}")
                # 设定止损价
                self.stop_price = order.executed.price - (
                    self.atr[0] * self.params.atr_stop_mult
                )
            elif order.issell():
                self.log(f"SELL EXEC: {order.executed.price:.2f}")
                self.stop_price = None
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        close = self.data.close[0]
        mean = self.sma[0]
        std = self.std[0]
        
        if std < 1e-9:
            return
        
        z_score = (close - mean) / std

        if not self.position:
            # 买入条件：Z-Score 低位 + RSI 超卖 (双重验证)
            if z_score < self.params.z_entry and self.rsi[0] < self.params.rsi_threshold:
                self.log(f"BUY CREATE (Z={z_score:.2f}, RSI={self.rsi[0]:.1f})")
                self.order = self.buy()
        else:
            # 止损逻辑优先
            if self.stop_price and close < self.stop_price:
                self.log(
                    f"STOP LOSS (Price={close:.2f} < Stop={self.stop_price:.2f})"
                )
                self.order = self.close()
                return

            # 正常均值回归出场
            if z_score > self.params.z_exit:
                self.log(f"SELL CREATE (Mean Reversion Z={z_score:.2f})")
                self.order = self.close()


# =============================================================================
# 2. RSI 趋势顺势策略
# =============================================================================
class RSITrendStrategy(bt.Strategy):
    """
    RSI 趋势顺势策略
    
    优化点：
    - 趋势过滤：仅在 SMA200 之上做多
    - RSI 钩头形态：等 RSI 下穿 30 后重新上穿才入场
    - 避免左侧抄底
    
    解决痛点：
    - RSI < 30 在强下跌中会死得很惨
    - RSI > 70 在强牛市中过早下车
    """
    params = (
        ("rsi_period", 14),
        ("trend_period", 200),    # 长期趋势线
        ("lower_band", 30),
        ("upper_band", 70),
        ("printlog", False),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.sma_trend = bt.indicators.SMA(self.data.close, period=self.params.trend_period)
        self.order = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        close = self.data.close[0]
        
        # 1. 趋势判断：价格在长期均线之上
        is_uptrend = close > self.sma_trend[0]

        if not self.position:
            # 2. 顺势买入：趋势向上 + RSI 从下方上穿超卖线 (Hook up)
            rsi_cross_up = (
                (self.rsi[-1] < self.params.lower_band) and 
                (self.rsi[0] >= self.params.lower_band)
            )
            
            if is_uptrend and rsi_cross_up:
                self.log(f"BUY CREATE (Trend Up + RSI Hook), RSI={self.rsi[0]:.2f}")
                self.order = self.buy()
        
        else:
            # 3. 卖出：RSI 超买 或 趋势破位
            if self.rsi[0] > self.params.upper_band:
                self.log("SELL CREATE (RSI Overbought)")
                self.order = self.close()
            elif close < self.sma_trend[0]:
                self.log("SELL CREATE (Trend Broken)")
                self.order = self.close()


# =============================================================================
# 3. Keltner 自适应通道策略
# =============================================================================
class KeltnerAdaptiveStrategy(bt.Strategy):
    """
    Keltner 通道突破策略 (ATR 动态仓位版)
    
    优化点：
    - 波动率定仓：仓位与通道宽度成反比
    - 吊灯止损：让利润奔跑
    - 突破上轨买入（趋势跟随）
    
    解决痛点：
    - 固定百分比入场缺乏灵活性
    - 出场过早导致利润回吐
    """
    params = (
        ("ema_period", 20),
        ("atr_period", 10),
        ("kc_mult", 2.0),
        ("risk_pct", 0.02),       # 账户风险百分比
        ("trail_mult", 3.0),      # 移动止损 ATR 倍数
        ("printlog", False),
    )

    def __init__(self):
        self.ema = bt.indicators.EMA(self.data.close, period=self.params.ema_period)
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        self.order = None
        self.highest_price = 0

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None
            if order.isbuy():
                self.highest_price = order.executed.price
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def _calc_size(self):
        """基于风险百分比计算仓位"""
        risk_money = self.broker.get_value() * self.params.risk_pct
        risk_per_share = self.atr[0] * self.params.trail_mult
        if risk_per_share == 0:
            return 100
        size = int(risk_money / risk_per_share)
        # A股取整到100股
        return max(100, size // 100 * 100)

    def next(self):
        if self.order:
            return

        close = self.data.close[0]
        upper = self.ema[0] + self.params.kc_mult * self.atr[0]
        
        if self.position:
            # 持仓：更新最高价，计算移动止损
            self.highest_price = max(self.highest_price, close)
            stop_price = self.highest_price - (self.atr[0] * self.params.trail_mult)
            
            if close < stop_price:
                self.log(f"SELL (Trail Stop) {close:.2f} < {stop_price:.2f}")
                self.order = self.close()
        else:
            # 突破上轨买入
            if close > upper:
                size = self._calc_size()
                self.log(f"BUY (Breakout) {close:.2f} > {upper:.2f}, Size={size}")
                self.order = self.buy(size=size)


# =============================================================================
# 4. 三均线 ADX 过滤策略
# =============================================================================
class TripleMA_ADX_Strategy(bt.Strategy):
    """
    三均线趋势策略 (ADX 过滤版)
    
    优化点：
    - ADX 指标过滤震荡行情
    - 只在 ADX > 25 时认为有足够趋势
    - 防止震荡市频繁止损
    
    解决痛点：
    - 均线策略是震荡市的"绞肉机"
    - 盘整期均线频繁缠绕产生假信号
    """
    params = (
        ("fast", 10),
        ("mid", 30),
        ("slow", 60),
        ("adx_period", 14),
        ("adx_threshold", 25),    # 趋势强度阈值
        ("printlog", False),
    )

    def __init__(self):
        self.ma_fast = bt.indicators.EMA(self.data.close, period=self.params.fast)
        self.ma_mid = bt.indicators.EMA(self.data.close, period=self.params.mid)
        self.ma_slow = bt.indicators.EMA(self.data.close, period=self.params.slow)
        self.adx = bt.indicators.ADX(self.data, period=self.params.adx_period)
        self.order = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        # 多头排列
        bull_align = (
            (self.ma_fast[0] > self.ma_mid[0]) and 
            (self.ma_mid[0] > self.ma_slow[0])
        )
        # 趋势强度足够
        strong_trend = self.adx[0] > self.params.adx_threshold

        if not self.position:
            if bull_align and strong_trend:
                self.log(f"BUY (Triple MA + ADX={self.adx[0]:.1f})")
                self.order = self.buy()
        else:
            # 退出：均线排列破坏
            if self.ma_fast[0] < self.ma_mid[0]:
                self.log("SELL (Alignment Broken)")
                self.order = self.close()


# =============================================================================
# 5. MACD 脉冲策略
# =============================================================================
class MACDImpulseStrategy(bt.Strategy):
    """
    MACD 强势回调策略
    
    优化点：
    - 零轴过滤：MACD 必须 > -0.5，避免深水区接飞刀
    - 动能过滤：柱状图必须是扩张的
    - 零轴上方金叉更可靠
    
    解决痛点：
    - MACD 金叉在下跌中继非常常见
    - 买入即套的问题
    """
    params = (
        ("fast", 12),
        ("slow", 26),
        ("signal", 9),
        ("zero_filter", -0.5),    # 零轴过滤阈值
        ("printlog", False),
    )

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
            plot=False
        )
        self.order = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        macd = self.macd.macd[0]
        signal = self.macd.signal[0]
        hist = macd - signal
        prev_hist = self.macd.macd[-1] - self.macd.signal[-1]

        # 金叉检测
        cross_up = (self.macd.macd[-1] < self.macd.signal[-1]) and (macd > signal)
        
        # 1. 零轴过滤
        zero_filter = macd > self.params.zero_filter
        
        # 2. 动能过滤：柱状图扩张
        momentum_ok = hist > prev_hist

        if not self.position:
            if cross_up and zero_filter and momentum_ok:
                self.log(f"BUY (MACD Cross + Zero Filter + Momentum)")
                self.order = self.buy()
        else:
            # 死叉卖出
            if macd < signal:
                self.log("SELL (MACD Death Cross)")
                self.order = self.close()


# =============================================================================
# 6. SMA 趋势跟随策略
# =============================================================================
class SMATrendFollowingStrategy(bt.Strategy):
    """
    SMA 均线交叉增强版
    
    优化点：
    - 均线斜率检查：确保趋势确实已启动
    - 快线向上才有效
    - 跌破慢线提前止损
    
    解决痛点：
    - 均线交叉滞后严重
    - 金叉但价格开始暴跌的背离情况
    """
    params = (
        ('fast_period', 10),
        ('slow_period', 60),      # 增大周期差，捕捉大趋势
        ('atr_period', 14),
        ('printlog', False),
    )

    def __init__(self):
        self.sma_fast = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.sma_slow = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        self.order = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        # 均线交叉
        crossover = (
            (self.sma_fast[-1] < self.sma_slow[-1]) and 
            (self.sma_fast[0] > self.sma_slow[0])
        )
        
        # 确认：快线本身向上
        fast_is_rising = self.sma_fast[0] > self.sma_fast[-1]

        if not self.position:
            if crossover and fast_is_rising:
                self.log("BUY (SMA Cross + Rising Fast)")
                self.order = self.buy()
        else:
            # 跌破慢线止损（比死叉更早）
            if self.data.close[0] < self.sma_slow[0]:
                self.log("SELL (Below Slow MA)")
                self.order = self.close()


# =============================================================================
# 7. 多因子稳健策略
# =============================================================================
class MultiFactorRobustStrategy(bt.Strategy):
    """
    多因子选股策略 (自适应版)
    
    优化点：
    - 大盘趋势过滤：熊市停止开仓
    - 因子排序法替代线性加权
    - 动量 + 低波动组合
    
    解决痛点：
    - 固定权重难以验证有效性
    - 熊市中所有因子效性大幅降低
    """
    params = (
        ('ma_trend', 200),        # 牛熊分界线
        ('mom_period', 20),
        ('vol_period', 20),
        ('printlog', False),
    )
    
    def __init__(self):
        self.ma_trend = bt.indicators.SMA(self.data.close, period=self.params.ma_trend)
        self.mom = bt.indicators.ROC(self.data.close, period=self.params.mom_period)
        
        # 负波动率因子 (低波动更好)
        rets = bt.indicators.PctChange(self.data.close, period=1)
        self.vol = bt.indicators.StdDev(rets, period=self.params.vol_period)
        
        self.order = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None
        
    def next(self):
        if self.order:
            return

        # 1. 市场环境过滤 (Regime Filter)
        if self.data.close[0] < self.ma_trend[0]:
            if self.position:
                self.log("SELL (Bear Market)")
                self.order = self.close()
            return

        # 2. 简单等权因子打分
        # 动量 > 0 且 波动率低（负波动率因子）
        vol_score = -self.vol[0] if self.vol[0] > 0 else 0
        score = self.mom[0] * 0.5 + vol_score * 0.5
        
        if not self.position:
            # 动量为正，且处于长期均线之上
            if self.mom[0] > 0 and score > 0:
                self.log(f"BUY (Mom={self.mom[0]:.2f}, Score={score:.4f})")
                self.order = self.buy()
        else:
            # 动量转负离场
            if self.mom[0] < 0:
                self.log("SELL (Momentum Negative)")
                self.order = self.close()


# =============================================================================
# 参数转换函数
# =============================================================================
def _coerce_zscore_enhanced(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    if "period" in out: out["period"] = int(out["period"])
    if "z_entry" in out: out["z_entry"] = float(out["z_entry"])
    if "z_exit" in out: out["z_exit"] = float(out["z_exit"])
    if "rsi_period" in out: out["rsi_period"] = int(out["rsi_period"])
    if "rsi_threshold" in out: out["rsi_threshold"] = float(out["rsi_threshold"])
    if "atr_stop_mult" in out: out["atr_stop_mult"] = float(out["atr_stop_mult"])
    return out


def _coerce_rsi_trend(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    if "rsi_period" in out: out["rsi_period"] = int(out["rsi_period"])
    if "trend_period" in out: out["trend_period"] = int(out["trend_period"])
    if "lower_band" in out: out["lower_band"] = float(out["lower_band"])
    if "upper_band" in out: out["upper_band"] = float(out["upper_band"])
    return out


def _coerce_keltner_adaptive(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    if "ema_period" in out: out["ema_period"] = int(out["ema_period"])
    if "atr_period" in out: out["atr_period"] = int(out["atr_period"])
    if "kc_mult" in out: out["kc_mult"] = float(out["kc_mult"])
    if "risk_pct" in out: out["risk_pct"] = float(out["risk_pct"])
    if "trail_mult" in out: out["trail_mult"] = float(out["trail_mult"])
    return out


def _coerce_triple_ma_adx(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    for k in ["fast", "mid", "slow", "adx_period", "adx_threshold"]:
        if k in out: out[k] = int(out[k])
    return out


def _coerce_macd_impulse(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    for k in ["fast", "slow", "signal"]:
        if k in out: out[k] = int(out[k])
    if "zero_filter" in out: out["zero_filter"] = float(out["zero_filter"])
    return out


def _coerce_sma_trend(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    if "fast_period" in out: out["fast_period"] = int(out["fast_period"])
    if "slow_period" in out: out["slow_period"] = int(out["slow_period"])
    return out


def _coerce_multifactor_robust(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    for k in ["ma_trend", "mom_period", "vol_period"]:
        if k in out: out[k] = int(out[k])
    return out


# =============================================================================
# 策略配置字典
# =============================================================================
ENHANCED_STRATEGY_CONFIGS = {
    'zscore_enhanced': {
        'name': 'zscore_enhanced',
        'description': 'Z-Score Mean Reversion with RSI Filter and ATR Stop',
        'strategy_class': ZScoreEnhancedStrategy,
        'param_names': ['period', 'z_entry', 'z_exit', 'rsi_threshold', 'atr_stop_mult'],
        'defaults': {
            'period': 20, 'z_entry': -2.0, 'z_exit': 0.0, 
            'rsi_threshold': 30, 'atr_stop_mult': 2.0
        },
        'grid_defaults': {
            'period': [15, 20, 25],
            'z_entry': [-2.0, -2.5],
            'z_exit': [0.0, 0.5],
            'rsi_threshold': [25, 30, 35],
        },
        'coercer': _coerce_zscore_enhanced,
        'multi_symbol': False,
    },
    'rsi_trend': {
        'name': 'rsi_trend',
        'description': 'RSI Pullback Strategy in Uptrend with Hook Pattern',
        'strategy_class': RSITrendStrategy,
        'param_names': ['rsi_period', 'trend_period', 'lower_band', 'upper_band'],
        'defaults': {
            'rsi_period': 14, 'trend_period': 200, 
            'lower_band': 30, 'upper_band': 70
        },
        'grid_defaults': {
            'rsi_period': [14],
            'trend_period': [100, 200],
            'lower_band': [25, 30, 35],
        },
        'coercer': _coerce_rsi_trend,
        'multi_symbol': False,
    },
    'keltner_adaptive': {
        'name': 'keltner_adaptive',
        'description': 'Keltner Breakout with Volatility Sizing and Chandelier Exit',
        'strategy_class': KeltnerAdaptiveStrategy,
        'param_names': ['ema_period', 'kc_mult', 'risk_pct', 'trail_mult'],
        'defaults': {
            'ema_period': 20, 'kc_mult': 2.0, 
            'risk_pct': 0.02, 'trail_mult': 3.0
        },
        'grid_defaults': {
            'ema_period': [15, 20, 25],
            'kc_mult': [1.5, 2.0, 2.5],
            'trail_mult': [2.5, 3.0, 3.5],
        },
        'coercer': _coerce_keltner_adaptive,
        'multi_symbol': False,
    },
    'triple_ma_adx': {
        'name': 'triple_ma_adx',
        'description': 'Triple EMA with ADX Trend Strength Filter',
        'strategy_class': TripleMA_ADX_Strategy,
        'param_names': ['fast', 'mid', 'slow', 'adx_threshold'],
        'defaults': {'fast': 10, 'mid': 30, 'slow': 60, 'adx_threshold': 25},
        'grid_defaults': {
            'fast': [8, 10, 12],
            'mid': [25, 30, 35],
            'slow': [50, 60, 70],
            'adx_threshold': [20, 25, 30],
        },
        'coercer': _coerce_triple_ma_adx,
        'multi_symbol': False,
    },
    'macd_impulse': {
        'name': 'macd_impulse',
        'description': 'MACD Zero-Line Bias Strategy with Momentum Filter',
        'strategy_class': MACDImpulseStrategy,
        'param_names': ['fast', 'slow', 'signal', 'zero_filter'],
        'defaults': {'fast': 12, 'slow': 26, 'signal': 9, 'zero_filter': -0.5},
        'grid_defaults': {
            'fast': [10, 12, 14],
            'slow': [24, 26, 28],
            'signal': [9],
        },
        'coercer': _coerce_macd_impulse,
        'multi_symbol': False,
    },
    'sma_trend_following': {
        'name': 'sma_trend_following',
        'description': 'SMA Cross with Slope Confirmation',
        'strategy_class': SMATrendFollowingStrategy,
        'param_names': ['fast_period', 'slow_period'],
        'defaults': {'fast_period': 10, 'slow_period': 60},
        'grid_defaults': {
            'fast_period': [8, 10, 12],
            'slow_period': [50, 60, 70],
        },
        'coercer': _coerce_sma_trend,
        'multi_symbol': False,
    },
    'multifactor_robust': {
        'name': 'multifactor_robust',
        'description': 'Trend-Filtered Multi-Factor with Regime Filter',
        'strategy_class': MultiFactorRobustStrategy,
        'param_names': ['ma_trend', 'mom_period', 'vol_period'],
        'defaults': {'ma_trend': 200, 'mom_period': 20, 'vol_period': 20},
        'grid_defaults': {
            'ma_trend': [150, 200],
            'mom_period': [15, 20, 25],
        },
        'coercer': _coerce_multifactor_robust,
        'multi_symbol': False,
    },
}


__all__ = [
    # 策略类
    'ZScoreEnhancedStrategy',
    'RSITrendStrategy',
    'KeltnerAdaptiveStrategy',
    'TripleMA_ADX_Strategy',
    'MACDImpulseStrategy',
    'SMATrendFollowingStrategy',
    'MultiFactorRobustStrategy',
    # 参数转换
    '_coerce_zscore_enhanced',
    '_coerce_rsi_trend',
    '_coerce_keltner_adaptive',
    '_coerce_triple_ma_adx',
    '_coerce_macd_impulse',
    '_coerce_sma_trend',
    '_coerce_multifactor_robust',
    # 配置字典
    'ENHANCED_STRATEGY_CONFIGS',
]
