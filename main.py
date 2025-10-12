"""
A股实时监控系统 V2.0 - 模块化版本
支持AI、芯片、黄金等主题股票监控
"""

import sys
import os
import logging
import argparse
from typing import Optional

# 配置日志：只在控制台显示ERROR级别，WARNING级别写入文件
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log', encoding='utf-8'),  # 写入文件
    ]
)
# 控制台只显示ERROR级别
console = logging.StreamHandler()
console.setLevel(logging.ERROR)
logging.getLogger('').addHandler(console)

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import *
from src.monitors import StockMonitor
from src.backtest import SimpleBacktestEngine
from src.backtest.backtrader_adapter import BacktraderAdapter, run_backtrader_backtest
from src.strategies import *  # 兼容现有导出
from src.strategies.registry import list_strategies, create_strategy
from src.data_sources import DataSourceFactory, CachedDataSource
from src.utils.data_downloader import DataDownloader
from datetime import datetime, timedelta


def main_monitor():
    """实时监控主程序"""
    print("=" * 80)
    print("A股实时监控系统 V2.0")
    print("=" * 80)
    print("\n请选择监控方案:")
    print("1. 默认方案 (AI+芯片+黄金+优质股)")
    print("2. AI芯片主题")
    print("3. 黄金主题")
    print("4. 新能源汽车")
    print("5. 优质蓝筹")
    print("6. 科技综合")
    print("7. 全部股票")
    print("8. 自定义")
    print("0. 返回")
    
    choice = input("\n请选择 (0-8): ").strip()
    
    watchlist = None
    indices_list = INDICES
    
    if choice == '1':
        watchlist = DEFAULT_WATCHLIST
    elif choice == '2':
        plan = get_preset_plan('ai_chip')
        watchlist = plan['stocks']
        indices_list = {k: INDICES[k] for k in plan['indices'] if k in INDICES}
    elif choice == '3':
        plan = get_preset_plan('gold')
        watchlist = plan['stocks']
        indices_list = {k: INDICES[k] for k in plan['indices'] if k in INDICES}
    elif choice == '4':
        plan = get_preset_plan('ev')
        watchlist = plan['stocks']
        indices_list = {k: INDICES[k] for k in plan['indices'] if k in INDICES}
    elif choice == '5':
        plan = get_preset_plan('blue_chip')
        watchlist = plan['stocks']
        indices_list = {k: INDICES[k] for k in plan['indices'] if k in INDICES}
    elif choice == '6':
        plan = get_preset_plan('tech')
        watchlist = plan['stocks']
        indices_list = {k: INDICES[k] for k in plan['indices'] if k in INDICES}
    elif choice == '7':
        watchlist = get_all_stocks()
    elif choice == '8':
        print("\n请输入股票代码（用逗号分隔）:")
        codes = input().strip().split(',')
        watchlist = {code.strip(): code.strip() for code in codes if code.strip()}
    elif choice == '0':
        return
    else:
        print("无效选择")
        return
    
    if not watchlist:
        print("未选择任何股票")
        return
    
    print(f"\n将监控 {len(watchlist)} 只股票...")
    show_indicators = input("是否显示技术指标? (y/n, 默认y): ").strip().lower() != 'n'
    
    # 创建监控器
    monitor = StockMonitor(
        watchlist=watchlist,
        indices=indices_list,
        refresh_interval=REFRESH_INTERVAL,
        data_source=DATA_SOURCE
    )
    
    # 启动监控
    monitor.run(show_indicators=show_indicators)


def main_backtest():
    """回测主程序"""
    print("\n" + "=" * 80)
    print("回测系统 V2.0")
    print("=" * 80)
    
    # 选择回测引擎
    print("\n请选择回测引擎:")
    print("1. 简单回测引擎 (快速)")
    print("2. Backtrader引擎 (专业，带图表)")
    print("0. 返回")
    
    engine_choice = input("请选择 (0-2): ").strip()
    
    if engine_choice == '0':
        return
    elif engine_choice == '1':
        main_backtest_simple()
    elif engine_choice == '2':
        main_backtest_backtrader()
    else:
        print("无效选择")


def main_backtest_simple():
    """简单回测引擎"""
    print("\n" + "=" * 80)
    print("简单回测引擎")
    print("=" * 80)
    
    # 选择股票
    stock_code, stock_name = select_stock()
    if not stock_code:
        return
    
    # 选择策略
    print("\n选择回测策略:")
    print("1. 双均线交叉 (MA5/MA20)")
    print("2. 三均线策略 (MA5/MA10/MA20)")
    print("3. RSI超买超卖")
    print("4. MACD信号")
    print("5. MACD零轴")
    
    strategy_choice = input("请选择策略 (1-5): ").strip()
    
    strategies = {
        '1': MACrossStrategy(5, 20),
        '2': TripleMACrossStrategy(5, 10, 20),
        '3': RSIStrategy(14, 30, 70),
        '4': MACDStrategy(12, 26, 9),
        '5': MACDZeroCrossStrategy(12, 26, 9),
    }
    
    strategy = strategies.get(strategy_choice)
    if not strategy:
        print("无效策略")
        return
    
    # 选择回测周期
    start_date, end_date = select_backtest_period()
    if not start_date:
        return
    
    # 获取数据
    print(f"\n正在获取 {stock_name}({stock_code}) 的历史数据...")
    
    # 使用简单的 AKShare 数据获取方法，绕过复杂的缓存系统
    try:
        data_source = DataSourceFactory.create(DATA_SOURCE)
        df = data_source.get_stock_history_simple(stock_code, start_date, end_date)
    except Exception as e:
        print(f"❌ 数据获取失败: {e}")
        # 回退到原来的方法
        data_source = DataSourceFactory.create(DATA_SOURCE)
        df = data_source.get_stock_history(stock_code, start_date, end_date)
    
    if df.empty:
        print("获取数据失败")
        return
    
    print(f"获取到 {len(df)} 条数据")
    
    # 运行回测
    print(f"\n使用 {strategy.name} 进行回测...")
    
    engine = SimpleBacktestEngine(
        initial_capital=BACKTEST_CONFIG['initial_capital'],
        commission=BACKTEST_CONFIG['commission'],
        stamp_duty=BACKTEST_CONFIG['stamp_duty'],
        slippage=BACKTEST_CONFIG['slippage']
    )
    
    results = engine.run(df, strategy)
    
    # 显示结果
    display_backtest_results(stock_name, stock_code, strategy.name, results)


def main_backtest_backtrader():
    """Backtrader专业回测"""
    print("\n" + "=" * 80)
    print("Backtrader专业回测引擎")
    print("=" * 80)
    
    # 检查backtrader是否安装
    try:
        import backtrader as bt
    except ImportError:
        print("\n❌ Backtrader未安装！")
        print("请运行以下命令安装:")
        print("  pip install backtrader matplotlib")
        input("\n按回车键返回...")
        return
    
    # 选择股票（复用选择逻辑）
    stock_code, stock_name = select_stock()
    if not stock_code:
        return
    
    # 选择策略（与 registry 对齐，方便未来扩展）
    from src.strategies.registry import list_strategies
    all_strats = list_strategies()
    keys = list(all_strats.keys())

    print("\n选择回测策略（来自注册表）:")
    for i, k in enumerate(keys, 1):
        print(f"{i:2d}. {k:18s} - {all_strats[k]}")
    try:
        idx = int(input(f"请选择策略 (1-{len(keys)}): ").strip())
        if not 1 <= idx <= len(keys):
            raise ValueError()
        strategy_key = keys[idx - 1]
    except Exception:
        print("无效策略")
        return
    
    # 选择回测周期
    start_date, end_date = select_backtest_period()
    if not start_date:
        return
    
    # 获取数据
    print(f"\n正在获取 {stock_name}({stock_code}) 的历史数据...")
    
    # 使用简单的 AKShare 数据获取方法，绕过复杂的缓存系统
    try:
        data_source = DataSourceFactory.create(DATA_SOURCE)
        df = data_source.get_stock_history_simple(stock_code, start_date, end_date)
    except Exception as e:
        print(f"❌ 数据获取失败: {e}")
        # 回退到原来的方法
        data_source = DataSourceFactory.create(DATA_SOURCE)
        df = data_source.get_stock_history(stock_code, start_date, end_date)
    
    if df.empty:
        print("获取数据失败")
        return
    
    print(f"获取到 {len(df)} 条数据")
    
    # 运行Backtrader回测
    print(f"\n使用策略 {strategy_key} 进行回测（Backtrader）...")

    # Backtrader 适配器现在基于“外置策略→Signal”，只需传 registry 键
    sizer_cfg = BACKTEST_CONFIG.get('sizer', {}) or {}
    result_tuple = run_backtrader_backtest(
        df=df,
        strategy_key=strategy_key,
        initial_capital=BACKTEST_CONFIG['initial_capital'],
        commission=BACKTEST_CONFIG.get('commission', 0.0001),
        stamp_duty=BACKTEST_CONFIG.get('stamp_duty', 0.0),
        min_cash_per_trade=float(sizer_cfg.get('min_cash', 20000.0)),
        max_cash_per_trade=float(sizer_cfg.get('max_cash', 50000.0))
    )

    # run_backtrader_backtest 现在返回 (results, adapter)
    results = None
    adapter = None
    if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
        results, adapter = result_tuple
    else:
        results = result_tuple

    if results:
        print("\n✅ 回测完成！")
        
        # 询问是否绘图
        show_plot = input("\n是否显示图表? (y/n, 默认y): ").strip().lower() != 'n'
        if show_plot and adapter is not None:
            adapter.plot()
    
    input("\n按回车键继续...")


def select_stock():
    """选择股票（公共函数）"""
    print("\n请选择股票:")
    print("1. 手动输入代码")
    print("2. 从分组选择")
    
    choice = input("请选择 (1-2): ").strip()
    
    stock_code = None
    stock_name = None
    
    if choice == '1':
        stock_code = input("请输入股票代码: ").strip()
        stock_name = stock_code
    elif choice == '2':
        groups = get_stock_groups()
        print("\n股票分组:")
        for idx, (name, stocks) in enumerate(groups.items(), 1):
            print(f"{idx}. {name} ({len(stocks)}只)")
        
        group_choice = input(f"请选择分组 (1-{len(groups)}): ").strip()
        try:
            group_name = list(groups.keys())[int(group_choice) - 1]
            group_stocks = groups[group_name]
            
            print(f"\n{group_name}组股票:")
            for idx, (code, name) in enumerate(group_stocks.items(), 1):
                print(f"{idx}. {name}({code})")
            
            stock_choice = input(f"请选择股票 (1-{len(group_stocks)}): ").strip()
            stock_code = list(group_stocks.keys())[int(stock_choice) - 1]
            stock_name = group_stocks[stock_code]
        except:
            print("无效选择")
            return None, None
    else:
        print("无效选择")
        return None, None
    
    return stock_code, stock_name


def select_backtest_period():
    """选择回测周期（公共函数）"""
    print("\n选择回测周期:")
    print("1. 短期 (30天)")
    print("2. 中期 (90天)")
    print("3. 长期 (365天)")
    print("4. 自定义")
    
    period_choice = input("请选择 (1-4): ").strip()
    
    if period_choice in ['1', '2', '3']:
        days = {'1': 30, '2': 90, '3': 365}[period_choice]
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days + 60)).strftime('%Y%m%d')
    elif period_choice == '4':
        start_date = input("开始日期 (YYYYMMDD): ").strip()
        end_date = input("结束日期 (YYYYMMDD): ").strip()
    else:
        print("无效选择")
        return None, None
    
    return start_date, end_date


def display_backtest_results(stock_name: str, stock_code: str, 
                            strategy_name: str, results: dict):
    """显示回测结果"""
    print("\n" + "=" * 90)
    print(f"{'回测报告':^80}")
    print("=" * 90)
    print(f"股票: {stock_name}({stock_code})")
    print(f"策略: {strategy_name}")
    print("-" * 90)
    print(f"初始资金: {results['initial_capital']:,.2f} 元")
    print(f"最终资金: {results['final_capital']:,.2f} 元")
    print(f"总收益率: {results['total_return']:+.2f}%")
    print(f"买入持有收益率: {results['buy_hold_return']:+.2f}%")
    print(f"相对收益: {results['total_return'] - results['buy_hold_return']:+.2f}%")
    print("-" * 90)
    print(f"最大回撤: {results['max_drawdown']:.2f}%")
    print(f"夏普比率: {results['sharpe_ratio']:.2f}")
    print(f"交易次数: {results['total_trades']}")
    print(f"胜率: {results['win_rate']:.2f}%")
    print(f"平均盈利: {results['avg_profit']:,.2f} 元 ({results['avg_profit_pct']:.2f}%)")
    
    # 显示交易记录
    if results['trades']:
        print("\n最近交易记录:")
        print("-" * 90)
        for trade in results['trades'][-10:]:
            if trade['type'] == 'BUY':
                print(f"{trade['date']} | 买入 | 价格: {trade['price']:8.2f} | "
                      f"股数: {int(trade['shares']):6d} | 成本: {trade['cost']:10,.2f}")
            else:
                profit_str = f"{trade['profit']:+10,.2f} ({trade['profit_pct']:+.2f}%)"
                print(f"{trade['date']} | 卖出 | 价格: {trade['price']:8.2f} | "
                      f"股数: {int(trade['shares']):6d} | 盈亏: {profit_str}")
    
    print("=" * 90)


def main_data_management():
    """数据管理主菜单"""
    while True:
        print("\n" + "=" * 80)
        print("数据管理中心")
        print("=" * 80)
        print("\n选择操作:")
        print("1. 缓存信息统计")
        print("2. 数据库预览")
        print("3. 下载最近数据")
        print("4. 下载指定股票")
        print("5. 下载指数数据") 
        print("6. 更新缓存数据")
        print("7. 测试数据源")
        print("8. 清空缓存")
        print("0. 返回主菜单")
        
        choice = input("\n请选择 (0-8): ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            show_cache_info()
        elif choice == '2':
            preview_database()
        elif choice == '3':
            download_recent_data()
        elif choice == '4':
            download_custom_stocks()
        elif choice == '5':
            download_indices_data()
        elif choice == '6':
            update_cache_data()
        elif choice == '7':
            test_data_source()
        elif choice == '8':
            clear_cache_data()
        else:
            print("\n无效选择，请重试")


def show_cache_info():
    """显示缓存信息"""
    try:
        cached_source = CachedDataSource()
        stats = cached_source.get_cache_stats()
        downloader = DataDownloader()
        suggestions = downloader.get_download_suggestions()
        
        print(f"\n{'='*50}")
        print("📦 缓存信息统计")
        print(f"{'='*50}")
        print(f"📁 数据库路径: {stats.get('db_path', 'N/A')}")
        print(f"💾 数据库大小: {stats.get('db_size_mb', 0):.2f} MB")
        print(f"📈 股票数量: {stats.get('stock_symbols', 0)}")
        print(f"📊 股票记录数: {stats.get('stock_records', 0):,}")
        print(f"📉 指数数量: {stats.get('index_symbols', 0)}")
        print(f"📋 指数记录数: {stats.get('index_records', 0):,}")
        
        if suggestions.get('recommendations'):
            print(f"\n💡 建议:")
            for rec in suggestions['recommendations']:
                print(f"   • {rec['message']}")
                
        input("\n按回车键继续...")
        
    except Exception as e:
        print(f"❌ 获取缓存信息失败: {e}")
        input("\n按回车键继续...")


def preview_database():
    """预览数据库内容"""
    try:
        import sqlite3
        from pathlib import Path
        
        print(f"\n{'='*80}")
        print("📊 数据库预览")
        print(f"{'='*80}")
        
        db_path = Path("datacache") / "stock_data.db"
        
        if not db_path.exists():
            print("❌ 数据库文件不存在")
            input("\n按回车键继续...")
            return
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 菜单选项
            print("\n选择预览内容:")
            print("1. 股票数据概览")
            print("2. 指数数据概览")
            print("3. 最近更新记录")
            print("4. 查看指定股票数据")
            print("5. 查看指定指数数据")
            print("0. 返回")
            
            choice = input("\n请选择 (0-5): ").strip()
            
            if choice == '0':
                return
            elif choice == '1':
                preview_stock_summary(conn)
            elif choice == '2':
                preview_index_summary(conn)
            elif choice == '3':
                preview_recent_updates(conn)
            elif choice == '4':
                preview_specific_stock(conn)
            elif choice == '5':
                preview_specific_index(conn)
            else:
                print("❌ 无效选择")
        
        input("\n按回车键继续...")
        
    except Exception as e:
        print(f"❌ 预览数据库失败: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键继续...")


def preview_stock_summary(conn):
    """预览股票数据概览"""
    cursor = conn.cursor()
    
    print(f"\n{'='*80}")
    print("📈 股票数据概览")
    print(f"{'='*80}")
    
    # 获取所有股票及其数据量
    cursor.execute('''
        SELECT stock_code, adjust_type, COUNT(*) as count, 
               MIN(date) as start_date, MAX(date) as end_date
        FROM stock_history
        GROUP BY stock_code, adjust_type
        ORDER BY stock_code
    ''')
    
    results = cursor.fetchall()
    
    if not results:
        print("❌ 暂无股票数据")
        return
    
    print(f"\n共 {len(results)} 只股票(不同复权类型)")
    print(f"\n{'股票代码':<12} {'复权类型':<10} {'记录数':<10} {'开始日期':<15} {'结束日期':<15}")
    print("-" * 80)
    
    for row in results:
        stock_code, adjust_type, count, start_date, end_date = row
        print(f"{stock_code:<12} {adjust_type:<10} {count:<10} {start_date:<15} {end_date:<15}")
    
    # 显示最近的数据样例
    print(f"\n{'='*80}")
    print("📋 最近10条股票数据样例")
    print(f"{'='*80}")
    
    cursor.execute('''
        SELECT stock_code, date, open, high, low, close, volume
        FROM stock_history
        ORDER BY date DESC, stock_code
        LIMIT 10
    ''')
    
    samples = cursor.fetchall()
    
    if samples:
        print(f"\n{'股票':<10} {'日期':<12} {'开盘':<10} {'最高':<10} {'最低':<10} {'收盘':<10} {'成交量':<15}")
        print("-" * 80)
        for row in samples:
            stock_code, date, open_p, high, low, close, volume = row
            volume_str = f"{int(volume):,}" if volume else "N/A"
            print(f"{stock_code:<10} {date:<12} {open_p:<10.2f} {high:<10.2f} {low:<10.2f} {close:<10.2f} {volume_str:<15}")


def preview_index_summary(conn):
    """预览指数数据概览"""
    cursor = conn.cursor()
    
    print(f"\n{'='*80}")
    print("📉 指数数据概览")
    print(f"{'='*80}")
    
    # 获取所有指数及其数据量
    cursor.execute('''
        SELECT index_code, COUNT(*) as count, 
               MIN(date) as start_date, MAX(date) as end_date
        FROM index_history
        GROUP BY index_code
        ORDER BY index_code
    ''')
    
    results = cursor.fetchall()
    
    if not results:
        print("❌ 暂无指数数据")
        return
    
    print(f"\n共 {len(results)} 个指数")
    print(f"\n{'指数代码':<12} {'记录数':<10} {'开始日期':<15} {'结束日期':<15}")
    print("-" * 80)
    
    for row in results:
        index_code, count, start_date, end_date = row
        print(f"{index_code:<12} {count:<10} {start_date:<15} {end_date:<15}")
    
    # 显示最近的数据样例
    print(f"\n{'='*80}")
    print("📋 最近10条指数数据样例")
    print(f"{'='*80}")
    
    cursor.execute('''
        SELECT index_code, date, open, high, low, close, volume
        FROM index_history
        ORDER BY date DESC, index_code
        LIMIT 10
    ''')
    
    samples = cursor.fetchall()
    
    if samples:
        print(f"\n{'指数':<10} {'日期':<12} {'开盘':<10} {'最高':<10} {'最低':<10} {'收盘':<10} {'成交量':<15}")
        print("-" * 80)
        for row in samples:
            index_code, date, open_p, high, low, close, volume = row
            volume_str = f"{int(volume):,}" if volume else "N/A"
            print(f"{index_code:<10} {date:<12} {open_p:<10.2f} {high:<10.2f} {low:<10.2f} {close:<10.2f} {volume_str:<15}")


def preview_recent_updates(conn):
    """预览最近更新记录"""
    cursor = conn.cursor()
    
    print(f"\n{'='*80}")
    print("🔄 最近更新记录")
    print(f"{'='*80}")
    
    cursor.execute('''
        SELECT symbol, symbol_type, last_update_date, last_update_time, data_count
        FROM data_updates
        ORDER BY last_update_time DESC
        LIMIT 20
    ''')
    
    results = cursor.fetchall()
    
    if not results:
        print("❌ 暂无更新记录")
        return
    
    print(f"\n{'代码':<12} {'类型':<10} {'最后日期':<15} {'更新时间':<20} {'记录数':<10}")
    print("-" * 80)
    
    for row in results:
        symbol, symbol_type, last_date, last_time, count = row
        # 格式化时间
        if last_time and len(last_time) > 19:
            last_time = last_time[:19]
        print(f"{symbol:<12} {symbol_type:<10} {last_date:<15} {last_time:<20} {count:<10}")


def preview_specific_stock(conn):
    """查看指定股票的详细数据"""
    stock_code = input("\n请输入股票代码: ").strip()
    
    if not stock_code:
        print("❌ 股票代码不能为空")
        return
    
    cursor = conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"📊 股票 {stock_code} 的历史数据")
    print(f"{'='*80}")
    
    cursor.execute('''
        SELECT date, open, high, low, close, volume, amount, pct_change
        FROM stock_history
        WHERE stock_code = ?
        ORDER BY date DESC
        LIMIT 30
    ''', (stock_code,))
    
    results = cursor.fetchall()
    
    if not results:
        print(f"❌ 未找到股票 {stock_code} 的数据")
        return
    
    print(f"\n找到 {len(results)} 条记录（显示最近30条）")
    print(f"\n{'日期':<12} {'开盘':<10} {'最高':<10} {'最低':<10} {'收盘':<10} {'成交量':<15} {'成交额':<15} {'涨跌幅%':<10}")
    print("-" * 120)
    
    for row in results:
        date, open_p, high, low, close, volume, amount, pct_change = row
        volume_str = f"{int(volume):,}" if volume else "N/A"
        amount_str = f"{amount/100000000:.2f}亿" if amount and amount > 0 else "N/A"
        pct_str = f"{pct_change:+.2f}" if pct_change else "N/A"
        
        print(f"{date:<12} {open_p:<10.2f} {high:<10.2f} {low:<10.2f} {close:<10.2f} {volume_str:<15} {amount_str:<15} {pct_str:<10}")


def preview_specific_index(conn):
    """查看指定指数的详细数据"""
    index_code = input("\n请输入指数代码: ").strip()
    
    if not index_code:
        print("❌ 指数代码不能为空")
        return
    
    cursor = conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"📉 指数 {index_code} 的历史数据")
    print(f"{'='*80}")
    
    cursor.execute('''
        SELECT date, open, high, low, close, volume, amount, pct_change
        FROM index_history
        WHERE index_code = ?
        ORDER BY date DESC
        LIMIT 30
    ''', (index_code,))
    
    results = cursor.fetchall()
    
    if not results:
        print(f"❌ 未找到指数 {index_code} 的数据")
        return
    
    print(f"\n找到 {len(results)} 条记录（显示最近30条）")
    print(f"\n{'日期':<12} {'开盘':<10} {'最高':<10} {'最低':<10} {'收盘':<10} {'成交量':<15} {'成交额':<15} {'涨跌幅%':<10}")
    print("-" * 120)
    
    for row in results:
        date, open_p, high, low, close, volume, amount, pct_change = row
        volume_str = f"{int(volume):,}" if volume else "N/A"
        amount_str = f"{amount/100000000:.2f}亿" if amount and amount > 0 else "N/A"
        pct_str = f"{pct_change:+.2f}" if pct_change else "N/A"
        
        print(f"{date:<12} {open_p:<10.2f} {high:<10.2f} {low:<10.2f} {close:<10.2f} {volume_str:<15} {amount_str:<15} {pct_str:<10}")


def download_recent_data():
    """下载最近数据"""
    try:
        print("\n📥 下载最近数据")
        print("-" * 30)
        
        days = input("请输入天数 (默认365天): ").strip()
        if not days:
            days = 365
        else:
            days = int(days)
        
        print("\n可选股票组:")
        groups = list(STOCK_GROUPS.keys())
        for i, group in enumerate(groups, 1):
            print(f"{i}. {group}")
        print(f"{len(groups)+1}. 全部股票组")
        
        group_choice = input(f"\n选择股票组 (1-{len(groups)+1}): ").strip()
        
        selected_groups = None
        if group_choice and group_choice.isdigit():
            choice_idx = int(group_choice) - 1
            if 0 <= choice_idx < len(groups):
                selected_groups = [groups[choice_idx]]
        
        print(f"\n🚀 开始下载最近 {days} 天的数据...")
        
        downloader = DataDownloader()
        results = downloader.download_recent_data(days, selected_groups)
        
        # 显示结果
        print(f"\n{'='*50}")
        print("📊 下载结果")
        print(f"{'='*50}")
        
        for category, result_dict in results.items():
            if isinstance(result_dict, dict):
                success_count = sum(1 for v in result_dict.values() if v)
                total_count = len(result_dict)
                print(f"📂 {category}: {success_count}/{total_count} 成功")
        
        print("\n✅ 下载完成")
        input("\n按回车键继续...")
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        input("\n按回车键继续...")


def download_custom_stocks():
    """下载指定股票"""
    try:
        print("\n📥 下载指定股票")
        print("-" * 30)
        
        codes_input = input("请输入股票代码 (多个用逗号分隔): ").strip()
        if not codes_input:
            print("❌ 股票代码不能为空")
            input("\n按回车键继续...")
            return
        
        stock_codes = [code.strip() for code in codes_input.split(',')]
        
        start_date = input("开始日期 (YYYY-MM-DD, 默认30天前): ").strip()
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        end_date = input("结束日期 (YYYY-MM-DD, 默认今天): ").strip()
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"\n🚀 开始下载 {len(stock_codes)} 只股票的数据...")
        print(f"📅 日期范围: {start_date} ~ {end_date}")
        
        downloader = DataDownloader()
        results = downloader.download_custom_stocks(stock_codes, start_date, end_date)
        
        # 显示结果
        print(f"\n{'='*50}")
        print("📊 下载结果")
        print(f"{'='*50}")
        
        for stock_code, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {stock_code}")
        
        success_count = sum(results.values())
        print(f"\n📈 总计: {success_count}/{len(results)} 成功")
        input("\n按回车键继续...")
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        input("\n按回车键继续...")


def download_indices_data():
    """下载指数数据"""
    try:
        print("\n📥 下载指数数据")
        print("-" * 30)
        
        start_date = input("开始日期 (YYYY-MM-DD, 默认30天前): ").strip()
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        end_date = input("结束日期 (YYYY-MM-DD, 默认今天): ").strip()
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"\n🚀 开始下载主要指数数据...")
        print(f"📅 日期范围: {start_date} ~ {end_date}")
        
        downloader = DataDownloader()
        results = downloader.download_major_indices(start_date, end_date)
        
        # 显示结果
        print(f"\n{'='*50}")
        print("📊 下载结果")
        print(f"{'='*50}")
        
        for index_code, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {index_code}")
        
        success_count = sum(results.values())
        print(f"\n📈 总计: {success_count}/{len(results)} 成功")
        input("\n按回车键继续...")
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        input("\n按回车键继续...")


def update_cache_data():
    """更新缓存数据"""
    try:
        print("\n🔄 更新缓存数据")
        print("-" * 30)
        
        days_back = input("往前多少天开始更新 (默认7天): ").strip()
        if not days_back:
            days_back = 7
        else:
            days_back = int(days_back)
        
        print(f"\n🔄 开始增量更新最近 {days_back} 天的数据...")
        
        downloader = DataDownloader()
        results = downloader.update_data(days_back)
        
        # 显示结果
        print(f"\n{'='*50}")
        print("📊 更新结果")
        print(f"{'='*50}")
        
        for category, result_dict in results.items():
            if isinstance(result_dict, dict):
                success_count = sum(1 for v in result_dict.values() if v)
                total_count = len(result_dict)
                print(f"📂 {category}: {success_count}/{total_count} 成功")
        
        print(f"\n✅ 更新完成")
        input("\n按回车键继续...")
        
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        input("\n按回车键继续...")


def test_data_source():
    """测试数据源"""
    try:
        print("\n🧪 测试数据源连接")
        print("-" * 30)
        
        print("📡 正在初始化缓存数据源...")
        cached_source = CachedDataSource()
        
        print("📊 测试实时数据接口...")
        realtime_data = cached_source.get_stock_realtime('000001')
        if realtime_data:
            print(f"✅ 实时数据接口正常: {realtime_data.get('name', 'N/A')}")
        else:
            print("⚠️ 实时数据接口异常")
        
        print("📈 测试历史数据接口...")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        history_data = cached_source.get_stock_history('000001', start_date, end_date)
        if not history_data.empty:
            print(f"✅ 历史数据接口正常，获取到 {len(history_data)} 条记录")
        else:
            print("⚠️ 历史数据接口异常或无数据")
        
        print("\n✅ 数据源测试完成")
        input("\n按回车键继续...")
        
    except Exception as e:
        print(f"❌ 数据源测试失败: {e}")
        input("\n按回车键继续...")


def clear_cache_data():
    """清空缓存数据"""
    try:
        print("\n🗑️ 清空缓存数据")
        print("-" * 30)
        print("⚠️ 警告：此操作将删除所有本地缓存数据！")
        
        confirm = input("\n确定要清空所有缓存吗？(输入 'yes' 确认): ").strip()
        if confirm.lower() != 'yes':
            print("❌ 操作已取消")
            input("\n按回车键继续...")
            return
        
        print("\n🗑️ 正在清空缓存...")
        cached_source = CachedDataSource()
        cached_source.clear_cache()
        
        print("✅ 缓存清空完成")
        input("\n按回车键继续...")
        
    except Exception as e:
        print(f"❌ 清空缓存失败: {e}")
        input("\n按回车键继续...")


def run_monitor_cli(plan: Optional[str], no_indicators: bool, refresh_override: Optional[int]):
    """基于命令行参数的监控入口（非交互）。"""
    indices_list = INDICES
    if plan:
        plan_cfg = PRESET_PLANS.get(plan)
        if plan_cfg:
            watchlist = plan_cfg['stocks']
            indices_list = {k: INDICES[k] for k in plan_cfg['indices'] if k in INDICES}
        else:
            # 兜底使用默认
            watchlist = DEFAULT_WATCHLIST
    else:
        watchlist = DEFAULT_WATCHLIST

    refresh = refresh_override if refresh_override is not None else REFRESH_INTERVAL
    # DATA_SOURCE 可被 CLI 覆盖由外部注入（通过全局 DATA_SOURCE 或者传参）
    monitor = StockMonitor(watchlist=watchlist, indices=indices_list, refresh_interval=refresh, data_source=DATA_SOURCE)
    monitor.run(show_indicators=(not no_indicators))


def run_backtest_cli(engine: str, strategy_key: str, code: str, period: str,
                     start_date: Optional[str], end_date: Optional[str], **kwargs):
    """基于命令行参数的回测入口（非交互）。

    Args:
        engine: 'simple' 或 'bt'（backtrader）
        strategy_key: 来自 registry 的键名（如 'rsi', 'macd', 'ma_cross'）
        code: 股票代码
        period: 'short'|'mid'|'long'|'custom'
        start_date/end_date: 自定义区间时必填（YYYYMMDD）
    """
    # 解析周期
    if period in ['short', 'mid', 'long']:
        days_map = {'short': 30, 'mid': 90, 'long': 365}
        days = days_map[period]
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days + 60)).strftime('%Y%m%d')
    elif period == 'custom':
        if not (start_date and end_date):
            raise SystemExit("自定义周期需提供 --start 与 --end (YYYYMMDD)")
    else:
        raise SystemExit("未知周期，请使用 short/mid/long/custom")

    from src.data_sources import DataSourceFactory
    
    # 使用简单的 AKShare 数据获取方法，绕过复杂的缓存系统
    try:
        data_source = DataSourceFactory.create(DATA_SOURCE)
        df = data_source.get_stock_history_simple(code, start_date, end_date)
    except Exception as e:
        print(f"❌ 数据获取失败: {e}")
        # 回退到原来的方法
        data_source = DataSourceFactory.create(DATA_SOURCE)
        df = data_source.get_stock_history(code, start_date, end_date)
        
    if df.empty:
        raise SystemExit("获取历史数据失败或为空")

    if engine == 'simple':
        # 通过注册表创建策略
        try:
            strategy = create_strategy(strategy_key)
        except KeyError as e:
            available = ', '.join(list_strategies().keys())
            raise SystemExit(f"{e}\n可用策略: {available}")

        engine_runner = SimpleBacktestEngine(
            initial_capital=BACKTEST_CONFIG['initial_capital'],
            commission=BACKTEST_CONFIG['commission'],
            stamp_duty=BACKTEST_CONFIG['stamp_duty'],
            slippage=BACKTEST_CONFIG['slippage']
        )
        results = engine_runner.run(df, strategy)
        display_backtest_results(code, code, strategy.name, results)
    elif engine in ['bt', 'backtrader']:
        # Backtrader 引擎：直接使用外置策略键
        sizer_cfg = BACKTEST_CONFIG.get('sizer', {}) or {}
        result_tuple = run_backtrader_backtest(
            df=df,
            strategy_key=strategy_key,
            initial_capital=BACKTEST_CONFIG['initial_capital'],
            commission=BACKTEST_CONFIG.get('commission', 0.0001),
            stamp_duty=BACKTEST_CONFIG.get('stamp_duty', 0.0),
            min_cash_per_trade=float(sizer_cfg.get('min_cash', 20000.0)),
            max_cash_per_trade=float(sizer_cfg.get('max_cash', 50000.0))
        )
        results = None
        adapter = None
        if isinstance(result_tuple, tuple) and len(result_tuple) == 2:
            results, adapter = result_tuple
        else:
            results = result_tuple

        if results:
            print("\n✅ 回测完成！（Backtrader+外置策略）")
            # 若CLI需要显示图表，可在此处调用 adapter.plot()（CLI一般不弹窗）
    else:
        raise SystemExit("未知回测引擎，请使用 simple 或 bt")


def build_arg_parser():
    p = argparse.ArgumentParser(description="A股监控与回测系统 V2.0 (CLI 扩展)")
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument('--monitor', action='store_true', help='启动实时监控（非交互）')
    g.add_argument('--backtest', action='store_true', help='启动回测（非交互）')

    # 监控参数
    p.add_argument('--plan', type=str, help='预设方案键，如 ai_chip/gold/ev/blue_chip/tech')
    p.add_argument('--no-indicators', action='store_true', help='监控时不显示技术指标')
    p.add_argument('--refresh', type=int, help='刷新间隔（秒）')
    p.add_argument('--data-source', type=str, default=None, help='数据源 (akshare|sina|tushare|yfinance|auto)')

    # 回测参数
    p.add_argument('--engine', type=str, default='simple', help='simple 或 bt')
    p.add_argument('--strategy', type=str, help='策略键（来自 registry）')
    p.add_argument('--code', type=str, help='股票代码')
    p.add_argument('--period', type=str, choices=['short', 'mid', 'long', 'custom'], help='回测周期')
    p.add_argument('--start', type=str, help='自定义开始日期 YYYYMMDD')
    p.add_argument('--end', type=str, help='自定义结束日期 YYYYMMDD')
    return p


def main():
    """主函数"""
    parser = build_arg_parser()
    args, unknown = parser.parse_known_args()

    # 非交互 CLI
    if args.monitor:
        # 若用户指定 data_source，则覆盖全局 DATA_SOURCE
        if args.data_source:
            ds_arg = args.data_source
        else:
            ds_arg = DATA_SOURCE
        # 将 data source 通过环境或全局传递给监控入口
        # run_monitor_cli 将使用 DataSourceFactory.create 内部的逻辑
        # 暂时直接设置全局 DATA_SOURCE
        globals()['DATA_SOURCE'] = ds_arg
        run_monitor_cli(plan=args.plan, no_indicators=args.no_indicators, refresh_override=args.refresh)
        return
    if args.backtest:
        if not (args.strategy and args.code and args.period):
            parser.error("回测模式需要 --strategy --code --period 参数")
        if args.data_source:
            globals()['DATA_SOURCE'] = args.data_source
        run_backtest_cli(engine=args.engine, strategy_key=args.strategy, code=args.code,
                         period=args.period, start_date=args.start, end_date=args.end)
        return

    # 交互菜单（原逻辑保留）
    while True:
        print("\n" + "=" * 80)
        print("A股监控与回测系统 V2.0")
        print("=" * 80)
        print("\n功能菜单:")
        print("1. 实时监控")
        print("2. 策略回测")
        print("3. 数据管理")
        print("4. 查看股票分组")
        print("5. 系统说明")
        print("0. 退出")
        
        choice = input("\n请选择 (0-5): ").strip()
        
        if choice == '1':
            main_monitor()
        elif choice == '2':
            main_backtest()
        elif choice == '3':
            main_data_management()
        elif choice == '4':
            show_stock_groups()
        elif choice == '5':
            show_help()
        elif choice == '0':
            print("\n感谢使用，再见！")
            break
        else:
            print("\n无效选择，请重试")


def show_stock_groups():
    """显示股票分组"""
    print("\n" + "=" * 80)
    print("股票分组信息")
    print("=" * 80)
    
    groups = get_stock_groups()
    for group_name, stocks in groups.items():
        print(f"\n【{group_name}】({len(stocks)}只)")
        for code, name in stocks.items():
            print(f"  {name:12s} ({code})")


def show_help():
    """显示帮助信息"""
    print("\n" + "=" * 80)
    print("系统说明")
    print("=" * 80)
    print("""
本系统是模块化的A股监控与回测平台，具有以下特点：

1. 模块化架构
   - 数据源模块：支持akshare，预留tushare等接口
   - 策略模块：内置多种策略，易于扩展
   - 指标模块：常用技术指标计算
   - 回测模块：简单回测引擎，预留backtrader接口

2. 股票分组
   - AI相关：AI芯片、AI算力等
   - 半导体：芯片、集成电路
   - 新能源：电驱、锂电池
   - 黄金：黄金矿业股
   - 优质蓝筹：茅台、平安等

3. 技术指标
   - 均线：MA5/10/20/60
   - 趋势：MACD, EMA
   - 震荡：RSI, KDJ
   - 波动：布林带, ATR

4. 回测策略
   - 双均线交叉
   - 三均线策略
   - RSI超买超卖
   - MACD信号
   - 可自定义扩展

5. 未来扩展
   - 支持backtrader深度回测
   - 支持更多数据源
   - 支持更多技术指标
   - 支持机器学习策略

配置文件：src/config.py
修改此文件可自定义股票列表、指标参数等。
    """)
    
    input("\n按回车键继续...")


if __name__ == "__main__":
    main()
