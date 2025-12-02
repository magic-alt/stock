# -*- coding: utf-8 -*-
"""
集合竞价策略 - Backtrader版本
开盘涨幅 + 成交量放大过滤

V3.0.0 优化:
- 增加 gap_max 防止追高"力竭缺口"
- 增加 max_pos_pct 单笔最大仓位限制
- 增加 ATR 止损线
"""
import backtrader as bt


class AuctionOpenSelectionStrategy(bt.Strategy):
    """
    集合竞价选股策略
    - 开盘涨幅 >= gap_min 且 <= gap_max（相对昨收）
    - 当日成交量 >= 过去均量 * vol_ratio_min
    
    V3.0.0 优化:
    - gap_max: 防止追高力竭缺口（过大的涨幅往往是出货）
    - max_pos_pct: 单笔最大仓位限制，防止梭哈
    - ATR 动态止损：允许回撤 0.5 ATR
    """
    params = (
        ('gap_min', 2.0),          # 最小开盘涨幅（%）
        ('gap_max', 7.0),          # V3.0: 最大开盘涨幅，防止追高力竭缺口
        ('vol_ratio_min', 1.5),    # 最小量比
        ('vol_period', 20),        # 成交量均值周期
        ('atr_period', 14),
        ('atr_mult', 2.0),
        ('max_pos_pct', 0.5),      # V3.0: 单笔最大仓位限制(50%资金)
        ('stop_atr_mult', 0.5),    # V3.0: 止损 ATR 倍数
        ('printlog', False),
    )
    
    def __init__(self):
        self.vol_ma = bt.indicators.SMA(self.data.volume, period=self.p.vol_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.entry_price = None
    
    def log(self, txt: str, dt=None):
        if self.p.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt.isoformat()} {txt}")
    
    def next(self):
        # 计算开盘涨幅
        prev_close = self.data.close[-1]
        if prev_close == 0 or self.vol_ma[0] == 0:
            return
        
        gap_pct = (self.data.open[0] / prev_close - 1.0) * 100.0
        vol_ratio = self.data.volume[0] / self.vol_ma[0]
        
        # 开仓条件
        if not self.position:
            # V3.0: 增加 gap_max 过滤，防止追高力竭缺口
            if self.p.gap_min <= gap_pct <= self.p.gap_max and vol_ratio >= self.p.vol_ratio_min:
                size = self._calc_size()
                self.buy(size=size)
                self.entry_price = self.data.open[0]
                self.log(f"BUY: Gap={gap_pct:.1f}%, VolRatio={vol_ratio:.1f}")
        else:
            # V3.0 增强止损：收盘跌破开盘价 OR 跌破 ATR 止损线
            stop_price = self.data.open[0] - (self.atr[0] * self.p.stop_atr_mult)
            
            if self.data.close[0] < self.data.open[0]:
                self.log(f"SELL: Close < Open (Day Reversal)")
                self.close()
                self.entry_price = None
            elif self.data.close[0] < stop_price:
                self.log(f"SELL: ATR Stop @ {stop_price:.2f}")
                self.close()
                self.entry_price = None
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 100  # 最小1手
        
        cash = self.broker.getcash()
        risk_amount = self.broker.getvalue() * 0.02
        size_risk = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        
        # V3.0: 增加仓位上限保护
        price = self.data.close[0]
        if price > 0:
            max_size = int((cash * self.p.max_pos_pct) / price)
            size_risk = min(size_risk, max_size)
        
        # 强制100股整数倍（A股规则）
        lots = max(1, size_risk // 100)
        return lots * 100


def _coerce_auction(d: dict) -> dict:
    return {
        'gap_min': float(d.get('gap_min', 2.0)),
        'gap_max': float(d.get('gap_max', 7.0)),
        'vol_ratio_min': float(d.get('vol_ratio_min', 1.5)),
        'vol_period': int(d.get('vol_period', 20)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
        'max_pos_pct': float(d.get('max_pos_pct', 0.5)),
        'stop_atr_mult': float(d.get('stop_atr_mult', 0.5)),
    }
