"""
EMA均线交叉策略 (Backtrader版本)
当价格向上突破EMA均线时买入，向下跌破时卖出
"""
import backtrader as bt
from typing import Dict, Any


class EMAStrategy(bt.Strategy):
    """
    EMA crossover strategy: buy when price crosses above EMA, sell when it crosses below.
    """
    params = (
        ("period", 20),
        ("printlog", False),
    )

    def __init__(self):
        # Check if we have enough data for the indicator
        data_len = len(self.data)
        if data_len < self.params.period:
            raise ValueError(
                f"EMA period ({self.params.period}) requires at least {self.params.period} "
                f"bars of data, but only {data_len} bars available. "
                f"Please use a shorter period or longer date range."
            )
        
        self.ema = bt.indicators.ExponentialMovingAverage(
            self.data.close, period=self.params.period
        )
        self.crossover = bt.indicators.CrossOver(self.data.close, self.ema)
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
                self.log(f"BUY CREATE, {self.data.close[0]:.2f}")
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.log(f"SELL CREATE, {self.data.close[0]:.2f}")
                self.order = self.sell()


def _coerce_ema(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce EMA parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'ema',
    'description': 'EMA crossover strategy',
    'strategy_class': EMAStrategy,
    'param_names': ['period'],
    'defaults': {'period': 20},
    'grid_defaults': {'period': list(range(5, 121, 5))},
    'coercer': _coerce_ema,
    'multi_symbol': False,
}
