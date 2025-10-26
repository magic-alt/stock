# -*- coding: utf-8 -*-
"""
多因子策略集合 - Backtrader版本
包含：多因子选股、指数增强、行业轮动
"""
import backtrader as bt
import numpy as np


class MultiFactorSelectionStrategy(bt.Strategy):
    """
    多因子选股策略（择时版本）
    - 动量因子（20日、60日）
    - 波动率因子（20日）
    - 均线偏离度
    - 成交量因子
    综合打分 > 阈值时做多
    """
    params = (
        ('mom_period_short', 20),
        ('mom_period_long', 60),
        ('vol_period', 20),
        ('ma_period', 20),
        ('vol_ma_period', 20),
        ('score_window', 60),      # Z-score标准化窗口
        ('buy_threshold', 0.0),    # 买入阈值
        ('atr_period', 14),
        ('atr_mult', 2.0),
    )
    
    def __init__(self):
        # 动量因子
        self.mom20 = bt.indicators.ROC(self.data.close, period=self.p.mom_period_short)
        self.mom60 = bt.indicators.ROC(self.data.close, period=self.p.mom_period_long)
        
        # 波动率因子
        self.returns = bt.indicators.PctChange(self.data.close, period=1)
        self.volatility = bt.indicators.StdDev(self.returns, period=self.p.vol_period)
        
        # 均线偏离度
        self.ma20 = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        
        # 成交量因子
        self.vol_ma = bt.indicators.SMA(self.data.volume, period=self.p.vol_ma_period)
        
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        
        # 用于存储历史分数
        self.scores = []
    
    def next(self):
        # 计算各因子
        if self.ma20[0] == 0 or self.vol_ma[0] == 0:
            return
        
        # 均线偏离度
        dist_ma = (self.data.close[0] / self.ma20[0] - 1.0)
        
        # 量比
        vol_ratio = self.data.volume[0] / self.vol_ma[0]
        
        # 计算综合得分（简化版，直接加权）
        score = (
            self.mom20[0] * 0.3 +           # 短期动量
            self.mom60[0] * 0.2 +           # 长期动量
            (-self.volatility[0] * 100) * 0.2 +  # 低波动加分
            dist_ma * 100 * 0.15 +          # 均线偏离度
            (vol_ratio - 1) * 0.15          # 量比
        )
        
        self.scores.append(score)
        if len(self.scores) > self.p.score_window:
            self.scores.pop(0)
        
        # Z-score标准化（简化版）
        if len(self.scores) >= 20:
            mean_score = np.mean(self.scores)
            std_score = np.std(self.scores)
            if std_score > 0:
                z_score = (score - mean_score) / std_score
            else:
                z_score = 0
        else:
            z_score = 0
        
        # 交易逻辑
        if not self.position:
            if z_score > self.p.buy_threshold:
                size = self._calc_size()
                self.buy(size=size)
        else:
            if z_score < -0.5:  # 分数转负，平仓
                self.close()
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 100  # 最小1手
        risk_amount = self.broker.getvalue() * 0.02
        size = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        # 强制100股整数倍（A股规则）
        lots = max(1, size // 100)
        return lots * 100


class IndexEnhancementStrategy(bt.Strategy):
    """
    指数增强策略
    - 参考大盘指数趋势
    - 仅在指数上升趋势中做多个股
    注意：需要benchmark数据，这里简化为自身MA过滤
    """
    params = (
        ('ma_period', 100),         # 趋势判断均线
        ('mom_period', 20),          # 动量周期
        ('atr_period', 14),
        ('atr_mult', 2.0),
    )
    
    def __init__(self):
        self.ma = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.momentum = bt.indicators.ROC(self.data.close, period=self.p.mom_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
    
    def next(self):
        # 趋势判断：价格 > 长期均线 且 动量为正
        uptrend = self.data.close[0] > self.ma[0]
        positive_momentum = self.momentum[0] > 0
        
        if not self.position:
            if uptrend and positive_momentum:
                size = self._calc_size()
                self.buy(size=size)
        else:
            # 趋势反转或动量转负，平仓
            if not uptrend or not positive_momentum:
                self.close()
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 100  # 最小1手
        risk_amount = self.broker.getvalue() * 0.02
        size = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        # 强制100股整数倍（A股规则）
        lots = max(1, size // 100)
        return lots * 100


class IndustryRotationStrategy(bt.Strategy):
    """
    行业轮动策略（单标的简化版）
    - 使用行业相对强度
    - 价格强于长期均线且动量向上时做多
    注意：完整版需要多标的比较，这里简化为单标的强度评估
    """
    params = (
        ('ma_period', 60),           # 行业强度参考均线
        ('momentum_period', 20),      # 动量周期
        ('atr_period', 14),
        ('atr_mult', 2.0),
    )
    
    def __init__(self):
        self.ma = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.momentum = bt.indicators.ROC(self.data.close, period=self.p.momentum_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
    
    def next(self):
        # 行业强度：价格 > 均线 且 动量为正
        strong = self.data.close[0] > self.ma[0]
        positive_mom = self.momentum[0] > 0
        
        if not self.position:
            if strong and positive_mom:
                size = self._calc_size()
                self.buy(size=size)
        else:
            # 强度减弱，平仓
            if not strong or not positive_mom:
                self.close()
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 100  # 最小1手
        risk_amount = self.broker.getvalue() * 0.02
        size = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        # 强制100股整数倍（A股规则）
        lots = max(1, size // 100)
        return lots * 100


# 参数转换函数
def _coerce_multifactor(d: dict) -> dict:
    return {
        'mom_period_short': int(d.get('mom_period_short', 20)),
        'mom_period_long': int(d.get('mom_period_long', 60)),
        'vol_period': int(d.get('vol_period', 20)),
        'ma_period': int(d.get('ma_period', 20)),
        'vol_ma_period': int(d.get('vol_ma_period', 20)),
        'score_window': int(d.get('score_window', 60)),
        'buy_threshold': float(d.get('buy_threshold', 0.0)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
    }


def _coerce_index_enhancement(d: dict) -> dict:
    return {
        'ma_period': int(d.get('ma_period', 100)),
        'mom_period': int(d.get('mom_period', 20)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
    }


def _coerce_industry_rotation(d: dict) -> dict:
    return {
        'ma_period': int(d.get('ma_period', 60)),
        'momentum_period': int(d.get('momentum_period', 20)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
    }
