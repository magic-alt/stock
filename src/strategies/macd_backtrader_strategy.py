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
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
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


def _coerce_macd(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce MACD parameters to correct types."""
    out = params.copy()
    for k in ("fast", "slow", "signal"):
        if k in out:
            out[k] = int(out[k])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'macd',
    'description': 'MACD signal crossover',
    'strategy_class': MACDStrategy,
    'param_names': ['fast', 'slow', 'signal'],
    'defaults': {'fast': 12, 'slow': 26, 'signal': 9},
    'grid_defaults': {
        'fast': list(range(4, 21, 2)),
        'slow': list(range(10, 41, 5)),
        'signal': [9]
    },
    'coercer': _coerce_macd,
    'multi_symbol': False,
}
