"""
MACD策略
"""

import pandas as pd
from .base import BaseStrategy


class MACDStrategy(BaseStrategy):
    """MACD策略"""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(name=f"MACD策略({fast}/{slow}/{signal})")
        self.fast = fast
        self.slow = slow
        self.signal = signal
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        策略逻辑：
        - MACD上穿Signal线：买入
        - MACD下穿Signal线：卖出
        """
        # 计算MACD
        if 'MACD' not in df.columns:
            exp1 = df['收盘'].ewm(span=self.fast, adjust=False).mean()
            exp2 = df['收盘'].ewm(span=self.slow, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_Signal'] = df['MACD'].ewm(span=self.signal, adjust=False).mean()
            df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        # 生成信号
        df['Signal'] = 0
        df.loc[df['MACD'] > df['MACD_Signal'], 'Signal'] = 1
        df.loc[df['MACD'] <= df['MACD_Signal'], 'Signal'] = -1
        
        df['Position'] = df['Signal'].diff()
        
        return df


class MACDZeroCrossStrategy(BaseStrategy):
    """MACD零轴穿越策略"""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(name="MACD零轴策略")
        self.fast = fast
        self.slow = slow
        self.signal = signal
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        策略逻辑：
        - MACD上穿零轴：买入
        - MACD下穿零轴：卖出
        """
        # 计算MACD
        if 'MACD' not in df.columns:
            exp1 = df['收盘'].ewm(span=self.fast, adjust=False).mean()
            exp2 = df['收盘'].ewm(span=self.slow, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_Signal'] = df['MACD'].ewm(span=self.signal, adjust=False).mean()
        
        # 生成信号
        df['Signal'] = 0
        df.loc[df['MACD'] > 0, 'Signal'] = 1
        df.loc[df['MACD'] <= 0, 'Signal'] = -1
        
        df['Position'] = df['Signal'].diff()
        
        return df
