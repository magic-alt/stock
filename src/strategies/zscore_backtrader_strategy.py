"""
Z-Score均值回归策略 (Backtrader版本)
当价格的Z-Score低于入场阈值时买入，高于出场阈值时卖出

V3.1.0 优化:
- 增加长期趋势过滤 (SMA200)，只在牛市中做均值回归
- 增加 ATR 止损，防止趋势市中的大幅亏损
- 增加 RSI 确认，过滤假信号
- 增加 ATR 动态仓位管理
"""
import backtrader as bt
from typing import Dict, Any


class ZScoreStrategy(bt.Strategy):
    """
    Rolling-mean z-score mean reversion strategy with risk management.
    
    V3.1.0 优化:
    - 只在价格高于长期均线时入场 (趋势过滤)
    - ATR 止损保护
    - RSI 超卖确认
    - 动态仓位管理
    """
    params = (
        ("period", 20),
        ("z_entry", -2.0),
        ("z_exit", -0.5),
        # V3.1 新增参数
        ("trend_ma", 200),         # 长期趋势均线
        ("use_trend_filter", True), # 是否启用趋势过滤
        ("atr_period", 14),        # ATR 周期
        ("stop_mult", 2.5),        # 止损乘数 (均值回归策略用更宽的止损)
        ("risk_pct", 0.015),       # 单笔风险 (1.5%)
        ("use_rsi_confirm", True), # 是否使用RSI确认
        ("rsi_period", 14),        # RSI 周期
        ("rsi_oversold", 35),      # RSI 超卖阈值
        ("printlog", False),
    )

    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.period
        )
        self.std = bt.indicators.StandardDeviation(
            self.data.close, period=self.params.period
        )
        
        # V3.1: 趋势过滤均线
        if self.params.use_trend_filter:
            self.trend_ma = bt.indicators.SMA(
                self.data.close, period=self.params.trend_ma
            )
        
        # V3.1: ATR 止损
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        
        # V3.1: RSI 确认
        if self.params.use_rsi_confirm:
            self.rsi = bt.indicators.RSI_Safe(
                self.data.close, period=self.params.rsi_period
            )
        
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

        close = self.data.close[0]
        mean = self.sma[0]
        std = self.std[0]
        
        if std < 1e-9:
            return
        
        z_score = (close - mean) / std

        if not self.position:
            # V3.1: 趋势过滤 - 只在牛市中做均值回归
            if self.params.use_trend_filter:
                if close < self.trend_ma[0]:
                    return  # 熊市不做均值回归
            
            # V3.1: RSI 确认
            rsi_ok = True
            if self.params.use_rsi_confirm:
                rsi_ok = self.rsi[0] < self.params.rsi_oversold
            
            if z_score < self.params.z_entry and rsi_ok:
                size = self._calc_size()
                self.log(f"BUY CREATE (z={z_score:.2f}, RSI={self.rsi[0] if self.params.use_rsi_confirm else 'N/A'}), {close:.2f}")
                self.order = self.buy(size=size)
        else:
            if z_score > self.params.z_exit:
                self.log(f"CLOSE (z={z_score:.2f} > {self.params.z_exit:.2f}), {close:.2f}")
                self.order = self.close()


def _coerce_zscore(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce Z-Score parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    if "z_entry" in out:
        out["z_entry"] = float(out["z_entry"])
    if "z_exit" in out:
        out["z_exit"] = float(out["z_exit"])
    if "trend_ma" in out:
        out["trend_ma"] = int(out["trend_ma"])
    if "atr_period" in out:
        out["atr_period"] = int(out["atr_period"])
    if "stop_mult" in out:
        out["stop_mult"] = float(out["stop_mult"])
    if "risk_pct" in out:
        out["risk_pct"] = float(out["risk_pct"])
    if "rsi_period" in out:
        out["rsi_period"] = int(out["rsi_period"])
    if "rsi_oversold" in out:
        out["rsi_oversold"] = float(out["rsi_oversold"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'zscore',
    'description': 'Z-Score mean reversion with trend filter and ATR stop',
    'strategy_class': ZScoreStrategy,
    'param_names': ['period', 'z_entry', 'z_exit'],
    'defaults': {'period': 20, 'z_entry': -2.0, 'z_exit': -0.5},
    'grid_defaults': {
        'period': [12, 16, 20, 24],
        'z_entry': [-1.8, -2.0, -2.2],
        'z_exit': [-0.7, -0.5]
    },
    'coercer': _coerce_zscore,
    'multi_symbol': False,
}
