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


class RSIMaFilterStrategy(bt.Strategy):
    """
    RSI + MA Filter strategy
    - Only buy when RSI is oversold AND price is above long-term MA (uptrend)
    - Combines mean reversion with trend following
    """
    params = (
        ("rsi_period", 14),
        ("oversold", 30.0),
        ("ma_period", 200),
        ("printlog", False),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.params.rsi_period,
        )
        self.ma = bt.indicators.SMA(self.data.close, period=self.params.ma_period)
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

        rsi_val = self.rsi[0]
        in_uptrend = self.data.close[0] > self.ma[0]

        if not self.position:
            # Buy only in uptrend when RSI oversold
            if rsi_val < self.params.oversold and in_uptrend:
                self.log(f"BUY CREATE (RSI oversold + uptrend), RSI={rsi_val:.2f}")
                self.order = self.buy()
        else:
            # Exit when trend breaks down or RSI normalizes
            if not in_uptrend or rsi_val > 50:
                self.log(f"SELL CREATE (exit condition), RSI={rsi_val:.2f}")
                self.order = self.sell()


class RSIDivergenceStrategy(bt.Strategy):
    """
    RSI Divergence strategy
    - Bullish divergence: Price makes lower low, RSI makes higher low
    - Bearish divergence: Price makes higher high, RSI makes lower high
    """
    params = (
        ("period", 14),
        ("lookback", 5),
        ("printlog", False),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=self.params.period,
        )
        self.order = None
        self.price_history = []
        self.rsi_history = []

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

        # Keep history
        self.price_history.append(self.data.close[0])
        self.rsi_history.append(self.rsi[0])
        
        # Only keep lookback window
        if len(self.price_history) > self.params.lookback:
            self.price_history.pop(0)
            self.rsi_history.pop(0)

        if len(self.price_history) < self.params.lookback:
            return

        current_price = self.price_history[-1]
        current_rsi = self.rsi_history[-1]
        min_price = min(self.price_history[:-1])
        max_price = max(self.price_history[:-1])
        min_rsi = min(self.rsi_history[:-1])
        max_rsi = max(self.rsi_history[:-1])

        if not self.position:
            # Bullish divergence: price at/near low, RSI higher than previous low
            if current_price <= min_price and current_rsi > min_rsi:
                self.log(f"BUY CREATE (bullish divergence), RSI={current_rsi:.2f}")
                self.order = self.buy()
        else:
            # Bearish divergence: price at/near high, RSI lower than previous high
            if current_price >= max_price and current_rsi < max_rsi:
                self.log(f"SELL CREATE (bearish divergence), RSI={current_rsi:.2f}")
                self.order = self.sell()


def _coerce_rsi(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce RSI parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    if "rsi_period" in out:
        out["rsi_period"] = int(out["rsi_period"])
    if "upper" in out:
        out["upper"] = float(out["upper"])
    if "lower" in out:
        out["lower"] = float(out["lower"])
    if "oversold" in out:
        out["oversold"] = float(out["oversold"])
    if "ma_period" in out:
        out["ma_period"] = int(out["ma_period"])
    if "lookback" in out:
        out["lookback"] = int(out["lookback"])
    return out
