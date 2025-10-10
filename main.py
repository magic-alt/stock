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
from src.data_sources import DataSourceFactory
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
    
    # 选择策略
    print("\n选择回测策略:")
    print("1. 双均线交叉 (SMA Cross)")
    print("2. RSI超买超卖")
    print("3. MACD信号")
    
    strategy_choice = input("请选择策略 (1-3): ").strip()
    
    strategy_map = {
        '1': ('sma_cross', {'fast_period': 5, 'slow_period': 20}),
        '2': ('rsi', {'period': 14, 'oversold': 30, 'overbought': 70}),
        '3': ('macd', {'fast': 12, 'slow': 26, 'signal': 9})
    }
    
    if strategy_choice not in strategy_map:
        print("无效策略")
        return
    
    strategy_name, strategy_params = strategy_map[strategy_choice]
    
    # 选择回测周期
    start_date, end_date = select_backtest_period()
    if not start_date:
        return
    
    # 获取数据
    print(f"\n正在获取 {stock_name}({stock_code}) 的历史数据...")
    
    data_source = DataSourceFactory.create(DATA_SOURCE)
    df = data_source.get_stock_history(stock_code, start_date, end_date)
    
    if df.empty:
        print("获取数据失败")
        return
    
    print(f"获取到 {len(df)} 条数据")
    
    # 运行Backtrader回测
    print(f"\n使用 {strategy_name} 策略进行回测...")
    
    results = run_backtrader_backtest(
        df=df,
        strategy_name=strategy_name,
        initial_capital=BACKTEST_CONFIG['initial_capital'],
        **strategy_params
    )
    
    if results:
        print("\n✅ 回测完成！")
        
        # 询问是否绘图
        show_plot = input("\n是否显示图表? (y/n, 默认y): ").strip().lower() != 'n'
        if show_plot:
            adapter = BacktraderAdapter()
            adapter.setup(BACKTEST_CONFIG['initial_capital'])
            adapter.add_data(df)
            adapter.add_strategy(strategy_name, **strategy_params)
            adapter.run()
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
        # Backtrader 引擎：将注册表键名映射到已有适配器参数
        # 简化映射（只覆盖示例三类）
        map_bt = {
            'ma_cross': ('sma_cross', {'fast_period': 5, 'slow_period': 20}),
            'rsi': ('rsi', {'period': 14, 'oversold': 30, 'overbought': 70}),
            'macd': ('macd', {'fast': 12, 'slow': 26, 'signal': 9}),
        }
        if strategy_key not in map_bt:
            raise SystemExit("backtrader 引擎目前仅支持 ma_cross/rsi/macd 示例映射")
        strategy_name, strategy_params = map_bt[strategy_key]

        results = run_backtrader_backtest(
            df=df,
            strategy_name=strategy_name,
            initial_capital=BACKTEST_CONFIG['initial_capital'],
            **strategy_params
        )
        if results:
            print("\n✅ 回测完成！")
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
        run_monitor_cli(plan=args.plan, no_indicators=args.no_indicators, refresh_override=args.refresh)
        return
    if args.backtest:
        if not (args.strategy and args.code and args.period):
            parser.error("回测模式需要 --strategy --code --period 参数")
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
        print("3. 查看股票分组")
        print("4. 系统说明")
        print("0. 退出")
        
        choice = input("\n请选择 (0-4): ").strip()
        
        if choice == '1':
            main_monitor()
        elif choice == '2':
            main_backtest()
        elif choice == '3':
            show_stock_groups()
        elif choice == '4':
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
