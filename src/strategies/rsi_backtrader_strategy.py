"""
RSI超买超卖策略 (Backtrader版本)
当RSI低于下限时买入，高于上限时卖出

V3.1.0 优化:
- 增加趋势过滤 (SMA200)，只在牛市中做反转
- 增加 ATR 止损保护
- 动态仓位管理
- 修复 sell() 为 close()
"""
import backtrader as bt
from typing import Dict, Any


class RSIStrategy(bt.Strategy):
    """
    RSI threshold strategy with trend filter and risk management.
    
    V3.1.0 优化:
    - 趋势过滤: 只在价格高于长期均线时入场
    - ATR 止损保护
    - 动态仓位管理
    """
    params = (
        ("period", 14),
        ("upper", 70.0),
        ("lower", 30.0),
        # V3.1 新增参数
        ("use_trend_filter", True),
        ("trend_ma", 50),           # 趋势均线 (使用50更灵活)
        ("atr_period", 14),
        ("stop_mult", 2.0),
        ("risk_pct", 0.02),
        ("printlog", False),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI_Safe(
            self.data.close,
            period=self.params.period,
        )
        # V3.1: 趋势过滤均线
        if self.params.use_trend_filter:
            self.trend_ma = bt.indicators.SMA(
                self.data.close, period=self.params.trend_ma
            )
        # V3.1: ATR 止损
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        
        self.order = None
        self.entry_price = None
        self.stop_price = None

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
                self.entry_price = order.executed.price
                self.stop_price = self.entry_price - self.atr[0] * self.params.stop_mult
                self.log(
                    f"BUY EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Stop: {self.stop_price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
            elif order.issell():
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
                self.entry_price = None
                self.stop_price = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f"TRADE PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}")

    def _calc_size(self):
        """V3.1: ATR 动态仓位"""
        if self.atr[0] <= 0:
            return None
        risk = self.broker.getvalue() * self.params.risk_pct
        risk_per_share = self.atr[0] * self.params.stop_mult
        size = int(risk / risk_per_share)
        return max(100, (size // 100) * 100)

    def next(self):
        if self.order:
            return

        # V3.1: 止损检查
        if self.position and self.stop_price:
            if self.data.close[0] < self.stop_price:
                self.log(f"STOP LOSS at {self.data.close[0]:.2f} < {self.stop_price:.2f}")
                self.order = self.close()
                return

        rsi_val = self.rsi[0]

        if not self.position:
            # V3.1: 趋势过滤
            trend_ok = True
            if self.params.use_trend_filter:
                trend_ok = self.data.close[0] > self.trend_ma[0]
            
            if rsi_val < self.params.lower and trend_ok:
                size = self._calc_size()
                self.log(f"BUY CREATE (RSI oversold + uptrend), RSI={rsi_val:.2f}, {self.data.close[0]:.2f}")
                self.order = self.buy(size=size)
        else:
            if rsi_val > self.params.upper:
                # V3.1: Use close() instead of sell() to avoid accidental short position
                self.log(f"CLOSE POSITION (RSI overbought), RSI={rsi_val:.2f}, {self.data.close[0]:.2f}")
                self.order = self.close()


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
        self.rsi = bt.indicators.RSI_Safe(
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
        self.rsi = bt.indicators.RSI_Safe(
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
