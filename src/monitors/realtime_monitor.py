"""
实时监控器
"""

import os
import time
from datetime import datetime
from typing import Dict, List
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
    
    def display_stocks(self, show_indicators: bool = True):
        """
        显示股票信息
        
        Args:
            show_indicators: 是否显示技术指标
        """
        print("\n【自选股票】")
        print("-" * 100)
        
        has_data = False
        error_count = 0
        
        for code, name in self.watchlist.items():
            stock_data = self.data_source.get_stock_realtime(code)
            
            if not stock_data:
                error_count += 1
                continue
            
            # 检查是否有有效数据（非交易时间数据全为0）
            if stock_data['最新价'] == 0:
                continue
            
            has_data = True
            change_str = format_change(stock_data['涨跌幅'])
            
            print(f"\n{stock_data['名称']}({stock_data['代码']})")
            print(f"  价格: {stock_data['最新价']:7.2f}  {change_str:15s}  "
                  f"今开: {stock_data['今开']:7.2f}  最高: {stock_data['最高']:7.2f}  "
                  f"最低: {stock_data['最低']:7.2f}")
            
            # 成交额单位处理：使用统一格式化函数
            volume_str = format_amount(stock_data['成交额'])
            
            print(f"  成交额: {volume_str}  "
                  f"换手率: {stock_data['换手率']:.2f}%  "
                  f"振幅: {stock_data['振幅']:.2f}%")
            
            # 显示技术指标
            if show_indicators:
                indicators = self.get_indicators(code)
                if indicators:
                    print(f"  技术指标:")
                    print(f"    MA5: {indicators.get('MA5', 'N/A'):7.2f}  "
                          f"MA10: {indicators.get('MA10', 'N/A'):7.2f}  "
                          f"MA20: {indicators.get('MA20', 'N/A'):7.2f}")
                    print(f"    RSI14: {indicators.get('RSI14', 'N/A'):5.2f}  "
                          f"MACD: {indicators.get('MACD', 'N/A'):7.4f}  "
                          f"Signal: {indicators.get('MACD_Signal', 'N/A'):7.4f}")
        
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
            
            df = self.data_source.get_stock_history(stock_code, start_date, end_date)
            
            if df.empty or len(df) < 20:
                return {}
            
            # 计算指标
            df = TechnicalIndicators.calculate_all_indicators(df)
            
            # 返回最新指标
            return TechnicalIndicators.get_latest_indicators(df)
            
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
