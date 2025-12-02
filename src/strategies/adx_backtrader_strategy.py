"""
ADX趋势强度策略 (Backtrader版本)
当ADX高于阈值且+DI>-DI时买入，反之卖出

V3.0.0 优化:
- 增加 ATR 移动止损 (Trailing Stop) 锁定利润
- 解决 ADX 信号滞后导致的利润回吐问题
"""
import backtrader as bt
from typing import Dict, Any


class ADXTrendStrategy(bt.Strategy):
    """
    ADX(+DI/-DI) trend filter with ATR trailing stop.
    
    Buy when ADX > threshold and +DI > -DI (strong uptrend).
    Exit when ADX drops, +DI < -DI, OR trailing stop triggered.
    
    V3.0.0 优化:
    - trail_mult: ATR 移动止损倍数，锁定利润
    - 止损只能上移，不能下移
    """
    params = (
        ("adx_period", 14),
        ("adx_th", 25.0),
        ("atr_period", 14),        # V3.0: ATR 周期
        ("trail_mult", 2.0),       # V3.0: 移动止损 ATR 倍数
        ("printlog", False),
    )

    def __init__(self):
        # Backtrader's ADX indicator includes plusDI and minusDI
        self.adx_ind = bt.indicators.AverageDirectionalMovementIndex(
            self.data, period=self.params.adx_period
        )
        # V3.0: ATR 用于移动止损
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        self.order = None
        self.stop_price = None  # V3.0: 追踪止损价

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
                # V3.0: 初始化止损价
                self.stop_price = order.executed.price - (self.atr[0] * self.params.trail_mult)
            elif order.issell():
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
                self.stop_price = None
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

        adx = self.adx_ind.adx[0]
        plus_di = self.adx_ind.DIplus[0]
        minus_di = self.adx_ind.DIminus[0]

        strong_uptrend = (adx > self.params.adx_th) and (plus_di > minus_di)

        if not self.position:
            if strong_uptrend:
                self.log(
                    f"BUY CREATE (ADX trend), "
                    f"ADX={adx:.2f}, +DI={plus_di:.2f}, -DI={minus_di:.2f}"
                )
                self.order = self.buy()
        else:
            # V3.0: 移动止损逻辑
            new_stop = self.data.close[0] - (self.atr[0] * self.params.trail_mult)
            if self.stop_price is None:
                self.stop_price = new_stop
            else:
                # 止损只能上移，不能下移
                self.stop_price = max(self.stop_price, new_stop)
            
            # 出场条件1：ADX 趋势破坏
            if not strong_uptrend:
                self.log(
                    f"SELL CREATE (ADX trend broken), "
                    f"ADX={adx:.2f}, +DI={plus_di:.2f}, -DI={minus_di:.2f}"
                )
                self.order = self.close()
            # V3.0 出场条件2：触及移动止损
            elif self.data.close[0] < self.stop_price:
                self.log(f"SELL CREATE (Trailing Stop @ {self.stop_price:.2f})")
                self.order = self.close()


def _coerce_adx(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce ADX parameters to correct types."""
    out = params.copy()
    if "adx_period" in out:
        out["adx_period"] = int(out["adx_period"])
    if "adx_th" in out:
        out["adx_th"] = float(out["adx_th"])
    if "atr_period" in out:
        out["atr_period"] = int(out["atr_period"])
    if "trail_mult" in out:
        out["trail_mult"] = float(out["trail_mult"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'adx_trend',
    'description': 'ADX(+DI/-DI) trend filter with ATR trailing stop',
    'strategy_class': ADXTrendStrategy,
    'param_names': ['adx_period', 'adx_th', 'trail_mult'],
    'defaults': {'adx_period': 14, 'adx_th': 25.0, 'trail_mult': 2.0},
    'grid_defaults': {
        'adx_period': [12, 14, 16],
        'adx_th': [20, 25, 30],
        'trail_mult': [1.5, 2.0, 2.5],
    },
    'coercer': _coerce_adx,
    'multi_symbol': False,
}
