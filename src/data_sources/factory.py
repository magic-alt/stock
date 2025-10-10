"""
数据源工厂 - 创建不同的数据源实例（支持自动降级）
"""

import logging
from .base import DataSource
from .akshare_source import AKShareDataSource

logger = logging.getLogger(__name__)

class DataSourceFactory:
    """数据源工厂（智能降级）"""
    
    @staticmethod
    def create(source_type: str = 'akshare') -> DataSource:
        """
        创建数据源实例，支持自动降级
        
        Args:
            source_type: 数据源类型 ('akshare', 'sina', 'auto')
        
        Returns:
            DataSource实例
        """
        if source_type.lower() == 'auto':
            # 自动选择可用的数据源
            return DataSourceFactory._create_auto_fallback()
        elif source_type.lower() == 'akshare':
            return AKShareDataSource()
        elif source_type.lower() == 'sina':
            # 延迟导入避免循环依赖
            from .sina_source import SinaDataSource
            return SinaDataSource()
        elif source_type.lower() == 'tushare':
            # 延迟导入，避免依赖不存在导致导入失败
            from .tushare_source import TuShareDataSource
            return TuShareDataSource()
        elif source_type.lower() == 'yfinance':
            from .yfinance_source import YFinanceDataSource
            return YFinanceDataSource()
        elif source_type.lower() == 'eastmoney':
            # 预留东方财富接口
            raise NotImplementedError("东方财富数据源暂未实现")
        else:
            raise ValueError(f"不支持的数据源类型: {source_type}")
    
    @staticmethod
    def _create_auto_fallback() -> DataSource:
        """自动降级创建数据源"""
        logger.info("🔄 自动选择可用数据源...")
        
        # 1. 首先尝试AKShare
        try:
            source = AKShareDataSource()
            # 快速测试连接
            logger.info("📡 测试AKShare连接...")
            test_result = source._quick_test_connection()
            if test_result:
                logger.info("✅ AKShare数据源可用")
                return source
            else:
                logger.warning("⚠ AKShare连接测试失败，尝试备用数据源...")
        except Exception as e:
            logger.warning(f"⚠ AKShare初始化失败: {e}")
        
        # 2. 降级到新浪财经
        try:
            from .sina_source import SinaDataSource
            source = SinaDataSource()
            logger.info("✅ 已自动降级到新浪财经数据源")
            print("📢 已自动切换到新浪财经数据源（AKShare连接异常）")
            return source
        except Exception as e:
            logger.error(f"❌ 新浪数据源也失败: {e}")
        
        # 3. 最后返回AKShare（即使有问题也要有个实例）
        logger.warning("⚠ 所有数据源测试失败，返回默认AKShare实例")
        return AKShareDataSource()