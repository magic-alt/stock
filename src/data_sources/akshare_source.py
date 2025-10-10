"""
AKShare数据源实现（补丁：统一成交额为"元"）
"""

import akshare as ak
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import logging
from .base import DataSource
from src.utils.safe_cast import safe_float, safe_int, safe_str

# 配置日志
logger = logging.getLogger(__name__)

# ==== 新增：明确单位配置 ====
# Eastmoney 个股成交额：万元；指数成交额：亿元（若将来变更，只需改这里）
AMOUNT_UNIT_STOCK = "wan"  # "wan" 表示万元
AMOUNT_UNIT_INDEX = "yi"   # "yi"  表示亿元

def _to_yuan(amount: float, unit: str) -> float:
    """将不同单位的金额统一转换为【元】"""
    if amount is None:
        return 0.0
    try:
        if unit == "wan":
            return float(amount) * 1e4    # 万元 -> 元
        if unit == "yi":
            return float(amount) * 1e8    # 亿元 -> 元
        # 默认为"元"
        return float(amount)
    except Exception:
        return 0.0


class AKShareDataSource(DataSource):
    """AKShare数据源"""
    
    def __init__(self):
        super().__init__()
        self._stock_spot_cache = None
        self._index_spot_cache = None
        self._cache_time = None
        self._last_error_time = None  # 记录上次错误时间，避免重复打印
    
    def _refresh_spot_cache(self):
        """刷新实时数据缓存"""
        now = datetime.now()
        
        # 计算缓存年龄
        cache_age = 0 if self._cache_time is None else (now - self._cache_time).total_seconds()
        
        if (self._cache_time is None or cache_age > self.cache_expire):
            try:
                self._stock_spot_cache = ak.stock_zh_a_spot_em()
                self._index_spot_cache = ak.stock_zh_index_spot_em()
                old_cache_time = self._cache_time
                self._cache_time = now
                self._last_error_time = None  # 清除错误记录
                
                logger.info(f"缓存刷新成功，旧缓存年龄: {cache_age:.0f}秒")
                
            except Exception as e:
                # 避免重复打印相同错误（60秒内只打印一次）
                should_print = True
                if self._last_error_time:
                    time_since_error = (now - self._last_error_time).total_seconds()
                    should_print = time_since_error > 60
                
                if should_print:
                    # 用户可见的友好提示
                    print(f"⚠ 网络异常，无法刷新数据: {e}")
                    if self._cache_time:
                        cache_age_min = int(cache_age / 60)
                        print(f"  继续使用旧缓存（缓存年龄: {cache_age_min}分钟）")
                    
                    # 日志记录（同样去重）
                    logger.warning(f"刷新缓存失败: {e}，保留旧缓存")
                    
                    # 检查缓存是否过期过久
                    if cache_age > self.cache_expire * 5:
                        logger.error(f"⚠ 缓存已过期 {cache_age:.0f}秒（超过5倍TTL），可能存在网络问题")
                    
                    self._last_error_time = now
    
    def get_stock_realtime(self, stock_code: str) -> Optional[Dict]:
        """获取股票实时数据（成交额已统一为"元"）"""
        try:
            self._refresh_spot_cache()
            
            if self._stock_spot_cache is None:
                return None
            
            stock_data = self._stock_spot_cache[
                self._stock_spot_cache['代码'] == stock_code
            ]
            
            if stock_data.empty:
                return None
            
            info = stock_data.iloc[0]
            
            # === 关键修复：个股成交额(万元) -> 元 ===
            amount_wan = safe_float(info['成交额'])
            amount_yuan = _to_yuan(amount_wan, AMOUNT_UNIT_STOCK)
            
            return {
                '代码': stock_code,
                '名称': safe_str(info['名称'], stock_code),
                '最新价': safe_float(info['最新价']),
                '涨跌幅': safe_float(info['涨跌幅']),
                '涨跌额': safe_float(info['涨跌额']),
                '成交量': safe_int(info['成交量']),
                '成交额': amount_yuan,  # 统一为"元"
                '振幅': safe_float(info['振幅']),
                '最高': safe_float(info['最高']),
                '最低': safe_float(info['最低']),
                '今开': safe_float(info['今开']),
                '昨收': safe_float(info['昨收']),
                '换手率': safe_float(info['换手率']),
                '更新时间': datetime.now().strftime('%H:%M:%S'),
            }
        except Exception as e:
            print(f"获取股票 {stock_code} 实时数据失败: {e}")
            return None
    
    def get_index_realtime(self, index_code: str) -> Optional[Dict]:
        """获取指数实时数据（成交额已统一为"元"）"""
        try:
            self._refresh_spot_cache()
            
            if self._index_spot_cache is None:
                return None
            
            index_data = self._index_spot_cache[
                self._index_spot_cache['代码'] == index_code
            ]
            
            if index_data.empty:
                return None
            
            info = index_data.iloc[0]
            
            # === 关键修复：指数成交额(亿元) -> 元 ===
            amount_em = safe_float(info['成交额'])
            amount_yuan = _to_yuan(amount_em, AMOUNT_UNIT_INDEX)
            
            return {
                '代码': index_code,
                '名称': safe_str(info['名称'], index_code),
                '最新价': safe_float(info['最新价']),
                '涨跌幅': safe_float(info['涨跌幅']),
                '涨跌额': safe_float(info['涨跌额']),
                '成交量': safe_int(info['成交量']),
                '成交额': amount_yuan,  # 统一为"元"
                '振幅': safe_float(info['振幅']),
                '最高': safe_float(info['最高']),
                '最低': safe_float(info['最低']),
                '今开': safe_float(info['今开']),
                '昨收': safe_float(info['昨收']),
                '更新时间': datetime.now().strftime('%H:%M:%S'),
            }
        except Exception as e:
            print(f"获取指数 {index_code} 实时数据失败: {e}")
            return None
    
    def get_stock_history(self, stock_code: str, start_date: str, 
                         end_date: str, adjust: str = 'qfq') -> pd.DataFrame:
        """获取股票历史数据"""
        try:
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            return df
        except Exception as e:
            print(f"获取股票 {stock_code} 历史数据失败: {e}")
            return pd.DataFrame()
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        try:
            # 从实时数据中获取基本信息
            return self.get_stock_realtime(stock_code)
        except Exception as e:
            print(f"获取股票 {stock_code} 信息失败: {e}")
            return None
    
    def get_all_stocks_realtime(self) -> pd.DataFrame:
        """获取所有股票实时数据"""
        self._refresh_spot_cache()
        return self._stock_spot_cache if self._stock_spot_cache is not None else pd.DataFrame()
    
    def get_all_indices_realtime(self) -> pd.DataFrame:
        """获取所有指数实时数据"""
        self._refresh_spot_cache()
        return self._index_spot_cache if self._index_spot_cache is not None else pd.DataFrame()
