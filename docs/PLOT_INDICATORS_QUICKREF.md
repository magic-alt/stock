# Backtrader 绘图增强 - 快速参考

## 📊 自动添加的技术指标

| 指标 | 位置 | 说明 |
|------|------|------|
| EMA(25) | 主图 | 指数移动平均线，与K线叠加 |
| WMA(25) | 子图 | 加权移动平均线 |
| StochasticSlow | 子图 | 慢速随机指标 |
| MACD | 子图 | MACD柱状图 |
| RSI + SMA(10) | 子图 | RSI及其平滑均线 |
| ATR | 隐藏 | 仅计算不显示 |

## 🎨 使用方法

### 基础用法
```python
adapter.plot()  # 显示所有指标（默认）
```

### 控制指标显示
```python
adapter.plot(show_indicators=True)   # 显示指标
adapter.plot(show_indicators=False)  # 仅K线+成交量
```

### 自定义样式
```python
adapter.plot(style='candlestick')  # 蜡烛图（默认）
adapter.plot(style='line')         # 线形图
```

## 🚀 完整示例

```python
from src.backtest.backtrader_adapter import run_backtrader_backtest

# 一键回测+绘图
results, adapter = run_backtrader_backtest(
    df=data,
    strategy_key='ma_cross',
    initial_capital=100000
)

adapter.plot()  # 显示带指标的图表
```

## 📝 测试脚本

运行测试：
```powershell
python test_plot_indicators.py
```

## 🎯 图表特性

✅ 红涨绿跌（A股配色）  
✅ 成交量独立子图  
✅ 中文字体支持  
✅ 日期自动格式化  
✅ 多指标分层显示  

## 📖 详细文档

查看完整文档：`docs/PLOT_INDICATORS_GUIDE.md`
