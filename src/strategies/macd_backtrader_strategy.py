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
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, 0)
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
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
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
    return out
