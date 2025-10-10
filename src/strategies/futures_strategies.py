# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from .base import BaseStrategy


class FuturesMACrossStrategy(BaseStrategy):
    """双均线策略(期货) —— 使用 EMA，信号 T+1 生效，可用于日/分钟"""
    def __init__(self, short_window: int = 9, long_window: int = 34):
        super().__init__(name=f"期货MA({short_window}/{long_window})")
        self.sw, self.lw = short_window, long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out[f'EMA{self.sw}'] = out['收盘'].ewm(span=self.sw, adjust=False, min_periods=max(2, self.sw//2)).mean()
        out[f'EMA{self.lw}'] = out['收盘'].ewm(span=self.lw, adjust=False, min_periods=max(2, self.lw//2)).mean()
        sig = np.where(out[f'EMA{self.sw}'] > out[f'EMA{self.lw}'], 1, -1)
        out['Signal'] = pd.Series(sig, index=out.index).shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out


class FuturesGridStrategy(BaseStrategy):
    """
    网格交易(期货) —— 以首段中位价为中心的等距百分比网格；仅做多/减仓版本（简洁稳健）
    需要较为平稳的品种与足够的频率（分钟级更佳）。
    """
    def __init__(self, grid_pct: float = 0.004, layers: int = 6, max_pos: int = 3):
        super().__init__(name=f"网格(±{grid_pct*100:.2f}%×{layers})")
        self.gp, self.layers, self.max_pos = grid_pct, layers, max_pos

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        mid = out['收盘'].iloc[:max(50, self.layers*10)].median()
        # 生成网格线
        grids = [mid * (1 + self.gp * i) for i in range(-self.layers, self.layers+1)]
        grids.sort()

        # 位置：跨越上格 -> 减仓；跌破下格 -> 加仓
        pos = np.zeros(len(out), dtype=int)
        last_level = np.searchsorted(grids, out['收盘'].iloc[0])
        for i in range(1, len(out)):
            level = np.searchsorted(grids, out['收盘'].iloc[i])
            step = level - last_level
            pos[i] = pos[i-1]
            if step < 0:  # 向下穿越 -> 买
                pos[i] = min(self.max_pos, pos[i] + abs(step))
            elif step > 0:  # 向上穿越 -> 卖
                pos[i] = max(0, pos[i] - step)
            last_level = level
        # 只输出方向信号（>0 做多；==0 空仓）
        sig = (pos > 0).astype(int)
        out['Signal'] = pd.Series(sig, index=out.index).shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out


class FuturesMarketMakingStrategy(BaseStrategy):
    """
    做市商交易(期货) —— 使用均值回归带模拟在中性库存限制下的报价回转（仅基于OHLC近似）。
    仅做 T+1 信号执行，真实挂单撮合不在此处模拟。
    """
    def __init__(self, band_pct: float = 0.003, inventory_limit: int = 2):
        super().__init__(name=f"做市商(±{band_pct*100:.2f}%,限{inventory_limit})")
        self.band, self.inv = band_pct, inventory_limit

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        mid = out['收盘'].rolling(50, min_periods=20).mean()
        upper = mid * (1 + self.band)
        lower = mid * (1 - self.band)
        inv = 0
        sig = np.zeros(len(out), dtype=int)
        for i in range(1, len(out)):
            px = out['收盘'].iloc[i]
            if px <= (lower.iloc[i] if not np.isnan(lower.iloc[i]) else px*0.999) and inv < self.inv:
                inv += 1   # 买入补库存
            elif px >= (upper.iloc[i] if not np.isnan(upper.iloc[i]) else px*1.001) and inv > -self.inv:
                inv -= 1   # 卖出去库存
            sig[i] = 1 if inv > 0 else ( -1 if inv < 0 else 0 )
        out['Signal'] = pd.Series(sig, index=out.index).shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out


class TurtleFuturesStrategy(BaseStrategy):
    """海龟交易法(期货) —— 唐奇安通道20/10 + ATR×K 止损"""
    def __init__(self, entry_n: int = 20, exit_n: int = 10, atr_mult: float = 2.0):
        super().__init__(name=f"海龟({entry_n}/{exit_n},ATR×{atr_mult})")
        self.en, self.xn, self.k = entry_n, exit_n, atr_mult

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        hh = out['最高'].rolling(self.en, min_periods=max(2, self.en//2)).max().shift(1)
        ll = out['最低'].rolling(self.xn, min_periods=max(2, self.xn//2)).min().shift(1)

        tr1 = out['最高'] - out['最低']
        tr2 = (out['最高'] - out['收盘'].shift()).abs()
        tr3 = (out['最低'] - out['收盘'].shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14, min_periods=7).mean()

        sig = np.where(out['收盘'] > hh, 1, np.where(out['收盘'] < ll, -1, 0))
        # ATR 止损（多头）
        entry = out['收盘'].where(sig == 1).ffill()
        stop = entry - self.k * atr
        stop_hit = out['收盘'] < stop
        sig = np.where(stop_hit, -1, sig)

        out['Signal'] = pd.Series(sig, index=out.index).shift(1).fillna(0)
        out['Position'] = out['Signal'].diff().fillna(0)
        return out