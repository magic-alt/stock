"""
新浪财经数据源实现（临时备用方案）
"""

import requests
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import time
import re
from .base import DataSource
from src.utils.safe_cast import safe_float, safe_int, safe_str

logger = logging.getLogger(__name__)

class SinaDataSource(DataSource):
    """新浪财经数据源（备用）"""
    
    def __init__(self):
        super().__init__()
        self._cache = {}
        self._cache_time = None
        self._last_error_time = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://finance.sina.com.cn/',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive'
        })
    
    def _parse_sina_data(self, content: str) -> Dict:
        """解析新浪财经数据格式"""
        try:
            # 新浪数据格式: var hq_str_sh000001="name,current,yesterday,open,high,low,..."
            match = re.search(r'var hq_str_[^=]+="([^"]+)"', content)
            if not match:
                return None
            
            data_parts = match.group(1).split(',')
            if len(data_parts) < 10:
                return None
            
            # 新浪财经数据字段位置
            name = data_parts[0]
            open_price = safe_float(data_parts[1])
            yesterday = safe_float(data_parts[2])
            current = safe_float(data_parts[3])
            high = safe_float(data_parts[4])
            low = safe_float(data_parts[5])
            
            # 成交量和成交额位置
            volume = safe_int(data_parts[8]) if len(data_parts) > 8 else 0
            amount = safe_float(data_parts[9]) if len(data_parts) > 9 else 0.0
            
            # 计算振幅
            amplitude = 0.0
            if yesterday > 0:
                amplitude = ((high - low) / yesterday) * 100
            
            # 换手率需要额外计算或设为0（新浪不直接提供）
            turnover_rate = 0.0
            
            return {
                '名称': name,
                '最新价': current,
                '昨收': yesterday, 
                '今开': open_price,
                '最高': high,
                '最低': low,
                '成交量': volume,
                '成交额': amount,
                '振幅': amplitude,
                '换手率': turnover_rate,
                '更新时间': datetime.now().strftime('%H:%M:%S')
            }
        except Exception as e:
            logger.warning(f"解析新浪数据失败: {e}")
            return None
    
    def get_stock_realtime(self, stock_code: str) -> Optional[Dict]:
        """获取股票实时数据"""
        try:
            # 转换股票代码格式：000001 -> sz000001, 600000 -> sh600000  
            if stock_code.startswith('6'):
                sina_code = f"sh{stock_code}"
            elif stock_code.startswith(('0', '3')):
                sina_code = f"sz{stock_code}"
            else:
                sina_code = stock_code
            
            url = f"http://hq.sinajs.cn/list={sina_code}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = self._parse_sina_data(response.text)
                if data:
                    # 计算涨跌幅和涨跌额
                    current = data.get('最新价', 0)
                    yesterday = data.get('昨收', 0)
                    if yesterday > 0:
                        change = current - yesterday
                        change_pct = (change / yesterday) * 100
                        data['涨跌额'] = change
                        data['涨跌幅'] = change_pct
                    
                    data['代码'] = stock_code
                    return data
            
            return None
        except Exception as e:
            logger.warning(f"获取股票{stock_code}数据失败: {e}")
            return None
    
    def get_index_realtime(self, index_code: str) -> Optional[Dict]:
        """获取指数实时数据"""
        # 指数代码映射
        index_map = {
            '000001': 'sh000001',  # 上证指数
            '399001': 'sz399001',  # 深证成指
            '399006': 'sz399006',  # 创业板指
            '000300': 'sh000300',  # 沪深300
            '000016': 'sh000016',  # 上证50
            '000688': 'sh000688',  # 科创50
            '399975': 'sz399975',  # 证券公司
            '000905': 'sh000905',  # 中证500
        }
        
        sina_code = index_map.get(index_code, f"sh{index_code}")
        
        try:
            url = f"http://hq.sinajs.cn/list={sina_code}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = self._parse_sina_data(response.text)
                if data:
                    # 计算涨跌幅和涨跌额
                    current = data.get('最新价', 0)
                    yesterday = data.get('昨收', 0)
                    if yesterday > 0:
                        change = current - yesterday
                        change_pct = (change / yesterday) * 100
                        data['涨跌额'] = change
                        data['涨跌幅'] = change_pct
                    
                    data['代码'] = index_code
                    return data
            
            return None
        except Exception as e:
            logger.warning(f"获取指数{index_code}数据失败: {e}")
            return None
    
    def get_stock_history(self, stock_code: str, start_date: str, 
                         end_date: str, adjust: str = 'qfq') -> pd.DataFrame:
        """获取股票历史数据（新浪不提供完整历史数据，返回模拟数据）"""
        logger.warning("新浪数据源不支持完整历史数据获取")
        
        # 返回包含当前价格的最小数据集，用于基本回测
        try:
            current_data = self.get_stock_realtime(stock_code)
            if current_data:
                # 模拟最近几天的数据（用于技术指标计算）
                dates = pd.date_range(end=datetime.now().date(), periods=30, freq='D')
                current_price = current_data.get('最新价', 100)
                
                # 生成模拟的价格数据（基于当前价格的小幅波动）
                import numpy as np
                np.random.seed(42)  # 固定种子确保结果一致
                returns = np.random.normal(0, 0.02, 30)  # 2%标准差的正态分布
                prices = [current_price]
                for ret in returns[:-1]:
                    prices.append(prices[-1] * (1 + ret))
                prices.reverse()
                
                df = pd.DataFrame({
                    '日期': dates,
                    '开盘': [p * 0.99 for p in prices],
                    '收盘': prices,
                    '最高': [p * 1.02 for p in prices],
                    '最低': [p * 0.98 for p in prices],
                    '成交量': [current_data.get('成交量', 1000000)] * 30,
                    '成交额': [current_data.get('成交额', 100000000)] * 30,
                })
                return df
        except Exception as e:
            logger.error(f"生成模拟历史数据失败: {e}")
        
        return pd.DataFrame()
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        return self.get_stock_realtime(stock_code)
    
    def get_all_stocks_realtime(self) -> pd.DataFrame:
        """获取所有股票实时数据（新浪不支持批量，返回空）"""
        logger.warning("新浪数据源不支持批量获取所有股票")
        return pd.DataFrame()
    
    def get_all_indices_realtime(self) -> pd.DataFrame:
        """获取所有指数实时数据（新浪不支持批量，返回空）"""
        logger.warning("新浪数据源不支持批量获取所有指数")
        return pd.DataFrame()