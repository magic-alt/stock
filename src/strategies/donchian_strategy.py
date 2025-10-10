# -*- coding: utf-8 -*-
"""
唐奇安通道突破策略（Donchian Channel Breakout）
经典趋势跟踪策略，适用于趋势明显的市场
"""
import pandas as pd
from .base import BaseStrategy


class DonchianBreakoutStrategy(BaseStrategy):
    """
    唐奇安通道突破策略
    
    策略逻辑：
    - 入场：收盘价突破 N 日最高价 → 买入
    - 出场：收盘价跌破 exit_N 日最低价 → 卖出
    
    适用场景：
    - 趋势市场（单边上涨或下跌）
    - 大周期交易（日线以上）
    - 避免震荡市使用
    
    参数说明：
    - n: 突破周期（默认20日）
    - exit_n: 出场周期（默认10日，小于 n）
    """
    
    def __init__(self, n: int = 20, exit_n: int = 10):
        """
        初始化唐奇安通道策略
        
        Args:
            n: 突破周期（计算 N 日最高价）
            exit_n: 出场周期（计算 exit_N 日最低价）
        """
        super().__init__(name=f"Donchian({n},{exit_n})")
        self.n = n
        self.exit_n = exit_n
        
        if exit_n >= n:
            print(f"⚠ 警告：exit_n ({exit_n}) >= n ({n})，可能导致过早出场")
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        策略逻辑：
        1. 计算 N 日最高价（HH）和 exit_N 日最低价（LL）
        2. 收盘价突破 HH → 买入信号
        3. 收盘价跌破 LL → 卖出信号
        
        Args:
            df: 历史数据（需包含：最高、最低、收盘）
        
        Returns:
            添加了 Signal 和 Position 列的 DataFrame
        """
        df = df.copy()
        
        # 计算唐奇安通道
        # shift(1)：避免使用当日数据，防止未来函数
        df['HH'] = df['最高'].rolling(
            window=self.n, 
            min_periods=max(2, self.n // 2)
        ).max().shift(1)
        
        df['LL'] = df['最低'].rolling(
            window=self.exit_n,
            min_periods=max(2, self.exit_n // 2)
        ).min().shift(1)
        
        # 初始化信号
        df['Signal'] = 0
        
        # 买入信号：收盘价突破 N 日最高
        df.loc[df['收盘'] > df['HH'], 'Signal'] = 1
        
        # 卖出信号：收盘价跌破 exit_N 日最低
        df.loc[df['收盘'] < df['LL'], 'Signal'] = -1
        
        # 生成交易信号（仅在信号变化点交易）
        df['Position'] = df['Signal'].diff().fillna(0)
        
        return df
    
    def get_channel_width(self, df: pd.DataFrame) -> pd.Series:
        """
        计算通道宽度（用于评估市场波动性）
        
        Returns:
            通道宽度百分比序列
        """
        if 'HH' not in df.columns or 'LL' not in df.columns:
            df = self.generate_signals(df)
        
        # 通道宽度 = (最高 - 最低) / 最低 * 100
        width = ((df['HH'] - df['LL']) / df['LL'] * 100).fillna(0)
        return width
    
    def validate_parameters(self) -> bool:
        """
        验证参数合理性
        
        Returns:
            True: 参数合理
            False: 参数不合理
        """
        if self.n <= 0 or self.exit_n <= 0:
            print(f"❌ 参数错误：n 和 exit_n 必须 > 0")
            return False
        
        if self.exit_n >= self.n:
            print(f"⚠ 建议：exit_n ({self.exit_n}) < n ({self.n}) 以快速止损")
        
        return True
