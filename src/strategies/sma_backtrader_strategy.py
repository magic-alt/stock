"""
SMA Cross Strategy (Backtrader version)
Simple Moving Average crossover with ATR-based position sizing
"""
import backtrader as bt


class SMACrossStrategy(bt.Strategy):
    """
    Simple Moving Average crossover strategy
    - Buy when fast SMA crosses above slow SMA
    - Sell when fast SMA crosses below slow SMA
    - Uses ATR for position sizing
    """
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
        ('atr_period', 14),
        ('atr_mult', 2.0),
    )

    def __init__(self):
        self.sma_fast = bt.indicators.SMA(self.data.close, period=self.p.fast_period)
        self.sma_slow = bt.indicators.SMA(self.data.close, period=self.p.slow_period)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.order = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.crossover > 0:  # Golden cross
                size = self._calc_size()
                self.order = self.buy(size=size)
        else:
            if self.crossover < 0:  # Death cross
                self.order = self.sell(size=self.position.size)

    def _calc_size(self):
        """Calculate position size based on ATR"""
        if self.atr[0] == 0:
            return 100  # 最小1手
        risk_amount = self.broker.getcash() * 0.02  # 2% risk per trade
        atr_risk = self.atr[0] * self.p.atr_mult
        if atr_risk == 0:
            return 100
        size = int(risk_amount / atr_risk)
        # 强制100股整数倍（A股规则）
        lots = max(1, size // 100)
        return lots * 100

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None


def _coerce_sma_cross(d: dict) -> dict:
    """Coerce parameters to correct types"""
    return {
        'fast_period': int(d.get('fast_period', 10)),
        'slow_period': int(d.get('slow_period', 30)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
    }
