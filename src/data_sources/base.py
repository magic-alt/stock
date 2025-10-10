"""
数据源基类 - 定义统一的数据接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime


class DataSource(ABC):
    """数据源抽象基类"""
    
    def __init__(self):
        self.cache = {}
        self.cache_expire = 60  # 缓存过期时间（秒）
    
    @abstractmethod
    def get_stock_realtime(self, stock_code: str) -> Optional[Dict]:
        """获取股票实时数据"""
        pass
    
    @abstractmethod
    def get_index_realtime(self, index_code: str) -> Optional[Dict]:
        """获取指数实时数据"""
        pass
    
    @abstractmethod
    def get_stock_history(self, stock_code: str, start_date: str, 
                          end_date: str, adjust: str = 'qfq') -> pd.DataFrame:
        """获取股票历史数据"""
        pass
    
    @abstractmethod
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        pass
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
