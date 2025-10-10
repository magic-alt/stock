"""
独立回测脚本 - 快速测试交易策略
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class QuickBacktest:
    """快速回测工具"""
    
    def __init__(self, stock_code, days=365, initial_capital=100000):
        self.stock_code = stock_code
        self.days = days
        self.initial_capital = initial_capital
        
    def get_data(self):
        """获取历史数据"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=self.days + 100)).strftime('%Y%m%d')
        
        try:
            df = ak.stock_zh_a_hist(symbol=self.stock_code, period="daily", 
                                   start_date=start_date, end_date=end_date, adjust="qfq")
            return df
        except Exception as e:
            print(f"获取数据失败: {e}")
            return pd.DataFrame()
    
    def strategy_ma_cross(self, df):
        """双均线交叉策略"""
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        
        df['Signal'] = 0
        df.loc[df['MA5'] > df['MA20'], 'Signal'] = 1  # 买入
        df.loc[df['MA5'] <= df['MA20'], 'Signal'] = -1  # 卖出
        df['Position'] = df['Signal'].diff()
        
        return df
    
    def strategy_rsi(self, df):
        """RSI策略（超买超卖）"""
        # 计算RSI
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        df['Signal'] = 0
        df.loc[df['RSI'] < 30, 'Signal'] = 1  # 超卖，买入
        df.loc[df['RSI'] > 70, 'Signal'] = -1  # 超买，卖出
        df['Position'] = df['Signal'].diff()
        
        return df
    
    def run(self, strategy='ma'):
        """运行回测"""
        df = self.get_data()
        if df.empty:
            return None
        
        # 选择策略
        if strategy == 'ma':
            df = self.strategy_ma_cross(df)
            strategy_name = "双均线交叉策略"
        elif strategy == 'rsi':
            df = self.strategy_rsi(df)
            strategy_name = "RSI超买超卖策略"
        else:
            print("未知策略")
            return None
        
        # 执行回测
        capital = self.initial_capital
        position = 0
        trades = []
        
        for idx, row in df.iterrows():
            if pd.isna(row['Position']):
                continue
            
            # 买入
            if row['Position'] > 0 and position == 0:
                position = capital / row['收盘']
                trades.append({
                    'date': row['日期'],
                    'action': 'BUY',
                    'price': row['收盘'],
                    'capital': capital
                })
            
            # 卖出
            elif row['Position'] < 0 and position > 0:
                capital = position * row['收盘']
                profit = capital - trades[-1]['capital']
                profit_pct = (profit / trades[-1]['capital']) * 100
                trades.append({
                    'date': row['日期'],
                    'action': 'SELL',
                    'price': row['收盘'],
                    'capital': capital,
                    'profit': profit,
                    'profit_pct': profit_pct
                })
                position = 0
        
        # 最后如果还持仓，按最后价格卖出
        if position > 0:
            capital = position * df.iloc[-1]['收盘']
        
        # 计算指标
        total_return = ((capital - self.initial_capital) / self.initial_capital) * 100
        
        # 计算买入持有策略收益
        buy_hold_return = ((df.iloc[-1]['收盘'] - df.iloc[0]['收盘']) / df.iloc[0]['收盘']) * 100
        
        # 胜率
        winning_trades = [t for t in trades if t['action'] == 'SELL' and t.get('profit', 0) > 0]
        total_trades = len([t for t in trades if t['action'] == 'SELL'])
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'strategy': strategy_name,
            'initial_capital': self.initial_capital,
            'final_capital': capital,
            'total_return': total_return,
            'buy_hold_return': buy_hold_return,
            'trades': trades,
            'win_rate': win_rate,
            'total_trades': total_trades
        }
    
    def display_results(self, results):
        """显示结果"""
        if not results:
            return
        
        print("\n" + "=" * 90)
        print(f"{'回测报告':^80}")
        print("=" * 90)
        print(f"股票代码: {self.stock_code}")
        print(f"回测策略: {results['strategy']}")
        print(f"回测天数: {self.days}天")
        print("-" * 90)
        print(f"初始资金: {results['initial_capital']:,.2f} 元")
        print(f"最终资金: {results['final_capital']:,.2f} 元")
        print(f"策略收益率: {results['total_return']:+.2f}%")
        print(f"买入持有收益率: {results['buy_hold_return']:+.2f}%")
        print(f"相对收益: {results['total_return'] - results['buy_hold_return']:+.2f}%")
        print("-" * 90)
        print(f"交易次数: {results['total_trades']}")
        print(f"胜率: {results['win_rate']:.2f}%")
        
        if results['trades']:
            print("\n交易记录（最近10笔）:")
            print("-" * 90)
            for trade in results['trades'][-10:]:
                if trade['action'] == 'BUY':
                    print(f"{trade['date']} | 买入 | 价格: {trade['price']:8.2f} | 资金: {trade['capital']:12,.2f}")
                else:
                    print(f"{trade['date']} | 卖出 | 价格: {trade['price']:8.2f} | 资金: {trade['capital']:12,.2f} | "
                          f"盈亏: {trade['profit']:+10,.2f} ({trade['profit_pct']:+.2f}%)")
        
        print("=" * 90)


def main():
    """主函数"""
    print("=" * 90)
    print("A股快速回测工具")
    print("=" * 90)
    
    # 获取用户输入
    stock_code = input("\n请输入股票代码（默认600519）: ").strip() or '600519'
    days = input("回测天数（默认365）: ").strip()
    days = int(days) if days else 365
    
    print("\n选择策略:")
    print("1. 双均线交叉策略（MA5/MA20）")
    print("2. RSI超买超卖策略")
    
    strategy_choice = input("请选择（默认1）: ").strip() or '1'
    strategy = 'ma' if strategy_choice == '1' else 'rsi'
    
    print("\n正在获取数据并运行回测...")
    
    # 运行回测
    bt = QuickBacktest(stock_code, days)
    results = bt.run(strategy)
    
    if results:
        bt.display_results(results)
        
        # 询问是否尝试另一个策略
        print("\n是否尝试另一个策略进行对比？(y/n): ", end='')
        if input().strip().lower() == 'y':
            other_strategy = 'rsi' if strategy == 'ma' else 'ma'
            print(f"\n运行{'RSI' if other_strategy == 'rsi' else '双均线'}策略...")
            results2 = bt.run(other_strategy)
            if results2:
                bt.display_results(results2)
    else:
        print("回测失败，请检查股票代码和网络连接。")


if __name__ == "__main__":
    main()
