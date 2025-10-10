# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from typing import Optional, Sequence
from .base import BaseStrategy


class MultiFactorSelectionStrategy(BaseStrategy):
    """
    多因子选股（单标的评分版）：
    - 动量(Mom_20/60)、波动(Vol_20)、均线偏离(Dist_MA20)、成交量因子(量比)；
    - 对各因子做标准化后线性加权；分数>阈值时做多，否则空仓。
    在单标的回测里可视作“择时打分”；若批量回测可用于选股过滤。
    """
    def __init__(self, use_factors: Optional[Sequence[str]] = None, buy_thresh: float = 0.0):
        super().__init__(name="多因子选股")
        self.use_factors = use_factors
        self.th = buy_thresh

    def _z(self, s: pd.Series) -> pd.Series:
        return (s - s.rolling(60, min_periods=20).mean()) / s.rolling(60, min_periods=20).std().replace(0, np.nan)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out['收盘']
        mom20 = close.pct_change(20)
        mom60 = close.pct_change(60)
        vol20 = close.pct_change().rolling(20, min_periods=10).std()
        ma20 = close.rolling(20, min_periods=10).mean()
        dist_ma20 = (close / ma20 - 1.0)
        vratio = (out['成交量'] / out['成交量'].rolling(20, min_periods=10).mean().replace(0, np.nan))

        feats = {
            'Mom20': self._z(mom20),
            'Mom60': self._z(mom60),
            'Vol20': -self._z(vol20),      # 低波动加分
            'DistMA20': self._z(dist_ma20),
            'VRatio': self._z(vratio)
        }
        if self.use_factors:
            feats = {k: v for k, v in feats.items() if k in self.use_factors}
        score = sum(feats.values()).fillna(0)
        sig = (score > self.th).astype(int)
        out['MF_Score'] = score
        out['Signal'] = sig.shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out


class IndexEnhancementStrategy(BaseStrategy):
    """
    指数增强（股票）：
    - 参考指数列（默认 '指数收盘'）的趋势过滤（MA）与动量；
    - 指数上行阶段才做多个股（或指数），否则空仓。
    若 df 不包含指数列，则退化为自身 MA 过滤。
    """
    def __init__(self, index_col: str = "指数收盘", ma: int = 100):
        super().__init__(name=f"指数增强(MA{ma})")
        self.icol, self.ma = index_col, ma

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        base = out[self.icol] if self.icol in out.columns else out['收盘']
        ma = base.rolling(self.ma, min_periods=max(5, self.ma//5)).mean()
        up = base > ma
        mom = base.pct_change(20)
        sig = (up & (mom > 0)).astype(int)
        out['Signal'] = sig.shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out


class IndustryRotationOverlay(BaseStrategy):
    """
    行业轮动（股票，单标的叠加信号版）：
    - 需要行业指数列 `industry_col`（如 '行业指数收盘'）；
    - 当行业指数相对其 MA 向上、且行业近20日动量为正时，增强个股做多意愿；否则空仓。
    """
    def __init__(self, industry_col: str = "行业指数收盘", lookback: int = 20):
        super().__init__(name="行业轮动")
        self.icol, self.lb = industry_col, lookback

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if self.icol not in out.columns:
            out['Signal'] = 0
            out['Position'] = 0
            return out
        ind = out[self.icol]
        ma = ind.rolling(60, min_periods=20).mean()
        sig = ((ind > ma) & (ind.pct_change(self.lb) > 0)).astype(int)
        out['Signal'] = sig.shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out