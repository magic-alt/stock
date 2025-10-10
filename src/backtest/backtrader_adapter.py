"""
Backtrader适配器 - 完整实现
"""

import pandas as pd
import backtrader as bt
from datetime import datetime


class BacktraderAdapter:
    """
    Backtrader适配器
    
    用于将本系统与backtrader库集成
    """
    
    def __init__(self):
        self.cerebro = None
        
    def setup(self, initial_capital: float = 100000, commission: float = 0.0003, 
              stamp_duty: float = 0.001):
        """
        设置backtrader环境
        
        Args:
            initial_capital: 初始资金
            commission: 佣金率
            stamp_duty: 印花税率
        """
        try:
            self.cerebro = bt.Cerebro()
            self.cerebro.broker.setcash(initial_capital)
            
            # 设置佣金（包含印花税）
            self.cerebro.broker.setcommission(
                commission=commission + stamp_duty/2,  # 简化：买卖各收一半
                stocklike=True
            )
            
            # 设置交易单位为100股（1手）
            self.cerebro.addsizer(bt.sizers.FixedSize, stake=100)
            
            return True
        except ImportError:
            print("❌ Backtrader未安装，请运行: pip install backtrader")
            return False
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            return False
    
    def add_data(self, df: pd.DataFrame, name: str = 'stock'):
        """
        添加数据到backtrader
        
        Args:
            df: pandas DataFrame (需包含日期、开盘、最高、最低、收盘、成交量列)
            name: 数据名称
        """
        if self.cerebro is None:
            print("❌ 请先调用setup()初始化")
            return False
        
        try:
            # 准备数据格式
            data_df = df.copy()
            
            # 确保列名正确
            column_map = {
                '日期': 'date',
                '开盘': 'open', 
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume'
            }
            
            for cn, en in column_map.items():
                if cn in data_df.columns:
                    data_df.rename(columns={cn: en}, inplace=True)
            
            # 设置日期索引
            if 'date' in data_df.columns:
                data_df['date'] = pd.to_datetime(data_df['date'])
                data_df.set_index('date', inplace=True)
            
            # 确保必需列存在
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in data_df.columns:
                    print(f"❌ 缺少必需列: {col}")
                    return False
            
            # 创建backtrader数据源
            data = bt.feeds.PandasData(
                dataname=data_df,
                datetime=None,  # 使用索引作为日期
                open='open',
                high='high',
                low='low',
                close='close',
                volume='volume',
                openinterest=-1
            )
            
            self.cerebro.adddata(data, name=name)
            return True
            
        except Exception as e:
            print(f"❌ 添加数据失败: {e}")
            return False
    
    def add_strategy(self, strategy_class, **kwargs):
        """
        添加策略
        
        Args:
            strategy_class: backtrader策略类或策略名称
            **kwargs: 策略参数
        """
        if self.cerebro is None:
            print("❌ 请先调用setup()初始化")
            return False
        
        try:
            # 如果是字符串，转换为内置策略
            if isinstance(strategy_class, str):
                strategy_class = self._get_builtin_strategy(strategy_class)
                if strategy_class is None:
                    return False
            
            self.cerebro.addstrategy(strategy_class, **kwargs)
            return True
        except Exception as e:
            print(f"❌ 添加策略失败: {e}")
            return False
    
    def _get_builtin_strategy(self, strategy_name: str):
        """获取内置策略"""
        strategies = {
            'sma_cross': SMACrossStrategy,
            'rsi': RSIStrategy,
            'macd': MACDStrategy
        }
        
        strategy = strategies.get(strategy_name.lower())
        if strategy is None:
            print(f"❌ 未知策略: {strategy_name}")
            print(f"可用策略: {', '.join(strategies.keys())}")
        return strategy
    
    def run(self):
        """运行回测"""
        if self.cerebro is None:
            print("❌ 请先调用setup()初始化")
            return None
        
        try:
            print("\n开始运行回测...")
            start_value = self.cerebro.broker.getvalue()
            print(f"初始资金: {start_value:,.2f}")
            
            results = self.cerebro.run()
            
            end_value = self.cerebro.broker.getvalue()
            print(f"最终资金: {end_value:,.2f}")
            print(f"收益: {end_value - start_value:+,.2f} ({(end_value/start_value - 1)*100:+.2f}%)")
            
            return results
        except Exception as e:
            print(f"❌ 运行回测失败: {e}")
            return None
    
    def plot(self, style='candlestick'):
        """绘制回测结果"""
        if self.cerebro is None:
            print("❌ 请先调用setup()初始化并运行回测")
            return
        
        try:
            print("\n正在生成图表...")
            self.cerebro.plot(style=style, iplot=False)
        except Exception as e:
            print(f"❌ 绘图失败: {e}")
            print("提示: 可能需要安装 matplotlib")


# ============ 内置策略 ============

class SMACrossStrategy(bt.Strategy):
    """双均线交叉策略"""
    params = (
        ('fast_period', 5),
        ('slow_period', 20),
    )
    
    def __init__(self):
        self.sma_fast = bt.indicators.SMA(self.data.close, period=self.params.fast_period)
        self.sma_slow = bt.indicators.SMA(self.data.close, period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)
        
    def next(self):
        if not self.position:
            if self.crossover > 0:  # 金叉
                self.buy()
        else:
            if self.crossover < 0:  # 死叉
                self.close()


class RSIStrategy(bt.Strategy):
    """RSI策略"""
    params = (
        ('period', 14),
        ('oversold', 30),
        ('overbought', 70),
    )
    
    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.period)
        
    def next(self):
        if not self.position:
            if self.rsi < self.params.oversold:  # 超卖
                self.buy()
        else:
            if self.rsi > self.params.overbought:  # 超买
                self.close()


class MACDStrategy(bt.Strategy):
    """MACD策略"""
    params = (
        ('fast', 12),
        ('slow', 26),
        ('signal', 9),
    )
    
    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal
        )
        
    def next(self):
        if not self.position:
            if self.macd.macd > self.macd.signal:  # MACD上穿信号线
                self.buy()
        else:
            if self.macd.macd < self.macd.signal:  # MACD下穿信号线
                self.close()


# ============ 工具函数 ============

def run_backtrader_backtest(df: pd.DataFrame, strategy_name: str = 'sma_cross',
                           initial_capital: float = 100000, **strategy_params):
    """
    快速运行backtrader回测
    
    Args:
        df: 历史数据DataFrame
        strategy_name: 策略名称 ('sma_cross', 'rsi', 'macd')
        initial_capital: 初始资金
        **strategy_params: 策略参数
    
    Returns:
        回测结果
    """
    adapter = BacktraderAdapter()
    
    if not adapter.setup(initial_capital):
        return None
    
    if not adapter.add_data(df):
        return None
    
    if not adapter.add_strategy(strategy_name, **strategy_params):
        return None
    
    results = adapter.run()
    
    return results
