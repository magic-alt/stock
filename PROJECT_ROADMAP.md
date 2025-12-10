# 项目路线图 | Project Roadmap

**项目**: 量化回测与实盘系统 (Unified Quant Platform)  
**当前版本**: V3.1.0-alpha.3  
**更新日期**: 2025-12-10  
**状态**: 🟢 商业级架构升级中

---

## 📋 目录

- [版本历史](#版本历史)
- [当前状态](#当前状态)
- [架构升级计划](#架构升级计划)
- [开发路线图](#开发路线图)
- [已完成功能](#已完成功能)
- [进行中任务](#进行中任务)
- [未来计划](#未来计划)

---

## 🎯 商业级系统升级目标

### 核心目标
构建一个**生产就绪的自动化量化交易系统**，具备：
- 🏢 **企业级架构**: 清晰的模块边界、统一的接口规范
- 🔒 **风控系统**: 多层次风险管理（账户级/策略级/订单级）
- ⚡ **高性能**: 低延迟执行、高并发回测
- 🔄 **回测-实盘统一**: 一次编写策略，无缝切换环境
- 📊 **专业分析**: 机构级绩效归因、风险分析

### 关键技术挑战
1. **策略接口统一**: Backtrader 策略 vs 事件驱动策略
2. **数据流标准化**: 历史回测 vs 实时行情
3. **执行层抽象**: 模拟撮合 vs 真实 API
4. **状态管理**: 持仓、订单、账户的一致性

---

## 📅 版本历史

### V3.1.0-alpha (2025-12-09) 🆕 当前版本
**主题**: 商业级架构升级 + 代码清理

**本次更新**:
- 🔍 **深度代码审查**: 识别冗余模块和技术债务
- 🧹 **代码清理**: 删除废弃的 template 模块
- 📐 **架构规划**: 制定商业级系统升级路线

**架构问题识别**:
```
❌ 发现问题:
1. strategy/ 与 strategies/ 目录功能重叠
2. 3 套策略基类 (base.py, strategy_base.py, template.py)
3. 33+ 处 print 语句未使用 logger
4. 策略文件命名不规范 (*_template.py)
5. 部分硬编码配置值
```

**清理计划**:
| 模块 | 状态 | 说明 |
|------|------|------|
| `src/strategy/` | ✅ 已删除 | 与 `core/strategy_base.py` 重复 |
| `ema_template.py` | ✅ 已删除 | 与 `ema_backtrader_strategy.py` 重复 |
| `macd_template.py` | ✅ 已删除 | 与 `macd_backtrader_strategy.py` 重复 |

### V3.0.0-alpha (2025-12-03)
**主题**: 架构统一与实盘准备

**核心更新**:
- ✅ **统一接口层**: 新增 `src/core/interfaces.py`，集中定义所有 Protocol
- ✅ **策略统一**: 新增 `src/core/strategy_base.py`，实现 "一次编写，到处运行"
- ✅ **Gateway 清理**: `PaperGatewayV3` 移除 V2 遗留代码，强制使用 MatchingEngine
- ✅ **类型安全**: 新增 `BarData`, `PositionInfo`, `AccountInfo` 等统一数据结构
- ✅ **Backtrader 适配器**: `BacktraderStrategyAdapter` 自动包装 BaseStrategy

**架构亮点**:
```
BaseStrategy (统一策略接口)
    ├── BacktraderStrategyAdapter → Backtrader 回测
    └── PaperRunner (Future) → EventEngine 实盘/模拟
```

### V2.10.2.0 (2025-10-26) ✅ 稳定版本
**主题**: 企业级重构 + 报告系统 + CI/CD

**核心更新**:
- ✅ Markdown回测报告系统
- ✅ GitHub CI/CD持续集成
- ✅ 项目目录结构标准化
- ✅ Pre-commit钩子和代码质量检查
- ✅ 完善文档和示例代码

**详细**: 查看 [CHANGELOG.md](CHANGELOG.md#v21020---2025-10-26)

---

### V2.10.1.2 (2025-01-26)
**主题**: 数据库优化 + 复权文档

- ✅ 数据库增加公司名称字段
- ✅ 复权类型详细文档 (230+行)
- ✅ 自动保存报告到report目录
- ✅ 双格式保存 (PNG + Pickle)

---

### V2.10.1.1 (2025-01-26)
**主题**: 数据库结构优化

- ✅ Per-Symbol独立表架构
- ✅ 国际指数支持
- ✅ CSV批量导入功能
- ✅ 13/13测试通过

---

### V2.8.5
**主题**: ML策略集成

- ✅ 机器学习走步训练策略
- ✅ XGBoost/RandomForest/PyTorch支持
- ✅ 自动特征工程
- ✅ 多空独立阈值

---

### V2.5.1
**主题**: 关键Bug修复

- ✅ 修复StopIteration错误
- ✅ 修复AKShare符号格式问题
- ✅ 修复时区不匹配错误

---

### V2.5.0 - Phase 2 完成
**主题**: 模块化重构

- ✅ 分析、绘图、自动化模块分离
- ✅ 代码从2138行精简到214行
- ✅ Pareto前沿分析
- ✅ 风险平价策略

---

## 🎯 当前状态

### 项目成熟度
| 模块 | 状态 | 完成度 | 说明 |
|------|------|--------|------|
| **数据源** | 🟢 稳定 | 95% | 支持AKShare/YFinance/TuShare |
| **策略库** | 🟢 稳定 | 90% | 15+策略，包含ML策略 |
| **回测引擎** | 🟢 稳定 | 95% | 单次/批量/自动化流程 |
| **可视化** | 🟢 稳定 | 90% | 7种指标图表 + Markdown报告 |
| **GUI界面** | 🟡 完善中 | 80% | tkinter界面，功能完整 |
| **文档** | 🟢 完善 | 95% | 完整文档 + 示例代码 |
| **测试** | 🟢 完善 | 90% | 单元测试 + 集成测试 (164 tests) |
| **CI/CD** | 🟢 就绪 | 100% | GitHub Actions全流程 |
| **统一接口** | 🟢 完成 | 100% | V3.0 Protocol + 数据类型 |
| **策略统一** | 🟢 完成 | 95% | BaseStrategy + Context + 适配器 |
| **日志系统** | 🟢 新增 | 100% | structlog 结构化日志 |
| **TradingGateway** | 🟢 新增 | 90% | 统一交易接口 + Paper/Live |
| **OrderManager** | 🟢 新增 | 90% | 订单管理系统 |
| **RiskManagerV2** | 🟢 新增 | 90% | 多层风控系统 |
| **RealtimeData** | 🟢 新增 | 85% | 实时数据流 + 信号生成 |
| **LiveGateway** | 🟡 桩代码 | 50% | CTP/IB/Futu 接口定义 |

### 技术债务 (已更新 2025-12-10)
- ✅ ~~PaperGateway V2/V3 混合代码~~ (已清理)
- ✅ ~~strategy/ 重复目录~~ (已删除 2025-12-09)
- ✅ ~~template 策略文件~~ (已删除 2025-12-09)
- ✅ ~~print 语句需要替换为 logger~~ (已完成 2025-12-10)
- ✅ ~~硬编码配置值需要参数化~~ (已完成 2025-12-10)
- 🟡 GUI界面需要重构（考虑使用更现代的框架）
- 🟡 测试覆盖率需要提升到90%+
- 🟡 文档需要添加英文版本
- 🟡 ML策略需要更多实盘验证

---

## 🏗️ 架构升级计划 (V3.1.0 重点)

### 一、当前架构分析

#### 1.1 目录结构问题
```
已清理后的结构 (2025-12-10):
src/
├── strategies/         # ✅ 主要策略目录 (已清理)
│   ├── base.py         # ✅ Backtrader 策略基类
│   └── *_backtrader_strategy.py  # ✅ 所有策略实现
└── core/
    ├── strategy_base.py # ✅ 统一策略基类 (BaseStrategy)
    └── interfaces.py    # ✅ Protocol 定义

已删除:
├── src/strategy/       # ❌ 已删除 (冗余目录)
├── ema_template.py     # ❌ 已删除 (使用废弃template)
└── macd_template.py    # ❌ 已删除 (使用废弃template)
```

#### 1.2 策略基类层次问题
```
已清理后 (2025-12-10):
src/core/strategy_base.py (BaseStrategy) - 唯一的统一基类
    ├── Backtrader 环境 → BacktraderStrategyAdapter
    └── EventEngine 环境 → EventEngineContext

辅助基类:
└── src/strategies/base.py  # Backtrader 专用基类 (向后兼容)
```

### 二、升级实施计划

#### Phase 3.5: 代码清理与架构统一 (1周)

**Step 1: 删除废弃模块** ✅ 已完成 (2025-12-09)
```
删除列表:
✓ src/strategy/__init__.py
✓ src/strategy/template.py
✓ src/strategies/ema_template.py  
✓ src/strategies/macd_template.py

更新依赖:
✓ src/core/paper_runner_v3.py → 使用 core/strategy_base.py
✓ tests/test_strategy.py → 使用 core/strategy_base.py
```

**Step 2: 日志系统完善** ✅ 已完成 (2025-12-10)
```
替换 print 为 logger:
✓ src/backtest/engine.py (10+ 处)
✓ src/pipeline/handlers.py (10+ 处)
✓ src/core/config.py (1处)

新增日志模块:
✓ src/core/logger.py (structlog 结构化日志)
```

**Step 3: 策略命名规范化** ✅ 已完成 (2025-12-10)
```
实现方案: 策略别名映射系统
✓ 添加 STRATEGY_ALIASES 映射表
✓ 添加 STRATEGY_CANONICAL_NAMES 标准化名称
✓ 实现 resolve_strategy_name() 别名解析
✓ 实现 get_canonical_name() 标准化命名
✓ 更新 get_backtrader_strategy() 支持别名

命名规范:
- 基础策略: indicator_name (小写, 下划线分隔)
- 增强版本: indicator_enhanced (统一 _enhanced 后缀)
- 优化版本: indicator_optimized (统一 _optimized 后缀)
- 组合策略: indicator1_indicator2 (按重要性排序)
```

**Step 4: 配置参数化** ✅ 已完成 (2025-12-10)
```
新增集中配置模块 src/core/defaults.py:
✓ BACKTEST_DEFAULTS - 回测默认参数
✓ DATA_DEFAULTS - 数据源默认配置
✓ RISK_DEFAULTS - 风控默认参数
✓ EXECUTION_DEFAULTS - 执行默认参数
✓ STRATEGY_DEFAULTS - 策略默认参数
✓ STRATEGY_PARAM_GRIDS - 策略参数优化网格
✓ LOGGING_DEFAULTS - 日志默认配置
```

### 三、商业级架构目标

#### 3.1 分层架构设计
```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  CLI/GUI    │  │  REST API   │  │  WebSocket  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│                    Application Layer                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ StrategyMgr │  │  RiskMgr    │  │  OrderMgr   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│                     Domain Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ BaseStrategy│  │  Position   │  │   Order     │     │
│  │   Context   │  │  Portfolio  │  │   Trade     │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│                  Infrastructure Layer                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ DataSource  │  │  Gateway    │  │  Database   │     │
│  │   Portal    │  │ (CTP/IB)    │  │  (SQLite)   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

#### 3.2 核心接口标准化
```python
# 目标: 所有模块通过接口通信
from src.core.interfaces import (
    IDataProvider,      # 数据提供者接口
    IStrategy,          # 策略接口
    IGateway,           # 交易网关接口
    IRiskManager,       # 风控接口
    IOrderManager,      # 订单管理接口
)
```

#### 3.3 事件驱动架构
```
事件类型:
├── MarketEvent     # 行情事件 (Bar/Tick)
├── SignalEvent     # 信号事件 (买入/卖出)
├── OrderEvent      # 订单事件 (创建/取消/修改)
├── FillEvent       # 成交事件
├── PositionEvent   # 持仓变更事件
├── RiskEvent       # 风控事件 (预警/强平)
└── HeartbeatEvent  # 心跳事件 (系统健康)
```

### 四、下一阶段重点任务

#### 优先级 P0 (本周) ✅ 已完成
| 任务 | 状态 | 负责 | 完成日期 |
|------|------|------|----------|
| 删除 src/strategy/ 目录 | ✅ | - | 2025-12-09 |
| 删除 template 策略文件 | ✅ | - | 2025-12-09 |
| 更新依赖导入 | ✅ | - | 2025-12-09 |
| 运行测试验证 | ✅ | - | 2025-12-10 (110 passed) |

#### 优先级 P1 (下周) ✅ 已完成
| 任务 | 状态 | 负责 | 完成日期 |
|------|------|------|----------|
| 替换所有 print 为 logger | ✅ | - | 2025-12-10 |
| 配置参数化 | ✅ | - | 2025-12-10 |
| 策略命名规范化 | ✅ | - | 2025-12-10 |

#### 优先级 P2 (月底) ✅ 已完成
| 任务 | 状态 | 负责 | 完成日期 |
|------|------|------|----------|
| 完善 TradingGateway | ✅ | - | 2025-12-10 |
| 多层次风控系统 | ✅ | - | 2025-12-10 |
| 订单管理系统 | ✅ | - | 2025-12-10 |
| 实时数据流 | ✅ | - | 2025-12-10 |

---

## 🗺️ 开发路线图

### Phase 3: 实盘交易集成 (进行中 🟡)
**目标**: 统一回测与实盘架构，准备实盘交易

#### 3.1 策略统一层 ✅ 完成
- [x] 定义 `BaseStrategy` 抽象基类
- [x] 实现 `BacktraderStrategyAdapter` 适配器
- [x] 创建 `StrategyContext` 统一接口
- [x] 提供示例策略 `ExampleDualMAStrategy`
- [x] 实现 `EventEngineContext` 适配器

#### 3.2 网关标准化 ✅ 完成
- [x] 创建 `src/core/interfaces.py` 统一接口定义
- [x] 清理 `PaperGateway` V2 遗留代码
- [x] 新增 `PaperGatewayV3` 纯 MatchingEngine 版本
- [x] 实现 `LiveGateway` 接口桩代码
- [x] 添加 `CTPGateway` / `IBGateway` / `XtQuantGateway` 桩实现

#### 3.3 系统健壮性 ✅ 完成
- [x] 引入 `structlog` 日志配置 (`src/core/logger.py`)
- [x] 提供 `get_logger()` 和 `configure_logging()` API
- [ ] 替换所有 `print` 为 logger (逐步进行)
- [ ] 增加 `Heartbeat` (心跳) 事件
- [ ] 实现进程监控和自动重启

#### 3.4 交易接口层 ✅ 完成 (2025-12-10)
- [x] 设计统一的交易接口 (`TradingGateway`)
- [x] 支持模拟交易（虚拟盘） - `PaperTradingAdapter`
- [x] 支持实盘交易接口 - `LiveTradingAdapter` (桩代码)
- [x] 订单管理系统 (`OrderManager`) - 完整生命周期管理

**新增模块**:
- `src/core/trading_gateway.py` - 统一交易网关
- `src/core/order_manager.py` - 订单管理系统

**支持的经纪商** (接口定义完成):
- [x] 东方财富API (桩代码)
- [x] 富途API (FutuOpenD) (桩代码)
- [ ] 雪球API
- [x] Interactive Brokers (IBKR) (桩代码)

#### 3.2 风险管理系统 ✅ 完成 (2025-12-10)
- [x] 仓位管理 (Position Sizing) - 多级仓位限制
- [x] 风险限额 (Risk Limits) - 账户/策略/订单级
- [x] 实时风控监控 - `RiskManagerV2.check_order()`
- [x] 自动止损/止盈 - `PositionStop` 自动触发

**新增模块**:
- `src/core/risk_manager_v2.py` - 增强型风险管理系统

**风险检查项**:
- 单笔订单金额限制 (max_order_value)
- 单笔订单占比限制 (max_order_pct)
- 单持仓占比限制 (max_position_pct)
- 最大回撤限制 (max_drawdown)
- 日亏损限制 (max_daily_loss)
- 账户级/策略级风控

#### 3.3 实时数据流 ✅ 完成 (2025-12-10)
- [x] WebSocket实时行情 - `WebSocketDataProvider`
- [x] 分钟级K线数据 - `BarBuilder` 分钟K线合成
- [x] Tick级数据支持 - `RealtimeQuote` / `on_tick()`
- [x] 实时信号生成 - `SignalGenerator` / `SignalRule`

**新增模块**:
- `src/core/realtime_data.py` - 实时数据流管理

**信号类型**:
- MA交叉 (`create_ma_cross_rule`)
- 价格突破 (`create_price_breakout_rule`)
- 自定义信号规则

---

### Phase 4: Web平台 (规划中)
**目标**: 构建基于Web的量化平台

#### 4.1 Web后端 🔴 未开始
- [ ] FastAPI/Flask REST API
- [ ] 用户认证和权限管理
- [ ] 策略市场 (Strategy Marketplace)
- [ ] 云端回测服务

#### 4.2 Web前端 🔴 未开始
- [ ] React/Vue前端界面
- [ ] 可视化拖拽策略编辑器
- [ ] 实时监控仪表板
- [ ] 移动端支持

#### 4.3 云部署 🔴 未开始
- [ ] Docker容器化
- [ ] Kubernetes编排
- [ ] 微服务架构
- [ ] 分布式回测集群

---

### Phase 5: 高级功能 (未来)
**目标**: 企业级高级功能

#### 5.1 机器学习增强 🟡 进行中
- [x] 基础ML策略 (V2.8.5)
- [ ] 深度学习模型 (LSTM, Transformer)
- [ ] 强化学习 (RL)
- [ ] 自动化特征选择
- [ ] 模型集成 (Ensemble)

#### 5.2 大数据支持 🔴 未开始
- [ ] 分布式数据存储 (ClickHouse)
- [ ] 流式处理 (Kafka/Flink)
- [ ] 大规模并行回测
- [ ] 云端存储集成 (OSS/S3)

#### 5.3 社区功能 🔴 未开始
- [ ] 策略分享平台
- [ ] 社区论坛
- [ ] 策略评级系统
- [ ] 知识库和教程

---

## ✅ 已完成功能

### 核心功能
- [x] 统一回测框架 (V2.0)
- [x] 多数据源支持 (V2.1)
- [x] 15+ 交易策略 (V2.4)
- [x] 参数优化 (网格搜索) (V2.3)
- [x] Pareto前沿分析 (V2.5)
- [x] 自动化流程 (auto_pipeline) (V2.5)
- [x] GUI图形界面 (V2.8.1)
- [x] 机器学习策略 (V2.8.5)
- [x] 数据库优化 (Per-Symbol表) (V2.10.1.1)
- [x] Markdown报告系统 (V2.10.2.0)
- [x] CI/CD集成 (V2.10.2.0)

### 数据源
- [x] AKShare (中国A股，免费)
- [x] YFinance (全球市场，免费)
- [x] TuShare (专业数据，需Token)
- [x] SQLite3数据库缓存
- [x] CSV导入/导出

### 策略库
- [x] 趋势跟踪: SMA/EMA Cross, MACD, ADX, Donchian
- [x] 均值回归: Bollinger, RSI, Z-Score, Keltner
- [x] 多指标: Triple MA
- [x] 组合策略: Risk Parity
- [x] 机器学习: ML Walk-Forward

### 可视化
- [x] K线图表 (Candlestick/Line)
- [x] 7种技术指标叠加
- [x] 买卖信号标注
- [x] 中文配色方案
- [x] PNG/Pickle双格式导出
- [x] Markdown报告生成
- [x] JSON数据导出

### 工程化
- [x] 模块化架构 (src/)
- [x] 单元测试 (tests/)
- [x] 集成测试
- [x] 文档完善 (docs/)
- [x] 示例代码 (examples/)
- [x] GitHub CI/CD
- [x] Pre-commit钩子
- [x] 代码质量检查

---

## 🚧 进行中任务

### 高优先级
- [ ] 提升测试覆盖率到90%+
- [ ] 添加更多ML策略示例
- [ ] 优化GUI界面响应速度
- [ ] 完善英文文档

### 中优先级
- [ ] 添加更多国际市场数据源
- [ ] 策略回测结果对比功能
- [ ] 策略组合优化工具
- [ ] Web API接口设计

### 低优先级
- [ ] 移动端支持
- [ ] 多语言支持
- [ ] 主题切换功能

---

## 🔮 未来计划

### 2025 Q2
- [ ] Phase 3.1: 模拟交易接口
- [ ] 测试覆盖率 >90%
- [ ] 性能优化（大规模回测）

### 2025 Q3
- [ ] Phase 3.2: 风险管理系统
- [ ] 实盘交易Demo
- [ ] Web API Beta版

### 2025 Q4
- [ ] Phase 4.1: Web平台后端
- [ ] Docker部署
- [ ] 策略市场Alpha版

### 2026
- [ ] Phase 4.2: Web前端
- [ ] Phase 5: 高级功能
- [ ] 社区平台

---

## 📊 开发统计

### 代码量
- **总代码行数**: ~15,000 lines
- **核心模块**: ~8,000 lines
- **测试代码**: ~2,000 lines
- **文档**: ~5,000 lines

### 提交记录
- **总提交数**: 150+ commits
- **贡献者**: 2
- **开发周期**: 12个月

### 性能指标
- **单次回测**: <5秒 (1年日线数据)
- **网格搜索**: 10-30秒 (100组参数)
- **自动化流程**: 1-5分钟 (5股票×5策略)

---

## 🤝 贡献指南

欢迎贡献代码、报告Bug、提出建议！

### 如何贡献
1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 开发规范
- 遵循 PEP 8 代码风格
- 添加单元测试（覆盖率>80%）
- 更新相关文档
- 通过CI/CD检查

### 联系方式
- **Issues**: https://github.com/magic-alt/stock/issues
- **Discussions**: https://github.com/magic-alt/stock/discussions
- **Email**: your-email@example.com

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

### 主要依赖
- [Backtrader](https://www.backtrader.com/) - 回测框架
- [AKShare](https://github.com/akfamily/akshare) - 中国金融数据
- [yfinance](https://github.com/ranaroussi/yfinance) - 全球市场数据
- [pandas](https://pandas.pydata.org/) - 数据分析
- [matplotlib](https://matplotlib.org/) - 数据可视化

### 参考资料
- [Quantopian Lectures](https://www.quantopian.com/lectures)
- [QuantConnect](https://www.quantconnect.com/)
- [Zipline](https://github.com/quantopian/zipline)

---

**最后更新**: 2025-10-26  
**维护者**: magic-alt  
**项目状态**: 🟢 Active Development
