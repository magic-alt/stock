"""
数据源工厂 - 创建不同的数据源实例
"""

from .base import DataSource
from .akshare_source import AKShareDataSource


class DataSourceFactory:
    """数据源工厂"""
    
    @staticmethod
    def create(source_type: str = 'akshare') -> DataSource:
        """
        创建数据源实例
        
        Args:
            source_type: 数据源类型 ('akshare', 'tushare', 'eastmoney')
        
        Returns:
            DataSource实例
        """
        if source_type.lower() == 'akshare':
            return AKShareDataSource()
        elif source_type.lower() == 'tushare':
            # 预留tushare接口
            raise NotImplementedError("Tushare数据源暂未实现")
        elif source_type.lower() == 'eastmoney':
            # 预留东方财富接口
            raise NotImplementedError("东方财富数据源暂未实现")
        else:
            raise ValueError(f"不支持的数据源类型: {source_type}")
