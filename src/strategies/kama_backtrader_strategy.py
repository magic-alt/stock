"""
KAMA Strategy (Backtrader version)
Kaufman Adaptive Moving Average - adapts to market volatility

V3.0.0 优化:
- 增加 SMA(200) 长期趋势过滤
- 只在牛市环境 (Close > SMA200) 做多
"""
import backtrader as bt


class KAMAIndicator(bt.Indicator):
    """
    Kaufman Adaptive Moving Average (KAMA)
    Adjusts smoothing based on market efficiency ratio
    """
    lines = ('kama',)
    params = (
        ('period', 10),
        ('fast_ema', 2),
        ('slow_ema', 30),
    )

    def __init__(self):
        # Efficiency Ratio
        change = abs(self.data.close - self.data.close(-self.p.period))
        volatility = bt.indicators.SumN(
            abs(self.data.close - self.data.close(-1)),
            period=self.p.period
        )
        self.er = change / volatility

        # Smoothing constant
        fast_sc = 2.0 / (self.p.fast_ema + 1)
        slow_sc = 2.0 / (self.p.slow_ema + 1)
        self.sc = (self.er * (fast_sc - slow_sc) + slow_sc) ** 2

    def next(self):
        if len(self) == 1:
            self.lines.kama[0] = self.data.close[0]
        else:
            prev_kama = self.lines.kama[-1]
            self.lines.kama[0] = prev_kama + self.sc[0] * (self.data.close[0] - prev_kama)


class KAMAStrategy(bt.Strategy):
    """
    KAMA crossover strategy with regime filter
    
    V3.0.0 优化:
    - regime_period: 长期趋势 SMA 周期 (默认 200)
    - 只在 Close > SMA(200) 牛市环境做多
    - 避免熊市假反弹信号
    """
    params = (
        ('period', 10),
        ('fast_ema', 2),
        ('slow_ema', 30),
        ('atr_period', 14),
        ('atr_mult', 2.0),
        ('regime_period', 200),  # V3.0: 趋势过滤周期
    )

    def __init__(self):
        self.kama = KAMAIndicator(
            self.data,
            period=self.p.period,
            fast_ema=self.p.fast_ema,
            slow_ema=self.p.slow_ema
        )
        self.crossover = bt.indicators.CrossOver(self.data.close, self.kama)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.sma_regime = bt.indicators.SMA(self.data.close, period=self.p.regime_period)  # V3.0
        self.order = None

    def next(self):
        if self.order:
            return

        # V3.0: 牛市过滤器
        bullish_regime = self.data.close[0] > self.sma_regime[0]

        if not self.position:
            # V3.0: 只在牛市环境做多
            if self.crossover > 0 and bullish_regime:
                size = self._calc_size()
                self.order = self.buy(size=size)
        else:
            if self.crossover < 0:  # Price crosses below KAMA
                self.order = self.close()

    def _calc_size(self):
        """Calculate position size based on ATR"""
        if self.atr[0] == 0:
            return 100  # 最小1手
        risk_amount = self.broker.getcash() * 0.02
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


def _coerce_kama(d: dict) -> dict:
    """Coerce parameters to correct types"""
    return {
        'period': int(d.get('period', 10)),
        'fast_ema': int(d.get('fast_ema', 2)),
        'slow_ema': int(d.get('slow_ema', 30)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
        'regime_period': int(d.get('regime_period', 200)),
    }
