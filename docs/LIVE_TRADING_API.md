# A股实盘交易接口实现文档

**版本**: V3.2.0+（P3 加固完成）
**更新日期**: 2026-02-28
**状态**: ✅ 已实现（桩模式 + SDK接口预留 + P3 生产加固）

---

## 1. 概述

本文档描述了量化回测与实盘系统中 A股实盘交易接口的实现。基于现有的统一策略接口 + 事件驱动 + 风控/订单生命周期框架，实现了三种主流的实盘交易网关：

| 网关 | 类名 | 优先级 | 适用场景 |
|------|------|--------|----------|
| **XtQuant/QMT** | `XtQuantGateway` | ⭐⭐⭐ | 个人投资者首选，生态最完善 |
| **中泰XTP** | `XtpGateway` | ⭐⭐ | 机构/量化客户，低延迟交易 |
| **恒生UFT** | `HundsunUftGateway` | ⭐⭐ | 机构通用柜台，可扩展性强 |

---

## 2. 架构设计

### 2.1 模块结构

```
src/gateways/
├── __init__.py              # 模块入口 + 网关工厂
├── base_live_gateway.py     # 抽象基类 + 通用功能
├── mappers.py               # 代码/订单字段映射
├── xtquant_gateway.py       # XtQuant/QMT 实现
├── xtp_gateway.py           # 中泰XTP 实现
└── hundsun_uft_gateway.py   # 恒生UFT 实现
```

### 2.2 与现有架构的集成

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│                 (CLI / GUI / REST API)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                          │
│              (BacktestEngine / PaperRunner)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Domain Layer                             │
│    ┌──────────────┬──────────────┬──────────────┐          │
│    │ RiskManager  │ OrderManager │ RealtimeData │          │
│    │    V2        │              │              │          │
│    └──────────────┴──────────────┴──────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                        │
│    ┌──────────────────────────────────────────────────┐    │
│    │               TradingGateway                      │    │
│    │  ┌─────────────┬─────────────┬─────────────┐    │    │
│    │  │ XtQuantGW   │   XtpGW     │ HundsunGW   │    │    │
│    │  │ (QMT)       │   (XTP)     │   (UFT)     │    │    │
│    │  └─────────────┴─────────────┴─────────────┘    │    │
│    └──────────────────────────────────────────────────┘    │
│    ┌──────────────┬──────────────┬──────────────┐          │
│    │  DataPortal  │  DBManager   │  EventEngine │          │
│    └──────────────┴──────────────┴──────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 事件驱动模型

```
[Broker SDK Callback Thread]
    │
    ▼
normalize(Order/Trade/Tick)
    │
    ▼
put(EventQueue)
    │
    ▼
[EventEngine Thread]
    │
    ▼
handle(OrderEvent/FillEvent/MarketEvent)
    │
    ├──► OrderManager (状态更新)
    ├──► RiskManager (风控检查)
    └──► Strategy (信号触发)
```

---

## 3. 快速开始

### 3.1 安装依赖

```bash
# 基础依赖
pip install -r requirements.txt

# XtQuant (通过QMT/MiniQMT终端获取)
# 安装后将xtquant添加到Python路径

# XTP SDK (从中泰证券获取)
# 需要C++编译环境

# Hundsun UFT (从券商获取)
# 需要C++编译环境
```

### 3.2 基本使用

```python
from queue import Queue
from src.gateways import (
    XtQuantGateway,
    XtpGateway,
    HundsunUftGateway,
    GatewayConfig,
    create_gateway,
)

# 方式1: 直接创建网关
config = GatewayConfig(
    account_id="YOUR_ACCOUNT",
    broker="xtquant",
    terminal_type="QMT",
)

event_queue = Queue()
gateway = XtQuantGateway(config, event_queue)

# 方式2: 使用工厂函数
gateway = create_gateway("xtquant", config, event_queue)

# 连接
gateway.connect()

# 发送订单
order_id = gateway.send_order(
    symbol="600519.SH",
    side="buy",
    quantity=100,
    price=1800.0,
    order_type="limit",
)

# 查询账户
account = gateway.query_account()

# 查询持仓
positions = gateway.query_positions()

# 撤单
gateway.cancel_order(order_id)

# 断开连接
gateway.disconnect()
```

---

## 4. API 参考

### 4.1 GatewayConfig

网关配置类，包含所有网关的配置参数。

```python
@dataclass
class GatewayConfig:
    # 通用配置
    account_id: str              # 交易账号（必填）
    broker: str = "xtquant"      # 券商类型
    password: Optional[str]      # 密码（建议使用环境变量）
    
    # XtQuant/QMT 配置
    terminal_type: str = "QMT"   # QMT 或 MiniQMT
    terminal_path: Optional[str] # 终端路径
    
    # XTP 配置
    trade_server: Optional[str]  # 交易服务器 tcp://ip:port
    quote_server: Optional[str]  # 行情服务器
    client_id: int = 1           # 客户端ID
    
    # Hundsun UFT 配置
    td_front: Optional[str]      # 交易前置 tcp://ip:port
    md_front: Optional[str]      # 行情前置
    
    # 连接配置
    auto_reconnect: bool = True  # 自动重连
    reconnect_interval: float = 5.0  # 重连间隔(秒)
    max_reconnect_attempts: int = 10 # 最大重连次数
    
    # 限流配置
    max_orders_per_second: float = 10.0  # 每秒最大订单数
```

### 4.2 BaseLiveGateway

所有网关的抽象基类。

#### 连接管理

```python
def connect(self) -> bool:
    """
    连接到券商。
    
    Returns:
        连接成功返回 True
    """

def disconnect(self) -> None:
    """断开连接。"""

def close(self) -> None:
    """关闭网关并释放资源。"""

@property
def is_connected(self) -> bool:
    """是否已连接。"""

@property
def status(self) -> GatewayStatus:
    """当前网关状态。"""
```

#### 订单管理

```python
def send_order(
    self,
    symbol: str,
    side: OrderSide | str,
    quantity: float,
    price: Optional[float] = None,
    order_type: OrderType | str = OrderType.LIMIT,
    time_in_force: TimeInForce = TimeInForce.DAY,
    strategy_id: str = "",
    **kwargs,
) -> str:
    """
    发送订单。
    
    Args:
        symbol: 标的代码 (e.g., "600519.SH")
        side: 方向 (buy/sell)
        quantity: 数量
        price: 价格 (限价单必填)
        order_type: 订单类型 (market/limit/stop)
        time_in_force: 有效期
        strategy_id: 策略ID
        
    Returns:
        client_order_id 用于跟踪
        
    Raises:
        RuntimeError: 网关未连接
        ValueError: 订单验证失败
    """

def cancel_order(self, client_order_id: str) -> bool:
    """
    撤销订单。
    
    Args:
        client_order_id: 客户端订单ID
        
    Returns:
        撤单请求是否成功发送
    """

def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
    """
    撤销所有订单。
    
    Args:
        symbol: 可选，按标的过滤
        
    Returns:
        已发送的撤单请求数
    """

def get_order(self, client_order_id: str) -> Optional[OrderUpdate]:
    """获取订单信息。"""

def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderUpdate]:
    """获取所有活动订单。"""
```

#### 查询接口

```python
def query_account(self) -> Optional[AccountUpdate]:
    """查询账户信息。"""

def query_positions(self) -> List[PositionUpdate]:
    """查询所有持仓。"""

def query_position(self, symbol: str) -> Optional[PositionUpdate]:
    """查询指定标的持仓。"""
```

#### 回调注册

```python
def on_order(self, callback: Callable[[OrderUpdate], None]) -> None:
    """注册订单更新回调。"""

def on_trade(self, callback: Callable[[TradeUpdate], None]) -> None:
    """注册成交更新回调。"""
```

### 4.3 数据结构

#### OrderStatus (订单状态)

```python
class OrderStatus(str, Enum):
    PENDING_SUBMIT = "pending_submit"  # 本地已创建
    SUBMITTED = "submitted"            # 已报
    PARTIALLY_FILLED = "partial_fill"  # 部分成交
    FILLED = "filled"                  # 全部成交
    CANCEL_PENDING = "cancel_pending"  # 待撤
    CANCELLED = "cancelled"            # 已撤
    REJECTED = "rejected"              # 废单
    EXPIRED = "expired"                # 过期
    ERROR = "error"                    # 错误
```

#### OrderUpdate (订单更新)

```python
@dataclass
class OrderUpdate:
    client_order_id: str     # 客户端订单号
    broker_order_id: str     # 券商订单号
    symbol: str              # 标的代码
    side: OrderSide          # 买卖方向
    status: OrderStatus      # 订单状态
    order_type: OrderType    # 订单类型
    price: float             # 委托价格
    quantity: float          # 委托数量
    filled_quantity: float   # 成交数量
    avg_fill_price: float    # 成交均价
    update_time: datetime    # 更新时间
    error_code: str          # 错误代码
    error_msg: str           # 错误信息
```

#### TradeUpdate (成交更新)

```python
@dataclass
class TradeUpdate:
    trade_id: str            # 成交编号
    client_order_id: str     # 客户端订单号
    broker_order_id: str     # 券商订单号
    symbol: str              # 标的代码
    side: OrderSide          # 买卖方向
    price: float             # 成交价格
    quantity: float          # 成交数量
    commission: float        # 手续费
    trade_time: datetime     # 成交时间
```

#### AccountUpdate (账户更新)

```python
@dataclass
class AccountUpdate:
    account_id: str          # 账户ID
    cash: float              # 现金
    available: float         # 可用资金
    frozen: float            # 冻结资金
    margin: float            # 保证金
    equity: float            # 总权益
    unrealized_pnl: float    # 浮动盈亏
    realized_pnl: float      # 实现盈亏
```

#### PositionUpdate (持仓更新)

```python
@dataclass
class PositionUpdate:
    symbol: str              # 标的代码
    total_quantity: float    # 总持仓
    available_quantity: float # 可用数量
    frozen_quantity: float   # 冻结数量
    yesterday_quantity: float # 昨仓
    today_quantity: float    # 今仓
    avg_price: float         # 持仓成本
    cost: float              # 成本金额
    market_value: float      # 市值
    unrealized_pnl: float    # 浮动盈亏
    last_price: float        # 最新价
```

---

## 5. 标的代码规范

### 5.1 内部格式

统一使用 `{code}.{exchange}` 格式：

| 市场 | 格式 | 示例 |
|------|------|------|
| 上交所 | XXXXXX.SH | 600519.SH |
| 深交所 | XXXXXX.SZ | 000001.SZ |
| 北交所 | XXXXXX.BJ | 430047.BJ |

### 5.2 代码映射

使用 `SymbolMapper` 进行格式转换：

```python
from src.gateways.mappers import SymbolMapper, XTPExchange

# 解析内部格式
code, exchange = SymbolMapper.parse("600519.SH")
# code = "600519", exchange = "SH"

# 转换为 XTP 格式
code, market = SymbolMapper.to_xtp("600519.SH")
# code = "600519", market = XTPExchange.SH (1)

# 从 XTP 格式转换
symbol = SymbolMapper.from_xtp("600519", XTPExchange.SH)
# symbol = "600519.SH"

# 转换为 UFT 格式
code, exchange_id = SymbolMapper.to_uft("600519.SH")
# code = "600519", exchange_id = "1"
```

---

## 6. 配置示例

### 6.1 config.yaml

```yaml
live_trading:
  enabled: true
  broker: "xtquant"
  account_id: "YOUR_ACCOUNT"
  
  # XtQuant/QMT 配置
  xtquant:
    terminal_type: "QMT"
    # password 建议使用环境变量: ${XTQUANT_PASSWORD}
  
  # XTP 配置
  xtp:
    trade_server: "tcp://x.x.x.x:6001"
    quote_server: "tcp://x.x.x.x:6002"
    client_id: 1
    # password: ${XTP_PASSWORD}
  
  # Hundsun UFT 配置
  hundsun_uft:
    td_front: "tcp://x.x.x.x:port"
    md_front: "tcp://x.x.x.x:port"
    # password: ${UFT_PASSWORD}
  
  # 连接配置
  auto_reconnect: true
  reconnect_interval: 5.0
  max_reconnect_attempts: 10
  heartbeat_interval: 30.0
  
  # 限流配置
  max_orders_per_second: 10.0
```

### 6.2 环境变量

```bash
# XtQuant
export XTQUANT_PASSWORD="your_password"

# XTP
export XTP_PASSWORD="your_password"

# Hundsun UFT
export UFT_PASSWORD="your_password"
```

---

## 7. 联调与测试

### 7.1 开发模式（桩模式）

当 SDK 不可用时，网关自动进入桩模式：

```python
gateway = XtQuantGateway(config, event_queue)
# 输出: xtp_gateway_stub_mode, msg="XTP SDK not available, running in stub mode"

# 桩模式下可以正常调用所有接口
gateway.connect()  # 返回 True
order_id = gateway.send_order(...)  # 返回模拟订单ID
account = gateway.query_account()  # 返回模拟数据
```

### 7.2 测试阶段

| 阶段 | 目标 | 验证点 |
|------|------|--------|
| 0 | 只接行情 | tick/bar 推送正常，断线重连 |
| 1 | 仿真交易 | 下单-撤单-查询一致性 |
| 2 | 最小实盘 | 单只股票限价单，严格风控 |
| 3 | 一致性校验 | 系统 vs 柜台持仓/资金/成交 |

### 7.3 生产必做清单

1. **幂等与去重**: `trade_id` 去重必做
2. **订单映射持久化**: `client_order_id ↔ broker_order_id` 落库
3. **断线恢复**: 重连后查询当日委托/成交/持仓
4. **交易时段控制**: 非交易时段拒单
5. **审计日志**: 全链路日志记录

---

## 8. 事件类型

### 8.1 网关事件

```python
class GatewayEventType:
    # 连接事件
    CONNECTED = "gateway.connected"
    DISCONNECTED = "gateway.disconnected"
    RECONNECTING = "gateway.reconnecting"
    ERROR = "gateway.error"
    
    # 订单事件
    ORDER_SUBMITTED = "gateway.order.submitted"
    ORDER_ACCEPTED = "gateway.order.accepted"
    ORDER_REJECTED = "gateway.order.rejected"
    ORDER_CANCELLED = "gateway.order.cancelled"
    ORDER_FILLED = "gateway.order.filled"
    ORDER_PARTIAL = "gateway.order.partial"
    ORDER_ERROR = "gateway.order.error"
    
    # 成交事件
    TRADE_EXECUTED = "gateway.trade.executed"
    
    # 账户/持仓事件
    ACCOUNT_UPDATE = "gateway.account.update"
    POSITION_UPDATE = "gateway.position.update"
```

### 8.2 事件处理示例

```python
from queue import Queue
import threading

event_queue = Queue()
gateway = XtQuantGateway(config, event_queue)

# 事件处理线程
def event_handler():
    while True:
        event = event_queue.get()
        event_type = event["type"]
        data = event["data"]
        
        if event_type == "gateway.order.filled":
            print(f"订单成交: {data}")
        elif event_type == "gateway.trade.executed":
            print(f"成交回报: {data}")
        elif event_type == "gateway.account.update":
            print(f"账户更新: {data}")

threading.Thread(target=event_handler, daemon=True).start()

# 连接并交易
gateway.connect()
gateway.send_order("600519.SH", "buy", 100, price=1800.0)
```

---

## 9. 网关对比

| 特性 | XtQuant/QMT | XTP | Hundsun UFT |
|------|-------------|-----|-------------|
| **个人可获得性** | ⭐⭐⭐ 高 | ⭐⭐ 中 | ⭐ 低 |
| **文档/生态** | ⭐⭐⭐ 完善 | ⭐⭐ 一般 | ⭐⭐ 一般 |
| **延迟** | 毫秒级 | 微秒级 | 毫秒级 |
| **Level2行情** | 支持 | 支持 | 支持 |
| **适用场景** | 个人/小资金 | 机构/量化 | 机构/资管 |
| **部署复杂度** | 低（终端+包） | 中（SDK编译） | 中（SDK编译） |

---

## 10. 参考资料

### 10.1 XtQuant/QMT

- [BigQuant QMT实盘教程](https://bigquant.com/wiki/doc/Ux2t1gwmNn)
- [ThinkTrader 文档](https://dict.thinktrader.net/nativeApi/)
- [知乎 XtQuant 详解](https://zhuanlan.zhihu.com/p/13330916214)

### 10.2 XTP

- [XTP GitHub](https://github.com/AtlasCoCo/Zhongtai_XTP_API_Python)
- [DolphinDB XTP 插件](https://docs.dolphindb.cn/zh/plugins/xtp.html)

### 10.3 Hundsun UFT

- [恒生极速接口文档](https://www.hs.net/home/openapi/)
- [vn.py UFT 讨论](https://www.vnpy.com/forum/topic/31782)

---

## 更新日志

### V3.2.0 (2026-01-11)

- ✅ 新增 `src/gateways/` 模块
- ✅ 实现 `BaseLiveGateway` 抽象基类
- ✅ 实现 `XtQuantGateway` (QMT/MiniQMT)
- ✅ 实现 `XtpGateway` (中泰XTP)
- ✅ 实现 `HundsunUftGateway` (恒生UFT)
- ✅ 实现 `SymbolMapper` 和 `OrderMapper`
- ✅ 支持桩模式开发
- ✅ 完整API文档

### V3.2.0+ / P3（2026-02-28）

- ✅ **QueryResultCache**：`base_live_gateway.py` 新增线程安全的异步查询结果缓存，使用 `threading.Event` 实现同步等待，彻底替代轮询/sleep 模式
- ✅ **SDK 路径动态配置**：`GatewayConfig` 新增 `sdk_path` / `sdk_log_path` 字段，`__post_init__` 自动注入 `sys.path`，支持多环境 SDK 部署
- ✅ **SDK import 明确报错**：XTP / 恒生 UFT 在 SDK 不可用时抛出明确 `ImportError`，替代静默 `try/except pass`
- ✅ **实盘运行器加固**（`src/core/live_runner.py`）：策略执行异常捕获 + skip/retry/halt 策略、仓位定期同步校验、启动/停止/异常事件审计日志
- ✅ **仿真 A 股规则**（`src/simulation/matching_engine.py`）：T+1 限制、涨跌停判断、停牌处理、整手限制（100股/手）
- ✅ **监控告警外发**（`src/core/monitoring.py`）：邮件/企业微信/钉钉 webhook 告警通道，阈值触发自动告警
- ✅ **Mock SDK 测试**（`tests/test_gateway_mock_sdk.py`）：12 个测试类覆盖 XTP/UFT stub 模式全生命周期、QueryResultCache、工厂函数、事件流
- ✅ **SDK 安装文档**（`docs/GATEWAY_SDK_SETUP.md`）：XTP/UFT/XtQuant SDK 安装、配置示例、故障排查
