"""
交易时间管理模块
提供交易日历和交易时段判定
"""

from datetime import datetime, time, timedelta
from typing import Optional, Tuple
import pandas as pd


class TradingCalendar:
    """交易日历（A股）"""
    
    # A股交易时段
    MORNING_START = time(9, 30)
    MORNING_END = time(11, 30)
    AFTERNOON_START = time(13, 0)
    AFTERNOON_END = time(15, 0)
    
    # 集合竞价时段
    CALL_AUCTION_START = time(9, 15)
    CALL_AUCTION_END = time(9, 25)
    
    # 周末
    WEEKEND_DAYS = [5, 6]  # 周六、周日
    
    @classmethod
    def is_trading_day(cls, date: datetime) -> bool:
        """
        判断是否为交易日（简化版，不考虑节假日）
        
        Args:
            date: 日期时间
        
        Returns:
            是否为交易日
        
        Note:
            完整实现需要接入节假日API或维护节假日列表
        """
        # 排除周末
        if date.weekday() in cls.WEEKEND_DAYS:
            return False
        
        # TODO: 接入节假日数据
        # 当前简化实现：只排除周末
        return True
    
    @classmethod
    def is_trading_session(cls, dt: Optional[datetime] = None) -> bool:
        """
        判断当前是否为交易时段
        
        Args:
            dt: 日期时间，默认为当前时间
        
        Returns:
            是否为交易时段
        """
        if dt is None:
            dt = datetime.now()
        
        # 首先检查是否为交易日
        if not cls.is_trading_day(dt):
            return False
        
        current_time = dt.time()
        
        # 检查是否在交易时段
        in_morning = cls.MORNING_START <= current_time <= cls.MORNING_END
        in_afternoon = cls.AFTERNOON_START <= current_time <= cls.AFTERNOON_END
        
        return in_morning or in_afternoon
    
    @classmethod
    def is_call_auction(cls, dt: Optional[datetime] = None) -> bool:
        """
        判断是否为集合竞价时段
        
        Args:
            dt: 日期时间，默认为当前时间
        
        Returns:
            是否为集合竞价时段
        """
        if dt is None:
            dt = datetime.now()
        
        if not cls.is_trading_day(dt):
            return False
        
        current_time = dt.time()
        return cls.CALL_AUCTION_START <= current_time <= cls.CALL_AUCTION_END
    
    @classmethod
    def get_trading_status(cls, dt: Optional[datetime] = None) -> str:
        """
        获取交易状态描述
        
        Args:
            dt: 日期时间，默认为当前时间
        
        Returns:
            状态描述：'交易中'、'集合竞价'、'午间休市'、'盘后'、'周末'、'节假日'
        """
        if dt is None:
            dt = datetime.now()
        
        # 检查是否为周末
        if dt.weekday() in cls.WEEKEND_DAYS:
            return '周末'
        
        # TODO: 检查是否为节假日
        if not cls.is_trading_day(dt):
            return '节假日'
        
        current_time = dt.time()
        
        # 集合竞价
        if cls.CALL_AUCTION_START <= current_time <= cls.CALL_AUCTION_END:
            return '集合竞价'
        
        # 上午交易
        if cls.MORNING_START <= current_time <= cls.MORNING_END:
            return '交易中'
        
        # 午间休市
        if cls.MORNING_END < current_time < cls.AFTERNOON_START:
            return '午间休市'
        
        # 下午交易
        if cls.AFTERNOON_START <= current_time <= cls.AFTERNOON_END:
            return '交易中'
        
        # 盘后
        return '盘后'
    
    @classmethod
    def get_next_trading_session(cls, dt: Optional[datetime] = None) -> Tuple[datetime, str]:
        """
        获取下一个交易时段
        
        Args:
            dt: 日期时间，默认为当前时间
        
        Returns:
            (下一个交易时段的开始时间, 描述)
        """
        if dt is None:
            dt = datetime.now()
        
        status = cls.get_trading_status(dt)
        current_time = dt.time()
        
        if status == '交易中':
            return dt, '当前正在交易'
        
        # 集合竞价 -> 等待开盘
        if status == '集合竞价':
            next_time = dt.replace(
                hour=cls.MORNING_START.hour,
                minute=cls.MORNING_START.minute,
                second=0
            )
            return next_time, '早盘开盘'
        
        # 午间休市 -> 下午开盘
        if status == '午间休市':
            next_time = dt.replace(
                hour=cls.AFTERNOON_START.hour,
                minute=cls.AFTERNOON_START.minute,
                second=0
            )
            return next_time, '午盘开盘'
        
        # 盘后、周末、节假日 -> 下一个交易日早盘
        next_day = dt + timedelta(days=1)
        while not cls.is_trading_day(next_day):
            next_day += timedelta(days=1)
        
        next_time = next_day.replace(
            hour=cls.MORNING_START.hour,
            minute=cls.MORNING_START.minute,
            second=0
        )
        return next_time, '下一交易日开盘'
    
    @classmethod
    def get_trading_hint(cls, dt: Optional[datetime] = None) -> str:
        """
        获取交易时间提示信息
        
        Args:
            dt: 日期时间，默认为当前时间
        
        Returns:
            提示信息
        """
        if dt is None:
            dt = datetime.now()
        
        status = cls.get_trading_status(dt)
        
        if status == '交易中':
            return "✓ 当前为交易时间"
        
        next_time, desc = cls.get_next_trading_session(dt)
        time_diff = next_time - dt
        
        hours = int(time_diff.total_seconds() // 3600)
        minutes = int((time_diff.total_seconds() % 3600) // 60)
        
        hints = [
            f"⚠ 当前为非交易时间（{status}）",
            f"下次交易: {desc}",
            f"时间: {next_time.strftime('%Y-%m-%d %H:%M')}",
        ]
        
        if hours > 0:
            hints.append(f"距离开盘: {hours}小时{minutes}分钟")
        else:
            hints.append(f"距离开盘: {minutes}分钟")
        
        return '\n  '.join(hints)


# 便捷函数
def is_trading_session(dt: Optional[datetime] = None) -> bool:
    """判断是否为交易时段（便捷函数）"""
    return TradingCalendar.is_trading_session(dt)


def get_trading_status(dt: Optional[datetime] = None) -> str:
    """获取交易状态（便捷函数）"""
    return TradingCalendar.get_trading_status(dt)


def get_trading_hint(dt: Optional[datetime] = None) -> str:
    """获取交易提示（便捷函数）"""
    return TradingCalendar.get_trading_hint(dt)
