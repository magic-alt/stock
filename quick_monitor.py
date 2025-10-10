"""
快速启动脚本 - 直接开始实时监控
"""

import akshare as ak
import pandas as pd
from datetime import datetime
import time
import os

# 配置
WATCHLIST = ['600519', '000858', '601318', '600036']  # 自选股票
REFRESH_INTERVAL = 30  # 刷新间隔（秒）

def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_stock_info(stock_code):
    """获取股票信息"""
    try:
        df = ak.stock_zh_a_spot_em()
        stock = df[df['代码'] == stock_code]
        if not stock.empty:
            return stock.iloc[0]
    except:
        pass
    return None

def display_monitor():
    """显示监控面板"""
    clear_screen()
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print("=" * 100)
    print(f"{'A股实时监控':^90}")
    print(f"更新时间: {current_time}")
    print("=" * 100)
    
    # 显示指数
    print("\n【主要指数】")
    try:
        df = ak.stock_zh_index_spot_em()
        for code, name in [('000001', '上证指数'), ('399001', '深证成指'), ('399006', '创业板指')]:
            index = df[df['代码'] == code]
            if not index.empty:
                info = index.iloc[0]
                change_symbol = '↑' if info['涨跌幅'] > 0 else '↓' if info['涨跌幅'] < 0 else '-'
                print(f"  {name}: {info['最新价']:.2f} ({info['涨跌幅']:+.2f}%) {change_symbol}")
    except Exception as e:
        print(f"  获取指数数据失败: {e}")
    
    # 显示自选股
    print("\n【自选股票】")
    print("-" * 100)
    
    for stock_code in WATCHLIST:
        info = get_stock_info(stock_code)
        if info is not None:
            change_symbol = '↑' if info['涨跌幅'] > 0 else '↓' if info['涨跌幅'] < 0 else '-'
            print(f"\n{info['名称']}({info['代码']}) {change_symbol}")
            print(f"  价格: {info['最新价']:.2f} | 涨跌: {info['涨跌幅']:+.2f}% | "
                  f"今开: {info['今开']:.2f} | 最高: {info['最高']:.2f} | 最低: {info['最低']:.2f}")
            print(f"  成交额: {info['成交额']:.2f}万 | 换手率: {info['换手率']:.2f}% | 振幅: {info['振幅']:.2f}%")
    
    print("\n" + "=" * 100)
    print(f"下次更新: {REFRESH_INTERVAL}秒后 | 按 Ctrl+C 退出")

def main():
    """主函数"""
    print("正在启动A股实时监控...")
    print("首次加载可能需要几秒钟...\n")
    
    try:
        while True:
            display_monitor()
            time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        print("\n\n监控已停止。再见！")

if __name__ == "__main__":
    main()
