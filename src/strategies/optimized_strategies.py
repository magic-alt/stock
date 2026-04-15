# -*- coding: utf-8 -*-
"""
Optimized Strategies - 增强版策略集合

针对原策略的量化增强版本，增加了：
- 动态风险管理 (ATR-based position sizing & stops)
- 市场状态过滤 (Regime Filter)
- 多指标确认 (Multi-indicator confirmation)
- 时间过滤 (Time-based filters)

V3.0.0: Initial implementation with 5 optimized strategies.

Strategies:
1. KAMAStrategy_Optimized - KAMA + SMA200 趋势过滤
2. FuturesGrid_ATR_Optimized - ATR 动态网格间距
3. IntradayReversion_Optimized - 时间过滤 + ATR 阈值
4. BollingerRSI_Optimized - RSI 超卖确认
5. DonchianATR_Optimized - ATR 波动率突破确认
"""
from __future__ import annotations

import backtrader as bt
import datetime
from typing import Dict, Any


# =============================================================================
# 1. KAMA 策略优化：增加长期均线趋势过滤 + ATR 动态止损
# =============================================================================

class KAMAIndicator(bt.Indicator):
    """
    Kaufman Adaptive Moving Average (KAMA)
    
    自适应移动平均线，根据市场效率比率调整平滑系数。
    在趋势明显时快速跟随，在震荡时缓慢响应。
    
    Math:
        ER = |Change| / Volatility
        SC = (ER * (fast_sc - slow_sc) + slow_sc)^2
        KAMA = KAMA[-1] + SC * (Close - KAMA[-1])
    """
    lines = ('kama',)
    params = (
        ('period', 10),
        ('fast_ema', 2),
        ('slow_ema', 30),
    )

    def __init__(self):
        # Efficiency Ratio: 方向性变化 / 波动性
        change = abs(self.data.close - self.data.close(-self.p.period))
        volatility = bt.indicators.SumN(
            abs(self.data.close - self.data.close(-1)),
            period=self.p.period
        )
        # 避免除零
        self.er = change / (volatility + 1e-10)

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


class KAMAStrategy_Optimized(bt.Strategy):
    """
    KAMA 优化策略：趋势过滤 + 动态止损
    
    优化点：
    1. 增加 SMA(filter_period) 作为趋势过滤器
       - 牛市（价格 > SMA）：允许 KAMA 金叉做多
       - 熊市（价格 < SMA）：不开新仓或只做空
    2. ATR 动态止损，随波动率调整
    3. 移动止损（Trailing Stop）保护利润
    
    Signal Logic:
        Entry: (Price CrossAbove KAMA) AND (Price > SMA_filter)
        Exit: (Price CrossBelow KAMA) OR (Price < Stop_Loss)
    
    Parameters:
        period: KAMA 效率比率计算周期 (default: 10)
        fast_ema: 快速平滑常数 (default: 2)
        slow_ema: 慢速平滑常数 (default: 30)
        filter_period: 趋势过滤均线周期 (default: 200)
        atr_period: ATR 计算周期 (default: 14)
        atr_stop_mult: ATR 止损倍数 (default: 2.0)
        trail_atr_mult: 移动止损 ATR 倍数 (default: 1.5)
    """
    params = (
        ('period', 10),
        ('fast_ema', 2),
        ('slow_ema', 30),
        ('filter_period', 200),
        ('atr_period', 14),
        ('atr_stop_mult', 2.0),
        ('trail_atr_mult', 1.5),
        ('use_trailing', True),
        ('printlog', False),
    )

    def __init__(self):
        # KAMA 指标
        self.kama = KAMAIndicator(
            self.data,
            period=self.p.period,
            fast_ema=self.p.fast_ema,
            slow_ema=self.p.slow_ema
        )
        
        # 趋势过滤器：长期均线
        self.trend_ma = bt.indicators.SMA(self.data.close, period=self.p.filter_period)
        
        # 信号：价格与 KAMA 交叉
        self.crossover = bt.indicators.CrossOver(self.data.close, self.kama)
        
        # ATR 用于动态止损和仓位计算
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        
        # 订单和止损追踪
        self.order = None
        self.stop_price = None
        self.entry_price = None

    def log(self, txt: str, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_price = order.executed.price
                self.stop_price = self.entry_price - (self.atr[0] * self.p.atr_stop_mult)
                self.log(f"BUY @ {order.executed.price:.2f}, Stop: {self.stop_price:.2f}")
            elif order.issell():
                self.log(f"SELL @ {order.executed.price:.2f}")
                self.entry_price = None
                self.stop_price = None
        self.order = None

    def next(self):
        if self.order:
            return

        # === 持仓管理：止损 & 移动止损 ===
        if self.position.size > 0:
            current_price = self.data.close[0]
            
            # 检查止损
            if self.stop_price and current_price < self.stop_price:
                self.log(f"STOP LOSS triggered @ {current_price:.2f}")
                self.order = self.close()
                return
            
            # 移动止损：价格上涨时提高止损位
            if self.p.use_trailing and self.entry_price:
                new_stop = current_price - (self.atr[0] * self.p.trail_atr_mult)
                if new_stop > self.stop_price:
                    self.stop_price = new_stop
                    self.log(f"Trailing stop raised to {self.stop_price:.2f}")
            
            # KAMA 死叉平仓
            if self.crossover < 0:
                self.log(f"KAMA CrossDown - EXIT")
                self.order = self.close()
                return

        # === 开仓逻辑：趋势过滤 + KAMA 金叉 ===
        if not self.position:
            # 条件1: 价格在长期均线之上（牛市）
            is_bullish = self.data.close[0] > self.trend_ma[0]
            
            # 条件2: KAMA 金叉
            is_crossover = self.crossover > 0
            
            if is_bullish and is_crossover:
                size = self._calc_size()
                self.log(f"BUY SIGNAL: Price={self.data.close[0]:.2f} > MA={self.trend_ma[0]:.2f}")
                self.order = self.buy(size=size)

    def _calc_size(self):
        """基于 ATR 的仓位计算"""
        if self.atr[0] == 0:
            return 100
        
        # 风险金额 = 2% 账户价值
        risk_amount = self.broker.getvalue() * 0.02
        risk_per_share = self.atr[0] * self.p.atr_stop_mult
        
        if risk_per_share == 0:
            return 100
        
        size = int(risk_amount / risk_per_share)
        # A股：100股整数倍
        lots = max(1, size // 100)
        return lots * 100


def _coerce_kama_optimized(d: dict) -> dict:
    """参数类型转换"""
    return {
        'period': int(d.get('period', 10)),
        'fast_ema': int(d.get('fast_ema', 2)),
        'slow_ema': int(d.get('slow_ema', 30)),
        'filter_period': int(d.get('filter_period', 200)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_stop_mult': float(d.get('atr_stop_mult', 2.0)),
        'trail_atr_mult': float(d.get('trail_atr_mult', 1.5)),
        'use_trailing': bool(d.get('use_trailing', True)),
    }


# =============================================================================
# 2. 期货网格优化：ATR 动态网格间距 + 总体止损
# =============================================================================

class FuturesGrid_ATR_Optimized(bt.Strategy):
    """
    ATR 动态网格策略
    
    优化点：
    1. 网格间距基于 ATR（波动率），而非固定百分比
       - 高波动时：网格变宽，减少交易频率
       - 低波动时：网格变窄，增加交易机会
    2. 增加账户级止损（最大回撤限制）
    3. 定期重新计算网格（适应市场变化）
    
    Math:
        Grid_Spacing = ATR * grid_atr_mult
        Position_Level = floor((Price - Base) / Grid_Spacing)
    
    Parameters:
        atr_period: ATR 计算周期 (default: 14)
        grid_atr_mult: 网格间距 = ATR * mult (default: 0.5)
        layers: 网格层数 (default: 6)
        max_pos: 最大持仓档位 (default: 3)
        lookback: 基准价计算周期 (default: 50)
        stop_loss_pct: 账户止损百分比 (default: 0.10)
        recalc_days: 网格重算周期 (default: 20)
    """
    params = (
        ('atr_period', 14),
        ('grid_atr_mult', 0.5),
        ('layers', 6),
        ('max_pos', 3),
        ('lookback', 50),
        ('stop_loss_pct', 0.10),
        ('recalc_days', 20),
        ('printlog', False),
    )
    
    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.grid_lines = []
        self.position_level = 0
        self.base_price = None
        self.start_cash = None
        self.last_recalc = 0
        self.grid_spacing = None

    def log(self, txt: str, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def prenext(self):
        if len(self) >= self.p.lookback:
            self.next()
    
    def next(self):
        # 初始化起始资金
        if self.start_cash is None:
            self.start_cash = self.broker.getcash()
        
        # === 风控：账户回撤止损 ===
        current_value = self.broker.getvalue()
        if current_value < self.start_cash * (1 - self.p.stop_loss_pct):
            if self.position:
                self.log(f"ACCOUNT STOP LOSS: Value={current_value:.2f}")
                self.close()
            return

        # === 初始化/重算网格 ===
        bars_since_recalc = len(self) - self.last_recalc
        need_recalc = (self.base_price is None) or (bars_since_recalc >= self.p.recalc_days)
        
        if need_recalc:
            self._init_grid()
            self.last_recalc = len(self)
        
        if not self.grid_lines:
            return
        
        # === 网格交易逻辑 ===
        current_price = self.data.close[0]
        current_level = self._get_grid_level(current_price)
        
        # 价格下跌：加仓（做多网格）
        if current_level < self.position_level:
            if self.position_level < self.p.max_pos:
                self.log(f"GRID BUY: Level {self.position_level} -> {self.position_level + 1}")
                self.buy(size=1)
                self.position_level += 1
        
        # 价格上涨：减仓
        elif current_level > self.position_level:
            if self.position_level > -self.p.max_pos:
                self.log(f"GRID SELL: Level {self.position_level} -> {self.position_level - 1}")
                self.sell(size=1)
                self.position_level -= 1
    
    def _init_grid(self):
        """初始化网格线（基于 ATR）"""
        # 计算基准价（中位数）
        prices = [self.data.close[-i] for i in range(min(self.p.lookback, len(self)))]
        if not prices:
            return
        
        self.base_price = sorted(prices)[len(prices) // 2]
        
        # ATR 动态间距
        self.grid_spacing = self.atr[0] * self.p.grid_atr_mult
        if self.grid_spacing <= 0:
            self.grid_spacing = self.base_price * 0.005  # Fallback: 0.5%
        
        # 构建网格线
        self.grid_lines = [
            self.base_price + (self.grid_spacing * i)
            for i in range(-self.p.layers, self.p.layers + 1)
        ]
        self.grid_lines.sort()
        
        self.log(f"Grid Init: Base={self.base_price:.2f}, Spacing={self.grid_spacing:.2f}")
    
    def _get_grid_level(self, price):
        """获取价格所在网格层级"""
        if not self.grid_lines:
            return 0
        for i, line in enumerate(self.grid_lines):
            if price < line:
                return i - self.p.layers
        return self.p.layers


def _coerce_futures_grid_atr(d: dict) -> dict:
    """参数类型转换"""
    return {
        'atr_period': int(d.get('atr_period', 14)),
        'grid_atr_mult': float(d.get('grid_atr_mult', 0.5)),
        'layers': int(d.get('layers', 6)),
        'max_pos': int(d.get('max_pos', 3)),
        'lookback': int(d.get('lookback', 50)),
        'stop_loss_pct': float(d.get('stop_loss_pct', 0.10)),
        'recalc_days': int(d.get('recalc_days', 20)),
    }


# =============================================================================
# 3. 日内回转优化：时间过滤 + ATR 动态阈值 + 止损增强
# =============================================================================

class IntradayReversion_Optimized(bt.Strategy):
    """
    日内回转策略优化版
    
    优化点：
    1. 时间过滤：
       - 开盘观察期：等待价格稳定
       - 尾盘强平：避免隔夜风险
    2. ATR 动态阈值：
       - 入场阈值 = ATR * entry_mult
       - 止损阈值 = ATR * stop_mult
    3. 单边行情保护：最大持仓时间限制
    
    Parameters:
        entry_atr_mult: 入场偏离阈值 (ATR 倍数, default: 1.0)
        stop_atr_mult: 止损偏离阈值 (ATR 倍数, default: 2.0)
        atr_period: ATR 周期 (default: 14)
        start_hour/min: 开仓开始时间 (default: 9:45)
        exit_hour/min: 强平时间 (default: 14:50)
        max_hold_bars: 最大持仓 K 线数 (default: 30)
    """
    params = (
        ('entry_atr_mult', 1.0),
        ('stop_atr_mult', 2.0),
        ('atr_period', 14),
        ('start_hour', 9),
        ('start_min', 45),
        ('exit_hour', 14),
        ('exit_min', 50),
        ('max_hold_bars', 30),
        ('allow_short', False),
        ('printlog', False),
    )

    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.day_open = None
        self.current_date = None
        self.entry_bar = None
        self.start_time = datetime.time(self.p.start_hour, self.p.start_min)
        self.exit_time = datetime.time(self.p.exit_hour, self.p.exit_min)

    def log(self, txt: str, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.datetime(0)
            print(f"{dt} {txt}")

    def next(self):
        current_dt = self.data.datetime.datetime(0)
        current_date = current_dt.date()
        current_time = current_dt.time()

        # === 每日初始化 ===
        if current_date != self.current_date:
            self.day_open = self.data.open[0]
            self.current_date = current_date
            # 如有持仓，视为隔夜（不应发生）
            if self.position:
                self.log("Overnight position detected - CLOSE")
                self.close()
            return

        if self.day_open is None or self.day_open == 0:
            return

        # === 尾盘强制平仓 ===
        if current_time >= self.exit_time:
            if self.position:
                self.log(f"END OF DAY - CLOSE @ {self.data.close[0]:.2f}")
                self.close()
                self.entry_bar = None
            return

        # === 开盘观察期：不交易 ===
        if current_time < self.start_time:
            return

        # === 计算动态阈值 ===
        atr_val = self.atr[0]
        if atr_val == 0:
            return
        
        entry_threshold = atr_val * self.p.entry_atr_mult
        stop_threshold = atr_val * self.p.stop_atr_mult
        deviation = self.data.close[0] - self.day_open

        # === 持仓管理 ===
        if self.position:
            # 检查持仓时间
            if self.entry_bar and (len(self) - self.entry_bar) >= self.p.max_hold_bars:
                self.log(f"MAX HOLD TIME - CLOSE")
                self.close()
                self.entry_bar = None
                return
            
            # 止损检查
            if self.position.size > 0:  # 多头
                if deviation < -stop_threshold:
                    self.log(f"LONG STOP LOSS @ {self.data.close[0]:.2f}")
                    self.close()
                    self.entry_bar = None
                    return
                # 止盈：回归开盘价
                if self.data.close[0] >= self.day_open * 0.998:
                    self.log(f"LONG TARGET - CLOSE @ {self.data.close[0]:.2f}")
                    self.close()
                    self.entry_bar = None
                    return
            
            elif self.position.size < 0:  # 空头
                if deviation > stop_threshold:
                    self.log(f"SHORT STOP LOSS @ {self.data.close[0]:.2f}")
                    self.close()
                    self.entry_bar = None
                    return
                # 止盈：回归开盘价
                if self.data.close[0] <= self.day_open * 1.002:
                    self.log(f"SHORT TARGET - CLOSE @ {self.data.close[0]:.2f}")
                    self.close()
                    self.entry_bar = None
                    return
        
        # === 开仓逻辑 ===
        else:
            # 超跌做多
            if deviation < -entry_threshold:
                size = self._calc_size()
                self.log(f"LONG ENTRY: Deviation={deviation:.2f} < -{entry_threshold:.2f}")
                self.buy(size=size)
                self.entry_bar = len(self)
            
            # 超涨做空（如果允许）
            elif self.p.allow_short and deviation > entry_threshold:
                size = self._calc_size()
                self.log(f"SHORT ENTRY: Deviation={deviation:.2f} > {entry_threshold:.2f}")
                self.sell(size=size)
                self.entry_bar = len(self)
    
    def _calc_size(self):
        """仓位计算"""
        if self.atr[0] == 0:
            return 100
        risk = self.broker.getvalue() * 0.02
        risk_per_share = self.atr[0] * self.p.stop_atr_mult
        if risk_per_share == 0:
            return 100
        size = int(risk / risk_per_share)
        lots = max(1, size // 100)
        return lots * 100


def _coerce_intraday_optimized(d: dict) -> dict:
    """参数类型转换"""
    return {
        'entry_atr_mult': float(d.get('entry_atr_mult', 1.0)),
        'stop_atr_mult': float(d.get('stop_atr_mult', 2.0)),
        'atr_period': int(d.get('atr_period', 14)),
        'start_hour': int(d.get('start_hour', 9)),
        'start_min': int(d.get('start_min', 45)),
        'exit_hour': int(d.get('exit_hour', 14)),
        'exit_min': int(d.get('exit_min', 50)),
        'max_hold_bars': int(d.get('max_hold_bars', 30)),
        'allow_short': bool(d.get('allow_short', False)),
    }


# =============================================================================
# 4. 布林带优化：RSI 过滤 + 趋势确认
# =============================================================================

class BollingerRSI_Optimized(bt.Strategy):
    """
    布林带 + RSI 确认策略
    
    优化点：
    1. RSI 过滤：只有 RSI 超卖时才在下轨买入
       - 避免在强势下跌中"接飞刀"
    2. 趋势过滤（可选）：价格需在 SMA 之上
    3. 分批止盈：中轨平仓一半，上轨全部平仓
    
    Entry Condition:
        Price < BB_Lower AND RSI < rsi_oversold
    
    Exit Condition:
        (Price > BB_Mid) OR (RSI > rsi_overbought)
    
    Parameters:
        period: 布林带周期 (default: 20)
        devfactor: 标准差倍数 (default: 2.0)
        rsi_period: RSI 周期 (default: 14)
        rsi_oversold: RSI 超卖阈值 (default: 30)
        rsi_overbought: RSI 超买阈值 (default: 70)
        use_trend_filter: 是否使用趋势过滤 (default: False)
        trend_period: 趋势均线周期 (default: 50)
    """
    params = (
        ('period', 20),
        ('devfactor', 2.0),
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
        ('use_trend_filter', False),
        ('trend_period', 50),
        ('partial_exit', True),
        ('printlog', False),
    )

    def __init__(self):
        # 布林带
        self.bb = bt.indicators.BollingerBands(
            self.data.close, 
            period=self.p.period, 
            devfactor=self.p.devfactor
        )
        
        # RSI
        self.rsi = bt.indicators.RSI_Safe(self.data.close, period=self.p.rsi_period)
        
        # 趋势过滤（可选）
        if self.p.use_trend_filter:
            self.trend_ma = bt.indicators.SMA(self.data.close, period=self.p.trend_period)
        else:
            self.trend_ma = None
        
        self.order = None
        self.entry_size = 0
        self.partial_exited = False

    def log(self, txt: str, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f"BUY @ {order.executed.price:.2f}")
            else:
                self.log(f"SELL @ {order.executed.price:.2f}")
        self.order = None

    def next(self):
        if self.order:
            return

        close = self.data.close[0]
        
        if not self.position:
            self.partial_exited = False
            
            # === 入场条件 ===
            # 条件1: 价格触及下轨
            below_lower = close < self.bb.bot[0]
            
            # 条件2: RSI 超卖
            rsi_oversold = self.rsi[0] < self.p.rsi_oversold
            
            # 条件3: 趋势过滤（可选）
            trend_ok = True
            if self.trend_ma is not None:
                trend_ok = close > self.trend_ma[0]
            
            if below_lower and rsi_oversold and trend_ok:
                size = self._calc_size()
                self.entry_size = size
                self.log(f"BUY: Close={close:.2f} < BB_Bot={self.bb.bot[0]:.2f}, RSI={self.rsi[0]:.1f}")
                self.order = self.buy(size=size)
        
        else:
            # === 出场条件 ===
            
            # 分批止盈：中轨平仓一半
            if self.p.partial_exit and not self.partial_exited:
                if close > self.bb.mid[0]:
                    half_size = self.position.size // 2
                    if half_size > 0:
                        self.log(f"PARTIAL EXIT @ Mid Band: {close:.2f}")
                        self.order = self.sell(size=half_size)
                        self.partial_exited = True
                        return
            
            # 全部平仓条件
            # 条件1: 触及上轨
            above_upper = close > self.bb.top[0]
            
            # 条件2: RSI 超买
            rsi_overbought = self.rsi[0] > self.p.rsi_overbought
            
            if above_upper or rsi_overbought:
                self.log(f"EXIT: Close={close:.2f}, RSI={self.rsi[0]:.1f}")
                self.order = self.close()
    
    def _calc_size(self):
        """仓位计算"""
        cash = self.broker.getcash()
        price = self.data.close[0]
        if price == 0:
            return 100
        size = int(cash * 0.95 / price)
        lots = max(1, size // 100)
        return lots * 100


def _coerce_bollinger_rsi(d: dict) -> dict:
    """参数类型转换"""
    return {
        'period': int(d.get('period', 20)),
        'devfactor': float(d.get('devfactor', 2.0)),
        'rsi_period': int(d.get('rsi_period', 14)),
        'rsi_oversold': float(d.get('rsi_oversold', 30)),
        'rsi_overbought': float(d.get('rsi_overbought', 70)),
        'use_trend_filter': bool(d.get('use_trend_filter', False)),
        'trend_period': int(d.get('trend_period', 50)),
        'partial_exit': bool(d.get('partial_exit', True)),
    }


# =============================================================================
# 5. 唐奇安通道优化：ATR 波动率突破确认
# =============================================================================

class DonchianATR_Optimized(bt.Strategy):
    """
    唐奇安通道 + ATR 波动率确认
    
    优化点：
    1. 波动率确认：只有当 ATR 上升时才视为有效突破
       - 避免低波动率环境下的假突破
    2. ATR 动态止损：止损位随波动率调整
    3. 移动止损：保护利润
    
    Entry Condition:
        (Price > Upper_Channel) AND (ATR > ATR_MA)
    
    Exit Condition:
        (Price < Lower_Channel) OR (Price < Trailing_Stop)
    
    Parameters:
        upper_period: 上轨周期 (default: 20)
        lower_period: 下轨周期 (default: 10)
        atr_period: ATR 周期 (default: 14)
        atr_ma_period: ATR 均线周期，用于判断波动率趋势 (default: 20)
        atr_stop_mult: ATR 止损倍数 (default: 2.0)
        use_volatility_filter: 是否使用波动率过滤 (default: True)
    """
    params = (
        ('upper_period', 20),
        ('lower_period', 10),
        ('atr_period', 14),
        ('atr_ma_period', 20),
        ('atr_stop_mult', 2.0),
        ('use_volatility_filter', True),
        ('printlog', False),
    )

    def __init__(self):
        # 唐奇安通道
        self.highest = bt.indicators.Highest(self.data.high, period=self.p.upper_period)
        self.lowest = bt.indicators.Lowest(self.data.low, period=self.p.lower_period)
        
        # ATR 和 ATR 均线
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.atr_ma = bt.indicators.SMA(self.atr, period=self.p.atr_ma_period)
        
        self.order = None
        self.entry_price = None
        self.stop_price = None

    def log(self, txt: str, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_price = order.executed.price
                self.stop_price = self.entry_price - (self.atr[0] * self.p.atr_stop_mult)
                self.log(f"BUY @ {order.executed.price:.2f}, Stop: {self.stop_price:.2f}")
            else:
                self.log(f"SELL @ {order.executed.price:.2f}")
                self.entry_price = None
                self.stop_price = None
        self.order = None

    def next(self):
        if self.order:
            return

        close = self.data.close[0]
        
        # 使用前一天的通道值（正确的突破逻辑）
        high_channel = self.highest[-1] if len(self) > 1 else self.highest[0]
        low_channel = self.lowest[-1] if len(self) > 1 else self.lowest[0]
        
        if self.position:
            # === 止损检查 ===
            if self.stop_price and close < self.stop_price:
                self.log(f"STOP LOSS @ {close:.2f}")
                self.order = self.close()
                return
            
            # === 移动止损 ===
            new_stop = close - (self.atr[0] * self.p.atr_stop_mult)
            if self.stop_price and new_stop > self.stop_price:
                self.stop_price = new_stop
            
            # === 跌破下轨出场 ===
            if close < low_channel:
                self.log(f"BREAKDOWN EXIT: {close:.2f} < {low_channel:.2f}")
                self.order = self.close()
        
        else:
            # === 入场条件 ===
            # 条件1: 突破上轨
            breakout = close > high_channel
            
            # 条件2: 波动率确认（ATR > ATR_MA，表示波动率在扩大）
            volatility_rising = True
            if self.p.use_volatility_filter:
                volatility_rising = self.atr[0] > self.atr_ma[0]
            
            if breakout and volatility_rising:
                size = self._calc_size()
                self.log(f"BREAKOUT: {close:.2f} > {high_channel:.2f}, ATR={self.atr[0]:.2f}")
                self.order = self.buy(size=size)
    
    def _calc_size(self):
        """仓位计算"""
        if self.atr[0] == 0:
            return 100
        risk = self.broker.getvalue() * 0.02
        risk_per_share = self.atr[0] * self.p.atr_stop_mult
        if risk_per_share == 0:
            return 100
        size = int(risk / risk_per_share)
        lots = max(1, size // 100)
        return lots * 100


def _coerce_donchian_atr(d: dict) -> dict:
    """参数类型转换"""
    return {
        'upper_period': int(d.get('upper_period', 20)),
        'lower_period': int(d.get('lower_period', 10)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_ma_period': int(d.get('atr_ma_period', 20)),
        'atr_stop_mult': float(d.get('atr_stop_mult', 2.0)),
        'use_volatility_filter': bool(d.get('use_volatility_filter', True)),
    }


# =============================================================================
# 策略配置导出
# =============================================================================

OPTIMIZED_STRATEGIES = {
    'kama_opt': {
        'name': 'kama_opt',
        'description': 'KAMA with SMA200 trend filter and ATR trailing stop',
        'strategy_class': KAMAStrategy_Optimized,
        'param_names': ['period', 'filter_period', 'atr_stop_mult', 'trail_atr_mult'],
        'defaults': {'period': 10, 'filter_period': 200, 'atr_stop_mult': 2.0, 'trail_atr_mult': 1.5},
        'grid_defaults': {
            'period': [8, 10, 12, 15],
            'filter_period': [100, 150, 200],
            'atr_stop_mult': [1.5, 2.0, 2.5],
        },
        'coercer': _coerce_kama_optimized,
    },
    'futures_grid_atr': {
        'name': 'futures_grid_atr',
        'description': 'ATR dynamic grid with account-level stop loss',
        'strategy_class': FuturesGrid_ATR_Optimized,
        'param_names': ['grid_atr_mult', 'layers', 'max_pos', 'stop_loss_pct'],
        'defaults': {'grid_atr_mult': 0.5, 'layers': 6, 'max_pos': 3, 'stop_loss_pct': 0.10},
        'grid_defaults': {
            'grid_atr_mult': [0.3, 0.5, 0.7, 1.0],
            'layers': [4, 6, 8],
            'max_pos': [2, 3, 4],
        },
        'coercer': _coerce_futures_grid_atr,
    },
    'intraday_opt': {
        'name': 'intraday_opt',
        'description': 'Intraday reversion with time filter and ATR threshold',
        'strategy_class': IntradayReversion_Optimized,
        'param_names': ['entry_atr_mult', 'stop_atr_mult', 'max_hold_bars'],
        'defaults': {'entry_atr_mult': 1.0, 'stop_atr_mult': 2.0, 'max_hold_bars': 30},
        'grid_defaults': {
            'entry_atr_mult': [0.8, 1.0, 1.2, 1.5],
            'stop_atr_mult': [1.5, 2.0, 2.5],
        },
        'coercer': _coerce_intraday_optimized,
    },
    'bollinger_rsi': {
        'name': 'bollinger_rsi',
        'description': 'Bollinger Bands with RSI confirmation filter',
        'strategy_class': BollingerRSI_Optimized,
        'param_names': ['period', 'devfactor', 'rsi_oversold', 'rsi_overbought'],
        'defaults': {'period': 20, 'devfactor': 2.0, 'rsi_oversold': 30, 'rsi_overbought': 70},
        'grid_defaults': {
            'period': [15, 20, 25],
            'devfactor': [1.8, 2.0, 2.2],
            'rsi_oversold': [25, 30, 35],
        },
        'coercer': _coerce_bollinger_rsi,
    },
    'donchian_atr': {
        'name': 'donchian_atr',
        'description': 'Donchian breakout with ATR volatility confirmation',
        'strategy_class': DonchianATR_Optimized,
        'param_names': ['upper_period', 'lower_period', 'atr_stop_mult'],
        'defaults': {'upper_period': 20, 'lower_period': 10, 'atr_stop_mult': 2.0},
        'grid_defaults': {
            'upper_period': [15, 20, 25, 30],
            'lower_period': [8, 10, 12],
            'atr_stop_mult': [1.5, 2.0, 2.5],
        },
        'coercer': _coerce_donchian_atr,
    },
}


__all__ = [
    # Strategies
    'KAMAStrategy_Optimized',
    'FuturesGrid_ATR_Optimized',
    'IntradayReversion_Optimized',
    'BollingerRSI_Optimized',
    'DonchianATR_Optimized',
    # Indicators
    'KAMAIndicator',
    # Coercers
    '_coerce_kama_optimized',
    '_coerce_futures_grid_atr',
    '_coerce_intraday_optimized',
    '_coerce_bollinger_rsi',
    '_coerce_donchian_atr',
    # Config
    'OPTIMIZED_STRATEGIES',
]
