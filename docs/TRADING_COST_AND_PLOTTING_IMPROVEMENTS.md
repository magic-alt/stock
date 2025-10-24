# 交易成本与图表优化说明

## 优化内容总览

本次优化解决了三个关键问题：

1. ✅ **横坐标时间轴显示** - 图表横轴现在清晰显示交易日期
2. ✅ **买卖标记可见性** - 买入/卖出箭头更大、更醒目
3. ✅ **真实交易成本** - 完整模拟中国A股交易费用（佣金+印花税）

---

## 1. 中国A股交易成本设置

### 交易规则
- **初始资金**: 200,000元（默认）
- **最小交易单位**: 1手 = 100股（强制执行）
- **交易规则**: 只能买卖100股的整数倍（100、200、300...）
- **佣金率**: 万分之一 (0.0001)
- **佣金规则**: 
  - **免五（默认）**: 按实际佣金率收取，无最低限制
  - **不免五**: 佣金不足5元时按5元收取（需修改代码参数）
- **印花税**: 万分之五 (0.0005)，**仅卖出时收取**

**重要**: 系统已强制所有交易必须是100股的整数倍，符合A股实际交易规则。

### 成本计算示例

#### 买入示例（100股 = 1手）
```
买入价格: 1770.85元/股
买入数量: 100股（1手）
交易金额: 177,085元
佣金计算: 177,085 × 0.0001 = 17.71元（免五，按实际收取）
印花税: 0元（买入不收）
总成本: 177,085 + 17.71 = 177,102.71元
```

#### 卖出示例（100股 = 1手）
```
卖出价格: 1745.51元/股
卖出数量: 100股（1手）
交易金额: 174,551元
佣金计算: 174,551 × 0.0001 = 17.46元（免五，按实际收取）
印花税: 174,551 × 0.0005 = 87.28元
总费用: 17.46 + 87.28 = 104.74元
实际到手: 174,551 - 104.74 = 174,446.26元
```

#### 买入示例（200股 = 2手）
```
买入价格: 1770.85元/股
买入数量: 200股（2手）
交易金额: 354,170元
佣金计算: 354,170 × 0.0001 = 35.42元（免五，按实际收取）
印花税: 0元（买入不收）
总成本: 354,170 + 35.42 = 354,205.42元
```

#### 卖出示例（200股 = 2手）
```
卖出价格: 1745.51元/股  
卖出数量: 200股（2手）
交易金额: 349,102元
佣金计算: 349,102 × 0.0001 = 34.91元（免五，按实际收取）
印花税: 349,102 × 0.0005 = 174.55元
总费用: 34.91 + 174.55 = 209.46元
实际到手: 349,102 - 209.46 = 348,892.54元
```

### 实现代码
位置: `src/backtest/engine.py` 第136-178行

```python
class CNStockCommission(bt.CommInfoBase):
    """中国A股佣金和印花税计算"""
    params = (
        ('commission', 0.0001),      # 佣金率：万分之一
        ('stamp_duty', 0.0005),      # 印花税：万分之五
        ('min_commission', 0.0),     # 最低佣金：0元（免五）
    )
    
    def _getcommission(self, size, price, pseudoexec):
        """计算佣金
        
        免五模式（min_commission=0）：按实际佣金率收取
        不免五模式（min_commission=5）：佣金不足5元按5元收取
        """
        value = abs(size) * price
        comm = value * self.p.commission
        
        # 如果设置了最低佣金（不免五）
        if self.p.min_commission > 0 and comm < self.p.min_commission:
            comm = self.p.min_commission
        
        return comm
    
    def getcommission(self, size, price):
        """总交易成本 = 佣金 + 印花税（仅卖出）"""
        # 佣金（买卖都收）
        comm = self._getcommission(size, price, False)
        
        # 印花税仅在卖出时收取
        stamp = 0.0
        if size < 0:  # 卖出
            stamp = abs(size) * price * self.p.stamp_duty
        
        return comm + stamp
```

---

## 2. 图表时间轴优化

### 改进前
- 横坐标显示空白或数字索引
- 无法直观看出交易日期

### 改进后
- ✅ 清晰显示 `YYYY-MM-DD` 格式日期
- ✅ 根据数据量自动调整日期间隔
  - 数据>500天: 每20个交易日显示
  - 数据>250天: 每10个交易日显示
  - 数据>100天: 每5个交易日显示
  - 数据<100天: 每2个交易日显示
- ✅ 日期标签45度倾斜，避免重叠
- ✅ 显示次要刻度线，便于定位
- ✅ 粗体标注"交易日期 (Trading Date)"

### 实现代码
位置: `src/backtest/plotting.py` 第325-360行

```python
# 强制启用日期模式
ax.xaxis_date()
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))

# 旋转标签
plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)

# 设置轴标签
ax.set_xlabel('交易日期 (Trading Date)', fontsize=9, fontweight='bold')

# 强制刷新日期格式
fig.autofmt_xdate(rotation=45, ha='right')
```

---

## 3. 买卖标记优化

### 改进前
- 标记尺寸小 (size=12)
- 颜色不够鲜明
- 轮廓细，不易辨识

### 改进后
- ✅ **标记尺寸增大**: 12 → 15
- ✅ **买入标记**: 
  - 符号: ▲ (向上三角形)
  - 颜色: 红色 (red)
  - 轮廓: 深红色 (darkred), 2.0px粗
  - 透明度: 90%
- ✅ **卖出标记**: 
  - 符号: ▼ (向下三角形)
  - 颜色: 亮绿色 (lime) - 比普通绿色更显眼
  - 轮廓: 深绿色 (darkgreen), 2.0px粗
  - 透明度: 90%

### 实现代码
位置: `src/backtest/plotting.py` 第282-310行

```python
class CNPlotScheme(PlotScheme):
    def __init__(self):
        # 买入标记
        self.trademarker = '^'               # 向上三角
        self.trademarkersize = 15            # 增大尺寸
        self.trademarkercolor = 'red'        # 红色
        self.trademarkeroutline = 'darkred'  # 深红轮廓
        self.trademarkeroutlinewidth = 2.0   # 粗轮廓
        self.trademarkeralpha = 0.9          # 90%透明度
        
        # 卖出标记
        self.sellmarker = 'v'                # 向下三角
        self.sellmarkersize = 15             # 增大尺寸
        self.sellmarkercolor = 'lime'        # 亮绿色
        self.sellmarkeroutline = 'darkgreen' # 深绿轮廓
        self.sellmarkeroutlinewidth = 2.0    # 粗轮廓
        self.sellmarkeralpha = 0.9           # 90%透明度
```

---

## 4. 使用方法

### 单策略回测（默认200,000元）
```bash
python unified_backtest_framework.py run \
    --symbol 600519.SH \
    --strategy macd \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --plot
```

### 自定义初始资金
```bash
python unified_backtest_framework.py run \
    --symbol 600519.SH \
    --strategy macd \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --cash 500000 \
    --plot
```

### 多策略优化
```bash
python unified_backtest_framework.py auto \
    --symbols 600519.SH 000333.SZ \
    --start 2022-01-01 \
    --end 2024-12-31 \
    --strategies macd rsi bollinger \
    --cash 200000
```

---

## 5. 交易日志输出示例

### 免五模式（默认，100股/手交易）
```
================================================================================
交易日志 (Trade Log)
================================================================================
Starting Portfolio Value: 200000.00

2023-03-24, BUY EXECUTED, Size 100, Price: 1770.85, Cost: 177085.00, Commission 17.7085
2023-04-12, SELL EXECUTED, Size -100, Price: 1745.51, Value: 177085.00, Commission 104.7306
2023-04-28, BUY EXECUTED, Size 100, Price: 1764.77, Cost: 176477.00, Commission 17.6477
...

Final Portfolio Value: 198500.00
================================================================================
```

**说明**:
- **Size**: 以股为单位，必须是100的整数倍
  - Size 100 = 100股 = 1手
  - Size 200 = 200股 = 2手
  - Size 300 = 300股 = 3手
- **Commission**: 总费用（佣金 + 印花税）
  - **买入100股**: 佣金约17.71元
  - **卖出100股**: 佣金17.46元 + 印花税87.28元 = 104.74元

---

## 6. 技术细节

### 佣金计算逻辑
```python
def _getcommission(self, size, price, pseudoexec):
    """
    免五模式（默认）：min_commission = 0.0
    不免五模式：min_commission = 5.0
    """
    value = abs(size) * price
    comm = value * 0.0001
    
    # 免五：无最低限制
    if self.p.min_commission == 0:
        return comm
    
    # 不免五：不足5元按5元收
    if comm < self.p.min_commission:
        comm = self.p.min_commission
    
    return comm

def getcommission(self, size, price):
    """
    size > 0: 买入
    size < 0: 卖出
    """
    # 佣金（买卖都收）
    comm = self._getcommission(size, price, False)
    
    # 印花税（仅卖出）
    stamp = 0.0
    if size < 0:
        stamp = abs(size) * price * 0.0005
    
    return comm + stamp
```

#### 示例计算（1股交易，免五模式）

**买入1股 @ 1770.85元**：
```python
佣金 = 1770.85 × 0.0001 = 0.1771元
印花税 = 0元
总费用 = 0.1771元
```

**卖出1股 @ 1745.51元**：
```python
佣金 = 1745.51 × 0.0001 = 0.1745元
印花税 = 1745.51 × 0.0005 = 0.8728元
总费用 = 0.1745 + 0.8728 = 1.0473元
```

#### 示例计算（100股交易，免五模式）

**买入100股 @ 1770.85元**：
```python
佣金 = 177085 × 0.0001 = 17.71元
印花税 = 0元
总费用 = 17.71元
```

**卖出100股 @ 1745.51元**：
```python
佣金 = 174551 × 0.0001 = 17.46元
印花税 = 174551 × 0.0005 = 87.28元
总费用 = 17.46 + 87.28 = 104.74元
```

### 最小交易单位（100股）
```python
def getsize(self, price, cash):
    """计算可买数量（100股整数倍）"""
    # 预估成本含税费
    effective_price = price * 1.0006
    max_shares = int(cash / effective_price)
    
    # 向下取整到100倍数
    lots = max_shares // 100
    return lots * 100
```

---

## 7. 验证结果

### 测试案例: 600519.SH (茅台) 2023年
- **初始资金**: 200,000元
- **交易规则**: 每次最少100股（1手），必须是100股的整数倍
- **最终资金**: ~198,500元（预估）
- **交易次数**: 约5-10次（每次100股或200股）

### 佣金明细（100股/手交易）
- **买入佣金**: 约17.71元/手
- **卖出佣金**: 约17.46元/手
- **印花税**: 约87.28元/手（仅卖出）
- **单次完整交易成本**: 约122元（17.71买入 + 17.46卖出 + 87.28印花税）

### 成本占比分析

#### 100股交易（1手）
```
交易金额: 约177,000元
双向成本: 约122元
成本占比: 122 / 177000 = 0.069%
```

#### 200股交易（2手）
```
交易金额: 约354,000元
双向成本: 约244元
成本占比: 244 / 354000 = 0.069%
```

**结论**: 交易成本约为交易金额的万分之七（0.07%），符合A股实际情况。

### 图表验证
- ✅ 横坐标显示完整日期 (2023-01-01 ~ 2023-12-31)
- ✅ 买入点显示红色▲，卖出点显示绿色▼
- ✅ 标记清晰可见，大小合适

---

## 8. 配置文件更新

### unified_backtest_framework.py
- 默认初始资金: 100000 → **200000**
- 默认佣金率: 0.001 → **0.0001**
- 所有命令(run/grid/auto)统一更新

### src/backtest/engine.py
- 新增 `CNStockCommission` 类
- 实现佣金免五规则
- 实现卖出印花税计算
- 实现100股整数倍交易

### src/backtest/plotting.py
- 增强时间轴显示（日期格式化）
- 增大买卖标记尺寸（15px）
- 优化标记颜色（lime绿更显眼）
- 增加标记轮廓（2px粗边框）

---

## 9. 注意事项

### Size单位说明
- **Backtrader中Size单位是股**
  - Size 1 = 1股
  - Size 100 = 100股 = 1手
  - Size 1000 = 1000股 = 10手

### 佣金免五 vs 不免五

#### 免五（默认配置）
```python
CNStockCommission(
    commission=0.0001,      # 万一
    stamp_duty=0.0005,      # 印花税万五
    min_commission=0.0      # 免五：无最低限制
)
```
- ✅ 适合小额交易、高频交易
- ✅ 按实际佣金率收取，精确计算
- ⚠️ 1股交易佣金仅0.17元左右

#### 不免五
```python
CNStockCommission(
    commission=0.0001,
    stamp_duty=0.0005,
    min_commission=5.0      # 不免五：最低5元
)
```
- ⚠️ 小额交易成本高
- 示例：1股@1770元，理论佣金0.17元，实收5元（实际费率2.8‰）
- 适合模拟老券商账户

### 交易成本影响

#### 1股交易（免五）
```
买入：1770.85元，佣金0.18元（费率0.010%）
卖出：1745.51元，总费用1.05元（费率0.060%）
双向成本：约0.070%
```

#### 100股交易（免五）
```
买入：177,085元，佣金17.71元（费率0.010%）
卖出：174,551元，总费用104.74元（费率0.060%）
双向成本：约0.070%
```

#### 1股交易（不免五）
```
买入：1770.85元，佣金5元（费率0.282%）❌ 成本过高
卖出：1745.51元，总费用5.87元（费率0.336%）
双向成本：约0.618%
```

### 印花税只在卖出收取
- ✅ 买入: 只收佣金
- ✅ 卖出: 佣金 + 印花税（万分之五）
- 双向总成本: 约万分之六 (0.0001 + 0.0001 + 0.0005 = 0.0006)

### 图表性能优化
- 数据量大时（>500天），日期标签自动稀疏显示
- 避免标签过密导致重叠
- 可通过鼠标悬停查看精确日期

---

## 10. 后续优化建议

### 可考虑的改进
1. **融资融券成本**: 增加利息计算
2. **过户费**: 沪市股票收取（深市不收）
3. **分级佣金**: 根据资金量调整佣金率
4. **税费优化策略**: 考虑持仓时间影响（>1年免税等）

### 数据验证
- 建议与实盘券商账单对比验证
- 不同券商佣金率可能有差异
- 可通过 `--commission` 参数自定义

---

## 更新时间
2025-10-23

## 相关文档
- [PLOTTING_ENHANCEMENTS_V2.md](./PLOTTING_ENHANCEMENTS_V2.md) - 绘图增强说明
- [CACHE_SYSTEM_GUIDE.md](./CACHE_SYSTEM_GUIDE.md) - 缓存系统使用
- [QUICK_START_V2.4.md](../QUICK_START_V2.4.md) - 快速入门指南
