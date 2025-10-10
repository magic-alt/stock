"""
RSI系列策略（增强）
"""
import numpy as np
import pandas as pd
from .base import BaseStrategy


class RSIStrategy(BaseStrategy):
    """RSI超买超卖（稳健版）"""
    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(name=f"RSI策略(周期{period})")
        self.period, self.oversold, self.overbought = period, oversold, overbought

    def _rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=max(2, period//2)).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=max(2, period//2)).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.bfill().fillna(50.0)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df[f'RSI{self.period}'] = self._rsi(df['收盘'], self.period)
        sig = np.where(df[f'RSI{self.period}'] < self.oversold, 1,
                       np.where(df[f'RSI{self.period}'] > self.overbought, -1, 0))
        df['Signal'] = pd.Series(sig, index=df.index).shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        return df


class RSIMaFilterStrategy(BaseStrategy):
    """RSI + 长期均线过滤（趋势内做超跌反弹）"""
    def __init__(self, period: int = 14, oversold: int = 30, ma: int = 200):
        super().__init__(name=f"RSI+MA过滤(RSI{period}/MA{ma})")
        self.period, self.oversold, self.ma = period, oversold, ma

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        rsi = RSIStrategy(period=self.period, oversold=self.oversold, overbought=100)._rsi(df['收盘'], self.period)
        ma = df['收盘'].rolling(self.ma, min_periods=max(5, self.ma//5)).mean()
        uptrend = df['收盘'] > ma
        sig = np.where(uptrend & (rsi < self.oversold), 1, 0)
        df['Signal'] = pd.Series(sig, index=df.index).shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        df[f'RSI{self.period}'] = rsi
        return df


class RSIDivergenceStrategy(BaseStrategy):
    """RSI背离（稳健计算）"""
    def __init__(self, period: int = 14, lookback: int = 5):
        super().__init__(name="RSI背离策略")
        self.period, self.lookback = period, lookback

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        rsi = RSIStrategy(period=self.period, oversold=0, overbought=100)._rsi(df['收盘'], self.period)
        df['Signal'] = 0
        for i in range(self.lookback, len(df)):
            recent_p = df['收盘'].iloc[i-self.lookback:i+1]
            recent_r = rsi.iloc[i-self.lookback:i+1]
            if (df['收盘'].iloc[i] <= recent_p.min()) and (rsi.iloc[i] > recent_r.min()):
                df.loc[df.index[i], 'Signal'] = 1
            if (df['收盘'].iloc[i] >= recent_p.max()) and (rsi.iloc[i] < recent_r.max()):
                df.loc[df.index[i], 'Signal'] = -1
        df['Signal'] = df['Signal'].shift(1).fillna(0)
        df['Position'] = df['Signal'].diff().fillna(0)
        df[f'RSI{self.period}'] = rsi
        return df
