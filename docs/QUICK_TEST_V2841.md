# V2.8.4.1 快速测试命令

## ✅ 验证通过的命令

### 1. Bollinger Enhanced (推荐) - 已验证产生交易

```bash
# 基础测试（2年数据）
python unified_backtest_framework.py run \
  --strategy boll_e \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --benchmark 000300.SH \
  --out_dir test_v2841 \
  --plot

# 预期结果:
# - trades: 1笔
# - 入场: 2023-04-18 @ 1753.88
# - 出场: 2023-05-19 @ 1670.16 (ATR止损)
```

### 2. MACD Regime (需3年+数据)

```bash
# 推荐：长周期测试
python unified_backtest_framework.py run \
  --strategy macd_r \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31 \
  --benchmark 000300.SH \
  --out_dir test_v2841 \
  --plot

# 预期结果:
# - warmup: 200根
# - 需要至少600根K线(~3年)才能充分测试
```

---

## 🔧 参数调整示例

### Bollinger - 更激进入场

```bash
# 放宽反弹检测 + 关闭趋势过滤
python unified_backtest_framework.py run \
  --strategy boll_e \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --params '{"rebound_lookback": 5, "trend_filter": false}' \
  --out_dir test_aggressive \
  --plot
```

### Bollinger - 更宽松止损

```bash
# 增加止损距离 + 放宽回落出场
python unified_backtest_framework.py run \
  --strategy boll_e \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --params '{"atr_mult_sl": 2.5, "trail_drop_pct": 0.05}' \
  --out_dir test_wider_stop \
  --plot
```

### MACD - 完全放开过滤

```bash
# 关闭趋势过滤 + 延长等待期
python unified_backtest_framework.py run \
  --strategy macd_r \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31 \
  --params '{"trend_filter": false, "max_lag": 10}' \
  --out_dir test_no_filter \
  --plot
```

---

## 📊 Grid优化命令

### Bollinger Grid搜索

```bash
# 搜索最佳参数组合
python unified_backtest_framework.py grid \
  --strategy boll_e \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --out_dir grid_boll

# Grid范围（来自backtrader_registry.py）:
# - period: [18, 20, 22]
# - devfactor: [1.8, 2.0, 2.2]
# - atr_mult_sl: [1.5, 2.0, 2.5]
# - rebound_lookback: [2, 3, 5]
# - trend_filter: [True, False]
```

### MACD Grid搜索（需更长数据）

```bash
# 搜索最佳参数组合
python unified_backtest_framework.py grid \
  --strategy macd_r \
  --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31 \
  --out_dir grid_macd

# Grid范围:
# - pullback_k: [0.3, 0.5, 0.8]
# - max_lag: [5, 7, 10]
# - atr_sl_mult: [1.5, 2.0, 2.5]
# - trend_logic: ['or', 'and']
```

---

## 🧪 调试命令

### 启用策略日志输出

```python
# 修改策略类，临时启用printlog
# 在 unified_backtest_framework.py 或直接修改策略文件

# For Bollinger:
cerebro.addstrategy(Bollinger_EnhancedStrategy, printlog=True, ...)

# For MACD:
cerebro.addstrategy(MACD_RegimePullback, printlog=True, ...)
```

### 使用调试脚本

```bash
# 直接运行调试脚本（包含详细输出）
python test_strategy_debug.py

# 输出包括：
# - warmup_bars计算结果
# - cross_bar位置
# - 每笔交易日志
# - 最终状态变量
```

---

## 📈 多标的批量测试

### 测试不同板块标的

```bash
# 银行股
python unified_backtest_framework.py run \
  --strategy boll_e \
  --symbols 601318.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --out_dir test_bank --plot

# 科技股
python unified_backtest_framework.py run \
  --strategy boll_e \
  --symbols 600031.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --out_dir test_tech --plot

# 消费股
python unified_backtest_framework.py run \
  --strategy boll_e \
  --symbols 600519.SH 600887.SH 600276.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --out_dir test_consumer --plot
```

---

## ⚠️ 注意事项

### 1. 参数格式

❌ **错误**:
```bash
--params "trend_filter=false"  # 无引号的JSON会报错
--params '{trend_filter: false}'  # 单引号内没有双引号
```

✅ **正确**:
```bash
--params '{"trend_filter": false}'  # PowerShell/Bash
--params "{\"trend_filter\": false}"  # CMD需要转义
```

### 2. 数据周期要求

| 策略 | 最小周期 | 推荐周期 | warmup |
|------|----------|----------|--------|
| boll_e | 6个月 | 1-3年 | 30根 |
| macd_r | 2年 | 3-5年 | 200根 |

### 3. 首次测试建议

```bash
# Step 1: 单次测试验证逻辑
python unified_backtest_framework.py run --strategy boll_e ...

# Step 2: 确认有交易后再Grid
python unified_backtest_framework.py grid --strategy boll_e ...

# Step 3: 多标的验证稳定性
# 在不同板块测试相同参数
```

---

## 🎯 预期结果

### Bollinger_Enhanced (2年测试)

```json
{
  "trades": 1,  // V2.8.4: 0 → V2.8.4.1: 1
  "win_rate": 0.0,
  "final_value": 191544.95,
  "cum_return": -4.23%,
  "status": "✅ 逻辑正常（单笔亏损不代表策略无效）"
}
```

### MACD_RegimePullback (2年测试)

```json
{
  "trades": 0,  // 预期：需要更长周期
  "warmup_bars": 200,
  "total_bars": 484,
  "cross_bar": 469,
  "recommendation": "使用3年以上数据",
  "status": "⚠️ 逻辑正常但时间窗口不足"
}
```

---

## 📚 相关文档

- **详细补丁说明**: `docs/V2.8.4.1_RELAXATION_PATCH.md`
- **完成报告**: `docs/V2.8.4.1_COMPLETION_REPORT.md`
- **策略指南**: `docs/V2.8.4_ENHANCED_STRATEGIES.md`
- **更新日志**: `CHANGELOG.md`

---

**版本**: V2.8.4.1  
**更新日期**: 2025-01-25  
**验证状态**: ✅ 测试通过
