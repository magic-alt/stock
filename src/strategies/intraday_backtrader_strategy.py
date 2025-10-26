# -*- coding: utf-8 -*-
"""
日内回转策略 - Backtrader版本
基于开盘价的日内均值回归
"""
import backtrader as bt


class IntradayReversionStrategy(bt.Strategy):
    """
    日内回转交易策略
    - 价格偏离开盘价达到阈值时入场
    - 回归开盘价或收盘时平仓
    注意：适用于分钟级数据，日线数据效果有限
    """
    params = (
        ('threshold_pct', 0.8),    # 偏离阈值（%）
        ('allow_short', False),     # 是否允许做空
        ('atr_period', 14),
        ('atr_mult', 2.0),
    )
    
    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.day_open = None
        self.current_date = None
    
    def prenext(self):
        self.next()
    
    def next(self):
        # 检测新的交易日
        current_date = self.data.datetime.date(0)
        if current_date != self.current_date:
            # 新的一天，记录开盘价
            self.day_open = self.data.open[0]
            self.current_date = current_date
            # 如果有持仓，先平仓（日内回转）
            if self.position:
                self.close()
            return
        
        if self.day_open is None or self.day_open == 0:
            return
        
        # 计算偏离百分比
        deviation = (self.data.close[0] / self.day_open - 1.0) * 100.0
        
        if not self.position:
            # 开仓逻辑：价格大幅偏离开盘价
            if deviation <= -self.p.threshold_pct:
                # 下跌超过阈值，做多（预期回归）
                size = self._calc_size()
                self.buy(size=size)
            elif self.p.allow_short and deviation >= self.p.threshold_pct:
                # 上涨超过阈值，做空（预期回归）
                size = self._calc_size()
                self.sell(size=size)
        else:
            # 平仓逻辑：回归开盘价附近
            if self.position.size > 0:  # 持有多头
                if self.data.close[0] >= self.day_open * 0.995:
                    self.close()
            elif self.position.size < 0:  # 持有空头
                if self.data.close[0] <= self.day_open * 1.005:
                    self.close()
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 100  # 最小1手
        risk_amount = self.broker.getvalue() * 0.02
        size = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        # 强制100股整数倍（A股规则）
        lots = max(1, size // 100)
        return lots * 100


def _coerce_intraday(d: dict) -> dict:
    return {
        'threshold_pct': float(d.get('threshold_pct', 0.8)),
        'allow_short': bool(d.get('allow_short', False)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
    }
