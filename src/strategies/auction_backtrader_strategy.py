# -*- coding: utf-8 -*-
"""
集合竞价策略 - Backtrader版本
开盘涨幅 + 成交量放大过滤
"""
import backtrader as bt


class AuctionOpenSelectionStrategy(bt.Strategy):
    """
    集合竞价选股策略
    - 开盘涨幅 >= gap_min（相对昨收）
    - 当日成交量 >= 过去均量 * vol_ratio_min
    """
    params = (
        ('gap_min', 2.0),          # 最小开盘涨幅（%）
        ('vol_ratio_min', 1.5),    # 最小量比
        ('vol_period', 20),        # 成交量均值周期
        ('atr_period', 14),
        ('atr_mult', 2.0),
    )
    
    def __init__(self):
        self.vol_ma = bt.indicators.SMA(self.data.volume, period=self.p.vol_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
    
    def next(self):
        # 计算开盘涨幅
        prev_close = self.data.close[-1]
        if prev_close == 0:
            return
        
        gap_pct = (self.data.open[0] / prev_close - 1.0) * 100.0
        
        # 计算量比
        if self.vol_ma[0] == 0:
            return
        vol_ratio = self.data.volume[0] / self.vol_ma[0]
        
        # 开仓条件
        if not self.position:
            if gap_pct >= self.p.gap_min and vol_ratio >= self.p.vol_ratio_min:
                size = self._calc_size()
                self.buy(size=size)
        else:
            # 简单止盈止损：收盘价跌破开盘价则平仓
            if self.data.close[0] < self.data.open[0]:
                self.close()
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 100  # 最小1手
        risk_amount = self.broker.getvalue() * 0.02
        size = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        # 强制100股整数倍（A股规则）
        lots = max(1, size // 100)
        return lots * 100


def _coerce_auction(d: dict) -> dict:
    return {
        'gap_min': float(d.get('gap_min', 2.0)),
        'vol_ratio_min': float(d.get('vol_ratio_min', 1.5)),
        'vol_period': int(d.get('vol_period', 20)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
    }
