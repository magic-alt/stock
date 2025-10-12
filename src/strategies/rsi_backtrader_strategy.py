"""
RSI超买超卖策略 (Backtrader版本)
当RSI低于下限时买入，高于上限时卖出
"""
import backtrader as bt
from typing import Dict, Any


class RSIStrategy(bt.Strategy):
    """
    RSI threshold strategy: buy when RSI is oversold, sell when overbought.
    """
    params = (
        ("period", 14),
        ("upper", 70.0),
        ("lower", 30.0),
        ("printlog", False),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.params.period,
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

        rsi_val = self.rsi[0]

        if not self.position:
            if rsi_val < self.params.lower:
                self.log(f"BUY CREATE (RSI oversold), RSI={rsi_val:.2f}, {self.data.close[0]:.2f}")
                self.order = self.buy()
        else:
            if rsi_val > self.params.upper:
                self.log(f"SELL CREATE (RSI overbought), RSI={rsi_val:.2f}, {self.data.close[0]:.2f}")
                self.order = self.sell()


def _coerce_rsi(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce RSI parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    if "upper" in out:
        out["upper"] = float(out["upper"])
    if "lower" in out:
        out["lower"] = float(out["lower"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'rsi',
    'description': 'RSI threshold strategy',
    'strategy_class': RSIStrategy,
    'param_names': ['period', 'upper', 'lower'],
    'defaults': {'period': 14, 'upper': 70.0, 'lower': 30.0},
    'grid_defaults': {
        'period': list(range(10, 31, 2)),
        'upper': [65, 70, 75],
        'lower': [25, 30, 35]
    },
    'coercer': _coerce_rsi,
    'multi_symbol': False,
}
