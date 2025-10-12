"""
AKShare数据源实现（多接口自动切换 + 稳定性增强）
优先使用 AKShare 官方接口；当 AKShare 不可用时，回退到备用源。

主要改动点：
1) 新增 _quick_test_connection() 以配合工厂健康检查；
2) stock_zh_index_spot_em 显式传入 symbol 并拼接多个板块，符合官方签名；
3) 东财接口加入退避重试 & 轻量校验，降低被风控的失败率；
4) 历史接口字段与索引标准化，统一成交额为“元”。
"""

import os
import akshare as ak
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
import re
from .base import DataSource
from src.utils.safe_cast import safe_float, safe_int, safe_str

# 配置日志
logger = logging.getLogger(__name__)

# ==== 新增：明确单位配置 ====
# Eastmoney 个股成交额：万元；指数成交额：亿元（若将来变更，只需改这里）
AMOUNT_UNIT_STOCK = "wan"  # "wan" 表示万元
AMOUNT_UNIT_INDEX = "yi"   # "yi"  表示亿元

# ==== 新增：多数据源配置 ====
class DataSourceType:
    """数据源类型枚举"""
    EASTMONEY = "eastmoney"      # 东方财富（主要）
    SINA = "sina"                # 新浪财经（备用1）
    SINA_WEB = "sina_web"        # 新浪网页抓取（备用2）
    TENCENT = "tencent"          # 腾讯财经（备用3）

# 数据源优先级（按可靠性和速度排序）
DATA_SOURCE_PRIORITY = [
    DataSourceType.EASTMONEY,
    DataSourceType.SINA,
    DataSourceType.SINA_WEB,
    DataSourceType.TENCENT,
]

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
    """AKShare数据源（多接口自动切换版本）"""
    
    def __init__(self):
        super().__init__()
        self._stock_spot_cache = None
        self._index_spot_cache = None
        self._cache_time = None
        self._last_error_time = None
        self._current_source = DataSourceType.EASTMONEY  # 当前使用的数据源
        self._source_status = {}  # 各数据源状态记录
        self._setup_session()
        self._init_source_status()
        # 兼容工厂初始化健康检查（见 monitor.log）
        # 若工厂调用 _quick_test_connection，不再报属性缺失
        try:
            _ = self._quick_test_connection()
        except Exception:
            # 不抛出，避免初始化失败；实际切换时会再次健康检查
            pass

    # -------- 新增：工厂健康检查所需的快速连通性测试 --------
    def _quick_test_connection(self) -> bool:
        """
        轻量自检：
        - 索引：取“沪深重要指数”一组；
        - 个股：尝试拉取 A 股快照；
        仅检查是否有非空数据，避免重负载。
        """
        try:
            idx = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
            if idx is None or idx.empty:
                return False
        except Exception:
            return False
        try:
            spot = ak.stock_zh_a_spot_em()
            if spot is None or spot.empty:
                return False
        except Exception:
            return False
        return True
    
    def _init_source_status(self):
        """初始化数据源状态"""
        for source in DATA_SOURCE_PRIORITY:
            self._source_status[source] = {
                'available': True,
                'last_error': None,
                'error_count': 0,
                'last_success': None,
                'consecutive_failures': 0
            }
    
    def _setup_session(self):
        """配置增强的网络会话"""
        # 创建自定义session以改善连接稳定性
        self.session = requests.Session()
        
        # 设置更真实的User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,  # 总重试次数
            backoff_factor=1,  # 退避因子
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的状态码
            allowed_methods=["HEAD", "GET", "OPTIONS"]  # 允许重试的方法
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 设置超时
        self.session.timeout = (10, 30)  # (连接超时, 读取超时)
        
        # 尝试配置akshare使用我们的session
        try:
            # 某些版本的akshare支持session配置
            if hasattr(ak, 'session'):
                ak.session = self.session
        except:
            pass
    
    def _test_source_connection(self, source_type: str) -> bool:
        """测试特定数据源的连接状态"""
        try:
            if source_type == DataSourceType.EASTMONEY:
                # 测试东方财富接口
                test_df = ak.stock_zh_a_spot_em()
                return test_df is not None and len(test_df) > 0
            
            elif source_type == DataSourceType.SINA:
                # 测试新浪财经接口
                test_df = ak.stock_zh_a_spot()
                return test_df is not None and len(test_df) > 0
            
            elif source_type == DataSourceType.SINA_WEB:
                # 测试新浪网页抓取
                response = self.session.get(
                    "https://vip.stock.finance.sina.com.cn/mkt/#hs_a",
                    timeout=5
                )
                return response.status_code == 200
            
            elif source_type == DataSourceType.TENCENT:
                # 测试腾讯财经接口（通过网页API）
                response = self.session.get(
                    "http://qt.gtimg.cn/q=sh000001",
                    timeout=5
                )
                return response.status_code == 200 and len(response.text) > 10
            
            return False
        except Exception as e:
            logger.debug(f"测试数据源 {source_type} 失败: {e}")
            return False
    
    def _mark_source_status(self, source_type: str, success: bool, error_msg: str = None):
        """标记数据源状态"""
        now = datetime.now()
        status = self._source_status.get(source_type, {})
        
        if success:
            status['available'] = True
            status['last_success'] = now
            status['consecutive_failures'] = 0
            status['last_error'] = None
        else:
            status['error_count'] = status.get('error_count', 0) + 1
            status['consecutive_failures'] = status.get('consecutive_failures', 0) + 1
            status['last_error'] = error_msg
            
            # 连续失败3次以上暂时标记为不可用
            if status['consecutive_failures'] >= 3:
                status['available'] = False
                logger.warning(f"数据源 {source_type} 连续失败3次，暂时标记为不可用")
        
        self._source_status[source_type] = status
    
    def _get_next_available_source(self) -> Optional[str]:
        """获取下一个可用的数据源"""
        # 检查当前源是否仍然可用
        current_status = self._source_status.get(self._current_source, {})
        if current_status.get('available', True):
            # 当前源可用且最近没有失败，继续使用
            if current_status.get('consecutive_failures', 0) == 0:
                return self._current_source
        
        # 按优先级查找可用数据源
        for source in DATA_SOURCE_PRIORITY:
            status = self._source_status.get(source, {})
            if status.get('available', True):
                # 检查是否需要重新测试
                last_error = status.get('last_error')
                if last_error:
                    time_since_error = (datetime.now() - status.get('last_error_time', datetime.now())).total_seconds()
                    if time_since_error > 300:  # 5分钟后重新尝试
                        status['available'] = True
                        status['consecutive_failures'] = 0
                
                if status.get('available', True):
                    if source != self._current_source:
                        logger.info(f"切换数据源: {self._current_source} -> {source}")
                        self._current_source = source
                    return source
        
        # 所有源都不可用，重置状态并使用默认源
        logger.warning("所有数据源都不可用，重置状态并使用东方财富")
        self._init_source_status()
        self._current_source = DataSourceType.EASTMONEY
        return DataSourceType.EASTMONEY
    
    def _fetch_stock_data_eastmoney(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """从东方财富获取数据（带退避重试 & 显式参数）"""
        # 指数接口需要显式 symbol；官方文档提供多个板块，合并以覆盖常见指数
        # 参考：AKShare 文档 - stock_zh_index_spot_em（symbol 取值）
        # https://akshare.akfamily.xyz/data/index/index.html
        index_symbol_groups = [
            "沪深重要指数", "上证系列指数", "深证系列指数", "中证系列指数"
        ]

        last_err = None
        for attempt in range(3):
            try:
                # --- A股个股快照 ---
                logger.debug("正在从东方财富获取股票实时数据...")
                stock_df = ak.stock_zh_a_spot_em()
                if stock_df is None or stock_df.empty or len(stock_df) < 100:
                    raise ValueError("东财个股快照为空或数量异常")

                # --- 指数快照（按组拼接） ---
                logger.debug("正在从东方财富获取指数实时数据(多组)...")
                idx_list = []
                for sym in index_symbol_groups:
                    try:
                        # 控制请求速率，避免触发风控（参考社区 issue）
                        time.sleep(0.2)
                        _df = ak.stock_zh_index_spot_em(symbol=sym)
                        if _df is not None and not _df.empty:
                            idx_list.append(_df)
                    except Exception as ie:
                        logger.debug(f"指数分组 {sym} 获取失败: {ie}")
                        continue
                index_df = pd.concat(idx_list, ignore_index=True) if idx_list else pd.DataFrame()
                if index_df.empty or len(index_df) < 5:
                    raise ValueError("东财指数快照为空或数量异常")

                # 通过基本质量校验返回
                return stock_df, index_df

            except Exception as e:
                last_err = e
                # 退避重试（指数接口近期有验证码风控，放缓节奏）
                backoff = 1.0 + attempt * 1.0 + random.uniform(0.0, 0.5)
                logger.warning(f"东方财富数据获取失败，第{attempt+1}次重试将在 {backoff:.1f}s 后进行：{e}")
                time.sleep(backoff)
                continue

        # 最终失败
        logger.warning(f"东方财富数据获取最终失败：{last_err}")
        raise last_err
    
    def _fetch_stock_data_sina(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """从新浪财经获取数据（增强重试机制）"""
        try:
            logger.debug("正在从新浪财经获取股票实时数据...")
            
            # 新浪财经有时会返回HTML而不是数据，增加重试机制
            for attempt in range(3):
                try:
                    # 添加延迟避免被识别为爬虫
                    if attempt > 0:
                        delay = 1 + random.uniform(0.5, 1.5)
                        logger.debug(f"新浪重试第{attempt+1}次，等待{delay:.1f}秒...")
                        time.sleep(delay)
                    
                    stock_df = ak.stock_zh_a_spot()
                    
                    # 验证数据是否有效
                    if stock_df is not None and not stock_df.empty and len(stock_df) > 100:
                        break
                    else:
                        logger.warning(f"新浪股票数据异常，尝试{attempt+1}次")
                        if attempt == 2:  # 最后一次尝试
                            raise ValueError("新浪股票数据验证失败")
                        
                except Exception as e:
                    if attempt == 2:  # 最后一次尝试
                        raise e
                    logger.debug(f"新浪股票数据获取失败，尝试{attempt+1}次: {e}")
                    continue
            
            time.sleep(0.5)  # 增加间隔时间
            
            logger.debug("正在从新浪财经获取指数实时数据...")
            # 对指数数据也使用重试机制
            index_df = None
            for attempt in range(3):
                try:
                    if attempt > 0:
                        delay = 1 + random.uniform(0.5, 1.5)
                        time.sleep(delay)
                    
                    # 尝试获取指数数据
                    try:
                        index_df = ak.stock_zh_index_spot()
                        if index_df is not None and not index_df.empty:
                            break
                    except:
                        # 如果指数接口失败，使用备用方案
                        logger.debug("新浪指数接口失败，使用备用指数数据")
                        index_df = self._get_basic_index_data_sina()
                        if index_df is not None and not index_df.empty:
                            break
                        
                    if attempt == 2:
                        # 最后的备用方案：创建空的指数数据框架
                        logger.warning("无法获取指数数据，使用空数据框架")
                        index_df = self._create_empty_index_dataframe()
                        
                except Exception as e:
                    if attempt == 2:
                        logger.warning(f"指数数据获取最终失败: {e}")
                        index_df = self._create_empty_index_dataframe()
                        break
                    continue
            
            return self._normalize_sina_data(stock_df), index_df
            
        except Exception as e:
            logger.warning(f"新浪财经数据获取失败: {e}")
            raise e
    
    def _fetch_stock_data_sina_web(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """从新浪网页抓取数据"""
        try:
            logger.debug("正在从新浪网页抓取数据...")
            
            # 网页抓取实现相对复杂，这里先提供基础框架
            # 实际实现需要解析HTML和JavaScript
            stock_df = self._scrape_sina_web_stocks()
            index_df = self._scrape_sina_web_indices()
            
            return stock_df, index_df
        except Exception as e:
            logger.warning(f"新浪网页抓取失败: {e}")
            raise e
    
    def _normalize_sina_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化新浪财经数据格式"""
        if df is None or df.empty:
            return df
        
        # 新浪财经的列名可能不同，需要映射
        column_mapping = {
            '代码': '代码',
            '名称': '名称', 
            '最新价': '最新价',
            '涨跌额': '涨跌额',
            '涨跌幅': '涨跌幅',
            '今开': '今开',
            '最高': '最高',
            '最低': '最低',
            '昨收': '昨收',
            '成交量': '成交量',
            '成交额': '成交额',
            '换手率': '换手率',
        }
        
        # 重命名列（如果需要）
        normalized_df = df.copy()
        
        # 新浪财经成交额单位是元，无需转换
        return normalized_df
    
    def _get_basic_index_data_sina(self) -> pd.DataFrame:
        """获取基础指数数据（新浪备用）"""
        try:
            # 使用新浪的简单API获取基本指数
            basic_indices = [
                ('sh000001', '上证指数'),
                ('sh000002', 'A股指数'), 
                ('sh000003', 'B股指数'),
                ('sz399001', '深证成指'),
                ('sz399006', '创业板指'),
                ('sz399005', '中小100'),
                ('sz399002', '深成指R'),
                ('sz399004', '深证100R'),
            ]
            
            data = []
            for sina_code, name in basic_indices:
                try:
                    # 使用新浪的简单查询API
                    url = f"http://hq.sinajs.cn/list={sina_code}"
                    response = self.session.get(url, timeout=5)
                    
                    if response.status_code == 200 and response.text:
                        # 解析新浪数据格式：var hq_str_sh000001="上证指数,2968.26,2969.10,..."
                        content = response.text.strip()
                        if 'hq_str_' in content and '=' in content:
                            data_part = content.split('="')[1].split('";')[0]
                            fields = data_part.split(',')
                            
                            if len(fields) >= 10:
                                index_data = {
                                    '代码': sina_code[2:],  # 去掉sh/sz前缀
                                    '名称': fields[0],
                                    '最新价': safe_float(fields[3]),
                                    '昨收': safe_float(fields[2]),
                                    '今开': safe_float(fields[1]),
                                    '最高': safe_float(fields[4]),
                                    '最低': safe_float(fields[5]),
                                    '成交量': safe_int(fields[8]),
                                    '成交额': safe_float(fields[9]),
                                }
                                
                                # 计算涨跌额和涨跌幅
                                current_price = index_data['最新价']
                                prev_close = index_data['昨收']
                                if current_price and prev_close and prev_close > 0:
                                    change = current_price - prev_close
                                    change_pct = (change / prev_close) * 100
                                    index_data['涨跌额'] = change
                                    index_data['涨跌幅'] = change_pct
                                    index_data['振幅'] = 0.0  # 新浪简单API没有振幅数据
                                else:
                                    index_data['涨跌额'] = 0.0
                                    index_data['涨跌幅'] = 0.0
                                    index_data['振幅'] = 0.0
                                
                                data.append(index_data)
                                logger.debug(f"获取指数 {name} 数据成功: {current_price}")
                            
                except Exception as e:
                    logger.debug(f"获取指数 {name} 失败: {e}")
                    continue
            
            df = pd.DataFrame(data) if data else pd.DataFrame()
            logger.info(f"新浪简单API获取到 {len(df)} 个指数数据")
            return df
            
        except Exception as e:
            logger.warning(f"获取基础指数数据失败: {e}")
            return pd.DataFrame()
    
    def _create_empty_index_dataframe(self) -> pd.DataFrame:
        """创建空的指数数据框架"""
        columns = ['代码', '名称', '最新价', '涨跌额', '涨跌幅', '今开', '最高', '最低', '昨收', '成交量', '成交额', '振幅']
        return pd.DataFrame(columns=columns)
    
    def _fetch_stock_data_sina_web(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """从新浪网页抓取数据（简化版）"""
        try:
            logger.debug("正在从新浪网页抓取数据...")
            
            # 使用新浪的移动端API，更轻量级
            stock_df = self._scrape_sina_mobile_stocks()
            index_df = self._scrape_sina_mobile_indices()
            
            return stock_df, index_df
        except Exception as e:
            logger.warning(f"新浪网页抓取失败: {e}")
            raise e
    
    def _scrape_sina_mobile_stocks(self) -> pd.DataFrame:
        """使用新浪移动端API获取股票数据"""
        try:
            # 新浪移动端API获取热门股票
            popular_stocks = [
                'sh600519', 'sz000002', 'sz300750', 'sh600036', 'sh601318',
                'sz000001', 'sh600000', 'sh601166', 'sz002594', 'sh600276',
                'sz000858', 'sh601888', 'sh600009', 'sz002415', 'sh600887'
            ]
            
            data = []
            
            # 批量查询热门股票
            for i in range(0, len(popular_stocks), 5):  # 每次查询5个
                batch = popular_stocks[i:i+5]
                batch_codes = ','.join(batch)
                
                try:
                    url = f"http://hq.sinajs.cn/list={batch_codes}"
                    response = self.session.get(url, timeout=5)
                    
                    if response.status_code == 200:
                        lines = response.text.strip().split('\n')
                        for line in lines:
                            if 'hq_str_' in line and '=' in line:
                                stock_data = self._parse_sina_stock_line(line)
                                if stock_data:
                                    data.append(stock_data)
                    
                    time.sleep(0.2)  # 避免请求过快
                    
                except Exception as e:
                    logger.debug(f"获取股票批次失败: {e}")
                    continue
            
            df = pd.DataFrame(data) if data else pd.DataFrame()
            logger.info(f"新浪移动端API获取到 {len(df)} 只股票数据")
            return df
            
        except Exception as e:
            logger.warning(f"新浪移动端股票抓取失败: {e}")
            return pd.DataFrame()
    
    def _scrape_sina_mobile_indices(self) -> pd.DataFrame:
        """使用新浪移动端API获取指数数据"""
        try:
            # 重用已有的指数获取逻辑
            return self._get_basic_index_data_sina()
        except Exception as e:
            logger.warning(f"新浪移动端指数抓取失败: {e}")
            return pd.DataFrame()
    
    def _parse_sina_stock_line(self, line: str) -> Optional[Dict]:
        """解析新浪股票数据行"""
        try:
            # 解析格式：var hq_str_sh600519="贵州茅台,1663.36,1662.00,..."
            if 'hq_str_' not in line or '=' not in line:
                return None
            
            # 提取股票代码
            code_part = line.split('hq_str_')[1].split('=')[0]
            stock_code = code_part[2:]  # 去掉sh/sz前缀
            
            # 提取数据部分
            data_part = line.split('="')[1].split('";')[0]
            fields = data_part.split(',')
            
            if len(fields) < 32:  # 新浪股票数据有32个字段
                return None
            
            stock_data = {
                '代码': stock_code,
                '名称': fields[0],
                '今开': safe_float(fields[1]),
                '昨收': safe_float(fields[2]),
                '最新价': safe_float(fields[3]),
                '最高': safe_float(fields[4]),
                '最低': safe_float(fields[5]),
                '成交量': safe_int(fields[8]),  # 股
                '成交额': safe_float(fields[9]),  # 元
            }
            
            # 计算涨跌额和涨跌幅
            current_price = stock_data['最新价']
            prev_close = stock_data['昨收']
            if current_price and prev_close and prev_close > 0:
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                stock_data['涨跌额'] = change
                stock_data['涨跌幅'] = change_pct
                
                # 计算振幅
                high = stock_data['最高']
                low = stock_data['最低']
                if high and low and prev_close > 0:
                    amplitude = ((high - low) / prev_close) * 100
                    stock_data['振幅'] = amplitude
                else:
                    stock_data['振幅'] = 0.0
                    
                # 计算换手率（简化版，实际需要流通股本数据）
                stock_data['换手率'] = 0.0  # 新浪简单API无法直接获取
            else:
                stock_data['涨跌额'] = 0.0
                stock_data['涨跌幅'] = 0.0
                stock_data['振幅'] = 0.0
                stock_data['换手率'] = 0.0
            
            return stock_data
            
        except Exception as e:
            logger.debug(f"解析股票数据行失败: {e}")
            return None
    def _refresh_spot_cache(self):
        """刷新实时数据缓存（多数据源自动切换版本）"""
        now = datetime.now()
        
        # 计算缓存年龄
        cache_age = 0 if self._cache_time is None else (now - self._cache_time).total_seconds()
        
        if (self._cache_time is None or cache_age > self.cache_expire):
            success = False
            last_error = None
            
            # 尝试所有可用的数据源
            for attempt in range(len(DATA_SOURCE_PRIORITY)):
                current_source = self._get_next_available_source()
                if not current_source:
                    break
                
                try:
                    logger.info(f"尝试使用数据源: {current_source}")
                    
                    # 根据数据源类型选择获取方法
                    if current_source == DataSourceType.EASTMONEY:
                        stock_df, index_df = self._fetch_stock_data_eastmoney()
                    elif current_source == DataSourceType.SINA:
                        stock_df, index_df = self._fetch_stock_data_sina()
                    elif current_source == DataSourceType.SINA_WEB:
                        stock_df, index_df = self._fetch_stock_data_sina_web()
                    else:
                        # 其他数据源的处理
                        raise NotImplementedError(f"数据源 {current_source} 暂未实现")
                    
                    # 验证数据质量
                    if self._validate_data_quality(stock_df, index_df):
                        self._stock_spot_cache = stock_df
                        self._index_spot_cache = index_df
                        self._cache_time = now
                        self._last_error_time = None
                        self._mark_source_status(current_source, True)
                        
                        logger.info(f"✅ 数据源 {current_source} 获取成功，股票数量: {len(stock_df) if stock_df is not None else 0}")
                        success = True
                        break
                    else:
                        raise ValueError("数据质量验证失败")
                        
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    self._mark_source_status(current_source, False, error_msg)
                    
                    logger.warning(f"❌ 数据源 {current_source} 失败: {error_msg}")
                    
                    # 如果不是最后一次尝试，添加延迟
                    if attempt < len(DATA_SOURCE_PRIORITY) - 1:
                        delay = 1 + random.uniform(0.5, 1.5)  # 1-2.5秒随机延迟
                        logger.info(f"等待 {delay:.1f}秒后尝试下一个数据源...")
                        time.sleep(delay)
            
            # 所有数据源都失败的处理
            if not success and last_error:
                self._handle_all_sources_failed(last_error, cache_age)
    
    def _validate_data_quality(self, stock_df: pd.DataFrame, index_df: pd.DataFrame) -> bool:
        """验证数据质量"""
        try:
            # 检查数据框是否为空
            if stock_df is None or stock_df.empty:
                logger.warning("股票数据为空")
                return False
            
            if index_df is None or index_df.empty:
                logger.warning("指数数据为空")
                return False
            
            # 检查基本列是否存在
            required_stock_columns = ['代码', '名称', '最新价']
            for col in required_stock_columns:
                if col not in stock_df.columns:
                    logger.warning(f"股票数据缺少必要列: {col}")
                    return False
            
            required_index_columns = ['代码', '名称', '最新价']
            for col in required_index_columns:
                if col not in index_df.columns:
                    logger.warning(f"指数数据缺少必要列: {col}")
                    return False
            
            # 检查数据量是否合理
            if len(stock_df) < 100:  # 至少应该有100只股票
                logger.warning(f"股票数据量过少: {len(stock_df)}")
                return False
            
            if len(index_df) < 5:  # 至少应该有5个指数
                logger.warning(f"指数数据量过少: {len(index_df)}")
                return False
            
            return True
        except Exception as e:
            logger.warning(f"数据质量验证出错: {e}")
            return False
    
    def _handle_all_sources_failed(self, last_error: Exception, cache_age: float):
        """处理所有数据源都失败的情况"""
        # 避免重复打印相同错误（60秒内只打印一次）
        should_print = True
        if self._last_error_time:
            time_since_error = (datetime.now() - self._last_error_time).total_seconds()
            should_print = time_since_error > 60
        
        if should_print:
            # 用户可见的友好提示
            error_str = str(last_error)
            print(f"⚠ 所有数据源都无法访问：")
            print(f"  1. 东方财富: 可能被限制访问频率")
            print(f"  2. 新浪财经: 可能网络连接问题")
            print(f"  3. 建议稍后重试或检查网络连接")
            
            if self._cache_time:
                cache_age_min = int(cache_age / 60)
                print(f"  当前使用旧缓存（缓存年龄: {cache_age_min}分钟）")
            else:
                print(f"  暂无可用数据，请检查网络连接")
            
            # 显示各数据源状态
            print(f"  数据源状态:")
            for source, status in self._source_status.items():
                available = "✅" if status.get('available', True) else "❌"
                failures = status.get('consecutive_failures', 0)
                print(f"    {available} {source}: {failures}次连续失败")
            
            # 日志记录
            logger.error(f"所有数据源失败，最后错误: {last_error}")
            
            # 检查缓存是否过期过久
            if cache_age > self.cache_expire * 5:
                logger.error(f"⚠ 缓存已过期 {cache_age:.0f}秒（超过5倍TTL），数据可能已过时")
            
            self._last_error_time = datetime.now()
    
    def get_stock_realtime(self, stock_code: str) -> Optional[Dict]:
        """获取股票实时数据（支持多数据源自动切换）"""
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
            
            # 根据当前数据源决定成交额单位处理
            if self._current_source == DataSourceType.EASTMONEY:
                # 东方财富：个股成交额(万元) -> 元
                amount_wan = safe_float(info.get('成交额'))
                amount_yuan = _to_yuan(amount_wan, AMOUNT_UNIT_STOCK)
            else:
                # 新浪等其他数据源：成交额已经是元
                amount_yuan = safe_float(info.get('成交额'))
            
            return {
                '代码': stock_code,
                '名称': safe_str(info['名称'], stock_code),
                '最新价': safe_float(info['最新价']),
                '涨跌幅': safe_float(info['涨跌幅']),
                '涨跌额': safe_float(info['涨跌额']),
                '成交量': safe_int(info['成交量']),
                '成交额': amount_yuan,  # 统一为"元"
                '振幅': safe_float(info.get('振幅', 0.0)),
                '最高': safe_float(info['最高']),
                '最低': safe_float(info['最低']),
                '今开': safe_float(info['今开']),
                '昨收': safe_float(info['昨收']),
                '换手率': safe_float(info.get('换手率', 0.0)),
                '更新时间': datetime.now().strftime('%H:%M:%S'),
                '数据源': self._current_source,  # 添加数据源标识
            }
        except Exception as e:
            logger.warning(f"获取股票 {stock_code} 实时数据失败: {e}")
            return None
    
    def get_index_realtime(self, index_code: str) -> Optional[Dict]:
        """获取指数实时数据（支持多数据源自动切换）"""
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
            
            # 根据当前数据源决定成交额单位处理
            if self._current_source == DataSourceType.EASTMONEY:
                # 东方财富：指数成交额(亿元) -> 元
                amount_em = safe_float(info.get('成交额'))
                amount_yuan = _to_yuan(amount_em, AMOUNT_UNIT_INDEX)
            else:
                # 新浪等其他数据源：成交额已经是元
                amount_yuan = safe_float(info.get('成交额'))
            
            return {
                '代码': index_code,
                '名称': safe_str(info['名称'], index_code),
                '最新价': safe_float(info['最新价']),
                '涨跌幅': safe_float(info['涨跌幅']),
                '涨跌额': safe_float(info['涨跌额']),
                '成交量': safe_int(info.get('成交量', 0)),
                '成交额': amount_yuan,  # 统一为"元"
                '振幅': safe_float(info.get('振幅', 0.0)),
                '最高': safe_float(info['最高']),
                '最低': safe_float(info['最低']),
                '今开': safe_float(info['今开']),
                '昨收': safe_float(info['昨收']),
                '更新时间': datetime.now().strftime('%H:%M:%S'),
                '数据源': self._current_source,  # 添加数据源标识
            }
        except Exception as e:
            logger.warning(f"获取指数 {index_code} 实时数据失败: {e}")
            return None
    
    def get_stock_history(self, stock_code: str, start_date: str, 
                         end_date: str, adjust: str = 'qfq') -> pd.DataFrame:
        """
        获取股票历史数据（标准化列 & 指数化单位）
        参考官方示例：ak.stock_zh_a_hist(symbol="000001", period="daily", start_date="YYYYMMDD", end_date="YYYYMMDD", adjust="qfq")
        文档：tutorial & data/stock/stock.html
        """
        # 调整合法性
        adjust = adjust if adjust in ('', 'qfq', 'hfq') else 'qfq'

        last_err = None
        for attempt in range(3):
            try:
                # 放缓请求，避免风控
                if attempt > 0:
                    time.sleep(0.5 + random.uniform(0.0, 0.5))
                # 转换日期格式为 YYYYMMDD（AKShare 要求的格式）
                start_date_formatted = start_date.replace('-', '')
                end_date_formatted = end_date.replace('-', '')
                
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=start_date_formatted,
                    end_date=end_date_formatted,
                    adjust=adjust
                )
                if df is None or df.empty:
                    raise ValueError("历史数据为空")

                # 标准化：日期索引、列名、单位
                if '日期' in df.columns:
                    df['日期'] = pd.to_datetime(df['日期'])
                    df = df.sort_values('日期').reset_index(drop=True)
                    df.set_index('日期', inplace=True)  # 修复：应该是 inplace=True
                # 统一成交额为“元”（东财日线返回单位通常为“元”本身，此处兜底处理）
                if '成交额' in df.columns:
                    df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce').fillna(0.0)

                # 保留常用字段（注意：设置索引后不再包含'日期'列）
                keep_cols = ['开盘', '收盘', '最高', '最低', '成交量', '成交额']
                df = df[[c for c in keep_cols if c in df.columns]].copy()
                return df

            except Exception as e:
                last_err = e
                logger.debug(f"获取历史数据失败，第{attempt+1}次尝试：{e}")
                continue

        print(f"获取股票 {stock_code} 历史数据失败: {last_err}")
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
    
    def get_current_source(self) -> str:
        """获取当前使用的数据源"""
        return self._current_source
    
    def get_source_status(self) -> Dict:
        """获取所有数据源状态"""
        return self._source_status.copy()
    
    def force_switch_source(self, source_type: str):
        """强制切换到指定数据源"""
        if source_type in DATA_SOURCE_PRIORITY:
            logger.info(f"强制切换数据源到: {source_type}")
            self._current_source = source_type
            # 清空缓存，强制重新获取
            self._cache_time = None
            self._stock_spot_cache = None
            self._index_spot_cache = None
        else:
            logger.warning(f"不支持的数据源类型: {source_type}")
    
    def reset_source_status(self):
        """重置所有数据源状态"""
        logger.info("重置所有数据源状态")
        self._init_source_status()
        self._current_source = DataSourceType.EASTMONEY
    
    def test_all_sources(self) -> Dict[str, bool]:
        """测试所有数据源的连接状态"""
        results = {}
        logger.info("开始测试所有数据源连接状态...")
        
        for source in DATA_SOURCE_PRIORITY:
            try:
                logger.info(f"测试数据源: {source}")
                result = self._test_source_connection(source)
                results[source] = result
                status_text = "✅ 可用" if result else "❌ 不可用"
                logger.info(f"  {source}: {status_text}")
                
                # 更新状态
                self._mark_source_status(source, result, None if result else "连接测试失败")
                
            except Exception as e:
                results[source] = False
                logger.warning(f"  {source}: ❌ 测试出错 - {e}")
                self._mark_source_status(source, False, str(e))
        
        return results
    
    def get_data_source_info(self) -> Dict:
        """获取数据源详细信息"""
        return {
            'current_source': self._current_source,
            'cache_time': self._cache_time,
            'cache_age_seconds': (datetime.now() - self._cache_time).total_seconds() if self._cache_time else None,
            'source_priority': DATA_SOURCE_PRIORITY,
            'source_status': self._source_status,
            'available_sources': [s for s, status in self._source_status.items() if status.get('available', True)],
        }
    
    # ============= 批量下载和CSV缓存功能 =============
    
    def load_stock_daily_batch(
        self,
        symbols: List[str],
        start: str,
        end: str,
        adjust: str = 'qfq',
        cache_dir: str = './cache',
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        批量下载股票日线数据并缓存到CSV
        
        参数:
            symbols: 股票代码列表（如 ['000001', '600519']）
            start: 开始日期 YYYY-MM-DD
            end: 结束日期 YYYY-MM-DD
            adjust: 复权方式 ('', 'qfq', 'hfq')
            cache_dir: CSV缓存目录
            force_refresh: 是否强制刷新（忽略缓存）
        
        返回:
            {股票代码: DataFrame} 字典
        """
        os.makedirs(cache_dir, exist_ok=True)
        result = {}
        
        logger.info(f"开始批量下载 {len(symbols)} 只股票的历史数据")
        
        for i, symbol in enumerate(symbols, 1):
            try:
                # 构建缓存文件路径
                cache_file = os.path.join(
                    cache_dir,
                    f"{symbol}_{start}_{end}_{adjust}.csv"
                )
                
                # 检查缓存
                if not force_refresh and os.path.exists(cache_file):
                    logger.debug(f"[{i}/{len(symbols)}] {symbol} 从缓存加载")
                    df = pd.read_csv(cache_file, parse_dates=['日期'])
                    result[symbol] = df
                    continue
                
                # 下载数据
                logger.info(f"[{i}/{len(symbols)}] 下载 {symbol}")
                df = self.get_stock_history(symbol, start, end, adjust)
                
                if df is not None and not df.empty:
                    # 标准化列名
                    df = self._standardize_stock_dataframe(df)
                    
                    # 保存到CSV
                    df.to_csv(cache_file, index=False, encoding='utf-8-sig')
                    logger.debug(f"  已保存到 {cache_file}")
                    
                    result[symbol] = df
                else:
                    logger.warning(f"  {symbol} 数据为空")
                
                # 限速：避免被封禁
                if i < len(symbols):
                    time.sleep(0.3 + random.uniform(0, 0.2))
                    
            except Exception as e:
                logger.error(f"[{i}/{len(symbols)}] {symbol} 下载失败: {e}")
                continue
        
        logger.info(f"批量下载完成：成功 {len(result)}/{len(symbols)}")
        return result
    
    def load_index_daily(
        self,
        index_code: str,
        start: str,
        end: str,
        cache_dir: str = './cache',
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        下载指数日线数据并缓存到CSV
        
        参数:
            index_code: 指数代码（如 '000001', '399001'）
            start: 开始日期 YYYY-MM-DD
            end: 结束日期 YYYY-MM-DD
            cache_dir: CSV缓存目录
            force_refresh: 是否强制刷新
        
        返回:
            DataFrame 包含日期、开盘、收盘等字段
        """
        os.makedirs(cache_dir, exist_ok=True)
        
        # 构建缓存文件路径
        cache_file = os.path.join(cache_dir, f"INDEX_{index_code}_{start}_{end}.csv")
        
        # 检查缓存
        if not force_refresh and os.path.exists(cache_file):
            logger.debug(f"指数 {index_code} 从缓存加载")
            return pd.read_csv(cache_file, parse_dates=['日期'])
        
        # 下载数据
        logger.info(f"下载指数 {index_code} 历史数据")
        
        last_err = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(0.5 + random.uniform(0, 0.5))
                
                df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
                
                if df is None or df.empty:
                    raise ValueError("指数数据为空")
                
                # 标准化
                if 'date' in df.columns:
                    df['日期'] = pd.to_datetime(df['date'])
                elif '日期' in df.columns:
                    df['日期'] = pd.to_datetime(df['日期'])
                
                # 过滤日期范围
                df = df[
                    (df['日期'] >= start) &
                    (df['日期'] <= end)
                ].sort_values('日期').reset_index(drop=True)
                
                # 标准化列名
                column_map = {
                    'open': '开盘', 'close': '收盘', 'high': '最高', 'low': '最低',
                    'volume': '成交量', 'amount': '成交额'
                }
                df = df.rename(columns=column_map)
                
                # 保留需要的列
                keep_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额']
                df = df[[c for c in keep_cols if c in df.columns]].copy()
                
                # 保存到CSV
                df.to_csv(cache_file, index=False, encoding='utf-8-sig')
                logger.debug(f"指数数据已保存到 {cache_file}")
                
                return df
                
            except Exception as e:
                last_err = e
                logger.debug(f"下载指数失败，第{attempt+1}次尝试：{e}")
                continue
        
        logger.error(f"指数 {index_code} 下载失败: {last_err}")
        return pd.DataFrame()
    
    def _standardize_stock_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化股票数据框格式，输出统一的列名和类型
        
        输出列: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额
        """
        if df is None or df.empty:
            return df
        
        # 标准化日期
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'])
        elif 'date' in df.columns:
            df['日期'] = pd.to_datetime(df['date'])
        
        # 标准化列名映射
        column_map = {
            'open': '开盘', '开盘': '开盘',
            'close': '收盘', '收盘': '收盘',
            'high': '最高', '最高': '最高',
            'low': '最低', '最低': '最低',
            'volume': '成交量', '成交量': '成交量',
            'amount': '成交额', '成交额': '成交额',
        }
        
        df = df.rename(columns=column_map)
        
        # 数值类型转换
        for col in ['开盘', '收盘', '最高', '最低', '成交量', '成交额']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 填充缺失值
        df = df.fillna(0)
        
        return df
    
    def get_stock_history_simple(self, stock_code: str, start_date: str, end_date: str, adjust: str = 'qfq') -> pd.DataFrame:
        """
        简化的股票历史数据获取方法，直接使用 AKShare
        绕过复杂的多数据源切换逻辑，确保数据获取的稳定性
        """
        try:
            # 转换日期格式为 YYYYMMDD
            start_date_formatted = start_date.replace('-', '')
            end_date_formatted = end_date.replace('-', '')
            
            print(f"正在获取股票 {stock_code} 的历史数据...")
            print(f"日期范围: {start_date} 到 {end_date}")
            
            # 调用 AKShare API
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date_formatted,
                end_date=end_date_formatted,
                adjust=adjust if adjust in ('', 'qfq', 'hfq') else 'qfq'
            )
            
            if df is None or df.empty:
                print("❌ AKShare 返回空数据")
                return pd.DataFrame()
            
            print(f"✅ 成功获取 {len(df)} 条数据")
            
            # 标准化数据格式
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'])
                df.set_index('日期', inplace=True)
            
            # 保留必要的列（使用中文列名）
            required_columns = ['开盘', '最高', '最低', '收盘', '成交量']
            available_columns = [col for col in required_columns if col in df.columns]
            df = df[available_columns].copy()
            
            # 确保数据类型正确
            for col in available_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 填充缺失值
            df = df.ffill().fillna(0)
            
            # 为了兼容简单回测引擎，重新添加 '日期' 列
            df = df.reset_index()
            df['date'] = df['日期']  # 同时添加英文日期列以兼容不同组件
            
            print(f"数据预览:\n{df.head()}")
            return df
            
        except Exception as e:
            print(f"❌ 获取数据失败: {e}")
            logger.error(f"获取股票 {stock_code} 历史数据失败: {e}")
            return pd.DataFrame()
