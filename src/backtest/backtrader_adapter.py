"""
Backtrader 适配器（外置策略版 + 绘图优化 + 风险控制）

要点：
1) 使用外置策略生成的 pandas 'Signal' 执行交易；
2) 自定义 CNPlotScheme（红涨绿跌），成交量独立子图；
3) run_backtrader_backtest 返回 (results, adapter)，主流程直接 adapter.plot()，避免重复回测打印；
4) 执行器支持 stop_loss_pct / take_profit_pct 简易风控；
"""

import pandas as pd
import backtrader as bt
from datetime import datetime
from backtrader.plot import PlotScheme

# 依赖策略注册表，统一创建外置策略实例
try:
    from src.strategies.registry import create_strategy
except Exception:
    # 兼容导入路径
    from strategies.registry import create_strategy


class BacktraderAdapter:
    """
    Backtrader适配器
    
    仅负责将 DataFrame 转为 Backtrader 的 Data Feed，并运行 Cerebro
    """
    def __init__(self):
        self.cerebro = None
        self._last_results = None  # 保存最近一次 run() 返回，供 plot 使用

    # -------- 自定义按金额下单的 Sizer --------
    class CashValueSizer(bt.Sizer):
        """
        按金额（现金）确定买入股数：
          - 买入：用不超过 max_cash 的现金买入，至少满足 min_cash；
          - 卖出：若直接 close()，Backtrader 会自己平仓；若 sell() 开空则返回与买入相同的手数逻辑。
        """
        params = (('min_cash', 20000.0), ('max_cash', 50000.0),)

        def _getsizing(self, comminfo, cash, data, isbuy):
            price = float(data.close[0])
            if price <= 0 or cash <= 0:
                return 0
            if isbuy:
                # 在 max_cash 内尽量买更多；若 max_cash>现金，则受现金约束
                budget = min(cash, float(self.p.max_cash))
                size = int(budget // price)
                # 如果按 max_cash 算出来为 0，尝试按 min_cash 兜底
                if size <= 0 and self.p.min_cash <= cash:
                    size = int(float(self.p.min_cash) // price)
                return max(size, 0)
            else:
                # 对于 sell()（若允许做空可改逻辑）；对于 close()，size 无视
                position = self.broker.getposition(data)
                return abs(int(position.size))

    def setup(self, initial_capital: float = 100000, commission: float = 0.0001,
              stamp_duty: float = 0.0, min_cash_per_trade: float = 20000.0,
              max_cash_per_trade: float = 50000.0):
        try:
            self.cerebro = bt.Cerebro()
            self.cerebro.broker.setcash(initial_capital)
            # 使用自定义 CommissionInfo：基础佣金按 commission，印花税仅在卖出时收取（stamp_duty）
            class StampDutyCommission(bt.CommInfoBase):
                params = (
                    ('commission', commission),
                    ('stamp_duty', stamp_duty),
                    ('stocklike', True),
                )

                def _getcommission(self, size, price, pseudoexec=False):
                    # size > 0 表示买入，size < 0 表示卖出
                    base = abs(size) * price * float(self.p.commission)
                    stamp = 0.0
                    if size < 0 and float(self.p.stamp_duty) > 0:
                        stamp = abs(size) * price * float(self.p.stamp_duty)
                    return base + stamp

            # 注册自定义手续费模型
            self.cerebro.broker.addcommissioninfo(StampDutyCommission())
            # 使用“按金额下单”的自定义 Sizer（每笔 2~5 万）
            self.cerebro.addsizer(self.CashValueSizer, min_cash=min_cash_per_trade, max_cash=max_cash_per_trade)
            return True
        except ImportError:
            print("❌ Backtrader未安装，请运行: pip install backtrader")
            return False
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            return False

    def add_data(self, df: pd.DataFrame, name: str = 'stock'):
        if self.cerebro is None:
            print("❌ 请先调用setup()初始化")
            return False

        try:
            data_df = df.copy()

            # ===== 1) 统一拍平/字符串化列名，避免 tuple 列名触发 backtrader 的 .lower() 报错 =====
            # 如果是 MultiIndex，扁平化为 level0_level1_... 的字符串列名
            if isinstance(data_df.columns, pd.MultiIndex):
                data_df.columns = [
                    "_".join([str(x) for x in col if x is not None]).strip("_")
                    for col in data_df.columns.values
                ]

            # 将任何非字符串列名强制转换为字符串（元组 -> 合并或单元素解包）
            safe_cols = []
            for col in data_df.columns:
                if isinstance(col, str):
                    safe_cols.append(col)
                elif isinstance(col, tuple):
                    # 单元素元组 ('open',) -> 'open'，否则按下划线连接
                    safe_cols.append(str(col[0]) if len(col) == 1 else "_".join(map(str, col)))
                else:
                    safe_cols.append(str(col))
            data_df.columns = safe_cols

            # ===== 2) 列名标准化（中英文&缩写全覆盖）=====
            # 先做一个“通用映射”函数：对每个列名做小写比对以最大化兼容
            def _normalize_name(col: str) -> str:
                c = col.strip()
                cl = c.lower()
                # 日期
                if cl in ('date', 'datetime', '时间', '日期'):
                    return 'date'
                # 开盘
                if cl in ('open', 'o', '开盘', '今开', '开'):
                    return 'open'
                # 最高
                if cl in ('high', 'h', '最高'):
                    return 'high'
                # 最低
                if cl in ('low', 'l', '最低'):
                    return 'low'
                # 收盘
                if cl in ('close', 'c', '收盘', '收'):
                    return 'close'
                # 成交量
                if cl in ('volume', 'vol', 'v', '成交量', '量'):
                    return 'volume'
                # 允许保留其他字段（如 Signal/指标等）原名
                return c

            data_df.rename(columns={c: _normalize_name(c) for c in data_df.columns}, inplace=True)

            if 'date' in data_df.columns:
                data_df['date'] = pd.to_datetime(data_df['date'])
                data_df.set_index('date', inplace=True)
            elif data_df.index.name != 'date' and not isinstance(data_df.index, pd.DatetimeIndex):
                # 如果没有日期列且索引不是日期，尝试转换索引为日期
                try:
                    data_df.index = pd.to_datetime(data_df.index)
                except:
                    # 如果转换失败，创建一个默认的日期索引
                    data_df.index = pd.date_range(start='2024-01-01', periods=len(data_df), freq='D')

            # ===== 3) 关键列存在性检查 + 兜底 =====
            # 尽量保证 backtrader 所需 5 列具备；缺失则尽可能从 close 推断/用 0 填充
            if 'close' not in data_df.columns:
                print("❌ 缺少必需列: close")
                return False
            if 'open' not in data_df.columns:
                data_df['open'] = data_df['close']
            if 'high' not in data_df.columns:
                data_df['high'] = data_df['close']
            if 'low' not in data_df.columns:
                data_df['low'] = data_df['close']
            if 'volume' not in data_df.columns:
                data_df['volume'] = 0

            # 如果包含策略预先计算的 'Signal' 列，则使用带自定义行的 Data Feed
            if 'Signal' in data_df.columns or 'signal' in data_df.columns:
                if 'signal' in data_df.columns and 'Signal' not in data_df.columns:
                    data_df.rename(columns={'signal': 'Signal'}, inplace=True)

                class SignalPandasData(bt.feeds.PandasData):
                    lines = ('signal',)
                    params = (
                        ('datetime', None),
                        ('open', 'open'),
                        ('high', 'high'),
                        ('low', 'low'),
                        ('close', 'close'),
                        ('volume', 'volume'),
                        ('openinterest', -1),
                        ('signal', 'Signal'),
                    )

                data = SignalPandasData(dataname=data_df)
            else:
                data = bt.feeds.PandasData(
                    dataname=data_df,
                    datetime=None,
                    open='open',
                    high='high',
                    low='low',
                    close='close',
                    volume='volume',
                    openinterest=-1
                )

            self.cerebro.adddata(data, name=name)
            return True
        except Exception as e:
            print(f"❌ 添加数据失败: {e}")
            return False

    def add_strategy(self, strategy_class, **kwargs):
        if self.cerebro is None:
            print("❌ 请先调用setup()初始化")
            return False

        try:
            # 现在仅支持直接传入 Backtrader 的策略类（例如 BacktraderSignalStrategy），
            # 或者用户自定义的 bt.Strategy 子类；不再映射内置字符串名。
            self.cerebro.addstrategy(strategy_class, **kwargs)
            return True
        except Exception as e:
            print(f"❌ 添加策略失败: {e}")
            return False

    def run(self):
        if self.cerebro is None:
            print("❌ 请先调用setup()初始化")
            return None

        try:
            print("\n开始运行回测...")
            start_value = self.cerebro.broker.getvalue()
            print(f"初始资金: {start_value:,.2f}")

            # 添加详细错误捕获
            import traceback
            try:
                results = self.cerebro.run()
            except AttributeError as ae:
                print(f"❌ AttributeError during cerebro.run(): {ae}")
                print("完整堆栈:")
                traceback.print_exc()
                raise
            except Exception as e:
                print(f"❌ 其他错误 during cerebro.run(): {type(e).__name__}: {e}")
                traceback.print_exc()
                raise
                
            self._last_results = results

            end_value = self.cerebro.broker.getvalue()
            print(f"最终资金: {end_value:,.2f}")
            print(f"收益: {end_value - start_value:+,.2f} ({(end_value / start_value - 1) * 100:+.2f}%)")

            return results
        except Exception as e:
            print(f"❌ 运行回测失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def plot(self, style='candlestick'):
        if self.cerebro is None:
            print("❌ 请先调用setup()初始化并运行回测")
            return

        try:
            print("\n正在生成图表...")
            
            # 配置matplotlib中文显示
            try:
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                from matplotlib import rcParams
                
                # 设置中文字体（如果可用）
                rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
                rcParams['axes.unicode_minus'] = False
                
                # 设置日期格式
                plt.rcParams['figure.figsize'] = [16, 10]
                plt.rcParams['axes.grid'] = True
                plt.rcParams['grid.alpha'] = 0.3
                
            except ImportError:
                pass  # matplotlib不可用时继续
            
            # ==== 自定义绘图方案（红涨绿跌 + 成交量独立子图） ====
            class CNPlotScheme(PlotScheme):
                def __init__(self):
                    super().__init__()
                    # K 线与成交量配色（A股：红涨绿跌）
                    self.barup = 'red'
                    self.bardown = 'green'
                    self.barupfill = 'red'
                    self.bardownfill = 'green'
                    self.volup = 'red'
                    self.voldown = 'green'
                    # 其他
                    self.grid = True
                    self.gridstyle = '--'
                    self.gridalpha = 0.25
                    # self.loc = 'best'

            plot_kwargs = dict(
                style=style,
                iplot=False,
                figsize=(16, 9),
                numfigs=1,
                plotdist=0.15,
                scheme=CNPlotScheme(),
                volume=True,         # 显示成交量
                voloverlay=False,    # 成交量独立子图，避免价格图底部大片绿色
                tight=True,
            )

            # 注意：cerebro.plot() 不需要传 run() 的返回值；传入会被当作自定义 plotter 而报错
            figs = self.cerebro.plot(**plot_kwargs)

            # ====== 坐标轴与刻度进一步美化 ======
            try:
                import matplotlib.pyplot as plt
                import matplotlib.ticker as mticker
                fig = plt.gcf()
                axes = fig.get_axes()

                for ax in axes:
                    # 改善x轴日期格式
                    if hasattr(ax, 'xaxis'):
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
                        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

                    # 改善y轴标签
                    if hasattr(ax, 'yaxis'):
                        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))

                plt.tight_layout()
                
            except:
                pass  # 如果格式化失败也继续
                
        except Exception as e:
            print(f"❌ 绘图失败: {e}")
            print("提示: 可能需要安装 matplotlib")


# ============ 信号驱动的 Backtrader 策略 ============

class BacktraderSignalStrategy(bt.Strategy):
    """
    通用信号执行器：依赖数据源中的 `signal` 行（来自 DataFrame 的 'Signal' 列）。
    规则（默认长/平）：
      - signal > 0 且无仓位 → 买入
      - signal <= 0 且有多头 → 平仓
    可选：allow_short=True 开启做空：
      - signal < 0 且无仓位 → 卖出建立空头
      - signal >= 0 且有空头 → 平空
    """
    params = (
        ('allow_short', False),
        ('stop_loss_pct', None),     # 例如 0.03 表示 3% 止损
        ('take_profit_pct', None),   # 例如 0.06 表示 6% 止盈
    )

    def __init__(self):
        # 若数据无 signal 行，将抛错；请在 add_data 前准备好 'Signal' 列
        self.signal = self.datas[0].signal
        # 交易记录，用于调试
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.entry_price = None

    def log(self, txt, dt=None):
        """日志函数"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}: {txt}')

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入执行: 价格 {order.executed.price:.2f}, 成本 {order.executed.value:.2f}, 佣金 {order.executed.comm:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                self.entry_price = order.executed.price
            elif order.issell():
                self.log(f'卖出执行: 价格 {order.executed.price:.2f}, 成本 {order.executed.value:.2f}, 佣金 {order.executed.comm:.2f}')
                # 若是平仓，将入场价清空
                if self.position.size == 0:
                    self.entry_price = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')
        self.order = None

    def notify_trade(self, trade):
        """交易完成通知"""
        if not trade.isclosed:
            return
        self.log(f'交易盈亏: 毛利 {trade.pnl:.2f}, 净利 {trade.pnlcomm:.2f}')

    def next(self):
        # 防止重复下单
        if self.order:
            return

        sig = int(round(self.signal[0])) if not pd.isna(self.signal[0]) else 0
        pos = self.position.size if self.position else 0
        price = self.data.close[0]

        # 多头逻辑
        # 多头逻辑
        if sig > 0:
            if pos <= 0:  # 空仓或空头 -> 开多 / 平空后开多
                self.log(f'买入信号: 价格 {price:.2f}, 信号值 {sig}')
                self.order = self.buy()
        else:
            if pos > 0:
                self.log(f'平多信号: 价格 {price:.2f}, 信号值 {sig}')
                self.order = self.close()  # 平多

        # 简易风控（仅多头）：达到止损/止盈阈值则平仓
        if pos > 0 and self.entry_price:
            sl = self.p.stop_loss_pct
            tp = self.p.take_profit_pct
            if sl is not None and price <= self.entry_price * (1 - float(sl)):
                self.log(f'止损触发: 入场 {self.entry_price:.2f} -> 当前 {price:.2f} (阈值 {sl:.1%})')
                self.order = self.close()
            elif tp is not None and price >= self.entry_price * (1 + float(tp)):
                self.log(f'止盈触发: 入场 {self.entry_price:.2f} -> 当前 {price:.2f} (阈值 {tp:.1%})')
                self.order = self.close()

        # 做空（可选）
        if self.p.allow_short:
            if sig < 0:
                if pos >= 0:  # 空仓或多头 -> 开空
                    self.log(f'卖出信号: 价格 {price:.2f}, 信号值 {sig}')
                    self.order = self.sell()
            else:
                if pos < 0:
                    self.log(f'平空信号: 价格 {price:.2f}, 信号值 {sig}')
                    self.order = self.close()  # 平空


def run_backtrader_backtest(df: pd.DataFrame, strategy_key,
                            initial_capital: float = 100000,
                            allow_short: bool = False,
                            commission: float = 0.0001,
                            stamp_duty: float = 0.0,
                            min_cash_per_trade: float = 20000.0,
                            max_cash_per_trade: float = 50000.0,
                            **strategy_params):
    """
    使用 **外置策略（registry）** 生成信号后，在 Backtrader 中复盘执行。

    Args:
        df: 历史数据 DataFrame（包含：日期/开盘/最高/最低/收盘/成交量）
        strategy_key: 策略注册表键（如 'ma_cross'/'rsi'/'macd'/...）
        initial_capital: 初始资金
        allow_short: 是否允许做空（默认 False）
        **strategy_params: 传递给外置策略的参数（覆盖默认）
    """
    # 1) 生成外置策略信号（Signal 列）
    # 兼容 strategy_key 传入 tuple 的场景（如 (key, params) 或注册表三元组）
    try:
        strat = None
        key_to_use = strategy_key

        # 如果传入的是 (key, params) 形式
        if isinstance(strategy_key, tuple):
            if len(strategy_key) == 2 and isinstance(strategy_key[0], str) and isinstance(strategy_key[1], dict):
                key_to_use, extra = strategy_key
                strategy_params = {**extra, **strategy_params}
            else:
                # 可能是注册表的三元组：(Class, defaults, desc) 或类似结构
                try:
                    cls = None
                    defaults = {}
                    # (Class, defaults, ...) 形式
                    if len(strategy_key) >= 2 and callable(strategy_key[0]):
                        cls = strategy_key[0]
                        if isinstance(strategy_key[1], dict):
                            defaults = strategy_key[1]
                    if cls is not None:
                        merged = {**defaults, **strategy_params}
                        strat = cls(**merged)
                except Exception:
                    pass

        # 正常的字符串 key 走注册表创建
        if strat is None and isinstance(key_to_use, str):
            strat = create_strategy(key_to_use, **strategy_params)

        # 兜底：直接从注册表里取出定义并实例化
        if strat is None:
            try:
                # 兼容不同命名：_REGISTRY / REGISTRY / get_registry()
                from src.strategies import registry as _reg
                _d = None
                if hasattr(_reg, "get_registry"):
                    _d = _reg.get_registry()
                elif hasattr(_reg, "_REGISTRY"):
                    _d = _reg._REGISTRY
                elif hasattr(_reg, "REGISTRY"):
                    _d = _reg.REGISTRY
                if isinstance(_d, dict):
                    spec = _d.get(strategy_key if isinstance(strategy_key, str) else str(strategy_key))
                    if spec and isinstance(spec, (tuple, list)) and callable(spec[0]):
                        cls = spec[0]
                        defaults = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                        merged = {**defaults, **strategy_params}
                        strat = cls(**merged)
            except Exception:
                pass

        if strat is None:
            raise ValueError(f"无法根据 strategy_key={strategy_key} 创建策略实例")
    except Exception as e:
        print(f"❌ 创建策略失败: {e}")
        return None

    df_sig = strat.generate_signals(df.copy())
    if 'Signal' not in df_sig.columns:
        print("❌ 外置策略未生成 'Signal' 列")
        return None

    # 2) 启动 BT，加载带信号的数据
    adapter = BacktraderAdapter()
    if not adapter.setup(initial_capital=initial_capital,
                         commission=commission,
                         stamp_duty=stamp_duty,
                         min_cash_per_trade=min_cash_per_trade,
                         max_cash_per_trade=max_cash_per_trade):
        return None
    if not adapter.add_data(df_sig):
        return None

    # 3) 使用通用执行器，根据 signal 行下单
    if not adapter.add_strategy(BacktraderSignalStrategy, allow_short=allow_short):
        return None

    # 4) 运行
    results = adapter.run()
    # 返回 (results, adapter)，让调用方直接 adapter.plot()，避免为绘图再跑一遍回测
    return results, adapter
