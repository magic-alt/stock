"""
均线类策略（强化）
"""
import numpy as np
import pandas as pd
from .base import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略（稳健版，min_periods/shift 防未来函数）"""
    def __init__(self, short_window: int = 5, long_window: int = 20):
        super().__init__(name=f"MA交叉策略({short_window}/{long_window})")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        sw, lw = self.short_window, self.long_window
        df[f'MA{sw}'] = df['收盘'].rolling(window=sw, min_periods=max(2, sw//2)).mean()
        df[f'MA{lw}'] = df['收盘'].rolling(window=lw, min_periods=max(2, lw//2)).mean()

        # 金叉/死叉（用前一日信号交易，避免未来函数）
        cond_long = df[f'MA{sw}'] > df[f'MA{lw}']
        signal = np.where(cond_long, 1, -1)
        df['Signal'] = pd.Series(signal, index=df.index).shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        return df


class TripleMACrossStrategy(BaseStrategy):
    """三均线交叉策略（稳健版）"""
    def __init__(self, fast: int = 5, mid: int = 10, slow: int = 20):
        super().__init__(name=f"三均线策略({fast}/{mid}/{slow})")
        self.fast, self.mid, self.slow = fast, mid, slow

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for p in [self.fast, self.mid, self.slow]:
            df[f'MA{p}'] = df['收盘'].rolling(window=p, min_periods=max(2, p//2)).mean()
        long_cond = (df[f'MA{self.fast}'] > df[f'MA{self.mid}']) & (df[f'MA{self.mid}'] > df[f'MA{self.slow}'])
        short_cond = (df[f'MA{self.fast}'] < df[f'MA{self.mid}']) & (df[f'MA{self.mid}'] < df[f'MA{self.slow}'])
        signal = np.where(long_cond, 1, np.where(short_cond, -1, 0))
        df['Signal'] = pd.Series(signal, index=df.index).shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        return df


class EMACrossStrategy(BaseStrategy):
    """EMA 双均线交叉 + 波动过滤（ATR% 或价格波动）"""
    def __init__(self, fast: int = 12, slow: int = 26, vol_filter: float = 0.0):
        super().__init__(name=f"EMA交叉({fast}/{slow})")
        self.fast, self.slow, self.vol_filter = fast, slow, vol_filter

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df[f'EMA{self.fast}'] = df['收盘'].ewm(span=self.fast, adjust=False, min_periods=max(2, self.fast//2)).mean()
        df[f'EMA{self.slow}'] = df['收盘'].ewm(span=self.slow, adjust=False, min_periods=max(2, self.slow//2)).mean()
        cross_up = (df[f'EMA{self.fast}'] > df[f'EMA{self.slow}'])
        cross_dn = ~cross_up
        # 简易波动过滤：最近N日标准差/价格
        vol = df['收盘'].pct_change().rolling(10, min_periods=5).std()
        pass_vol = (vol.fillna(0) >= self.vol_filter) if self.vol_filter > 0 else True
        sig = np.where(cross_up & pass_vol, 1, np.where(cross_dn & pass_vol, -1, 0))
        df['Signal'] = pd.Series(sig, index=df.index).shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        return df


class KAMACrossStrategy(BaseStrategy):
    """Kaufman Adaptive Moving Average(自适应均线) 交叉"""
    def __init__(self, fast_ema: int = 2, slow_ema: int = 30, er_window: int = 10):
        super().__init__(name=f"KAMA交叉(er={er_window})")
        self.fast_ema, self.slow_ema, self.er_window = fast_ema, slow_ema, er_window

    @staticmethod
    def _kama(close: pd.Series, er_w: int, fast: int, slow: int) -> pd.Series:
        change = (close - close.shift(er_w)).abs()
        volatility = close.diff().abs().rolling(er_w, min_periods=max(2, er_w//2)).sum()
        er = (change / volatility.replace(0, np.nan)).fillna(0)
        sc = (er * (2/(fast+1) - 2/(slow+1)) + 2/(slow+1)) ** 2
        kama = close.copy()
        for i in range(1, len(close)):
            alpha = sc.iloc[i]
            kama.iloc[i] = kama.iloc[i-1] + alpha * (close.iloc[i] - kama.iloc[i-1]) if pd.notna(alpha) else kama.iloc[i-1]
        return kama

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        kama_fast = self._kama(df['收盘'], self.er_window, self.fast_ema, self.slow_ema)
        kama_slow = kama_fast.rolling(10, min_periods=5).mean()
        sig = np.where(kama_fast > kama_slow, 1, -1)
        df['Signal'] = pd.Series(sig, index=df.index).shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        return df
