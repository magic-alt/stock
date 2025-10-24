# ZScore热力图问题分析总结

**日期**: 2025-01-XX  
**问题**: `heat_zscore.png` 看起来奇怪  
**状态**: ✅ 已修复

---

## 🔍 问题根源

### 症状
用户发现 `heat_zscore.png` 显示的图表非常奇怪，数据展示混乱，类似锯齿状的折线图。

### 根本原因

**ZScore策略有3个参数，但热力图只展示了1个维度**：

```python
# ZScore策略参数
params = (
    ("period", 20),      # 计算周期
    ("z_entry", -2.0),   # 买入阈值
    ("z_exit", -0.5),    # 卖出阈值
)

# 参数组合: 3 × 3 × 2 = 18组
period:   [14, 18, 22]          # 3个值
z_entry:  [-2.2, -2.0, -1.8]    # 3个值
z_exit:   [-0.7, -0.4]          # 2个值
```

**错误的可视化逻辑**：
```python
# ❌ 旧代码：简单折线图
plt.plot(df_sorted["period"], df_sorted[val_key])
```

**问题**：
- 每个 `period` 值（14, 18, 22）对应 **6个不同的数据点**（3个z_entry × 2个z_exit）
- 折线图将18个点连成锯齿状线条
- 无法展示 `z_entry` 和 `z_exit` 参数的影响

---

## ✅ 解决方案

### 修复代码

```python
# ✅ 新代码：2D热力图
elif module.name == "zscore" and {"z_entry", "z_exit"}.issubset(df.columns):
    # 创建 z_entry vs z_exit 的2D热力图，对period取平均
    piv = df.pivot_table(
        index="z_entry", 
        columns="z_exit", 
        values=val_key, 
        aggfunc="mean"  # 对3个period值取平均
    )
    piv_tr = df.pivot_table(
        index="z_entry", 
        columns="z_exit", 
        values="trades", 
        aggfunc="sum"
    ) if "trades" in df.columns else None
    
    _safe_imshow(
        piv, piv_tr, 
        f"ZScore {val_key} (avg over period)", 
        "z_exit", "z_entry", 
        os.path.join(out_dir, "heat_zscore.png")
    )
```

### 改进效果

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| **图表类型** | 折线图 | 2D热力图 |
| **X轴** | period (重叠) | z_exit (清晰) |
| **Y轴** | expectancy | z_entry |
| **颜色** | 无 | expectancy平均值 |
| **数据重叠** | ❌ 严重 | ✅ 无 |
| **可读性** | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 📊 数据分析

### 期望收益统计（按period分组）

```
       mean      min       max    count
14   2073.53     29.18   3961.96    6
18   2616.96   2104.97   3613.96    6
22    418.62   -680.52   1450.82    6
```

**观察**：
- Period=18 最稳定（最小值最高）
- Period=22 有负期望收益（最差）
- 每个period对应6个参数组合

### 热力图结构

修复后的热力图是 **3×2** 矩阵：

```
         z_exit=-0.7    z_exit=-0.4
z_entry=-1.8   [avg]        [avg]
z_entry=-2.0   [avg]        [avg]
z_entry=-2.2   [avg]        [avg]
```

每个格子显示的是3个period的平均expectancy。

---

## 🔧 修改文件

### 已修改
- ✅ `src/backtest/analysis.py` (第123-128行)
  - 将ZScore的折线图改为2D热力图
  - 使用 `pivot_table` 重组数据
  - 对 `period` 参数取平均

### 新增文档
- ✅ `docs/ZSCORE_HEATMAP_FIX.md` - 详细修复报告
- ✅ `docs/ZSCORE_ANALYSIS_SUMMARY.md` - 本文档

---

## 📝 相关发现

### Keltner策略也需要改进

**检查结果**：
```
Keltner参数: ema_period=[12,16,20], kc_mult=[1.8,2.0,2.2], entry_mode=['pierce','close_below']
参数组合数: 3 × 3 × 2 = 18组
热力图状态: ❌ 不存在（analysis.py中没有对应分支）
```

**建议**：为Keltner添加热力图支持（类似ZScore的修复）

---

## 🎯 最佳实践

### 热力图选择指南

| 参数数量 | 推荐可视化 | 理由 |
|---------|-----------|------|
| **1个** | 折线图 `plot(param, metric)` | 清晰展示趋势 |
| **2个** | 2D热力图 `imshow(p1×p2)` | 标准热力图 |
| **3个** | 2D热力图 + 平均第3个 | 降维处理 |
| **4+个** | 降维/多子图 | PCA或分面图 |

### 诊断命令

```python
# 检查参数组合数
df.groupby('param1').size()  # 每个值应只对应1个点（折线图）

# 检查数据维度
df['param1'].nunique() * df['param2'].nunique()  # 应等于len(df)

# 验证pivot table
piv = df.pivot_table(index='p1', columns='p2', values='metric', aggfunc='mean')
print(piv.shape)  # 检查维度
print(piv.isna().sum().sum())  # 无缺失值
```

---

## ✅ 验证结果

### 测试命令

```bash
# 重新生成ZScore热力图
python -c "
from src.backtest.analysis import save_heatmap
from src.backtest.strategy_modules import STRATEGY_REGISTRY
import pandas as pd
df = pd.read_csv('reports_bulk_10/opt_zscore.csv')
module = STRATEGY_REGISTRY['zscore']
save_heatmap(module, df, 'reports_bulk_10')
print('ZScore heatmap regenerated')
"
```

### 输出

```
[zscore] zero-trade cells: 0.0%
ZScore heatmap regenerated
```

✅ **所有参数组合都有交易**  
✅ **热力图正确显示为3×2矩阵**  
✅ **无数据重叠问题**

---

## 📚 相关文档

1. **ZSCORE_HEATMAP_FIX.md** - 详细的技术修复报告
2. **DONCHIAN_STRATEGY_FIX.md** - Donchian策略的0交易BUG修复
3. **unified_backtest_framework_usage.md** - 框架使用指南

---

## 🎓 经验总结

### 问题教训

1. **多参数策略需要合适的可视化方式**
   - 折线图只适合1个参数
   - 2D热力图适合2-3个参数

2. **数据重叠是红色警报**
   - 检查每个x值对应几个y值
   - 多对一关系不适合折线图

3. **降维策略**
   - 对不重要的参数取平均
   - 或创建多个子图分别展示

### 设计原则

- ✅ **参数维度匹配可视化方式**
- ✅ **避免数据重叠和混淆**
- ✅ **可读性优先于完整性**
- ✅ **快速识别最优参数**

---

**修复完成时间**: 2025-01-XX  
**修复状态**: ✅ 通过验证  
**后续任务**: 考虑为Keltner等策略添加热力图支持
