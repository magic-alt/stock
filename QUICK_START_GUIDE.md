# 🚀 模块化回测系统 - 快速上手指南

## 📦 新增功能一览

### 1. 数据下载模块

#### AKShare (A股市场)
```python
from src.data_sources.akshare_source import AKShareDataSource

source = AKShareDataSource()

# 批量下载（自动CSV缓存）
data = source.load_stock_daily_batch(
    symbols=['000001', '600519'],
    start='2024-01-01',
    end='2024-12-31',
    cache_dir='./cache'
)
```

#### YFinance (全球市场)
```python
from src.data_sources.yfinance_source import YFinanceDataSource

source = YFinanceDataSource()

# 下载全球股票（美股、港股、A股）
data = source.download_batch_with_retry(
    symbols=['AAPL', '0700.HK', '600519.SH'],
    start='2024-01-01',
    end='2024-12-31',
    max_retries=3
)
```

### 2. 报告生成模块

```python
from src.backtest.report_generator import quick_report
import pandas as pd

# 快速生成完整报告（指标+图表）
results = quick_report(
    strategy_name='My_Strategy',
    nav_series=nav_series,  # 你的净值序列
    benchmark_series=benchmark_series,  # 基准净值（可选）
    output_dir='./reports'
)

# 查看指标
print(f"累计收益: {results['metrics']['total_return']:.2f}%")
print(f"夏普比率: {results['metrics']['sharpe_ratio']:.2f}")
print(f"最大回撤: {results['metrics']['max_drawdown']:.2f}%")

# 查看生成的文件
print(f"净值图: {results['nav_plot']}")
print(f"回撤图: {results['drawdown_plot']}")
```

---

## 🎯 典型使用场景

### 场景1: A股策略回测

```python
from src.data_sources.akshare_source import AKShareDataSource
from src.backtest.report_generator import quick_report
import pandas as pd

# 1. 下载数据
source = AKShareDataSource()
data = source.load_stock_daily_batch(
    symbols=['000001', '600519', '000333'],
    start='2023-01-01',
    end='2024-01-01',
    cache_dir='./cache'
)

# 2. 策略逻辑（示例）
for symbol, df in data.items():
    print(f"{symbol}: {len(df)} 条数据")

# 3. 生成净值曲线（示例：模拟净值）
nav_series = pd.Series([1.0, 1.05, 1.10, 1.08, 1.15])

# 4. 生成报告
results = quick_report(
    strategy_name='A股策略',
    nav_series=nav_series,
    output_dir='./reports'
)

print("✅ 完成！")
```

### 场景2: 全球市场策略

```python
from src.data_sources.yfinance_source import YFinanceDataSource
from src.backtest.report_generator import ReportGenerator

# 下载美股 + 指数
source = YFinanceDataSource()
data = source.load_stock_daily_batch(
    symbols=['AAPL', 'MSFT', 'GOOGL'],
    start='2023-01-01',
    end='2024-01-01'
)

# 下载基准（S&P 500）
benchmark_data = source.load_index_daily(
    index_code='^GSPC',
    start='2023-01-01',
    end='2024-01-01'
)

# 生成报告...
```

---

## 🧪 测试命令

### 测试报告生成 ✅
```bash
python test_report_generator.py
```

**预期输出**:
- ✅ 指标计算通过
- ✅ 报告生成通过
- ✅ 快速报告通过
- 📁 生成6个PNG图 + 2个JSON + 2个TXT

### 测试数据下载
```bash
python test_data_download.py
```

**预期输出**:
- ✅ AKShare批量下载
- ✅ CSV缓存工作
- ✅ YFinance下载
- ✅ 重试机制正常

---

## 📊 性能指标说明

### 基础指标
- **累计收益率**: 总收益百分比
- **年化收益率**: 按年计算的收益率
- **年化波动率**: 风险度量（越低越稳定）
- **夏普比率**: 风险调整后收益（>1为优秀）
- **最大回撤**: 最大损失幅度

### 交易指标
- **交易次数**: 总交易笔数
- **胜率**: 盈利交易占比
- **盈亏比**: 平均盈利/平均亏损

### 对比指标
- **基准收益率**: 市场基准表现
- **超额收益**: 策略收益 - 基准收益

---

## 🎨 生成的报告内容

### 文本报告 (TXT + JSON)
```
回测报告 - My_Strategy
================================================================================

策略参数:
  period: 20
  threshold: 0.02

性能指标:
  累计收益率: 15.50%
  年化收益率: 12.30%
  夏普比率: 1.85
  最大回撤: 8.20%
  ...
```

### 图表报告 (PNG)
1. **净值对比图**: 策略 vs 基准
2. **回撤曲线**: 显示历史回撤
3. **收益率分布**: 直方图 + 均值线

### 数据导出 (CSV)
- 日期 + 净值数据
- 可导入Excel进一步分析

---

## 💡 高级技巧

### 技巧1: 使用缓存加速开发

```python
# 第一次：下载并缓存（慢）
data = source.load_stock_daily_batch(
    symbols=['000001', '600519'],
    start='2023-01-01',
    end='2024-01-01',
    cache_dir='./cache',
    force_refresh=True  # 强制下载
)

# 第二次及以后：从缓存加载（快）
data = source.load_stock_daily_batch(
    symbols=['000001', '600519'],
    start='2023-01-01',
    end='2024-01-01',
    cache_dir='./cache',
    force_refresh=False  # 使用缓存
)
```

### 技巧2: 批量指标计算

```python
from src.backtest.report_generator import BacktestMetrics

# 单独计算某个指标
sharpe = BacktestMetrics.calculate_sharpe_ratio(nav_series)
max_dd = BacktestMetrics.calculate_max_drawdown(nav_series)[0]

# 一次性计算所有指标
metrics = BacktestMetrics.calculate_all_metrics(
    nav_series,
    benchmark_series,
    trades
)

print(metrics)  # 所有指标的字典
```

### 技巧3: 自定义报告内容

```python
from src.backtest.report_generator import ReportGenerator

generator = ReportGenerator(output_dir='./reports')

# 只生成特定图表
generator.plot_nav_comparison(
    {'策略A': nav1, '策略B': nav2, '基准': benchmark},
    title='多策略对比',
    filename='comparison.png'
)

generator.plot_drawdown(
    nav_series,
    title='回撤分析',
    filename='drawdown.png'
)
```

---

## 🔧 常见问题

### Q1: YFinance下载速度慢？
**A**: 使用 `download_batch_with_retry()` 带重试机制，失败会自动重试。

### Q2: AKShare被限流？
**A**: 已内置限速保护（0.3-0.5秒），并有自动重试。如仍被限，增大 `time.sleep()` 延迟。

### Q3: 如何使用自己的净值数据？
**A**: 创建 pandas Series，索引为日期：
```python
import pandas as pd
nav_series = pd.Series(
    [1.0, 1.05, 1.10],  # 净值
    index=pd.to_datetime(['2024-01-01', '2024-02-01', '2024-03-01'])
)
```

### Q4: 如何添加交易记录到报告？
**A**: 传入交易列表：
```python
trades = [
    {'date': '2024-01-15', 'symbol': '000001', 'pnl': 1500},
    {'date': '2024-02-20', 'symbol': '600519', 'pnl': -800},
]

generator.generate_complete_report(
    strategy_name='My_Strategy',
    params={},
    nav_series=nav_series,
    trades=trades  # 添加交易记录
)
```

---

## 📚 更多资源

- 📖 完整文档: `docs/REFACTORING_COMPLETED_REPORT.md`
- 🔍 详细指南: `docs/MODULAR_REFACTORING_REPORT.md`
- 🧪 测试代码: `test_report_generator.py`, `test_data_download.py`

---

## ✨ 特色功能

### ✅ 稳定的数据下载
- 多数据源自动切换（AKShare）
- 自动重试机制（YFinance）
- 智能限速防封禁
- CSV缓存提速

### ✅ 专业的报告生成
- 10+项性能指标
- 3种可视化图表
- JSON/TXT/CSV多格式
- 一键生成全部报告

### ✅ 灵活的扩展性
- 模块化设计
- 统一接口
- 易于集成
- 支持自定义

---

**快速开始**: 运行 `python test_report_generator.py` 查看示例！

**最后更新**: 2025-10-12
