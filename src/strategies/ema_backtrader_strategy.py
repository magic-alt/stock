"""
EMA均线交叉策略 (Backtrader版本)
当价格向上突破EMA均线时买入，向下跌破时卖出

V3.0.0 优化:
- 增加 EMA 斜率判断，过滤震荡市场的假突破
- 只在 EMA 上行趋势中做多
"""
import backtrader as bt
from typing import Dict, Any


class EMAStrategy(bt.Strategy):
    """
    EMA crossover strategy with slope filter.
    
    Buy when price crosses above EMA AND EMA is trending up.
    Sell when price crosses below EMA.
    
    V3.0.0 优化:
    - slope_lookback: EMA 斜率计算周期
    - 过滤震荡市场的假突破信号
    """
    params = (
        ("period", 20),
        ("slope_lookback", 5),    # V3.0: EMA 斜率计算周期
        ("printlog", False),
    )

    def __init__(self):
        # Check if we have enough data for the indicator
        data_len = len(self.data)
        min_bars = self.params.period + self.params.slope_lookback
        if data_len < min_bars:
            raise ValueError(
                f"EMA period ({self.params.period}) + slope_lookback ({self.params.slope_lookback}) "
                f"requires at least {min_bars} bars of data, but only {data_len} bars available. "
                f"Please use shorter periods or longer date range."
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

        # V3.0: EMA 斜率判断
        lb = self.params.slope_lookback
        if len(self.ema) > lb:
            slope = self.ema[0] - self.ema[-lb]
            trending_up = slope > 0
        else:
            trending_up = False

        if not self.position:
            # V3.0: 只在 EMA 上行趋势中买入
            if self.crossover > 0 and trending_up:
                self.log(f"BUY CREATE (EMA trending up), {self.data.close[0]:.2f}")
                self.order = self.buy()
        else:
            if self.crossover < 0:
                self.log(f"SELL CREATE, {self.data.close[0]:.2f}")
                self.order = self.close()


def _coerce_ema(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce EMA parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    if "slope_lookback" in out:
        out["slope_lookback"] = int(out["slope_lookback"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'ema',
    'description': 'EMA crossover strategy with slope filter',
    'strategy_class': EMAStrategy,
    'param_names': ['period', 'slope_lookback'],
    'defaults': {'period': 20, 'slope_lookback': 5},
    'grid_defaults': {
        'period': list(range(10, 61, 10)),
        'slope_lookback': [3, 5, 8],
    },
    'coercer': _coerce_ema,
    'multi_symbol': False,
}
