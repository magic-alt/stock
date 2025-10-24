# 架构升级计划 - 向vn.py靠拢

**日期**: 2025-10-24  
**版本**: V2.6.0 (架构升级)  
**状态**: 🔄 Phase 1 进行中

---

## 一、升级动机

### 当前架构痛点

| 问题 | 影响 | 优先级 |
|------|------|--------|
| **与Backtrader强耦合** | 难以切换撮合引擎（仿真/实盘） | 🔴 高 |
| **策略不可复用** | 回测与实盘需重写策略代码 | 🔴 高 |
| **缺乏事件驱动主干** | 组件间耦合，难以扩展 | 🟡 中 |
| **交易规则硬编码** | A股规则写死在engine中 | 🟡 中 |
| **配置分散** | 参数散落在代码各处 | 🟢 低 |

### vn.py的优势

vn.py通过以下设计实现了**一套策略，多种环境**的目标：

1. **EventEngine（事件总线）**：统一的消息中心
2. **Gateway（网关协议）**：抽象数据源和交易接口
3. **StrategyTemplate（策略模板）**：标准化回调接口
4. **MainEngine（应用总线）**：插件式架构

参考：
- https://github.com/vnpy/vnpy
- https://www.vnpy.com/docs/

---

## 二、升级策略

### 核心原则

✅ **保留现有优势**（A股规则、参数优化、可视化）  
✅ **最小化破坏性变更**（保持CLI和用户体验）  
✅ **渐进式实施**（分阶段落地，可回滚）  
✅ **向后兼容**（现有策略继续工作）

### 三阶段路线图

```
Phase 1 (本周)      Phase 2 (下周)        Phase 3 (月内)
基础设施           策略抽象              完善生态
┌──────────┐      ┌──────────┐         ┌──────────┐
│事件总线   │ →   │策略模板   │  →     │仿真撮合   │
│网关协议   │      │交易插件   │        │配置系统   │
│依赖注入   │      │事件驱动   │        │单元测试   │
└──────────┘      └──────────┘         └──────────┘
   3天              2-3天               待定
```

---

## 三、Phase 1实施（已完成✅）

### 1.1 事件总线核心

**文件**: `src/core/events.py`

**核心类**:
```python
@dataclass(slots=True)
class Event:
    type: str
    data: Any = None

class EventEngine:
    def register(self, etype: str, handler: Handler) -> None: ...
    def put(self, event: Event) -> None: ...
    def start(self) -> None: ...  # 启动后台线程
    def stop(self) -> None: ...
```

**标准事件类型**:
```python
class EventType:
    DATA_LOADED = "data.loaded"
    STRATEGY_SIGNAL = "strategy.signal"
    ORDER_FILLED = "order.filled"
    METRICS_CALCULATED = "metrics.calculated"
    PIPELINE_STAGE = "pipeline.stage"
    RISK_WARNING = "risk.warning"
    # ... 更多
```

**设计特点**:
- ✅ 线程安全（Queue + Thread）
- ✅ 非阻塞发布（put不会等待）
- ✅ 异常隔离（handler错误不影响其他handler）
- ✅ 优雅关闭（stop会等待线程）

### 1.2 网关协议

**文件**: `src/core/gateway.py`

**核心协议**:
```python
class HistoryGateway(Protocol):
    """历史数据接口"""
    def load_bars(...) -> Dict[str, pd.DataFrame]: ...
    def load_index_nav(...) -> pd.Series: ...

class TradeGateway(Protocol):
    """交易执行接口"""
    def send_order(...) -> Any: ...
    def cancel_order(...) -> None: ...
    def query_account() -> Dict[str, Any]: ...
    def query_position(...) -> Dict[str, Any]: ...
```

**BacktestGateway实现**:
```python
class BacktestGateway:
    """回测网关：包装现有providers"""
    def __init__(self, source: str = "akshare", cache_dir: str = "./cache"):
        self._prov = get_provider(source)  # 复用现有数据源
        
    def load_bars(self, symbols, start, end, adj=None):
        return self._prov.load_stock_daily(...)  # 向后兼容
```

**设计特点**:
- ✅ 向后兼容（BacktestGateway包装现有providers）
- ✅ 易于扩展（PaperGateway/LiveGateway预留）
- ✅ 统一接口（回测/仿真/实盘共用协议）

### 1.3 Engine依赖注入（下一步）

**目标**: 解耦Engine与数据源/事件系统

**改动点**: `src/backtest/engine.py`

```python
class BacktestEngine:
    def __init__(
        self,
        *,
        source: str = "akshare",  # 保持向后兼容
        benchmark_source: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
        # 新增：可选注入
        event_engine: EventEngine | None = None,
        history_gateway: HistoryGateway | None = None,
    ) -> None:
        # 默认使用BacktestGateway（保持向后兼容）
        self.events = event_engine or EventEngine()
        self.gw = history_gateway or BacktestGateway(source, cache_dir)
        
    def _load_data(self, symbols, start, end, adj=None):
        # 改用gateway协议
        data = self.gw.load_bars(symbols, start, end, adj=adj)
        # 发布事件
        self.events.put(Event(EventType.DATA_LOADED, {"symbols": list(data.keys())}))
        return data
```

**影响范围**:
- ✅ CLI不变（使用默认参数）
- ✅ 现有策略不变
- ✅ 测试/仿真场景可注入不同gateway

---

## 四、Phase 2计划（下周）

### 2.1 交易规则插件化

**目标**: 将A股规则抽成可配置插件

**文件**: `src/bt_plugins/fees_cn.py`

```python
class CNStockCommission(bt.CommInfoBase):
    """
    中国A股交易成本配置
    
    支持参数:
    - commission_rate: 佣金率（默认0.0001=万一）
    - min_commission: 最低佣金（默认0=免五）
    - stamp_tax_rate: 印花税率（默认0.0005=万五）
    - stamp_tax_on: 印花税征收方向（默认"sell"）
    """
    params = (
        ("commission_rate", 0.0001),
        ("min_commission", 0.0),  # 免五模式
        ("stamp_tax_rate", 0.0005),
        ("stamp_tax_on", "sell"),
    )
```

**使用方式**:
```python
# CLI新增参数
python unified_backtest_framework.py run \
  --fee-config fees_cn  # 使用A股规则
  --fee-config fees_us  # 使用美股规则（待实现）
```

### 2.2 策略模板抽象

**目标**: 统一策略接口，支持跨撮合引擎

**文件**: `src/strategy/template.py`

```python
class StrategyTemplate(Protocol):
    """标准策略模板协议"""
    params: Dict[str, Any]
    
    def on_init(self) -> None:
        """策略初始化（数据加载后）"""
        
    def on_start(self) -> None:
        """策略启动（回测开始前）"""
        
    def on_bar(self, symbol: str, bar: pd.Series) -> None:
        """新K线到达"""
        
    def on_stop(self) -> None:
        """策略停止"""

class BacktraderAdapter:
    """将StrategyTemplate适配到Backtrader"""
    def to_bt_strategy(self) -> type[bt.Strategy]:
        # 生成bt.Strategy子类
```

**示例策略**:
```python
class EMATemplate:
    """EMA交叉策略模板（可复用于回测/仿真/实盘）"""
    params = {"fast": 10, "slow": 30}
    
    def on_init(self):
        self.fast_ma = {}
        self.slow_ma = {}
    
    def on_bar(self, symbol, bar):
        # 计算均线
        # 生成信号
        if fast_ma > slow_ma and not self.position:
            self.buy(symbol, size=100)
```

**迁移路径**:
```python
# 方式1：继续使用Backtrader策略（向后兼容）
cerebro.addstrategy(TurningPointBT, ...)

# 方式2：使用新模板（推荐）
adapter = BacktraderAdapter(EMATemplate, fast=10, slow=30)
cerebro.addstrategy(adapter.to_bt_strategy())
```

### 2.3 Pipeline事件化

**目标**: 解耦pipeline职责，易于扩展

**改动**: `engine.auto_pipeline()`

```python
def auto_pipeline(self, ...):
    # 启动事件引擎
    self.events.start()
    
    # 注册事件处理器
    self.events.register(EventType.DATA_LOADED, self._on_data_loaded)
    self.events.register(EventType.PIPELINE_STAGE, self._on_stage_complete)
    self.events.register(EventType.METRICS_CALCULATED, self._save_csv)
    
    # 执行流程（发事件而非直接保存文件）
    data_map = self._load_data(...)  # 自动发DATA_LOADED事件
    self.events.put(Event(EventType.PIPELINE_STAGE, {"stage": "data_loaded"}))
    
    for strategy in strategies:
        results = self.grid_search(...)
        self.events.put(Event(EventType.METRICS_CALCULATED, {
            "strategy": strategy,
            "results": results
        }))
    
    self.events.stop()  # 优雅关闭
```

**好处**:
- 报告生成逻辑移到handler
- 可插拔监听器（如实时进度条、Telegram通知）
- 便于调试和日志

---

## 五、Phase 3展望（月内）

### 5.1 仿真撮合

**文件**: `src/core/paper_gateway.py`

```python
class PaperGateway(HistoryGateway, TradeGateway):
    """仿真交易网关"""
    def __init__(self, matching_engine: MatchingEngine):
        self._engine = matching_engine
        
    def send_order(self, symbol, side, size, price=None):
        # 提交到仿真撮合队列
        # 模拟滑点、延迟、部分成交
```

**撮合引擎**:
```python
class MatchingEngine:
    """
    仿真撮合引擎
    
    特性:
    - 限价/市价/止损单
    - 滑点模型（固定/百分比/冲击成本）
    - 成交延迟（tick级/秒级）
    - 部分成交模拟
    """
```

### 5.2 配置系统

**文件**: `config/backtest.yaml`

```yaml
# 默认配置
backtest:
  cash: 200000
  commission: 0.0001
  slippage: 0.001
  
# A股交易规则
markets:
  cn_stock:
    commission_rate: 0.0001
    min_commission: 0.0  # 免五
    stamp_tax_rate: 0.0005
    lot_size: 100
    price_tick: 0.01
  
  us_stock:
    commission_rate: 0.0
    min_commission: 1.0  # $1最低
    lot_size: 1
    price_tick: 0.01
```

**使用**:
```python
from pydantic import BaseSettings

class BacktestConfig(BaseSettings):
    cash: float = 200000
    commission: float = 0.0001
    
    class Config:
        env_file = "config/backtest.yaml"
```

### 5.3 风控中间件

**文件**: `src/risk/manager.py`

```python
class RiskManager:
    """
    风险管理中间件
    
    规则:
    - 单票最大持仓比例
    - 组合总敞口限制
    - 单日最大亏损
    - 连续亏损止损
    """
    def check_order(self, order: Order) -> bool:
        # 拦截超限订单
```

**事件集成**:
```python
engine.events.register(EventType.ORDER_SENT, risk_manager.check_order)
engine.events.register(EventType.RISK_BREACH, lambda e: print(f"风控告警: {e.data}"))
```

---

## 六、向后兼容性

### 现有功能保持不变

✅ **CLI命令**: `run/grid/auto/list` 全部正常  
✅ **现有策略**: 所有Backtrader策略继续工作  
✅ **数据源**: AKShare/YFinance/TuShare不受影响  
✅ **参数优化**: 网格搜索/Pareto分析/热力图正常  
✅ **可视化**: 绘图/指标/中文配色不变  

### 新旧混用

```python
# 旧方式：直接使用Engine（推荐现有用户）
engine = BacktestEngine(source="akshare")
engine.run_strategy("ema", ...)

# 新方式：注入gateway和events（推荐新功能）
events = EventEngine()
gateway = BacktestGateway("akshare")
engine = BacktestEngine(event_engine=events, history_gateway=gateway)
engine.run_strategy("ema", ...)
```

---

## 七、测试计划

### 单元测试

```python
# test/test_events.py
def test_event_engine():
    engine = EventEngine()
    events = []
    engine.register("test", lambda e: events.append(e))
    engine.start()
    engine.put(Event("test", "hello"))
    time.sleep(0.1)
    engine.stop()
    assert len(events) == 1
    assert events[0].data == "hello"

# test/test_gateway.py
def test_backtest_gateway():
    gw = BacktestGateway("akshare")
    data = gw.load_bars(["600519.SH"], "2024-01-01", "2024-01-31")
    assert "600519.SH" in data
    assert not data["600519.SH"].empty
```

### 集成测试

```bash
# 验证现有功能不受影响
python unified_backtest_framework.py run \
  --strategy ema --symbols 600519.SH \
  --start 2022-01-01 --end 2024-12-31

# 验证事件系统
python test/test_event_integration.py

# 验证gateway切换
python test/test_gateway_switch.py
```

---

## 八、文档更新

### 新增文档

- `docs/ARCHITECTURE_V2.6.md` - 架构设计文档
- `docs/EVENT_SYSTEM.md` - 事件系统使用指南
- `docs/GATEWAY_GUIDE.md` - 网关开发指南
- `docs/STRATEGY_TEMPLATE.md` - 策略模板指南

### 更新文档

- `README_V2.md` - 添加架构升级说明
- `项目总览_V2.md` - 更新架构图
- `CHANGELOG.md` - 记录V2.6.0变更

---

## 九、实施检查清单

### Phase 1（本周）

- [x] 创建 `src/core/events.py`
- [x] 创建 `src/core/gateway.py`
- [x] 创建 `src/core/__init__.py`
- [ ] 修改 `engine.py` 依赖注入
- [ ] 单元测试（events/gateway）
- [ ] 集成测试（验证向后兼容）
- [ ] 文档更新

### Phase 2（下周）

- [ ] 创建 `src/bt_plugins/fees_cn.py`
- [ ] 创建 `src/strategy/template.py`
- [ ] 示例模板策略（EMA/MACD）
- [ ] Pipeline事件化改造
- [ ] CLI参数扩展（--fee-config）
- [ ] 测试覆盖

### Phase 3（月内）

- [ ] PaperGateway实现
- [ ] MatchingEngine实现
- [ ] pydantic配置系统
- [ ] RiskManager中间件
- [ ] 性能测试
- [ ] 完整文档

---

## 十、风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 向后兼容性破坏 | 高 | 低 | 保留默认参数，充分测试 |
| 性能下降 | 中 | 低 | 事件系统异步，网关零拷贝 |
| 学习曲线 | 中 | 中 | 详细文档+示例+保持旧接口 |
| 代码复杂度增加 | 低 | 高 | 模块化设计+清晰协议 |

---

**下一步行动**: 完成Engine依赖注入改造，验证事件系统工作正常。

**负责人**: AI Assistant  
**审核**: User  
**完成时间**: 2025-10-24 ~ 2025-10-31
