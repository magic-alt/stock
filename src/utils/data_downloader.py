"""
数据下载工具 - 批量下载股票和指数历史数据到本地缓存
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from ..data_sources.cached_source import CachedDataSource
from ..config import STOCK_GROUPS

logger = logging.getLogger(__name__)


class DataDownloader:
    """数据下载器"""
    
    def __init__(self, cache_dir: str = "datacache"):
        """
        初始化数据下载器
        
        Args:
            cache_dir: 缓存目录
        """
        self.cached_source = CachedDataSource(cache_dir=cache_dir)
        logger.info("📥 数据下载器初始化完成")
    
    def download_predefined_stocks(self, start_date: str, end_date: str, 
                                  groups: Optional[List[str]] = None,
                                  adjust: str = 'qfq') -> Dict[str, Dict[str, bool]]:
        """
        下载预定义股票组的历史数据
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            groups: 要下载的股票组名称列表，如果为None则下载所有组
            adjust: 复权类型
            
        Returns:
            下载结果 {group_name: {stock_code: success}}
        """
        if groups is None:
            groups = list(STOCK_GROUPS.keys())
        
        results = {}
        
        logger.info(f"📊 开始下载预定义股票组数据: {groups}")
        
        for group_name in groups:
            if group_name not in STOCK_GROUPS:
                logger.warning(f"⚠️ 未知股票组: {group_name}")
                continue
            
            stock_codes = STOCK_GROUPS[group_name]
            logger.info(f"📂 下载股票组 [{group_name}]: {len(stock_codes)}只股票")
            
            group_results = self.cached_source.download_stock_data(
                stock_codes, start_date, end_date, adjust
            )
            
            results[group_name] = group_results
            
            success_count = sum(group_results.values())
            logger.info(f"✅ 股票组 [{group_name}] 完成: {success_count}/{len(stock_codes)} 成功")
        
        return results
    
    def download_custom_stocks(self, stock_codes: List[str], start_date: str, 
                              end_date: str, adjust: str = 'qfq') -> Dict[str, bool]:
        """
        下载自定义股票列表的历史数据
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型
            
        Returns:
            下载结果 {stock_code: success}
        """
        logger.info(f"📊 开始下载自定义股票数据: {len(stock_codes)}只股票")
        
        return self.cached_source.download_stock_data(
            stock_codes, start_date, end_date, adjust
        )
    
    def download_major_indices(self, start_date: str, end_date: str) -> Dict[str, bool]:
        """
        下载主要指数的历史数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            下载结果 {index_code: success}
        """
        # 主要指数代码
        major_indices = [
            '000001',  # 上证指数
            '399001',  # 深证成指
            '399006',  # 创业板指
            '000300',  # 沪深300
            '000016',  # 上证50
            '000905',  # 中证500
            '000852',  # 中证1000
            '000688',  # 科创50
        ]
        
        logger.info(f"📊 开始下载主要指数数据: {len(major_indices)}个指数")
        
        return self.cached_source.download_index_data(
            major_indices, start_date, end_date
        )
    
    def download_recent_data(self, days: int = 365, groups: Optional[List[str]] = None) -> Dict:
        """
        下载最近N天的数据
        
        Args:
            days: 天数
            groups: 股票组
            
        Returns:
            下载结果
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        logger.info(f"📅 下载最近 {days} 天数据: {start_date} ~ {end_date}")
        
        results = {}
        
        # 下载股票数据
        if groups is not None or len(STOCK_GROUPS) > 0:
            results['stocks'] = self.download_predefined_stocks(
                start_date, end_date, groups
            )
        
        # 下载指数数据
        results['indices'] = self.download_major_indices(start_date, end_date)
        
        return results
    
    def update_data(self, days_back: int = 7) -> Dict:
        """
        更新数据（增量下载最近几天的数据）
        
        Args:
            days_back: 往前多少天开始更新
            
        Returns:
            更新结果
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        logger.info(f"🔄 增量更新数据: {start_date} ~ {end_date}")
        
        results = {}
        
        # 获取所有已缓存的股票代码
        cache_stats = self.cached_source.get_cache_stats()
        
        if cache_stats.get('stock_symbols', 0) > 0:
            # 这里简化处理，实际可以查询数据库获取所有已缓存的股票代码
            # 暂时使用预定义的股票组
            all_stocks = []
            for group_stocks in STOCK_GROUPS.values():
                all_stocks.extend(group_stocks)
            all_stocks = list(set(all_stocks))  # 去重
            
            if all_stocks:
                results['stocks'] = self.cached_source.download_stock_data(
                    all_stocks, start_date, end_date, force_update=True
                )
        
        # 更新指数数据
        results['indices'] = self.download_major_indices(start_date, end_date)
        
        return results
    
    def get_download_suggestions(self) -> Dict:
        """
        获取下载建议
        
        Returns:
            包含建议信息的字典
        """
        cache_stats = self.cached_source.get_cache_stats()
        
        suggestions = {
            'cache_status': cache_stats,
            'recommendations': []
        }
        
        if cache_stats.get('stock_symbols', 0) == 0:
            suggestions['recommendations'].append({
                'type': 'initial_download',
                'message': '建议首次下载最近1年的数据',
                'action': 'download_recent_data(365)'
            })
        else:
            suggestions['recommendations'].append({
                'type': 'regular_update',
                'message': '建议定期更新最近一周的数据',
                'action': 'update_data(7)'
            })
        
        if cache_stats.get('index_symbols', 0) == 0:
            suggestions['recommendations'].append({
                'type': 'index_download',
                'message': '建议下载主要指数数据',
                'action': 'download_major_indices()'
            })
        
        return suggestions
    
    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        return self.cached_source.get_cache_stats()
    
    def clear_cache(self, symbol: Optional[str] = None, symbol_type: Optional[str] = None):
        """清空缓存"""
        self.cached_source.clear_cache(symbol, symbol_type)


def create_download_scheduler():
    """创建下载调度器（示例函数）"""
    import schedule
    import time
    
    downloader = DataDownloader()
    
    def daily_update():
        """每日更新任务"""
        logger.info("🕐 开始每日数据更新任务")
        try:
            results = downloader.update_data(7)
            logger.info(f"✅ 每日更新完成: {results}")
        except Exception as e:
            logger.error(f"❌ 每日更新失败: {e}")
    
    def weekly_full_update():
        """每周完整更新任务"""
        logger.info("🕐 开始每周完整数据更新任务")
        try:
            results = downloader.download_recent_data(30)
            logger.info(f"✅ 每周更新完成: {results}")
        except Exception as e:
            logger.error(f"❌ 每周更新失败: {e}")
    
    # 安排任务
    schedule.every().day.at("18:00").do(daily_update)
    schedule.every().monday.at("06:00").do(weekly_full_update)
    
    logger.info("📅 数据下载调度器已启动")
    
    # 运行调度器（这是示例，实际使用需要在后台运行）
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)
    
    return {
        'daily_update': daily_update,
        'weekly_update': weekly_full_update,
        'scheduler': schedule
    }