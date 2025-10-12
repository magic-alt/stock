# 🚀 V2.4.0 模块化系统快速开始

> **注意**: 本指南适用于V2.4.0及以上版本。如果您使用的是旧版本，请先查看升级指南。

## 📦 安装依赖

```bash
pip install backtrader pandas numpy matplotlib akshare yfinance
```

## 🎯 5分钟快速开始

### 1. 列出所有可用策略

```python
from src.strategies import list_backtrader_strategies

strategies = list_backtrader_strategies()
for name, desc in strategies.items():
    print(f"{name:15s} - {desc}")
```

**输出示例**:
```
ema             - EMA crossover strategy
macd            - MACD signal crossover
bollinger       - Bollinger band mean reversion
rsi             - RSI threshold strategy
keltner         - Keltner Channel mean reversion
zscore          - Rolling-mean z-score mean reversion
donchian        - Donchian channel breakout
triple_ma       - Triple moving average trend
adx_trend       - ADX(+DI/-DI) trend filter
```

### 2. 创建策略并运行回测

```python
import backtrader as bt
from datetime import datetime, timedelta
from src.strategies import create_backtrader_strategy
from src.data_sources import DataSourceFactory

# 获取数据
source = DataSourceFactory.create('akshare')
end = datetime.now().strftime('%Y%m%d')
start = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
df = source.get_stock_history('600519', start, end)

# 标准化列名
df = df.rename(columns={
    '日期': 'datetime', '开盘': 'open', '收盘': 'close',
    '最高': 'high', '最低': 'low', '成交量': 'volume'
}).set_index('datetime')

# 创建回测环境
cerebro = bt.Cerebro()
cerebro.adddata(bt.feeds.PandasData(dataname=df))

# 添加策略
strategy_cls = create_backtrader_strategy('macd', fast=12, slow=26, signal=9)
cerebro.addstrategy(strategy_cls)

# 设置参数
cerebro.broker.setcash(100000.0)
cerebro.broker.setcommission(commission=0.001)

# 运行回测
print(f"初始: {cerebro.broker.getvalue():,.2f}")
cerebro.run()
print(f"最终: {cerebro.broker.getvalue():,.2f}")

# 显示图表
cerebro.plot()
```

### 3. 生成专业报告

```python
from src.backtest.report_generator import quick_report

quick_report(
    df=backtest_df,
    output_dir='./reports',
    report_name='my_backtest',
    include_txt=True,
    include_json=True,
    include_charts=True
)
```

## 📖 常用功能

### 批量下载数据

```python
from src.data_sources.akshare_source import AKShareDataSource

source = AKShareDataSource()
data_map = source.load_stock_daily_batch(
    symbols=['600519', '000001', '000002'],
    start='20230101',
    end='20241012',
    cache_dir='./cache'
)

# 访问数据
maotai_df = data_map['600519']
print(f"茅台数据: {len(maotai_df)} 条")
```

### 自定义策略参数

```python
# RSI策略 - 调整超买超卖阈值
strategy_cls = create_backtrader_strategy(
    'rsi',
    period=14,  # RSI周期
    upper=75,   # 超买阈值
    lower=25    # 超卖阈值
)

# Bollinger策略 - 调整入场出场方式
strategy_cls = create_backtrader_strategy(
    'bollinger',
    period=20,
    devfactor=2.5,
    entry_mode='close_below',  # 收盘价低于下轨
    exit_mode='upper'          # 触及上轨出场
)
```

### 获取策略信息

```python
from src.strategies import get_backtrader_strategy

# 查看策略详细信息
module = get_backtrader_strategy('ema')
print(f"策略名称: {module.name}")
print(f"策略描述: {module.description}")
print(f"参数列表: {module.param_names}")
print(f"默认值: {module.defaults}")
print(f"网格搜索范围: {module.grid_defaults}")
```

## 🧪 运行测试

```bash
# 测试策略模块
python test_backtrader_strategies.py

# 测试报告生成
python test_report_generator.py

# 测试数据下载
python test_data_download.py

# 集成测试
python test_integration.py
```

## 📚 可用策略详解

### 指标策略

| 策略 | 描述 | 主要参数 |
|------|------|----------|
| `ema` | EMA均线交叉 | period(20) |
| `macd` | MACD信号交叉 | fast(12), slow(26), signal(9) |
| `bollinger` | 布林带均值回归 | period(20), devfactor(2.0) |
| `rsi` | RSI超买超卖 | period(14), upper(70), lower(30) |
| `keltner` | Keltner通道 | ema_period(20), atr_period(14) |
| `zscore` | Z-Score均值回归 | period(20), z_entry(-2.0) |

### 趋势策略

| 策略 | 描述 | 主要参数 |
|------|------|----------|
| `donchian` | Donchian通道突破 | upper(20), lower(10) |
| `triple_ma` | 三均线多头排列 | fast(5), mid(20), slow(60) |
| `adx_trend` | ADX趋势强度 | adx_period(14), adx_th(25) |

## 🔧 高级用法

### 参数优化

```python
from src.strategies import get_backtrader_strategy

# 获取策略的网格搜索参数范围
module = get_backtrader_strategy('ema')
period_range = module.grid_defaults['period']  # [5, 10, 15, ..., 120]

# 遍历参数进行优化
best_result = None
best_period = None

for period in period_range:
    cerebro = bt.Cerebro()
    cerebro.adddata(data_feed)
    
    strategy_cls = create_backtrader_strategy('ema', period=period)
    cerebro.addstrategy(strategy_cls)
    
    result = cerebro.run()
    final_value = cerebro.broker.getvalue()
    
    if best_result is None or final_value > best_result:
        best_result = final_value
        best_period = period

print(f"最佳周期: {best_period}, 最终资金: {best_result:,.2f}")
```

### 多策略对比

```python
strategies_to_test = ['ema', 'macd', 'rsi', 'bollinger']
results = {}

for strategy_name in strategies_to_test:
    cerebro = bt.Cerebro()
    cerebro.adddata(data_feed)
    
    strategy_cls = create_backtrader_strategy(strategy_name)
    cerebro.addstrategy(strategy_cls)
    
    cerebro.broker.setcash(100000.0)
    cerebro.run()
    
    results[strategy_name] = cerebro.broker.getvalue()

# 打印结果
for name, value in sorted(results.items(), key=lambda x: x[1], reverse=True):
    profit = value - 100000
    profit_pct = (profit / 100000) * 100
    print(f"{name:15s}: ¥{value:>12,.2f} ({profit_pct:+6.2f}%)")
```

## 📊 生成自定义报告

```python
from src.backtest.report_generator import BacktestMetrics, ReportGenerator

# 计算指标
metrics = BacktestMetrics(df)
stats = metrics.calculate_all_metrics()

print(f"累计收益率: {stats['cumulative_return']:.2f}%")
print(f"夏普比率: {stats['sharpe_ratio']:.2f}")
print(f"最大回撤: {stats['max_drawdown']:.2f}%")

# 生成报告
generator = ReportGenerator(df)

# 分别生成不同格式
generator.generate_text_report('./reports/result.txt')
generator.generate_json_report('./reports/result.json')
generator.plot_nav_comparison('./reports/nav.png')
generator.plot_drawdown('./reports/drawdown.png')
generator.save_to_csv('./reports/data.csv')
```

## 🆘 常见问题

### Q1: 数据列名不匹配

**问题**: `ValueError: 'close' is not in list`

**解决**:
```python
# AKShare返回中文列名，需要标准化
df = df.rename(columns={
    '日期': 'datetime', '开盘': 'open', '收盘': 'close',
    '最高': 'high', '最低': 'low', '成交量': 'volume'
})
df = df.set_index('datetime')
```

### Q2: 策略未找到

**问题**: `ValueError: Strategy 'xxx' not found`

**解决**:
```python
# 查看所有可用策略
from src.strategies import list_backtrader_strategies
print(list_backtrader_strategies())
```

### Q3: 数据下载失败

**问题**: 网络错误或数据源不可用

**解决**:
```python
# 使用备用数据源
source = DataSourceFactory.create('yfinance')  # 使用yfinance代替akshare

# 或者使用缓存
df = source.get_stock_history('600519', start, end, use_cache=True)
```

## 📖 完整文档

- **V2.4.0_FINAL_REPORT.md** - 完整功能说明和使用指南
- **STRATEGY_MODULARIZATION_REPORT.md** - 策略模块化技术文档
- **MODULAR_REFACTORING_REPORT.md** - 数据源模块化说明
- **CHANGELOG.md** - 版本更新记录

## 🎯 下一步

1. ✅ 运行测试确保环境正确
2. ✅ 尝试示例代码
3. ✅ 查看完整文档了解高级功能
4. ✅ 开始开发自己的策略

## 💡 提示

- 所有模块都在 `src/` 目录下
- 策略在 `src/strategies/` 
- 数据源在 `src/data_sources/`
- 报告生成在 `src/backtest/`
- 测试在项目根目录下的 `test_*.py` 文件

---

**版本**: V2.4.0  
**更新日期**: 2025年10月12日  
**状态**: ✅ 稳定可用

🎉 祝您使用愉快！
