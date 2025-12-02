"""
Donchian Channel趋势突破策略 (Backtrader版本)
当价格突破N日最高价时买入，跌破M日最低价时卖出

V3.0.0 优化:
- 增加 ATR 波动扩张确认
- 只在波动放大时入场，过滤低波动假突破
"""
import backtrader as bt
from typing import Dict, Any


class DonchianStrategy(bt.Strategy):
    """
    Donchian channel breakout with ATR volatility confirmation.
    
    V3.0.0 优化:
    - atr_period: ATR 计算周期
    - vol_lookback: 波动率比较周期
    - 只在 ATR > 过去 vol_lookback 周期平均时入场
    - 过滤低波动市场的假突破
    """
    params = (
        ("upper", 20),           # Period for upper channel (highest high)
        ("lower", 10),           # Period for lower channel (lowest low)
        ("atr_period", 14),      # V3.0: ATR 周期
        ("vol_lookback", 20),    # V3.0: 波动率比较周期
        ("printlog", False),
    )

    def __init__(self):
        self.highest = bt.indicators.Highest(
            self.data.high, period=self.params.upper
        )
        self.lowest = bt.indicators.Lowest(
            self.data.low, period=self.params.lower
        )
        # V3.0: ATR 和波动率均值
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        self.atr_ma = bt.indicators.SMA(self.atr, period=self.params.vol_lookback)
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
        # 使用前一天的通道值来判断今天的突破
        # 这是正确的Donchian逻辑：今天收盘价突破昨天的N日高点
        high_val = self.highest[-1] if len(self) > 1 else self.highest[0]
        low_val = self.lowest[-1] if len(self) > 1 else self.lowest[0]
        
        # V3.0: 波动扩张确认
        vol_expanding = self.atr[0] > self.atr_ma[0]

        if not self.position:
            # V3.0: 只在波动扩张时买入
            if close > high_val and vol_expanding:
                self.log(f"BUY CREATE (Donchian breakout + ATR expanding), {close:.2f} > {high_val:.2f}")
                self.order = self.buy()
        else:
            # Sell on breakdown below lower channel (close < yesterday's M-period low)
            if close < low_val:
                self.log(f"SELL CREATE (Donchian breakdown), {close:.2f} < {low_val:.2f}")
                self.order = self.close()


def _coerce_donchian(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Donchian parameters to correct types."""
    out = params.copy()
    if "upper" in out:
        out["upper"] = int(out["upper"])
    if "lower" in out:
        out["lower"] = int(out["lower"])
    if "atr_period" in out:
        out["atr_period"] = int(out["atr_period"])
    if "vol_lookback" in out:
        out["vol_lookback"] = int(out["vol_lookback"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'donchian',
    'description': 'Donchian channel breakout with ATR volatility confirmation',
    'strategy_class': DonchianStrategy,
    'param_names': ['upper', 'lower', 'atr_period', 'vol_lookback'],
    'defaults': {'upper': 20, 'lower': 10, 'atr_period': 14, 'vol_lookback': 20},
    'grid_defaults': {
        'upper': [18, 20, 22, 24],
        'lower': [8, 10, 12],
        'vol_lookback': [15, 20, 25],
    },
    'coercer': _coerce_donchian,
    'multi_symbol': False,
}
