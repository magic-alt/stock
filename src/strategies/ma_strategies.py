"""
双均线交叉策略
"""

import pandas as pd
from .base import BaseStrategy


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略"""
    
    def __init__(self, short_window: int = 5, long_window: int = 20):
        super().__init__(name=f"MA交叉策略({short_window}/{long_window})")
        self.short_window = short_window
        self.long_window = long_window
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        策略逻辑：
        - 短期均线上穿长期均线：买入信号
        - 短期均线下穿长期均线：卖出信号
        """
        # 确保有均线数据
        if f'MA{self.short_window}' not in df.columns:
            df[f'MA{self.short_window}'] = df['收盘'].rolling(
                window=self.short_window
            ).mean()
        
        if f'MA{self.long_window}' not in df.columns:
            df[f'MA{self.long_window}'] = df['收盘'].rolling(
                window=self.long_window
            ).mean()
        
        # 生成信号
        df['Signal'] = 0
        df.loc[
            df[f'MA{self.short_window}'] > df[f'MA{self.long_window}'],
            'Signal'
        ] = 1  # 多头
        df.loc[
            df[f'MA{self.short_window}'] <= df[f'MA{self.long_window}'],
            'Signal'
        ] = -1  # 空头
        
        # 生成交易信号（信号变化点）
        df['Position'] = df['Signal'].diff()
        
        return df


class TripleMACrossStrategy(BaseStrategy):
    """三均线交叉策略"""
    
    def __init__(self, fast: int = 5, mid: int = 10, slow: int = 20):
        super().__init__(name=f"三均线策略({fast}/{mid}/{slow})")
        self.fast = fast
        self.mid = mid
        self.slow = slow
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        策略逻辑：
        - 快线>中线>慢线：强烈买入
        - 快线<中线<慢线：强烈卖出
        """
        # 计算均线
        for period in [self.fast, self.mid, self.slow]:
            if f'MA{period}' not in df.columns:
                df[f'MA{period}'] = df['收盘'].rolling(window=period).mean()
        
        # 生成信号
        df['Signal'] = 0
        
        # 多头排列
        df.loc[
            (df[f'MA{self.fast}'] > df[f'MA{self.mid}']) &
            (df[f'MA{self.mid}'] > df[f'MA{self.slow}']),
            'Signal'
        ] = 1
        
        # 空头排列
        df.loc[
            (df[f'MA{self.fast}'] < df[f'MA{self.mid}']) &
            (df[f'MA{self.mid}'] < df[f'MA{self.slow}']),
            'Signal'
        ] = -1
        
        df['Position'] = df['Signal'].diff()
        
        return df
