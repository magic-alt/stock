"""
Z-Score均值回归策略 (Backtrader版本)
当价格的Z-Score低于入场阈值时买入，高于出场阈值时卖出
"""
import backtrader as bt
from typing import Dict, Any


class ZScoreStrategy(bt.Strategy):
    """
    Rolling-mean z-score mean reversion strategy.
    Buy when z-score drops below z_entry, sell when it rises above z_exit.
    """
    params = (
        ("period", 20),
        ("z_entry", -2.0),
        ("z_exit", -0.5),
        ("printlog", False),
    )

    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.period
        )
        self.std = bt.indicators.StandardDeviation(
            self.data.close, period=self.params.period
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

        close = self.data.close[0]
        mean = self.sma[0]
        std = self.std[0]
        
        if std < 1e-9:
            return
        
        z_score = (close - mean) / std

        if not self.position:
            if z_score < self.params.z_entry:
                self.log(f"BUY CREATE (z-score={z_score:.2f} < {self.params.z_entry:.2f}), {close:.2f}")
                self.order = self.buy()
        else:
            if z_score > self.params.z_exit:
                self.log(f"SELL CREATE (z-score={z_score:.2f} > {self.params.z_exit:.2f}), {close:.2f}")
                self.order = self.sell()


def _coerce_zscore(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Z-Score parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    if "z_entry" in out:
        out["z_entry"] = float(out["z_entry"])
    if "z_exit" in out:
        out["z_exit"] = float(out["z_exit"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'zscore',
    'description': 'Rolling-mean z-score mean reversion',
    'strategy_class': ZScoreStrategy,
    'param_names': ['period', 'z_entry', 'z_exit'],
    'defaults': {'period': 20, 'z_entry': -2.0, 'z_exit': -0.5},
    'grid_defaults': {
        'period': [12, 16, 20, 24],
        'z_entry': [-1.8, -2.0, -2.2],
        'z_exit': [-0.7, -0.5]
    },
    'coercer': _coerce_zscore,
    'multi_symbol': False,
}
