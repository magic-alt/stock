"""
格式化工具函数
提供统一的数据格式化策略（补丁：format_amount 输入为【元】）
"""

from typing import Union, Optional
import math


def format_amount(amount_yuan: Optional[float], precision: int = 2) -> str:
    """
    格式化成交额（输入单位：元）
    
    规则：
    - >= 1亿（1e8）：显示为 "XX.XX亿"
    - < 1亿：显示为 "XX.XX万"
    
    Args:
        amount_yuan: 成交额（单位：元）
        precision: 小数位数，默认2位
    
    Returns:
        格式化后的字符串
    
    Examples:
        >>> format_amount(690275671200)  # 6902.76亿元
        '6902.76亿'
        >>> format_amount(11483977500)   # 114.84亿元
        '114.84亿'
        >>> format_amount(50000000)      # 5000万元
        '5000.00万'
        >>> format_amount(0)
        '0.00万'
    """
    if amount_yuan is None:
        return "0.00万"
    try:
        amt = float(amount_yuan)
        if math.isnan(amt) or math.isinf(amt):
            return "0.00万"
        if amt >= 1e8:  # >= 1亿元
            return f"{amt / 1e8:.{precision}f}亿"
        else:           # < 1亿元
            return f"{amt / 1e4:.{precision}f}万"
    except Exception:
        return "0.00万"


def format_percent(value: float, precision: int = 2, show_sign: bool = True) -> str:
    """
    格式化百分比
    
    Args:
        value: 数值（如 0.0523 表示 5.23%）
        precision: 小数位数
        show_sign: 是否显示正负号
    
    Returns:
        格式化后的字符串
    
    Examples:
        >>> format_percent(0.0523)
        '+5.23%'
        >>> format_percent(-0.0312)
        '-3.12%'
        >>> format_percent(0.0, show_sign=False)
        '0.00%'
    """
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            v = 0.0
    except Exception:
        v = 0.0
    if show_sign:
        return f"{v:+.{precision}f}%"
    else:
        return f"{v:.{precision}f}%"


def format_change(value: float, precision: int = 2) -> str:
    """
    格式化涨跌幅（带方向指示）
    
    Args:
        value: 涨跌幅数值
        precision: 小数位数
    
    Returns:
        格式化后的字符串，带涨跌指示符
    
    Examples:
        >>> format_change(5.23)
        '+5.23% ↑'
        >>> format_change(-3.12)
        '-3.12% ↓'
        >>> format_change(0)
        '0.00% -'
    """
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            v = 0.0
    except Exception:
        v = 0.0
    if v > 0:
        return f"+{v:.{precision}f}% ↑"
    elif v < 0:
        return f"{v:.{precision}f}% ↓"
    else:
        return f"{v:.{precision}f}% -"


def format_price(price: float, precision: int = 2) -> str:
    """
    格式化价格
    
    Args:
        price: 价格
        precision: 小数位数
    
    Returns:
        格式化后的字符串
    """
    return f"{price:.{precision}f}"


def format_volume(volume: Union[int, float], unit: str = 'auto') -> str:
    """
    格式化成交量
    
    Args:
        volume: 成交量
        unit: 单位 ('auto', '手', '万手', '亿手')
    
    Returns:
        格式化后的字符串
    
    Examples:
        >>> format_volume(12345678)
        '123.46万手'
        >>> format_volume(1234567890)
        '1.23亿手'
    """
    if unit == 'auto':
        if volume >= 100000000:  # >= 1亿手
            return f"{volume/100000000:.2f}亿手"
        elif volume >= 10000:  # >= 1万手
            return f"{volume/10000:.2f}万手"
        else:
            return f"{int(volume)}手"
    elif unit == '手':
        return f"{int(volume)}手"
    elif unit == '万手':
        return f"{volume/10000:.2f}万手"
    elif unit == '亿手':
        return f"{volume/100000000:.2f}亿手"
    else:
        return f"{volume}"


def format_large_number(value: Union[int, float], precision: int = 2) -> str:
    """
    格式化大数字（自动选择单位：K/M/B）
    
    Args:
        value: 数值
        precision: 小数位数
    
    Returns:
        格式化后的字符串
    """
    if abs(value) >= 1_000_000_000:  # Billion
        return f"{value/1_000_000_000:.{precision}f}B"
    elif abs(value) >= 1_000_000:  # Million
        return f"{value/1_000_000:.{precision}f}M"
    elif abs(value) >= 1_000:  # Thousand
        return f"{value/1_000:.{precision}f}K"
    else:
        return f"{value:.{precision}f}"


def format_shares(shares: Union[int, float]) -> str:
    """
    格式化股数（A股以手为单位，1手=100股）
    
    Args:
        shares: 股数
    
    Returns:
        格式化后的字符串
    
    Examples:
        >>> format_shares(300)
        '300股 (3手)'
        >>> format_shares(10000)
        '10000股 (100手)'
    """
    shares_int = int(shares)
    lots = shares_int // 100
    return f"{shares_int}股 ({lots}手)"


def align_text(text: str, width: int, align: str = 'left') -> str:
    """
    文本对齐
    
    Args:
        text: 文本
        width: 宽度
        align: 对齐方式 ('left', 'right', 'center')
    
    Returns:
        对齐后的字符串
    """
    if align == 'left':
        return text.ljust(width)
    elif align == 'right':
        return text.rjust(width)
    elif align == 'center':
        return text.center(width)
    else:
        return text


def format_table_row(columns: list, widths: list, aligns: Optional[list] = None) -> str:
    """
    格式化表格行
    
    Args:
        columns: 列数据
        widths: 各列宽度
        aligns: 各列对齐方式
    
    Returns:
        格式化后的行字符串
    """
    if aligns is None:
        aligns = ['left'] * len(columns)
    
    parts = []
    for col, width, align in zip(columns, widths, aligns):
        parts.append(align_text(str(col), width, align))
    
    return '  '.join(parts)
