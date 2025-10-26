# Backtrader 绘图与技术指标使用指南

## 概述

本文档说明如何使用 `BacktraderAdapter` 的增强绘图功能，该功能在基本的价格和收益展示外，还集成了多个技术指标的可视化。

## 功能特点

### 1. 基础功能
- **中文支持**: 自动配置中文字体（SimHei）
- **A股配色**: 红涨绿跌的配色方案
- **成交量独立子图**: 避免与价格图重叠
- **日期格式优化**: 自动旋转和格式化日期标签

### 2. 技术指标

根据 [Backtrader 官方文档](https://www.poloxue.com/backtrader/docs/03-quickstart/10-plotting/) 推荐，`plot()` 方法自动添加以下技术指标：

| 指标 | 说明 | 显示位置 | 参数 |
|------|------|----------|------|
| **EMA** | 指数移动平均线 | 主图（与K线一起） | period=25 |
| **WMA** | 加权移动平均线 | 独立子图 | period=25, subplot=True |
| **StochasticSlow** | 慢速随机指标 | 独立子图 | 默认参数 |
| **MACD** | MACD柱状图 | 独立子图 | 默认参数 |
| **ATR** | 平均真实波幅 | 不显示 | plot=False |
| **RSI** | 相对强弱指标 | 独立子图 | 默认参数 |
| **SMA on RSI** | RSI上的平滑移动平均 | 与RSI同子图 | period=10 |

### 3. 图表布局

```
┌─────────────────────────────────────┐
│ 主图: K线 + EMA(25)                 │
├─────────────────────────────────────┤
│ 子图1: 成交量                       │
├─────────────────────────────────────┤
│ 子图2: WMA(25)                      │
├─────────────────────────────────────┤
│ 子图3: StochasticSlow               │
├─────────────────────────────────────┤
│ 子图4: MACD                         │
├─────────────────────────────────────┤
│ 子图5: RSI + SMA(10)                │
└─────────────────────────────────────┘
```

## 使用方法

### 基本用法

```python
from src.backtest.backtrader_adapter import BacktraderAdapter, BacktraderSignalStrategy

# 1. 创建适配器
adapter = BacktraderAdapter()
adapter.setup(initial_capital=100000)

# 2. 添加数据
adapter.add_data(df_with_signals)

# 3. 添加策略
adapter.add_strategy(BacktraderSignalStrategy)

# 4. 运行回测
results = adapter.run()

# 5. 绘制图表（自动包含所有技术指标）
adapter.plot()
```

### 高级用法

#### 控制指标显示

```python
# 显示所有技术指标（默认）
adapter.plot(show_indicators=True)

# 不显示技术指标（仅显示K线和成交量）
adapter.plot(show_indicators=False)

# 自定义K线样式
adapter.plot(style='line')  # 线形图而非蜡烛图
```

#### 与 unified_backtest_framework 集成

```python
from src.backtest.backtrader_adapter import run_backtrader_backtest

# 一步完成：策略执行 + 回测 + 绘图
results, adapter = run_backtrader_backtest(
    df=data,
    strategy_key='ma_cross',
    initial_capital=100000,
    short=10,
    long=30
)

# 绘制带指标的图表
if adapter:
    adapter.plot(show_indicators=True)
```

## 示例代码

### 完整示例

参见 `test_plot_indicators.py`:

```python
import pandas as pd
import numpy as np
from src.backtest.backtrader_adapter import BacktraderAdapter, BacktraderSignalStrategy

# 生成测试数据
def generate_test_data(days=100):
    dates = pd.date_range(start='2024-01-01', periods=days, freq='D')
    close_prices = 100 + np.cumsum(np.random.randn(days) * 2)
    
    df = pd.DataFrame({
        'date': dates,
        'open': close_prices + np.random.randn(days) * 0.5,
        'high': close_prices + np.abs(np.random.randn(days) * 2),
        'low': close_prices - np.abs(np.random.randn(days) * 2),
        'close': close_prices,
        'volume': np.random.randint(1000000, 10000000, days)
    })
    
    # 生成信号
    df['ma_short'] = df['close'].rolling(window=5).mean()
    df['ma_long'] = df['close'].rolling(window=20).mean()
    df['Signal'] = 0
    df.loc[df['ma_short'] > df['ma_long'], 'Signal'] = 1
    
    return df

# 运行测试
df = generate_test_data()
adapter = BacktraderAdapter()
adapter.setup(initial_capital=100000)
adapter.add_data(df)
adapter.add_strategy(BacktraderSignalStrategy)
adapter.run()
adapter.plot(show_indicators=True)
```

## 技术细节

### 指标添加时机

技术指标在 `plot()` 方法中动态添加到图表，**不影响回测结果**。这意味着：

1. 指标仅用于可视化展示
2. 不参与实际的交易决策
3. 可以随时开启/关闭（通过 `show_indicators` 参数）

### 指标配置原理

根据 Backtrader 文档，指标通过以下方式配置：

```python
# 默认：指标显示在主图
bt.indicators.ExponentialMovingAverage(data, period=25)

# subplot=True：指标显示在独立子图
bt.indicators.WeightedMovingAverage(data, period=25, subplot=True)

# plot=False：指标不显示
bt.indicators.ATR(data, plot=False)

# 嵌套指标：在另一个指标上计算
rsi = bt.indicators.RSI(data)
bt.indicators.SmoothedMovingAverage(rsi, period=10)  # 显示在RSI子图
```

### 自定义配色方案

代码使用自定义的 `CNPlotScheme`，符合A股习惯：

```python
class CNPlotScheme(PlotScheme):
    def __init__(self):
        super().__init__()
        self.barup = 'red'        # 阳线：红色
        self.bardown = 'green'    # 阴线：绿色
        self.volup = 'red'        # 上涨成交量：红色
        self.voldown = 'green'    # 下跌成交量：绿色
```

## 常见问题

### Q1: 为什么看不到某些指标？

**A**: 检查以下几点：
1. 数据量是否足够（如 MACD 需要至少 33 根K线）
2. ATR 默认设置为 `plot=False`，不会显示
3. 确保 `show_indicators=True`

### Q2: 图表太拥挤怎么办？

**A**: 可以选择性关闭指标：

```python
# 方法1: 完全关闭指标
adapter.plot(show_indicators=False)

# 方法2: 修改代码，注释掉不需要的指标
# 在 backtrader_adapter.py 的 plot() 方法中注释相应行
```

### Q3: 如何添加自定义指标？

**A**: 在 `plot()` 方法的指标添加部分添加代码：

```python
if show_indicators and data is not None:
    # 现有指标...
    
    # 添加自定义指标
    bt.indicators.BollingerBands(data, period=20)
    bt.indicators.CCI(data)
    # ... 更多指标
```

### Q4: 图表保存为文件而非显示

**A**: 修改 `plot_kwargs` 中的参数：

```python
# 在 plot() 方法中修改
plot_kwargs = dict(
    # ... 其他参数
    iplot=False,  # False = 显示窗口; True = 返回图表对象
    # ... 
)

# 如需保存到文件
figs = self.cerebro.plot(**plot_kwargs)
if figs:
    figs[0][0].savefig('backtest_result.png', dpi=300, bbox_inches='tight')
```

## 性能考虑

- **内存占用**: 添加多个指标会增加内存使用，但对中小型数据集（< 10万条）影响不大
- **绘图速度**: 首次绘图可能需要几秒钟，后续调整窗口大小实时响应
- **数据量建议**: 
  - 最佳: 100-500条K线
  - 可接受: 500-2000条
  - 较慢: > 2000条（考虑分批或采样）

## 参考资料

- [Backtrader 官方文档 - 可视化](https://www.poloxue.com/backtrader/docs/03-quickstart/10-plotting/)
- [Backtrader 技术指标参考](https://www.backtrader.com/docu/indautoref/)
- 项目文档: `docs/BACKTRADER_PLOTTING_ENHANCEMENTS.md`

## 更新日志

### 2025-10-15
- ✨ 新增 7 个技术指标自动显示
- ✨ 新增 `show_indicators` 参数控制指标显示
- 📝 完善文档和示例代码
- 🎨 优化图表布局和配色方案

---

**提示**: 技术指标仅用于回测后的结果分析和可视化，不参与实际的交易决策逻辑。如需在策略中使用指标，请在策略类的 `__init__` 方法中添加。
