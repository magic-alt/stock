# Phase 4-5 技术路线图

**文档版本**: V1.0  
**更新日期**: 2025-10-26  
**依赖**: [架构对比分析](./ARCHITECTURE_COMPARISON.md)

---

## 一、项目当前状态

### 1.1 已完成阶段（V2.8.6.5）

| 阶段 | 完成度 | 实际工期 | 状态 |
|------|-------|---------|------|
| **Phase 1: 基础设施** | 100% | 2天 | ✅ 完成 |
| - EventEngine（事件总线） | 100% | | ✅ |
| - Gateway协议（网关抽象） | 100% | | ✅ |
| - Engine依赖注入 | 100% | | ✅ |
| **Phase 2: 业务抽象** | 60% | 2天 | ⚠️ 部分完成 |
| - 交易规则插件化 | 100% | | ✅ |
| - Pipeline事件化 | 30% | | ⚠️ |
| - 策略模板抽象 | 0% | | ❌ 待实施 |
| - CLI参数扩展 | 0% | | ❌ 待实施 |
| **Phase 3: 仿真撮合** | 100% | 4小时 | ✅ 完成 |
| - 订单管理 | 100% | | ✅ |
| - 撮合引擎 | 100% | | ✅ |
| - 滑点模型 | 100% | | ✅ |
| - Gateway集成 | 100% | | ✅ |
| - 集成测试 | 100% | | ✅ 16/16通过 |

### 1.2 核心成果

**Phase 1 交付物**:
- ✅ `src/core/events.py` (364行) - 事件总线
- ✅ `src/core/gateway.py` (289行) - 网关协议
- ✅ `test/test_events.py` - 4个测试全通过
- ✅ `test/test_gateway.py` - 3个测试全通过

**Phase 2 交付物**:
- ✅ `src/bt_plugins/fees_cn.py` (189行) - A股费用插件
- ✅ `src/bt_plugins/sizers_cn.py` - 仓位管理插件
- ⚠️ 策略模板 - 未实施
- ⚠️ CLI参数 - 未实施

**Phase 3 交付物**:
- ✅ `src/simulation/order.py` (176行) - 订单数据类
- ✅ `src/simulation/order_book.py` (236行) - 订单簿
- ✅ `src/simulation/slippage.py` (208行) - 滑点模型
- ✅ `src/simulation/matching_engine.py` (326行) - 撮合引擎
- ✅ `src/core/paper_gateway.py` (+200行) - V3.0集成
- ✅ `test/test_simulation.py` (290行) - 12个单元测试
- ✅ `test/test_integration_simulation.py` (213行) - 4个集成测试

---

## 二、Phase 4 实施计划（标准化 + 数据门户）

### 2.1 目标概述

**核心主题**: 对标 VN.py/Zipline，完成策略标准化和数据管理

**关键里程碑**:
1. ⭐ **策略模板标准化**（Phase 2补完）- 策略跨引擎复用
2. ⭐ **数据对象标准化** - 统一数据结构
3. **DataPortal 数据门户** - 统一数据访问
4. **Pipeline 因子引擎** - 高效批量计算
5. **风控中间件** - 订单前风控
6. **统一配置系统** - YAML配置管理

### 2.2 详细任务清单

#### 🔴 高优先级（Week 1-2）

##### Task 4.1: 策略模板标准化 ⭐

**工期**: 2天  
**状态**: 📅 待实施  
**优先级**: 🔴 最高

**目标**: 策略可在回测/仿真/实盘复用（参考 VN.py CtaTemplate）

**设计方案**:
```python
# src/strategy/template.py
from typing import Protocol, Dict, Any
from src.core.objects import BarData, OrderData, PositionData

class StrategyTemplate(Protocol):
    """
    跨引擎策略模板协议
    - 不依赖 Backtrader
    - 标准生命周期
    - 统一数据/交易接口
    """
    params: Dict[str, Any]
    
    def on_init(self, context: Context) -> None:
        """初始化（加载历史数据/计算指标）"""
    
    def on_start(self, context: Context) -> None:
        """启动（开始交易前调用一次）"""
    
    def on_bar(self, context: Context, bar: BarData) -> None:
        """K线回调（主要交易逻辑）"""
    
    def on_stop(self, context: Context) -> None:
        """停止（清理资源/保存状态）"""

class Context:
    """策略上下文（统一API）"""
    def send_order(self, symbol: str, direction: str, 
                   volume: int, order_type: str = "market",
                   price: float = None) -> str:
        """发送订单"""
    
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
    
    def get_position(self, symbol: str) -> PositionData:
        """查询持仓"""
    
    def get_history(self, symbol: str, bars: int, 
                    fields: List[str] = ['close']) -> pd.DataFrame:
        """获取历史数据"""
    
    def log(self, message: str):
        """记录日志"""

# src/strategy/adapter.py
class BacktraderAdapter(bt.Strategy):
    """将 StrategyTemplate 适配到 Backtrader"""
    def __init__(self, template_class: Type[StrategyTemplate], **params):
        self.template = template_class()
        self.template.params = params
        self.context = BacktraderContext(self)
    
    def __init__(self):
        self.template.on_init(self.context)
    
    def start(self):
        self.template.on_start(self.context)
    
    def next(self):
        bar = self._convert_to_bardata()
        self.template.on_bar(self.context, bar)
    
    def stop(self):
        self.template.on_stop(self.context)
```

**使用示例**:
```python
# 新写法：策略模板
class EMAStrategy(StrategyTemplate):
    params = {"fast": 10, "slow": 20}
    
    def on_init(self, context):
        context.log(f"EMA Strategy: fast={self.params['fast']}, slow={self.params['slow']}")
    
    def on_bar(self, context, bar):
        history = context.get_history(bar.symbol, self.params['slow'])
        fast_ma = history['close'].tail(self.params['fast']).mean()
        slow_ma = history['close'].mean()
        
        position = context.get_position(bar.symbol)
        if fast_ma > slow_ma and position.volume == 0:
            context.send_order(bar.symbol, "buy", 100)
        elif fast_ma < slow_ma and position.volume > 0:
            context.send_order(bar.symbol, "sell", 100)

# 在 Backtrader 中使用
cerebro.addstrategy(BacktraderAdapter, 
                   template_class=EMAStrategy, 
                   fast=10, slow=20)
```

**待实现**:
- [ ] `src/strategy/template.py` - 协议定义
- [ ] `src/strategy/context.py` - Context类
- [ ] `src/strategy/adapter.py` - Backtrader适配器
- [ ] `src/strategies/ema_template.py` - EMA示例
- [ ] `src/strategies/macd_template.py` - MACD示例
- [ ] `test/test_strategy_template.py` - 单元测试

**验收标准**:
- ✅ 策略不依赖 Backtrader
- ✅ 同一策略可在回测/仿真运行
- ✅ 测试覆盖率 > 90%
- ✅ 向后兼容（旧策略继续工作）

---

##### Task 4.2: 数据对象标准化 ⭐

**工期**: 1天  
**状态**: 📅 待实施  
**优先级**: 🔴 高

**目标**: 统一数据结构（参考 VN.py trader.object）

**设计方案**:
```python
# src/core/objects.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# 枚举（扩展现有）
class OrderDirection(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

# 数据类（新增）
@dataclass
class BarData:
    """K线数据"""
    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_interest: float = 0.0  # 期货持仓量

@dataclass
class TickData:
    """Tick数据"""
    symbol: str
    datetime: datetime
    last_price: float
    volume: float
    turnover: float
    open_interest: float = 0.0
    
    # 五档行情
    bid_price_1: float = 0.0
    bid_volume_1: int = 0
    ask_price_1: float = 0.0
    ask_volume_1: int = 0

@dataclass
class OrderData:
    """订单数据（增强现有 Order）"""
    order_id: str
    symbol: str
    exchange: str = ""  # 交易所
    direction: OrderDirection
    order_type: OrderType
    volume: int
    price: float
    traded: int = 0  # 已成交数量
    status: OrderStatus = OrderStatus.PENDING
    datetime: datetime = None
    strategy_id: str = ""
    reference: str = ""  # 用户自定义标识

@dataclass
class TradeData:
    """成交数据（增强现有 Trade）"""
    trade_id: str
    order_id: str
    symbol: str
    exchange: str = ""
    direction: OrderDirection
    volume: int
    price: float
    datetime: datetime
    commission: float = 0.0
    strategy_id: str = ""

@dataclass
class PositionData:
    """持仓数据"""
    symbol: str
    exchange: str = ""
    direction: str = "long"  # "long" or "short"
    volume: int
    avg_price: float
    market_value: float
    pnl: float  # 总盈亏
    unrealized_pnl: float  # 浮动盈亏
    realized_pnl: float  # 已实现盈亏

@dataclass
class AccountData:
    """账户数据"""
    account_id: str
    balance: float  # 总资产
    available: float  # 可用资金
    commission: float  # 累计手续费
    margin: float = 0.0  # 期货保证金
    frozen: float = 0.0  # 冻结资金
    datetime: datetime = None
```

**迁移计划**:
1. 保留现有 `src/simulation/order.py` 中的数据类
2. 新增 `src/core/objects.py` 作为标准数据模型
3. 逐步迁移 `MatchingEngine` 和 `PaperGateway`
4. 更新策略模板使用新数据类

**待实现**:
- [ ] `src/core/objects.py` - 标准数据类
- [ ] 更新 `matching_engine.py` 使用新数据类
- [ ] 更新 `paper_gateway.py` 使用新数据类
- [ ] 更新测试使用新数据类
- [ ] 迁移文档

**验收标准**:
- ✅ 数据类型安全（IDE自动补全）
- ✅ 所有模块使用统一数据类
- ✅ 测试全部通过

---

#### 🟡 中优先级（Week 3-4）

##### Task 4.3: DataPortal 数据门户

**工期**: 3天  
**状态**: 📅 待实施  
**优先级**: 🟡 中

**目标**: 统一数据访问接口（参考 Zipline DataPortal）

**设计方案**:
```python
# src/data/portal.py
class DataPortal:
    """
    统一数据访问接口
    - 多数据源支持
    - 缓存管理
    - 数据对齐
    - 实时/历史统一
    """
    def __init__(self, providers: Dict[str, BaseDataProvider]):
        self._providers = providers
        self._cache = {}
        
    def get_history(self, symbols: Union[str, List[str]], 
                    start: str, end: str,
                    fields: List[str] = ['close'],
                    freq: str = '1d') -> Union[pd.DataFrame, pd.Series]:
        """
        获取历史数据
        
        Args:
            symbols: 单个或多个标的
            start: 开始日期
            end: 结束日期
            fields: 字段列表 ['open', 'high', 'low', 'close', 'volume']
            freq: 频率 '1d', '1h', '5m'
        
        Returns:
            单标的: Series (datetime索引)
            多标的: DataFrame (MultiIndex: datetime, symbol)
        """
        
    def current(self, symbols: Union[str, List[str]], 
                field: str) -> Union[float, pd.Series]:
        """
        获取当前值（简化接口）
        
        Args:
            symbols: 单个或多个标的
            field: 字段名
        
        Returns:
            单标的: float
            多标的: Series (symbol索引)
        """
        
    def get_current_bar(self, symbol: str) -> BarData:
        """获取当前K线（实时/仿真用）"""
        
    def get_current_tick(self, symbol: str) -> TickData:
        """获取当前Tick"""
```

**使用示例**:
```python
# 初始化
portal = DataPortal({
    'akshare': AkshareProvider(),
    'tushare': TushareProvider()
})

# 单标的历史数据
data = portal.get_history('600519.SH', '2023-01-01', '2023-12-31', fields=['close'])
# 返回: Series

# 多标的历史数据
data = portal.get_history(['600519.SH', '000858.SZ'], '2023-01-01', '2023-12-31')
# 返回: DataFrame (MultiIndex)

# 策略中使用
def on_bar(context, bar):
    # 获取最近20天收盘价
    history = context.portal.get_history(bar.symbol, bars=20, fields=['close'])
    ma20 = history.mean()
```

**待实现**:
- [ ] `src/data/portal.py` - DataPortal类
- [ ] 集成现有 providers
- [ ] 缓存策略实现
- [ ] 数据对齐算法
- [ ] 单元测试 + 性能测试

**验收标准**:
- ✅ 支持所有现有数据源
- ✅ 缓存命中率 > 80%
- ✅ 数据对齐正确性 100%
- ✅ 性能不低于直接调用 provider

---

##### Task 4.4: Pipeline 因子计算引擎

**工期**: 5天  
**状态**: 📅 待实施  
**优先级**: 🟡 中

**目标**: 高效批量因子计算（参考 Zipline Pipeline）

**设计方案**:
```python
# src/data/pipeline/factor.py
class Factor(ABC):
    """因子基类"""
    @abstractmethod
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """
        计算因子值
        
        Args:
            data: 输入数据 (MultiIndex: datetime, symbol)
        
        Returns:
            因子值 (MultiIndex: datetime, symbol)
        """

class SimpleMovingAverage(Factor):
    """简单移动平均"""
    def __init__(self, window: int):
        self.window = window
        
    def compute(self, data: pd.DataFrame) -> pd.Series:
        return data['close'].groupby(level='symbol').rolling(self.window).mean()

class RSI(Factor):
    """相对强弱指数"""
    def __init__(self, period: int = 14):
        self.period = period
        
    def compute(self, data: pd.DataFrame) -> pd.Series:
        def _rsi(prices):
            delta = prices.diff()
            gain = delta.where(delta > 0, 0).rolling(self.period).mean()
            loss = -delta.where(delta < 0, 0).rolling(self.period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        
        return data['close'].groupby(level='symbol').apply(_rsi)

# src/data/pipeline/pipeline.py
class Pipeline:
    """因子计算流水线"""
    def __init__(self):
        self._factors = {}
        
    def add(self, name: str, factor: Factor):
        """添加因子"""
        self._factors[name] = factor
        return self
    
    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        """批量计算因子"""
        results = {}
        for name, factor in self._factors.items():
            results[name] = factor.compute(data)
        return pd.DataFrame(results)
```

**因子库（30+因子）**:

| 类别 | 因子 | 说明 |
|------|------|------|
| **趋势** | SMA, EMA, MACD, ADX | 移动平均/趋势强度 |
| **动量** | RSI, ROC, MOM | 相对强弱/变化率 |
| **波动率** | ATR, BBands, Keltner | 真实波幅/布林带 |
| **成交量** | OBV, VWAP, VolumeRatio | 能量潮/成交量 |
| **形态** | Donchian, PivotPoints | 通道/枢轴点 |

**使用示例**:
```python
# 构建因子流水线
pipeline = Pipeline()
pipeline.add('ma20', SimpleMovingAverage(20))
pipeline.add('ma60', SimpleMovingAverage(60))
pipeline.add('rsi', RSI(14))
pipeline.add('atr', ATR(14))

# 批量计算（一次性计算所有标的和日期）
factors = pipeline.run(data)  # data: MultiIndex DataFrame

# 策略中使用
def on_bar(context, bar):
    ma20 = context.factors.loc[(bar.datetime, bar.symbol), 'ma20']
    ma60 = context.factors.loc[(bar.datetime, bar.symbol), 'ma60']
    if ma20 > ma60:
        context.send_order(bar.symbol, "buy", 100)
```

**待实现**:
- [ ] `src/data/pipeline/factor.py` - Factor基类
- [ ] `src/data/pipeline/pipeline.py` - Pipeline类
- [ ] `src/data/pipeline/factors/` - 30+因子实现
- [ ] 性能优化（Numba JIT）
- [ ] 单元测试 + 性能测试

**验收标准**:
- ✅ 30+ 因子实现
- ✅ 计算正确性 100%
- ✅ 性能提升 > 10x（vs 逐行计算）
- ✅ 内存优化（大数据集不OOM）

---

##### Task 4.5: 风控中间件

**工期**: 2天  
**状态**: 📅 待实施  
**优先级**: 🔴 高

**目标**: 订单前风控 + 实时监控

**设计方案**:
```python
# src/risk/manager.py
class RiskRule(ABC):
    """风控规则基类"""
    @abstractmethod
    def check(self, order: OrderData, portfolio: Portfolio) -> bool:
        pass
    
    @property
    @abstractmethod
    def reason(self) -> str:
        pass

class MaxPositionRule(RiskRule):
    """最大持仓限制"""
    def __init__(self, max_ratio: float = 0.3):
        self.max_ratio = max_ratio
        self._reason = ""
    
    def check(self, order: OrderData, portfolio: Portfolio) -> bool:
        if order.direction == OrderDirection.BUY:
            future_value = portfolio.get_position_value(order.symbol) + order.value
            ratio = future_value / portfolio.total_value
            if ratio > self.max_ratio:
                self._reason = f"持仓超限：{ratio:.2%} > {self.max_ratio:.2%}"
                return False
        return True
    
    @property
    def reason(self) -> str:
        return self._reason

class RiskManager:
    """风控中间件"""
    def __init__(self, event_engine: EventEngine):
        self.event_engine = event_engine
        self.rules: List[RiskRule] = []
        
    def add_rule(self, rule: RiskRule):
        """添加风控规则"""
        self.rules.append(rule)
        
    def check_order(self, order: OrderData, portfolio: Portfolio) -> bool:
        """订单前检查"""
        for rule in self.rules:
            if not rule.check(order, portfolio):
                self.event_engine.put(Event(
                    EventType.RISK_WARNING,
                    {'reason': rule.reason, 'order': order}
                ))
                return False
        return True
```

**风控规则清单**:

| 规则 | 说明 | 参数 |
|------|------|------|
| MaxPositionRule | 单只股票最大持仓比例 | max_ratio=0.3 |
| MaxDrawdownRule | 最大回撤止损 | max_dd=0.2 |
| MaxDailyLossRule | 单日最大亏损 | max_loss=0.05 |
| MinCashRule | 最低现金保留 | min_cash=10000 |
| PriceRangeRule | 价格范围检查 | min_price, max_price |

**待实现**:
- [ ] `src/risk/manager.py` - RiskManager类
- [ ] `src/risk/rules/` - 5+风控规则
- [ ] 集成到 `PaperGateway`
- [ ] 单元测试 + 集成测试

**验收标准**:
- ✅ 5+ 风控规则实现
- ✅ 订单前拦截正常工作
- ✅ 事件告警正常发布
- ✅ 测试覆盖率 > 90%

---

##### Task 4.6: 统一配置系统

**工期**: 1天  
**状态**: 📅 待实施  
**优先级**: 🟡 中

**目标**: YAML + 环境变量 + Pydantic校验

**设计方案**:
```python
# src/core/config.py
from pydantic import BaseSettings, Field, validator

class GlobalConfig(BaseSettings):
    """全局配置"""
    
    class Config:
        env_file = '.env'
        env_prefix = 'QUANT_'
        case_sensitive = False
    
    # 数据源
    data_provider: str = Field(default='akshare')
    tushare_token: str = Field(default='')
    cache_dir: str = Field(default='cache/')
    
    # 回测
    initial_cash: float = Field(default=1_000_000.0, ge=0)
    commission_rate: float = Field(default=0.0003, ge=0, le=0.01)
    slippage_rate: float = Field(default=0.001, ge=0, le=0.1)
    
    # 风控
    max_single_position: float = Field(default=0.3, ge=0, le=1)
    max_drawdown_stop: float = Field(default=0.2, ge=0, le=1)
    
    # 日志
    log_level: str = Field(default='INFO')
    log_file: str = Field(default='logs/quant.log')
    
    @validator('data_provider')
    def validate_provider(cls, v):
        valid = ['akshare', 'tushare', 'yfinance']
        if v not in valid:
            raise ValueError(f'Invalid provider: {v}')
        return v

# config/default.yaml
data_provider: akshare
initial_cash: 1000000.0
commission_rate: 0.0003
max_single_position: 0.3
log_level: INFO
```

**待实现**:
- [ ] `src/core/config.py` - 配置类
- [ ] `config/default.yaml` - 默认配置
- [ ] CLI支持 `--config` 参数
- [ ] 单元测试

**验收标准**:
- ✅ YAML配置正常加载
- ✅ 环境变量覆盖有效
- ✅ Pydantic校验生效
- ✅ CLI参数优先级正确

---

### 2.3 Phase 4 时间规划

| 任务 | 工期 | 优先级 | 周次 |
|------|------|--------|------|
| 策略模板标准化 | 2天 | 🔴 高 | Week 1 |
| 数据对象标准化 | 1天 | 🔴 高 | Week 1 |
| DataPortal 数据门户 | 3天 | 🟡 中 | Week 2 |
| Pipeline 因子引擎 | 5天 | 🟡 中 | Week 2-3 |
| 风控中间件 | 2天 | 🔴 高 | Week 3 |
| 统一配置系统 | 1天 | 🟡 中 | Week 3 |
| **合计** | **14天** | | **3周** |

**关键里程碑**:
- Week 1 结束：策略标准化完成，可跨引擎复用
- Week 2 结束：DataPortal + Pipeline完成，数据管理现代化
- Week 3 结束：风控 + 配置完成，Phase 4 全部完成

---

## 三、Phase 5 实施计划（生产部署）

### 3.1 目标概述

**核心主题**: 实盘交易支持 + 监控告警 + 性能优化

**关键里程碑**:
1. LiveGateway 实盘网关
2. Dashboard 监控面板
3. 性能优化（Cython/Numba）
4. 日志与审计

### 3.2 详细任务清单

#### Task 5.1: 实盘交易网关

**工期**: 15天  
**状态**: 📅 计划中  
**优先级**: 🔴 高

**目标**: 支持主流券商接口

**技术选型**:

| 券商 | 协议 | SDK | 难度 |
|------|------|-----|------|
| CTP期货 | TCP | openctp | ⭐⭐⭐⭐ |
| XTP股票 | TCP | xtp-python | ⭐⭐⭐⭐ |
| 华泰证券 | REST | - | ⭐⭐⭐ |
| 雪球/富途 | REST | futu-api | ⭐⭐ |

**设计方案**:
```python
# src/gateway/live_gateway.py
class LiveGateway(TradeGateway):
    """实盘交易网关"""
    def connect(self, config: dict) -> bool:
        """连接券商"""
    
    def subscribe(self, symbols: List[str]) -> None:
        """订阅行情"""
    
    def send_order(self, order: OrderData) -> str:
        """发送订单"""
    
    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
    
    def query_account(self) -> AccountData:
        """查询账户"""
    
    def query_position(self, symbol: str) -> PositionData:
        """查询持仓"""
```

**实施步骤**:
1. Week 1-2: CTP期货网关实现
2. Week 3: 单元测试 + 集成测试
3. Week 4: 实盘小额测试

**验收标准**:
- ✅ 连接成功率 > 99%
- ✅ 订单延迟 < 100ms
- ✅ 异常恢复机制完善

---

#### Task 5.2: 监控面板

**工期**: 10天  
**状态**: 📅 计划中  
**优先级**: 🟡 中

**技术栈**:
- 后端: Flask + SocketIO
- 前端: Vue.js + ECharts
- 数据库: SQLite (历史记录)

**功能模块**:
1. 策略监控（运行状态/持仓/盈亏）
2. 风控监控（实时指标/告警历史）
3. 系统监控（CPU/内存/延迟）
4. 交易日志（订单/成交记录）

**验收标准**:
- ✅ 实时推送延迟 < 1s
- ✅ Web UI 响应流畅
- ✅ 历史数据查询快速

---

#### Task 5.3: 性能优化

**工期**: 10天  
**状态**: 📅 计划中  
**优先级**: 🟢 低

**优化方向**:

| 技术 | 目标 | 提升 |
|------|------|------|
| Cython | 撮合引擎/指标计算 | 10-50x |
| Numba JIT | 因子计算 | 5-20x |
| PyArrow | 数据存储 | 3-5x |
| Dask | 并行计算 | 2-4x |

**验收标准**:
- ✅ 回测速度提升 > 10x
- ✅ 内存占用减少 > 30%
- ✅ 大规模数据不OOM

---

### 3.3 Phase 5 时间规划

| 任务 | 工期 | 优先级 | 月份 |
|------|------|--------|------|
| 实盘网关 | 15天 | 🔴 高 | Month 1-2 |
| 监控面板 | 10天 | 🟡 中 | Month 2 |
| 性能优化 | 10天 | 🟢 低 | Month 3 |
| **合计** | **35天** | | **3个月** |

---

## 四、总体时间线

```
当前 (2025-10-26)
    ↓
┌───────────────────────────────────────────────────────────────┐
│ Phase 2 补完 (Week 1)                                         │
│ - CLI 参数扩展                                                │
│ - 事件驱动完善                                                │
├───────────────────────────────────────────────────────────────┤
│ Phase 4 标准化 (Week 1-3)                                     │
│ - 策略模板 ⭐                                                 │
│ - 数据对象 ⭐                                                 │
│ - DataPortal                                                  │
│ - Pipeline                                                    │
│ - 风控中间件                                                  │
│ - 配置系统                                                    │
├───────────────────────────────────────────────────────────────┤
│ Phase 5 生产部署 (Month 1-3)                                  │
│ - 实盘网关                                                    │
│ - 监控面板                                                    │
│ - 性能优化                                                    │
└───────────────────────────────────────────────────────────────┘
    ↓
生产就绪 (2026-01-26)
```

**预计完成时间**: 2026年1月底（3个月后）

---

## 五、对标目标

### 5.1 短期（Phase 4完成后）

**对标 VN.py 回测模块水平**:
- ✅ 策略模板标准化
- ✅ 事件驱动完善
- ✅ 数据对象标准化
- ✅ 风控中间件

### 5.2 中期（Phase 5完成后）

**对标 Zipline 数据处理水平**:
- ✅ DataPortal 统一数据
- ✅ Pipeline 高效因子计算
- ✅ 性能优化（Cython/Numba）
- ✅ 实盘交易支持

### 5.3 长期（1年后）

**生产级量化平台**:
- ✅ 多市场支持（A股/期货/港股）
- ✅ 完整监控体系
- ✅ 风控系统完善
- ✅ 高性能引擎（> 10000笔/秒）

---

## 六、风险与缓解

### 6.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 实盘网关不稳定 | 🔴 高 | 🟡 中 | 多重连接重试 + 故障转移 |
| 性能优化效果不达标 | 🟡 中 | 🟢 低 | Cython分步优化，先易后难 |
| 数据对齐逻辑复杂 | 🟡 中 | 🟡 中 | 充分测试 + 边界条件覆盖 |

### 6.2 时间风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| Phase 4 超期 | 🟡 中 | 🟡 中 | MVP 优先，非核心功能延后 |
| 实盘网关开发延期 | 🔴 高 | 🟡 中 | 先完成仿真，实盘逐步接入 |

---

## 七、成功标准

### Phase 4 成功标准

- ✅ 策略可跨引擎复用（回测/仿真/实盘）
- ✅ 数据访问统一标准
- ✅ 因子计算性能提升 > 10x
- ✅ 风控规则完整有效
- ✅ 测试覆盖率 > 90%

### Phase 5 成功标准

- ✅ 实盘交易可用（小额验证）
- ✅ 监控面板完整可用
- ✅ 回测性能提升 > 10x
- ✅ 系统稳定性 > 99.5%
- ✅ 生产环境部署文档完善

---

**文档维护者**: AI Assistant  
**审核状态**: 待审核  
**下次更新**: Phase 4 完成后
