# -*- coding: utf-8 -*-
"""
日内回转策略 - Backtrader版本
基于开盘价的日内均值回归

V3.0.0 优化:
- 增加交易时间过滤 (start_time, exit_time)
- ATR 动态阈值替代固定百分比
- 避免开盘、尾盘剧烈波动期交易
"""
import backtrader as bt


class IntradayReversionStrategy(bt.Strategy):
    """
    日内回转交易策略
    
    V3.0.0 优化:
    - start_time: 开盘后多久开始交易 (默认 9:45)
    - exit_time: 收盘前强制平仓时间 (默认 14:50)
    - atr_thresh_mult: 用 ATR * mult 替代固定百分比阈值
    - 避免开盘集合竞价和尾盘剧烈波动
    
    注意：适用于分钟级数据，日线数据效果有限
    """
    params = (
        ('threshold_pct', 0.8),    # 偏离阈值（%）- 作为 fallback
        ('allow_short', False),     # 是否允许做空
        ('atr_period', 14),
        ('atr_mult', 2.0),
        ('start_time', '09:45'),   # V3.0: 开始交易时间
        ('exit_time', '14:50'),    # V3.0: 强制平仓时间
        ('atr_thresh_mult', 1.0),  # V3.0: ATR 阈值倍数
    )
    
    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.day_open = None
        self.current_date = None
    
    def prenext(self):
        self.next()
    
    def _parse_time(self, time_str):
        """Parse time string to (hour, minute) tuple"""
        parts = time_str.split(':')
        return int(parts[0]), int(parts[1])
    
    def _is_trading_time(self):
        """V3.0: Check if current time is within trading window"""
        try:
            current_dt = self.data.datetime.datetime(0)
            current_hour = current_dt.hour
            current_min = current_dt.minute
            
            start_h, start_m = self._parse_time(self.p.start_time)
            exit_h, exit_m = self._parse_time(self.p.exit_time)
            
            current_minutes = current_hour * 60 + current_min
            start_minutes = start_h * 60 + start_m
            exit_minutes = exit_h * 60 + exit_m
            
            return start_minutes <= current_minutes < exit_minutes
        except Exception:
            # 如果是日线数据，没有时间信息，返回 True
            return True
    
    def _should_force_exit(self):
        """V3.0: Check if it's time for forced exit"""
        try:
            current_dt = self.data.datetime.datetime(0)
            current_hour = current_dt.hour
            current_min = current_dt.minute
            
            exit_h, exit_m = self._parse_time(self.p.exit_time)
            
            current_minutes = current_hour * 60 + current_min
            exit_minutes = exit_h * 60 + exit_m
            
            return current_minutes >= exit_minutes
        except Exception:
            return False
    
    def next(self):
        # 检测新的交易日
        current_date = self.data.datetime.date(0)
        if current_date != self.current_date:
            # 新的一天，记录开盘价
            self.day_open = self.data.open[0]
            self.current_date = current_date
            # 如果有持仓，先平仓（日内回转）
            if self.position:
                self.close()
            return
        
        if self.day_open is None or self.day_open == 0:
            return
        
        # V3.0: 强制平仓时间检查
        if self._should_force_exit():
            if self.position:
                self.close()
            return
        
        # V3.0: 交易时间窗口检查
        if not self._is_trading_time():
            return
        
        # V3.0: ATR 动态阈值
        atr_threshold = (self.atr[0] / self.day_open * 100) * self.p.atr_thresh_mult
        threshold = max(self.p.threshold_pct, atr_threshold)  # 取较大值
        
        # 计算偏离百分比
        deviation = (self.data.close[0] / self.day_open - 1.0) * 100.0
        
        if not self.position:
            # 开仓逻辑：价格大幅偏离开盘价
            if deviation <= -threshold:
                # 下跌超过阈值，做多（预期回归）
                size = self._calc_size()
                self.buy(size=size)
            elif self.p.allow_short and deviation >= threshold:
                # 上涨超过阈值，做空（预期回归）
                size = self._calc_size()
                self.sell(size=size)
        else:
            # 平仓逻辑：回归开盘价附近
            if self.position.size > 0:  # 持有多头
                if self.data.close[0] >= self.day_open * 0.995:
                    self.close()
            elif self.position.size < 0:  # 持有空头
                if self.data.close[0] <= self.day_open * 1.005:
                    self.close()
    
    def _calc_size(self):
        if self.atr[0] == 0:
            return 100  # 最小1手
        risk_amount = self.broker.getvalue() * 0.02
        size = int(risk_amount / (self.atr[0] * self.p.atr_mult))
        # 强制100股整数倍（A股规则）
        lots = max(1, size // 100)
        return lots * 100


def _coerce_intraday(d: dict) -> dict:
    return {
        'threshold_pct': float(d.get('threshold_pct', 0.8)),
        'allow_short': bool(d.get('allow_short', False)),
        'atr_period': int(d.get('atr_period', 14)),
        'atr_mult': float(d.get('atr_mult', 2.0)),
        'start_time': str(d.get('start_time', '09:45')),
        'exit_time': str(d.get('exit_time', '14:50')),
        'atr_thresh_mult': float(d.get('atr_thresh_mult', 1.0)),
    }
