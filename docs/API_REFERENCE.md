# API参考文档 (V2.10.3.1)

## 测试修正状态

**更新日期**: 2025-10-26

### 测试统计 ✅
- **总测试数**: 112
- **通过**: 86 (76.8%) ⬆️ 从63.4%提升
- **失败**: 18 (16.1%)
- **跳过**: 8 (7.1%)
- **警告**: 4

### 改进历程
1. **初始状态**: 21/112 通过 (18.8%)
2. **第一轮修正**: 71/112 通过 (63.4%) ⬆️ 238%
3. **第二轮修正**: 79/112 通过 (70.5%) ⬆️ 11%
4. **第三轮修正**: 86/112 通过 (76.8%) ⬆️ 9% ✨

### 已修正的测试文件 (6/8)
1. ✅ **test_core.py** - 核心对象和事件引擎测试 (9处修正)
2. ✅ **test_data.py** - 数据源和数据管理测试 (11处修正)
3. ✅ **test_backtest.py** - 回测引擎和分析测试 (4处修正)
4. ✅ **test_strategy.py** - 策略模板测试（完全重写，2处修正）
5. ✅ **test_pipeline.py** - 管道和因子测试（完全重写）
6. ✅ **test_system_integration.py** - 系统集成测试（8处修正）

### 主要API修正
- ✅ Direction枚举值是字符串 ("long", "short") 不是数字
- ✅ OrderData.remaining 是属性不是方法
- ✅ 数据提供商工厂函数是 get_provider 不是 create_data_provider
- ✅ 类名: DataProvider (不是BaseDataProvider), AkshareProvider (不是AkShareProvider)
- ✅ SQLiteDataManager方法: save_stock_data/load_stock_data (不是save_bars/load_bars)
- ✅ load_stock_data参数: start/end (不是start_date/end_date)
- ✅ DataPortal构造函数: provider (不是data_source)
- ✅ DataPortal没有db_manager属性
- ✅ Position类参数: size/avg_price (不是direction/volume/price)
- ✅ Account类参数: cash/total_value (不是balance/frozen)
- ✅ 缺失的函数: calculate_sharpe_ratio, calculate_max_drawdown, calculate_total_return
- ✅ 缺失的类: StrategyContext, FactorEngine, FactorLibrary, OrderManager

### 剩余问题 (18个失败测试)
- 3个 PaperGateway测试（构造函数参数不匹配）
- 3个 数据库管理器测试（方法签名细节）
- 1个 数据提供商接口测试
- 1个 系统覆盖率测试
- 其他测试主要是业务逻辑细节问题

---

本文档列出项目的实际API，供测试文件参考。

## src/core/objects.py

### 枚举类型
```python
class Direction(str, Enum):
    LONG = "long"       # 不是 1
    SHORT = "short"     # 不是 -1

class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"

class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class Exchange(str, Enum):
    SSE = "SSE"
    SZSE = "SZSE"
    BSE = "BSE"
```

### 数据类
```python
@dataclass
class BarData:
    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    # 注意：没有自动修正功能，high < low会抛出ValueError

@dataclass
class TickData:
    symbol: str
    datetime: datetime
    last_price: float
    volume: float
    # 注意：参数名是 last_price，不是 bid_price/ask_price

@dataclass
class OrderData:
    symbol: str
    direction: Direction
    order_type: OrderType
    price: float
    volume: int
    status: OrderStatus
    traded: float = 0
    # 注意：remaining 是属性不是方法
    @property
    def remaining(self) -> float:
        return self.volume - self.traded
    
    # 注意：is_active 是方法
    def is_active(self) -> bool:
        return self.status not in [OrderStatus.FILLED, OrderStatus.CANCELLED]

@dataclass
class PositionData:
    symbol: str
    direction: Direction
    volume: int
    frozen: int
    price: float
    # 注意：available 是属性不是方法
    @property
    def available(self) -> int:
        return self.volume - self.frozen

@dataclass
class AccountData:
    balance: float
    frozen: float
    available: float
    # 注意：这些都不是方法，需要手动计算
    # 没有 total_value() 和 risk_ratio() 方法
```

### 工具函数
```python
def parse_symbol(symbol: str) -> tuple[str, Optional[Exchange]]:
    """解析股票代码，返回 (代码, 交易所)"""
    # 返回元组，不是两个独立变量
```

## src/data_sources/providers.py

### 主类
```python
class DataProvider:  # 不是 BaseDataProvider
    """数据提供商基类"""
    name: str
    
    def get_bars(self, symbol: str, start: str, end: str, 
                 adjust: str = "none") -> Optional[pd.DataFrame]:
        pass

class AkshareProvider(DataProvider):  # 注意首字母大小写
    name = "akshare"

class TuShareProvider(DataProvider):
    name = "tushare"
    def __init__(self, token: str):
        self.token = token

class YFinanceProvider(DataProvider):
    name = "yfinance"
```

### 工厂函数
```python
def get_provider(name: str, cache_dir: str = CACHE_DEFAULT) -> DataProvider:
    """创建数据提供商"""
    # 不是 create_data_provider
```

## src/data_sources/db_manager.py

```python
class SQLiteDataManager:
    def __init__(self, db_path: str):
        pass
    
    def save_bars(self, symbol: str, data: pd.DataFrame, adjust: str):
        pass
    
    def load_bars(self, symbol: str, start_date: str, end_date: str, 
                  adjust: str) -> Optional[pd.DataFrame]:
        pass
    
    def check_data_exists(self, symbol: str, start_date: str, 
                         end_date: str, adjust: str) -> bool:
        pass
    
    def delete_bars(self, symbol: str, adjust: str):
        pass
    
    def close(self):
        pass
```

## src/data_sources/data_portal.py

```python
class DataPortal:
    def __init__(self, data_source: str = "akshare", cache_dir: str = None):
        self.provider: DataProvider
        self.db_manager: SQLiteDataManager
    
    def get_bars(self, symbol: str, start_date: str, end_date: str,
                 adjust: str = "none", use_cache: bool = True) -> Optional[pd.DataFrame]:
        pass
    
    def batch_download(self, symbols: List[str], start_date: str, 
                      end_date: str, adjust: str = "none") -> Dict[str, pd.DataFrame]:
        pass
```

## src/backtest/analysis.py

### 主要函数
```python
def pareto_front(df: pd.DataFrame) -> pd.DataFrame:
    """计算帕累托前沿"""
    # 参数是DataFrame，不是两个数组

def save_heatmap(module, df: pd.DataFrame, out_dir: str) -> None:
    """保存热力图"""
    # 参数不同，需要module和df

# 注意：没有以下函数
# calculate_sharpe_ratio()
# calculate_max_drawdown()
# calculate_total_return()
```

## src/backtest/engine.py

```python
class BacktestEngine:
    def __init__(self, strategy_class: str, strategy_params: dict,
                 initial_capital: float, output_dir: str):
        self.initial_capital = initial_capital
        self.data = {}
    
    def load_data(self, data_dict: Dict[str, pd.DataFrame]):
        pass
    
    def run(self) -> Optional[dict]:
        pass
```

## src/backtest/plotting.py

### 主要函数
```python
def plot_equity_curve(equity: pd.Series, output_file: str):
    """绘制净值曲线"""
    pass

def plot_drawdown(equity: pd.Series, output_file: str):
    """绘制回撤图"""
    pass

def generate_report(results: dict, output_file: str):
    """生成HTML报告"""
    pass

def save_plot(fig, output_file: str):
    """保存matplotlib图表"""
    pass
```

## src/backtest/strategy_modules.py

```python
STRATEGY_REGISTRY: Dict[str, Any]  # 策略注册表

def load_strategy_class(name: str):
    """加载策略类"""
    pass

def get_strategy_info(name: str) -> dict:
    """获取策略信息"""
    pass

def list_strategies() -> List[str]:
    """列出所有策略"""
    pass
```

## src/strategy/template.py

### 协议类
```python
class Context(Protocol):
    """策略上下文协议"""
    # 这是Protocol，不是具体类
    pass

class StrategyTemplate(Protocol):
    """策略模板协议"""
    # 这是Protocol，不是具体类
    def on_bar(self, bar) -> None:
        pass

# 注意：没有以下类
# StrategyContext
# get_strategy_params()
# validate_strategy_params()
```

### 具体类
```python
class BacktraderContext:
    """Backtrader上下文实现"""
    pass

class BacktraderAdapter:
    """Backtrader适配器"""
    pass
```

## src/simulation/order.py

```python
class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

class OrderDirection(Enum):
    BUY = "buy"
    SELL = "sell"

class Order:
    def __init__(self, symbol: str, direction: OrderDirection,
                 order_type: OrderType, volume: int, price: float = None):
        self.symbol = symbol
        self.direction = direction
        self.order_type = order_type
        self.volume = volume
        self.price = price
        self.status = OrderStatus.PENDING
        self.filled_volume = 0
    
    @property
    def remaining_volume(self) -> int:
        return self.volume - self.filled_volume
    
    def fill(self, volume: int, price: float):
        """成交"""
        pass
    
    def cancel(self):
        """撤单"""
        pass

class Trade:
    """成交记录"""
    pass

# 注意：没有 OrderManager 类
```

## src/simulation/order_book.py

```python
class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids = []  # 买单
        self.asks = []  # 卖单
    
    def add_bid(self, price: float, volume: int):
        pass
    
    def add_ask(self, price: float, volume: int):
        pass
    
    def best_bid(self) -> Optional[float]:
        pass
    
    def best_ask(self) -> Optional[float]:
        pass
    
    def spread(self) -> float:
        pass
    
    def match_order(self, direction, price: float, volume: int) -> Optional[int]:
        pass
```

## src/simulation/slippage.py

```python
class FixedSlippage:
    def __init__(self, slip: float):
        self.slip = slip
    
    def calculate(self, direction, price: float, volume: int) -> float:
        pass

class PercentSlippage:
    def __init__(self, percent: float):
        self.percent = percent
    
    def calculate(self, direction, price: float, volume: int) -> float:
        pass

class VolumeShareSlippage:  # 不是 VolumeSlippage
    def __init__(self, volume_limit: float = 0.025, impact: float = 0.1):
        pass
    
    def calculate(self, direction, price: float, volume: int) -> float:
        pass

# 注意：没有 create_slippage_model() 函数
```

## src/simulation/matching_engine.py

```python
class MatchingEngine:
    def __init__(self, slippage_model=None):
        self.slippage_model = slippage_model
    
    def match(self, order: Order, bar_data: dict) -> dict:
        """撮合订单"""
        # 返回字典，包含 matched, fill_volume, fill_price
        pass

# 注意：没有以下类
# SimpleMatchingEngine
# RealisticMatchingEngine
# MatchResult
```

## src/pipeline/factor_engine.py

```python
class Factor(ABC):
    """因子基类"""
    @abstractmethod
    def compute(self, data: pd.DataFrame) -> pd.Series:
        pass

class Returns(Factor):
    """收益率因子"""
    pass

class Momentum(Factor):
    """动量因子"""
    pass

class RSI(Factor):
    """RSI因子"""
    pass

class Pipeline:
    """因子管道"""
    def __init__(self):
        self.factors = []
    
    def add_factor(self, name: str, factor: Factor):
        pass
    
    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        """运行管道，返回所有因子"""
        pass

def create_pipeline(*factors) -> Pipeline:
    """创建管道"""
    pass

# 注意：没有以下类/函数
# FactorEngine
# FactorLibrary
# calculate_factor()
# combine_factors()
```

## src/pipeline/handlers.py

```python
class PipelineEventCollector:
    """管道事件收集器"""
    pass

def make_pipeline_handlers(out_dir: str) -> List[Tuple[str, Handler]]:
    """创建管道处理器"""
    pass

# 注意：没有以下类
# DataHandler
# SignalHandler
# PortfolioHandler
# create_handler_chain()
```

## src/core/events.py

```python
class EventType(str, Enum):
    TICK = "tick"
    BAR = "bar"
    ORDER = "order"
    TRADE = "trade"

class EventEngine:
    def __init__(self):
        self.is_running = False
        self._handlers = {}
    
    def start(self):
        self.is_running = True
    
    def stop(self):
        self.is_running = False
    
    def register(self, event_type: EventType, handler: Callable):
        pass
    
    def unregister(self, event_type: EventType, handler: Callable):
        pass
    
    def put(self, event: dict):
        """触发事件"""
        pass
```

## src/core/config.py

```python
class GlobalConfig(BaseModel):  # Pydantic模型
    data_source: str = "akshare"
    cache_dir: str = "./cache"
    commission: float = 0.0003
    slippage: float = 0.001
    # 注意：使用 Pydantic，不需要手动验证

class ConfigManager:
    """配置管理器"""
    pass
```

## src/core/risk_manager.py

```python
class RiskCheckResult:
    def __init__(self, passed: bool, message: str = ""):
        self.passed = passed
        self.message = message

class RiskManager:
    def __init__(self):
        self.rules = []
    
    def add_rule(self, rule):
        pass
    
    def check_order(self, order, account, positions) -> RiskCheckResult:
        """检查订单风控"""
        pass

def create_moderate_risk_manager() -> RiskManager:
    """创建中等风险管理器"""
    pass
```

## src/core/gateway.py

```python
class TradeGateway(ABC):
    """交易网关基类"""
    @abstractmethod
    def connect(self):
        pass
    
    @abstractmethod
    def send_order(self, order) -> Optional[str]:
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass
```

## src/core/paper_gateway.py

```python
class PaperGateway(TradeGateway):
    """模拟交易网关"""
    def __init__(self, event_engine: EventEngine):
        self.event_engine = event_engine
    
    def connect(self):
        """连接（模拟）"""
        pass
    
    def send_order(self, order) -> Optional[str]:
        """提交订单"""
        pass
    
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        pass
```

## 关键差异总结

### 1. 枚举值类型
- `Direction.LONG.value` = `"long"` (不是 `1`)
- `Direction.SHORT.value` = `"short"` (不是 `-1`)

### 2. 方法 vs 属性
- `order.remaining` - **属性**，不是方法
- `position.available` - **属性**，不是方法
- `order.is_active()` - **方法**，不是属性

### 3. 类名差异
- `DataProvider` (不是 `BaseDataProvider`)
- `AkshareProvider` (不是 `AkShareProvider`)
- `VolumeShareSlippage` (不是 `VolumeSlippage`)

### 4. 函数名差异
- `get_provider()` (不是 `create_data_provider()`)

### 5. 不存在的类/函数
- ❌ `StrategyContext`
- ❌ `FactorEngine`
- ❌ `FactorLibrary`
- ❌ `DataHandler`
- ❌ `SignalHandler`
- ❌ `PortfolioHandler`
- ❌ `OrderManager`
- ❌ `SimpleMatchingEngine`
- ❌ `RealisticMatchingEngine`
- ❌ `calculate_sharpe_ratio()`
- ❌ `calculate_max_drawdown()`
- ❌ `calculate_total_return()`
- ❌ `create_slippage_model()`

### 6. TickData参数
- 实际: `last_price`, `volume`
- 测试错误使用: `bid_price`, `ask_price`

### 7. BarData验证
- 不会自动修正 `high < low`
- 会抛出 `ValueError`

### 8. AccountData
- 没有 `total_value()` 方法
- 没有 `risk_ratio()` 方法
- 需要手动计算

---

**更新日期**: 2025-10-26
**版本**: V2.10.3.1
