"""
策略基类
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Optional


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str = "Base Strategy"):
        self.name = name
        self.positions = {}  # 持仓信息
        self.trades = []     # 交易记录
        
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Args:
            df: 包含OHLCV数据和技术指标的DataFrame
        
        Returns:
            添加了信号列的DataFrame
        """
        pass
    
    def get_signal_at(self, df: pd.DataFrame, index: int) -> int:
        """
        获取指定位置的信号
        
        Returns:
            1: 买入, -1: 卖出, 0: 持有
        """
        if 'Signal' not in df.columns or index >= len(df):
            return 0
        return int(df.iloc[index]['Signal'])
    
    def reset(self):
        """重置策略状态"""
        self.positions = {}
        self.trades = []
