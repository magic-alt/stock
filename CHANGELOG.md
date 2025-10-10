# A股监控系统更新日志

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
