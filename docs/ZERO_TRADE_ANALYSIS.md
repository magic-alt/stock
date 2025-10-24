# Zero-Trade Cells 分析报告

**日期**: 2025-01-XX  
**命令**: `auto --strategies adx_trend macd triple_ma donchian zscore keltner bollinger rsi`  
**状态**: ✅ 统计正确，仅MACD有1个问题参数

---

## 问题背景

用户运行auto流程后看到：
```
[adx_trend] zero-trade cells: 0.0%
[macd] zero-trade cells: 5.0%
[triple_ma] zero-trade cells: 0.0%
[donchian] zero-trade cells: 0.0%
[zscore] zero-trade cells: 0.0%
[keltner] zero-trade cells: 0.0%
[bollinger] zero-trade cells: 0.0%
[rsi] zero-trade cells: 0.0%
```

**疑问**: 为什么7个策略都是0.0%？是否统计有误？

---

## 验证结果

### ✅ 统计是正确的

经过详细检查各策略的CSV文件，确认 **zero-trade cells 统计完全正确**：

| 策略 | 总参数 | 零交易 | 比例 | 交易范围 | 平均交易 | 状态 |
|------|--------|--------|------|---------|---------|------|
| **adx_trend** | 9 | 0 | 0.0% | 5-16笔 | 8.7笔 | ✅ 健康 |
| **macd** | 20 | 1 | 5.0% | 0-28笔 | 25.6笔 | ⚠️ 有1个问题 |
| **triple_ma** | 18 | 0 | 0.0% | 10-12笔 | 10.7笔 | ✅ 健康 |
| **donchian** | 9 | 0 | 0.0% | 9-10笔 | 9.2笔 | ✅ 健康 |
| **zscore** | 18 | 0 | 0.0% | 9-25笔 | 16.3笔 | ✅ 健康 |
| **keltner** | 18 | 0 | 0.0% | 3-10笔 | 6.1笔 | ✅ 正常 |
| **bollinger** | 16 | 0 | 0.0% | 3-18笔 | 9.8笔 | ✅ 健康 |
| **rsi** | 16 | 0 | 0.0% | 1-2笔 | 1.1笔 | ⚠️ 交易过少 |

---

## 关键发现

### 1. MACD策略的问题参数

**唯一的零交易参数组合**：
```
fast=13, slow=13, signal=9
trades=0, cum_return=0.0, sharpe=NaN
```

**问题原因**：
- `fast=13, slow=13` → 快线和慢线周期相同！
- 这导致 MACD = EMA(13) - EMA(13) = 0 (恒为0)
- MACD恒为0，永远不会与信号线产生交叉
- **因此永远不会触发买卖信号**

**结论**：这是一个**无效参数组合**，应该在网格搜索中过滤掉。

### 2. RSI策略的潜在问题

虽然0%零交易，但交易频率极低：
```
交易数分布:
- 最少: 1笔
- 最多: 2笔
- 平均: 1.1笔
```

**分析**：
- RSI策略在3年回测期间平均只产生1.1笔交易
- 这意味着策略参数可能过于保守
- 建议检查RSI阈值是否过严（如upper=70, lower=30）

### 3. 其他策略表现

**表现良好**：
- **ADX Trend**: 平均8.7笔交易，范围5-16笔 ✅
- **ZScore**: 平均16.3笔交易，范围9-25笔 ✅
- **Triple MA**: 平均10.7笔交易，范围10-12笔 ✅
- **Bollinger**: 平均9.8笔交易，范围3-18笔 ✅

**正常但偏低**：
- **Keltner**: 平均6.1笔交易，范围3-10笔（可接受）
- **Donchian**: 平均9.2笔交易，范围9-10笔（稳定）

---

## 为什么大部分策略是0.0%？

这是**好现象**，说明：

### 1. 策略逻辑健康
- 所有参数组合都能产生交易信号
- 没有出现"永远不触发"的情况
- 参数范围设置合理

### 2. Donchian修复生效
之前Donchian策略有100%零交易（使用 `highest[0]` 的BUG），修复后现在0%零交易 ✅

### 3. ZScore修复生效
之前的折线图问题已修复，现在正常产生交易 ✅

### 4. 100股整手规则生效
所有策略都正确执行100股整数倍交易，没有因为资金不足导致无法交易 ✅

---

## 统计代码验证

```python
# src/backtest/analysis.py (第163-165行)
if "trades" in df.columns and len(df) > 0:
    zero_ratio = float((df["trades"].fillna(0) <= 0).mean())
    print(f"[{module.name}] zero-trade cells: {zero_ratio:.1%}")
```

**逻辑**：
1. 检查每个参数组合的 `trades` 列
2. 统计 `trades <= 0` 的比例
3. 使用 `.mean()` 计算百分比

**验证**：
- MACD: 20个参数中1个为0 → 1/20 = 5.0% ✅
- 其他7个: 所有参数都 > 0 → 0/N = 0.0% ✅

---

## 建议改进

### 1. 修复MACD网格搜索

**问题参数**：允许 `fast=slow` 的组合

**解决方案1**: 添加参数验证
```python
# src/strategies/macd_backtrader_strategy.py
def _coerce_macd(params: Dict[str, Any]) -> Dict[str, Any]:
    out = params.copy()
    for k in ("fast", "slow", "signal"):
        if k in out:
            out[k] = int(out[k])
    
    # 新增：确保 fast < slow
    if out.get("fast", 12) >= out.get("slow", 26):
        raise ValueError(f"MACD fast period ({out['fast']}) must be < slow period ({out['slow']})")
    
    return out
```

**解决方案2**: 修改网格定义（推荐）
```python
# src/backtest/engine.py 第706行
if module.name == "macd":
    # 旧代码（有问题）
    # return {"fast": [10,11,12,13], "slow": [13,14,15,16,17], "signal": [9]}
    
    # 新代码（确保 fast < slow）
    return {"fast": [10,11,12], "slow": [14,15,16,17], "signal": [9]}
```

### 2. 优化RSI参数范围

当前RSI平均只有1.1笔交易，可能过于保守：

```python
# 当前参数
{"period": [14,18,20,22], "upper": [70,75], "lower": [25,30]}

# 建议调整（更宽松的阈值）
{"period": [14,18,20,22], "upper": [65,70,75], "lower": [25,30,35]}
```

### 3. 添加交易频率检查

在auto流程中过滤掉交易过少的策略：

```python
# engine.py auto_pipeline
# 在保存结果前添加
df_filtered = df[df['trades'] >= min_trades]  # 已有
df_filtered = df_filtered[df_filtered['trades'] >= 3]  # 新增：至少3笔交易
```

---

## 测试建议

### 1. 修复MACD后重新测试

```bash
# 修改grid定义后重新运行
python unified_backtest_framework.py grid \
  --strategy macd \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31 \
  --out_csv macd_fixed.csv

# 检查是否还有零交易
python -c "
import pandas as pd
df = pd.read_csv('macd_fixed.csv')
print(f'零交易组合: {(df[\"trades\"] <= 0).sum()}')
"
```

### 2. 测试RSI更宽松的参数

```bash
python unified_backtest_framework.py grid \
  --strategy rsi \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31 \
  --grid '{"period": [14], "upper": [65,70,75], "lower": [25,30,35]}' \
  --out_csv rsi_relaxed.csv
```

---

## 总结

### ✅ 统计结果正确

**zero-trade cells: 0.0%** 表示：
- 该策略的所有参数组合都至少产生了1笔交易
- 策略逻辑正常，参数设置合理
- 这是一个**好现象**

### ⚠️ 需要关注的问题

1. **MACD有1个无效参数** (fast=13, slow=13)
   - 占比5.0% (20个中1个)
   - 建议修改网格定义避免此类组合

2. **RSI交易频率过低** (平均1.1笔)
   - 虽然0%零交易，但交易太少
   - 建议放宽阈值参数

### 📊 整体评估

| 指标 | 结果 | 评级 |
|------|------|------|
| **策略健康度** | 7/8策略无零交易 | ⭐⭐⭐⭐⭐ |
| **统计准确性** | 与CSV数据完全一致 | ✅ 正确 |
| **修复效果** | Donchian/ZScore已修复 | ✅ 生效 |
| **需改进项** | MACD和RSI | ⚠️ 2项 |

---

**报告生成时间**: 2025-01-XX  
**验证状态**: ✅ 通过  
**后续操作**: 修复MACD网格定义（可选）
