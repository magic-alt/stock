"""
MACD系列策略（增强）
"""
import numpy as np
import pandas as pd
from .base import BaseStrategy


class MACDStrategy(BaseStrategy):
    """MACD信号线交叉（稳健版，min_periods/shift）"""
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9, regime_ma: int = 100):
        super().__init__(name=f"MACD策略({fast}/{slow}/{signal})")
        self.fast, self.slow, self.signal = fast, slow, signal
        self.regime_ma = regime_ma

    def _calc_macd(self, close: pd.Series) -> pd.DataFrame:
        exp1 = close.ewm(span=self.fast, adjust=False, min_periods=max(2, self.fast//2)).mean()
        exp2 = close.ewm(span=self.slow, adjust=False, min_periods=max(2, self.slow//2)).mean()
        macd = exp1 - exp2
        macd_sig = macd.ewm(span=self.signal, adjust=False, min_periods=max(2, self.signal//2)).mean()
        hist = macd - macd_sig
        return pd.DataFrame({'MACD': macd, 'MACD_Signal': macd_sig, 'MACD_Hist': hist})

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        macd_df = self._calc_macd(df['收盘'])
        df = pd.concat([df, macd_df], axis=1)
        regime = df['收盘'].rolling(self.regime_ma, min_periods=max(5, self.regime_ma//5)).mean()
        uptrend = df['收盘'] > regime
        sig = np.where((df['MACD'] > df['MACD_Signal']) & uptrend, 1,
                       np.where((df['MACD'] <= df['MACD_Signal']) & (~uptrend), -1, 0))
        df['Signal'] = pd.Series(sig, index=df.index).shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        return df


class MACDZeroCrossStrategy(BaseStrategy):
    """MACD零轴穿越策略（稳健版）"""
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(name="MACD零轴策略")
        self.fast, self.slow, self.signal = fast, slow, signal

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        exp1 = df['收盘'].ewm(span=self.fast, adjust=False, min_periods=max(2, self.fast//2)).mean()
        exp2 = df['收盘'].ewm(span=self.slow, adjust=False, min_periods=max(2, self.slow//2)).mean()
        macd = exp1 - exp2
        df['MACD'] = macd
        df['Signal'] = np.where(df['MACD'] > 0, 1, -1)
        df['Signal'] = df['Signal'].shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        return df


class MACDHistogramMomentum(BaseStrategy):
    """MACD Histogram 动量策略：Hist 由负转正做多、由正转负做空，可选阈值过滤"""
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9, thresh: float = 0.0):
        super().__init__(name="MACD-Hist动量")
        self.fast, self.slow, self.signal, self.thresh = fast, slow, signal, thresh

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        exp1 = df['收盘'].ewm(span=self.fast, adjust=False, min_periods=max(2, self.fast//2)).mean()
        exp2 = df['收盘'].ewm(span=self.slow, adjust=False, min_periods=max(2, self.slow//2)).mean()
        macd = exp1 - exp2
        macd_sig = macd.ewm(span=self.signal, adjust=False, min_periods=max(2, self.signal//2)).mean()
        hist = macd - macd_sig
        turn_up = (hist > self.thresh) & (hist.shift(1) <= self.thresh)
        turn_dn = (hist < -self.thresh) & (hist.shift(1) >= -self.thresh)
        sig = np.where(turn_up, 1, np.where(turn_dn, -1, 0))
        df['Signal'] = pd.Series(sig, index=df.index).shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        df['MACD_Hist'] = hist
        return df
