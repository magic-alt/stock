# Unified Backtest Framework - 绘图功能快速参考

## ✨ 新功能亮点

### 🎨 交易图表可视化
回测完成后自动生成专业级交易图表，包含：
- K线图 + 买卖点标记
- 7 个技术指标自动展示
- 红涨绿跌配色（A股习惯）
- 高清图表保存

## 🚀 快速开始

### 命令行方式（推荐）

```bash
python unified_backtest_framework.py run \
    --strategy ema \
    --symbols 600519.SH \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --out_dir ./results \
    --plot  # 关键：启用绘图
```

### 编程方式

```python
from unified_backtest_framework import BacktestEngine, plot_backtest_with_indicators

# 1. 创建引擎
engine = BacktestEngine(source="akshare")

# 2. 运行回测（启用绘图）
metrics = engine.run_strategy(
    strategy="ema",
    symbols=["600519.SH"],
    start="2024-01-01",
    end="2024-06-30",
    enable_plot=True,  # 关键：启用绘图
)

# 3. 获取图表
cerebro = metrics.get("_cerebro")
if cerebro:
    plot_backtest_with_indicators(cerebro, out_file="./chart.png")
```

## 📊 技术指标

| 指标 | 位置 | 说明 |
|------|------|------|
| EMA(25) | 主图 | 与K线叠加 |
| WMA(25) | 子图 | 独立显示 |
| StochasticSlow | 子图 | 慢速随机指标 |
| MACD | 子图 | MACD柱状图 |
| RSI + SMA(10) | 子图 | RSI及其平滑均线 |
| ATR | 隐藏 | 仅计算不显示 |

## 📖 可用策略

```bash
# 查看所有策略
python unified_backtest_framework.py list
```

当前支持：
- `ema` - EMA交叉
- `macd` - MACD信号
- `bollinger` - 布林带
- `rsi` - RSI阈值
- `keltner` - Keltner通道
- `zscore` - Z-score
- `donchian` - 唐奇安通道
- `triple_ma` - 三重均线
- `adx_trend` - ADX趋势
- `turning_point` - 拐点选择
- `risk_parity` - 风险平价

## 🧪 测试

### 快速测试
```bash
python quick_test_plot.py
```

### 完整测试
```bash
python test_unified_plot.py
```

## 📚 完整文档

- [完整使用指南](docs/UNIFIED_BACKTEST_PLOTTING_GUIDE.md)
- [Backtrader 绘图指南](docs/PLOT_INDICATORS_GUIDE.md)
- [快速参考](docs/PLOT_INDICATORS_QUICKREF.md)

## 🎯 使用技巧

### 1. 保存到文件
```bash
--plot --out_dir ./results  # 自动保存为 {strategy}_chart.png
```

### 2. 显示窗口
```python
plot_backtest_with_indicators(cerebro, out_file=None)  # 显示窗口
```

### 3. 关闭指标
```python
plot_backtest_with_indicators(cerebro, show_indicators=False)  # 仅K线
```

### 4. 自定义大小
```python
plot_backtest_with_indicators(cerebro, figsize=(20, 12))  # 更大的图表
```

## 💡 常见问题

**Q: 如何启用绘图？**  
A: 添加 `--plot` 参数（命令行）或 `enable_plot=True`（编程方式）

**Q: 图表保存在哪里？**  
A: `--out_dir` 指定的目录，文件名为 `{strategy}_chart.png`

**Q: 如何关闭某些指标？**  
A: 设置 `show_indicators=False` 关闭所有指标，或修改代码自定义

**Q: 支持哪些数据源？**  
A: akshare（默认）、yfinance、tushare

## 📝 更新日志

### V2.4.2 (2025-10-15)
- ✅ 新增 `--plot` 命令行参数
- ✅ 新增 7 个技术指标自动展示
- ✅ 新增 `plot_backtest_with_indicators()` 函数
- ✅ 支持自定义图表配置
- ✅ 完善文档和测试脚本

## 🔗 参考资料

- [Backtrader 官方文档](https://www.poloxue.com/backtrader/docs/03-quickstart/10-plotting/)
- [项目主文档](README_V2.md)
- [更新日志](CHANGELOG.md)

---

**提示**: 技术指标仅用于图表展示，不影响回测逻辑。
