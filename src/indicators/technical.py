"""
技术指标计算模块
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class TechnicalIndicators:
    """技术指标计算器"""

    @staticmethod
    def _ensure_numeric(df: pd.DataFrame, cols: list) -> pd.DataFrame:
        """确保指定列为数值类型"""
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        return df
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """
        计算移动平均线
        
        Args:
            df: 包含'收盘'列的DataFrame
            periods: MA周期列表
        
        Returns:
            添加了MA列的DataFrame
        """
        df = TechnicalIndicators._ensure_numeric(df, ['收盘'])
        for period in periods:
            df[f'MA{period}'] = df['收盘'].rolling(window=period, min_periods=max(1, period//2)).mean()
        return df
    
    @staticmethod
    def calculate_ema(df: pd.DataFrame, periods: list = [12, 26]) -> pd.DataFrame:
        """
        计算指数移动平均线
        
        Args:
            df: 包含'收盘'列的DataFrame
            periods: EMA周期列表
        
        Returns:
            添加了EMA列的DataFrame
        """
        df = TechnicalIndicators._ensure_numeric(df, ['收盘'])
        for period in periods:
            df[f'EMA{period}'] = df['收盘'].ewm(span=period, adjust=False, min_periods=max(1, period//2)).mean()
        return df
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        计算RSI指标
        
        Args:
            df: 包含'收盘'列的DataFrame
            period: RSI周期
        
        Returns:
            添加了RSI列的DataFrame
        """
        df = TechnicalIndicators._ensure_numeric(df, ['收盘'])
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=max(1, period//2)).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=max(1, period//2)).mean()

        # 防除零
        rs = np.where(loss == 0, np.nan, gain / loss)
        rsi = 100 - (100 / (1 + rs))
        df[f'RSI{period}'] = pd.Series(rsi, index=df.index).bfill().fillna(50.0)
        
        return df
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, 
                      signal: int = 9) -> pd.DataFrame:
        """
        计算MACD指标
        
        Args:
            df: 包含'收盘'列的DataFrame
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期
        
        Returns:
            添加了MACD相关列的DataFrame
        """
        df = TechnicalIndicators._ensure_numeric(df, ['收盘'])
        exp1 = df['收盘'].ewm(span=fast, adjust=False, min_periods=max(1, fast//2)).mean()
        exp2 = df['收盘'].ewm(span=slow, adjust=False, min_periods=max(1, slow//2)).mean()
        
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False, min_periods=max(1, signal//2)).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        return df
    
    @staticmethod
    def calculate_bollinger(df: pd.DataFrame, period: int = 20, 
                           std_dev: int = 2) -> pd.DataFrame:
        """
        计算布林带
        
        Args:
            df: 包含'收盘'列的DataFrame
            period: 周期
            std_dev: 标准差倍数
        
        Returns:
            添加了布林带列的DataFrame
        """
        df = TechnicalIndicators._ensure_numeric(df, ['收盘'])
        df['BB_Middle'] = df['收盘'].rolling(window=period, min_periods=max(1, period//2)).mean()
        std = df['收盘'].rolling(window=period, min_periods=max(1, period//2)).std()
        df['BB_Upper'] = df['BB_Middle'] + (std * std_dev)
        df['BB_Lower'] = df['BB_Middle'] - (std * std_dev)
        
        return df
    
    @staticmethod
    def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, 
                     m2: int = 3) -> pd.DataFrame:
        """
        计算KDJ指标
        
        Args:
            df: 包含'最高', '最低', '收盘'列的DataFrame
            n: RSV周期
            m1: K值周期
            m2: D值周期
        
        Returns:
            添加了KDJ列的DataFrame
        """
        df = TechnicalIndicators._ensure_numeric(df, ['最高', '最低', '收盘'])
        low_list = df['最低'].rolling(window=n, min_periods=max(1, n//2)).min()
        high_list = df['最高'].rolling(window=n, min_periods=max(1, n//2)).max()
        
        den = (high_list - low_list)
        den = den.replace(0, np.nan)
        rsv = (df['收盘'] - low_list) / den * 100
        
        df['K'] = rsv.ewm(com=m1 - 1, adjust=False, min_periods=1).mean()
        df['D'] = df['K'].ewm(com=m2 - 1, adjust=False, min_periods=1).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        
        return df
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        计算ATR (平均真实波幅)
        
        Args:
            df: 包含'最高', '最低', '收盘'列的DataFrame
            period: ATR周期
        
        Returns:
            添加了ATR列的DataFrame
        """
        df = TechnicalIndicators._ensure_numeric(df, ['最高', '最低', '收盘'])
        high_low = df['最高'] - df['最低']
        high_close = np.abs(df['最高'] - df['收盘'].shift())
        low_close = np.abs(df['最低'] - df['收盘'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        
        df[f'ATR{period}'] = true_range.rolling(window=period, min_periods=max(1, period//2)).mean()
        
        return df
    
    @staticmethod
    def calculate_volume_ma(df: pd.DataFrame, periods: list = [5, 10]) -> pd.DataFrame:
        """
        计算成交量移动平均
        
        Args:
            df: 包含'成交量'列的DataFrame
            periods: 周期列表
        
        Returns:
            添加了成交量MA列的DataFrame
        """
        df = TechnicalIndicators._ensure_numeric(df, ['成交量'])
        for period in periods:
            df[f'VOL_MA{period}'] = df['成交量'].rolling(window=period, min_periods=max(1, period//2)).mean()
        return df
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame, config: Dict = None) -> pd.DataFrame:
        """
        计算所有常用技术指标
        
        Args:
            df: 原始DataFrame
            config: 配置参数
        
        Returns:
            添加了所有指标的DataFrame
        """
        if config is None:
            config = {}
        
        # MA
        df = TechnicalIndicators.calculate_ma(
            df, config.get('ma_periods', [5, 10, 20, 60])
        )
        
        # EMA
        df = TechnicalIndicators.calculate_ema(
            df, config.get('ema_periods', [12, 26])
        )
        
        # RSI
        df = TechnicalIndicators.calculate_rsi(
            df, config.get('rsi_period', 14)
        )
        
        # MACD
        df = TechnicalIndicators.calculate_macd(
            df, 
            config.get('macd_fast', 12),
            config.get('macd_slow', 26),
            config.get('macd_signal', 9)
        )
        
        # Bollinger Bands
        df = TechnicalIndicators.calculate_bollinger(
            df,
            config.get('bb_period', 20),
            config.get('bb_std', 2)
        )
        
        # KDJ
        df = TechnicalIndicators.calculate_kdj(
            df,
            config.get('kdj_n', 9),
            config.get('kdj_m1', 3),
            config.get('kdj_m2', 3)
        )
        
        # ATR
        df = TechnicalIndicators.calculate_atr(
            df, config.get('atr_period', 14)
        )
        
        # Volume MA
        df = TechnicalIndicators.calculate_volume_ma(
            df, config.get('vol_ma_periods', [5, 10])
        )
        
        return df
    
    @staticmethod
    def get_latest_indicators(df: pd.DataFrame) -> Dict:
        """
        获取最新的技术指标值
        
        Args:
            df: 包含技术指标的DataFrame
        
        Returns:
            最新指标字典
        """
        if df.empty:
            return {}
        
        latest = df.iloc[-1]
        indicators = {}
        
        # 提取所有技术指标
        for col in df.columns:
            if col in ['MA5', 'MA10', 'MA20', 'MA60', 'EMA12', 'EMA26',
                      'RSI14', 'MACD', 'MACD_Signal', 'MACD_Hist',
                      'BB_Upper', 'BB_Middle', 'BB_Lower',
                      'K', 'D', 'J', 'ATR14', 'VOL_MA5', 'VOL_MA10']:
                value = latest.get(col)
                if pd.notna(value):
                    indicators[col] = round(float(value), 4)
        
        return indicators
