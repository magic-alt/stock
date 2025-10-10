# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from .base import BaseStrategy


class IntradayReversionStrategy(BaseStrategy):
    """
    日内回转交易（股票/期货通用）：
    - 以当日开盘为基准，若(收盘-开盘)/开盘 < -k% 则做多，> +k% 则做空（默认为仅做多）；
    - 每个交易日收盘平仓（daily_reset=True）。
    适用于分钟级数据；日线将退化为“开收价反转”信号。
    """
    def __init__(self, k: float = 0.8, daily_reset: bool = True, allow_short: bool = False):
        super().__init__(name=f"日内回转(k={k:.2f}%)")
        self.k, self.reset, self.short = k, daily_reset, allow_short

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        date = pd.to_datetime(out.index).date
        day_open = out['开盘'].groupby(date).transform('first')
        ret = (out['收盘'] / day_open - 1.0) * 100.0
        long_cond = ret <= -self.k
        short_cond = ret >= self.k if self.short else pd.Series(False, index=out.index)
        sig = long_cond.astype(int) - short_cond.astype(int)
        if self.reset:
            # 收盘前一根强制平仓：将当日最后一根的信号设为0
            last_bar = pd.Series(date, index=out.index).astype(str).ne(pd.Series(date, index=out.index).shift(-1).astype(str))
            sig = sig.mask(last_bar, 0)
        out['Signal'] = sig.shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out