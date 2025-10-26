"""
Triple Moving Average趋势策略 (Backtrader版本)
当快速均线>中速均线>慢速均线时买入（多头排列），反之卖出
"""
import backtrader as bt
from typing import Dict, Any


class TripleMAStrategy(bt.Strategy):
    """
    Triple moving average trend (fast>mid>slow) with ATR sizing.
    Buy when fast MA > mid MA > slow MA (bullish alignment).
    Sell when alignment breaks.
    """
    params = (
        ("fast", 5),
        ("mid", 20),
        ("slow", 60),
        ("printlog", False),
    )

    def __init__(self):
        self.ma_fast = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.fast
        )
        self.ma_mid = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.mid
        )
        self.ma_slow = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.slow
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

        fast = self.ma_fast[0]
        mid = self.ma_mid[0]
        slow = self.ma_slow[0]

        bullish_alignment = (fast > mid) and (mid > slow)

        if not self.position:
            if bullish_alignment:
                self.log(
                    f"BUY CREATE (triple MA bullish), "
                    f"fast={fast:.2f} > mid={mid:.2f} > slow={slow:.2f}"
                )
                self.order = self.buy()
        else:
            if not bullish_alignment:
                self.log(
                    f"SELL CREATE (triple MA broken), "
                    f"fast={fast:.2f}, mid={mid:.2f}, slow={slow:.2f}"
                )
                self.order = self.sell()


def _coerce_tma(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Triple MA parameters to correct types."""
    out = params.copy()
    for k in ("fast", "mid", "slow"):
        if k in out:
            out[k] = int(out[k])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'triple_ma',
    'description': 'Triple moving average trend (fast>mid>slow) with ATR sizing',
    'strategy_class': TripleMAStrategy,
    'param_names': ['fast', 'mid', 'slow'],
    'defaults': {'fast': 5, 'mid': 20, 'slow': 60},
    'grid_defaults': {
        'fast': [5, 8],
        'mid': [18, 20, 22],
        'slow': [55, 60, 65]
    },
    'coercer': _coerce_tma,
    'multi_symbol': False,
}
