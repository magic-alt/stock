# 绘图功能增强 V2.0

## 更新日期
2025-10-23

## 概述
基于 Backtrader 官方文档 (https://www.poloxue.com/backtrader/docs/03-quickstart/10-plotting/)，对绘图模块进行了全面增强。

## 主要改进

### 1. **交易分析报告** ✅
现在运行回测时会自动显示详细的交易分析：

```
================================================================================
交易分析 (Trade Analysis)
================================================================================
总交易次数: 10
平仓交易: 9
持仓交易: 1

盈亏统计:
  净盈亏: -193.30
  平均盈亏: -21.48

盈利交易:
  次数: 2
  总盈利: 73.12
  平均盈利: 36.56
  最大盈利: 46.87

亏损交易:
  次数: 7
  总亏损: -266.42
  平均亏损: -38.06
  最大亏损: -62.15

连续交易:
  最长连胜: 1 次
  最长连亏: 3 次
================================================================================
```

**功能特点**：
- 总交易次数统计（包括平仓和持仓）
- 净盈亏和平均盈亏
- 盈利交易明细（次数、总额、平均、最大）
- 亏损交易明细（次数、总额、平均、最大）
- 连续交易统计（最长连胜/连亏）

### 2. **买卖点标记** ✅
图表中会自动显示买入和卖出时间点：

- **买入标记**: ↑ 红色向上箭头
- **卖出标记**: ↓ 绿色向下箭头

**实现方式**：
```python
class CNPlotScheme(PlotScheme):
    def __init__(self):
        super().__init__()
        # 买卖点标记
        self.trademarker = '^'  # 买入向上箭头
        self.trademarkersize = 10
        self.sellmarker = 'v'   # 卖出向下箭头
        self.sellmarkersize = 10

plot_kwargs = dict(
    # ...
    plottrades=True,  # 启用买卖点标记
)
```

### 3. **丰富的技术指标** ✅
参照 Backtrader 官方文档，添加了多个技术指标类别：

#### 移动平均线系列
- **SMA(5, 20)** - 简单移动平均（短期、中期）
- **EMA(25)** - 指数移动平均
- **WMA(25)** - 加权移动平均（独立子图）

#### 趋势指标
- **MACD** - 移动平均收敛发散
- **MACD Histogram** - MACD柱状图
- **ADX(14)** - 平均趋向指数

#### 震荡指标
- **RSI(14) + SMA(10)** - 相对强弱指标及其均线
- **Stochastic Slow** - 慢速随机指标
- **CCI(20)** - 商品通道指数

#### 波动率指标
- **Bollinger Bands(20, 2)** - 布林带
- **ATR(14)** - 平均真实波幅（隐藏）

#### 动量指标
- **ROC(12)** - 变动率指标（独立子图）
- **Momentum(14)** - 动量指标（独立子图）

#### 成交量指标
- **Volume SMA(20)** - 成交量移动平均（独立子图）

### 4. **中文显示优化** ✅
- 支持中文标题和标签
- 红涨绿跌配色（符合A股习惯）
- 优化的网格和坐标轴格式

### 5. **图表布局** ✅
- **主图**: K线 + SMA(5,20) + EMA(25) + Bollinger Bands + 买卖点标记
- **子图1**: WMA(25)
- **子图2**: MACD + MACD Histogram
- **子图3**: ADX
- **子图4**: RSI + SMA(10)
- **子图5**: Stochastic
- **子图6**: CCI
- **子图7**: ROC
- **子图8**: Momentum
- **子图9**: Volume + Volume SMA(20)

## 使用方法

### 命令行方式
```bash
python unified_backtest_framework.py run \
  --symbol 600519.SH \
  --strategy macd \
  --start 2023-01-01 \
  --end 2023-12-31 \
  --plot
```

### 参数说明
- `--plot`: 启用绘图功能
- 图表会自动显示所有技术指标和买卖点标记
- 关闭图表窗口后程序继续运行

### 保存图表
如果指定了 `--out_dir`，图表会自动保存：
```bash
python unified_backtest_framework.py run \
  --symbol 600519.SH \
  --strategy macd \
  --start 2023-01-01 \
  --end 2023-12-31 \
  --out_dir reports \
  --plot
```

图表保存位置: `reports/macd_chart.png`

## 技术实现

### 交易分析
使用 Backtrader 内置的 `TradeAnalyzer`：
```python
def print_trade_analysis(cerebro: bt.Cerebro) -> None:
    strat = cerebro.runstrats[0][0]
    trade_analysis = strat.analyzers.trades.get_analysis()
    # 提取并显示交易统计
```

### 技术指标添加
在绘图前动态添加指标：
```python
if show_indicators and cerebro.datas:
    data = cerebro.datas[0]
    
    # 添加各类指标
    bt.indicators.SimpleMovingAverage(data, period=5)
    bt.indicators.MACD(data)
    bt.indicators.RSI(data, period=14)
    # ...
```

### 买卖点标记
通过自定义 `PlotScheme` 配置：
```python
class CNPlotScheme(PlotScheme):
    def __init__(self):
        super().__init__()
        self.trademarker = '^'      # 买入标记
        self.sellmarker = 'v'       # 卖出标记
        self.trademarkersize = 10
        self.sellmarkersize = 10
```

## 示例输出

### 交易分析示例
```
总交易次数: 10
平仓交易: 9
持仓交易: 1

盈亏统计:
  净盈亏: -193.30
  平均盈亏: -21.48

盈利交易:
  次数: 2
  总盈利: 73.12
  平均盈利: 36.56
  最大盈利: 46.87

亏损交易:
  次数: 7
  总亏损: -266.42
  平均亏损: -38.06
  最大亏损: -62.15

连续交易:
  最长连胜: 1 次
  最长连亏: 3 次
```

### 技术指标输出
```
✓ 已添加技术指标：
  均线系列: SMA(5,20), EMA(25), WMA(25)
  趋势指标: MACD, MACD_Hist, ADX
  震荡指标: RSI+SMA(10), Stochastic, CCI
  波动率: Bollinger Bands, ATR(hidden)
  动量指标: ROC, Momentum
  成交量: Volume SMA(20)
```

## 与旧版对比

### V1.0（旧版）
- ❌ 无交易明细
- ❌ 无买卖点标记
- ⚠️ 仅5个基础指标

### V2.0（新版）
- ✅ 完整交易分析报告
- ✅ 图表买卖点标记
- ✅ 13个技术指标
- ✅ 多子图布局
- ✅ 中文显示优化

## 注意事项

1. **依赖库**: 需要 matplotlib
   ```bash
   pip install matplotlib
   ```

2. **显示问题**: 如果中文显示异常，可能需要安装中文字体：
   - Windows: 自动使用 SimHei
   - Linux/Mac: 需要安装中文字体

3. **性能**: 添加多个指标会增加绘图时间，但不影响回测性能

4. **自定义**: 可以在 `plotting.py` 中修改指标参数和显示方式

## 参考资料

- Backtrader 绘图文档: https://www.poloxue.com/backtrader/docs/03-quickstart/10-plotting/
- Backtrader 指标库: https://www.backtrader.com/docu/indautoref/
- TradeAnalyzer 文档: https://www.backtrader.com/docu/analyzers/tradeanalyzer/

## 更新日志

### V2.0 (2025-10-23)
- ✅ 新增交易分析报告
- ✅ 新增买卖点标记
- ✅ 扩展技术指标（5→13个）
- ✅ 优化图表布局
- ✅ 改进中文显示

### V1.0 (2025-10-10)
- 基础绘图功能
- 5个基础技术指标
