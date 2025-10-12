"""
本地数据缓存管理器 - 使用SQLite数据库存储历史数据
支持股票和指数的历史数据缓存，优先从本地读取，缺失数据从网络获取
"""

import sqlite3
import pandas as pd
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class DataCacheManager:
    """数据缓存管理器"""
    
    def __init__(self, cache_dir: str = "datacache"):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # 数据库文件路径
        self.db_path = self.cache_dir / "stock_data.db"
        
        # 初始化数据库
        self._init_database()
        
        logger.info(f"📦 数据缓存管理器初始化完成，缓存目录: {self.cache_dir}")
    
    def _init_database(self):
        """初始化SQLite数据库和表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建股票历史数据表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stock_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code TEXT NOT NULL,
                        date TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        amount REAL,
                        turnover REAL,
                        pct_change REAL,
                        adjust_type TEXT DEFAULT 'qfq',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(stock_code, date, adjust_type)
                    )
                ''')
                
                # 创建指数历史数据表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS index_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        index_code TEXT NOT NULL,
                        date TEXT NOT NULL,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume INTEGER,
                        amount REAL,
                        pct_change REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(index_code, date)
                    )
                ''')
                
                # 创建数据更新记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS data_updates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        symbol_type TEXT NOT NULL,  -- 'stock' or 'index'
                        last_update_date TEXT NOT NULL,
                        last_update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        data_count INTEGER DEFAULT 0,
                        UNIQUE(symbol, symbol_type)
                    )
                ''')
                
                # 创建索引以提高查询性能
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_code_date ON stock_history(stock_code, date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_index_code_date ON index_history(index_code, date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol_type ON data_updates(symbol, symbol_type)')
                
                conn.commit()
                logger.info("✅ 数据库表结构初始化完成")
                
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise
    
    def get_cached_stock_data(self, stock_code: str, start_date: str, end_date: str, 
                             adjust: str = 'qfq') -> Optional[pd.DataFrame]:
        """
        从缓存获取股票历史数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            adjust: 复权类型
            
        Returns:
            缓存的数据DataFrame或None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = '''
                    SELECT date, open, high, low, close, volume, amount, 
                           turnover, pct_change
                    FROM stock_history 
                    WHERE stock_code = ? AND date >= ? AND date <= ? AND adjust_type = ?
                    ORDER BY date
                '''
                
                df = pd.read_sql_query(query, conn, params=(stock_code, start_date, end_date, adjust))
                
                if df.empty:
                    return None
                
                # 设置日期为索引
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                logger.debug(f"📋 从缓存获取股票数据: {stock_code}, {len(df)}条记录")
                return df
                
        except Exception as e:
            logger.error(f"❌ 获取缓存股票数据失败: {e}")
            return None
    
    def get_cached_index_data(self, index_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        从缓存获取指数历史数据
        
        Args:
            index_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            缓存的数据DataFrame或None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = '''
                    SELECT date, open, high, low, close, volume, amount, pct_change
                    FROM index_history 
                    WHERE index_code = ? AND date >= ? AND date <= ?
                    ORDER BY date
                '''
                
                df = pd.read_sql_query(query, conn, params=(index_code, start_date, end_date))
                
                if df.empty:
                    return None
                
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                logger.debug(f"📋 从缓存获取指数数据: {index_code}, {len(df)}条记录")
                return df
                
        except Exception as e:
            logger.error(f"❌ 获取缓存指数数据失败: {e}")
            return None
    
    def save_stock_data(self, stock_code: str, data: pd.DataFrame, adjust: str = 'qfq'):
        """
        保存股票历史数据到缓存
        
        Args:
            stock_code: 股票代码
            data: 股票数据DataFrame
            adjust: 复权类型
        """
        if data.empty:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 准备数据
                data_to_save = data.copy()
                
                # 处理不同的date列名称
                date_columns = ['date', '日期', 'Date', 'DATE']
                date_col = None
                for col in date_columns:
                    if col in data_to_save.columns:
                        date_col = col
                        break
                
                # 如果没有找到日期列，检查索引
                if date_col is None:
                    if data_to_save.index.name in date_columns or isinstance(data_to_save.index, pd.DatetimeIndex):
                        data_to_save = data_to_save.reset_index()
                        date_col = data_to_save.columns[0]  # 假设第一列是日期
                
                # 确保有日期列
                if date_col is None:
                    logger.error(f"无法找到日期列: {list(data_to_save.columns)}")
                    return
                
                # 统一日期列名为date
                if date_col != 'date':
                    data_to_save = data_to_save.rename(columns={date_col: 'date'})
                
                # 确保日期格式正确
                data_to_save['date'] = pd.to_datetime(data_to_save['date']).dt.strftime('%Y-%m-%d')
                
                # 处理列名映射（支持中文列名）
                column_mapping = {
                    '开盘': 'open',
                    '收盘': 'close', 
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '换手率': 'turnover',
                    '涨跌幅': 'pct_change'
                }
                
                # 应用列名映射
                for old_name, new_name in column_mapping.items():
                    if old_name in data_to_save.columns:
                        data_to_save = data_to_save.rename(columns={old_name: new_name})
                
                # 批量插入数据（使用REPLACE避免重复）
                for _, row in data_to_save.iterrows():
                    cursor.execute('''
                        REPLACE INTO stock_history 
                        (stock_code, date, open, high, low, close, volume, amount, 
                         turnover, pct_change, adjust_type, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        stock_code,
                        row.get('date'),
                        float(row.get('open', 0)) if pd.notna(row.get('open')) else None,
                        float(row.get('high', 0)) if pd.notna(row.get('high')) else None,
                        float(row.get('low', 0)) if pd.notna(row.get('low')) else None,
                        float(row.get('close', 0)) if pd.notna(row.get('close')) else None,
                        int(float(row.get('volume', 0))) if pd.notna(row.get('volume')) else None,
                        float(row.get('amount', 0)) if pd.notna(row.get('amount')) else None,
                        float(row.get('turnover', 0)) if pd.notna(row.get('turnover')) else None,
                        float(row.get('pct_change', 0)) if pd.notna(row.get('pct_change')) else None,
                        adjust
                    ))
                
                # 更新数据更新记录
                last_date = data_to_save['date'].max()
                cursor.execute('''
                    REPLACE INTO data_updates 
                    (symbol, symbol_type, last_update_date, last_update_time, data_count)
                    VALUES (?, 'stock', ?, CURRENT_TIMESTAMP, ?)
                ''', (stock_code, last_date, len(data_to_save)))
                
                conn.commit()
                logger.info(f"💾 保存股票数据到缓存: {stock_code}, {len(data_to_save)}条记录")
                
        except Exception as e:
            logger.error(f"❌ 保存股票数据失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def save_index_data(self, index_code: str, data: pd.DataFrame):
        """
        保存指数历史数据到缓存
        
        Args:
            index_code: 指数代码
            data: 指数数据DataFrame
        """
        if data.empty:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                data_to_save = data.copy()
                
                # 处理不同的date列名称
                date_columns = ['date', '日期', 'Date', 'DATE']
                date_col = None
                for col in date_columns:
                    if col in data_to_save.columns:
                        date_col = col
                        break
                
                # 如果没有找到日期列，检查索引
                if date_col is None:
                    if data_to_save.index.name in date_columns or isinstance(data_to_save.index, pd.DatetimeIndex):
                        data_to_save = data_to_save.reset_index()
                        date_col = data_to_save.columns[0]
                
                # 确保有日期列
                if date_col is None:
                    logger.error(f"无法找到日期列: {list(data_to_save.columns)}")
                    return
                
                # 统一日期列名为date
                if date_col != 'date':
                    data_to_save = data_to_save.rename(columns={date_col: 'date'})
                
                # 确保日期格式正确
                data_to_save['date'] = pd.to_datetime(data_to_save['date']).dt.strftime('%Y-%m-%d')
                
                # 处理列名映射
                column_mapping = {
                    '开盘': 'open',
                    '收盘': 'close', 
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '涨跌幅': 'pct_change'
                }
                
                # 应用列名映射
                for old_name, new_name in column_mapping.items():
                    if old_name in data_to_save.columns:
                        data_to_save = data_to_save.rename(columns={old_name: new_name})
                
                for _, row in data_to_save.iterrows():
                    cursor.execute('''
                        REPLACE INTO index_history 
                        (index_code, date, open, high, low, close, volume, amount, 
                         pct_change, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        index_code,
                        row.get('date'),
                        float(row.get('open', 0)) if pd.notna(row.get('open')) else None,
                        float(row.get('high', 0)) if pd.notna(row.get('high')) else None,
                        float(row.get('low', 0)) if pd.notna(row.get('low')) else None,
                        float(row.get('close', 0)) if pd.notna(row.get('close')) else None,
                        int(float(row.get('volume', 0))) if pd.notna(row.get('volume')) else None,
                        float(row.get('amount', 0)) if pd.notna(row.get('amount')) else None,
                        float(row.get('pct_change', 0)) if pd.notna(row.get('pct_change')) else None
                    ))
                
                last_date = data_to_save['date'].max()
                cursor.execute('''
                    REPLACE INTO data_updates 
                    (symbol, symbol_type, last_update_date, last_update_time, data_count)
                    VALUES (?, 'index', ?, CURRENT_TIMESTAMP, ?)
                ''', (index_code, last_date, len(data_to_save)))
                
                conn.commit()
                logger.info(f"💾 保存指数数据到缓存: {index_code}, {len(data_to_save)}条记录")
                
        except Exception as e:
            logger.error(f"❌ 保存指数数据失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def get_data_coverage(self, symbol: str, symbol_type: str = 'stock') -> Optional[Dict]:
        """
        获取符号的数据覆盖情况
        
        Args:
            symbol: 股票或指数代码
            symbol_type: 'stock' 或 'index'
            
        Returns:
            包含数据范围信息的字典
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if symbol_type == 'stock':
                    query = '''
                        SELECT MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as count
                        FROM stock_history WHERE stock_code = ?
                    '''
                else:
                    query = '''
                        SELECT MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as count
                        FROM index_history WHERE index_code = ?
                    '''
                
                cursor = conn.cursor()
                cursor.execute(query, (symbol,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    return {
                        'start_date': result[0],
                        'end_date': result[1],
                        'count': result[2]
                    }
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取数据覆盖情况失败: {e}")
            return None
    
    def get_missing_date_ranges(self, symbol: str, start_date: str, end_date: str, 
                               symbol_type: str = 'stock') -> List[Tuple[str, str]]:
        """
        获取指定日期范围内缺失的数据区间
        
        Args:
            symbol: 符号代码
            start_date: 查询开始日期
            end_date: 查询结束日期
            symbol_type: 符号类型
            
        Returns:
            缺失的日期区间列表 [(start, end), ...]
        """
        try:
            # 获取已有的数据日期
            with sqlite3.connect(self.db_path) as conn:
                if symbol_type == 'stock':
                    query = 'SELECT DISTINCT date FROM stock_history WHERE stock_code = ? AND date >= ? AND date <= ? ORDER BY date'
                else:
                    query = 'SELECT DISTINCT date FROM index_history WHERE index_code = ? AND date >= ? AND date <= ? ORDER BY date'
                
                df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
            
            if df.empty:
                return [(start_date, end_date)]
            
            # 生成完整的日期范围（工作日）
            full_dates = pd.bdate_range(start=start_date, end=end_date)
            existing_dates = pd.to_datetime(df['date'])
            
            # 找出缺失的日期
            missing_dates = full_dates.difference(existing_dates)
            
            if len(missing_dates) == 0:
                return []
            
            # 将连续的缺失日期合并为区间
            missing_ranges = []
            if len(missing_dates) > 0:
                missing_dates = sorted(missing_dates)
                range_start = missing_dates[0]
                range_end = missing_dates[0]
                
                for date in missing_dates[1:]:
                    # 确保日期类型一致，转换为 Timestamp 进行比较
                    date_ts = pd.Timestamp(date)
                    range_end_ts = pd.Timestamp(range_end)
                    if (date_ts - range_end_ts).days <= 3:  # 允许3天的间隔（考虑周末）
                        range_end = date
                    else:
                        missing_ranges.append((range_start.strftime('%Y-%m-%d'), range_end.strftime('%Y-%m-%d')))
                        range_start = date
                        range_end = date
                
                missing_ranges.append((range_start.strftime('%Y-%m-%d'), range_end.strftime('%Y-%m-%d')))
            
            return missing_ranges
            
        except Exception as e:
            logger.error(f"❌ 获取缺失日期区间失败: {e}")
            return [(start_date, end_date)]
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 统计股票数据
                cursor.execute('SELECT COUNT(DISTINCT stock_code) FROM stock_history')
                stock_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM stock_history')
                stock_records = cursor.fetchone()[0]
                
                # 统计指数数据
                cursor.execute('SELECT COUNT(DISTINCT index_code) FROM index_history')
                index_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM index_history')
                index_records = cursor.fetchone()[0]
                
                # 数据库大小
                db_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
                
                return {
                    'stock_symbols': stock_count,
                    'stock_records': stock_records,
                    'index_symbols': index_count,
                    'index_records': index_records,
                    'db_size_mb': round(db_size, 2),
                    'db_path': str(self.db_path)
                }
                
        except Exception as e:
            logger.error(f"❌ 获取缓存统计失败: {e}")
            return {}
    
    def clear_cache(self, symbol: Optional[str] = None, symbol_type: Optional[str] = None):
        """
        清空缓存数据
        
        Args:
            symbol: 可选，指定符号
            symbol_type: 可选，符号类型 'stock' 或 'index'
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if symbol and symbol_type:
                    if symbol_type == 'stock':
                        cursor.execute('DELETE FROM stock_history WHERE stock_code = ?', (symbol,))
                        cursor.execute('DELETE FROM data_updates WHERE symbol = ? AND symbol_type = ?', (symbol, 'stock'))
                    else:
                        cursor.execute('DELETE FROM index_history WHERE index_code = ?', (symbol,))
                        cursor.execute('DELETE FROM data_updates WHERE symbol = ? AND symbol_type = ?', (symbol, 'index'))
                    logger.info(f"🗑️ 清空缓存: {symbol_type} {symbol}")
                else:
                    cursor.execute('DELETE FROM stock_history')
                    cursor.execute('DELETE FROM index_history')
                    cursor.execute('DELETE FROM data_updates')
                    logger.info("🗑️ 清空所有缓存数据")
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ 清空缓存失败: {e}")