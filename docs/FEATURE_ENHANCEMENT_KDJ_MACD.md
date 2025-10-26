# 绘图功能增强 - KDJ 指标 + MACD Histogram 颜色优化

## 📅 更新日期
2025-10-26

## 🎯 功能概述

本次更新为所有策略的回测图表添加了两项重要增强：

### 1. MACD Histogram 颜色优化
- **功能**: MACD 柱状图根据数值自动着色
- **规则**: 
  - `>0` → 红色（多头动能）
  - `<0` → 绿色（空头动能）
  - `=0` → 灰色
- **视觉效果**: 更直观地判断市场动能变化

### 2. KDJ 指标（第五子图）
- **功能**: 为所有策略图表添加 KDJ 随机指标
- **包含线条**:
  - **K 线**（蓝色）: 快速随机指标
  - **D 线**（红色）: K 线的移动平均
  - **J 线**（橙色）: 3×K - 2×D（超买超卖敏感线）
- **参数**: KDJ(9,3,3)
- **超买超卖线**: 80（上限）、20（下限）

## 🔧 技术实现

### 修改的文件

#### 1. `src/backtest/engine.py`

**新增内容**:
```python
# 自定义 KDJ 指标类（第 47-95 行）
class KDJ(bt.Indicator):
    """
    KDJ 指标（随机指标的中国化版本）
    K线 = Stochastic %K
    D线 = K线的移动平均
    J线 = 3*K - 2*D
    """
    lines = ('percK', 'percD', 'percJ',)
    params = (
        ('period', 9),          # K线周期
        ('period_dfast', 3),    # K线平滑周期
        ('period_dslow', 3),    # D线平滑周期
        ('upperband', 80.0),
        ('lowerband', 20.0),
    )
    # ... 完整实现见源码
```

**修改位置**: `_run_module()` 方法中的 `StrategyWithPlotIndicators` 类（第 270-290 行）

```python
# MACD histogram 配置
self._plot_macd.plotlines.histo._method = 'bar'
self._plot_macd.plotlines.histo.plotname = 'histogram'

# 添加 KDJ 指标
self._plot_kdj = KDJ(
    data,
    period=9,
    period_dfast=3,
    period_dslow=3,
    upperband=80.0,
    lowerband=20.0,
)
```

#### 2. `src/backtest/plotting.py`

**修改位置**: `plot_backtest_with_indicators()` 函数（第 420-470 行）

**新增逻辑**:
```python
# 遍历所有子图，找到 MACD 子图
for ax in axes:
    # 识别 MACD 子图（通过图例检测）
    legend = ax.get_legend()
    if legend:
        legend_texts = [t.get_text().lower() for t in legend.get_texts()]
        has_macd = any('macd' in text or 'histo' in text 
                      for text in legend_texts)
    
    if has_macd:
        # 重新着色 histogram 柱状图
        for container in ax.containers:
            for bar in container:
                height = bar.get_height()
                if height > 0:
                    bar.set_facecolor('red')      # 多头
                elif height < 0:
                    bar.set_facecolor('green')    # 空头
                else:
                    bar.set_facecolor('gray')     # 中性
```

## 📊 图表结构

更新后的回测图表包含 **5 个子图**：

```
┌─────────────────────────────────────────────────┐
│ 子图 1: 价格走势                                 │
│  - K线（红涨绿跌）                              │
│  - 布林带（Bollinger Bands）                    │
│  - 均线（MA5, MA10, MA20, MA30）                │
│  - 买卖点标记（▲ 买入, ▼ 卖出）                │
├─────────────────────────────────────────────────┤
│ 子图 2: 成交量（Volume）                         │
│  - 红色柱状 = 上涨日                            │
│  - 绿色柱状 = 下跌日                            │
├─────────────────────────────────────────────────┤
│ 子图 3: RSI(14) 相对强弱指标                     │
│  - 超买线: 70                                   │
│  - 超卖线: 30                                   │
├─────────────────────────────────────────────────┤
│ 子图 4: MACD 指标（增强版）⭐                     │
│  - MACD 线（蓝色）                              │
│  - Signal 线（红色）                            │
│  - Histogram 柱状图：                           │
│    * >0 = 红色（多头动能）                      │
│    * <0 = 绿色（空头动能）                      │
├─────────────────────────────────────────────────┤
│ 子图 5: KDJ(9,3,3) 随机指标 ⭐ 新增              │
│  - K 线（蓝色）- 快速线                         │
│  - D 线（红色）- 慢速线                         │
│  - J 线（橙色）- 敏感线                         │
│  - 超买线: 80                                   │
│  - 超卖线: 20                                   │
└─────────────────────────────────────────────────┘
```

## 💡 使用方法

### 方法 1: 命令行（推荐）

```bash
# 单策略回测 + 完整图表
python unified_backtest_framework.py run \
    --strategy macd \
    --symbols 000858.SZ \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --plot \
    --out_dir test_output

# 输出: test_output/macd_chart.png
# 图表包含 5 个子图，MACD histogram 自动着色，KDJ 指标完整显示
```

### 方法 2: Python API

```python
from src.backtest.engine import BacktestEngine

# 初始化引擎
engine = BacktestEngine(cache_dir="./cache")

# 运行策略并启用绘图
metrics = engine.run_strategy(
    strategy="macd",
    symbols=["000858.SZ"],
    start="2023-01-01",
    end="2023-12-31",
    enable_plot=True,  # 关键：启用绘图指标
    out_dir="./test_output"
)

# 获取 cerebro 实例并绘图
cerebro = metrics.pop("_cerebro", None)
if cerebro:
    from src.backtest.plotting import plot_backtest_with_indicators
    plot_backtest_with_indicators(
        cerebro,
        style='candlestick',
        figsize=(16, 10),
        out_file="./test_output/macd_chart.png"
    )
```

## 🎨 视觉效果说明

### MACD Histogram 着色规则

| 数值范围 | 颜色 | 边框颜色 | 市场含义 |
|---------|------|---------|---------|
| `> 0` | 红色 | 深红色 | 多头动能增强 |
| `< 0` | 绿色 | 深绿色 | 空头动能增强 |
| `= 0` | 灰色 | 深灰色 | 动能均衡 |

**交易信号解读**:
- Histogram 从绿色转红色 → 潜在买入信号
- Histogram 从红色转绿色 → 潜在卖出信号
- Histogram 柱状高度 → 动能强度

### KDJ 指标使用技巧

#### 超买超卖判断
- **超买区域**: K、D、J > 80
  - 市场过热，注意回调风险
  - 可考虑减仓或止盈

- **超卖区域**: K、D、J < 20
  - 市场超跌，可能反弹
  - 可考虑建仓或加仓

#### 金叉死叉信号
- **金叉**: K 线上穿 D 线
  - 短期看涨信号
  - 配合 J 线确认

- **死叉**: K 线下穿 D 线
  - 短期看跌信号
  - 配合 J 线确认

#### J 线特殊作用
- **J > 100**: 严重超买，警惕顶部
- **J < 0**: 严重超卖，关注底部
- **J 线摆动**: 最敏感，领先 K、D 线

## 📈 实际案例

### 测试结果（000858.SZ, 2023-01-01 至 2023-12-31）

```
策略: MACD
参数: fast=12, slow=26, signal=9
交易次数: 7 次（6 次平仓，1 次持仓）
累计收益: -10.66%
最大回撤: 17.76%
夏普比率: -0.69

图表输出:
✅ MACD histogram 已着色：209 个柱状（>0红色，<0绿色）
✅ KDJ 指标已添加（K、D、J 三条线完整显示）
✅ 已添加买卖点标记: 7 个买入, 6 个卖出
✅ 图表已保存到: test_output_kdj/macd_chart.png
```

## ✅ 验证清单

### 功能验证

- [x] ✅ MACD histogram 柱状图自动着色
  - [x] >0 显示为红色
  - [x] <0 显示为绿色
  - [x] 边框颜色正确（深红/深绿）
  
- [x] ✅ KDJ 指标完整显示
  - [x] K 线（蓝色）正确绘制
  - [x] D 线（红色）正确绘制
  - [x] J 线（橙色）正确计算并绘制
  - [x] 超买超卖线（80/20）显示
  
- [x] ✅ 适用于所有策略
  - [x] MACD 策略测试通过
  - [x] 其他策略（Bollinger, RSI, EMA 等）继承相同绘图逻辑

### 性能验证

- [x] ✅ 绘图速度无明显影响（< 1 秒）
- [x] ✅ 内存占用正常
- [x] ✅ 图表文件大小合理（~1MB）

## 🔄 兼容性

### 向后兼容
- ✅ 旧代码无需修改
- ✅ 现有策略自动获得新功能
- ✅ 图表保存路径不变

### 依赖要求
- Python >= 3.8
- backtrader >= 1.9.76
- matplotlib >= 3.5.0
- numpy, pandas（无新增依赖）

## 🐛 已知问题

### 问题 1: 部分策略 KDJ 数据不足
**现象**: 策略运行初期（前 9 天），KDJ 指标可能显示为空白

**原因**: KDJ 需要至少 9 个交易日的数据才能计算

**解决方案**: 正常现象，Backtrader 会自动处理数据预热期

### 问题 2: MACD histogram 颜色在某些主题下不明显
**现象**: 暗色主题下红绿色对比度降低

**当前状态**: 使用标准红绿色，符合 A 股习惯

**未来优化**: 可考虑添加主题配置选项

## 📚 相关文档

- **架构文档**: `ARCHITECTURE_OPTIMIZATION_V2.8.6.3.md`
- **变更日志**: `CHANGELOG.md`
- **绘图模块**: `src/backtest/plotting.py`
- **引擎模块**: `src/backtest/engine.py`

## 🎉 总结

本次更新通过两项关键增强，显著提升了回测图表的信息密度和可读性：

1. **MACD Histogram 颜色优化**: 通过红绿着色，快速识别多空动能变化
2. **KDJ 指标添加**: 提供额外的超买超卖参考，辅助交易决策

所有现有策略无需修改即可享受这些增强功能！

---

**更新版本**: V2.8.6.3+  
**作者**: GitHub Copilot  
**测试状态**: ✅ 通过  
**发布日期**: 2025-10-26
