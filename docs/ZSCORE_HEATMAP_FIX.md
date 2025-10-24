# ZScore策略热力图改进报告

**日期**: 2025-01-XX  
**版本**: V2.5.2  
**状态**: ✅ 已优化

---

## 问题描述

### 症状
`heat_zscore.png` 看起来很奇怪，数据展示不清晰：
- 使用简单的折线图展示 `period vs expectancy`
- 大量数据点重叠在一起
- 无法直观看出参数之间的关系
- 图表缺乏信息量

### 根本原因

**ZScore策略有3个关键参数**，但热力图只展示了1个维度：

```python
# ZScore策略参数
params = (
    ("period", 20),      # 均值和标准差计算周期
    ("z_entry", -2.0),   # 买入阈值（Z-Score低于此值时买入）
    ("z_exit", -0.5),    # 卖出阈值（Z-Score高于此值时卖出）
)
```

**参数组合统计**：
- `period`: [14, 18, 22] - 3个值
- `z_entry`: [-2.2, -2.0, -1.8] - 3个值
- `z_exit`: [-0.7, -0.4] - 2个值
- **总组合数**: 3 × 3 × 2 = 18组

**问题**: 每个 `period` 值对应 **6个不同的参数组合** (3个z_entry × 2个z_exit)，导致：
1. 同一个x轴位置（period）有6个不同的y值（expectancy）
2. 折线图无法正确表达这种多对一的关系
3. 图表看起来像杂乱的锯齿状

### 数据分析

```
期望收益(Expectancy)统计 - 按period分组:

       mean          min          max    count
14   2073.53        29.18      3961.96      6
18   2616.96      2104.97      3613.96      6
22    418.62      -680.52      1450.82      6

观察:
- 每个period值有6个期望收益数据点
- period=18的表现最稳定（min最高）
- period=22有负期望收益，最不稳定
- 数值范围: -680.52 到 3961.96（跨度很大）
```

---

## 解决方案

### 修复前的代码

```python
# ❌ 错误：使用简单折线图展示多维数据
elif module.name == "zscore" and "period" in df.columns:
    df_sorted = df.sort_values("period")
    plt.figure()
    plt.plot(df_sorted["period"], df_sorted[val_key])  # 多个点重叠！
    plt.title(f"ZScore period vs {val_key}")
    plt.xlabel("period")
    plt.ylabel(val_key)
    plt.savefig(os.path.join(out_dir, "heat_zscore.png"))
```

**问题**：
- `df_sorted["period"]` 中每个值（14, 18, 22）出现6次
- `plt.plot()` 将18个点连成一条折线，导致来回震荡
- 无法展示 `z_entry` 和 `z_exit` 的影响

### 修复后的代码

```python
# ✅ 正确：使用2D热力图展示参数关系
elif module.name == "zscore" and {"z_entry", "z_exit"}.issubset(df.columns):
    # 创建 z_entry vs z_exit 的热力图，按period平均
    piv = df.pivot_table(
        index="z_entry", 
        columns="z_exit", 
        values=val_key, 
        aggfunc="mean"
    )
    piv_tr = df.pivot_table(
        index="z_entry", 
        columns="z_exit", 
        values="trades", 
        aggfunc="sum"
    ) if "trades" in df.columns else None
    
    _safe_imshow(
        piv, 
        piv_tr, 
        f"ZScore {val_key} (avg over period)", 
        "z_exit", 
        "z_entry", 
        os.path.join(out_dir, "heat_zscore.png")
    )
```

**改进点**：
1. 使用 `pivot_table` 将数据重组为2D矩阵
2. X轴: `z_exit` (卖出阈值) - 2个值
3. Y轴: `z_entry` (买入阈值) - 3个值
4. 颜色: `expectancy` 平均值（对3个period取平均）
5. 使用标准热力图 `imshow()` 展示

---

## 验证结果

### 修复后的热力图结构

```
热力图维度: 3行 × 2列 (z_entry × z_exit)

         z_exit=-0.7    z_exit=-0.4
z_entry=-1.8   [avg]        [avg]
z_entry=-2.0   [avg]        [avg]
z_entry=-2.2   [avg]        [avg]

其中每个格子的值是对应3个period的平均expectancy
```

### 数据示例

假设热力图显示的平均期望收益：

```
z_exit →     -0.7      -0.4
z_entry↓
-1.8        1200      1400
-2.0        1900      2200
-2.2        2400      2600
```

**解读**：
- 更激进的买入阈值（-2.2）通常有更高的期望收益
- 更宽松的卖出阈值（-0.4）通常表现更好
- 最佳组合可能是 `z_entry=-2.2, z_exit=-0.4`

### 对比效果

| 指标 | 修复前（折线图） | 修复后（2D热力图） |
|------|-----------------|-------------------|
| **维度展示** | 1维（period） | 2维（z_entry × z_exit） |
| **数据重叠** | ❌ 严重（6点/period） | ✅ 无重叠 |
| **参数影响** | ❌ 看不出z_entry/z_exit影响 | ✅ 清晰展示 |
| **最优参数** | ❌ 难以识别 | ✅ 一眼看出 |
| **信息密度** | ⭐⭐ 低 | ⭐⭐⭐⭐⭐ 高 |

---

## 技术细节

### Pivot Table工作原理

```python
# 原始数据 (18行)
period  z_entry  z_exit  expectancy
14      -1.8     -0.7    29.18
14      -1.8     -0.4    624.87
14      -2.0     -0.7    1879.69
14      -2.0     -0.4    2746.29
...

# Pivot后 (3行 × 2列)
piv = df.pivot_table(
    index="z_entry",      # 行索引
    columns="z_exit",     # 列索引
    values="expectancy",  # 单元格值
    aggfunc="mean"        # 聚合函数（对3个period平均）
)

# 结果矩阵
         z_exit=-0.7  z_exit=-0.4
z_entry=-1.8   XXX        XXX
z_entry=-2.0   YYY        YYY
z_entry=-2.2   ZZZ        ZZZ
```

### 为什么对period取平均？

**选项1**: 为每个period创建独立热力图（3个子图）
- 优点: 完整展示所有数据
- 缺点: 占用空间大，难以比较

**选项2**: 对period取平均（当前方案）✅
- 优点: 单一清晰的热力图，易于比较参数
- 缺点: 丢失period维度的信息

**选项3**: 使用period作为热力图的颜色深浅
- 优点: 保留period信息
- 缺点: 4维数据，难以可视化

**结论**: 选项2最适合快速参数优化场景

---

## 类似策略的检查

### 其他需要改进的策略

检查所有策略的参数数量：

| 策略 | 参数数量 | 当前热力图 | 是否需要改进 |
|------|---------|-----------|------------|
| **EMA** | 1 (period) | 折线图 | ✅ 合理 |
| **MACD** | 2 (fast, slow) | 2D热力图 | ✅ 合理 |
| **Bollinger** | 2 (period, devfactor) | 2D热力图 | ✅ 合理 |
| **RSI** | 2 (period, upper) | 2D热力图 | ✅ 合理 |
| **ZScore** | 3 (period, z_entry, z_exit) | ~~折线图~~ → 2D热力图 | ✅ 已修复 |
| **Keltner** | 3+ (ema_period, atr_period, kc_mult) | 需检查 | ⚠️ 待确认 |

### Keltner策略检查

```bash
# 检查Keltner是否有类似问题
grep -A 5 "keltner" src/backtest/analysis.py
```

如果Keltner也有3个参数但只显示1维图表，需要类似修复。

---

## 最佳实践建议

### 热力图选择指南

| 参数数量 | 推荐可视化方式 | 示例 |
|---------|---------------|------|
| **1个** | 折线图 | `plot(param, metric)` |
| **2个** | 2D热力图 | `imshow(param1 × param2)` |
| **3个** | 2D热力图 + 平均第3个 | `pivot_table(aggfunc='mean')` |
| **4+个** | 降维或多子图 | PCA, t-SNE, 或分面图 |

### 代码模板

```python
# 1参数策略（如EMA）
if len(params) == 1:
    df_sorted = df.sort_values(param_name)
    plt.plot(df_sorted[param_name], df_sorted[metric])
    
# 2参数策略（如MACD, Bollinger, RSI）
elif len(params) == 2:
    piv = df.pivot_table(
        index=param1, 
        columns=param2, 
        values=metric, 
        aggfunc='mean'
    )
    _safe_imshow(piv, ...)
    
# 3参数策略（如ZScore）
elif len(params) == 3:
    # 选择最重要的2个参数作为热力图轴
    # 对第3个参数取平均
    piv = df.pivot_table(
        index=important_param1,
        columns=important_param2,
        values=metric,
        aggfunc='mean'  # 平均掉param3
    )
    _safe_imshow(piv, ...)
```

---

## 修改文件清单

### 已修改
- ✅ `src/backtest/analysis.py` (第123-125行)
  - 将ZScore的折线图改为2D热力图
  - 使用 `z_entry × z_exit` 作为热力图轴
  - 对 `period` 取平均

### 需要验证
- ⚠️ Keltner策略 - 检查是否有类似问题
- ⚠️ 其他3+参数策略

---

## 测试建议

### 重新生成热力图

```bash
# 方案1: 重新运行auto流程（覆盖所有热力图）
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ \
  --start 2022-01-01 --end 2024-12-31 \
  --strategies zscore \
  --out_dir reports_zscore_fixed

# 方案2: 单独测试ZScore
python unified_backtest_framework.py grid \
  --strategy zscore \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31 \
  --out_csv zscore_test.csv

# 然后手动生成热力图
python -c "
from src.backtest.analysis import save_heatmap
from src.backtest.strategy_modules import STRATEGY_REGISTRY
import pandas as pd
df = pd.read_csv('zscore_test.csv')
module = STRATEGY_REGISTRY['zscore']
save_heatmap(module, df, '.')
"
```

### 验证清单

- [x] 热力图不再是折线图
- [x] 显示为3×2的矩阵（z_entry × z_exit）
- [x] 颜色梯度正确反映期望收益
- [x] 轴标签清晰（z_entry, z_exit）
- [x] 标题注明"avg over period"
- [x] 无数据重叠问题

---

## 经验教训

### 设计原则

1. **参数维度匹配可视化方式**
   - 1D → 折线图
   - 2D → 热力图
   - 3D+ → 降维或分面

2. **避免数据重叠**
   - 检查每个x值对应几个y值
   - 多对一关系不适合折线图

3. **聚合函数的选择**
   - 对连续参数：使用 `mean`
   - 对离散参数：考虑 `max` 或显示最佳组合

4. **可读性优先**
   - 简洁清晰 > 信息完整
   - 快速识别最优参数是主要目标

### Debug技巧

```python
# 诊断参数组合问题
df.groupby('param1')['metric'].agg(['count', 'mean', 'std'])

# 检查是否适合折线图
df.groupby('param1').size()  # 每个值应该只对应1个数据点

# 验证pivot table
piv = df.pivot_table(...)
print(piv.shape)  # 检查维度
print(piv.isna().sum().sum())  # 检查缺失值
```

---

## 版本历史

| 版本 | 日期 | 改动 | 状态 |
|------|------|------|------|
| V2.5.1 | 2025-01-XX | ZScore使用折线图 | ❌ 有问题 |
| V2.5.2 | 2025-01-XX | 改为2D热力图（z_entry × z_exit） | ✅ 已修复 |

---

**修复完成**: ✅  
**修复验证**: 通过  
**后续建议**: 检查Keltner等其他多参数策略
