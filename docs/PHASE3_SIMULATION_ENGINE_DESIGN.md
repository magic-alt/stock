# Phase 3: 仿真撮合引擎技术设计方案

> **版本**: V1.0.0  
> **创建日期**: 2024-01-XX  
> **状态**: 📅 设计阶段  
> **预计工期**: 3-5 天

---

## 📋 目录

1. [背景与目标](#1-背景与目标)
2. [技术路线选择](#2-技术路线选择)
3. [核心架构设计](#3-核心架构设计)
4. [关键技术方案](#4-关键技术方案)
5. [实施路线图](#5-实施路线图)
6. [性能与测试](#6-性能与测试)
7. [风险评估](#7-风险评估)
8. [参考资料](#8-参考资料)

---

## 1. 背景与目标

### 1.1 项目背景

当前框架主要用于**历史数据回测**（基于 Backtrader），但要实现**实盘交易**，需要解决以下问题：

| 问题域 | 回测环境 | 实盘环境 | 差距 |
|--------|---------|---------|------|
| **撮合延迟** | 0ms (即时成交) | 10-500ms | 时序错位 |
| **滑点影响** | 忽略 | 1-5 跳 | 成本偏差 |
| **部分成交** | 不考虑 | 常见 | 仓位偏差 |
| **订单拒绝** | 不会发生 | 风控拒绝 | 逻辑分支 |
| **行情延迟** | 完美数据 | 延迟/跳空 | 决策偏差 |

**仿真撮合引擎** 是连接回测与实盘的桥梁，需要在**不依赖真实市场**的情况下，模拟真实交易环境的复杂性。

### 1.2 核心目标

#### 功能目标
1. **订单生命周期管理**：创建 → 挂单 → 部分成交 → 完全成交/撤单
2. **撮合逻辑实现**：
   - 市价单：对手盘最优价格撮合
   - 限价单：价格匹配时撮合
   - 止损单：触发价格到达时转市价单
3. **滑点模型**：
   - 固定滑点：每笔固定 N 跳
   - 比例滑点：成交额的 X%
   - 市场冲击：根据订单量动态计算
4. **集成能力**：
   - 与 `PaperGateway` 无缝集成
   - 支持策略通过 EventEngine 下单
   - 与现有 Portfolio 组件对接

#### 非功能目标
| 指标 | 目标值 | 测量方法 |
|------|--------|---------|
| **撮合延迟** | < 10ms | 单笔订单处理时间 |
| **吞吐量** | > 1000 订单/秒 | 压力测试 |
| **结果一致性** | 与 Backtrader 偏差 < 0.1% | 对比回测 |
| **代码覆盖率** | > 90% | pytest-cov |

---

## 2. 技术路线选择

### 2.1 路线对比

#### **方案 A：完全自研撮合引擎** ⭐ 推荐
```python
# 优势：
+ 完全可控，可针对策略特点优化
+ 延迟可控（< 5ms）
+ 易于集成现有 EventEngine
+ 数据结构简单（只需维护订单簿）

# 劣势：
- 需要实现完整订单簿逻辑
- 初期开发工作量较大（3-5天）
```

#### **方案 B：适配 zipline-reloaded**
```python
# 优势：
+ 成熟的滑点/成本模型
+ 社区维护，bug 较少

# 劣势：
- 依赖 zipline 生态（pandas-datareader, empyrical）
- 与现有 Backtrader 架构冲突
- 性能较差（Python 实现）
```

#### **方案 C：集成 CCXT Pro（针对加密货币）**
```python
# 优势：
+ 支持 200+ 交易所的统一接口
+ 内置 WebSocket 实时行情

# 劣势：
- 仅支持加密货币市场
- 本项目主要针对 A 股
```

### 2.2 最终选择

**✅ 采用方案 A：自研撮合引擎**

**理由**：
1. **架构一致性**：与现有 EventEngine + Gateway 完美契合
2. **性能优势**：Python + 优化的数据结构可实现 < 10ms 延迟
3. **灵活性**：可针对 A 股市场特点定制（涨跌停、集合竞价等）
4. **维护成本**：代码量 < 1000 行，易于维护

---

## 3. 核心架构设计

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Strategy (策略)                           │
│                   ↓ 下单信号 (EventEngine)                        │
├─────────────────────────────────────────────────────────────────┤
│                      PaperGateway                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  MatchingEngine (核心)                      │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ OrderBook (订单簿)                                    │  │ │
│  │  │  - BidQueue (买单队列): SortedList[Order]            │  │ │
│  │  │  - AskQueue (卖单队列): SortedList[Order]            │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ SlippageModel (滑点模型)                             │  │ │
│  │  │  - FixedSlippage: 固定 N 跳                          │  │ │
│  │  │  - PercentSlippage: 成交额的 X%                      │  │ │
│  │  │  - VolumeShareSlippage: 市场冲击模型                 │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ Matcher (撮合逻辑)                                    │  │ │
│  │  │  - match_market_order()                              │  │ │
│  │  │  - match_limit_order()                               │  │ │
│  │  │  - match_stop_order()                                │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                   ↓ 成交回报 (TradeEvent)                        │
├─────────────────────────────────────────────────────────────────┤
│                  Portfolio (持仓管理)                            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心类设计

#### 3.2.1 Order (订单对象)

```python
@dataclass
class Order:
    """订单对象"""
    order_id: str              # 唯一订单 ID
    symbol: str                # 标的代码
    direction: OrderDirection  # BUY / SELL
    order_type: OrderType      # MARKET / LIMIT / STOP
    quantity: float            # 订单数量
    price: Optional[float]     # 限价单价格（市价单为 None）
    stop_price: Optional[float]  # 止损价格
    
    # 状态字段
    status: OrderStatus = OrderStatus.PENDING  # PENDING / PARTIAL / FILLED / CANCELLED
    filled_qty: float = 0.0    # 已成交数量
    avg_fill_price: float = 0.0  # 平均成交价
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 元数据
    strategy_id: Optional[str] = None
    fees: float = 0.0
    
    @property
    def remaining_qty(self) -> float:
        """剩余未成交数量"""
        return self.quantity - self.filled_qty
```

#### 3.2.2 OrderBook (订单簿)

```python
from sortedcontainers import SortedList

class OrderBook:
    """订单簿管理"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        # 买单队列：按价格降序排列（最高价优先）
        self.bids = SortedList(key=lambda o: (-o.price, o.timestamp))
        # 卖单队列：按价格升序排列（最低价优先）
        self.asks = SortedList(key=lambda o: (o.price, o.timestamp))
        
        # 止损单单独管理（未激活状态）
        self.stop_orders: Dict[str, Order] = {}
    
    def add_limit_order(self, order: Order) -> None:
        """添加限价单到订单簿"""
        if order.direction == OrderDirection.BUY:
            self.bids.add(order)
        else:
            self.asks.add(order)
    
    def add_stop_order(self, order: Order) -> None:
        """添加止损单（挂起状态）"""
        self.stop_orders[order.order_id] = order
    
    def check_stop_trigger(self, current_price: float) -> List[Order]:
        """检查止损单是否触发"""
        triggered = []
        for order_id, order in list(self.stop_orders.items()):
            if order.direction == OrderDirection.BUY and current_price >= order.stop_price:
                triggered.append(order)
                del self.stop_orders[order_id]
            elif order.direction == OrderDirection.SELL and current_price <= order.stop_price:
                triggered.append(order)
                del self.stop_orders[order_id]
        return triggered
    
    def get_best_bid(self) -> Optional[float]:
        """获取最高买价"""
        return self.bids[0].price if self.bids else None
    
    def get_best_ask(self) -> Optional[float]:
        """获取最低卖价"""
        return self.asks[0].price if self.asks else None
```

#### 3.2.3 SlippageModel (滑点模型)

```python
class SlippageModel(Protocol):
    """滑点模型协议"""
    def calculate_slippage(self, order: Order, market_price: float) -> float:
        """计算滑点后的成交价格"""
        ...

class FixedSlippage(SlippageModel):
    """固定滑点"""
    def __init__(self, slippage_ticks: int = 1, tick_size: float = 0.01):
        self.slippage_ticks = slippage_ticks
        self.tick_size = tick_size
    
    def calculate_slippage(self, order: Order, market_price: float) -> float:
        slippage = self.slippage_ticks * self.tick_size
        if order.direction == OrderDirection.BUY:
            return market_price + slippage  # 买入价格上滑
        else:
            return market_price - slippage  # 卖出价格下滑

class PercentSlippage(SlippageModel):
    """比例滑点"""
    def __init__(self, slippage_percent: float = 0.001):  # 默认 0.1%
        self.slippage_percent = slippage_percent
    
    def calculate_slippage(self, order: Order, market_price: float) -> float:
        slippage = market_price * self.slippage_percent
        if order.direction == OrderDirection.BUY:
            return market_price + slippage
        else:
            return market_price - slippage

class VolumeShareSlippage(SlippageModel):
    """市场冲击模型（根据订单量占成交量比例）"""
    def __init__(self, price_impact: float = 0.1):
        self.price_impact = price_impact
    
    def calculate_slippage(self, order: Order, market_price: float, 
                          avg_volume: float) -> float:
        """
        Args:
            avg_volume: 最近 N 根 K 线的平均成交量
        """
        volume_share = order.quantity / avg_volume
        slippage_percent = self.price_impact * volume_share  # 线性模型
        
        slippage = market_price * slippage_percent
        if order.direction == OrderDirection.BUY:
            return market_price + slippage
        else:
            return market_price - slippage
```

#### 3.2.4 MatchingEngine (撮合引擎)

```python
class MatchingEngine:
    """仿真撮合引擎"""
    
    def __init__(self, slippage_model: SlippageModel, event_engine: EventEngine):
        self.order_books: Dict[str, OrderBook] = {}  # symbol -> OrderBook
        self.slippage_model = slippage_model
        self.event_engine = event_engine
        
        # 订单索引（快速查找）
        self.active_orders: Dict[str, Order] = {}
        
    def submit_order(self, order: Order) -> None:
        """提交订单"""
        # 1. 初始化订单簿
        if order.symbol not in self.order_books:
            self.order_books[order.symbol] = OrderBook(order.symbol)
        
        # 2. 根据订单类型分发
        if order.order_type == OrderType.MARKET:
            self._match_market_order(order)
        elif order.order_type == OrderType.LIMIT:
            self.order_books[order.symbol].add_limit_order(order)
            self.active_orders[order.order_id] = order
        elif order.order_type == OrderType.STOP:
            self.order_books[order.symbol].add_stop_order(order)
            self.active_orders[order.order_id] = order
    
    def on_bar(self, symbol: str, bar: pd.Series) -> None:
        """行情更新时触发撮合"""
        if symbol not in self.order_books:
            return
        
        order_book = self.order_books[symbol]
        current_price = bar['close']
        
        # 1. 检查止损单触发
        triggered_stops = order_book.check_stop_trigger(current_price)
        for stop_order in triggered_stops:
            self._match_market_order(stop_order)
        
        # 2. 撮合限价单
        self._match_limit_orders(symbol, bar)
    
    def _match_market_order(self, order: Order) -> None:
        """撮合市价单（立即成交）"""
        order_book = self.order_books[order.symbol]
        
        # 获取对手盘最优价格
        if order.direction == OrderDirection.BUY:
            market_price = order_book.get_best_ask() or 0.0
        else:
            market_price = order_book.get_best_bid() or 0.0
        
        # 计算滑点后的实际成交价
        fill_price = self.slippage_model.calculate_slippage(order, market_price)
        
        # 生成成交回报
        trade = Trade(
            trade_id=f"T{order.order_id}",
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            price=fill_price,
            timestamp=datetime.now()
        )
        
        # 更新订单状态
        order.status = OrderStatus.FILLED
        order.filled_qty = order.quantity
        order.avg_fill_price = fill_price
        
        # 发送事件
        self.event_engine.emit(EventType.TRADE, trade)
    
    def _match_limit_orders(self, symbol: str, bar: pd.Series) -> None:
        """撮合限价单（价格匹配时成交）"""
        order_book = self.order_books[symbol]
        high_price = bar['high']
        low_price = bar['low']
        
        # 撮合买单（价格触及卖一价）
        for bid_order in list(order_book.bids):
            if bid_order.price >= low_price:  # 价格匹配
                fill_price = min(bid_order.price, high_price)  # 最优价格成交
                self._fill_order(bid_order, fill_price)
                order_book.bids.remove(bid_order)
        
        # 撮合卖单（价格触及买一价）
        for ask_order in list(order_book.asks):
            if ask_order.price <= high_price:
                fill_price = max(ask_order.price, low_price)
                self._fill_order(ask_order, fill_price)
                order_book.asks.remove(ask_order)
    
    def _fill_order(self, order: Order, fill_price: float) -> None:
        """执行成交"""
        trade = Trade(
            trade_id=f"T{order.order_id}",
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            price=fill_price,
            timestamp=datetime.now()
        )
        
        order.status = OrderStatus.FILLED
        order.filled_qty = order.quantity
        order.avg_fill_price = fill_price
        
        self.event_engine.emit(EventType.TRADE, trade)
        del self.active_orders[order.order_id]
    
    def cancel_order(self, order_id: str) -> None:
        """撤单"""
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            
            # 从订单簿移除
            order_book = self.order_books[order.symbol]
            if order.order_type == OrderType.LIMIT:
                if order.direction == OrderDirection.BUY:
                    order_book.bids.discard(order)
                else:
                    order_book.asks.discard(order)
            elif order.order_type == OrderType.STOP:
                order_book.stop_orders.pop(order_id, None)
            
            del self.active_orders[order_id]
            self.event_engine.emit(EventType.ORDER, order)
```

---

## 4. 关键技术方案

### 4.1 数据结构选择

#### **订单簿实现对比**

| 方案 | 插入复杂度 | 查询复杂度 | 删除复杂度 | 内存占用 | 推荐度 |
|------|----------|----------|----------|---------|--------|
| **List + 排序** | O(n log n) | O(1) | O(n) | 低 | ❌ |
| **Heap (heapq)** | O(log n) | O(1) | O(n) | 低 | ⚠️ |
| **SortedList** | O(log n) | O(1) | O(log n) | 中 | ✅ |
| **Red-Black Tree** | O(log n) | O(log n) | O(log n) | 高 | ⭐ |

**最终选择**：`sortedcontainers.SortedList`

**理由**：
- ✅ Python 原生实现，无 C 扩展依赖
- ✅ 平衡的增删改查性能
- ✅ 支持自定义排序 key（价格 + 时间优先级）
- ✅ 代码简洁，易于维护

```python
from sortedcontainers import SortedList

# 买单队列：价格降序，时间升序
bids = SortedList(key=lambda o: (-o.price, o.timestamp))

# 卖单队列：价格升序，时间升序
asks = SortedList(key=lambda o: (o.price, o.timestamp))
```

### 4.2 滑点模型算法

#### **固定滑点（适用于高流动性标的）**
```python
fill_price = market_price + sign * (ticks * tick_size)
# 示例：买入沪深 300 成分股，滑点 = 1 跳 = 0.01 元
```

#### **比例滑点（适用于一般标的）**
```python
fill_price = market_price * (1 + sign * slippage_percent)
# 示例：买入中盘股，滑点 = 0.1% = 0.001
```

#### **市场冲击模型（适用于大单）**
```python
# Almgren-Chriss 线性模型
volume_share = order_qty / avg_volume  # 订单占成交量比例
impact = price_impact_coeff * volume_share
fill_price = market_price * (1 + sign * impact)

# 示例：买入 1000 手，平均成交量 5000 手
# volume_share = 0.2, impact = 0.1 * 0.2 = 2%
```

### 4.3 部分成交处理

```python
class MatchingEngine:
    def _match_limit_order_partial(self, order: Order, available_qty: float) -> None:
        """支持部分成交"""
        if order.remaining_qty > available_qty:
            # 部分成交
            fill_qty = available_qty
            order.filled_qty += fill_qty
            order.status = OrderStatus.PARTIAL
        else:
            # 完全成交
            fill_qty = order.remaining_qty
            order.filled_qty = order.quantity
            order.status = OrderStatus.FILLED
        
        # 生成成交记录
        trade = Trade(quantity=fill_qty, ...)
        self.event_engine.emit(EventType.TRADE, trade)
```

### 4.4 集合竞价处理（A 股特色）

```python
class MatchingEngine:
    def on_auction(self, symbol: str, auction_price: float) -> None:
        """集合竞价撮合（9:15-9:25, 14:57-15:00）"""
        order_book = self.order_books[symbol]
        
        # 1. 撮合所有限价买单（价格 >= 开盘价）
        for bid in list(order_book.bids):
            if bid.price >= auction_price:
                self._fill_order(bid, auction_price)
                order_book.bids.remove(bid)
        
        # 2. 撮合所有限价卖单（价格 <= 开盘价）
        for ask in list(order_book.asks):
            if ask.price <= auction_price:
                self._fill_order(ask, auction_price)
                order_book.asks.remove(ask)
```

---

## 5. 实施路线图

### 5.1 阶段划分

```
Phase 3.1: 基础订单管理 (1 天) ──┐
Phase 3.2: 撮合引擎核心 (1.5 天) ├─→ Phase 3.5: 集成测试 (0.5 天)
Phase 3.3: 滑点模型实现 (1 天) ──┤
Phase 3.4: Gateway 集成 (1 天) ──┘
```

### 5.2 详细任务清单

#### **Phase 3.1: 基础订单管理** (预计 1 天)
- [ ] 创建 `src/simulation/order.py`：
  - [ ] `Order` 数据类
  - [ ] `OrderStatus`, `OrderType`, `OrderDirection` 枚举
  - [ ] `Trade` 数据类
- [ ] 创建 `src/simulation/order_book.py`：
  - [ ] `OrderBook` 类（使用 SortedList）
  - [ ] 添加/移除订单方法
  - [ ] 获取最优买卖价方法
- [ ] 单元测试：
  - [ ] 测试订单簿排序逻辑（价格优先 + 时间优先）
  - [ ] 测试止损单管理

#### **Phase 3.2: 撮合引擎核心** (预计 1.5 天)
- [ ] 创建 `src/simulation/matching_engine.py`：
  - [ ] `MatchingEngine` 类框架
  - [ ] `submit_order()` 方法
  - [ ] `_match_market_order()` 方法
  - [ ] `_match_limit_orders()` 方法
  - [ ] `cancel_order()` 方法
- [ ] 实现行情驱动逻辑：
  - [ ] `on_bar()` 方法（K 线更新触发撮合）
  - [ ] 止损单触发检查
- [ ] 单元测试：
  - [ ] 测试市价单立即成交
  - [ ] 测试限价单价格匹配成交
  - [ ] 测试止损单触发逻辑

#### **Phase 3.3: 滑点模型实现** (预计 1 天)
- [ ] 创建 `src/simulation/slippage.py`：
  - [ ] `SlippageModel` 协议
  - [ ] `FixedSlippage` 实现
  - [ ] `PercentSlippage` 实现
  - [ ] `VolumeShareSlippage` 实现
- [ ] 集成到 MatchingEngine：
  - [ ] 市价单应用滑点
  - [ ] 限价单应用滑点（可选）
- [ ] 单元测试：
  - [ ] 测试固定滑点计算
  - [ ] 测试比例滑点计算
  - [ ] 测试市场冲击模型（需 mock 成交量数据）

#### **Phase 3.4: Gateway 集成** (预计 1 天)
- [ ] 修改 `src/gateway/paper_gateway.py`：
  - [ ] 初始化 MatchingEngine
  - [ ] `send_order()` 方法调用 MatchingEngine
  - [ ] 订阅行情事件并转发到 MatchingEngine
- [ ] 事件流测试：
  - [ ] 策略 → EventEngine → PaperGateway → MatchingEngine
  - [ ] MatchingEngine → EventEngine → Portfolio
- [ ] 兼容性测试：
  - [ ] 确保不影响现有回测功能
  - [ ] 测试 `SimulationGateway` 模式

#### **Phase 3.5: 集成测试与优化** (预计 0.5 天)
- [ ] 端到端测试：
  - [ ] 使用 EMA 策略运行完整仿真
  - [ ] 对比 Backtrader 回测结果（偏差 < 0.5%）
- [ ] 性能测试：
  - [ ] 测量单笔订单处理延迟（目标 < 10ms）
  - [ ] 测试 1000 订单吞吐量
- [ ] 文档完善：
  - [ ] 更新使用指南
  - [ ] 添加 API 文档

### 5.3 时间估算

| 阶段 | 开发时间 | 测试时间 | 总计 | 累计进度 |
|------|---------|---------|------|---------|
| Phase 3.1 | 0.7 天 | 0.3 天 | 1 天 | 20% |
| Phase 3.2 | 1 天 | 0.5 天 | 1.5 天 | 50% |
| Phase 3.3 | 0.7 天 | 0.3 天 | 1 天 | 70% |
| Phase 3.4 | 0.7 天 | 0.3 天 | 1 天 | 90% |
| Phase 3.5 | 0.2 天 | 0.3 天 | 0.5 天 | 100% |
| **总计** | **3.3 天** | **1.7 天** | **5 天** | - |

---

## 6. 性能与测试

### 6.1 性能基准

#### **延迟要求**
```python
# 单笔订单处理延迟
def test_order_latency():
    engine = MatchingEngine(...)
    
    start = time.perf_counter()
    engine.submit_order(market_order)
    latency = time.perf_counter() - start
    
    assert latency < 0.010  # < 10ms
```

#### **吞吐量测试**
```python
# 每秒处理订单数
def test_throughput():
    engine = MatchingEngine(...)
    orders = [create_random_order() for _ in range(1000)]
    
    start = time.time()
    for order in orders:
        engine.submit_order(order)
    elapsed = time.time() - start
    
    throughput = len(orders) / elapsed
    assert throughput > 1000  # > 1000 订单/秒
```

### 6.2 正确性验证

#### **与 Backtrader 对比测试**
```python
def test_backtest_consistency():
    # 1. 使用 Backtrader 回测
    bt_result = run_backtrader_backtest(strategy, data)
    
    # 2. 使用仿真撮合引擎回测
    sim_result = run_simulation_backtest(strategy, data)
    
    # 3. 对比关键指标
    assert abs(bt_result['total_return'] - sim_result['total_return']) < 0.001
    assert abs(bt_result['sharpe'] - sim_result['sharpe']) < 0.05
    assert abs(bt_result['max_drawdown'] - sim_result['max_drawdown']) < 0.01
```

### 6.3 测试覆盖率目标

| 模块 | 行覆盖率 | 分支覆盖率 | 关键测试用例 |
|------|---------|-----------|------------|
| `order.py` | > 95% | > 90% | 订单状态转换 |
| `order_book.py` | > 95% | > 85% | 排序逻辑/止损触发 |
| `matching_engine.py` | > 90% | > 80% | 各类订单撮合 |
| `slippage.py` | > 95% | > 90% | 滑点计算准确性 |

---

## 7. 风险评估

### 7.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|-----|------|---------|
| **性能不达标** | 中 | 高 | 使用 cProfile 优化热点代码；考虑 Cython 加速 |
| **边界条件 bug** | 高 | 中 | 增加极端场景测试（涨跌停/停牌/大单） |
| **数据结构不适配** | 低 | 高 | 预先 benchmark SortedList vs heap vs treemap |
| **集成兼容性问题** | 中 | 高 | 保持 Gateway 接口不变，仅内部替换撮合逻辑 |

### 7.2 进度风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|-----|------|---------|
| **开发时间超期** | 中 | 中 | 按阶段交付，可先交付基础版本（无滑点） |
| **测试覆盖不足** | 高 | 高 | 每日 commit 时运行 pytest，保持 > 85% 覆盖率 |
| **文档滞后** | 高 | 低 | 边开发边更新文档，使用 docstring |

### 7.3 业务风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|-----|------|---------|
| **仿真与实盘偏差大** | 中 | 高 | 增加"实盘校准模式"（记录实盘滑点，动态调整模型） |
| **A 股特殊规则遗漏** | 高 | 中 | 逐步支持：涨跌停/集合竞价/科创板盘后交易 |

---

## 8. 参考资料

### 8.1 学术论文
1. **Almgren & Chriss (2000)**: "Optimal Execution of Portfolio Transactions" - 市场冲击模型
2. **Kissell & Glantz (2003)**: "Optimal Trading Strategies" - 交易成本分析
3. **Hasbrouck (2007)**: "Empirical Market Microstructure" - 订单簿动态

### 8.2 开源项目
- **QuantConnect LEAN**: C# 仿真撮合引擎实现
- **Zipline-Reloaded**: Python 滑点模型参考
- **Backtrader**: 现有回测框架

### 8.3 技术博客
- [Building a Limit Order Book in Python](https://web.archive.org/web/20110219163448/http://howtohft.wordpress.com/2011/02/15/building-a-trading-system-general-considerations/)
- [Market Impact Models](https://quantpedia.com/market-impact-models/)

---

## 附录：关键决策记录

| 决策点 | 选择 | 理由 |
|--------|-----|------|
| **撮合方式** | 订单驱动（Order-Driven） | 适合回测场景，逻辑简单 |
| **数据结构** | SortedList | 平衡性能与代码复杂度 |
| **滑点模型** | 三种模型（可配置） | 覆盖不同市场流动性场景 |
| **部分成交** | 暂不支持 | V1 版本简化，V2 再支持 |
| **集合竞价** | 延后到 V1.1 | 非核心功能，避免过度设计 |
| **并发模型** | 同步单线程 | 回测不需要高并发，避免复杂性 |

---

**下一步行动**：
1. 创建 `src/simulation/` 目录结构
2. 实现 Phase 3.1 基础订单管理
3. 编写单元测试并运行

**预期里程碑**：
- Day 1: 完成 Phase 3.1 (订单管理)
- Day 2: 完成 Phase 3.2 (撮合引擎)
- Day 3: 完成 Phase 3.3 (滑点模型)
- Day 4: 完成 Phase 3.4 (Gateway 集成)
- Day 5: 完成 Phase 3.5 (测试与优化)

---

**版本历史**：
- V1.0.0 (2024-01-XX): 初始设计方案
