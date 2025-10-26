# Grid Search 自动分析功能 (V2.8.6.3)

## 功能概述

从 V2.8.6.3 版本开始，`grid_search()` 方法会在网格搜索完成后**自动生成**分析结果，无需手动调用 `analysis.py` 中的函数。

## 自动生成的内容

### 1. Pareto 前沿分析
**文件位置**: `cache/grid_analysis/{strategy}_pareto.csv`

**说明**: 
- 自动筛选出 Pareto 最优解（非劣解）
- 基于 Sharpe、累计收益率、最大回撤三个指标
- 帮助快速识别最优参数组合

**示例输出**:
```csv
strategy,fast,slow,signal,cum_return,sharpe,mdd,trades,win_rate,...
macd,10,24,7,-0.0499,-0.296,0.135,6,0.333,...
```

### 2. 参数热力图
**文件位置**: `cache/grid_analysis/{strategy}/heat_{strategy}.png`

**说明**:
- 根据策略类型自动生成对应的参数热力图
- 可视化参数组合与收益率的关系
- 灰色区域表示无交易或交易失败的参数组合

**支持的策略**:
- MACD: fast vs slow 热力图
- Bollinger: period vs devfactor 热力图
- RSI: period vs upper 热力图
- EMA: period vs 收益曲线图
- 更多策略请参考 `src/backtest/analysis.py`

## 使用方法

### 方法一：直接调用 grid_search

```python
from backtest.engine import BacktestEngine

engine = BacktestEngine(cache_dir="./cache")

# 执行网格搜索（自动生成分析结果）
result_df = engine.grid_search(
    strategy="macd",
    grid={
        "fast": [10, 12, 14],
        "slow": [24, 26, 28],
        "signal": [7, 9],
    },
    symbols=["000858.SZ"],
    start="2023-01-01",
    end="2023-12-31",
    cash=100000,
    commission=0.0003,
)

# 分析结果已自动保存到：
# - cache/grid_analysis/macd_pareto.csv
# - cache/grid_analysis/macd/heat_macd.png
```

### 方法二：使用 CLI 命令

```bash
# 单策略网格搜索（自动生成分析）
python unified_backtest_framework.py grid \
    --strategy macd \
    --symbols 000858.SZ \
    --start 2023-01-01 --end 2023-12-31 \
    --params fast=10,12,14 slow=24,26,28 signal=7,9

# 多策略自动优化（已集成 analysis.py）
python unified_backtest_framework.py auto \
    --strategies macd bollinger rsi \
    --symbols 000858.SZ 600036.SH \
    --start 2023-01-01 --end 2023-12-31 \
    --benchmark 000300.SH \
    --top_n 5 --out_dir reports_auto
```

## 输出示例

执行 `grid_search()` 后，控制台输出：

```
✅ Pareto frontier saved: ./cache/grid_analysis/macd_pareto.csv (3 points)
[macd] zero-trade cells: 0.0%
✅ Heatmaps saved in: ./cache/grid_analysis/macd
```

## 优势

| 特性 | 手动调用 analysis.py | 自动分析 (V2.8.6.3) |
|------|---------------------|---------------------|
| **便利性** | ❌ 需要额外代码调用 | ✅ 自动生成 |
| **一致性** | ⚠️ 可能忘记调用 | ✅ 每次都生成 |
| **输出位置** | ❓ 需要手动指定 | ✅ 标准化路径 |
| **错误处理** | ❌ 需要自行处理 | ✅ 内置 try-except |

## 技术细节

### 集成位置
- **文件**: `src/backtest/engine.py`
- **方法**: `grid_search()` (第 656-695 行)
- **触发时机**: 网格搜索完成后，返回结果前

### 依赖函数
```python
from .analysis import pareto_front, save_heatmap
```

- `pareto_front(df)`: 计算 Pareto 前沿
- `save_heatmap(module, df, out_dir)`: 生成参数热力图

### 错误处理
如果分析失败（例如数据不完整），会输出警告但不影响 grid_search 主流程：

```python
⚠️  Failed to generate analysis outputs: {error_message}
```

## 验证测试

运行以下命令验证功能是否正常：

```bash
python test_grid_search_analysis.py
```

预期输出：
```
✅ Test 1: analysis.py module import
✅ Test 2: grid_search auto-analysis

🎉 ALL TESTS PASSED - V2.8.6.3 enhancement verified!
```

## 相关文档

- **架构优化文档**: `ARCHITECTURE_OPTIMIZATION_V2.8.6.3.md`
- **架构总结**: `ARCHITECTURE_SUMMARY.md`
- **变更日志**: `CHANGELOG.md` (V2.8.6.3 部分)
- **analysis.py 源码**: `src/backtest/analysis.py`

## 常见问题

### Q: 为什么只有 1 个 Pareto 最优点？
A: 说明当前参数组合中只有 1 个配置是 Pareto 最优的（非劣解）。其他配置在某些指标上都被该配置"支配"。

### Q: 热力图中的灰色区域是什么？
A: 灰色区域表示该参数组合没有产生交易或交易失败（trades <= 0）。

### Q: 如何禁用自动分析？
A: 当前版本不支持禁用。如果分析失败，会自动跳过并输出警告，不影响 grid_search 主流程。

### Q: 分析结果在哪里？
A: 
- Pareto 前沿: `cache/grid_analysis/{strategy}_pareto.csv`
- 热力图: `cache/grid_analysis/{strategy}/heat_{strategy}.png`

---

**版本**: V2.8.6.3  
**日期**: 2025-10-26  
**作者**: GitHub Copilot
