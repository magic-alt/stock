"""
Bollinger Bands均值回归策略 (Backtrader版本)
当价格触及下轨时买入，触及上轨或中轨时卖出
"""
import backtrader as bt
from typing import Dict, Any


class BollingerStrategy(bt.Strategy):
    """
    Bollinger band mean reversion with flexible entry/exit modes.
    
    Entry modes:
    - 'pierce': Enter when price pierces lower band
    - 'close_below': Enter when close is below lower band by below_pct%
    
    Exit modes:
    - 'mid': Exit at middle band
    - 'upper': Exit at upper band
    """
    params = (
        ("period", 20),
        ("devfactor", 2.0),
        ("entry_mode", "pierce"),
        ("below_pct", 0.0),
        ("exit_mode", "mid"),
        ("printlog", False),
    )

    def __init__(self):
        self.bb = bt.indicators.BollingerBands(
            self.data.close,
            period=self.params.period,
            devfactor=self.params.devfactor,
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
        bot = self.bb.bot[0]
        mid = self.bb.mid[0]
        top = self.bb.top[0]

        if not self.position:
            # Entry logic
            if self.params.entry_mode == "pierce":
                if close < bot:
                    self.log(f"BUY CREATE (pierce lower), {close:.2f} < {bot:.2f}")
                    self.order = self.buy()
            elif self.params.entry_mode == "close_below":
                threshold = bot * (1.0 - self.params.below_pct / 100.0)
                if close < threshold:
                    self.log(f"BUY CREATE (close_below), {close:.2f} < {threshold:.2f}")
                    self.order = self.buy()
        else:
            # Exit logic
            if self.params.exit_mode == "mid":
                if close >= mid:
                    self.log(f"SELL CREATE (reached mid), {close:.2f} >= {mid:.2f}")
                    self.order = self.sell()
            elif self.params.exit_mode == "upper":
                if close >= top:
                    self.log(f"SELL CREATE (reached upper), {close:.2f} >= {top:.2f}")
                    self.order = self.sell()


def _coerce_bb(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Bollinger parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    if "devfactor" in out:
        out["devfactor"] = float(out["devfactor"])
    if "below_pct" in out:
        out["below_pct"] = float(out["below_pct"])
    if "entry_mode" in out:
        out["entry_mode"] = str(out["entry_mode"])
    if "exit_mode" in out:
        out["exit_mode"] = str(out["exit_mode"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'bollinger',
    'description': 'Bollinger band mean reversion with flexible entry/exit modes',
    'strategy_class': BollingerStrategy,
    'param_names': ['period', 'devfactor', 'entry_mode', 'below_pct', 'exit_mode'],
    'defaults': {
        'period': 20,
        'devfactor': 2.0,
        'entry_mode': 'pierce',
        'below_pct': 0.0,
        'exit_mode': 'mid'
    },
    'grid_defaults': {
        'period': list(range(10, 31, 2)),
        'devfactor': [1.5, 2.0, 2.5],
        'entry_mode': ['pierce'],
        'exit_mode': ['mid']
    },
    'coercer': _coerce_bb,
    'multi_symbol': False,
}
