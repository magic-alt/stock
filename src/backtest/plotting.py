"""
Plotting Module

Provides plotting utilities for backtest results with technical indicators.
"""
from __future__ import annotations

from typing import Optional, Tuple, List
import pandas as pd
import datetime
import os
import traceback

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
        self.processed_orders = set()  # 记录已处理的订单，避免重复
    
    def next(self):
        # 记录当前日期和价格
        current_date = self.data.datetime.date(0)
        close_price = self.data.close[0]
        
        # 检查是否有订单执行
        for order in self._owner.broker.orders:
            if order.status == order.Completed:
                # 使用订单ID避免重复处理
                order_id = id(order)
                if order_id in self.processed_orders:
                    continue
                self.processed_orders.add(order_id)
                
                # 根据value直接计算费用（避免order.executed.comm的复杂存储方式）
                value = abs(order.executed.value)
                if order.isbuy():
                    total_cost = value * 0.0001  # 买入：仅佣金
                else:
                    total_cost = value * 0.0006  # 卖出：佣金+印花税
                
                trade_info = {
                    'date': current_date,
                    'type': 'BUY' if order.isbuy() else 'SELL',
                    'size': order.executed.size,
                    'price': order.executed.price,
                    'value': order.executed.value,
                    'commission': total_cost,
                }
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
                    # 根据value直接计算费用
                    value = abs(order.executed.value)
                    if order.isbuy():
                        total_cost = value * 0.0001  # 买入：仅佣金
                    else:
                        total_cost = value * 0.0006  # 卖出：佣金+印花税
                    
                    orders_log.append({
                        'date': exec_date,
                        'type': 'BUY' if order.isbuy() else 'SELL',
                        'action': 'EXECUTED',
                        'size': order.executed.size,
                        'price': order.executed.price,
                        'cost': order.executed.value,
                        'commission': total_cost,
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
                        # 买入：显示总佣金（保留2位小数）
                        print(f"{date_str}, BUY EXECUTED, Size {int(log['size'])}, "
                              f"Price: {log['price']:.2f}, Cost: {log['cost']:.2f}, "
                              f"Commission {log['commission']:.2f}")
                    else:
                        # 卖出：显示总费用（佣金+印花税）
                        print(f"{date_str}, SELL EXECUTED, Size {int(log['size'])}, "
                              f"Price: {log['price']:.2f}, Value: {log['cost']:.2f}, "
                              f"Commission {log['commission']:.2f}")
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
    indicator_preset: str = "clean",   # 新增：'clean' | 'full'
    auto_save: bool = False,           # 新增：自动保存到report目录
    strategy_name: str = "strategy",   # 新增：策略名称
    symbols: List[str] = None,         # 新增：股票代码列表
) -> Optional[str]:
    """
    绘制 Backtrader 回测结果，并添加技术指标。
    
    Args:
        cerebro: Backtrader Cerebro 实例（已运行回测）
        style: K线样式，'candlestick' 或 'line'
        show_indicators: 是否显示技术指标
        figsize: 图表大小
        out_file: 如果提供，保存图表到文件而非显示
        indicator_preset: 指标预设模式
            - 'clean': 仅主图(K线+布林+均线)、子图(成交量、MACD)
            - 'full' : 全量指标(MACD/ADX/RSI/Stoch/CCI等)
        auto_save: 是否自动保存到report目录（覆盖out_file）
        strategy_name: 策略名称（用于目录命名）
        symbols: 股票代码列表（用于目录命名）
    
    Returns:
        保存的目录路径（如果auto_save=True）
    """
    # 先打印交易分析
    print_trade_analysis(cerebro)
    
    # 自动保存模式：创建报告目录
    report_dir = None
    if auto_save:
        # 生成目录名：股票名_策略_时间
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        symbol_part = "_".join(symbols) if symbols else "unknown"
        # 简化符号名（去除.SH/.SZ等）
        symbol_part = symbol_part.replace(".SH", "").replace(".SZ", "").replace(".", "_")
        dir_name = f"{symbol_part}_{strategy_name}_{timestamp}"
        
        # 创建report目录
        report_dir = os.path.join("report", dir_name)
        os.makedirs(report_dir, exist_ok=True)
        
        # 设置输出文件路径
        out_file_png = os.path.join(report_dir, "backtest_result.png")
        out_file_pkl = os.path.join(report_dir, "backtest_result.pkl")
        
        print(f"\n[自动保存] 报告目录: {report_dir}")
        print(f"  - PNG图表: {out_file_png}")
        print(f"  - 原生格式: {out_file_pkl}")
    
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
        
        # 注意：技术指标已在engine.py的_run_module中添加（在cerebro.run()之前）
        # 这里不再重复添加，避免指标无历史数据的问题
        
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
                # MA线颜色（避免红绿色，使用蓝色系、紫色、橙色、青色）
                # Backtrader会循环使用这些颜色
                self.lcolors = ['blue', 'purple', 'darkorange', 'cyan', 
                               'darkblue', 'magenta', 'gold', 'teal']
        
        # 配置绘图参数
        plot_kwargs = dict(
            style=style,
            iplot=False,
            figsize=figsize,
            numfigs=1,
            plotdist=0.05,  # 减小子图间距，避免重叠
            scheme=CNPlotScheme(),
            volume=True,
            voloverlay=False,  # 关键修改：成交量独立子图，不叠加
            tight=False,  # 给标签留出空间
        )
        
        print("\n正在生成图表...")
        
        # 临时关闭matplotlib交互模式，防止弹出多余窗口
        was_interactive = plt.isinteractive()
        plt.ioff()  # 关闭交互模式
        
        # 记录绘图前的figure数量，用于检测空白图表
        figs_before = set(plt.get_fignums())
        
        try:
            figs = cerebro.plot(**plot_kwargs)
        finally:
            # 恢复原始交互模式
            if was_interactive:
                plt.ion()
        
        # 检测并关闭空白图表（cerebro.plot()可能创建多余的空figure）
        figs_after = set(plt.get_fignums())
        new_figs = figs_after - figs_before
        
        if len(new_figs) > 1:
            # 找出有效图表（包含axes的figure）
            valid_figs = []
            for fignum in new_figs:
                fig = plt.figure(fignum)
                if fig.get_axes():  # 检查是否有axes
                    valid_figs.append(fignum)
            
            # 关闭空白图表（没有axes的figure）
            for fignum in new_figs:
                if fignum not in valid_figs:
                    plt.close(fignum)
            
            if len(new_figs) - len(valid_figs) > 0:
                print(f"[OK] 已自动关闭 {len(new_figs) - len(valid_figs)} 个空白图表")
        
        # 手动添加买卖点标记（因为 Backtrader 默认标记可能不明显）
        try:
            if figs and len(figs) > 0:
                fig = figs[0][0]  # 获取第一个图表
                axes = fig.get_axes()
                
                # ========== 新增：自定义 MACD histogram 颜色 ==========
                # 遍历所有子图，找到 MACD 子图并重新绘制 histogram
                macd_found = False
                for ax in axes:
                    # 检查是否是 MACD 子图（通过图例或线条标签识别）
                    legend = ax.get_legend()
                    ylabel = ax.get_ylabel().lower() if ax.get_ylabel() else ""
                    title = ax.get_title().lower() if ax.get_title() else ""
                    
                    # 检查图例中是否包含 macd 相关标签
                    has_macd = False
                    if legend:
                        legend_texts = [t.get_text().lower() for t in legend.get_texts()]
                        has_macd = any('macd' in text or 'histo' in text or 'signal' in text 
                                      for text in legend_texts)
                    
                    if has_macd or 'macd' in ylabel or 'macd' in title:
                        # 获取所有 bar container（histogram 是 bar 类型）
                        # Backtrader 绘制的 histogram 包含在 ax.containers 中
                        bars_found = False
                        for container in ax.containers:
                            # BarContainer 包含多个 Rectangle patches
                            if hasattr(container, '__iter__'):
                                rectangles = [p for p in container if isinstance(p, matplotlib.patches.Rectangle)]
                                if rectangles:
                                    bars_found = True
                                    # 遍历每个柱状图，根据高度设置颜色
                                    colored_bars = 0
                                    for bar in rectangles:
                                        height = bar.get_height()
                                        if height > 0:
                                            bar.set_facecolor('red')
                                            bar.set_edgecolor('darkred')
                                            colored_bars += 1
                                        elif height < 0:
                                            bar.set_facecolor('green')
                                            bar.set_edgecolor('darkgreen')
                                            colored_bars += 1
                                        else:
                                            bar.set_facecolor('gray')
                                            bar.set_edgecolor('darkgray')
                                    
                                    if colored_bars > 0:
                                        print(f"[OK] MACD histogram 已着色：{colored_bars} 个柱状（>0红色，<0绿色）")
                                        macd_found = True
                                        break
                        
                        if macd_found:
                            break
                
                if not macd_found:
                    print("[提示] 未找到 MACD histogram 柱状图，可能使用了线条模式")
                # ========== MACD histogram 颜色优化结束 ==========
                
                # 获取策略实例以访问交易记录
                if cerebro.runstrats and len(cerebro.runstrats) > 0:
                    strat = cerebro.runstrats[0][0]
                    data = cerebro.datas[0]
                    
                    # 构建日期到索引的映射（Backtrader 使用数值索引作为 x 轴）
                    # 使用 Backtrader 的内部数据访问方式
                    date_to_index = {}
                    data_len = len(data)
                    
                    # 从后往前遍历，因为 Backtrader 使用负索引
                    for i in range(data_len):
                        try:
                            # 使用负索引访问历史数据
                            date_num = data.datetime[-i-1]
                            date_obj = bt.num2date(date_num)
                            date_key = date_obj.date()
                            # 存储正向索引（从0开始）
                            date_to_index[date_key] = data_len - i - 1
                        except:
                            continue
                    
                    # 收集买卖点数据
                    buy_indices = []
                    buy_prices = []
                    sell_indices = []
                    sell_prices = []
                    
                    # 从订单记录中提取买卖点
                    if hasattr(strat, '_orders'):
                        for order in strat._orders:
                            if order.status == order.Completed:
                                exec_date = bt.num2date(order.executed.dt).date()
                                price = order.executed.price
                                
                                # 将日期转换为索引
                                if exec_date in date_to_index:
                                    idx = date_to_index[exec_date]
                                    if order.isbuy():
                                        buy_indices.append(idx)
                                        buy_prices.append(price)
                                    else:
                                        sell_indices.append(idx)
                                        sell_prices.append(price)
                    
                    # 在第一个子图（价格图）上绘制标记
                    if len(axes) > 0 and (buy_indices or sell_indices):
                        price_ax = axes[0]  # 第一个子图是价格图
                        
                        # 绘制买入点（红色向上三角形）
                        if buy_indices:
                            price_ax.scatter(
                                buy_indices, buy_prices,
                                marker='^',
                                color='red',
                                s=80,  # 缩小标记，避免遮挡K线
                                alpha=0.9,
                                edgecolors='darkred',
                                linewidths=1.5,
                                zorder=5,  # 确保在其他元素上方
                                label='买入'
                            )
                        
                        # 绘制卖出点（绿色向下三角形）
                        if sell_indices:
                            price_ax.scatter(
                                sell_indices, sell_prices,
                                marker='v',
                                color='lime',
                                s=80,  # 缩小标记，避免遮挡K线
                                alpha=0.9,
                                edgecolors='darkgreen',
                                linewidths=1.5,
                                zorder=5,  # 确保在其他元素上方
                                label='卖出'
                            )
                        
                        # 添加图例
                        if buy_indices or sell_indices:
                            price_ax.legend(loc='upper left', fontsize=9, framealpha=0.8)
                            print(f"[OK] 已添加买卖点标记: {len(buy_indices)} 个买入, {len(sell_indices)} 个卖出")
        
        except Exception as e:
            print(f"[警告] 添加买卖点标记失败: {e}")
            import traceback
            traceback.print_exc()
            pass  # 标记失败也继续
        
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
        if auto_save:
            # 自动保存模式：保存PNG和原生格式
            try:
                import pickle
                
                if figs and len(figs) > 0:
                    fig_to_save = figs[0][0]
                else:
                    fig_to_save = plt.gcf()
                
                # 保存PNG格式
                fig_to_save.savefig(out_file_png, dpi=300, bbox_inches='tight')
                print(f"  ✓ PNG图表已保存")
                
                # 保存原生matplotlib格式（pickle）
                with open(out_file_pkl, 'wb') as f:
                    pickle.dump(fig_to_save, f)
                print(f"  ✓ 原生格式已保存（可用pickle加载）")
                
                # 关闭所有图表
                plt.close('all')
                
                print(f"\n[完成] 报告已保存到: {report_dir}")
                return report_dir
                
            except Exception as e:
                print(f"[错误] 保存报告失败: {e}")
                traceback.print_exc()
                return None
                
        elif out_file:
            # 传统模式：保存到指定文件
            # 只保存第一个有效的图表
            if figs and len(figs) > 0:
                fig_to_save = figs[0][0]
                fig_to_save.savefig(out_file, dpi=300, bbox_inches='tight')
                print(f"[OK] 图表已保存到: {out_file}")
            else:
                # 如果 cerebro.plot() 没有返回figure，尝试保存当前figure
                plt.savefig(out_file, dpi=300, bbox_inches='tight')
                print(f"[OK] 图表已保存到: {out_file}")
            # 关闭所有图表，避免残留
            plt.close('all')
            return None
        else:
            # 交互显示模式：只显示第一个有效的图表
            if figs and len(figs) > 0:
                # 关闭除第一个之外的所有图表
                all_figs = plt.get_fignums()
                if len(all_figs) > 1:
                    # 保留第一个figure，关闭其他
                    for fignum in all_figs[1:]:
                        plt.close(fignum)
                    print(f"[提示] 已关闭 {len(all_figs)-1} 个空白图表，只显示主图")
            
            print("[OK] 图表生成完成，关闭窗口继续...")
            plt.show()
            # 显示后关闭所有
            plt.close('all')
            return None
            
    except ImportError as e:
        print(f"[错误] 绘图失败: 缺少依赖库 - {e}")
        print("提示: 请确保安装了 matplotlib")
    except Exception as e:
        print(f"[错误] 绘图失败: {e}")
        import traceback
        traceback.print_exc()
        return None
