"""
A股实时监控和回测系统
功能：
1. 实时显示A股主要指数信息
2. 监控自选股票的实时价格和技术指标
3. 简单的回测功能
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import sys
from typing import List, Dict

# 配置区域
WATCHLIST = [
    '600519',  # 贵州茅台
    '000858',  # 五粮液
    '601318',  # 中国平安
    '600036',  # 招商银行
    '000001',  # 平安银行
]

# 指数代码
INDICES = {
    '000001': '上证指数',
    '399001': '深证成指',
    '399006': '创业板指',
    '000300': '沪深300',
}

REFRESH_INTERVAL = 30  # 刷新间隔（秒）


class StockMonitor:
    """股票监控类"""
    
    def __init__(self, watchlist: List[str], indices: Dict[str, str]):
        self.watchlist = watchlist
        self.indices = indices
        
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def get_index_realtime(self) -> pd.DataFrame:
        """获取指数实时数据"""
        index_data = []
        try:
            for code, name in self.indices.items():
                try:
                    # 获取指数实时行情
                    df = ak.stock_zh_index_spot_em()
                    index_info = df[df['代码'] == code]
                    
                    if not index_info.empty:
                        info = index_info.iloc[0]
                        index_data.append({
                            '代码': code,
                            '名称': name,
                            '最新价': info['最新价'],
                            '涨跌幅': info['涨跌幅'],
                            '涨跌额': info['涨跌额'],
                            '成交量': info['成交量'],
                            '成交额': info['成交额'],
                            '振幅': info['振幅'],
                        })
                except Exception as e:
                    print(f"获取指数 {name} 数据失败: {e}")
                    
        except Exception as e:
            print(f"获取指数数据失败: {e}")
        
        return pd.DataFrame(index_data)
    
    def get_stock_realtime(self, stock_code: str) -> Dict:
        """获取股票实时数据"""
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            stock_info = df[df['代码'] == stock_code]
            
            if stock_info.empty:
                return None
            
            info = stock_info.iloc[0]
            
            return {
                '代码': stock_code,
                '名称': info['名称'],
                '最新价': info['最新价'],
                '涨跌幅': info['涨跌幅'],
                '涨跌额': info['涨跌额'],
                '成交量': info['成交量'],
                '成交额': info['成交额'],
                '振幅': info['振幅'],
                '最高': info['最高'],
                '最低': info['最低'],
                '今开': info['今开'],
                '昨收': info['昨收'],
                '换手率': info['换手率'],
            }
        except Exception as e:
            print(f"获取股票 {stock_code} 数据失败: {e}")
            return None
    
    def calculate_technical_indicators(self, stock_code: str, period: int = 60) -> Dict:
        """计算技术指标"""
        try:
            # 获取历史数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=period * 2)).strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                                   start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df.empty or len(df) < 20:
                return {}
            
            # 计算MA均线
            df['MA5'] = df['收盘'].rolling(window=5).mean()
            df['MA10'] = df['收盘'].rolling(window=10).mean()
            df['MA20'] = df['收盘'].rolling(window=20).mean()
            
            # 计算RSI
            delta = df['收盘'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # 计算MACD
            exp1 = df['收盘'].ewm(span=12, adjust=False).mean()
            exp2 = df['收盘'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            
            # 获取最新指标
            latest = df.iloc[-1]
            
            return {
                'MA5': round(latest['MA5'], 2) if pd.notna(latest['MA5']) else None,
                'MA10': round(latest['MA10'], 2) if pd.notna(latest['MA10']) else None,
                'MA20': round(latest['MA20'], 2) if pd.notna(latest['MA20']) else None,
                'RSI': round(latest['RSI'], 2) if pd.notna(latest['RSI']) else None,
                'MACD': round(latest['MACD'], 4) if pd.notna(latest['MACD']) else None,
                'Signal': round(latest['Signal'], 4) if pd.notna(latest['Signal']) else None,
            }
        except Exception as e:
            print(f"计算 {stock_code} 技术指标失败: {e}")
            return {}
    
    def display_dashboard(self):
        """显示监控面板"""
        self.clear_screen()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print("=" * 100)
        print(f"{'A股实时监控系统':^90}")
        print(f"更新时间: {current_time}")
        print("=" * 100)
        
        # 显示指数信息
        print("\n【主要指数】")
        print("-" * 100)
        index_df = self.get_index_realtime()
        if not index_df.empty:
            print(index_df.to_string(index=False))
        else:
            print("暂无指数数据")
        
        # 显示自选股信息
        print("\n【自选股票】")
        print("-" * 100)
        
        for stock_code in self.watchlist:
            stock_info = self.get_stock_realtime(stock_code)
            
            if stock_info:
                # 涨跌幅颜色标记
                change_pct = stock_info['涨跌幅']
                color = '↑' if change_pct > 0 else '↓' if change_pct < 0 else '-'
                
                print(f"\n股票: {stock_info['名称']}({stock_info['代码']}) {color}")
                print(f"  最新价: {stock_info['最新价']:.2f} | 涨跌幅: {change_pct:.2f}% | 涨跌额: {stock_info['涨跌额']:.2f}")
                print(f"  今开: {stock_info['今开']:.2f} | 最高: {stock_info['最高']:.2f} | 最低: {stock_info['最低']:.2f} | 昨收: {stock_info['昨收']:.2f}")
                print(f"  成交量: {stock_info['成交量']} | 成交额: {stock_info['成交额']:.2f}万 | 振幅: {stock_info['振幅']:.2f}% | 换手率: {stock_info['换手率']:.2f}%")
                
                # 获取技术指标
                indicators = self.calculate_technical_indicators(stock_code)
                if indicators:
                    print(f"  技术指标:")
                    print(f"    MA5: {indicators.get('MA5', 'N/A')} | MA10: {indicators.get('MA10', 'N/A')} | MA20: {indicators.get('MA20', 'N/A')}")
                    print(f"    RSI(14): {indicators.get('RSI', 'N/A')} | MACD: {indicators.get('MACD', 'N/A')} | Signal: {indicators.get('Signal', 'N/A')}")
            else:
                print(f"\n股票 {stock_code}: 数据获取失败")
        
        print("\n" + "=" * 100)
        print(f"下次更新: {REFRESH_INTERVAL}秒后 | 按 Ctrl+C 退出")
    
    def run(self):
        """运行监控"""
        print("正在启动A股实时监控系统...")
        print("首次加载可能需要一些时间，请稍候...")
        
        try:
            while True:
                self.display_dashboard()
                time.sleep(REFRESH_INTERVAL)
        except KeyboardInterrupt:
            print("\n\n监控已停止。")
            sys.exit(0)


class SimpleBacktest:
    """简单回测系统"""
    
    def __init__(self, stock_code: str, start_date: str, end_date: str, initial_capital: float = 100000):
        self.stock_code = stock_code
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        
    def get_historical_data(self) -> pd.DataFrame:
        """获取历史数据"""
        try:
            df = ak.stock_zh_a_hist(symbol=self.stock_code, period="daily", 
                                   start_date=self.start_date, end_date=self.end_date, adjust="qfq")
            return df
        except Exception as e:
            print(f"获取历史数据失败: {e}")
            return pd.DataFrame()
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算买卖信号（基于MA双均线策略）"""
        # 计算均线
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        
        # 生成信号：MA5上穿MA20买入，下穿卖出
        df['Signal'] = 0
        df.loc[df['MA5'] > df['MA20'], 'Signal'] = 1  # 持仓
        df.loc[df['MA5'] <= df['MA20'], 'Signal'] = -1  # 空仓
        
        # 生成交易信号
        df['Position'] = df['Signal'].diff()
        
        return df
    
    def run_backtest(self) -> Dict:
        """运行回测"""
        df = self.get_historical_data()
        
        if df.empty:
            print("无法获取历史数据，回测失败")
            return {}
        
        df = self.calculate_signals(df)
        
        # 初始化
        capital = self.initial_capital
        position = 0  # 持仓数量
        trades = []
        
        for idx, row in df.iterrows():
            if pd.isna(row['Position']):
                continue
            
            # 买入信号
            if row['Position'] == 2 and position == 0:
                position = capital / row['收盘']
                buy_price = row['收盘']
                trades.append({
                    'date': row['日期'],
                    'action': 'BUY',
                    'price': buy_price,
                    'shares': position,
                    'capital': capital
                })
            
            # 卖出信号
            elif row['Position'] == -2 and position > 0:
                capital = position * row['收盘']
                sell_price = row['收盘']
                trades.append({
                    'date': row['日期'],
                    'action': 'SELL',
                    'price': sell_price,
                    'shares': position,
                    'capital': capital
                })
                position = 0
        
        # 如果最后还持仓，按最后价格卖出
        if position > 0:
            capital = position * df.iloc[-1]['收盘']
        
        # 计算收益
        total_return = (capital - self.initial_capital) / self.initial_capital * 100
        
        # 计算最大回撤
        df['Capital'] = self.initial_capital
        cumulative_capital = self.initial_capital
        
        for idx, row in df.iterrows():
            if position > 0:
                cumulative_capital = position * row['收盘']
            df.loc[idx, 'Capital'] = cumulative_capital
        
        df['Cummax'] = df['Capital'].cummax()
        df['Drawdown'] = (df['Capital'] - df['Cummax']) / df['Cummax'] * 100
        max_drawdown = df['Drawdown'].min()
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': capital,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'trades': trades,
            'trade_count': len(trades)
        }
    
    def display_results(self, results: Dict):
        """显示回测结果"""
        print("\n" + "=" * 80)
        print(f"{'回测结果':^70}")
        print("=" * 80)
        print(f"股票代码: {self.stock_code}")
        print(f"回测周期: {self.start_date} 至 {self.end_date}")
        print(f"初始资金: {results['initial_capital']:,.2f} 元")
        print(f"最终资金: {results['final_capital']:,.2f} 元")
        print(f"总收益率: {results['total_return']:.2f}%")
        print(f"最大回撤: {results['max_drawdown']:.2f}%")
        print(f"交易次数: {results['trade_count']}")
        
        print("\n交易记录:")
        print("-" * 80)
        for trade in results['trades']:
            print(f"{trade['date']} | {trade['action']:4s} | 价格: {trade['price']:8.2f} | "
                  f"数量: {trade['shares']:8.2f} | 资金: {trade['capital']:12,.2f}")
        
        print("=" * 80)


def main():
    """主函数"""
    print("=" * 80)
    print("A股实时监控和回测系统")
    print("=" * 80)
    print("\n请选择功能:")
    print("1. 实时监控")
    print("2. 回测系统")
    print("0. 退出")
    
    choice = input("\n请输入选项 (0-2): ").strip()
    
    if choice == '1':
        # 实时监控
        print("\n正在启动实时监控...")
        print(f"监控指数: {', '.join(INDICES.values())}")
        print(f"自选股票: {', '.join(WATCHLIST)}")
        print(f"刷新间隔: {REFRESH_INTERVAL}秒\n")
        
        monitor = StockMonitor(WATCHLIST, INDICES)
        monitor.run()
        
    elif choice == '2':
        # 回测系统
        print("\n回测系统")
        print("-" * 80)
        
        stock_code = input("请输入股票代码 (如 600519): ").strip()
        if not stock_code:
            stock_code = '600519'
        
        # 默认回测最近一年
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        print(f"\n使用默认回测周期: {start_date} 至 {end_date}")
        initial_capital = 100000
        
        custom = input("是否自定义参数? (y/n): ").strip().lower()
        if custom == 'y':
            start_date = input("开始日期 (YYYYMMDD): ").strip()
            end_date = input("结束日期 (YYYYMMDD): ").strip()
            initial_capital = float(input("初始资金 (元): ").strip())
        
        print("\n正在运行回测...")
        backtest = SimpleBacktest(stock_code, start_date, end_date, initial_capital)
        results = backtest.run_backtest()
        
        if results:
            backtest.display_results(results)
        
    elif choice == '0':
        print("\n再见!")
        sys.exit(0)
    else:
        print("\n无效选项，请重新运行程序。")


if __name__ == "__main__":
    main()
