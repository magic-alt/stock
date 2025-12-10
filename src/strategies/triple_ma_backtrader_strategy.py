"""
Triple Moving Average趋势策略 (Backtrader版本)
当快速均线>中速均线>慢速均线时买入（多头排列），反之卖出

V3.1.0 优化:
- 增加 ATR 止损，保护利润
- 增加动态仓位管理
- 修复 sell() 为 close() 防止意外做空
"""
import backtrader as bt
from typing import Dict, Any


class TripleMAStrategy(bt.Strategy):
    """
    Triple moving average trend with ATR stop loss.
    
    V3.1.0 优化:
    - ATR 止损保护
    - 动态仓位管理
    
    Buy when fast MA > mid MA > slow MA (bullish alignment).
    Exit when alignment breaks OR stop loss is hit.
    """
    params = (
        ("fast", 5),
        ("mid", 20),
        ("slow", 60),
        # V3.1 新增参数
        ("atr_period", 14),
        ("stop_mult", 2.0),
        ("risk_pct", 0.02),
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

        fast = self.ma_fast[0]
        mid = self.ma_mid[0]
        slow = self.ma_slow[0]

        bullish_alignment = (fast > mid) and (mid > slow)

        if not self.position:
            if bullish_alignment:
                size = self._calc_size()
                self.log(
                    f"BUY CREATE (triple MA bullish), "
                    f"fast={fast:.2f} > mid={mid:.2f} > slow={slow:.2f}"
                )
                self.order = self.buy(size=size)
        else:
            if not bullish_alignment:
                # V3.1: Use close() instead of sell() to avoid accidental short position
                self.log(
                    f"CLOSE POSITION (triple MA broken), "
                    f"fast={fast:.2f}, mid={mid:.2f}, slow={slow:.2f}"
                )
                self.order = self.close()


def _coerce_tma(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Triple MA parameters to correct types."""
    out = params.copy()
    for k in ("fast", "mid", "slow"):
        if k in out:
            out[k] = int(out[k])
    if "atr_period" in out:
        out["atr_period"] = int(out["atr_period"])
    if "stop_mult" in out:
        out["stop_mult"] = float(out["stop_mult"])
    if "risk_pct" in out:
        out["risk_pct"] = float(out["risk_pct"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'triple_ma',
    'description': 'Triple MA trend strategy with ATR stop loss',
    'strategy_class': TripleMAStrategy,
    'param_names': ['fast', 'mid', 'slow', 'atr_period', 'stop_mult'],
    'defaults': {'fast': 5, 'mid': 20, 'slow': 60, 'atr_period': 14, 'stop_mult': 2.0},
    'grid_defaults': {
        'fast': [5, 8],
        'mid': [18, 20, 22],
        'slow': [55, 60, 65]
    },
    'coercer': _coerce_tma,
    'multi_symbol': False,
}
