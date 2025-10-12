"""
缓存数据源 - 优先从本地缓存读取，缺失数据从网络获取并缓存
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from .base import DataSource
from .cache_manager import DataCacheManager
from .factory import DataSourceFactory

logger = logging.getLogger(__name__)


class CachedDataSource(DataSource):
    """带缓存功能的数据源包装器"""
    
    def __init__(self, underlying_source: Optional[DataSource] = None, cache_dir: str = "datacache"):
        """
        初始化缓存数据源
        
        Args:
            underlying_source: 底层数据源，如果为None则自动创建
            cache_dir: 缓存目录
        """
        super().__init__()
        
        # 缓存管理器
        self.cache_manager = DataCacheManager(cache_dir)
        
        # 底层数据源（用于获取网络数据）
        if underlying_source is None:
            self.underlying_source = DataSourceFactory.create('auto')
        else:
            self.underlying_source = underlying_source
        
        logger.info("🔗 缓存数据源初始化完成")
    
    def get_stock_realtime(self, stock_code: str) -> Optional[Dict]:
        """获取股票实时数据（直接从网络获取，不缓存）"""
        return self.underlying_source.get_stock_realtime(stock_code)
    
    def get_index_realtime(self, index_code: str) -> Optional[Dict]:
        """获取指数实时数据（直接从网络获取，不缓存）"""
        return self.underlying_source.get_index_realtime(index_code)
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息（直接从网络获取）"""
        return self.underlying_source.get_stock_info(stock_code)
    
    def get_stock_history(self, stock_code: str, start_date: str, 
                          end_date: str, adjust: str = 'qfq') -> pd.DataFrame:
        """
        获取股票历史数据（优先从缓存，缺失部分从网络获取）
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            adjust: 复权类型
            
        Returns:
            历史数据DataFrame
        """
        try:
            logger.debug(f"📊 获取股票历史数据: {stock_code} ({start_date} ~ {end_date})")
            
            # 1. 首先尝试从缓存获取完整数据
            cached_data = self.cache_manager.get_cached_stock_data(
                stock_code, start_date, end_date, adjust
            )
            
            # 2. 检查是否需要补充数据
            missing_ranges = self.cache_manager.get_missing_date_ranges(
                stock_code, start_date, end_date, 'stock'
            )
            
            if not missing_ranges:
                # 缓存数据完整
                if cached_data is not None and not cached_data.empty:
                    logger.info(f"📋 从缓存获取完整数据: {stock_code}, {len(cached_data)}条记录")
                    return cached_data
            
            # 3. 需要从网络获取缺失数据
            logger.info(f"🌐 需要从网络获取数据: {stock_code}, 缺失区间: {len(missing_ranges)}")
            
            all_data_frames = []
            
            # 添加已有的缓存数据
            if cached_data is not None and not cached_data.empty:
                all_data_frames.append(cached_data)
            
            # 获取缺失的数据区间
            for range_start, range_end in missing_ranges:
                try:
                    logger.debug(f"📡 获取网络数据: {range_start} ~ {range_end}")
                    
                    network_data = self.underlying_source.get_stock_history(
                        stock_code, range_start, range_end, adjust
                    )
                    
                    if network_data is not None and not network_data.empty:
                        # 保存到缓存
                        self.cache_manager.save_stock_data(stock_code, network_data, adjust)
                        all_data_frames.append(network_data)
                        logger.info(f"💾 缓存网络数据: {stock_code}, {len(network_data)}条记录")
                    
                except Exception as e:
                    logger.warning(f"⚠️ 获取网络数据失败 {range_start}~{range_end}: {e}")
                    continue
            
            # 4. 合并所有数据
            if all_data_frames:
                result = pd.concat(all_data_frames, ignore_index=False)
                result = result.sort_index().drop_duplicates()
                
                # 确保索引是DatetimeIndex
                if not isinstance(result.index, pd.DatetimeIndex):
                    if 'date' in result.columns:
                        result['date'] = pd.to_datetime(result['date'])
                        result.set_index('date', inplace=True)
                    elif '日期' in result.columns:
                        result['日期'] = pd.to_datetime(result['日期'])
                        result.set_index('日期', inplace=True)
                
                # 筛选请求的日期范围
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                
                result = result[
                    (result.index >= start_dt) & 
                    (result.index <= end_dt)
                ]
                
                logger.info(f"✅ 获取股票数据完成: {stock_code}, 总计{len(result)}条记录")
                return result
            
            # 5. 如果都失败了，返回空DataFrame
            logger.warning(f"⚠️ 无法获取股票数据: {stock_code}")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ 获取股票历史数据失败: {e}")
            return pd.DataFrame()
    
    def get_index_history(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取指数历史数据（优先从缓存，缺失部分从网络获取）
        
        Args:
            index_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            历史数据DataFrame
        """
        try:
            logger.debug(f"📊 获取指数历史数据: {index_code} ({start_date} ~ {end_date})")
            
            # 1. 从缓存获取数据
            cached_data = self.cache_manager.get_cached_index_data(
                index_code, start_date, end_date
            )
            
            # 2. 检查缺失区间
            missing_ranges = self.cache_manager.get_missing_date_ranges(
                index_code, start_date, end_date, 'index'
            )
            
            if not missing_ranges:
                if cached_data is not None and not cached_data.empty:
                    logger.info(f"📋 从缓存获取完整指数数据: {index_code}, {len(cached_data)}条记录")
                    return cached_data
            
            # 3. 获取缺失数据
            logger.info(f"🌐 需要从网络获取指数数据: {index_code}, 缺失区间: {len(missing_ranges)}")
            
            all_data_frames = []
            
            if cached_data is not None and not cached_data.empty:
                all_data_frames.append(cached_data)
            
            for range_start, range_end in missing_ranges:
                try:
                    # 检查底层数据源是否支持指数历史数据
                    if hasattr(self.underlying_source, 'get_index_history'):
                        network_data = self.underlying_source.get_index_history(
                            index_code, range_start, range_end
                        )
                    else:
                        # 如果不支持，尝试作为股票获取
                        network_data = self.underlying_source.get_stock_history(
                            index_code, range_start, range_end
                        )
                    
                    if network_data is not None and not network_data.empty:
                        self.cache_manager.save_index_data(index_code, network_data)
                        all_data_frames.append(network_data)
                        logger.info(f"💾 缓存指数数据: {index_code}, {len(network_data)}条记录")
                    
                except Exception as e:
                    logger.warning(f"⚠️ 获取指数网络数据失败 {range_start}~{range_end}: {e}")
                    continue
            
            # 4. 合并数据
            if all_data_frames:
                result = pd.concat(all_data_frames, ignore_index=False)
                result = result.sort_index().drop_duplicates()
                
                # 确保索引是DatetimeIndex
                if not isinstance(result.index, pd.DatetimeIndex):
                    if 'date' in result.columns:
                        result['date'] = pd.to_datetime(result['date'])
                        result.set_index('date', inplace=True)
                    elif '日期' in result.columns:
                        result['日期'] = pd.to_datetime(result['日期'])
                        result.set_index('日期', inplace=True)
                
                # 筛选请求的日期范围
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                
                result = result[
                    (result.index >= start_dt) & 
                    (result.index <= end_dt)
                ]
                
                logger.info(f"✅ 获取指数数据完成: {index_code}, 总计{len(result)}条记录")
                return result
            
            logger.warning(f"⚠️ 无法获取指数数据: {index_code}")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ 获取指数历史数据失败: {e}")
            return pd.DataFrame()
    
    def download_stock_data(self, stock_codes: list, start_date: str, end_date: str,
                           adjust: str = 'qfq', force_update: bool = False) -> Dict[str, bool]:
        """
        批量下载股票历史数据到缓存
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型
            force_update: 是否强制更新已有数据
            
        Returns:
            下载结果字典 {stock_code: success}
        """
        results = {}
        total = len(stock_codes)
        
        logger.info(f"📥 开始批量下载股票数据: {total}只股票")
        
        for i, stock_code in enumerate(stock_codes, 1):
            try:
                logger.info(f"📡 [{i}/{total}] 下载 {stock_code}")
                
                # 如果不强制更新，先检查是否已有数据
                if not force_update:
                    coverage = self.cache_manager.get_data_coverage(stock_code, 'stock')
                    if coverage and coverage['end_date'] >= end_date:
                        logger.info(f"📋 {stock_code} 数据已存在，跳过")
                        results[stock_code] = True
                        continue
                
                # 获取数据（会自动缓存）
                data = self.get_stock_history(stock_code, start_date, end_date, adjust)
                
                if not data.empty:
                    results[stock_code] = True
                    logger.info(f"✅ {stock_code} 下载成功: {len(data)}条记录")
                else:
                    results[stock_code] = False
                    logger.warning(f"⚠️ {stock_code} 下载失败或无数据")
                
            except Exception as e:
                results[stock_code] = False
                logger.error(f"❌ {stock_code} 下载异常: {e}")
        
        success_count = sum(results.values())
        logger.info(f"📊 批量下载完成: {success_count}/{total} 成功")
        
        return results
    
    def download_index_data(self, index_codes: list, start_date: str, end_date: str,
                           force_update: bool = False) -> Dict[str, bool]:
        """
        批量下载指数历史数据到缓存
        
        Args:
            index_codes: 指数代码列表
            start_date: 开始日期
            end_date: 结束日期
            force_update: 是否强制更新
            
        Returns:
            下载结果字典
        """
        results = {}
        total = len(index_codes)
        
        logger.info(f"📥 开始批量下载指数数据: {total}个指数")
        
        for i, index_code in enumerate(index_codes, 1):
            try:
                logger.info(f"📡 [{i}/{total}] 下载 {index_code}")
                
                if not force_update:
                    coverage = self.cache_manager.get_data_coverage(index_code, 'index')
                    if coverage and coverage['end_date'] >= end_date:
                        logger.info(f"📋 {index_code} 数据已存在，跳过")
                        results[index_code] = True
                        continue
                
                data = self.get_index_history(index_code, start_date, end_date)
                
                if not data.empty:
                    results[index_code] = True
                    logger.info(f"✅ {index_code} 下载成功: {len(data)}条记录")
                else:
                    results[index_code] = False
                    logger.warning(f"⚠️ {index_code} 下载失败或无数据")
                
            except Exception as e:
                results[index_code] = False
                logger.error(f"❌ {index_code} 下载异常: {e}")
        
        success_count = sum(results.values())
        logger.info(f"📊 批量下载完成: {success_count}/{total} 成功")
        
        return results
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        return self.cache_manager.get_cache_stats()
    
    def clear_cache(self, symbol: Optional[str] = None, symbol_type: Optional[str] = None):
        """清空缓存"""
        self.cache_manager.clear_cache(symbol, symbol_type)
    
    def get_stock_history_simple(self, stock_code: str, start_date: str, end_date: str, adjust: str = 'qfq') -> pd.DataFrame:
        """
        简化的股票历史数据获取方法
        直接调用底层数据源的简化方法，避免复杂的缓存逻辑
        """
        try:
            # 检查底层数据源是否有简化方法
            if hasattr(self.underlying_source, 'get_stock_history_simple'):
                return self.underlying_source.get_stock_history_simple(stock_code, start_date, end_date, adjust)
            else:
                # 回退到标准方法
                return self.underlying_source.get_stock_history(stock_code, start_date, end_date, adjust)
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 简化历史数据失败: {e}")
            return pd.DataFrame()