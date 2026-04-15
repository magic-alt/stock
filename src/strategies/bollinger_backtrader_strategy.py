"""
Bollinger Bands均值回归策略 (Backtrader版本)
当价格触及下轨时买入，触及上轨或中轨时卖出

V3.0.0 优化:
- 增加 RSI 超卖确认，过滤假突破
- 只在 RSI < rsi_oversold 时才触发买入
"""
import backtrader as bt
from typing import Dict, Any


class BollingerStrategy(bt.Strategy):
    """
    Bollinger band mean reversion with RSI confirmation.
    
    V3.0.0 优化:
    - rsi_period: RSI 计算周期 (默认 14)
    - rsi_oversold: RSI 超卖阈值 (默认 30)
    - 只在价格触及下轨 AND RSI < rsi_oversold 时买入
    - 避免正常回调被误判为超卖
    
    Entry modes:
    - 'pierce': Enter when price pierces lower band
    - 'close_below': Enter when close is below lower band by below_pct%
    
    Exit modes:
    - 'mid': Exit at middle band
    - 'upper': Exit at upper band
    """
    params = (
        ("period", 20),
        ("devfactor", 2.0),
        ("entry_mode", "pierce"),
        ("below_pct", 0.0),
        ("exit_mode", "mid"),
        ("rsi_period", 14),       # V3.0: RSI 周期
        ("rsi_oversold", 30),     # V3.0: RSI 超卖阈值
        ("printlog", False),
    )

    def __init__(self):
        self.bb = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.period,
            devfactor=self.params.devfactor,
        )
        # V3.0: RSI 指标
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.params.rsi_period)
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

        close = self.data.close[0]
        bot = self.bb.bot[0]
        mid = self.bb.mid[0]
        top = self.bb.top[0]
        rsi = self.rsi[0]  # V3.0

        if not self.position:
            # V3.0: RSI 超卖确认
            rsi_oversold = rsi < self.params.rsi_oversold
            
            # Entry logic
            if self.params.entry_mode == "pierce":
                if close < bot and rsi_oversold:
                    self.log(f"BUY CREATE (pierce lower + RSI {rsi:.1f}), {close:.2f} < {bot:.2f}")
                    self.order = self.buy()
            elif self.params.entry_mode == "close_below":
                threshold = bot * (1.0 - self.params.below_pct / 100.0)
                if close < threshold and rsi_oversold:
                    self.log(f"BUY CREATE (close_below + RSI {rsi:.1f}), {close:.2f} < {threshold:.2f}")
                    self.order = self.buy()
        else:
            # Exit logic
            if self.params.exit_mode == "mid":
                if close >= mid:
                    self.log(f"SELL CREATE (reached mid), {close:.2f} >= {mid:.2f}")
                    self.order = self.close()
            elif self.params.exit_mode == "upper":
                if close >= top:
                    self.log(f"SELL CREATE (reached upper), {close:.2f} >= {top:.2f}")
                    self.order = self.close()


def _coerce_bb(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Bollinger parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    if "devfactor" in out:
        out["devfactor"] = float(out["devfactor"])
    if "below_pct" in out:
        out["below_pct"] = float(out["below_pct"])
    if "entry_mode" in out:
        out["entry_mode"] = str(out["entry_mode"])
    if "exit_mode" in out:
        out["exit_mode"] = str(out["exit_mode"])
    # V3.0: RSI 参数
    if "rsi_period" in out:
        out["rsi_period"] = int(out["rsi_period"])
    if "rsi_oversold" in out:
        out["rsi_oversold"] = float(out["rsi_oversold"])
    # 增强版参数
    if "atr_period" in out:
        out["atr_period"] = int(out["atr_period"])
    if "atr_mult_sl" in out:
        out["atr_mult_sl"] = float(out["atr_mult_sl"])
    if "tp1_pct" in out:
        out["tp1_pct"] = float(out["tp1_pct"])
    if "tp1_frac" in out:
        out["tp1_frac"] = float(out["tp1_frac"])
    if "tp2_pct" in out:
        out["tp2_pct"] = float(out["tp2_pct"])
    if "tp2_frac" in out:
        out["tp2_frac"] = float(out["tp2_frac"])
    if "trail_drop_pct" in out:
        out["trail_drop_pct"] = float(out["trail_drop_pct"])
    if "min_hold" in out:
        out["min_hold"] = int(out["min_hold"])
    if "cooldown" in out:
        out["cooldown"] = int(out["cooldown"])
    if "warmup_bars" in out:
        val = out["warmup_bars"]
        out["warmup_bars"] = int(val) if val is not None else None
    if "trend_filter" in out:
        out["trend_filter"] = bool(out["trend_filter"])
    # V2.8.4.1 新增参数
    if "rebound_lookback" in out:
        out["rebound_lookback"] = int(out["rebound_lookback"])
    if "max_hold" in out:
        out["max_hold"] = int(out["max_hold"])
    return out


class Bollinger_EnhancedStrategy(bt.Strategy):
    """
    布林增强版：
    - 触发：跌破下轨后反弹（反穿下轨）
    - 分批止盈：tp1_pct / tp2_pct（到价卖出 tp1_frac / tp2_frac）
    - 回落出场：从持仓最高价回撤 trail_drop_pct 全清
    - 动态止损：ATR * atr_mult_sl
    - 预热期/冷却期/最小持有/趋势过滤（中轨斜率>0才做多，可关闭）
    - V2.8.4.1: rebound_lookback, max_hold, ATR fallback, dynamic warmup
    """
    params = (
        ("period", 20),
        ("devfactor", 2.0),

        ("atr_period", 14),
        ("atr_mult_sl", 2.0),         # 动态止损系数（放宽至2.0）

        ("tp1_pct", 0.03),            # +3% 触发 TP1
        ("tp1_frac", 0.5),            # 卖出 50%
        ("tp2_pct", 0.06),            # +6% 触发 TP2
        ("tp2_frac", 1.0),            # 卖出剩余全部(=1.0 相当于清仓)

        ("trail_drop_pct", 0.04),     # 从最高价回落 4% 清仓
        ("min_hold", 2),              # 最少持有 bars（放宽至2）
        ("cooldown", 3),              # 平仓后冷却 bars（放宽至3）
        ("warmup_bars", None),        # 自动计算
        ("rebound_lookback", 3),      # 最近N根在下轨下，当前收回到下轨上
        ("max_hold", 60),             # 最长持有N根，超时离场

        ("trend_filter", True),       # 中轨斜率>0 才允许做多
        ("printlog", False),
    )

    def __init__(self):
        # 布林
        bb = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.period,
            devfactor=self.params.devfactor,
            subplot=False, plotmaster=self.data  # 叠加到主图
        )
        self.mid = bb.mid
        self.top = bb.top
        self.bot = bb.bot

        # ATR 动态止损
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period, plot=False)

        # 中轨斜率（趋势过滤）
        self.mid_slope = self.mid - self.mid(-1)

        # 状态
        self.order = None
        self.entry_bar = None
        self.entry_price = None
        self.highest_since_entry = None
        self.tp1_done = False
        self.tp2_done = False
        self.last_exit_bar = -1_000_000
        
        # 自动 warmup
        self._warmup = (self.params.warmup_bars
                        if self.params.warmup_bars is not None
                        else max(self.params.period, self.params.atr_period, 30))

    def log(self, s):
        if self.params.printlog:
            dt = self.datas[0].datetime.date(0).isoformat()
            print(dt, s)

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

        # 预热期：只计算不交易
        if i < self._warmup:
            return

        # 冷却期：刚平仓不再开仓
        if (i - self.last_exit_bar) < int(self.params.cooldown):
            pass_cooldown = False
        else:
            pass_cooldown = True

        # 在持仓期间处理分批/止损/回落
        if self.position:
            atr = self._atr_safe()
            risk_abs = max(self.params.atr_mult_sl * atr, 0.01 * close)  # 最小1%
            hold_bars = i - (self.entry_bar or i)
            if hold_bars >= int(self.params.min_hold):
                # 持仓最高价
                self.highest_since_entry = max(self.highest_since_entry or close, close)

                # 回落出场
                if self.params.trail_drop_pct > 0 and self.highest_since_entry:
                    drop = (self.highest_since_entry - close) / self.highest_since_entry
                    if drop >= self.params.trail_drop_pct:
                        self.log(f"TRAIL EXIT @ {close:.2f}")
                        self.order = self.close()  # 清仓
                        self._mark_exit(i)
                        return

                # 动态止损（基于 ATR）
                if self.params.atr_mult_sl > 0 and self.entry_price is not None:
                    stop = self.entry_price - risk_abs
                    if close <= stop:
                        self.log(f"ATR STOP @ {close:.2f} (stop {stop:.2f})")
                        self.order = self.close()
                        self._mark_exit(i)
                        return

                # 分批止盈
                ret = (close / self.entry_price) - 1.0 if self.entry_price else 0.0

                # TP1
                if (not self.tp1_done) and ret >= self.params.tp1_pct and self.position.size > 0:
                    sz = max(1, int(self.position.size * self.params.tp1_frac + 0.5))
                    sz = min(sz, self.position.size)
                    self.log(f"TP1 SELL {sz} @ {close:.2f}")
                    self.order = self.sell(size=sz)
                    self.tp1_done = True
                    return

                # TP2（清掉剩余）
                if (not self.tp2_done) and ret >= self.params.tp2_pct and self.position.size > 0:
                    self.log(f"TP2 EXIT ALL @ {close:.2f}")
                    self.order = self.close()
                    self.tp2_done = True
                    self._mark_exit(i)
                    return

            # 超时离场（回到中轨附近）
            if (i - (self.entry_bar or i)) >= int(self.params.max_hold):
                if close >= float(self.mid[0]):
                    self.order = self.close()
                    self._mark_exit(i)
                    self.log(f"TIME EXIT @ {close:.2f}")
                    return

            return

        # 入场逻辑（空仓且通过冷却+趋势过滤）
        if (not self.position) and pass_cooldown:
            trend_ok = True
            if self.params.trend_filter:
                trend_ok = (float(self.mid_slope[0]) >= 0)

            # 反穿下轨：最近 N 根任意一根在下轨下，且当前收盘>下轨
            lookback = min(int(self.params.rebound_lookback), i - 1)
            below_recent = any(float(self.data.close[-k]) < float(self.bot[-k]) for k in range(1, lookback + 1))
            rebound_now = close > float(self.bot[0])

            if trend_ok and below_recent and rebound_now:
                self.order = self.buy()
                self.entry_bar = i
                self.entry_price = close
                self.highest_since_entry = close
                self.tp1_done = False
                self.tp2_done = False
                self.log(f"BUY @ {close:.2f} (trend_ok={trend_ok})")

    def notify_order(self, order):
        # 避免挂单阻塞
        if order.status in [order.Completed, order.Canceled, order.Rejected]:
            self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.last_exit_bar = len(self)
            self.entry_bar = None
            self.entry_price = None
            self.highest_since_entry = None
            self.tp1_done = False
            self.tp2_done = False

    def _mark_exit(self, i_bar: int):
        self.last_exit_bar = i_bar
        self.entry_bar = None
        self.entry_price = None
        self.highest_since_entry = None
        self.tp1_done = False
        self.tp2_done = False


# 策略配置
STRATEGY_CONFIG = {
    'name': 'bollinger',
    'description': 'Bollinger band mean reversion with RSI confirmation',
    'strategy_class': BollingerStrategy,
    'param_names': ['period', 'devfactor', 'entry_mode', 'below_pct', 'exit_mode', 'rsi_period', 'rsi_oversold'],
    'defaults': {
        'period': 20,
        'devfactor': 2.0,
        'entry_mode': 'pierce',
        'below_pct': 0.0,
        'exit_mode': 'mid',
        'rsi_period': 14,
        'rsi_oversold': 30,
    },
    'grid_defaults': {
        'period': list(range(10, 31, 5)),
        'devfactor': [1.5, 2.0, 2.5],
        'entry_mode': ['pierce'],
        'exit_mode': ['mid'],
        'rsi_oversold': [25, 30, 35],
    },
    'coercer': _coerce_bb,
    'multi_symbol': False,
}
