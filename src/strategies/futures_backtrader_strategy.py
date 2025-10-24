# -*- coding: utf-8 -*-
"""
期货Backtrader策略集合
包含：双均线、网格交易、做市商、海龟交易法
"""
import backtrader as bt


class FuturesMACrossStrategy(bt.Strategy):
    """期货双均线策略 - EMA交叉"""
    params = (
        ('short_period', 9),
        ('long_period', 34),
        ('atr_period', 14),
        ('atr_mult', 2.0),
    )
    
    def __init__(self):
        self.ema_short = bt.indicators.EMA(self.data.close, period=self.p.short_period)
        self.ema_long = bt.indicators.EMA(self.data.close, period=self.p.long_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.crossover = bt.indicators.CrossOver(self.ema_short, self.ema_long)
    
    def next(self):
        if not self.position:
            if self.crossover > 0:  # Golden cross
                size = self._calc_size()
                self.buy(size=size)
        else:
            if self.crossover < 0:  # Death cross
                self.close()
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 1
        risk_amount = self.broker.getvalue() * 0.02
        size = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        return max(1, size)


class FuturesGridStrategy(bt.Strategy):
    """期货网格交易策略"""
    params = (
        ('grid_pct', 0.004),  # 网格间距百分比
        ('layers', 6),         # 网格层数
        ('max_pos', 3),        # 最大持仓档位
        ('lookback', 50),      # 基准价计算周期
    )
    
    def __init__(self):
        self.grid_lines = []
        self.position_level = 0
        self.base_price = None
        
    def prenext(self):
        # 收集足够数据计算基准价
        if len(self) >= self.p.lookback:
            self.next()
    
    def next(self):
        # 首次运行，建立网格
        if self.base_price is None:
            prices = [self.data.close[i] for i in range(-self.p.lookback, 0)]
            self.base_price = sorted(prices)[len(prices)//2]  # 中位数
            self.grid_lines = [
                self.base_price * (1 + self.p.grid_pct * i)
                for i in range(-self.p.layers, self.p.layers + 1)
            ]
            self.grid_lines.sort()
        
        current_price = self.data.close[0]
        current_level = self._get_grid_level(current_price)
        
        # 网格交易逻辑
        if current_level < self.position_level:  # 价格下跌，加仓
            if self.position_level < self.p.max_pos:
                self.buy(size=1)
                self.position_level += 1
        elif current_level > self.position_level:  # 价格上涨，减仓
            if self.position_level > 0:
                self.sell(size=1)
                self.position_level -= 1
    
    def _get_grid_level(self, price):
        """获取价格所在网格层级"""
        for i, line in enumerate(self.grid_lines):
            if price < line:
                return i
        return len(self.grid_lines)


class FuturesMarketMakingStrategy(bt.Strategy):
    """期货做市商策略 - 均值回归"""
    params = (
        ('band_pct', 0.003),      # 买卖带宽百分比
        ('inventory_limit', 2),    # 库存限制
        ('ma_period', 50),         # 均线周期
    )
    
    def __init__(self):
        self.ma = bt.indicators.SMA(self.data.close, period=self.p.ma_period)
        self.inventory = 0
    
    def next(self):
        current_price = self.data.close[0]
        mid_price = self.ma[0]
        
        if mid_price == 0:
            return
        
        upper_band = mid_price * (1 + self.p.band_pct)
        lower_band = mid_price * (1 - self.p.band_pct)
        
        # 做市逻辑
        if current_price <= lower_band and self.inventory < self.p.inventory_limit:
            # 价格触及下轨，买入补库存
            self.buy(size=1)
            self.inventory += 1
        elif current_price >= upper_band and self.inventory > -self.p.inventory_limit:
            # 价格触及上轨，卖出去库存
            self.sell(size=1)
            self.inventory -= 1
        
        # 同步实际持仓（防止偏差）
        actual_pos = self.position.size
        if actual_pos > 0:
            self.inventory = min(self.p.inventory_limit, actual_pos)
        elif actual_pos < 0:
            self.inventory = max(-self.p.inventory_limit, actual_pos)
        else:
            self.inventory = 0


class TurtleFuturesStrategy(bt.Strategy):
    """海龟交易法 - 唐奇安通道突破 + ATR止损"""
    params = (
        ('entry_period', 20),   # 入场周期（20日高点）
        ('exit_period', 10),    # 出场周期（10日低点）
        ('atr_period', 14),     # ATR周期
        ('atr_mult', 2.0),      # ATR止损倍数
    )
    
    def __init__(self):
        self.highest = bt.indicators.Highest(self.data.high, period=self.p.entry_period)
        self.lowest = bt.indicators.Lowest(self.data.low, period=self.p.exit_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.entry_price = None
        self.stop_loss = None
    
    def next(self):
        if not self.position:
            # 突破入场
            if self.data.close[0] > self.highest[-1]:
                size = self._calc_size()
                self.buy(size=size)
                self.entry_price = self.data.close[0]
                self.stop_loss = self.entry_price - self.p.atr_mult * self.atr[0]
        else:
            # 出场条件：跌破出场通道 或 触及止损
            if self.data.close[0] < self.lowest[-1]:
                self.close()
                self.entry_price = None
                self.stop_loss = None
            elif self.stop_loss and self.data.close[0] < self.stop_loss:
                self.close()
                self.entry_price = None
                self.stop_loss = None
            else:
                # 移动止损（追踪）
                new_stop = self.data.close[0] - self.p.atr_mult * self.atr[0]
                if self.stop_loss is None or new_stop > self.stop_loss:
                    self.stop_loss = new_stop
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 1
        risk_amount = self.broker.getvalue() * 0.02
        size = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        return max(1, size)


# 参数转换函数
def _coerce_futures_ma(d: dict) -> dict:
    return {
        'short_period': int(d.get('short_period', 9)),
        'long_period': int(d.get('long_period', 34)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
    }


def _coerce_futures_grid(d: dict) -> dict:
    return {
        'grid_pct': float(d.get('grid_pct', 0.004)),
        'layers': int(d.get('layers', 6)),
        'max_pos': int(d.get('max_pos', 3)),
        'lookback': int(d.get('lookback', 50)),
    }


def _coerce_futures_mm(d: dict) -> dict:
    return {
        'band_pct': float(d.get('band_pct', 0.003)),
        'inventory_limit': int(d.get('inventory_limit', 2)),
        'ma_period': int(d.get('ma_period', 50)),
    }


def _coerce_turtle(d: dict) -> dict:
    return {
        'entry_period': int(d.get('entry_period', 20)),
        'exit_period': int(d.get('exit_period', 10)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
    }
