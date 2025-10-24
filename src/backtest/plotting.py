"""
Plotting Module

Provides plotting utilities for backtest results with technical indicators.
"""
from __future__ import annotations

from typing import Optional, Tuple, List
import pandas as pd
import datetime

try:
    import backtrader as bt
except ImportError as exc:
    raise ImportError("backtrader is required: pip install backtrader") from exc


class TradeLogger(bt.Observer):
    """
    记录每笔交易的详细信息
    """
    lines = ('trade_log',)
    plotinfo = dict(plot=False)
    
    def __init__(self):
        self.trades = []
    
    def next(self):
        # 记录当前日期和价格
        current_date = self.data.datetime.date(0)
        close_price = self.data.close[0]
        
        # 检查是否有订单执行
        for order in self._owner.broker.orders:
            if order.status == order.Completed:
                trade_info = {
                    'date': current_date,
                    'type': 'BUY' if order.isbuy() else 'SELL',
                    'size': order.executed.size,
                    'price': order.executed.price,
                    'value': order.executed.value,
                    'commission': order.executed.comm,
                }
                if trade_info not in self.trades:
                    self.trades.append(trade_info)


def print_trade_analysis(cerebro: bt.Cerebro) -> None:
    """
    打印交易分析报告 - 包含详细的每笔交易记录
    
    Args:
        cerebro: Backtrader Cerebro 实例（已运行回测）
    """
    try:
        strats = cerebro.runstrats
        if not strats or not strats[0]:
            return
        
        strat = strats[0][0]
        
        # 获取初始和最终资金
        initial_value = cerebro.broker.startingcash
        final_value = cerebro.broker.getvalue()
        
        print("\n" + "="*80)
        print("交易日志 (Trade Log)")
        print("="*80)
        print(f"Starting Portfolio Value: {initial_value:.2f}")
        print()
        
        # 收集所有订单执行记录
        orders_log = []
        
        # 遍历策略的所有订单
        if hasattr(strat, '_orders'):
            for order in strat._orders:
                if order.status in [order.Completed]:
                    exec_date = bt.num2date(order.executed.dt)
                    orders_log.append({
                        'date': exec_date,
                        'type': 'BUY' if order.isbuy() else 'SELL',
                        'action': 'EXECUTED',
                        'size': order.executed.size,
                        'price': order.executed.price,
                        'cost': order.executed.value,
                        'commission': order.executed.comm,
                    })
        
        # 如果没有找到订单，尝试从 notify 系统获取
        if not orders_log and hasattr(strat, 'order_log'):
            orders_log = strat.order_log
        
        # 按日期排序
        if orders_log:
            orders_log.sort(key=lambda x: x['date'])
            
            # 打印每笔交易
            for log in orders_log:
                date_str = log['date'].strftime('%Y-%m-%d')
                if log['action'] == 'EXECUTED':
                    if log['type'] == 'BUY':
                        # 买入：显示佣金（保留4位小数以显示小额佣金）
                        print(f"{date_str}, BUY EXECUTED, Size {int(log['size'])}, "
                              f"Price: {log['price']:.2f}, Cost: {log['cost']:.2f}, "
                              f"Commission {log['commission']:.4f}")
                    else:
                        # 卖出：显示总费用（佣金+印花税）
                        print(f"{date_str}, SELL EXECUTED, Size {int(log['size'])}, "
                              f"Price: {log['price']:.2f}, Value: {log['cost']:.2f}, "
                              f"Commission {log['commission']:.4f}")
        else:
            print("提示: 无法获取详细交易日志，请查看下方统计摘要")
        
        print()
        print(f"Final Portfolio Value: {final_value:.2f}")
        print("="*80)
        print()
        
        # 使用 TradeAnalyzer 获取交易统计
        if hasattr(strat, 'analyzers') and hasattr(strat.analyzers, 'trades'):
            trade_analysis = strat.analyzers.trades.get_analysis()
            
            print("="*80)
            print("交易统计摘要 (Trade Analysis Summary)")
            print("="*80)
            
            # 基本统计
            total = trade_analysis.get('total', {})
            if total:
                print(f"总交易次数: {total.get('total', 0)}")
                print(f"平仓交易: {total.get('closed', 0)}")
                print(f"持仓交易: {total.get('open', 0)}")
            
            # 盈亏统计
            pnl = trade_analysis.get('pnl', {})
            if pnl:
                print(f"\n盈亏统计:")
                net_total = pnl.get('net', {}).get('total', 0)
                print(f"  净盈亏: {net_total:.2f}")
                print(f"  平均盈亏: {pnl.get('net', {}).get('average', 0):.2f}")
            
            # 盈利交易
            won = trade_analysis.get('won', {})
            if won:
                print(f"\n盈利交易:")
                print(f"  次数: {won.get('total', 0)}")
                print(f"  总盈利: {won.get('pnl', {}).get('total', 0):.2f}")
                print(f"  平均盈利: {won.get('pnl', {}).get('average', 0):.2f}")
                print(f"  最大盈利: {won.get('pnl', {}).get('max', 0):.2f}")
            
            # 亏损交易
            lost = trade_analysis.get('lost', {})
            if lost:
                print(f"\n亏损交易:")
                print(f"  次数: {lost.get('total', 0)}")
                print(f"  总亏损: {lost.get('pnl', {}).get('total', 0):.2f}")
                print(f"  平均亏损: {lost.get('pnl', {}).get('average', 0):.2f}")
                print(f"  最大亏损: {lost.get('pnl', {}).get('max', 0):.2f}")
            
            # 连续交易
            streak = trade_analysis.get('streak', {})
            if streak:
                print(f"\n连续交易:")
                won_streak = streak.get('won', {})
                if won_streak:
                    print(f"  最长连胜: {won_streak.get('longest', 0)} 次")
                lost_streak = streak.get('lost', {})
                if lost_streak:
                    print(f"  最长连亏: {lost_streak.get('longest', 0)} 次")
            
            print("="*80)
            print("提示: 图表中的 ▲ 标记买入点, ▼ 标记卖出点")
            print("="*80 + "\n")
        
    except Exception as e:
        print(f"交易分析失败: {e}")
        import traceback
        traceback.print_exc()


def plot_backtest_with_indicators(
    cerebro: bt.Cerebro,
    style: str = 'candlestick',
    show_indicators: bool = True,
    figsize: Tuple[int, int] = (16, 10),
    out_file: Optional[str] = None,
) -> None:
    """
    绘制 Backtrader 回测结果，并添加多个技术指标。
    
    参照 https://www.poloxue.com/backtrader/docs/03-quickstart/10-plotting/
    
    Args:
        cerebro: Backtrader Cerebro 实例（已运行回测）
        style: K线样式，'candlestick' 或 'line'
        show_indicators: 是否显示技术指标
        figsize: 图表大小
        out_file: 如果提供，保存图表到文件而非显示
    """
    # 先打印交易分析
    print_trade_analysis(cerebro)
    
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import matplotlib.ticker as mticker
        from matplotlib import rcParams
        from backtrader.plot import PlotScheme
        
        # 配置中文显示
        rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
        rcParams['axes.unicode_minus'] = False
        plt.rcParams['figure.figsize'] = list(figsize)
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3
        
        # 添加技术指标（参考官方文档，添加更丰富的指标）
        if show_indicators and cerebro.datas:
            data = cerebro.datas[0]  # 主数据源
            
            # === 移动平均线系列 ===
            # 1. SMA - 简单移动平均（多周期）
            bt.indicators.SimpleMovingAverage(data, period=5)
            bt.indicators.SimpleMovingAverage(data, period=20)
            
            # 2. EMA - 指数移动平均
            bt.indicators.ExponentialMovingAverage(data, period=25)
            
            # 3. WMA - 加权移动平均（子图）
            bt.indicators.WeightedMovingAverage(data, period=25, subplot=True)
            
            # === 趋势指标 ===
            # 4. MACD - 移动平均收敛发散
            macd = bt.indicators.MACD(data)
            bt.indicators.MACDHisto(data)
            
            # 5. ADX - 平均趋向指数
            bt.indicators.AverageDirectionalMovementIndex(data, period=14)
            
            # === 震荡指标 ===
            # 6. RSI - 相对强弱指标
            rsi = bt.indicators.RSI(data, period=14)
            bt.indicators.SmoothedMovingAverage(rsi, period=10)  # RSI上的均线
            
            # 7. Stochastic - 随机指标
            bt.indicators.StochasticSlow(data)
            
            # 8. CCI - 商品通道指数
            bt.indicators.CommodityChannelIndex(data, period=20)
            
            # === 波动率指标 ===
            # 9. Bollinger Bands - 布林带
            bt.indicators.BollingerBands(data, period=20, devfactor=2.0)
            
            # 10. ATR - 平均真实波幅（隐藏，用于内部计算）
            bt.indicators.ATR(data, plot=False)
            
            # === 成交量指标 ===
            # 11. Volume - 成交量（如果有的话）
            if hasattr(data, 'volume'):
                bt.indicators.SMA(data.volume, period=20, subplot=True, plotname='Volume SMA')
            
            # === 动量指标 ===
            # 12. ROC - 变动率指标
            bt.indicators.RateOfChange(data, period=12, subplot=True)
            
            # 13. Momentum - 动量指标
            bt.indicators.Momentum(data, period=14, subplot=True)
            
            print("✓ 已添加技术指标：")
            print("  均线系列: SMA(5,20), EMA(25), WMA(25)")
            print("  趋势指标: MACD, MACD_Hist, ADX")
            print("  震荡指标: RSI+SMA(10), Stochastic, CCI")
            print("  波动率: Bollinger Bands, ATR(hidden)")
            print("  动量指标: ROC, Momentum")
            print("  成交量: Volume SMA(20)")
        
        # 自定义绘图方案（红涨绿跌，A股习惯）
        class CNPlotScheme(PlotScheme):
            def __init__(self):
                super().__init__()
                # K线颜色
                self.barup = 'red'
                self.bardown = 'green'
                self.barupfill = 'red'
                self.bardownfill = 'green'
                # 成交量颜色
                self.volup = 'red'
                self.voldown = 'green'
                # 网格
                self.grid = True
                self.gridstyle = '--'
                self.gridalpha = 0.25
                # 买卖点标记 - 使用更明显、更大的标记
                self.trademarker = '^'           # 买入: 向上三角形
                self.trademarkersize = 15        # 增大到15
                self.trademarkercolor = 'red'    # 买入红色
                self.trademarkeroutline = 'darkred'  # 深红色轮廓
                self.trademarkeroutlinewidth = 2.0   # 更粗的轮廓
                
                self.sellmarker = 'v'            # 卖出: 向下三角形
                self.sellmarkersize = 15         # 增大到15
                self.sellmarkercolor = 'lime'    # 卖出亮绿色（更显眼）
                self.sellmarkeroutline = 'darkgreen'  # 深绿色轮廓
                self.sellmarkeroutlinewidth = 2.0     # 更粗的轮廓
                
                # 设置标记透明度
                self.trademarkeralpha = 0.9
                self.sellmarkeralpha = 0.9
        
        plot_kwargs = dict(
            style=style,
            iplot=False,
            figsize=figsize,
            numfigs=1,
            plotdist=0.15,
            scheme=CNPlotScheme(),
            volume=True,
            voloverlay=False,  # 成交量独立子图
            tight=True,
            # 显示买卖点 - 确保启用
            plottrades=True,
        )
        
        print("\n正在生成图表...")
        figs = cerebro.plot(**plot_kwargs)
        
        # 美化坐标轴 - 改进时间轴显示
        try:
            fig = plt.gcf()
            axes = fig.get_axes()
            
            # 获取数据的日期范围
            if cerebro.datas:
                data = cerebro.datas[0]
                num_bars = len(data)
                
                # 根据数据量调整日期标签间隔
                if num_bars > 500:
                    interval = 20  # 大数据集：每20个交易日
                elif num_bars > 250:
                    interval = 10  # 中等数据集：每10个交易日
                elif num_bars > 100:
                    interval = 5   # 小数据集：每5个交易日
                else:
                    interval = 2   # 很小数据集：每2个交易日
            else:
                interval = 5
            
            for ax in axes:
                # 改善x轴日期格式
                if hasattr(ax, 'xaxis'):
                    # 强制设置日期格式和定位器
                    ax.xaxis_date()  # 启用日期模式
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
                    # 旋转标签以避免重叠
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)
                    # 显示次要刻度
                    ax.xaxis.set_minor_locator(mdates.DayLocator())
                    # 设置x轴标签
                    ax.set_xlabel('交易日期 (Trading Date)', fontsize=9, fontweight='bold')
                
                # 改善y轴标签
                if hasattr(ax, 'yaxis'):
                    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
                    # 增加y轴标签可读性
                    ax.tick_params(axis='y', labelsize=9)
                
                # 确保网格可见
                ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
            
            # 调整布局以显示所有标签
            plt.tight_layout()
            
            # 额外调整底部空间以显示旋转的日期标签
            fig.subplots_adjust(bottom=0.15, hspace=0.3)
            
            # 强制刷新日期格式
            fig.autofmt_xdate(rotation=45, ha='right')
            
        except Exception as e:
            print(f"坐标轴格式化警告: {e}")
            pass  # 格式化失败也继续
        
        # 保存或显示
        if out_file:
            plt.savefig(out_file, dpi=300, bbox_inches='tight')
            print(f"✓ 图表已保存到: {out_file}")
            plt.close()
        else:
            print("✓ 图表生成完成，关闭窗口继续...")
            plt.show()
            
    except ImportError as e:
        print(f"❌ 绘图失败: 缺少依赖库 - {e}")
        print("提示: 请确保安装了 matplotlib")
    except Exception as e:
        print(f"❌ 绘图失败: {e}")
        import traceback
        traceback.print_exc()
