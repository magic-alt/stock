# ML 策略使用示例与实战指南

> **版本**: V2.8.5
> 
> **目标读者**: 量化策略研究员、回测工程师
> 
> **前置条件**: 已安装 sklearn, pandas, numpy（可选：xgboost, torch）

---

## 📋 快速开始（5 分钟上手）

### 1. 验证环境

```bash
# 运行集成测试
python test_ml_integration.py

# 预期输出:
# ✅ ml_walk 策略已成功注册
# ✅ sklearn 可用
# ✅ 所有测试通过！
```

### 2. 第一次回测

```bash
# 使用默认参数回测茅台（600519.SH）
python unified_backtest_framework.py run \
  --strategy ml_walk \
  --symbols 600519.SH \
  --start 2023-01-01 \
  --end 2024-12-31 \
  --benchmark 000300.SH \
  --cash 200000 \
  --commission 0.0001 \
  --out_dir ./test_ml_first_run

# 回测完成后查看结果
cat ./test_ml_first_run/metrics.json
```

**预期输出示例**:
```json
{
  "strategy": "ml_walk",
  "cum_return": 0.08,
  "sharpe": 0.65,
  "mdd": 0.12,
  "trades": 8,
  "win_rate": 0.625,
  "ann_return": 0.10,
  "exposure_ratio": 0.28
}
```

---

## 🎯 使用场景与参数配置

### 场景 1: 弱市保守策略（参考 2023-2024 A 股）

**目标**: 降低交易频率，提高信号质量，减少回撤

```bash
python unified_backtest_framework.py run \
  --strategy ml_walk \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --params '{
    "model_type": "xgb",
    "prob_long": 0.60,
    "min_train": 300,
    "regime_ma": 200,
    "atr_sl": 2.5,
    "min_holding_bars": 3,
    "risk_per_trade": 0.08
  }' \
  --benchmark 000300.SH \
  --out_dir ./test_ml_conservative
```

**参数解读**:
- `prob_long=0.60`: 提高做多阈值（只在模型高度确信时进场）
- `min_train=300`: 更多训练样本（牺牲早期信号换取模型稳定）
- `regime_ma=200`: 严格趋势过滤（仅在 200 日线上方做多）
- `atr_sl=2.5`: 放宽止损（减少弱市震荡中的误触止损）
- `min_holding_bars=3`: 最小持有 3 天（避免过度频繁交易）
- `risk_per_trade=0.08`: 降低单笔风险至 8%

**适用市场**:
- ✅ 弱势震荡市（如 2023 年 A 股）
- ✅ 下行趋势中寻找反弹机会
- ✅ 风险偏好较低的资金

---

### 场景 2: 震荡市均值回归

**目标**: 捕捉短期超卖/超买机会，高频进出

```bash
python unified_backtest_framework.py run \
  --strategy ml_walk \
  --symbols 000858.SZ \
  --start 2024-01-01 --end 2024-12-31 \
  --params '{
    "label_h": 1,
    "model_type": "rf",
    "prob_long": 0.52,
    "prob_short": 0.52,
    "allow_short": true,
    "regime_ma": 0,
    "atr_sl": 1.5,
    "min_train": 150,
    "risk_per_trade": 0.12
  }' \
  --out_dir ./test_ml_meanreversion
```

**参数解读**:
- `label_h=1`: 预测 1 天收益（短期信号）
- `prob_long=0.52, prob_short=0.52`: 放松阈值（增加交易频率）
- `allow_short=true`: 启用做空（双向交易）
- `regime_ma=0`: 关闭趋势过滤（纯均值回归）
- `atr_sl=1.5`: 收紧止损（快进快出）
- `min_train=150`: 降低训练门槛（更早产生信号）

**适用市场**:
- ✅ 区间震荡市（无明确趋势）
- ✅ 日内/短期波动较大的标的
- ✅ T+0 或融券可用环境

---

### 场景 3: 趋势市中期持有

**目标**: 捕捉主升浪，持有至趋势反转

```bash
python unified_backtest_framework.py run \
  --strategy ml_walk \
  --symbols 600036.SH \
  --start 2022-01-01 --end 2023-12-31 \
  --params '{
    "label_h": 5,
    "model_type": "xgb",
    "prob_long": 0.55,
    "regime_ma": 100,
    "atr_sl": 3.0,
    "atr_tp": 6.0,
    "min_holding_bars": 5,
    "risk_per_trade": 0.15
  }' \
  --benchmark 000300.SH \
  --out_dir ./test_ml_trending
```

**参数解读**:
- `label_h=5`: 预测 5 天收益（中期信号）
- `model_type=xgb`: XGBoost 捕捉复杂趋势模式
- `atr_sl=3.0`: 放宽止损（容忍回调）
- `atr_tp=6.0`: 设置止盈（锁定利润）
- `min_holding_bars=5`: 最小持有 5 天（避免过早退出）
- `risk_per_trade=0.15`: 提高仓位（趋势确定性强）

**适用市场**:
- ✅ 明确上升趋势
- ✅ 大盘指数牛市
- ✅ 板块轮动明显阶段

---

## 🔬 参数优化工作流

### Step 1: 模型类型横向对比

```bash
# 网格搜索：测试不同模型性能
python unified_backtest_framework.py grid \
  --strategy ml_walk \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31 \
  --param-ranges '{
    "model_type": ["rf", "lr", "sgd"],
    "prob_long": [0.55]
  }' \
  --workers 3 \
  --out_dir ./grid_model_comparison
```

**查看结果**:
```bash
# 按 Sharpe 排序
cat ./grid_model_comparison/opt_all.csv | sort -t',' -k8 -nr | head -5

# 对比 RF vs LR
grep "\"rf\"" ./grid_model_comparison/opt_all.csv
grep "\"lr\"" ./grid_model_comparison/opt_all.csv
```

**典型发现**:
- RF 通常 Sharpe 更高（捕捉非线性关系）
- LR 运行速度最快（适合快速迭代）
- SGD 可能在大样本时表现更好

---

### Step 2: 预测期与训练窗口联合优化

```bash
# 网格搜索：label_h × min_train
python unified_backtest_framework.py grid \
  --strategy ml_walk \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31 \
  --param-ranges '{
    "label_h": [1, 3, 5, 10],
    "min_train": [100, 150, 200, 300],
    "model_type": ["rf"]
  }' \
  --workers 4 \
  --out_dir ./grid_horizon_window
```

**分析热力图**:
```python
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv('./grid_horizon_window/opt_all.csv')
pivot = df.pivot_table(values='sharpe', index='label_h', columns='min_train')

sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn')
plt.title('Sharpe Ratio: label_h vs min_train')
plt.savefig('./grid_horizon_window/heatmap_sharpe.png')
```

**常见模式**:
- 短期预测（label_h=1）+ 中等训练窗口（150-200）适合震荡市
- 中期预测（label_h=5）+ 大训练窗口（300+）适合趋势市
- 长期预测（label_h=10）容易过拟合，需谨慎

---

### Step 3: 概率阈值精调

```bash
# 网格搜索：prob_long × allow_short
python unified_backtest_framework.py grid \
  --strategy ml_walk \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --param-ranges '{
    "prob_long": [0.50, 0.52, 0.55, 0.58, 0.60, 0.62],
    "prob_short": [0.52, 0.55],
    "allow_short": [false, true],
    "model_type": ["rf"]
  }' \
  --workers 4 \
  --out_dir ./grid_threshold_tuning
```

**结果解读**:
```bash
# 查看交易频率 vs 胜率 vs Sharpe
cat ./grid_threshold_tuning/opt_all.csv | \
  awk -F',' '{print $3,$4,$6,$8}' | \
  column -t
# 列: prob_long allow_short trades sharpe
```

**优化目标**:
1. **高 Sharpe + 适中交易频率**（理想区间：5-15 笔/年）
2. **避免零交易**（prob_long < 0.50 时容易出现）
3. **做空策略验证**（allow_short=true 时需要 prob_short 独立调优）

---

## 🎨 高级技巧

### 技巧 1: 多标的轮动（准备中）

```bash
# 当前版本 ml_walk 为单标的策略
# 多标的需要自定义策略类（参考 turning_point）

# 变通方案：并行回测多标的，手动合成
for symbol in 600519.SH 000858.SZ 600036.SH; do
  python unified_backtest_framework.py run \
    --strategy ml_walk \
    --symbols $symbol \
    --out_dir ./multi_${symbol}
done

# 使用脚本合并 NAV 曲线
python -c "
import pandas as pd
navs = []
for sym in ['600519.SH', '000858.SZ', '600036.SH']:
    nav = pd.read_csv(f'./multi_{sym}/run_nav.csv', index_col=0)
    navs.append(nav)
combined = pd.concat(navs, axis=1).mean(axis=1)  # 等权组合
combined.to_csv('./portfolio_nav.csv')
"
```

---

### 技巧 2: 与技术指标策略对比

```bash
# 自动流程：ML vs 技术指标全面对比
python unified_backtest_framework.py auto \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --strategies \
    ml_walk \
    adx_trend \
    macd_e \
    donchian \
    rsi_ma_filter \
  --benchmark 000300.SH \
  --workers 5 \
  --out_dir ./auto_ml_vs_tech
```

**查看 Pareto 前沿**:
```bash
cat ./auto_ml_vs_tech/pareto_front.csv | head -10
```

**典型对比维度**:
| 维度 | ML 策略 | 技术指标策略 |
|------|---------|-------------|
| **参数敏感度** | 低-中（模型自适应） | 高（需精细调参） |
| **过拟合风险** | 中-高（需交叉验证） | 低（规则透明） |
| **计算开销** | 高（训练耗时） | 低（指标计算快） |
| **非线性捕捉** | 强 | 弱 |
| **可解释性** | 低（黑盒） | 高（规则清晰） |

---

### 技巧 3: 弱市环境专项优化

**结合 [策略优化指南_弱市环境.md](./策略优化指南_弱市环境.md) 的发现**:

```bash
# 基于市场环境分析的 ML 策略配置
# 场景：600519.SH 在 2023-2024 长期处于 MA200 下方（仅 23.1% 时间在上方）

python unified_backtest_framework.py run \
  --strategy ml_walk \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --params '{
    "model_type": "rf",
    "prob_long": 0.62,
    "regime_ma": 200,
    "min_train": 300,
    "atr_sl": 3.0,
    "label_h": 3,
    "risk_per_trade": 0.06
  }' \
  --benchmark 000300.SH \
  --out_dir ./test_ml_weak_market_optimized
```

**配置理由**:
- `prob_long=0.62`: 极严格阈值（弱市里多数信号是陷阱）
- `regime_ma=200`: 与市场环境分析一致（23.1% 时间可交易）
- `label_h=3`: 中期预测（避免短期噪音）
- `risk_per_trade=0.06`: 降低单笔风险（容错度更高）

**预期效果**:
- 交易次数：2-5 笔/年（极低频）
- 胜率：预期 > 60%（高质量信号）
- 最大回撤：预期 < 8%（严格风控）

---

## 📊 结果分析与诊断

### 常见问题排查

#### 问题 1: 零交易（trades=0）

**原因诊断**:
```bash
# 检查概率分布
python -c "
import pandas as pd
df = pd.read_csv('./test_ml_first_run/run_nav.csv')
# 假设策略输出了 ML_Prob 列
if 'ML_Prob' in df.columns:
    print(df['ML_Prob'].describe())
    print(f'prob >= 0.55: {(df[\"ML_Prob\"] >= 0.55).sum()} days')
"
```

**解决方案**:
1. 降低 `prob_long` 至 0.50-0.52
2. 减少 `min_train`（可能样本不足）
3. 关闭 `regime_ma`（趋势过滤太严格）
4. 检查数据质量（是否有大量缺失值）

---

#### 问题 2: 过拟合（训练期优秀，测试期崩盘）

**诊断**:
```bash
# 分段回测
python unified_backtest_framework.py run \
  --strategy ml_walk \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2023-12-31 \  # 训练期
  --out_dir ./train_period

python unified_backtest_framework.py run \
  --strategy ml_walk \
  --symbols 600519.SH \
  --start 2024-01-01 --end 2024-12-31 \  # 测试期
  --out_dir ./test_period

# 对比指标
diff <(grep "sharpe" ./train_period/metrics.json) \
     <(grep "sharpe" ./test_period/metrics.json)
```

**解决方案**:
1. 增加 `min_train`（更稳定的模型）
2. 使用更简单的模型（`model_type="lr"` 代替 `"xgb"`）
3. 增加正则化（XGBoost 的 `reg_lambda`，已默认=1.0）
4. 减少特征维度（当前自动生成 30+ 特征，可手动筛选）

---

#### 问题 3: 训练时间过长

**性能对比**:
| 模型 | 500 bars 耗时 | 加速方案 |
|------|--------------|---------|
| XGBoost | ~15s | 已使用 `n_jobs=-1` |
| RandomForest | ~20s | 已使用 `n_jobs=-1` |
| LogReg | ~10s | 已使用 `StandardScaler` 管线 |
| SGD | ~5s | **推荐**: 使用 `use_partial_fit=true` |

**优化方案**:
```bash
# 使用 SGD + partial_fit（增量训练）
python unified_backtest_framework.py run \
  --strategy ml_walk \
  --params '{
    "model_type": "sgd",
    "use_partial_fit": true
  }' \
  ...

# 或降低特征复杂度（修改 ml_strategies.py._ta()）
# 仅保留核心特征：ret1, vol10, rsi14, macd
```

---

## 🚀 生产环境部署（未来规划）

### 模型持久化（V2.8.6 计划）

```python
# 训练并保存模型
python unified_backtest_framework.py run \
  --strategy ml_walk \
  --params '{"model_cache_dir":"./models","save_model":true}' \
  ...

# 实盘加载模型（跳过训练）
python paper_trading.py \
  --strategy ml_walk \
  --params '{"model_cache_dir":"./models","use_cached_model":true}' \
  ...
```

### 在线学习（V2.8.7 计划）

```python
# 每日收盘后增量更新模型
# models/600519_rf_online.pkl 会持续演化
python online_learner.py \
  --strategy ml_walk \
  --symbols 600519.SH \
  --params '{"use_online_learning":true,"update_frequency":"daily"}' \
  ...
```

---

## 🎯 最佳实践总结

### DO ✅

1. **先跑默认参数**，了解基线性能
2. **网格搜索前先单变量测试**（如只变 prob_long）
3. **关注 Sharpe 和 MDD 组合**，而非单一指标
4. **保留测试集验证**（训练期 < 80% 总样本）
5. **记录每次实验的参数与结果**（便于复现）
6. **弱市优先测 ml_walk**（自适应特征可能捕捉转折）

### DON'T ❌

1. ❌ 不要在极短样本（< 500 bars）上训练
2. ❌ 不要忽略 `regime_ma` 过滤（弱市必开）
3. ❌ 不要用训练期表现决策（必须有测试期）
4. ❌ 不要过度依赖单一模型（至少对比 RF/LR）
5. ❌ 不要在零交易时继续优化参数（先诊断根因）
6. ❌ 不要忘记手续费/滑点设置（实盘差异巨大）

---

## 📚 相关文档

- [架构分析_ML策略集成.md](./架构分析_ML策略集成.md) - 技术实现细节
- [策略优化指南_弱市环境.md](./策略优化指南_弱市环境.md) - 弱市参数调优
- [CHANGELOG.md](../CHANGELOG.md#V2.8.5) - 版本更新日志
- [unified_backtest_framework_usage.md](../unified_backtest_framework_usage.md) - 框架使用指南

---

## 💬 社区与支持

**遇到问题？**

1. 运行 `python test_ml_integration.py` 诊断环境
2. 查看 `./test_ml_xxx/metrics.json` 详细指标
3. 检查 CHANGELOG 是否有已知问题
4. 提交 Issue 并附上完整命令与错误日志

**贡献新特性？**

- 特征工程增强：修改 `ml_strategies.py._ta()`
- 新模型类型：扩展 `_make_model()`
- 风控逻辑优化：调整 `MLWalkForwardBT.next()`

---

*最后更新：2025-10-25*
*版本：V2.8.5*
