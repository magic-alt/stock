"""
工具函数模块
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def format_number(num: float, precision: int = 2) -> str:
    """
    格式化数字显示
    
    Args:
        num: 数字
        precision: 精度
    
    Returns:
        格式化后的字符串
    """
    if num >= 100000000:  # 亿
        return f"{num/100000000:.{precision}f}亿"
    elif num >= 10000:  # 万
        return f"{num/10000:.{precision}f}万"
    else:
        return f"{num:.{precision}f}"


def get_date_range(days: int) -> tuple:
    """
    获取日期范围
    
    Args:
        days: 天数
    
    Returns:
        (开始日期, 结束日期) 格式: YYYYMMDD
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    return (start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d'))


def print_table(data: List[Dict], headers: List[str], widths: List[int] = None):
    """
    打印表格
    
    Args:
        data: 数据列表
        headers: 表头列表
        widths: 列宽列表
    """
    if not widths:
        widths = [15] * len(headers)
    
    # 打印表头
    header_line = " | ".join([h.center(w) for h, w in zip(headers, widths)])
    print(header_line)
    print("-" * len(header_line))
    
    # 打印数据
    for row in data:
        row_line = " | ".join([
            str(row.get(h, '')).center(w) for h, w in zip(headers, widths)
        ])
        print(row_line)


def save_to_file(data: str, filename: str, mode: str = 'w'):
    """
    保存数据到文件
    
    Args:
        data: 数据内容
        filename: 文件名
        mode: 写入模式
    """
    try:
        with open(filename, mode, encoding='utf-8') as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"保存文件失败: {e}")
        return False


def create_dir_if_not_exists(path: str):
    """
    如果目录不存在则创建
    
    Args:
        path: 目录路径
    """
    if not os.path.exists(path):
        os.makedirs(path)
