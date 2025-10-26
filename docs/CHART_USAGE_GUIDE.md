# 图表生成使用指南 (V2.8.3)

## 快速开始

### CLI 命令格式

```bash
python unified_backtest_framework.py run \
  --strategy [策略名称] \
  --symbols [股票代码] \
  --start [开始日期] \
  --end [结束日期] \
  --benchmark [基准指数] \
  --out_dir [输出目录] \
  --plot
```

### 示例 1: 单只股票 MACD 策略

```bash
python unified_backtest_framework.py run \
  --strategy macd \
  --symbols 600519.SH \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --benchmark 000300.SH \
  --out_dir reports_maotai \
  --plot
```

**输出文件**:
- `reports_maotai/macd_chart.png` - 主图表
- `reports_maotai/macd_nav.csv` - 净值序列
- `reports_maotai/run_nav_vs_benchmark.png` - 净值对比图

### 示例 2: 多只股票 EMA 策略

```bash
python unified_backtest_framework.py run \
  --strategy ema \
  --symbols 600519.SH 000333.SZ 600036.SH \
  --start 2023-01-01 \
  --end 2024-12-31 \
  --benchmark 000300.SH \
  --out_dir reports_multi \
  --plot
```

### 示例 3: 布林带策略（无基准）

```bash
python unified_backtest_framework.py run \
  --strategy bollinger \
  --symbols 601318.SH \
  --start 2022-01-01 \
  --end 2024-12-31 \
  --out_dir reports_bollinger \
  --plot
```

### 示例 4: 自动优化模式（批量生成图表）

```bash
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ \
  --strategies macd ema bollinger rsi \
  --start 2022-01-01 \
  --end 2024-12-31 \
  --benchmark 000300.SH \
  --top_n 5 \
  --out_dir reports_auto \
  --workers 2
```

**输出**: 每个 Top-5 策略都会生成独立图表。

---

## 图表元素说明

### 主图 (Figure 0)

#### 面板 1: 价格与均线
- **K线图**: 红色=上涨, 绿色=下跌（A股习惯）
- **移动平均线**: 
  - SMA(5) - 蓝色短期均线
  - SMA(20) - 橙色中期均线
  - EMA(25) - 绿色指数均线
- **买卖点标记**:
  - 🔺 **买入**: 红色向上三角形 (size 200)
  - 🔻 **卖出**: 亮绿色向下三角形 (size 200)

#### 面板 2: 成交量
- **柱状图**: 红色=放量上涨, 绿色=放量下跌
- **均线**: Volume SMA(20) - 成交量移动平均

#### 面板 3+: 技术指标
根据策略类型显示：
- **MACD**: MACD线, 信号线, 柱状图
- **RSI**: 相对强弱指数 + SMA(10)
- **Bollinger Bands**: 上轨/中轨/下轨
- **Stochastic**: %K线, %D线
- **ADX**: 平均趋向指数
- **CCI**: 商品通道指数
- **ROC**: 变动率指标
- **Momentum**: 动量指标

---

## GUI 使用方法

### 步骤 1: 启动 GUI

```bash
python backtest_gui.py
```

或双击 `启动工具.bat`

### 步骤 2: 配置参数

1. **数据配置** 标签页:
   - 输入股票代码（每行一个）
   - 或使用快速选择按钮：茅台/平安/招行/五粮液
   - 设置日期范围
   - 配置基准指数（默认: 000300.SH）

2. **策略配置** 标签页:
   - 勾选要测试的策略
   - 或使用快速选择：趋势策略/震荡策略/全部

3. **回测配置** 标签页:
   - ✅ **勾选"生成图表"** ← 重要！
   - 设置初始资金/手续费/滑点
   - 选择输出目录

### 步骤 3: 运行回测

点击"开始回测"按钮，图表将自动保存到输出目录。

### 步骤 4: 查看图表

1. 在 GUI 日志中找到输出路径
2. 打开文件管理器，进入输出目录
3. 双击 `*_chart.png` 文件查看

---

## 参数说明

### 必需参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--strategy` | 策略名称 | `macd`, `ema`, `bollinger` |
| `--symbols` | 股票代码（可多个） | `600519.SH` 或 `600519.SH 000333.SZ` |
| `--start` | 开始日期 | `2024-01-01` |
| `--end` | 结束日期 | `2024-12-31` |
| `--plot` | 生成图表 | 添加此标志即可 |

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--benchmark` | None | 基准指数代码 |
| `--out_dir` | None | 输出目录 |
| `--cash` | 200000 | 初始资金（元） |
| `--commission` | 0.0001 | 佣金比例 |
| `--slippage` | 0.0005 | 滑点比例 |
| `--source` | akshare | 数据源 (akshare/yfinance) |
| `--adj` | None | 复权方式 (qfq/hfq) |

### 策略列表

查看所有可用策略:
```bash
python unified_backtest_framework.py list
```

**常用策略**:
- `ema` - 指数移动平均（趋势跟踪）
- `macd` - MACD指标（趋势+动量）
- `bollinger` - 布林带（震荡交易）
- `rsi` - RSI指标（超买超卖）
- `adx_trend` - ADX趋势策略
- `triple_ma` - 三重均线系统
- `donchian` - 唐奇安通道
- `keltner` - 肯特纳通道
- `zscore` - Z-Score均值回归

---

## 高级用法

### 1. 自定义策略参数

使用 `--params` 传递 JSON 格式参数：

```bash
python unified_backtest_framework.py run \
  --strategy macd \
  --symbols 600519.SH \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --params '{"fast": 8, "slow": 21, "signal": 6}' \
  --out_dir reports_custom \
  --plot
```

### 2. 网格搜索 + 图表

```bash
python unified_backtest_framework.py grid \
  --strategy ema \
  --symbols 600519.SH \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --grid '{"period": [5, 10, 20, 30]}' \
  --out_csv grid_results.csv
```

然后手动运行最优参数组合生成图表。

### 3. 提高图表分辨率

**方法 A**: 修改代码（永久）
```python
# src/backtest/plotting.py, line ~390
fig_to_save.savefig(out_file, dpi=600, bbox_inches='tight')  # 改为 600 DPI
```

**方法 B**: 后处理（临时）
```python
from PIL import Image
img = Image.open("reports/macd_chart.png")
img.save("reports/macd_chart_hd.png", dpi=(600, 600))
```

### 4. 调整标记大小

编辑 `src/backtest/plotting.py` 第 ~350 行:

```python
# 买入标记
price_ax.scatter(
    buy_dates, buy_prices,
    marker='^',
    s=300,  # 从 200 增大到 300
    ...
)

# 卖出标记
price_ax.scatter(
    sell_dates, sell_prices,
    marker='v',
    s=300,  # 从 200 增大到 300
    ...
)
```

---

## 故障排除

### 问题 1: 没有生成图表

**症状**: 运行命令后只有 CSV 文件，没有 PNG 图表。

**解决方案**:
1. 确认使用了 `--plot` 参数
2. 检查是否有错误提示
3. 验证 matplotlib 已安装: `pip install matplotlib`

### 问题 2: 图表是空白的

**症状**: 生成了 PNG 文件，但打开后是空白。

**解决方案**:
1. 确认使用 V2.8.3 或更高版本
2. 检查数据是否下载成功: `ls cache/`
3. 手动下载数据:
   ```bash
   python unified_backtest_framework.py run \
     --strategy macd \
     --symbols 600519.SH \
     --start 2024-01-01 \
     --end 2024-12-31
   ```

### 问题 3: 看不到买卖点标记

**症状**: 图表生成了，但没有红色/绿色三角形标记。

**解决方案**:
1. 确认策略有交易记录（查看日志中的 "BUY/SELL EXECUTED"）
2. 检查是否使用 V2.8.3 版本（带有手动标记功能）
3. 尝试增大标记: 修改 `s=200` → `s=300`

### 问题 4: Unicode 编码错误

**症状**: 报错 `UnicodeEncodeError: 'gbk' codec can't encode`

**解决方案**:
1. 升级到 V2.8.3（已修复）
2. 或临时设置环境变量:
   ```powershell
   $env:PYTHONIOENCODING="utf-8"
   python unified_backtest_framework.py run ...
   ```

### 问题 5: 图表太小看不清

**解决方案**:
1. 增大图表尺寸（修改 `plotting.py`）:
   ```python
   figsize=(20, 12)  # 默认 (16, 10)
   ```
2. 提高 DPI:
   ```python
   dpi=600  # 默认 300
   ```

---

## 最佳实践

### 1. 数据准备
建议先下载数据再批量回测：
```bash
# GUI: 点击"下载数据"按钮
# CLI: 运行一次无 --plot 的快速回测
```

### 2. 快速测试
使用短周期数据快速验证策略：
```bash
--start 2024-07-01 --end 2024-10-01  # 3个月数据
```

### 3. 批量分析
使用 auto 模式进行系统化回测：
```bash
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ 600036.SH \
  --strategies macd ema bollinger rsi adx_trend \
  --start 2022-01-01 \
  --end 2024-12-31 \
  --top_n 10 \
  --out_dir reports_comprehensive \
  --workers 4
```

### 4. 结果对比
将所有图表放在同一目录，方便对比：
```bash
reports_comparison/
├─ macd_600519_chart.png
├─ ema_600519_chart.png
├─ bollinger_600519_chart.png
└─ rsi_600519_chart.png
```

---

## 图表阅读技巧

### 1. 识别趋势
- **上涨趋势**: 价格在均线上方，买入标记多
- **下跌趋势**: 价格在均线下方，卖出标记多
- **震荡行情**: 价格围绕均线波动，买卖交替

### 2. 分析买卖点
- 🔺 **买入**: 查看是否在低点，指标是否支持
- 🔻 **卖出**: 查看是否在高点，是否及时止盈/止损

### 3. 观察成交量
- **放量上涨**: 趋势强劲
- **缩量上涨**: 谨慎追高
- **放量下跌**: 恐慌出逃
- **缩量下跌**: 可能见底

### 4. 指标确认
- **MACD 金叉**: 买入信号（DIF 上穿 DEA）
- **MACD 死叉**: 卖出信号（DIF 下穿 DEA）
- **RSI > 70**: 超买区域（考虑卖出）
- **RSI < 30**: 超卖区域（考虑买入）
- **布林带突破**: 价格突破上轨=强势，跌破下轨=弱势

---

## 示例图表解读

### 案例: 600519.SH (茅台) MACD 策略

**图表元素**:
1. **价格面板**:
   - K线显示 2024年 价格从 1740 → 1533（下跌）
   - 7个红色买入点，7个绿色卖出点
   - SMA(5/20) 显示短期趋势变化

2. **成交量面板**:
   - 7月放量下跌（恐慌盘）
   - 9月缩量反弹（无力）

3. **MACD 面板**:
   - 3月 MACD 金叉 → 买入
   - 3月底 MACD 死叉 → 卖出
   - 后续多次金叉/死叉交易

4. **交易结果**:
   - 总交易: 7次
   - 胜率: 28.6% (2/7)
   - 累计收益: -10.16%（亏损）
   - 最大回撤: -17.24%

**分析**:
- MACD 策略在震荡市中频繁交易导致亏损
- 建议改用趋势策略（EMA/ADX）或降低交易频率

---

## 相关文档

- **完整文档**: `docs/V2.8.3_CHART_FIXES.md`
- **策略说明**: `docs/STRATEGY_MODULES.md`
- **GUI 指南**: `docs/GUI_V2.8.2_UPDATE.md`
- **API 文档**: `docs/API_REFERENCE.md`

---

## 更新日志

- **V2.8.3** (2025-10-25): 修复图表生成、买卖点标记、Unicode编码
- **V2.8.2** (2025-10-25): 单股选择、下载数据、图表保存
- **V2.8.1** (2025-10-24): 基准指数、预设配置、输出格式

---

**文档版本**: 1.0  
**适用版本**: V2.8.3+  
**最后更新**: 2025-10-25
