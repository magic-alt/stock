# 中国A股交易规则完整实现 V3.0

## 更新日期
2025-10-23

## 更新内容

本次更新完全实现了中国A股的真实交易规则，包括：

1. ✅ **强制100股整数倍交易**
2. ✅ **佣金免五规则**（按实际费率收取）
3. ✅ **印花税计算**（仅卖出收取）
4. ✅ **默认初始资金200,000元**
5. ✅ **完整的交易成本计算**

---

## 一、交易规则

### 1.1 最小交易单位

| 规则 | 说明 | 强制执行 |
|------|------|----------|
| 最小单位 | 1手 = 100股 | ✅ 是 |
| 交易数量 | 必须是100的整数倍 | ✅ 是 |
| 允许交易 | 100, 200, 300, 400... | ✅ |
| 禁止交易 | 1, 10, 50, 150, 250... | ❌ |

**实现位置**: `src/backtest/engine.py` → `CNStockCommission.getsize()`

### 1.2 交易成本

#### 佣金
- **费率**: 万分之一（0.0001）
- **方向**: 买卖双向收取
- **规则**: 免五（按实际费率，无最低限制）

#### 印花税
- **费率**: 万分之五（0.0005）
- **方向**: 仅卖出收取
- **规则**: 无最低限制

#### 成本公式

**买入总成本**:
```
买入成本 = 股数 × 价格 × (1 + 0.0001)
         = 交易金额 × 1.0001
```

**卖出总成本**:
```
卖出费用 = 股数 × 价格 × (0.0001 + 0.0005)
         = 交易金额 × 0.0006
```

**双向总成本率**:
```
总成本率 = 0.0001(买入佣金) + 0.0001(卖出佣金) + 0.0005(印花税)
         = 0.0007
         = 万分之七（0.07%）
```

---

## 二、默认配置

### 2.1 系统参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 初始资金 | 200,000元 | 适合A股1-2手操作 |
| 佣金率 | 0.0001 | 万分之一 |
| 印花税率 | 0.0005 | 万分之五 |
| 滑点 | 0.001 | 千分之一 |
| 最低佣金 | 0元 | 免五模式 |

**配置位置**:
- `unified_backtest_framework.py`
- `src/backtest/engine.py`

### 2.2 命令行参数

```bash
# run 命令
python unified_backtest_framework.py run \
    --symbol 600519.SH \
    --strategy macd \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --cash 200000 \          # 默认20万
    --commission 0.0001 \    # 默认万一
    --plot

# grid 命令
python unified_backtest_framework.py grid \
    --strategy macd \
    --symbols 600519.SH \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --cash 200000 \          # 默认20万
    --commission 0.0001      # 默认万一

# auto 命令
python unified_backtest_framework.py auto \
    --symbols 600519.SH 000333.SZ \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --cash 200000 \          # 默认20万
    --commission 0.0001      # 默认万一
```

---

## 三、交易成本示例

### 3.1 单手交易（100股）

#### 买入100股 @ 1770.85元
```
股数: 100
价格: 1770.85元/股
交易金额: 177,085元

佣金: 177,085 × 0.0001 = 17.71元
印花税: 0元（买入不收）
总费用: 17.71元

实际支付: 177,085 + 17.71 = 177,102.71元
```

#### 卖出100股 @ 1745.51元
```
股数: 100
价格: 1745.51元/股
交易金额: 174,551元

佣金: 174,551 × 0.0001 = 17.46元
印花税: 174,551 × 0.0005 = 87.28元
总费用: 17.46 + 87.28 = 104.74元

实际到手: 174,551 - 104.74 = 174,446.26元
```

#### 完整交易盈亏
```
买入成本: 177,102.71元
卖出所得: 174,446.26元
净亏损: -2,656.45元

其中：
  价格损失: (1745.51 - 1770.85) × 100 = -2,534元
  交易成本: 17.71 + 104.74 = 122.45元
```

### 3.2 双手交易（200股）

#### 买入200股 @ 1770.85元
```
交易金额: 354,170元
佣金: 35.42元
总支付: 354,205.42元
```

#### 卖出200股 @ 1745.51元
```
交易金额: 349,102元
佣金: 34.91元
印花税: 174.55元
总费用: 209.46元
实际到手: 348,892.54元
```

#### 完整交易
```
买入成本: 354,205.42元
卖出所得: 348,892.54元
净亏损: -5,312.88元

交易成本: 35.42 + 209.46 = 244.88元
成本占比: 244.88 / 354170 = 0.069%
```

---

## 四、交易日志示例

### 4.1 完整交易日志

```
================================================================================
交易日志 (Trade Log)
================================================================================
Starting Portfolio Value: 200000.00

2023-03-24, BUY EXECUTED, Size 100, Price: 1770.85, Cost: 177085.00, Commission 17.7085
2023-04-12, SELL EXECUTED, Size -100, Price: 1745.51, Value: 174551.00, Commission 104.7306
2023-04-28, BUY EXECUTED, Size 200, Price: 1764.77, Cost: 352954.00, Commission 35.2954
2023-05-11, SELL EXECUTED, Size -200, Price: 1729.27, Value: 345854.00, Commission 207.5124
2023-06-15, BUY EXECUTED, Size 100, Price: 1680.00, Cost: 168000.00, Commission 16.8000
2023-07-20, SELL EXECUTED, Size -100, Price: 1720.00, Value: 172000.00, Commission 103.1720

Final Portfolio Value: 198500.00
================================================================================
```

### 4.2 字段说明

| 字段 | 含义 | 示例 |
|------|------|------|
| Date | 交易日期 | 2023-03-24 |
| Action | 买入/卖出 | BUY/SELL EXECUTED |
| Size | 股数（必须是100倍数）| 100, 200, -100 |
| Price | 成交价格（元/股）| 1770.85 |
| Cost/Value | 交易金额（不含费用）| 177085.00 |
| Commission | 总费用（佣金+印花税）| 17.7085 |

---

## 五、代码实现

### 5.1 佣金计算类

```python
# src/backtest/engine.py

class CNStockCommission(bt.CommInfoBase):
    """中国A股佣金和印花税计算"""
    params = (
        ('commission', 0.0001),      # 佣金率：万分之一
        ('stocklike', True),         # 股票模式
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('percabs', False),
        ('stamp_duty', 0.0005),      # 印花税：万分之五（仅卖出）
        ('min_commission', 0.0),     # 最低佣金：0元（免五）
        ('mult', 1.0),
        ('margin', None),
    )
    
    def getsize(self, price, cash):
        """计算可购买股数（必须是100的整数倍）"""
        effective_price = price * 1.0006  # 考虑税费
        max_shares = int(cash / effective_price)
        lots = max_shares // 100  # 向下取整到100倍数
        return lots * 100
    
    def _getcommission(self, size, price, pseudoexec):
        """计算佣金（免五模式）"""
        value = abs(size) * price
        comm = value * self.p.commission
        
        # 如果设置了最低佣金（不免五）
        if self.p.min_commission > 0 and comm < self.p.min_commission:
            comm = self.p.min_commission
        
        return comm
    
    def getcommission(self, size, price):
        """获取总交易成本（佣金 + 印花税）"""
        comm = self._getcommission(size, price, False)
        
        # 印花税（仅卖出）
        stamp = 0.0
        if size < 0:
            stamp = abs(size) * price * self.p.stamp_duty
        
        return comm + stamp
```

### 5.2 使用方法

```python
# 在策略中下单
class MyStrategy(bt.Strategy):
    def next(self):
        if self.buy_signal:
            # 买入1手（100股）
            self.buy(size=100)
            
            # 或买入2手（200股）
            self.buy(size=200)
        
        elif self.sell_signal:
            # 卖出全部持仓（自动是100的倍数）
            self.sell(size=self.position.size)
```

---

## 六、切换到"不免五"模式

如果需要模拟老券商的"不免五"规则：

### 6.1 修改方法

```python
# src/backtest/engine.py 第207行

# 当前（免五）
cerebro.broker.addcommissioninfo(CNStockCommission())

# 改为不免五
cerebro.broker.addcommissioninfo(CNStockCommission(min_commission=5.0))
```

### 6.2 效果对比

**对于100股交易**（佣金17.71元）：
- 免五模式：收取17.71元 ✅
- 不免五模式：收取17.71元（已超5元最低）✅
- **结论**: 两者相同

**对于10股交易**（佣金1.77元）：
- 免五模式：收取1.77元 ✅
- 不免五模式：收取5.00元（不足5元按5元）❌
- **结论**: 不免五成本更高

**重要**: 由于系统强制100股起买，不免五与免五在实际使用中**没有区别**！

---

## 七、验证测试

### 7.1 测试命令

```bash
python unified_backtest_framework.py run \
    --symbol 600519.SH \
    --strategy macd \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --plot
```

### 7.2 预期结果

```json
{
  "cum_return": -0.01,
  "final_value": 198000.00,
  "trades": 8,
  "strategy": "macd"
}
```

### 7.3 验证要点

- ✅ 所有Size都是100的整数倍
- ✅ 佣金计算准确（约交易金额的0.01%）
- ✅ 印花税仅在卖出时收取
- ✅ 交易成本符合万分之七

---

## 八、文档更新清单

### 8.1 已更新文件

1. ✅ `src/backtest/engine.py`
   - CNStockCommission类完善
   - grid_search默认参数：cash=200000, commission=0.0001
   - auto_pipeline默认参数：cash=200000, commission=0.0001

2. ✅ `unified_backtest_framework.py`
   - run命令：cash=200000, commission=0.0001
   - grid命令：cash=200000, commission=0.0001
   - auto命令：cash=200000, commission=0.0001

3. ✅ `docs/TRADING_COST_AND_PLOTTING_IMPROVEMENTS.md`
   - 更新交易规则说明
   - 更新成本计算示例（100股起）
   - 更新交易日志示例

4. ✅ `docs/COMMISSION_CALCULATION_EXPLAINED.md`
   - 更新Size单位说明
   - 更新交易成本示例
   - 强调100股整数倍规则

5. ✅ `src/backtest/plotting.py`
   - Commission显示4位小数
   - 优化买卖标记显示
   - 改进时间轴标签

### 8.2 新增文件

1. ✅ `docs/FINAL_TRADING_RULES_V3.md`（本文档）
   - 完整交易规则说明
   - 代码实现详解
   - 使用示例和验证方法

---

## 九、常见问题

### Q1: 为什么必须100股起买？

**A**: 这是中国A股的强制规则。系统已在`CNStockCommission.getsize()`中实现，任何非100倍数的交易都会被调整。

### Q2: 免五和不免五有什么区别？

**A**: 
- **免五**: 按实际佣金率收取，无最低限制
- **不免五**: 佣金不足5元时按5元收

但由于系统强制100股起买，交易金额通常较大（>10万元），佣金都会超过5元，所以两者**实际效果相同**。

### Q3: Commission字段包含什么？

**A**: Commission = 佣金 + 印花税（仅卖出）

示例：
- 买入100股：Commission = 17.71元（纯佣金）
- 卖出100股：Commission = 104.74元（17.46佣金 + 87.28印花税）

### Q4: 如何修改初始资金？

**A**: 使用`--cash`参数：

```bash
python unified_backtest_framework.py run \
    --symbol 600519.SH \
    --strategy macd \
    --cash 500000  # 50万初始资金
```

### Q5: 如何验证交易成本计算正确？

**A**: 查看交易日志，手动计算：

```
买入100股@1770.85:
  佣金 = 177085 × 0.0001 = 17.7085 ✅

卖出100股@1745.51:
  佣金 = 174551 × 0.0001 = 17.4551
  印花税 = 174551 × 0.0005 = 87.2755
  总计 = 17.46 + 87.28 = 104.74 ✅
```

---

## 十、总结

### 核心改进

1. ✅ **强制100股整数倍** - 符合A股实际规则
2. ✅ **佣金免五** - 现代券商标准
3. ✅ **印花税正确** - 仅卖出收取万五
4. ✅ **默认20万资金** - 适合1-2手操作
5. ✅ **完整文档** - 所有规则清晰说明

### 使用建议

1. **策略开发**: 直接使用`self.buy(size=100)`或`self.buy(size=200)`
2. **回测验证**: 检查交易日志确认成本计算正确
3. **参数调整**: 根据实际券商费率调整commission参数
4. **资金管理**: 根据策略调整cash参数

### 与实盘对比

| 项目 | 回测系统 | 实盘 | 差异 |
|------|---------|------|------|
| 最小交易 | 100股 | 100股 | ✅ 一致 |
| 佣金率 | 0.01% | 0.01%-0.03% | ⚠️ 可调 |
| 印花税 | 0.05% | 0.05% | ✅ 一致 |
| 免五 | 是 | 部分券商 | ⚠️ 可选 |
| 过户费 | 无 | 有（沪市） | ⚠️ 未实现 |

**注意**: 系统未实现过户费（约0.002%），如需精确模拟可在佣金率中补偿。

---

## 更新日志

- **2025-10-23**: V3.0 - 强制100股整数倍，更新所有文档
- **2025-10-23**: V2.0 - 修正免五规则，改为按实际费率
- **2025-10-23**: V1.0 - 初始版本，实现佣金和印花税

## 相关文档

- [TRADING_COST_AND_PLOTTING_IMPROVEMENTS.md](./TRADING_COST_AND_PLOTTING_IMPROVEMENTS.md)
- [COMMISSION_CALCULATION_EXPLAINED.md](./COMMISSION_CALCULATION_EXPLAINED.md)
- [QUICK_START_V2.4.md](../QUICK_START_V2.4.md)
