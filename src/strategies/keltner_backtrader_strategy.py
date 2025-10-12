"""
Keltner Channel均值回归策略 (Backtrader版本)
使用EMA中轨和ATR带宽进行均值回归交易
"""
import backtrader as bt
from typing import Dict, Any


class KeltnerStrategy(bt.Strategy):
    """
    Keltner Channel mean reversion (EMA mid + ATR bands).
    
    Entry modes:
    - 'pierce': Enter when price pierces lower band
    - 'close_below': Enter when close is below lower band by below_pct%
    
    Exit modes:
    - 'mid': Exit at middle band (EMA)
    - 'upper': Exit at upper band
    """
    params = (
        ("ema_period", 20),
        ("atr_period", 14),
        ("kc_mult", 2.0),
        ("entry_mode", "pierce"),
        ("below_pct", 0.0),
        ("exit_mode", "mid"),
        ("printlog", False),
    )

    def __init__(self):
        self.ema = bt.indicators.ExponentialMovingAverage(
            self.data.close, period=self.params.ema_period
        )
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
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
        mid = self.ema[0]
        atr_val = self.atr[0]
        
        lower = mid - self.params.kc_mult * atr_val
        upper = mid + self.params.kc_mult * atr_val

        if not self.position:
            # Entry logic
            if self.params.entry_mode == "pierce":
                if close < lower:
                    self.log(f"BUY CREATE (pierce KC lower), {close:.2f} < {lower:.2f}")
                    self.order = self.buy()
            elif self.params.entry_mode == "close_below":
                threshold = lower * (1.0 - self.params.below_pct / 100.0)
                if close < threshold:
                    self.log(f"BUY CREATE (close_below KC), {close:.2f} < {threshold:.2f}")
                    self.order = self.buy()
        else:
            # Exit logic
            if self.params.exit_mode == "mid":
                if close >= mid:
                    self.log(f"SELL CREATE (reached KC mid), {close:.2f} >= {mid:.2f}")
                    self.order = self.sell()
            elif self.params.exit_mode == "upper":
                if close >= upper:
                    self.log(f"SELL CREATE (reached KC upper), {close:.2f} >= {upper:.2f}")
                    self.order = self.sell()


def _coerce_keltner(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Keltner parameters to correct types."""
    out = params.copy()
    if "ema_period" in out:
        out["ema_period"] = int(out["ema_period"])
    if "atr_period" in out:
        out["atr_period"] = int(out["atr_period"])
    if "kc_mult" in out:
        out["kc_mult"] = float(out["kc_mult"])
    if "below_pct" in out:
        out["below_pct"] = float(out["below_pct"])
    if "entry_mode" in out:
        out["entry_mode"] = str(out["entry_mode"])
    if "exit_mode" in out:
        out["exit_mode"] = str(out["exit_mode"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'keltner',
    'description': 'Keltner Channel mean reversion (EMA mid + ATR bands)',
    'strategy_class': KeltnerStrategy,
    'param_names': ['ema_period', 'atr_period', 'kc_mult', 'entry_mode', 'below_pct', 'exit_mode'],
    'defaults': {
        'ema_period': 20,
        'atr_period': 14,
        'kc_mult': 2.0,
        'entry_mode': 'pierce',
        'below_pct': 0.0,
        'exit_mode': 'mid'
    },
    'grid_defaults': {
        'ema_period': list(range(10, 25, 2)),
        'atr_period': [14],
        'kc_mult': [1.8, 2.0, 2.2],
        'entry_mode': ['pierce', 'close_below'],
        'exit_mode': ['mid']
    },
    'coercer': _coerce_keltner,
    'multi_symbol': False,
}
