# unified_backtest_framework 绘图功能使用指南

## 概述

`unified_backtest_framework.py` 现已集成 Backtrader 绘图功能，可在回测完成后自动生成带有多个技术指标的专业图表。

## 新增功能

### 1. 自动添加的技术指标

根据 [Backtrader 官方文档](https://www.poloxue.com/backtrader/docs/03-quickstart/10-plotting/)，系统在绘图时自动添加以下技术指标：

| 指标 | 说明 | 显示位置 | 参数 |
|------|------|----------|------|
| **EMA(25)** | 指数移动平均线 | 主图（与K线叠加） | period=25 |
| **WMA(25)** | 加权移动平均线 | 独立子图 | period=25, subplot=True |
| **StochasticSlow** | 慢速随机指标 | 独立子图 | 默认参数 |
| **MACD** | MACD柱状图 | 独立子图 | 默认参数 |
| **ATR** | 平均真实波幅 | 不显示 | plot=False |
| **RSI** | 相对强弱指标 | 独立子图 | 默认参数 |
| **SMA on RSI** | RSI上的平滑移动平均 | RSI子图 | period=10 |

### 2. 图表特性

- ✅ **红涨绿跌配色**：符合A股交易习惯
- ✅ **成交量独立子图**：避免与价格图重叠
- ✅ **中文字体支持**：自动配置 SimHei 字体
- ✅ **日期格式优化**：自动旋转和美化日期标签
- ✅ **多指标分层显示**：自动布局，层次清晰

## 使用方法

### 方法 1: 命令行方式

```bash
python unified_backtest_framework.py run \
    --strategy ema \
    --symbols 600519.SH \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --cash 100000 \
    --commission 0.0003 \
    --out_dir ./results \
    --plot  # 关键：启用绘图
```

**参数说明**:
- `--plot`: 启用绘图功能（新增参数）
- `--out_dir`: 输出目录（图表会保存为 `{strategy}_chart.png`）

### 方法 2: 编程方式

```python
from unified_backtest_framework import BacktestEngine, plot_backtest_with_indicators

# 创建引擎
engine = BacktestEngine(source="akshare", cache_dir="./cache")

# 运行回测（启用绘图）
metrics = engine.run_strategy(
    strategy="ema",
    symbols=["600519.SH"],
    start="2024-01-01",
    end="2024-06-30",
    cash=100000,
    commission=0.0003,
    enable_plot=True,  # 关键：启用绘图
)

# 获取 cerebro 对象并生成图表
cerebro = metrics.get("_cerebro")
if cerebro:
    plot_backtest_with_indicators(
        cerebro,
        style='candlestick',      # K线样式
        show_indicators=True,     # 显示技术指标
        figsize=(16, 10),         # 图表大小
        out_file="./result.png"   # 保存路径（None则显示窗口）
    )
```

## 可用策略列表

运行以下命令查看所有可用策略：

```bash
python unified_backtest_framework.py list
```

当前可用策略：
- `ema`: EMA 交叉策略
- `macd`: MACD 信号交叉
- `bollinger`: 布林带均值回归
- `rsi`: RSI 阈值策略
- `keltner`: Keltner 通道均值回归
- `zscore`: Z-score 均值回归
- `donchian`: 唐奇安通道突破
- `triple_ma`: 三重移动平均趋势
- `adx_trend`: ADX 趋势过滤
- `turning_point`: 多标的拐点选择
- `risk_parity`: 风险平价组合

## 完整示例

### 示例 1: 基本使用

```python
from unified_backtest_framework import BacktestEngine

# 创建引擎
engine = BacktestEngine(source="akshare")

# 运行回测并绘图
metrics = engine.run_strategy(
    strategy="ema",
    symbols=["600519.SH"],
    start="2024-01-01",
    end="2024-06-30",
    enable_plot=True,  # 启用绘图
)

# 查看结果
print(f"累计收益率: {metrics['cum_return']:.2%}")
print(f"夏普比率: {metrics['sharpe']:.2f}")
print(f"最大回撤: {metrics['mdd']:.2%}")
```

### 示例 2: 自定义绘图参数

```python
from unified_backtest_framework import BacktestEngine, plot_backtest_with_indicators
import os

# 运行回测
engine = BacktestEngine()
metrics = engine.run_strategy(
    strategy="macd",
    symbols=["600036.SH"],
    start="2024-01-01",
    end="2024-06-30",
    enable_plot=True,
)

# 自定义绘图
cerebro = metrics.get("_cerebro")
if cerebro:
    os.makedirs("./my_charts", exist_ok=True)
    plot_backtest_with_indicators(
        cerebro,
        style='candlestick',      # 或 'line'
        show_indicators=True,     # 显示技术指标
        figsize=(20, 12),         # 更大的图表
        out_file="./my_charts/macd_backtest.png"
    )
```

### 示例 3: 命令行批量测试

```bash
# 测试多个策略并生成图表
for strategy in ema macd rsi; do
    python unified_backtest_framework.py run \
        --strategy $strategy \
        --symbols 600519.SH \
        --start 2024-01-01 \
        --end 2024-06-30 \
        --out_dir ./results_$strategy \
        --plot
done
```

## 图表布局说明

生成的图表包含以下部分（从上到下）：

```
┌─────────────────────────────────────────┐
│ 主图: K线 + EMA(25) + 买卖点标记        │
├─────────────────────────────────────────┤
│ 子图1: 成交量                           │
├─────────────────────────────────────────┤
│ 子图2: WMA(25)                          │
├─────────────────────────────────────────┤
│ 子图3: StochasticSlow                   │
├─────────────────────────────────────────┤
│ 子图4: MACD                             │
├─────────────────────────────────────────┤
│ 子图5: RSI + SMA(10)                    │
└─────────────────────────────────────────┘
```

## API 参考

### `BacktestEngine.run_strategy(..., enable_plot=False)`

**新增参数**:
- `enable_plot` (bool): 是否启用绘图功能，默认 `False`

**返回值变化**:
- 当 `enable_plot=True` 时，返回的 `metrics` 字典中包含 `_cerebro` 键，存储 Cerebro 实例

### `plot_backtest_with_indicators(cerebro, ...)`

绘制回测结果图表。

**参数**:
- `cerebro` (bt.Cerebro): Backtrader Cerebro 实例（已运行回测）
- `style` (str): K线样式，'candlestick' 或 'line'，默认 'candlestick'
- `show_indicators` (bool): 是否显示技术指标，默认 `True`
- `figsize` (Tuple[int, int]): 图表大小，默认 `(16, 10)`
- `out_file` (Optional[str]): 保存路径，`None` 则显示窗口

**示例**:
```python
plot_backtest_with_indicators(
    cerebro,
    style='candlestick',
    show_indicators=True,
    figsize=(16, 10),
    out_file="./chart.png"  # 或 None 显示窗口
)
```

## 常见问题

### Q1: 如何关闭技术指标？

```python
plot_backtest_with_indicators(
    cerebro,
    show_indicators=False,  # 仅显示K线和成交量
)
```

### Q2: 如何显示图表窗口而不保存文件？

```python
plot_backtest_with_indicators(
    cerebro,
    out_file=None  # 显示窗口
)
```

### Q3: 图表中文显示乱码怎么办？

确保系统安装了中文字体（如 SimHei）。如果仍然乱码，可以手动设置：

```python
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
rcParams['axes.unicode_minus'] = False
```

### Q4: 如何自定义技术指标？

修改 `plot_backtest_with_indicators` 函数中的指标添加部分（约第 1800 行）。

### Q5: 为什么没有返回 cerebro 对象？

确保调用 `run_strategy` 时设置了 `enable_plot=True`。

## 测试脚本

### 快速测试

```bash
python quick_test_plot.py
```

### 完整测试

```bash
python test_unified_plot.py
```

## 性能考虑

- 绘图会增加 1-3 秒的执行时间
- 技术指标计算对性能影响很小（< 0.1秒）
- 建议在网格搜索（grid search）时关闭绘图，仅在最终验证时启用

## 更新日志

### V2.4.1 (2025-10-15)

#### 新增功能
- ✅ 添加 `--plot` 命令行参数
- ✅ 添加 `enable_plot` API 参数
- ✅ 集成 7 个技术指标自动显示
- ✅ 支持自定义绘图参数
- ✅ 自动保存或显示图表

#### 技术指标
- EMA(25) - 主图
- WMA(25) - 子图
- StochasticSlow - 子图
- MACD - 子图
- RSI + SMA(10) - 子图
- ATR - 隐藏

#### 文档
- 新增使用指南
- 新增 API 参考
- 新增测试脚本

## 参考资料

- [Backtrader 官方文档 - 可视化](https://www.poloxue.com/backtrader/docs/03-quickstart/10-plotting/)
- [Backtrader 技术指标参考](https://www.backtrader.com/docu/indautoref/)
- 项目文档: `docs/BACKTRADER_PLOTTING_ENHANCEMENTS.md`

---

**提示**: 技术指标仅用于图表展示和分析，不影响回测结果。策略的实际交易逻辑不包含这些指标。
