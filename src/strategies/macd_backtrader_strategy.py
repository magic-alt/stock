"""
MACD策略 (Backtrader版本)
当MACD线上穿信号线时买入，下穿时卖出
"""
import backtrader as bt
from typing import Dict, Any


class MACDStrategy(bt.Strategy):
    """
    MACD crossover strategy: buy when MACD crosses above signal, sell when it crosses below.
    """
    params = (
        ("fast", 12),
        ("slow", 26),
        ("signal", 9),
        ("printlog", False),
    )

    def __init__(self):
        # 关闭策略内部MACD的绘图（绘图由engine.py统一添加）
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
            plot=False  # 关键：避免与engine.py的绘图指标重复
        )
        # 关闭绘图，避免额外子图
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal, plot=False)
        self.order = None

    def log(self, txt: str, dt=None):
        """Logging helper."""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
            elif order.issell():
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f"TRADE PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}")

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.crossover > 0:
                self.log(f"BUY CREATE (MACD cross up), {self.data.close[0]:.2f}")
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.log(f"SELL CREATE (MACD cross down), {self.data.close[0]:.2f}")
                self.order = self.sell()


class MACDZeroCrossStrategy(bt.Strategy):
    """
    MACD Zero Line crossover strategy
    - Buy when MACD crosses above zero
    - Sell when MACD crosses below zero
    """
    params = (
        ("fast", 12),
        ("slow", 26),
        ("signal", 9),
        ("printlog", False),
    )

    def __init__(self):
        # 关闭策略内部MACD的绘图（绘图由engine.py统一添加）
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
            plot=False  # 关键：避免与engine.py的绘图指标重复
        )
        # 关闭绘图，避免额外子图
        self.crossover = bt.indicators.CrossOver(self.macd.macd, 0, plot=False)
        self.order = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.crossover > 0:  # MACD crosses above zero
                self.log(f"BUY CREATE (MACD > 0), {self.data.close[0]:.2f}")
                self.order = self.buy()
        else:
            if self.crossover < 0:  # MACD crosses below zero
                self.log(f"SELL CREATE (MACD < 0), {self.data.close[0]:.2f}")
                self.order = self.sell()


class MACDHistogramStrategy(bt.Strategy):
    """
    MACD Histogram momentum strategy
    - Buy when histogram turns from negative to positive
    - Sell when histogram turns from positive to negative
    """
    params = (
        ("fast", 12),
        ("slow", 26),
        ("signal", 9),
        ("threshold", 0.0),
        ("printlog", False),
    )

    def __init__(self):
        # 关闭策略内部MACD的绘图（绘图由engine.py统一添加）
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
            plot=False  # 关键：避免与engine.py的绘图指标重复
        )
        # Histogram is macd - signal
        self.histogram = self.macd.macd - self.macd.signal
        self.order = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order or len(self) < 2:
            return

        hist_now = self.histogram[0]
        hist_prev = self.histogram[-1]

        if not self.position:
            # Buy when histogram turns positive
            if hist_prev <= self.params.threshold and hist_now > self.params.threshold:
                self.log(f"BUY CREATE (Hist turn positive), {self.data.close[0]:.2f}")
                self.order = self.buy()
        else:
            # Sell when histogram turns negative
            if hist_prev >= -self.params.threshold and hist_now < -self.params.threshold:
                self.log(f"SELL CREATE (Hist turn negative), {self.data.close[0]:.2f}")
                self.order = self.sell()


def _coerce_macd(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce MACD parameters to correct types."""
    out = params.copy()
    for k in ("fast", "slow", "signal"):
        if k in out:
            out[k] = int(out[k])
    if 'threshold' in out:
        out['threshold'] = float(out['threshold'])
    if 'ema_trend_period' in out:
        out['ema_trend_period'] = int(out['ema_trend_period'])
    if 'cooldown' in out:
        out['cooldown'] = int(out['cooldown'])
    if 'min_hold' in out:
        out['min_hold'] = int(out['min_hold'])
    if 'stop_loss_pct' in out:
        out['stop_loss_pct'] = float(out['stop_loss_pct'])
    if 'take_profit_pct' in out:
        out['take_profit_pct'] = float(out['take_profit_pct'])
    if 'trend_filter' in out:
        out['trend_filter'] = bool(out['trend_filter'])
    # Regime Pullback 参数
    if 'roc_period' in out:
        out['roc_period'] = int(out['roc_period'])
    if 'ema_entry_period' in out:
        out['ema_entry_period'] = int(out['ema_entry_period'])
    if 'pullback_k' in out:
        out['pullback_k'] = float(out['pullback_k'])
    if 'max_lag' in out:
        out['max_lag'] = int(out['max_lag'])
    if 'atr_period' in out:
        out['atr_period'] = int(out['atr_period'])
    if 'atr_sl_mult' in out:
        out['atr_sl_mult'] = float(out['atr_sl_mult'])
    if 'atr_trail_mult' in out:
        out['atr_trail_mult'] = float(out['atr_trail_mult'])
    if 'tp1_R' in out:
        out['tp1_R'] = float(out['tp1_R'])
    if 'tp1_frac' in out:
        out['tp1_frac'] = float(out['tp1_frac'])
    if 'tp2_R' in out:
        out['tp2_R'] = float(out['tp2_R'])
    # V2.8.4.1 新增参数
    if 'trend_logic' in out:
        out['trend_logic'] = str(out['trend_logic']).lower()
    return out


class MACD_RegimePullback(bt.Strategy):
    """
    MACD 盈利增强：趋势过滤 + 回落入场 + ATR 风险控制 + 冷却/最小持有 + 分批止盈
    - 只做多（A股）；如需双向可扩展
    - V2.8.4.1: 放宽条件，trend_logic='or'，ATR fallback，动态 warmup
    """
    params = (
        # MACD
        ("fast", 12), ("slow", 26), ("signal", 9),

        # Regime 过滤
        ("ema_trend_period", 200),
        ("roc_period", 100),
        ("trend_filter", True),
        ("trend_logic", "or"),      # 'or' 更宽松：EMA斜率>0 或 ROC>0 即可

        # Pullback 入场
        ("ema_entry_period", 20),
        ("pullback_k", 0.5),        # k*ATR，默认 0.5
        ("max_lag", 7),             # 金叉后允许等待更久

        # 风险控制
        ("atr_period", 14),
        ("atr_sl_mult", 2.0),       # 初始止损 = entry - 2*ATR（略放宽）
        ("atr_trail_mult", 1.8),    # 移动止损 = high_since - 1.8*ATR
        ("min_hold", 2),
        ("cooldown", 3),

        # 分批止盈（以R度量；R=初始止损距离；ATR缺失时用 1% 替代）
        ("tp1_R", 0.8), ("tp1_frac", 0.5),
        ("tp2_R", 1.6),

        ("printlog", False),
    )

    def __init__(self):
        # 指标（关闭MACD绘图，避免与engine.py重复）
        self.macd = bt.indicators.MACD(self.data.close,
                                       period_me1=self.params.fast,
                                       period_me2=self.params.slow,
                                       period_signal=self.params.signal,
                                       plot=False)  # 关键：避免重复绘制
        self.xover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal, plot=False)
        self.ema_trend = bt.indicators.EMA(self.data.close, period=self.params.ema_trend_period, plot=False)
        # 移除危险的数组操作：self.ema_trend_slope = self.ema_trend - self.ema_trend(-1)
        self.roc = bt.indicators.RateOfChange(self.data.close, period=self.params.roc_period, plot=False)
        self.ema_entry = bt.indicators.EMA(self.data.close, period=self.params.ema_entry_period, plot=False)
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period, plot=False)

        # 状态
        self.order = None
        self.entry_bar = None
        self.entry_price = None
        self.highest = None
        self.last_exit_bar = -1_000_000
        self.cross_bar = None
        self.tp1_done = False

        # 动态计算预热长度，防止越界
        self.warmup_bars = max(self.params.ema_trend_period,
                               self.params.roc_period,
                               self.params.ema_entry_period,
                               self.params.atr_period,
                               self.params.slow + self.params.signal + 2)

    def log(self, s):
        if self.params.printlog:
            print(self.datas[0].datetime.date(0).isoformat(), s)

    def prenext(self):
        """在指标未完全初始化时被调用，避免访问未就绪的数据"""
        pass

    def _atr_safe(self) -> float:
        """Safe ATR getter with fallback to 0"""
        try:
            import math
            v = float(self.atr[0])
            if not math.isfinite(v) or v <= 0:
                return 0.0
            return v
        except Exception:
            return 0.0

    def next(self):
        if self.order:
            return

        i = len(self)
        close = float(self.data.close[0])

        # 记录金叉bar
        if self.xover > 0:
            self.cross_bar = i

        # 先处理持仓
        if self.position:
            atr = self._atr_safe()
            r = max(self.params.atr_sl_mult * atr, 0.01 * close)  # ATR缺失时用 1%
            # 更新最高价
            self.highest = max(self.highest or close, close)

            # 移动止损
            trail = self.highest - self.params.atr_trail_mult * (atr if atr > 0 else 0.01 * close)
            init_sl = (self.entry_price or close) - r
            stop_line = max(trail, init_sl)

            # 分批止盈
            if (not self.tp1_done) and close >= (self.entry_price or close) + self.params.tp1_R * r:
                sz = max(1, int(self.position.size * self.params.tp1_frac + 0.5))
                sz = min(sz, self.position.size)
                self.order = self.sell(size=sz)
                self.tp1_done = True
                self.log(f"TP1 -> SELL {sz} @ {close:.2f}")
                return

            if close >= (self.entry_price or close) + self.params.tp2_R * r:
                self.order = self.close()
                self._after_exit(i)
                self.log(f"TP2 -> EXIT ALL @ {close:.2f}")
                return

            # 最小持有后再评估止损
            if (i - (self.entry_bar or i)) >= int(self.params.min_hold):
                if close <= stop_line:
                    self.order = self.close()
                    self._after_exit(i)
                    self.log(f"STOP EXIT @ {close:.2f} (stop {stop_line:.2f})")
                    return

            # 反向死叉也出
            if self.xover < 0:
                self.order = self.close()
                self._after_exit(i)
                self.log(f"SELL (cross down) @ {close:.2f}")
                return

            return

        # 未持仓：预热/冷却
        if i < self.warmup_bars:
            return
        if (i - self.last_exit_bar) < int(self.params.cooldown):
            return

        # 趋势过滤（更宽松：'or'）
        regime_ok = True
        if self.params.trend_filter:
            # 安全访问，避免数组越界
            ema_up = False
            if len(self.ema_trend) >= 2:
                ema_now = float(self.ema_trend[0])
                ema_prev = float(self.ema_trend[-1])
                ema_up = (ema_now > ema_prev)
            
            roc_up = (self.roc[0] > 0)
            
            if self.params.trend_logic.lower() == "and":
                regime_ok = ema_up and roc_up
            else:
                regime_ok = ema_up or roc_up
        if not regime_ok:
            return

        # 入场：金叉后的 max_lag 根内，满足回落-再起 或 MACD上行配合
        allow_window = (self.cross_bar is not None) and ((i - self.cross_bar) <= int(self.params.max_lag))
        if not allow_window:
            return

        atr = self._atr_safe()
        ema20 = float(self.ema_entry[0])
        pullback_line = ema20 - self.params.pullback_k * (atr if atr > 0 else 0.01 * close)
        
        # 安全访问MACD历史数据
        macd_up = False
        if len(self.macd.macd) >= 2:
            macd_up = self.macd.macd[0] > self.macd.macd[-1]

        cond_a = (float(self.data.low[0]) <= pullback_line) and (close > ema20)
        cond_b = (close <= ema20) and macd_up  # 相对温和

        if cond_a or cond_b:
            self.order = self.buy()
            self.entry_bar = i
            self.entry_price = close
            self.highest = close
            self.tp1_done = False
            self.log(f"BUY (regime+pullback) @ {close:.2f}")

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.last_exit_bar = len(self)
            self.entry_bar = None
            self.entry_price = None
            self.highest = None
            self.tp1_done = False

    def _after_exit(self, i):
        self.last_exit_bar = i
        self.entry_bar = None
        self.entry_price = None
        self.highest = None
        self.tp1_done = False


class MACD_EnhancedStrategy(bt.Strategy):
    """
    MACD 增强版策略：
    - 进出场仍然依据 MACD / Signal 金叉/死叉
    - 增加趋势过滤（EMA200 上升才允许做多）
    - 增加冷却期、最小持仓 bars、止损/止盈
    """
    params = (
        ("fast", 12),
        ("slow", 26),
        ("signal", 9),
        ("ema_trend_period", 200),
        ("trend_filter", True),
        ("cooldown", 5),             # 平仓后的冷却期
        ("min_hold", 3),             # 最小持仓 bars
        ("stop_loss_pct", 0.05),     # 5% 止损
        ("take_profit_pct", 0.10),   # 10% 止盈
        ("printlog", False),
    )

    def __init__(self):
        # 关闭策略内部MACD的绘图（绘图由engine.py统一添加）
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
            plot=False  # 关键：避免与engine.py的绘图指标重复
        )
        # 关闭绘图，避免子图
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal, plot=False)
        self.ema_trend = bt.indicators.ExponentialMovingAverage(
            self.data.close, 
            period=self.params.ema_trend_period, 
            plot=False
        )
        # 使用安全的方式计算斜率，避免数组越界
        # self.ema_trend_slope = self.ema_trend - self.ema_trend(-1)  # 危险：第一根K线会越界
        self.order = None
        self.last_exit_bar = -10**9
        self.entry_bar = None
        self.entry_price = None

    def log(self, txt: str, dt=None):
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def prenext(self):
        """在指标未完全初始化时被调用，避免访问未就绪的数据"""
        pass

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        i = len(self)
        close = float(self.data.close[0])

        # 确保有足够的历史数据
        if i < self.params.ema_trend_period + 1:
            return

        # 止损/止盈（持仓中）
        if self.position:
            hold_bars = i - (self.entry_bar or i)
            if hold_bars >= self.params.min_hold:
                if self.params.take_profit_pct > 0 and self.entry_price:
                    if close >= self.entry_price * (1.0 + self.params.take_profit_pct):
                        self.log(f"TAKE PROFIT @ {close:.2f}")
                        self.order = self.close()  # 修复：使用close()而非sell()
                        self.last_exit_bar = i
                        return
                if self.params.stop_loss_pct > 0 and self.entry_price:
                    if close <= self.entry_price * (1.0 - self.params.stop_loss_pct):
                        self.log(f"STOP LOSS @ {close:.2f}")
                        self.order = self.close()  # 修复：使用close()而非sell()
                        self.last_exit_bar = i
                        return

        # 冷却期：平仓后若干 bar 不再开仓
        if (i - self.last_exit_bar) < int(self.params.cooldown):
            return

        # 趋势过滤：EMA200 斜率>0 才允许做多（安全访问）
        trend_ok = True
        if self.params.trend_filter and len(self.ema_trend) >= 2:
            # 使用安全的索引访问，避免数组越界
            ema_now = float(self.ema_trend[0])
            ema_prev = float(self.ema_trend[-1])
            trend_ok = (ema_now > ema_prev)

        if not self.position:
            if trend_ok and self.crossover > 0:
                self.order = self.buy()
                self.entry_bar = i
                self.entry_price = close
                self.log(f"BUY (trend_ok={trend_ok}) @ {close:.2f}")
        else:
            if self.crossover < 0:
                self.order = self.close()  # 修复：使用close()而非sell()
                self.last_exit_bar = i
                self.log(f"SELL @ {close:.2f}")


# 供 CLI/注册表使用（结构对齐 Bollinger 模块）
STRATEGY_CONFIG = {
    'name': 'macd_e',
    'description': 'MACD with trend filter, cooldown and SL/TP',
    'strategy_class': MACD_EnhancedStrategy,
    'param_names': ['fast', 'slow', 'signal', 'ema_trend_period', 'trend_filter', 
                    'cooldown', 'min_hold', 'stop_loss_pct', 'take_profit_pct'],
    'defaults': {
        'fast': 12, 'slow': 26, 'signal': 9,
        'ema_trend_period': 200, 'trend_filter': True,
        'cooldown': 5, 'min_hold': 3,
        'stop_loss_pct': 0.05, 'take_profit_pct': 0.10,
    },
    'grid_defaults': {
        'fast': [8, 12], 'slow': [20, 26, 32], 'signal': [9],
        'ema_trend_period': [100, 150, 200],
        'trend_filter': [True],
        'cooldown': [3, 5, 8],
        'min_hold': [2, 3, 5],
        'stop_loss_pct': [0.03, 0.05, 0.08],
        'take_profit_pct': [0.07, 0.10, 0.15],
    },
    'coercer': _coerce_macd,
    'multi_symbol': False,
}

