"""
ADX趋势强度策略 (Backtrader版本)
当ADX高于阈值且+DI>-DI时买入，反之卖出
"""
import backtrader as bt
from typing import Dict, Any


class ADXTrendStrategy(bt.Strategy):
    """
    ADX(+DI/-DI) trend filter with ATR sizing.
    Buy when ADX > threshold and +DI > -DI (strong uptrend).
    Sell when ADX drops or +DI < -DI.
    """
    params = (
        ("adx_period", 14),
        ("adx_th", 25.0),
        ("printlog", False),
    )

    def __init__(self):
        # Backtrader's ADX indicator includes plusDI and minusDI
        self.adx_ind = bt.indicators.AverageDirectionalMovementIndex(
            self.data, period=self.params.adx_period
        )
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
            if not strong_uptrend:
                self.log(
                    f"SELL CREATE (ADX trend broken), "
                    f"ADX={adx:.2f}, +DI={plus_di:.2f}, -DI={minus_di:.2f}"
                )
                self.order = self.sell()


def _coerce_adx(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce ADX parameters to correct types."""
    out = params.copy()
    if "adx_period" in out:
        out["adx_period"] = int(out["adx_period"])
    if "adx_th" in out:
        out["adx_th"] = float(out["adx_th"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'adx_trend',
    'description': 'ADX(+DI/-DI) trend filter with ATR sizing',
    'strategy_class': ADXTrendStrategy,
    'param_names': ['adx_period', 'adx_th'],
    'defaults': {'adx_period': 14, 'adx_th': 25.0},
    'grid_defaults': {
        'adx_period': [12, 14, 16],
        'adx_th': [20, 25, 30]
    },
    'coercer': _coerce_adx,
    'multi_symbol': False,
}
