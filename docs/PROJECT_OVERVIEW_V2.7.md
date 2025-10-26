# A股量化回测系统 V2.7.0 - 项目总览

**版本**: V2.7.0  
**更新日期**: 2025-10-24  
**状态**: ✅ 生产就绪 (Production Ready)  
**架构**: 模块化 + 事件驱动 + 插件化

---

## 🎯 项目定位

这是一个**企业级、事件驱动、高度模块化**的量化交易回测平台，基于 Backtrader + vn.py 设计理念构建，支持：

- ✅ **多数据源**: AKShare (免费) / YFinance (全球) / TuShare (专业)
- ✅ **插件化交易规则**: 可扩展的费率/仓位管理
- ✅ **框架独立策略**: 模板模式解耦策略逻辑
- ✅ **事件驱动架构**: 松耦合的组件通信
- ✅ **仿真交易**: 轻量级纸上交易引擎
- ✅ **11+ 策略**: 趋势跟踪、均值回归、动量策略、风险平价等
- ✅ **自动化流程**: 多股票 × 多策略 × 参数优化 × Pareto分析
- ✅ **高性能**: 多进程并行、智能缓存、批量处理
- ✅ **可视化**: 7种技术指标图表、中文配色、交易信号标注

---

## 🚀 V2.7.0 新特性 (最新)

### 四大模块化增强

#### 1️⃣ 交易规则插件系统 (`src/bt_plugins/`)

**问题**: 硬编码 107 行手续费/仓位管理类，难以扩展

**解决**: 插件化架构，装饰器注册

**核心文件** (3 files, 344 lines):
- `base.py` - 插件协议 + 注册表
- `fees_cn.py` - A股实现 (免五/不免五)
- `__init__.py` - 模块导出

**示例**:
```python
from src.bt_plugins.base import load_fee, load_sizer

# 自动加载默认插件（免五模式）
engine = BacktestEngine()

# 或自定义参数
fee = load_fee("cn_stock", commission_rate=0.0002, min_commission=5.0)
sizer = load_sizer("cn_lot100", lot_size=100)
```

**影响**:
- ✅ 引擎代码减少 82 行
- ✅ 可扩展：无需修改核心即可添加新插件
- ✅ 向后兼容：默认行为不变

---

#### 2️⃣ 策略模板抽象 (`src/strategy/`)

**问题**: 策略与 Backtrader 强耦合，难以测试和移植

**解决**: 协议化模板接口 + 适配器模式

**核心文件** (2 files, 440 lines):
- `template.py` - `StrategyTemplate` 协议 + `BacktraderAdapter`
- 示例: `src/strategies/ema_template.py` (180 lines)

**模板生命周期**:
```python
class MyStrategy(StrategyTemplate):
    params = {"period": 20}
    
    def on_init(self):    # 初始化
        self.ctx = {}
    
    def on_start(self):   # 启动
        pass
    
    def on_bar(self, symbol: str, bar: pd.Series):  # 处理每根K线
        # 纯Python逻辑，无Backtrader依赖
        if bar["close"] > threshold:
            self.emit_signal("buy")
    
    def on_stop(self):    # 停止
        pass
```

**双引擎支持**:
- **Backtrader**: 通过 `BacktraderAdapter` 桥接
- **PaperRunner**: 纯Python轻量执行

**影响**:
- ✅ 框架无关：策略可移植到任意引擎
- ✅ 易于测试：纯Python函数，无需mock
- ✅ 面向未来：为实盘交易做准备

---

#### 3️⃣ Pipeline 事件化 (`src/pipeline/`)

**问题**: 结果持久化和可视化硬编码在引擎中

**解决**: 事件驱动解耦，订阅者模式

**核心文件** (2 files, 180 lines):
- `handlers.py` - `PipelineEventCollector` + 工厂函数
- `__init__.py` - 模块导出

**引擎修改**: 在 `grid_search()` 添加 3 个事件注入点
1. `PIPELINE_STAGE("grid.start")` - 参数循环前
2. `METRICS_CALCULATED` - 每次回测后
3. `PIPELINE_STAGE("grid.done")` - 完成后

**示例**:
```python
from src.pipeline.handlers import make_pipeline_handlers

# 注册事件处理器
handlers = make_pipeline_handlers("./reports")
for etype, handler in handlers:
    engine.events.register(etype, handler)

# 运行网格搜索（自动保存CSV）
engine.grid_search(...)
# 输出: ./reports/ema_results.csv
```

**影响**:
- ✅ 解耦持久化逻辑
- ✅ 可定制可视化
- ✅ 易于监控和调试

---

#### 4️⃣ 仿真交易 (`src/core/`)

**问题**: 模板策略必须使用重量级 Backtrader

**解决**: 事件驱动纸上交易网关 + 纯Python执行器

**核心文件** (2 files, 590 lines):
- `paper_gateway.py` - `PaperGateway` 实现 `TradeGateway` 协议
- `paper_runner.py` - `run_paper()` + `run_paper_with_nav()`

**撮合模型**:
```
Bar N:   策略提交订单  →  ORDER_SENT 事件
                       ↓
                   _pending 队列
                       ↓
Bar N+1: 以开盘价成交  →  ORDER_FILLED 事件
```

**示例**:
```python
from src.core.paper_runner import run_paper
from src.strategies.ema_template import EMATemplate

# 加载数据
data_map = engine._load_data(["600519.SH"], "2024-01-01", "2024-12-31")

# 创建策略
strategy = EMATemplate()
strategy.params = {"period": 20}

# 运行仿真
events = EventEngine()
events.start()
result = run_paper(strategy, data_map, events, slippage=0.001)

print(f"最终权益: {result['equity']:.2f}")
events.stop()
```

**优势对比**:

| 特性 | Backtrader | PaperRunner |
|------|-----------|-------------|
| 设置复杂度 | 高 | 低（3行） |
| 执行速度 | 中等 | 快（纯Python） |
| 事件监控 | 有限 | 完整发布 |
| 调试难度 | 难 | 易 |
| 灵活性 | 中等 | 高（可注入网关） |

---

## 📐 系统架构 V2.7.0

```
┌─────────────────────────────────────────────────────────────────┐
│                   统一入口 (CLI Interface)                        │
│              unified_backtest_framework.py (214 lines)           │
│     [run] [grid] [auto] [list] - 100% 向后兼容                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                   核心业务层 (src/backtest/)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  engine.py   │  │ analysis.py  │  │ plotting.py  │         │
│  │ (回测引擎)   │  │ (Pareto分析) │  │ (图表可视化) │         │
│  │              │  │              │  │              │         │
│  │ • 事件驱动 🆕│  │ • 多目标优化 │  │ • 7种指标    │         │
│  │ • 网格搜索   │  │ • 热力图生成 │  │ • 中文配色   │         │
│  │ • 自动流水线 │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                   V2.7.0 新增模块 🆕                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐     │
│  │  bt_plugins/   │  │  strategy/     │  │  pipeline/   │     │
│  │  (插件系统)    │  │  (策略模板)    │  │  (事件处理)  │     │
│  │                │  │                │  │              │     │
│  │ • 费率插件     │  │ • 模板协议     │  │ • 事件收集器 │     │
│  │ • 仓位插件     │  │ • BT适配器     │  │ • CSV持久化  │     │
│  │ • 装饰器注册   │  │ • 生命周期管理 │  │ • 进度跟踪   │     │
│  └────────────────┘  └────────────────┘  └──────────────┘     │
│                                                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              core/ (核心组件) 🆕                     │       │
│  │  ┌───────────────┐  ┌───────────────────────────┐  │       │
│  │  │ events.py     │  │ gateway.py                │  │       │
│  │  │ (事件引擎)    │  │ (网关协议)                │  │       │
│  │  │               │  │                           │  │       │
│  │  │ • 线程安全    │  │ • HistoryGateway 协议     │  │       │
│  │  │ • 非阻塞队列  │  │ • TradeGateway 协议       │  │       │
│  │  │ • 异常隔离    │  │ • BacktestGateway 实现    │  │       │
│  │  └───────────────┘  │ • PaperGateway 实现 🆕    │  │       │
│  │                     └───────────────────────────┘  │       │
│  │  ┌───────────────────────────────────────────┐     │       │
│  │  │ paper_runner.py (仿真执行器) 🆕           │     │       │
│  │  │ • run_paper() - 基础执行                   │     │       │
│  │  │ • run_paper_with_nav() - NAV追踪          │     │       │
│  │  │ • SimpleBuyHoldTemplate - 示例策略        │     │       │
│  │  └───────────────────────────────────────────┘     │       │
│  └─────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                  数据与策略层 (strategies/)                       │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │  data_sources/       │  │  strategies/         │           │
│  │  providers.py        │  │  (11+ Backtrader +   │           │
│  │  (数据提供者)        │  │   Template策略) 🆕   │           │
│  │                      │  │                      │           │
│  │ • AKShare (默认)     │  │ Backtrader策略:      │           │
│  │ • YFinance           │  │ • EMA Cross          │           │
│  │ • TuShare            │  │ • MACD Signal        │           │
│  │ • 缓存机制           │  │ • Bollinger Bands    │           │
│  │ • OHLCV标准化        │  │ • RSI                │           │
│  └──────────────────────┘  │ • ADX Trend          │           │
│                            │ • Triple MA          │           │
│                            │ • ZScore             │           │
│                            │ • Donchian           │           │
│                            │ • Keltner            │           │
│                            │ • Risk Parity        │           │
│                            │                      │           │
│                            │ Template策略: 🆕     │           │
│                            │ • ema_template.py    │           │
│                            │ (可独立或适配BT)      │           │
│                            └──────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### V2.7.0 设计哲学

**灵感来源**: [vn.py](https://github.com/vnpy/vnpy) 事件驱动 + 模块化架构

| 设计模式 | 应用位置 | 优势 |
|---------|---------|------|
| **插件模式** | `bt_plugins/` | 热插拔交易规则 |
| **模板模式** | `strategy/template.py` | 框架无关策略开发 |
| **适配器模式** | `BacktraderAdapter` | 桥接模板到Backtrader |
| **观察者模式** | `pipeline/handlers.py` | 事件驱动解耦 |
| **网关模式** | `gateway.py` | 统一执行接口 |
| **工厂模式** | `load_fee()`, `load_sizer()` | 动态创建插件 |
| **协议模式** | `StrategyTemplate` Protocol | 类型安全的接口 |

---

## 📊 核心特性对比

### V2.6.0 → V2.7.0 演进

| 特性 | V2.6.0 | V2.7.0 | 改进 |
|------|--------|--------|------|
| **交易规则** | 硬编码107行 | 插件化 | ✅ 可扩展 |
| **策略开发** | 耦合Backtrader | 模板协议 | ✅ 框架独立 |
| **结果处理** | 嵌入引擎 | 事件订阅 | ✅ 解耦 |
| **仿真交易** | 仅Backtrader | PaperRunner | ✅ 轻量化 |
| **代码复杂度** | 907行 (engine.py) | 875行 (-32) | ✅ 更简洁 |
| **新增文件** | 3 | 10 (+7) | ✅ 模块化 |
| **向后兼容** | N/A | 100% | ✅ 无破坏 |

---

## 🚀 快速开始

### 1. 基础回测（使用默认插件）

```bash
python unified_backtest_framework.py run \
  --strategy ema \
  --symbols 600519.SH \
  --start 2024-01-01 \
  --end 2024-12-31
```

### 2. 网格搜索（自动持久化）

```python
from src.backtest.engine import BacktestEngine
from src.pipeline.handlers import make_pipeline_handlers

engine = BacktestEngine()

# 注册事件处理器（自动保存CSV）
handlers = make_pipeline_handlers("./reports")
for etype, handler in handlers:
    engine.events.register(etype, handler)

engine.events.start()

# 运行网格搜索
result_df = engine.grid_search(
    strategy="ema",
    grid={"period": [10, 20, 30]},
    symbols=["600519.SH"],
    start="2024-01-01",
    end="2024-12-31",
)

engine.events.stop()
```

### 3. 策略模板 + 仿真交易

```python
from src.strategies.ema_template import EMATemplate
from src.core.paper_runner import run_paper
from src.core.events import EventEngine

# 加载数据
engine = BacktestEngine()
data_map = engine._load_data(["600519.SH"], "2024-01-01", "2024-12-31")

# 创建策略
strategy = EMATemplate()
strategy.params = {"period": 20}

# 运行仿真
events = EventEngine()
events.start()
result = run_paper(strategy, data_map, events, slippage=0.001)
events.stop()

print(f"最终权益: {result['equity']:.2f}")
```

### 4. 自定义插件

```python
from src.bt_plugins.base import register_fee, FeePlugin
import backtrader as bt

@register_fee("my_fee")
class MyFeePlugin(FeePlugin):
    def __init__(self, rate: float = 0.001):
        self.rate = rate
    
    def register(self, broker: bt.BrokerBase):
        class MyCommission(bt.CommInfoBase):
            params = (('commission', self.rate),)
            def getcommission(self, size, price):
                return abs(size) * price * self.p.commission
        broker.addcommissioninfo(MyCommission())

# 使用
from src.bt_plugins.base import load_fee
fee = load_fee("my_fee", rate=0.002)
```

---

## 📦 完整文件结构

```
stock/
├── unified_backtest_framework.py   # CLI 入口
├── CHANGELOG.md                    # V2.7.0 更新日志
├── docs/
│   ├── V2.7.0_IMPLEMENTATION_REPORT.md    # 实施报告
│   ├── V2.7.0_PATCH1_COMPLETION.md        # 补丁1详情
│   └── V2.7.0_QUICK_REFERENCE.md          # 快速参考
├── src/
│   ├── __init__.py
│   ├── backtest/
│   │   ├── engine.py               # 回测引擎 (事件驱动)
│   │   ├── analysis.py             # Pareto分析
│   │   ├── plotting.py             # 可视化
│   │   └── strategy_modules.py     # 策略注册表
│   ├── bt_plugins/                 # 🆕 插件系统
│   │   ├── __init__.py
│   │   ├── base.py                 # 插件协议
│   │   └── fees_cn.py              # A股实现
│   ├── core/
│   │   ├── __init__.py
│   │   ├── events.py               # 事件引擎
│   │   ├── gateway.py              # 网关协议
│   │   ├── paper_gateway.py        # 🆕 仿真网关
│   │   └── paper_runner.py         # 🆕 仿真执行器
│   ├── data_sources/
│   │   └── providers.py            # 数据提供者
│   ├── pipeline/                   # 🆕 事件处理
│   │   ├── __init__.py
│   │   └── handlers.py             # 事件收集器
│   ├── strategies/
│   │   ├── ema_backtrader_strategy.py
│   │   ├── ema_template.py         # 🆕 模板策略
│   │   ├── macd_backtrader_strategy.py
│   │   └── ... (11+ 策略文件)
│   └── strategy/                   # 🆕 模板系统
│       ├── __init__.py
│       └── template.py             # 模板协议 + 适配器
├── cache/                          # 数据缓存
└── reports/                        # 结果报告
```

---

## 🧪 测试验证

### V2.7.0 综合测试

```
================================================================================
V2.7.0 Complete System Validation Summary
================================================================================
[1] Single Strategy Run ......................... ✅ TESTED
[2] Grid Search ................................. ✅ TESTED
[3] Plugin System ............................... ✅ TESTED
[4] Strategy Template + Adapter ................. ✅ TESTED
[5] PaperRunner ................................. ✅ TESTED
[6] Pipeline Event Handlers ..................... ✅ TESTED
[7] Backward Compatibility ...................... ✅ TESTED

V2.7.0 system fully validated and operational!
```

### 测试覆盖率

| 模块 | 测试类型 | 状态 |
|------|---------|------|
| Plugin System | 单元测试 | ✅ 通过 |
| Strategy Template | 集成测试 | ✅ 通过 |
| Pipeline Events | 功能测试 | ✅ 通过 |
| PaperRunner | 端到端测试 | ✅ 通过 |
| 向后兼容 | 回归测试 | ✅ 通过 |

---

## 📚 文档索引

| 文档 | 描述 | 路径 |
|------|------|------|
| **快速参考** | 使用示例和API | `docs/V2.7.0_QUICK_REFERENCE.md` |
| **实施报告** | 架构设计和实现 | `docs/V2.7.0_IMPLEMENTATION_REPORT.md` |
| **更新日志** | 版本变更记录 | `CHANGELOG.md` |
| **CLI使用** | 命令行指南 | `unified_backtest_framework_usage.md` |
| **项目总览** | 本文档 | `PROJECT_OVERVIEW_V2.7.md` |

---

## 🎯 未来路线图

### V2.8.0 计划

- [ ] **实盘网关**: 实现 `LiveGateway` + 券商API对接
- [ ] **风控模块**: 仓位限制、止损、组合约束
- [ ] **高级模板策略**: 均值回归、套利、ML策略
- [ ] **实时行情**: WebSocket支持
- [ ] **监控面板**: Web UI实时监控

### 长期愿景

- **多资产支持**: 期货、期权、数字货币
- **分布式回测**: 集群并行计算
- **策略市场**: 社区共享策略
- **AI优化**: 自动参数优化 + 强化学习

---

## 🏆 技术亮点

### V2.7.0 核心优势

1. **100% 向后兼容**: 零破坏性变更
2. **模块化**: 10个新文件，2000行代码
3. **事件驱动**: 松耦合组件通信
4. **插件化**: 热插拔交易规则
5. **框架独立**: 策略可移植
6. **仿真交易**: 轻量级执行引擎
7. **vn.py 设计**: 专业交易系统架构

### 代码质量

- ✅ **类型提示**: 完整类型注解
- ✅ **协议导向**: Protocol-based设计
- ✅ **文档齐全**: Docstring + 使用指南
- ✅ **测试覆盖**: 7大测试场景
- ✅ **性能优化**: 进程级并行 + 缓存

---

## 📞 支持与贡献

- **问题反馈**: GitHub Issues
- **功能请求**: GitHub Discussions
- **代码贡献**: Pull Requests
- **文档改进**: 欢迎PR

---

**项目地址**: [GitHub Repository]  
**许可证**: MIT  
**作者**: [Your Name]  
**更新**: 2025-10-24  
**版本**: V2.7.0 🚀
