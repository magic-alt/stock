"""
实时监控器
"""

import os
import time
from datetime import datetime
from typing import Dict, List, Tuple
import sys
import logging
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.data_sources import DataSourceFactory
from src.indicators import TechnicalIndicators
from src.utils.formatters import format_amount, format_change
from src.utils.timebox import get_trading_status, get_trading_hint

# 配置日志
logger = logging.getLogger(__name__)


class StockMonitor:
    """股票实时监控器"""
    
    def __init__(self, watchlist: Dict[str, str], indices: Dict[str, str],
                 data_source: str = 'akshare', refresh_interval: int = 30):
        """
        初始化监控器
        
        Args:
            watchlist: 监控股票字典 {代码: 名称}
            indices: 监控指数字典 {代码: 名称}
            data_source: 数据源类型
            refresh_interval: 刷新间隔（秒）
        """
        self.watchlist = watchlist
        self.indices = indices
        self.refresh_interval = refresh_interval
        self.data_source = DataSourceFactory.create(data_source)
        self._indicator_cache: Dict[str, Tuple[dict, float]] = {}  # code -> (indicators, ts)
        self._indicator_ttl_sec = 60  # 同一轮刷新内不重复计算
        
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_indices(self):
        """显示指数信息"""
        print("\n【主要指数】")
        print("-" * 100)
        
        # 显示交易状态
        status = get_trading_status()
        if status != '交易中':
            print(f"  交易状态: {status}")
        
        has_data = False
        error_count = 0
        
        for code, name in self.indices.items():
            index_data = self.data_source.get_index_realtime(code)
            if index_data and index_data['最新价'] > 0:
                has_data = True
                change_str = format_change(index_data['涨跌幅'])
                volume_str = format_amount(index_data['成交额'])
                print(f"  {name:8s} {index_data['最新价']:8.2f}  {change_str:15s}  "
                      f"成交额: {volume_str}")
            elif not index_data:
                error_count += 1
        
        if not has_data:
            if error_count > 0:
                print(f"\n  ⚠ 网络连接异常，无法获取实时数据")
                print(f"  提示: 检查网络连接或稍后重试")
            else:
                print(f"\n  {get_trading_hint()}")
    
    def display_stocks(self, show_indicators: bool = True, topn: int = 12):
        """
        显示股票信息
        
        Args:
            show_indicators: 是否显示技术指标
            topn: 优先显示的股票数量（按成交额排序）
        """
        print("\n【自选股票】")
        print("-" * 100)
        
        has_data = False
        error_count = 0
        
        rows = []
        for code, name in self.watchlist.items():
            stock_data = self.data_source.get_stock_realtime(code)
            
            if not stock_data:
                error_count += 1
                continue
            
            # 检查是否有有效数据（非交易时间数据全为0）
            if stock_data['最新价'] == 0:
                continue
            
            has_data = True
            rows.append(stock_data)

        # 先按成交额降序，聚焦主线
        rows.sort(key=lambda x: x.get('成交额', 0) or 0, reverse=True)

        for stock_data in rows[:max(1, topn)]:
            change_str = format_change(stock_data.get('涨跌幅', 0.0))
            print(f"\n{stock_data.get('名称', stock_data['代码'])}({stock_data['代码']})")
            print(f"  价格: {stock_data.get('最新价', 0):7.2f}  {change_str:15s}  "
                  f"今开: {stock_data.get('今开', 0):7.2f}  最高: {stock_data.get('最高', 0):7.2f}  "
                  f"最低: {stock_data.get('最低', 0):7.2f}")

            volume_str = format_amount(stock_data.get('成交额', 0))
            print(f"  成交额: {volume_str}  "
                  f"换手率: {stock_data.get('换手率', 0):.2f}%  "
                  f"振幅: {stock_data.get('振幅', 0):.2f}%")

            if show_indicators:
                indicators = self.get_indicators(stock_data['代码'])
                if indicators:
                    print(f"  技术指标:")
                    ma5 = indicators.get('MA5', float('nan'))
                    ma10 = indicators.get('MA10', float('nan'))
                    ma20 = indicators.get('MA20', float('nan'))
                    rsi14 = indicators.get('RSI14', float('nan'))
                    macd = indicators.get('MACD', float('nan'))
                    macd_signal = indicators.get('MACD_Signal', float('nan'))
                    
                    print(f"    MA5: {ma5:7.2f}  "
                          f"MA10: {ma10:7.2f}  "
                          f"MA20: {ma20:7.2f}")
                    print(f"    RSI14: {rsi14:5.2f}  "
                          f"MACD: {macd:7.4f}  "
                          f"Signal: {macd_signal:7.4f}")
        
        if not has_data:
            if error_count > 0:
                print(f"\n  ⚠ 网络连接异常，无法获取实时数据")
                print(f"  提示: 检查网络连接或稍后重试")
            else:
                print(f"\n  {get_trading_hint()}")
            print("  建议: 可在交易时间再次运行，或使用'策略回测'功能测试历史数据")
    
    def get_indicators(self, stock_code: str, days: int = 60) -> Dict:
        """获取技术指标"""
        try:
            from datetime import timedelta
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')

            # 简易指标缓存（TTL 60s）
            now_ts = time.time()
            cached = self._indicator_cache.get(stock_code)
            if cached and (now_ts - cached[1] < self._indicator_ttl_sec):
                return cached[0]

            df = self.data_source.get_stock_history(stock_code, start_date, end_date)
            
            if df.empty or len(df) < 20:
                return {}
            
            # 计算指标
            df = TechnicalIndicators.calculate_all_indicators(df)
            
            # 返回最新指标
            latest = TechnicalIndicators.get_latest_indicators(df)
            self._indicator_cache[stock_code] = (latest, now_ts)
            return latest
            
        except Exception as e:
            # print(f"计算指标失败: {e}")
            return {}
    
    def display_dashboard(self, show_indicators: bool = True):
        """显示监控面板"""
        self.clear_screen()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print("=" * 100)
        print(f"{'A股实时监控系统':^90}")
        print(f"更新时间: {current_time}")
        print("=" * 100)
        
        # 显示指数
        self.display_indices()
        
        # 显示股票
        self.display_stocks(show_indicators)
        
        print("\n" + "=" * 100)
        print(f"下次更新: {self.refresh_interval}秒后 | 按 Ctrl+C 退出")
    
    def run(self, show_indicators: bool = True):
        """
        运行监控
        
        Args:
            show_indicators: 是否显示技术指标
        """
        print("正在启动实时监控系统...")
        print("首次加载可能需要一些时间，请稍候...\n")
        
        try:
            while True:
                self.display_dashboard(show_indicators)
                time.sleep(self.refresh_interval)
        except KeyboardInterrupt:
            print("\n\n监控已停止。")
