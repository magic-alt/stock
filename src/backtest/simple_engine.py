"""
简单回测引擎
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime


class SimpleBacktestEngine:
    """简单回测引擎"""
    
    def __init__(self, initial_capital: float = 100000, 
                 commission: float = 0.0003,
                 stamp_duty: float = 0.001,
                 slippage: float = 0.0001):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            commission: 手续费率
            stamp_duty: 印花税率（仅卖出）
            slippage: 滑点率
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.stamp_duty = stamp_duty
        self.slippage = slippage
        
        self.capital = initial_capital
        self.position = 0
        self.trades = []
        self.daily_value = []
        
    def reset(self):
        """重置回测状态"""
        self.capital = self.initial_capital
        self.position = 0
        self.trades = []
        self.daily_value = []
    
    def calculate_cost(self, price: float, shares: float, is_buy: bool) -> float:
        """
        计算交易成本
        
        Args:
            price: 价格
            shares: 股数
            is_buy: 是否买入
        
        Returns:
            交易成本
        """
        amount = price * shares
        
        # 手续费
        commission_cost = amount * self.commission
        commission_cost = max(commission_cost, 5)  # 最低5元
        
        # 印花税（仅卖出）
        stamp_cost = amount * self.stamp_duty if not is_buy else 0
        
        # 滑点
        slippage_cost = amount * self.slippage
        
        return commission_cost + stamp_cost + slippage_cost
    
    def execute_trade(self, date, price: float, signal: int):
        """
        执行交易
        
        Args:
            date: 交易日期
            price: 价格
            signal: 信号 (1: 买入, -1: 卖出, 0: 持有)
        """
        if signal == 1 and self.position == 0:
            # 买入 - 按手（100股）交易
            max_shares = self.capital / price
            # 向下取整到100的整数倍（1手=100股）
            shares = int(max_shares / 100) * 100
            
            if shares < 100:  # 资金不足买1手
                return
            
            actual_amount = shares * price
            cost = self.calculate_cost(price, shares, True)
            
            if actual_amount + cost > self.capital:  # 加上成本后资金不足
                shares = int((self.capital - 100) / price / 100) * 100  # 预留成本
                if shares < 100:
                    return
                actual_amount = shares * price
                cost = self.calculate_cost(price, shares, True)
            
            self.position = shares
            self.capital -= (actual_amount + cost)
            
            self.trades.append({
                'date': date,
                'type': 'BUY',
                'price': price,
                'shares': shares,
                'cost': cost,
                'capital': self.capital,
                'value': self.position * price + self.capital
            })
            
        elif signal == -1 and self.position > 0:
            # 卖出
            shares = self.position
            actual_amount = shares * price
            cost = self.calculate_cost(price, shares, False)
            self.capital += (actual_amount - cost)
            
            # 计算盈亏
            buy_trade = [t for t in self.trades if t['type'] == 'BUY'][-1]
            buy_amount = buy_trade['price'] * shares
            sell_amount = actual_amount
            total_cost = cost + buy_trade['cost']
            profit = sell_amount - buy_amount - total_cost
            profit_pct = profit / buy_amount * 100
            
            self.trades.append({
                'date': date,
                'type': 'SELL',
                'price': price,
                'shares': shares,
                'cost': cost,
                'capital': self.capital,
                'value': self.capital,
                'profit': profit,
                'profit_pct': profit_pct
            })
            
            self.position = 0
    
    def run(self, df: pd.DataFrame, strategy) -> Dict:
        """
        运行回测
        
        Args:
            df: 历史数据DataFrame
            strategy: 策略对象
        
        Returns:
            回测结果字典
        """
        self.reset()
        
        # 生成信号
        df = strategy.generate_signals(df)
        
        # 执行回测
        for idx, row in df.iterrows():
            signal = 0
            
            if pd.notna(row.get('Position', 0)):
                if row['Position'] > 0:
                    signal = 1  # 买入信号
                elif row['Position'] < 0:
                    signal = -1  # 卖出信号
            
            self.execute_trade(row['日期'], row['收盘'], signal)
            
            # 记录每日价值
            current_value = self.capital
            if self.position > 0:
                current_value += self.position * row['收盘']
            
            self.daily_value.append({
                'date': row['日期'],
                'value': current_value,
                'price': row['收盘']
            })
        
        # 如果最后还有持仓，按最后价格卖出
        if self.position > 0:
            last_price = df.iloc[-1]['收盘']
            last_date = df.iloc[-1]['日期']
            self.execute_trade(last_date, last_price, -1)
        
        # 计算统计指标
        return self.calculate_metrics(df)
    
    def calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """计算回测指标"""
        # 总收益
        total_return = (self.capital - self.initial_capital) / self.initial_capital * 100
        
        # 买入持有收益
        buy_hold_return = (df.iloc[-1]['收盘'] - df.iloc[0]['收盘']) / df.iloc[0]['收盘'] * 100
        
        # 最大回撤
        values = [d['value'] for d in self.daily_value]
        cummax = pd.Series(values).cummax()
        drawdown = (pd.Series(values) - cummax) / cummax * 100
        max_drawdown = drawdown.min()
        
        # 交易统计
        sell_trades = [t for t in self.trades if t['type'] == 'SELL']
        winning_trades = [t for t in sell_trades if t.get('profit', 0) > 0]
        
        win_rate = len(winning_trades) / len(sell_trades) * 100 if sell_trades else 0
        
        avg_profit = np.mean([t['profit'] for t in sell_trades]) if sell_trades else 0
        avg_profit_pct = np.mean([t['profit_pct'] for t in sell_trades]) if sell_trades else 0
        
        # 夏普比率（简化版）
        if len(values) > 1:
            returns = pd.Series(values).pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_return': total_return,
            'buy_hold_return': buy_hold_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_profit_pct': avg_profit_pct,
            'trades': self.trades,
            'daily_value': self.daily_value
        }
