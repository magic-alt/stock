"""
Trend Pullback Enhanced Strategy (趋势回调增强版)

V3.0.0 新增策略 - 机构级综合策略

逻辑：
1. 趋势过滤：价格 > EMA200 且 EMA200 向上
2. 回调入场：价格回落至动态支撑区 (EMA20-ATR 通道)
3. 动态风控：基于 ATR 的波动率定仓 (Volatility Sizing)
4. 移动止损：吊灯止损 (Chandelier Exit) 锁定利润

核心改进：
- 内置基于账户风险百分比的仓位计算
- 结合长期趋势(EMA200)与短期动能(MACD)
- 严格的 ATR 止损与移动止损
"""
import backtrader as bt
from typing import Dict, Any


class TrendPullbackEnhanced(bt.Strategy):
    """
    机构级趋势回调策略
    
    核心特性：
    - 波动率定仓 (Volatility Sizing): 根据 ATR 动态调整仓位
    - 双重趋势确认: Close > EMA200 且 EMA200 斜率向上
    - 吊灯止损 (Chandelier Exit): 跟踪最高价，回撤 N*ATR 离场
    - RSI 避免追高: 超买时不入场
    
    适用场景：
    - 趋势明确的牛市环境
    - 中长期持仓 (日线/周线)
    - 风险可控的稳健增长
    """
    params = (
        # --- 趋势参数 ---
        ("ema_trend", 200),      # 长期趋势线
        ("ema_pullback", 20),    # 回调参考线
        
        # --- 动能参数 (MACD) ---
        ("macd_fast", 12),
        ("macd_slow", 26),
        ("macd_signal", 9),

        # --- 过滤器 ---
        ("rsi_period", 14),
        ("rsi_entry_max", 70),   # RSI高于此值不追高
        
        # --- 风险管理 (核心) ---
        ("atr_period", 14),
        ("risk_pct", 0.02),      # 单笔交易风险 (账户权益的 2%)
        ("sl_atr_mult", 2.0),    # 初始止损 = Entry - 2.0 * ATR
        ("trail_atr_mult", 2.5), # 移动止损 = High - 2.5 * ATR
        
        # --- 其他 ---
        ("printlog", False),
        ("min_warmup", 200),     # 最小预热期
    )

    def __init__(self):
        # 1. 核心指标 (plot=False 避免图表混乱)
        self.ema_long = bt.indicators.EMA(
            self.data.close, period=self.params.ema_trend, plot=False
        )
        self.ema_short = bt.indicators.EMA(
            self.data.close, period=self.params.ema_pullback, plot=False
        )
        
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.macd_fast,
            period_me2=self.params.macd_slow,
            period_signal=self.params.macd_signal,
            plot=False
        )
        self.atr = bt.indicators.ATR(
            self.data, period=self.params.atr_period, plot=False
        )
        self.rsi = bt.indicators.RSI(
            self.data.close, period=self.params.rsi_period, plot=False
        )

        # 2. 交易状态管理
        self.order = None
        self.stop_price = None       # 动态止损价
        self.highest_high = None     # 持仓期间最高价
        self.entry_atr = None        # 入场时的ATR值（用于计算固定R）

    def log(self, txt: str, dt=None):
        """增强版日志记录"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"[{dt.isoformat()}] {txt}")

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED | Price: {order.executed.price:.2f} | "
                    f"Size: {order.executed.size} | Comm: {order.executed.comm:.2f}"
                )
                # 设置初始止损
                if self.entry_atr is not None:
                    self.stop_price = order.executed.price - (
                        self.entry_atr * self.params.sl_atr_mult
                    )
                self.highest_high = order.executed.price
            elif order.issell():
                self.log(
                    f"SELL EXECUTED | Price: {order.executed.price:.2f} | "
                    f"PnL: {order.executed.pnl:.2f}"
                )
                self.stop_price = None
                self.highest_high = None
                self.entry_atr = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"Order Failed: {order.getstatusname()}")

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(
            f"TRADE CLOSED | Gross PnL: {trade.pnl:.2f} | Net PnL: {trade.pnlcomm:.2f}"
        )

    def _calculate_position_size(self, price: float, atr: float) -> int:
        """
        根据风险百分比计算仓位 (波动率定仓)
        
        公式: Size = (Account_Value * Risk_Pct) / (ATR * SL_Multiplier)
        
        这是机构交易的标准做法：
        - 市场波动大（ATR高）→ 仓位自动减少
        - 市场波动小（ATR低）→ 仓位自动增加
        - 确保单笔亏损不超过账户权益的 N%
        
        Args:
            price: 当前价格
            atr: 当前 ATR 值
            
        Returns:
            计算后的仓位大小 (A股向下取整到100股)
        """
        if atr <= 0:
            return 0
        
        cash = self.broker.getvalue()
        risk_amount = cash * self.params.risk_pct
        risk_per_share = atr * self.params.sl_atr_mult
        
        size = risk_amount / risk_per_share
        
        # A股/港股通常需要向下取整到 100 股
        size = int(size / 100) * 100
        return max(100, size)

    def next(self):
        # 0. 基础检查
        if self.order:  # 等待订单完成
            return
        if len(self) < self.params.min_warmup:
            return

        close = self.data.close[0]
        atr = self.atr[0]

        # ---------------------------
        # 1. 持仓管理 (Exit / Trail Logic)
        # ---------------------------
        if self.position:
            # 更新最高价
            if close > self.highest_high:
                self.highest_high = close
            
            # 吊灯止损计算 (Chandelier Exit)
            # 止损线上移：最高价回撤 N * ATR
            trail_stop = self.highest_high - (atr * self.params.trail_atr_mult)
            
            # 确保止损线只升不降 (对于多头)
            if self.stop_price is None:
                self.stop_price = trail_stop
            else:
                self.stop_price = max(self.stop_price, trail_stop)

            # 触发止损/止盈
            if close < self.stop_price:
                self.log(
                    f"EXIT TRIGGER (Stop/Trail) | "
                    f"Close: {close:.2f} < Stop: {self.stop_price:.2f}"
                )
                self.order = self.close()
            
            return

        # ---------------------------
        # 2. 入场逻辑 (Entry Logic)
        # ---------------------------
        
        # A. 趋势过滤 (Regime Filter)
        # 价格在 EMA200 之上，且 EMA200 本身在上涨 (利用当前和前一值比较)
        ema_long_up = self.ema_long[0] > self.ema_long[-1]
        trend_ok = (close > self.ema_long[0]) and ema_long_up

        if not trend_ok:
            return

        # B. 回调/价值区 (Value Area)
        # 价格并未远离 EMA20 太多 (避免追高)
        # 定义：价格在 EMA20 * 1.05 以内，或者 RSI < 70
        not_overextended = (
            (close < self.ema_short[0] * 1.05) and 
            (self.rsi[0] < self.params.rsi_entry_max)
        )

        # C. 触发信号 (Trigger)
        # MACD 柱状图翻红 (动能由负转正) 或 MACD 金叉
        macd_turning_up = (
            (self.macd.macd[0] > self.macd.signal[0]) and 
            (self.macd.macd[-1] <= self.macd.signal[-1])
        )

        # 综合判断
        if not_overextended and macd_turning_up:
            # 记录入场时的 ATR 用于风控
            self.entry_atr = atr
            
            # 动态计算仓位
            size = self._calculate_position_size(close, atr)
            
            if size > 0:
                self.log(
                    f"BUY SIGNAL | Price: {close:.2f} | "
                    f"ATR: {atr:.2f} | Calc Size: {size}"
                )
                self.order = self.buy(size=size)


def _coerce_trend_pullback(params: Dict[str, Any]) -> Dict[str, Any]:
    """参数类型强制转换"""
    out = params.copy()
    ints = [
        'ema_trend', 'ema_pullback', 'macd_fast', 'macd_slow', 'macd_signal', 
        'rsi_period', 'rsi_entry_max', 'atr_period', 'min_warmup'
    ]
    floats = ['risk_pct', 'sl_atr_mult', 'trail_atr_mult']
    
    for k in ints:
        if k in out:
            out[k] = int(out[k])
    for k in floats:
        if k in out:
            out[k] = float(out[k])
    return out


# 策略配置字典 (直接适配系统)
STRATEGY_CONFIG = {
    'name': 'trend_pullback_enhanced',
    'description': 'Trend following with pullback entry and volatility sizing',
    'strategy_class': TrendPullbackEnhanced,
    'param_names': [
        'ema_trend', 'ema_pullback', 
        'macd_fast', 'macd_slow', 'macd_signal',
        'risk_pct', 'sl_atr_mult', 'trail_atr_mult'
    ],
    'defaults': {
        'ema_trend': 200,
        'ema_pullback': 20,
        'macd_fast': 12, 
        'macd_slow': 26, 
        'macd_signal': 9,
        'risk_pct': 0.02,
        'sl_atr_mult': 2.0,
        'trail_atr_mult': 2.5,
    },
    'grid_defaults': {
        'ema_trend': [150, 200],
        'ema_pullback': [15, 20, 25],
        'risk_pct': [0.01, 0.02],
        'sl_atr_mult': [1.5, 2.0, 2.5],
    },
    'coercer': _coerce_trend_pullback,
    'multi_symbol': False,
}
