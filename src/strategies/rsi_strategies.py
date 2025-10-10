"""
RSI策略
"""

import pandas as pd
from .base import BaseStrategy


class RSIStrategy(BaseStrategy):
    """RSI超买超卖策略"""
    
    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(name=f"RSI策略(周期{period})")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        策略逻辑：
        - RSI < 超卖线：买入信号
        - RSI > 超买线：卖出信号
        """
        # 计算RSI
        if f'RSI{self.period}' not in df.columns:
            delta = df['收盘'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
            rs = gain / loss
            df[f'RSI{self.period}'] = 100 - (100 / (1 + rs))
        
        # 生成信号
        df['Signal'] = 0
        df.loc[df[f'RSI{self.period}'] < self.oversold, 'Signal'] = 1   # 超卖买入
        df.loc[df[f'RSI{self.period}'] > self.overbought, 'Signal'] = -1  # 超买卖出
        
        df['Position'] = df['Signal'].diff()
        
        return df


class RSIDivergenceStrategy(BaseStrategy):
    """RSI背离策略"""
    
    def __init__(self, period: int = 14, lookback: int = 5):
        super().__init__(name=f"RSI背离策略")
        self.period = period
        self.lookback = lookback
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        策略逻辑：
        - 价格创新低，RSI未创新低：底背离，买入
        - 价格创新高，RSI未创新高：顶背离，卖出
        """
        # 计算RSI
        if f'RSI{self.period}' not in df.columns:
            delta = df['收盘'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
            rs = gain / loss
            df[f'RSI{self.period}'] = 100 - (100 / (1 + rs))
        
        df['Signal'] = 0
        
        # 简化的背离检测
        for i in range(self.lookback, len(df)):
            recent_prices = df['收盘'].iloc[i-self.lookback:i+1]
            recent_rsi = df[f'RSI{self.period}'].iloc[i-self.lookback:i+1]
            
            # 底背离
            if (df['收盘'].iloc[i] == recent_prices.min() and
                df[f'RSI{self.period}'].iloc[i] > recent_rsi.min()):
                df.loc[df.index[i], 'Signal'] = 1
            
            # 顶背离
            if (df['收盘'].iloc[i] == recent_prices.max() and
                df[f'RSI{self.period}'].iloc[i] < recent_rsi.max()):
                df.loc[df.index[i], 'Signal'] = -1
        
        df['Position'] = df['Signal'].diff()
        
        return df
