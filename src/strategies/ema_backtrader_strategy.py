"""
EMA均线交叉策略 (Backtrader版本)
当价格向上突破EMA均线时买入，向下跌破时卖出

V3.1.0 优化:
- 增加 ATR 止损机制，保护利润，控制风险
- 增加 ATR 动态仓位计算 (风险百分比仓位管理)
- 增加冷却期，防止频繁交易

V3.0.0 优化:
- 增加 EMA 斜率判断，过滤震荡市场的假突破
- 只在 EMA 上行趋势中做多
"""
import backtrader as bt
from typing import Dict, Any


class EMAStrategy(bt.Strategy):
    """
    EMA crossover strategy with slope filter and risk management.
    
    Buy when price crosses above EMA AND EMA is trending up.
    Exit: when price crosses below EMA OR hits ATR stop loss.
    
    V3.1.0 新增:
    - ATR 止损: 防止大幅回撤
    - 动态仓位: 基于 ATR 风险定仓
    - 冷却期: 平仓后等待N根K线
    
    V3.0.0 优化:
    - slope_lookback: EMA 斜率计算周期
    - 过滤震荡市场的假突破信号
    """
    params = (
        ("period", 20),
        ("slope_lookback", 5),     # V3.0: EMA 斜率计算周期
        # V3.1 新增风控参数
        ("atr_period", 14),        # ATR 周期
        ("stop_mult", 2.0),        # 止损乘数 (ATR倍数)
        ("risk_pct", 0.02),        # 单笔风险比例 (2%)
        ("cooldown", 3),           # 冷却期 (K线数)
        ("use_atr_sizing", True),  # 是否使用ATR动态仓位
        ("printlog", False),
    )

    def __init__(self):
        # Backtrader strategy __init__ runs before bars are consumed, so len(self.data)
        # is still 0 here. Use the underlying DataFrame length when available.
        source_df = getattr(self.data, "_dataname", None)
        data_len = len(source_df) if hasattr(source_df, "__len__") else 0
        min_bars = max(self.params.period + self.params.slope_lookback, self.params.atr_period)
        if data_len and data_len < min_bars:
            raise ValueError(
                f"EMA strategy requires at least {min_bars} bars of data, "
                f"but only {data_len} bars available. "
                f"Please use shorter periods or longer date range."
            )
        
        self.ema = bt.indicators.ExponentialMovingAverage(
            self.data.close, period=self.params.period
        )
        self.crossover = bt.indicators.CrossOver(self.data.close, self.ema)
        
        # V3.1: ATR 用于止损和仓位计算
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        
        self.order = None
        self.entry_price = None
        self.stop_price = None
        self.last_exit_bar = -1000000  # 冷却期追踪

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
                # V3.1: 设置止损价
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
                self.last_exit_bar = len(self)  # 记录出场K线
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
        """V3.1: ATR 动态仓位计算"""
        if not self.params.use_atr_sizing or self.atr[0] <= 0:
            return None  # 使用默认仓位
        
        # 风险金额 = 账户价值 * 风险比例
        risk_amount = self.broker.getvalue() * self.params.risk_pct
        # 每股风险 = ATR * 止损乘数
        risk_per_share = self.atr[0] * self.params.stop_mult
        # 仓位 = 风险金额 / 每股风险
        size = int(risk_amount / risk_per_share)
        # A股整手 (100股)
        return max(100, (size // 100) * 100)

    def _in_cooldown(self):
        """V3.1: 检查是否在冷却期"""
        return (len(self) - self.last_exit_bar) < self.params.cooldown

    def next(self):
        if self.order:
            return

        # V3.1: 止损检查 (优先于其他逻辑)
        if self.position and self.stop_price:
            if self.data.close[0] < self.stop_price:
                self.log(f"STOP LOSS TRIGGERED at {self.data.close[0]:.2f} < {self.stop_price:.2f}")
                self.order = self.close()
                return

        # V3.0: EMA 斜率判断
        lb = self.params.slope_lookback
        if len(self.ema) > lb:
            slope = self.ema[0] - self.ema[-lb]
            trending_up = slope > 0
        else:
            trending_up = False

        if not self.position:
            # V3.1: 冷却期检查
            if self._in_cooldown():
                return
            
            # V3.0: 只在 EMA 上行趋势中买入
            if self.crossover > 0 and trending_up:
                size = self._calc_size()
                self.log(f"BUY CREATE (EMA trending up), {self.data.close[0]:.2f}, size={size}")
                self.order = self.buy(size=size)
        else:
            if self.crossover < 0:
                self.log(f"CLOSE POSITION (EMA cross down), {self.data.close[0]:.2f}")
                self.order = self.close()


def _coerce_ema(params: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce EMA parameters to correct types."""
    out = params.copy()
    if "period" in out:
        out["period"] = int(out["period"])
    if "slope_lookback" in out:
        out["slope_lookback"] = int(out["slope_lookback"])
    if "atr_period" in out:
        out["atr_period"] = int(out["atr_period"])
    if "stop_mult" in out:
        out["stop_mult"] = float(out["stop_mult"])
    if "risk_pct" in out:
        out["risk_pct"] = float(out["risk_pct"])
    if "cooldown" in out:
        out["cooldown"] = int(out["cooldown"])
    if "use_atr_sizing" in out:
        out["use_atr_sizing"] = bool(out["use_atr_sizing"])
    return out


# 策略配置
STRATEGY_CONFIG = {
    'name': 'ema',
    'description': 'EMA crossover strategy with ATR stop loss and dynamic position sizing',
    'strategy_class': EMAStrategy,
    'param_names': ['period', 'slope_lookback', 'atr_period', 'stop_mult', 'risk_pct'],
    'defaults': {'period': 20, 'slope_lookback': 5, 'atr_period': 14, 'stop_mult': 2.0, 'risk_pct': 0.02},
    'grid_defaults': {
        'period': list(range(10, 61, 10)),
        'slope_lookback': [3, 5, 8],
    },
    'coercer': _coerce_ema,
    'multi_symbol': False,
}
