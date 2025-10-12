# A股监控系统更新日志

## V2.4.0 (2025-10-12) - Unified Backtest Framework 模块化重构

### 🎯 重大更新

#### 数据下载模块化
- ✅ **akshare_source.py 增强**
  - 新增 `load_stock_daily_batch()` - 批量下载股票历史数据
  - 新增 `load_index_daily()` - 下载指数历史数据
  - 新增 `_standardize_stock_dataframe()` - 数据格式标准化
  - 支持 CSV 文件缓存，避免重复下载
  - 使用现有的稳定多数据源自动切换机制
  - 自动重试3次，带随机退避延迟
  - 智能限速（0.3-0.5秒），防止被封禁
  - 成交额统一转换为"元"

- ✅ **yfinance_source.py 增强**
  - 新增 `load_stock_daily_batch()` - 批量下载全球股票
  - 新增 `load_index_daily()` - 下载全球指数
  - 新增 `download_batch_with_retry()` - 带重试机制的批量下载
  - 新增 `get_all_indices_realtime()` - 获取常见指数实时数据
  - 支持美股、港股、A股、全球指数
  - CSV 缓存支持
  - 最多3次重试机制

#### 报告生成模块化
- ✅ **report_generator.py 新建**
  - `BacktestMetrics` 类 - 专业指标计算器
    - 累计收益率、年化收益率、年化波动率
    - 夏普比率、最大回撤
    - 胜率、盈亏比
    - 一键计算所有指标
  
  - `ReportGenerator` 类 - 报告生成器
    - 生成文本报告（TXT + JSON）
    - 绘制净值对比图（策略 vs 基准）
    - 绘制回撤曲线
    - 绘制收益率分布直方图
    - 保存净值到 CSV
    - 一键生成完整报告
  
  - `quick_report()` 便捷函数 - 快速生成完整报告

#### 策略模块化 (NEW!)
- ✅ **提取9个Backtrader策略到独立文件**
  
  **指标策略 (6个)**:
  - `ema_backtrader_strategy.py` - EMA均线交叉策略
  - `macd_backtrader_strategy.py` - MACD信号交叉策略
  - `bollinger_backtrader_strategy.py` - Bollinger布林带均值回归
  - `rsi_backtrader_strategy.py` - RSI超买超卖策略
  - `keltner_backtrader_strategy.py` - Keltner通道均值回归
  - `zscore_backtrader_strategy.py` - Z-Score均值回归

  **趋势策略 (3个)**:
  - `donchian_backtrader_strategy.py` - Donchian通道突破
  - `triple_ma_backtrader_strategy.py` - 三均线多头排列
  - `adx_backtrader_strategy.py` - ADX趋势强度过滤

- ✅ **backtrader_registry.py 策略注册器**
  - 统一管理所有Backtrader策略
  - `list_backtrader_strategies()` - 列出所有可用策略
  - `get_backtrader_strategy(name)` - 获取策略模块
  - `create_backtrader_strategy(name, **params)` - 创建策略实例
  - 自动参数类型转换
  - 支持网格搜索参数配置

- ✅ **策略特性**
  - 每个策略独立文件，便于维护
  - 统一的参数接口和配置格式
  - 完整的参数验证和类型转换
  - 支持自定义参数和默认参数
  - 清晰的文档字符串和使用说明

### 📝 变更文件
**新增**:
- `src/backtest/report_generator.py` - 报告生成模块（600+ 行）
- `src/strategies/ema_backtrader_strategy.py` - EMA策略
- `src/strategies/macd_backtrader_strategy.py` - MACD策略
- `src/strategies/bollinger_backtrader_strategy.py` - Bollinger策略
- `src/strategies/rsi_backtrader_strategy.py` - RSI策略
- `src/strategies/keltner_backtrader_strategy.py` - Keltner策略
- `src/strategies/zscore_backtrader_strategy.py` - Z-Score策略
- `src/strategies/donchian_backtrader_strategy.py` - Donchian策略
- `src/strategies/triple_ma_backtrader_strategy.py` - Triple MA策略
- `src/strategies/adx_backtrader_strategy.py` - ADX策略
- `src/strategies/backtrader_registry.py` - 策略注册器（250+ 行）
- `test_report_generator.py` - 报告生成测试
- `test_data_download.py` - 数据下载测试
- `test_backtrader_strategies.py` - 策略模块测试
- `docs/MODULAR_REFACTORING_REPORT.md` - 数据源重构报告
- `docs/STRATEGY_MODULARIZATION_REPORT.md` - 策略模块化报告
- `STRATEGY_MODULARIZATION_COMPLETED.md` - 完成总结
- `docs/REFACTORING_COMPLETED_REPORT.md` - 完成报告
- `QUICK_START_GUIDE.md` - 快速上手指南

**修改**:
- `src/data_sources/akshare_source.py` - 新增批量下载和CSV缓存功能
- `src/data_sources/yfinance_source.py` - 新增批量下载和重试机制

### 🧪 测试验证
**报告生成测试** ✅:
```bash
python test_report_generator.py
```
结果：
- ✅ 指标计算测试通过
- ✅ 报告生成测试通过
- ✅ 快速报告测试通过
- ✅ 生成 6 个 PNG + 2 个 JSON + 2 个 TXT + 1 个 CSV

**测试指标示例**:
```
累计收益率: -10.70%
年化收益率: -7.49%
年化波动率: 30.91%
夏普比率: -0.20
最大回撤: 48.75%
胜率: 62.50%
盈亏比: 2.64
```

### 💡 使用示例

#### 数据下载
```python
from src.data_sources.akshare_source import AKShareDataSource

source = AKShareDataSource()
data = source.load_stock_daily_batch(
    symbols=['000001', '600519'],
    start='2024-01-01',
    end='2024-12-31',
    cache_dir='./cache'
)
```

#### 报告生成
```python
from src.backtest.report_generator import quick_report

results = quick_report(
    strategy_name='My_Strategy',
    nav_series=nav_series,
    benchmark_series=benchmark_series,
    output_dir='./reports'
)
```

### 🎯 改进对比
**改进前**:
- unified_backtest_framework.py (2700+ 行单文件)
- 连接不稳定，无缓存机制
- 报告生成功能分散

**改进后**:
- ✅ 模块化设计，易于维护
- ✅ 稳定的多数据源自动切换
- ✅ CSV 缓存提高效率
- ✅ 统一的报告生成接口
- ✅ 完善的错误处理和日志

### 📊 功能覆盖
- ✅ A股数据下载（AKShare）
- ✅ 全球市场数据下载（YFinance）
- ✅ CSV 缓存机制
- ✅ 10+ 项性能指标计算
- ✅ 3 种可视化图表
- ✅ 多格式报告导出（TXT/JSON/CSV/PNG）

### 🔧 待完成任务
- ⏳ 提取策略到 strategies 文件夹（11个策略）
- ⏳ 简化 unified_backtest_framework.py
- ⏳ 完整的集成测试

### 📚 文档
- `docs/MODULAR_REFACTORING_REPORT.md` - 详细技术文档
- `docs/REFACTORING_COMPLETED_REPORT.md` - 完成报告和使用示例
- `QUICK_START_GUIDE.md` - 快速上手指南
- `test_report_generator.py` - 测试示例代码
- `test_data_download.py` - 数据下载测试

---

## V2.3.1 (2025-01-10) - 数据库预览功能

### 🎯 新增功能

#### 数据库预览系统
- ✅ **命令行预览**：通过 `data_manager.py preview` 查看数据库内容
- ✅ **交互式预览**：在主程序菜单中添加"数据库预览"选项
- ✅ **多种视图**：汇总、详情、更新记录等5种预览方式
- ✅ **格式化输出**：美观的表格显示，支持大数字千分位分隔

#### 预览功能详情
1. **股票数据汇总** - 显示所有股票的数据量和日期范围
2. **指数数据汇总** - 显示所有指数的数据量和日期范围
3. **最近更新记录** - 查看最近10次数据更新情况
4. **指定股票详情** - 查看单个股票的OHLCV详细数据
5. **指定指数详情** - 查看单个指数的详细行情数据

#### 诊断工具
- 📊 快速数据库检查脚本 `test_db_preview.py`
- 📖 详细使用指南 `docs/DATABASE_PREVIEW_GUIDE.md`
- 🔍 数据完整性验证

### 📝 变更文件
- `main.py` - 添加 `preview_database()` 和5个预览函数
- `data_manager.py` - 添加 `cmd_preview_data()` 命令
- `test_db_preview.py` - 新增数据库内容检查工具
- `docs/DATABASE_PREVIEW_GUIDE.md` - 新增预览功能使用指南

### 📊 当前数据状态
- 股票历史数据: 1,021 条（34只股票）
- 指数历史数据: 210 条（7个指数）
- 更新记录: 41 条
- 数据库大小: 288 KB
- 数据日期范围: 2025-09-12 至 2025-10-12

### 🔧 问题修复
- 解决用户在 DB Browser 中看不到数据的困惑
- 明确区分主数据库和测试数据库位置
- 提供多种方式验证数据存在性

---

## V2.2.3 (2025-10-10) - 日志系统优化

### 🎯 优化内容

#### 分层日志策略
- ✅ **控制台**：只显示用户友好信息和严重错误（ERROR级别）
- ✅ **日志文件**：记录所有WARNING及以上级别，供调试
- ✅ **去重机制**：logger.warning() 也纳入60秒去重控制

#### 配置改进
- 添加 `logging.basicConfig` 配置
- 控制台 handler 设置为 ERROR 级别
- 所有 WARNING 信息写入 `monitor.log` 文件

#### 用户体验
- 控制台保持清爽，无技术日志刷屏
- 详细错误信息保存在日志文件
- 开发者可随时查看完整日志

### 📝 变更文件
- `main.py` - 添加日志配置
- `src/data_sources/akshare_source.py` - logger 纳入去重控制

---

## V2.2.2 (2025-10-10) - 网络错误日志优化

### 🎯 优化内容

#### 用户体验改进
- ✅ **错误去重机制**：相同网络错误60秒内只显示一次
- ✅ **友好提示文字**：替换技术错误信息为用户友好提示
- ✅ **缓存年龄显示**：显示旧缓存的年龄（分钟），便于判断数据新鲜度
- ✅ **错误分类提示**：区分网络错误 vs 非交易时间

#### 技术改进
- 添加 `_last_error_time` 属性跟踪上次错误时间
- 优化控制台输出，减少重复信息
- 保留完整日志记录供调试

### 📝 变更文件
- `src/data_sources/akshare_source.py` - 错误去重逻辑
- `src/monitors/realtime_monitor.py` - 友好错误提示

---

## V2.2.1 (2025-10-10) - 成交额单位修复

### 🐛 问题修复

#### 成交额显示错误
- ❌ **问题**：成交额显示"天文数字"（如：1198192.46亿）
- ✅ **原因**：AKShare API 单位不统一（个股=万元，指数=亿元）
- ✅ **修复**：数据源统一转换为"元"，格式化层自动选择单位

#### 架构优化
- 数据源层：统一输出【元】（`_to_yuan()` 函数）
- 格式化层：以【元】为输入，自动选择【万/亿】显示
- 单位配置：中心化管理（`AMOUNT_UNIT_STOCK`, `AMOUNT_UNIT_INDEX`）

### 📝 变更文件
- `src/data_sources/akshare_source.py` - 单位标准化
- `src/utils/formatters.py` - 格式化函数更新
- `test_utils.py` - 测试用例更新

---

## V2.2 (2025-10-10) - 工具模块重构

### 🛠 模块化改进

#### 新增工具模块
- ✅ `src/utils/formatters.py` - 统一格式化工具（9个函数）
- ✅ `src/utils/safe_cast.py` - 安全类型转换（9个函数）
- ✅ `src/utils/timebox.py` - 交易时间管理（TradingCalendar类）

#### 代码重构
- `src/data_sources/akshare_source.py` - 使用 safe_cast 和 logging
- `src/monitors/realtime_monitor.py` - 使用 formatters 和 timebox

#### 测试覆盖
- `test_utils.py` - 综合测试套件
- 所有核心功能测试通过

---

## V2.1.1 (2025-10-09) - NaN错误修复

### 🐛 Bug修复
- ✅ 修复非交易时间 "cannot convert float NaN to integer" 错误
- ✅ 添加 NaN 安全处理（safe_float, safe_int）
- ✅ 非交易时间友好提示

---

## V2.1 (2025-10-09) - 三大修复

### 🎯 核心修复
1. ✅ **成交额显示错误**：单位换算修正（万元 → 显示）
2. ✅ **交易股数错误**：最小100股整数倍，修正成本计算
3. ✅ **Backtrader集成**：专业回测引擎，支持图表显示

### 📊 回测引擎
- 简单回测引擎：快速回测
- Backtrader引擎：专业回测+可视化

---

## V2.0 (初始版本)

### 🚀 核心功能
- 实时监控系统
- 策略回测
- 股票分组管理
- 技术指标计算

### 📁 模块化架构
- `data_sources/` - 数据源模块
- `strategies/` - 策略模块
- `indicators/` - 指标模块
- `backtest/` - 回测模块
- `monitors/` - 监控模块

---

## 未来规划

### 待实现功能
- [ ] CLI 参数化（argparse/typer）
- [ ] 策略注册表机制
- [ ] 标准化日志系统
- [ ] 数据缓存策略优化
- [ ] 更多单元测试
- [ ] CI/CD 集成
- [ ] 配置文件验证
- [ ] 性能监控

### 架构优化
- [ ] 数据契约定义（dataclass/pydantic）
- [ ] 交易日历管理
- [ ] 事件驱动架构
- [ ] 插件化策略系统

---

**当前版本：** V2.2.2  
**最后更新：** 2025-10-10  
**维护者：** GitHub Copilot + 用户
