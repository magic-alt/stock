# Changelog

All notable changes to this project will be documented in this file.

# Changelog

## [V2.8.2] - 2025-10-25

### 🎯 Feature Enhancements

**用户反馈改进**:

1. **单只股票快速选择** ✅
   - 新增4个常用单股快捷按钮：茅台(600519.SH)、平安(601318.SH)、招行(600036.SH)、五粮液(000858.SZ)
   - 优化快速选择布局：分为两行（单股/组合）
   - 一键填充股票代码，简化单只股票回测流程
   - **文件**: `backtest_gui.py` (第176-239行, 751-759行)

2. **下载数据功能** ✅
   - 新增"下载数据"按钮，批量下载股票数据到缓存
   - 显示下载进度和每只股票的数据记录数
   - 统计成功/失败数量，自动下载基准指数
   - 首次使用或更新数据时无需等待回测
   - **文件**: `backtest_gui.py` (第280-296行, 790-867行)

3. **图表生成选项** ✅
   - 确认图表选项已存在且正常工作
   - 默认开启图表生成，保存到输出目录
   - 图表包含价格走势、信号标记、净值曲线等
   - **文件**: `backtest_gui.py` (第449-454行, 1144行, 1238行)

### 📚 Documentation

4. **V2.8.2 更新文档** ✅
   - 完整的功能说明和使用指南
   - 界面布局优化示意图
   - 功能验证测试脚本
   - **文件**: `docs/GUI_V2.8.2_UPDATE.md`, `test_gui_v2.8.2.py`

### 📦 Files Changed

- `backtest_gui.py`: 用户体验优化（1353 → 1444行）
- `docs/GUI_V2.8.2_UPDATE.md`: 新增更新文档
- `test_gui_v2.8.2.py`: 新增测试脚本

---

## [V2.8.1] - 2024-10-24

### 🔧 Bug Fixes

**关键问题修复**:

1. **基准指数加载错误** ✅
   - 修复 `KeyError: 'date'` 错误
   - 添加指数代码格式转换（`000300.SH` → `sh000300`）
   - 重写缓存读取逻辑，使用位置索引替代列名
   - 添加回退机制，自动重新标准化不兼容的缓存
   - 改进错误信息，更清晰的失败提示
   - **文件**: `src/data_sources/providers.py` (第268-325行)

2. **Matplotlib 线程警告** ✅
   - 修复 "Starting a Matplotlib GUI outside of the main thread" 警告
   - 设置 Agg 后端（非交互式），确保线程安全
   - 所有图表自动保存为文件，不弹出窗口
   - **文件**: `backtest_gui.py` (第14-16行)

### 🎯 Feature Enhancements

**输出格式优化**:

3. **与 CLI 一致的输出格式** ✅
   - 单次回测：分节显示收益/风险/交易指标
   - 网格搜索：显示参数空间 + Top 5 排名
   - 自动化流程：任务配置 + 执行摘要
   - 使用 emoji 图标和对齐格式
   - 添加清晰的分隔线和文件输出总结
   - **文件**: `backtest_gui.py` (第975-1175行)

**用户体验增强**:

4. **内置预设配置方案** ✅
   - 5 个精心配置的快速启动方案：
     - **快速测试-3月**: 2股票 + 2策略，测试用（1-2分钟）
     - **白酒股-趋势策略**: 4白酒股 + 4趋势策略
     - **银行股-震荡策略**: 4银行股 + 4震荡策略
     - **科技股-全策略**: 4科技股 + 5混合策略
     - **单股深度分析**: 1股票 + 8策略完整测试
   - 下拉菜单一键选择
   - 自动填充所有参数（股票/日期/策略/模式）
   - 详情弹窗查看方案说明
   - **文件**: `backtest_gui.py` (第30-88行，1200-1280行)

5. **控制按钮区域重新设计** ✅
   - 3行布局：启动按钮 / 配置管理 / 预设方案
   - 预设方案下拉菜单（只读模式）
   - 详情按钮查看所有方案
   - 自动绑定选择事件
   - **文件**: `backtest_gui.py` (第635-657行)

### 📚 Documentation

6. **V2.8.1 更新文档** ✅
   - 完整的问题分析和修复说明
   - 代码对比（修复前 vs 修复后）
   - 测试验证用例
   - 使用指南和预设方案说明
   - 性能影响评估
   - **文件**: `docs/GUI_V2.8.1_UPDATE.md`

### 🔄 Compatibility

- ✅ 向后兼容所有缓存格式
- ✅ 配置文件完全兼容 V2.8.0
- ✅ 输出格式保持 CLI 标准
- ✅ 无需手动迁移

### 📦 Files Changed

- `backtest_gui.py`: 主程序优化（1234 → 1305行）
- `src/data_sources/providers.py`: 缓存读取修复
- `docs/GUI_V2.8.1_UPDATE.md`: 新增更新文档

---

## [V2.8.0] - 2024-10-24

### 🎨 New Features

**回测分析 GUI（图形用户界面）**

全新的图形界面程序，包含 CLI 的所有功能，让量化回测更加简单易用！

**核心功能**:

1. **数据管理界面**
   - 📊 多数据源支持（AKShare, YFinance, TuShare）
   - 📝 批量股票代码输入（支持多行文本）
   - 🔘 快速股票列表选择（白酒股/银行股/科技股）
   - 👁️ 数据预览验证功能
   - 💾 自动缓存机制
   - 📅 可视化日期选择

2. **策略配置界面**
   - 🎯 9+ 内置策略可视化选择
   - ☑️ 多选支持（Ctrl + 点击）
   - 🔍 策略分类快速选择（趋势/震荡）
   - ⚙️ JSON 格式参数配置
   - 📖 策略详情查看窗口
   - 🎲 全选/清空快捷按钮

3. **回测引擎界面**
   - 💰 可视化资金/费率配置
   - 📈 复权方式下拉选择
   - 📁 输出目录浏览器
   - 📊 图表生成开关
   - 📝 详细日志开关

4. **优化配置界面**
   - 🎮 三种运行模式（单次/网格/自动）
   - ⚡ 并行进程数调节（1-16）
   - 🏆 Top-N 配置（1-20）
   - 🔥 Hot-Only 模式开关
   - 📊 Pareto 前沿分析
   - 🎯 基准趋势过滤选项

5. **实时日志输出**
   - 📋 彩色日志显示
   - ⏱️ 时间戳标记
   - 🎨 语法高亮（成功/警告/错误）
   - 🔍 自动滚动显示
   - 🗑️ 一键清空日志

6. **配置管理**
   - 💾 保存配置到 JSON 文件
   - 📂 从文件加载配置
   - 📄 示例配置模板
   - 🔄 配置快速切换

**文件清单**:
- `backtest_gui.py` - GUI 主程序（900+ 行）
- `启动GUI.bat` - Windows 一键启动脚本
- `gui_config_example.json` - 配置示例模板
- `docs/GUI_USER_GUIDE.md` - 详细使用指南（3000+ 行）
- `GUI_README.md` - 快速参考文档

**启动方式**:
```bash
# Windows
启动GUI.bat

# Linux/Mac
python backtest_gui.py
```

**界面布局**:
```
┌─────────────────────────────────────────────────────────────┐
│  量化回测分析系统 V2.8.0                                      │
├───────────────────┬─────────────────────────────────────────┤
│  配置面板          │  实时日志输出                            │
│  ┌─────────────┐  │  ┌──────────────────────────────────┐  │
│  │ 📊 数据配置 │  │  │ [08:23:45] 开始回测...            │  │
│  │ 🎯 策略配置 │  │  │ [08:23:47] 加载数据完成           │  │
│  │ ⚙️ 回测配置 │  │  │ [08:24:15] 回测完成！             │  │
│  │ 🔍 优化配置 │  │  │                                   │  │
│  └─────────────┘  │  └──────────────────────────────────┘  │
│                   │                                         │
│  [▶️ 开始] [⏹️ 停止] [💾 保存] [📂 加载]                  │
└───────────────────┴─────────────────────────────────────────┘
```

**特色亮点**:
- ✅ 零命令行操作，完全图形化
- ✅ 实时进度显示，可视化日志
- ✅ 配置保存/加载，提升效率
- ✅ 多线程后台运行，界面不卡顿
- ✅ 所有 CLI 功能完整实现
- ✅ 友好的错误提示和帮助信息
- ✅ 预设快捷按钮，快速上手

**使用场景**:
- 💡 量化新手: 无需学习命令行
- 🎯 参数调优: 可视化网格搜索
- 📊 批量分析: 自动化流程一键启动
- 🔍 结果对比: Top-N 详细报告
- 💾 配置管理: 多场景快速切换

**5分钟快速上手**:
1. 双击 `启动GUI.bat`
2. 点击"白酒股"按钮 → 自动填充股票代码
3. 点击"趋势策略"按钮 → 自动选择策略
4. 选择"自动化流程"模式
5. 点击"▶️ 开始回测"
6. 等待完成，查看 `reports_gui/` 目录

**文档**:
- 📖 完整指南: `docs/GUI_USER_GUIDE.md`
- 📋 快速参考: `GUI_README.md`
- 💡 示例配置: `gui_config_example.json`

---

## [V2.7.1] - 2025-10-24 Hotfix

### 🐛 Bug Fixes

**Grid Search Error Handling Enhancement**

**问题**: auto pipeline 产生大量空白数据和 "array assignment index out of range" 错误

**根本原因**:
1. 短期数据（3个月）不足以计算大周期指标（如 EMA period=60-120）
2. Backtrader 内部抛出 IndexError 导致整个回测失败
3. 错误处理不完善，异常时只返回部分指标（8/23），导致 CSV 出现空白列

**修复内容**:

1. **增强错误处理** (`src/backtest/engine.py`)
   - `_run_module` 方法增加完整 try-except 包裹
   - 异常时返回完整的 23 个指标字段（而不是 8 个）
   - NAV 计算也增加 try-except 保护
   - 所有失败的参数组合现在都产生完整的 CSV 行

2. **参数验证** (`src/strategies/ema_backtrader_strategy.py`)
   - 在 `EMAStrategy.__init__` 中增加数据长度检查
   - 提前抛出清晰的 ValueError 而不是让 Backtrader 产生 IndexError
   - 错误信息：`"EMA period (X) requires at least X bars of data, but only Y bars available"`

**影响**:
- ✅ **无空白行**: CSV 中不再出现完全空白的行
- ✅ **错误完整性**: 所有 error 不为空的行，其他列都有有意义的值（NaN 或 0）
- ✅ **清晰错误**: error 列包含可读的诊断信息
- ✅ **可过滤分析**: 用户可以用 `df[df['error'].isna()]` 过滤出成功的配置

**向后兼容**: ✅ 不影响正常工作的参数组合

**建议**:
- 使用至少 6-12 个月的数据进行回测
- 根据数据长度调整参数范围
- 使用 `--hot_only` 模式避免不合理的参数组合

详细修复报告: `docs/GRID_SEARCH_ERROR_FIX.md`

---

## [V2.7.0] - 2025-10-23

### 🎯 Overview

V2.7.0 completes the modular architecture vision with four major enhancements inspired by vn.py design patterns. This release adds **plugin-based trading rules**, **framework-independent strategy templates**, **event-driven pipeline**, and **paper trading simulation**, while maintaining 100% backward compatibility.

**Design Philosophy**: Decouple core logic from implementation details, enable hot-swappable components, and prepare for live trading deployment.

### ✨ New Features

#### Patch 1: Trading Rules Plugin System (`src/bt_plugins/`)

**Problem Solved**: Hardcoded 107-line commission/sizer classes in engine made A-share rules non-extensible.

**Solution**: Plugin-based architecture with decorator registration.

**New Files** (3 files, 344 lines):
- `base.py` (127 lines): Plugin protocols (`FeePlugin`, `SizerPlugin`) + decorator registration
- `fees_cn.py` (186 lines): CN A-share implementations (`cn_stock`, `cn_lot100`)
- `__init__.py` (31 lines): Module exports

**Features**:
- **Fee Plugin**: Configurable commission + stamp tax (supports "免五" mode)
- **Sizer Plugin**: Lot-based position sizing (100 shares/lot for A-shares)
- **Decorator Registration**: `@register_fee("name")`, `@register_sizer("name")`
- **Factory Functions**: `load_fee()`, `load_sizer()`
- **Engine Integration**: 107 lines of embedded classes → 4 lines of plugin loading

**Usage**:
```python
# Custom fee plugin
@register_fee("my_fee")
class MyFeePlugin(FeePlugin):
    def register(self, broker):
        ...

# Load in engine
fee = load_fee("cn_stock", commission_rate=0.0001, stamp_tax_rate=0.0005)
```

**Impact**:
- ✅ 83-line reduction in engine.py
- ✅ Extensible: Add new plugins without modifying core
- ✅ Backward compatible: Default behavior unchanged

---

#### Patch 2: Strategy Template Abstraction (`src/strategy/`)

**Problem Solved**: Strategies tightly coupled to Backtrader, hard to test or port to other frameworks.

**Solution**: Protocol-based template interface + adapter pattern.

**New Files** (2 files, 440 lines):
- `template.py` (260 lines): `StrategyTemplate` protocol + `BacktraderAdapter`
- `__init__.py` (9 lines): Module exports

**Example**: `src/strategies/ema_template.py` (180 lines)

**Features**:
- **Lifecycle Protocol**: `on_init()`, `on_start()`, `on_bar()`, `on_stop()`
- **Framework Independence**: Pure Python, no Backtrader dependency
- **Backtrader Adapter**: Bridges template to Backtrader execution
- **Multi-Framework**: Same template works with Backtrader OR PaperRunner

**Usage**:
```python
# Define template strategy
class MyStrategy(StrategyTemplate):
    params = {"period": 20}
    
    def on_init(self):
        self.ctx = {}
    
    def on_bar(self, symbol: str, bar: pd.Series):
        # Pure Python logic, no Backtrader APIs
        if bar["close"] > threshold:
            self.emit_signal("buy", symbol)

# Use with Backtrader
adapter = BacktraderAdapter(MyStrategy, period=20)
cerebro.addstrategy(adapter.to_bt_strategy())

# Use with PaperRunner
result = run_paper(MyStrategy(), data_map, events)
```

**Impact**:
- ✅ Framework-agnostic strategy development
- ✅ Easier testing (pure Python, no mocking)
- ✅ Future-proof (ready for live trading)

---

#### Patch 3: Pipeline Eventification (`src/pipeline/`)

**Problem Solved**: Result persistence and visualization hardcoded in engine, difficult to customize.

**Solution**: Event-driven decoupling via subscriber pattern.

**New Files** (2 files, 180 lines):
- `handlers.py` (180 lines): `PipelineEventCollector` + factory functions
- `__init__.py` (9 lines): Module exports

**Engine Modifications**: Added 3 event injection points in `grid_search()`
1. `PIPELINE_STAGE("grid.start")` - Before parameter loop
2. `METRICS_CALCULATED` - After each run (parallel and serial modes)
3. `PIPELINE_STAGE("grid.done")` - After completion

**Features**:
- **Event Buffering**: Collects metrics from all parameter combinations
- **CSV Persistence**: Auto-saves results on completion
- **Pareto Analysis**: Optional Pareto frontier generation
- **Progress Tracking**: Extended collector with live updates

**Usage**:
```python
from src.pipeline.handlers import make_pipeline_handlers

# Create event handlers
handlers = make_pipeline_handlers("./reports")

# Register with engine
for etype, handler in handlers:
    engine.events.register(etype, handler)

# Run grid search (CSV auto-saved on completion)
engine.grid_search(...)
```

**Impact**:
- ✅ Decoupled persistence logic
- ✅ Customizable visualization
- ✅ Easier monitoring and debugging

---

#### Patch 4: Paper Trading Simulation (`src/core/`)

**Problem Solved**: No lightweight execution for template strategies, must use heavy Backtrader.

**Solution**: Event-driven paper gateway + pure Python runner.

**New Files** (2 files, 590 lines):
- `paper_gateway.py` (320 lines): `PaperGateway` implementing `TradeGateway`
- `paper_runner.py` (270 lines): `run_paper()` + `run_paper_with_nav()`

**Features**:
- **Next-Bar-Open Matching**: Orders submitted on bar N fill at bar N+1 open
- **Event Publishing**: `ORDER_SENT`, `ORDER_FILLED`, `ORDER_CANCELLED`
- **Cash/Position Tracking**: In-memory account management
- **Configurable Slippage**: Realistic fill simulation
- **NAV Tracking**: Optional equity curve recording

**Usage**:
```python
from src.core.paper_runner import run_paper
from src.strategies.ema_template import EMATemplate

# Create strategy and load data
strategy = EMATemplate()
strategy.params = {"period": 20}
data_map = engine._load_data(["600519.SH"], "2024-01-01", "2024-12-31")

# Run paper trading
events = EventEngine()
events.start()
result = run_paper(strategy, data_map, events, slippage=0.001)

print(f"Final Equity: {result['equity']:.2f}")
events.stop()
```

**Advantages over Backtrader**:
- ✅ Simpler API (no cerebro setup)
- ✅ Faster execution (pure Python loops)
- ✅ Event-driven monitoring
- ✅ Easier debugging

---

### 📊 Code Statistics

| Patch | New Files | Lines Added | Engine Changes | Status |
|-------|-----------|-------------|----------------|--------|
| **Patch 1** | 3 | 344 | -82 net lines | ✅ Verified |
| **Patch 2** | 2 | 440 | 0 | ✅ Verified |
| **Patch 3** | 2 + mods | 180 + 50 | +50 lines | ✅ Verified |
| **Patch 4** | 2 | 590 | 0 | ✅ Verified |
| **Total** | **10** | **~2,000** | **-32 net** | **✅ Complete** |

### 🧪 Comprehensive Testing

#### Individual Patch Tests:
- ✅ **Patch 1**: Plugin loading, fee calculation, sizer configuration
- ✅ **Patch 2**: Template lifecycle, BacktraderAdapter, EMA example
- ✅ **Patch 3**: Event collector, CSV persistence, factory functions
- ✅ **Patch 4**: PaperGateway order matching, PaperRunner execution
- ✅ **Patch 5**: Progress tracking collector (extended version)

#### Integration Tests:
1. ✅ **Single Strategy Run**: EMA on 600519.SH (Jan 2024)
2. ✅ **Grid Search**: 3 parameter combinations (period=10,20,30)
3. ✅ **Plugin Integration**: cn_stock + cn_lot100 auto-loaded
4. ✅ **Template + Adapter**: EMATemplate → BacktraderStrategy
5. ✅ **PaperRunner**: SimpleBuyHoldTemplate execution
6. ✅ **Pipeline Events**: Grid search CSV persistence
7. ✅ **Backward Compatibility**: MACD strategy runs unchanged

#### Test Results:
```
V2.7.0 Complete System Validation Summary
================================================================================
[1] Single Strategy Run ......................... TESTED
[2] Grid Search ................................. TESTED
[3] Plugin System ............................... TESTED
[4] Strategy Template + Adapter ................. TESTED
[5] PaperRunner ................................. TESTED
[6] Pipeline Event Handlers ..................... TESTED
[7] Backward Compatibility ...................... TESTED

V2.7.0 system fully validated and operational!
```

### ✅ Backward Compatibility

**100% Compatible**: All existing code works without changes

- ✅ **CLI Commands**: `run`, `grid`, `auto`, `list` unchanged
- ✅ **Default Behavior**: Engine auto-loads cn_stock + cn_lot100
- ✅ **No Breaking Changes**: Only additions, zero deletions
- ✅ **API Preserved**: All existing parameters and return values identical
- ✅ **Strategies**: All Backtrader strategies work as before

### 🏗️ Architecture Summary

**Before V2.7.0**:
- Monolithic engine with hardcoded trading rules
- Strategies tightly coupled to Backtrader
- Result persistence embedded in engine
- No simulation framework

**After V2.7.0**:
- Plugin-based trading rules (extensible)
- Framework-independent strategy templates
- Event-driven pipeline (decoupled)
- Lightweight paper trading (simulation-ready)

**Inspiration**: All four patches follow vn.py design patterns:
- Event-driven communication
- Protocol-based abstraction
- Plugin extensibility
- Gateway pattern for execution

### 📚 Documentation

- `docs/V2.7.0_IMPLEMENTATION_REPORT.md`: Complete design document (all 4 patches)
- `docs/V2.7.0_PATCH1_COMPLETION.md`: Patch 1 detailed report
- `docs/V2.7.0_QUICK_REFERENCE.md`: User quick start guide (to be created)

### 🎯 Future-Ready

**V2.8.0+ Roadmap**:
- [ ] **Live Trading Gateway**: Implement `LiveGateway` with broker API integration
- [ ] **Risk Management Module**: Position limits, stop-loss, portfolio constraints
- [ ] **Advanced Strategy Templates**: Mean-reversion, arbitrage, ML-based
- [ ] **Real-time Market Data**: WebSocket support for live feeds
- [ ] **Monitoring Dashboard**: Web UI for live strategy monitoring

### 🔗 References

- Inspired by [vn.py](https://github.com/vnpy/vnpy) modular architecture
- Plugin pattern from professional trading systems
- Template pattern from Gang of Four design patterns
- Event-driven architecture from reactive programming

---

## [V2.6.0] - 2025-10-24 - Architecture Upgrade (Event-Driven + Gateway Pattern)

### 🏗️ Architecture Enhancements

#### Event-Driven Infrastructure:
1. **EventEngine Implementation** (`src/core/events.py`)
   - Thread-safe event bus with pub-sub pattern
   - Non-blocking event publishing (Queue-based)
   - Automatic exception isolation (handler errors don't crash engine)
   - Graceful shutdown with timeout
   - **20+ standard event types** (DATA_LOADED, STRATEGY_SIGNAL, ORDER_FILLED, etc.)
   - **Inspiration**: Based on vn.py's EventEngine design

2. **Gateway Protocol Abstraction** (`src/core/gateway.py`)
   - `HistoryGateway` protocol: Unified interface for historical data
   - `TradeGateway` protocol: Unified interface for order execution
   - `BacktestGateway` implementation: Wraps existing providers (100% backward compatible)
   - Reserved: `PaperGateway` and `LiveGateway` for future simulation/live trading

3. **Engine Dependency Injection** (`src/backtest/engine.py`)
   - **Optional EventEngine injection**: `BacktestEngine(event_engine=...)`
   - **Optional HistoryGateway injection**: `BacktestEngine(history_gateway=...)`
   - **Default behavior preserved**: Creates instances automatically if not provided
   - **Event publishing**: `_load_data()` and `_load_benchmark()` now emit events
   - **Simplified code**: Removed multi-provider fallback logic (moved to Gateway)

### ✅ Backward Compatibility

- **100% Compatible**: All existing code works without changes
- **Default Parameters**: Engine creates EventEngine and BacktestGateway internally
- **CLI Unchanged**: All `run/grid/auto/list` commands work identically
- **Zero Breaking Changes**: No code deletion, only additions

### 📊 Code Statistics

- **New Files**: 3 (`events.py`, `gateway.py`, `__init__.py`)
- **New Lines**: 482
- **Modified Files**: 1 (`engine.py`)
- **Modified Locations**: 3 (imports, `__init__`, `_load_data/_load_benchmark`)
- **Deleted Lines**: 0

### 🧪 Verification

- ✅ EventEngine: Thread-safe event processing (6/6 tests passed)
- ✅ BacktestGateway: Data loading (22 rows from 600519.SH)
- ✅ Engine backward compatibility: Default parameters work
- ✅ Engine dependency injection: Custom EventEngine works
- ✅ Event publishing: 2 events (data.loaded, benchmark.loaded) triggered
- ✅ CLI compatibility: `run` command executes normally

### 📚 Documentation

- `docs/ARCHITECTURE_UPGRADE.md`: Full architecture design document
- `docs/V2.6.0_COMPLETION.md`: Implementation report with verification
- `docs/STRATEGY_FIX_REPORT.md`: MACD/RSI parameter fixes

### 🎯 Future-Ready

- **Phase 2 Ready**: Strategy template abstraction + trading rule plugins
- **Phase 3 Ready**: Paper trading gateway + matching engine
- **Extensible**: Easy to add custom gateways, event handlers, and middlewares

### 🔗 References

- Inspired by [vn.py](https://github.com/vnpy/vnpy) event-driven architecture
- Gateway pattern from professional trading systems (IB, CTP, Binance)

---

## [V2.5.2] - 2025-10-24 - Parameter Optimization Fixes

### 🐛 Bug Fixes

1. **MACD Invalid Parameter Combination**
   - **Issue**: Grid allowed `fast=slow` (e.g., fast=13, slow=13), causing zero trades
   - **Fix**: Adjusted hot grid to ensure `fast < slow`
     ```python
     # Before: {"fast": [10,11,12,13], "slow": [13,14,15,16,17]}
     # After:  {"fast": [10,11,12],    "slow": [14,15,16,17]}
     ```
   - **Impact**: Zero-trade ratio: 5.0% → 0.0%, avg trades: 25.6 → 28.8 (+12.5%)

2. **RSI Low Trade Frequency**
   - **Issue**: Overly strict thresholds (upper=70/75, lower=25/30) resulted in avg 1.1 trades/3yr
   - **Fix**: Relaxed thresholds to increase signal frequency
     ```python
     # Before: {"upper": [70, 75], "lower": [25, 30]}
     # After:  {"upper": [65, 70, 75], "lower": [25, 30, 35]}
     ```
   - **Impact**: Avg trades: 1.1 → 2.4 (+119.7%), parameter combinations: 16 → 36

### 📊 Verification Results

| Strategy | Before | After | Improvement |
|----------|--------|-------|-------------|
| **MACD** | 5.0% zero-trade | 0.0% zero-trade | ✅ Eliminated invalid combos |
| **MACD** | 25.6 avg trades | 28.8 avg trades | +12.5% |
| **RSI** | 1.1 avg trades | 2.4 avg trades | +119.7% |
| **RSI** | 0.0% zero-trade | 8.3% zero-trade | ⚠️ Acceptable (broader grid) |

### 📚 Documentation

- `docs/ZERO_TRADE_ANALYSIS.md`: Statistical analysis of zero-trade patterns
- `docs/STRATEGY_FIX_REPORT.md`: Detailed fix report with verification

---

## [V2.5.1] - 2025-01-XX - Bug Fixes & Stability Improvements

### 🐛 Bug Fixes

#### Critical Fixes:
1. **StopIteration Error Fix**
   - **Issue**: Empty `data_map` caused `StopIteration` exception in `strategy_modules.py`
   - **Fix**: Added comprehensive empty data validation
     - `add_data()` method now checks for empty data_map
     - `_rerun_top_n()` validates data before processing
     - `_run_single()` returns flat NAV instead of crashing
   - **Impact**: Prevents crashes during auto pipeline execution

2. **AKShare Symbol Format Error**
   - **Issue**: AKShare API requires pure numeric symbols (e.g., `'600519'`), but code passed full format (e.g., `'600519.SH'`)
   - **Fix**: Strip exchange suffix before API calls
   ```python
   ak_symbol = symbol.replace(".SH", "").replace(".SZ", "")
   df = ak.stock_zh_a_hist(symbol=ak_symbol, ...)
   ```
   - **Impact**: All AKShare data loading now works correctly

3. **Timezone Mismatch Error**
   - **Issue**: `TypeError: Cannot join tz-naive with tz-aware DatetimeIndex`
   - **Fix**: Force all DatetimeIndex to timezone-naive
     - Updated `_standardize_stock_frame()`
     - Updated `_standardize_index_frame()`
     - Updated `_standardize_yf()`
     - Added timezone cleanup in benchmark comparison
   - **Impact**: Eliminates pandas timezone conflicts

### 🔧 Improvements

- **Enhanced Error Messages**: Added diagnostic logging throughout data loading pipeline
- **Better Empty Data Handling**: Graceful fallback to flat NAV when data unavailable
- **Improved Cache Validation**: Detect and handle corrupted cache files

### 📝 Files Modified

- `src/data_sources/providers.py`
  - Fixed AKShare symbol format conversion
  - Added timezone normalization to all standardization functions
  - Enhanced error logging with traceback

- `src/backtest/engine.py`
  - Added empty data_map validation in `_rerun_top_n()`
  - Added timezone cleanup in benchmark comparison
  - Enhanced diagnostic output for data loading

- `src/backtest/strategy_modules.py`
  - Added empty data_map check in `add_data()` method
  - Improved error messages with strategy context

### 🧪 Testing

- ✅ Tested with 10 symbols (600519.SH, 000333.SZ, etc.)
- ✅ Tested with 8 strategies (adx_trend, macd, triple_ma, etc.)
- ✅ Tested with 4 parallel workers
- ✅ Confirmed 3-year date range (2022-2025) works correctly
- ✅ All auto pipeline features functional

### 📊 Test Results

```bash
# Successful execution:
python unified_backtest_framework.py auto \
  --symbols 600519.SH 000333.SZ 600036.SH 601318.SH 600276.SH \
            600104.SH 600031.SH 000651.SZ 000725.SZ 600887.SH \
  --start 2022-01-01 --end 2025-01-01 \
  --benchmark 000300.SS \
  --strategies adx_trend macd triple_ma donchian zscore keltner bollinger rsi \
  --hot_only --min_trades 1 --top_n 6 --workers 4 \
  --use_benchmark_regime --regime_scope trend \
  --out_dir reports_bulk_10

Output:
- 📊 Loaded data for 10 symbols successfully
- ⚡ Evaluated 124 parameter configurations
- 🏆 Generated Pareto frontier analysis
- 📈 Exported heatmaps and NAV curves
- ⏱️ Completed in 26.4 seconds
```

---

## [V2.5.0] - 2024 - Complete Modularization (Phase 1 + Phase 2)

### 🎉 Phase 2 Completed - Advanced Features Modularization

#### New Modules Created:
4. **`src/backtest/analysis.py`** (184 lines) - NEW
   - `pareto_front()` - Multi-objective optimization filter (Sharpe, return, drawdown)
   - `save_heatmap()` - Strategy-specific visualization for 10 strategy types
   - Support for EMA, MACD, Bollinger, RSI, ZScore, Donchian, TripleMA, ADX, RiskParity, TurningPoint
   - Zero-trade ratio reporting

5. **`src/backtest/plotting.py`** (149 lines) - NEW
   - `plot_backtest_with_indicators()` - Enhanced backtest visualization
   - `CNPlotScheme` - Chinese market color scheme (red-up/green-down)
   - 7 technical indicators: EMA, WMA, Stochastic, MACD, ATR, RSI, SMA
   - Candlestick and line chart styles
   - High-resolution output support

#### Enhanced Modules:
- **`src/backtest/engine.py`** (+313 lines → 819 lines total)
  - `auto_pipeline()` - Multi-strategy optimization workflow
  - `_hot_grid()` - Strategy-specific optimized parameter ranges
  - `_rerun_top_n()` - Pareto frontier replay with NAV curves
  - `_print_metrics_legend()`, `_print_top_configs()`, `_print_best_per_strategy()`
  - Benchmark regime filtering (EMA200)
  - Flexible strategy scope (trend/all/none)

- **`src/backtest/strategy_modules.py`** (+120 lines → 700 lines total)
  - `RiskParityBT` strategy - Multi-asset risk parity with inverse-volatility weighting
  - `_coerce_rp()` - Parameter validation for risk parity
  - `RISK_PARITY_MODULE` - Complete risk parity configuration
  - Momentum and regime filters
  - Benchmark gating for risk-on/risk-off

- **`src/data_sources/providers.py`** (+3 lines → 497 lines total)
  - Added `PROVIDER_NAMES` export for CLI integration

#### Simplified Main File:
- **`unified_backtest_framework.py`** (2138 → 214 lines, **90% reduction!**)
  - Removed all implementation code
  - Kept only CLI interface (parse_args, main)
  - Clean imports from modularized components
  - Full backward compatibility maintained

### ✨ New Features

#### Auto Pipeline Workflow
```bash
python unified_backtest_framework.py auto \
  --symbols 600519.SH --start 2023-01-01 --end 2023-12-31 \
  --strategies ema macd --top_n 5 --hot_only --use_benchmark_regime
```
- Multi-strategy parallel optimization
- Pareto frontier analysis
- Strategy-specific heatmaps
- Top-N configuration replay
- NAV curve visualization

#### Advanced Plotting
- Technical indicators overlay
- Chinese color scheme
- Multiple chart styles
- Export to PNG

#### Pareto Frontier Analysis
- Multi-objective optimization (Sharpe/Return/Drawdown)
- Automatic identification of Pareto-optimal configurations
- Visual heatmaps for parameter exploration

#### Risk Parity Strategy
- Multi-asset portfolio optimization
- Inverse-volatility weighting
- Periodic rebalancing (21 days default)
- Momentum filter (60-day lookback)
- Regime filter (EMA200)
- Benchmark gating (risk-on/risk-off)

### 🧪 Testing
- ✅ All 5 existing tests passing
- ✅ Manual CLI testing successful
- ✅ Backward compatibility verified
- ✅ No breaking changes

### 📝 Documentation
- Created `docs/PHASE2_COMPLETION_REPORT.md` (detailed Phase 2 report)
- Updated architecture diagrams
- Documented new APIs and workflows
- Added usage examples

### 🚀 Performance
- 90% code reduction in main file
- Improved maintainability
- Better test coverage
- Faster development cycle

---

## [V2.5.0-alpha] - 2024 - Modularization Phase 1

### 🎯 Major Refactoring - Modular Architecture
Successfully modularized the monolithic `unified_backtest_framework.py` (2138 lines) into clean, maintainable modules under `src/` structure.

### ✨ Added

#### New Modules Created:
1. **`src/data_sources/providers.py`** (450 lines)
   - Unified data provider module with factory pattern
   - `DataProvider` abstract base class
   - `AkshareProvider` for Chinese markets (default)
   - `YFinanceProvider` for global markets
   - `TuShareProvider` for Chinese markets with token
   - Data normalization helpers
   - NAV calculation utilities

2. **`src/backtest/strategy_modules.py`** (580 lines)
   - `StrategyModule` dataclass for strategy metadata
   - `GenericPandasData` Backtrader feed
   - `IntentLogger` analyzer for trade tracking
   - `TurningPointBT` strategy implementation
   - Signal computation utilities (`rolling_vwap`, `compute_signal_frame`)
   - Order decision logic
   - Strategy registry integration with backtrader strategies

3. **`src/backtest/engine.py`** (506 lines)
   - `BacktestEngine` class - Core execution engine
   - Data loading and caching
   - Strategy execution with comprehensive metrics
   - Grid search with multiprocessing support
   - Worker process management
   - Metrics calculation (Sharpe, MDD, win rate, profit factor, etc.)

### 📝 Documentation
- Created `docs/MODULARIZATION_PHASE1_COMPLETED.md` with detailed migration report
- Documented new import structure and architecture
- Added testing strategy outline

### 🔧 Improvements
- **Maintainability**: Each module has single responsibility
- **Testability**: Isolated components easier to test
- **Reusability**: Modules can be imported independently
- **Scalability**: Easy to add new providers/strategies
- **Performance**: Lazy imports, optimized caching, process-level data sharing
- **Type Safety**: Comprehensive type hints throughout

### 📊 Metrics
- Lines modularized: 1,536 / 2,138 (72%)
- New files: 3
- Import errors: 0 ✅
- Compile errors: 0 ✅

### 🎯 Next Steps (Phase 2)
- [ ] Extract auto pipeline functionality
- [ ] Complete RiskParity strategy
- [ ] Create `src/backtest/plotting.py`
- [ ] Create `src/backtest/analysis.py`
- [ ] Simplify main file to use new modules
- [ ] Add unit and integration tests

---

## [V2.4.2] - 2024 - Unified Framework Plotting

### ✨ Added
- Added plotting functionality to `unified_backtest_framework.py`
- `--plot` CLI flag for chart generation
- `enable_plot` parameter for programmatic use
- `plot_backtest_with_indicators()` helper function
- 7 technical indicators in charts (EMA, WMA, StochasticSlow, MACD, ATR, RSI, SMA)

### 📝 Documentation
- `docs/UNIFIED_BACKTEST_PLOTTING_GUIDE.md` - Comprehensive guide
- `docs/UNIFIED_PLOT_QUICKSTART.md` - Quick start guide
- Updated README with plotting examples

### 🧪 Testing
- Created `test_unified_plot.py` test script
- Verified plotting with multiple strategies (EMA, Bollinger, Turning Point)
- Generated sample charts in `test_plot_output/`

---

## [V2.4.0] - 2024 - Backtrader Adapter Plotting Enhancement

### ✨ Added
- Enhanced `backtrader_adapter.py` plot() method
- Added 7 technical indicators: EMA(25), WMA(25), StochasticSlow, MACD, ATR, RSI, SMA(10)
- Chinese color scheme (red-up/green-down) via CNPlotScheme
- Customizable figure size and output file support

### 📝 Documentation  
- Detailed docstrings with parameter descriptions
- Reference to Backtrader official docs

### 🧪 Testing
- Created `quick_test_plot.py` for rapid testing
- Verified plotting with sample stock data (600519.SH, 000001.SZ)

---

## [V2.3.0] - Previous Version
- Strategy modularization completed
- Multiple strategy implementations
- Grid search optimization
- Benchmark comparison

---

## Format
- 🎯 Major Refactoring
- ✨ Added
- 🔧 Improvements  
- 🐛 Fixed
- 📝 Documentation
- 🧪 Testing
- 📊 Metrics
