# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from .base import BaseStrategy


class AuctionOpenSelectionStrategy(BaseStrategy):
    """
    集合竞价选股（简化回测版）：
    - 开盘涨幅 >= gap_min（相对昨收）；
    - 首日成交量相对过去均量的放大倍数 >= vol_ratio_min；
    信号在开盘后 T+1 生效（防未来函数），仅输出做多/空仓。
    需要 df 包含列：'开盘'、'收盘'、'昨收'(可选)、'成交量'
    """
    def __init__(self, gap_min: float = 2.0, vol_ratio_min: float = 1.5):
        super().__init__(name=f"集合竞价(≥{gap_min:.1f}%,量比≥{vol_ratio_min:.1f})")
        self.gap, self.vr = gap_min, vol_ratio_min

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        prev_close = out.get('昨收', out['收盘'].shift())
        gap_pct = (out['开盘'] / prev_close - 1.0) * 100.0
        vol_ma = out['成交量'].rolling(20, min_periods=10).mean()
        vol_ratio = out['成交量'] / vol_ma.replace(0, np.nan)
        cond = (gap_pct >= self.gap) & (vol_ratio >= self.vr)
        sig = cond.astype(int)
        out['Signal'] = sig.shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out