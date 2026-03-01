"""
Real-time Data Stream Module - 实时数据流模块

支持多种实时数据源:
- WebSocket 行情推送
- 分钟级K线订阅
- Tick级数据流
- 实时信号生成

V3.1.0: Initial release

Usage:
    >>> from src.core.realtime_data import RealtimeDataManager, DataSource
    >>> 
    >>> dm = RealtimeDataManager()
    >>> 
    >>> # 订阅行情
    >>> dm.subscribe(["600519.SH", "000333.SZ"])
    >>> 
    >>> # 注册回调
    >>> dm.on_bar(lambda bar: print(f"Bar: {bar.symbol} {bar.close}"))
    >>> dm.on_tick(lambda tick: print(f"Tick: {tick.symbol} {tick.last_price}"))
    >>> 
    >>> # 启动数据流
    >>> dm.start()
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Set

from src.core.interfaces import BarData, TickData
from src.core.events import EventEngine, Event
from src.core.logger import get_logger

logger = get_logger("realtime_data")


# ---------------------------------------------------------------------------
# Data Source Types
# ---------------------------------------------------------------------------

class DataSource(str, Enum):
    """Real-time data source types."""
    SINA = "sina"           # 新浪财经
    EASTMONEY = "eastmoney" # 东方财富
    TENCENT = "tencent"     # 腾讯财经
    FUTU = "futu"           # 富途
    IB = "ib"               # Interactive Brokers
    BINANCE = "binance"     # 币安 (Crypto)
    SIMULATION = "simulation"  # 模拟数据
    AKSHARE = "akshare"        # AKShare HTTP 轮询


class DataType(str, Enum):
    """Data types."""
    TICK = "tick"
    BAR_1M = "bar_1m"
    BAR_5M = "bar_5m"
    BAR_15M = "bar_15m"
    BAR_30M = "bar_30m"
    BAR_1H = "bar_1h"
    BAR_1D = "bar_1d"


# ---------------------------------------------------------------------------
# Data Events
# ---------------------------------------------------------------------------

class DataEvent(str, Enum):
    """Data stream events."""
    CONNECTED = "data.connected"
    DISCONNECTED = "data.disconnected"
    SUBSCRIBED = "data.subscribed"
    UNSUBSCRIBED = "data.unsubscribed"
    TICK = "data.tick"
    BAR = "data.bar"
    ERROR = "data.error"


# ---------------------------------------------------------------------------
# Real-time Quote
# ---------------------------------------------------------------------------

@dataclass
class RealtimeQuote:
    """Real-time quote data."""
    symbol: str
    timestamp: datetime
    
    # Prices
    last_price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    pre_close: float = 0.0
    
    # Volume
    volume: float = 0.0
    amount: float = 0.0
    
    # Bid/Ask
    bid_price: List[float] = field(default_factory=lambda: [0.0] * 5)
    bid_volume: List[float] = field(default_factory=lambda: [0.0] * 5)
    ask_price: List[float] = field(default_factory=lambda: [0.0] * 5)
    ask_volume: List[float] = field(default_factory=lambda: [0.0] * 5)
    
    @property
    def change(self) -> float:
        return self.last_price - self.pre_close
    
    @property
    def change_pct(self) -> float:
        if self.pre_close == 0:
            return 0.0
        return (self.last_price - self.pre_close) / self.pre_close * 100
    
    @property
    def spread(self) -> float:
        if self.ask_price[0] > 0 and self.bid_price[0] > 0:
            return self.ask_price[0] - self.bid_price[0]
        return 0.0
    
    def to_tick(self) -> TickData:
        """Convert to TickData."""
        return TickData(
            symbol=self.symbol,
            timestamp=self.timestamp,
            last_price=self.last_price,
            volume=self.volume,
            bid_price=self.bid_price[0] if self.bid_price else 0.0,
            ask_price=self.ask_price[0] if self.ask_price else 0.0,
            bid_volume=self.bid_volume[0] if self.bid_volume else 0.0,
            ask_volume=self.ask_volume[0] if self.ask_volume else 0.0
        )


# ---------------------------------------------------------------------------
# Bar Builder (Aggregate ticks to bars)
# ---------------------------------------------------------------------------

class BarBuilder:
    """
    Aggregate tick data into OHLCV bars.
    
    支持多周期:
    - 1分钟、5分钟、15分钟、30分钟、1小时、日线
    """
    
    def __init__(self, symbol: str, interval_minutes: int = 1):
        """
        Initialize bar builder.
        
        Args:
            symbol: Trading symbol
            interval_minutes: Bar interval in minutes
        """
        self.symbol = symbol
        self.interval = timedelta(minutes=interval_minutes)
        
        # Current bar
        self._current_bar: Optional[BarData] = None
        self._bar_start_time: Optional[datetime] = None
        
        # Completed bars
        self._bars: List[BarData] = []
        self._max_bars = 1000
    
    def update(self, tick: TickData) -> Optional[BarData]:
        """
        Update with tick data.
        
        Args:
            tick: Tick data
            
        Returns:
            Completed bar if interval elapsed, None otherwise
        """
        # Determine bar start time
        bar_start = self._get_bar_start_time(tick.timestamp)
        
        if self._current_bar is None or bar_start != self._bar_start_time:
            # New bar
            completed_bar = self._current_bar
            
            self._bar_start_time = bar_start
            self._current_bar = BarData(
                symbol=self.symbol,
                timestamp=bar_start,
                open=tick.last_price,
                high=tick.last_price,
                low=tick.last_price,
                close=tick.last_price,
                volume=tick.volume
            )
            
            if completed_bar:
                self._bars.append(completed_bar)
                if len(self._bars) > self._max_bars:
                    self._bars = self._bars[-self._max_bars:]
                return completed_bar
        else:
            # Update current bar
            self._current_bar.high = max(self._current_bar.high, tick.last_price)
            self._current_bar.low = min(self._current_bar.low, tick.last_price)
            self._current_bar.close = tick.last_price
            self._current_bar.volume += tick.volume
        
        return None
    
    def _get_bar_start_time(self, timestamp: datetime) -> datetime:
        """Get bar start time for a timestamp."""
        interval_seconds = int(self.interval.total_seconds())
        
        # Round down to interval
        seconds = timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second
        bar_seconds = (seconds // interval_seconds) * interval_seconds
        
        return timestamp.replace(
            hour=bar_seconds // 3600,
            minute=(bar_seconds % 3600) // 60,
            second=bar_seconds % 60,
            microsecond=0
        )
    
    def get_current_bar(self) -> Optional[BarData]:
        """Get current incomplete bar."""
        return self._current_bar
    
    def get_bars(self, count: int = 100) -> List[BarData]:
        """Get recent completed bars."""
        return self._bars[-count:]
    
    def force_close_bar(self) -> Optional[BarData]:
        """Force close current bar (e.g., at market close)."""
        if self._current_bar:
            completed = self._current_bar
            self._bars.append(completed)
            self._current_bar = None
            self._bar_start_time = None
            return completed
        return None


# ---------------------------------------------------------------------------
# Base Data Provider
# ---------------------------------------------------------------------------

class BaseDataProvider(ABC):
    """Abstract base class for real-time data providers."""
    
    def __init__(self, event_engine: Optional[EventEngine] = None):
        self.event_engine = event_engine
        self._connected = False
        self._subscribed_symbols: Set[str] = set()
        
        # Callbacks
        self._tick_callbacks: List[Callable[[TickData], None]] = []
        self._quote_callbacks: List[Callable[[RealtimeQuote], None]] = []
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to data source."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from data source."""
        pass
    
    @abstractmethod
    def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to symbols."""
        pass
    
    @abstractmethod
    def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from symbols."""
        pass
    
    def is_connected(self) -> bool:
        return self._connected
    
    def on_tick(self, callback: Callable[[TickData], None]) -> None:
        """Register tick callback."""
        self._tick_callbacks.append(callback)
    
    def on_quote(self, callback: Callable[[RealtimeQuote], None]) -> None:
        """Register quote callback."""
        self._quote_callbacks.append(callback)
    
    def _emit_tick(self, tick: TickData) -> None:
        """Emit tick to callbacks."""
        for callback in self._tick_callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.error("Tick callback error", error=str(e))
        
        if self.event_engine:
            self.event_engine.put(Event(DataEvent.TICK.value, tick))
    
    def _emit_quote(self, quote: RealtimeQuote) -> None:
        """Emit quote to callbacks."""
        for callback in self._quote_callbacks:
            try:
                callback(quote)
            except Exception as e:
                logger.error("Quote callback error", error=str(e))


# ---------------------------------------------------------------------------
# Simulation Data Provider
# ---------------------------------------------------------------------------

class SimulationDataProvider(BaseDataProvider):
    """
    模拟数据提供者
    
    用于测试和开发，生成模拟的实时行情数据。
    """
    
    def __init__(
        self,
        event_engine: Optional[EventEngine] = None,
        interval_ms: int = 1000,
        volatility: float = 0.001
    ):
        super().__init__(event_engine)
        self.interval_ms = interval_ms
        self.volatility = volatility
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._prices: Dict[str, float] = {}
    
    def connect(self) -> bool:
        """Start simulation."""
        logger.info("Simulation data provider connected")
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        """Stop simulation."""
        self.stop()
        self._connected = False
        logger.info("Simulation data provider disconnected")
    
    def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to symbols."""
        for symbol in symbols:
            self._subscribed_symbols.add(symbol)
            if symbol not in self._prices:
                # Initialize random price
                self._prices[symbol] = 100.0 + hash(symbol) % 1000
        logger.info("Subscribed to symbols", symbols=symbols)
    
    def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from symbols."""
        for symbol in symbols:
            self._subscribed_symbols.discard(symbol)
        logger.info("Unsubscribed from symbols", symbols=symbols)
    
    def start(self) -> None:
        """Start generating simulated data."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Simulation started")
    
    def stop(self) -> None:
        """Stop generating data."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Simulation stopped")
    
    def _run(self) -> None:
        """Main simulation loop."""
        import random
        
        while self._running:
            for symbol in list(self._subscribed_symbols):
                # Generate random price movement
                price = self._prices.get(symbol, 100.0)
                change = random.gauss(0, self.volatility) * price
                new_price = max(0.01, price + change)
                self._prices[symbol] = new_price
                
                # Create tick
                tick = TickData(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    last_price=new_price,
                    volume=random.randint(100, 10000),
                    bid_price=new_price * 0.999,
                    ask_price=new_price * 1.001,
                    bid_volume=random.randint(100, 5000),
                    ask_volume=random.randint(100, 5000)
                )
                
                self._emit_tick(tick)
            
            time.sleep(self.interval_ms / 1000)
    
    def set_price(self, symbol: str, price: float) -> None:
        """Set price for a symbol (for testing)."""
        self._prices[symbol] = price


# ---------------------------------------------------------------------------
# Sina Data Provider (Stub)
# ---------------------------------------------------------------------------

class SinaDataProvider(BaseDataProvider):
    """
    新浪财经实时行情 (Stub)
    
    实际实现需要:
    - HTTP 轮询 or WebSocket
    - 解析新浪行情数据格式
    
    Reference:
    - http://hq.sinajs.cn/list=sh600519
    """
    
    def __init__(self, event_engine: Optional[EventEngine] = None):
        super().__init__(event_engine)
        self._poll_interval = 3  # seconds
    
    def connect(self) -> bool:
        logger.info("Connecting to Sina...")
        # TODO: Implement actual connection
        raise NotImplementedError("Sina provider not implemented")
    
    def disconnect(self) -> None:
        self._connected = False
    
    def subscribe(self, symbols: List[str]) -> None:
        for symbol in symbols:
            self._subscribed_symbols.add(symbol)
    
    def unsubscribe(self, symbols: List[str]) -> None:
        for symbol in symbols:
            self._subscribed_symbols.discard(symbol)


# ---------------------------------------------------------------------------
# AKShare Data Provider (HTTP polling)
# ---------------------------------------------------------------------------

class AKShareDataProvider(BaseDataProvider):
    """
    AKShare 实时行情 HTTP 轮询提供者.

    使用 akshare 库的 stock_bid_ask_em() 接口每隔 interval 秒拉取买卖盘行情，
    转换为 TickData 推送给注册的回调。

    连接/断开线程安全；网络错误仅 warning，不崩溃。
    """

    def __init__(
        self,
        interval: float = 3.0,
        event_engine: Optional[EventEngine] = None,
    ) -> None:
        super().__init__(event_engine)
        self.interval = interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def connect(self) -> bool:
        """启动后台轮询线程."""
        if self._connected:
            return True
        try:
            import akshare  # noqa: F401 — validate package available
        except ImportError as exc:
            logger.warning("akshare not installed; AKShareDataProvider unavailable", error=str(exc))
            return False
        self._connected = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="akshare-poll")
        self._thread.start()
        logger.info("AKShareDataProvider connected, polling every %.1fs", self.interval)
        return True

    def disconnect(self) -> None:
        """停止轮询线程."""
        self._connected = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(self.interval * 2, 5))
        self._thread = None
        logger.info("AKShareDataProvider disconnected")

    def subscribe(self, symbols: List[str]) -> None:
        for symbol in symbols:
            self._subscribed_symbols.add(symbol)

    def unsubscribe(self, symbols: List[str]) -> None:
        for symbol in symbols:
            self._subscribed_symbols.discard(symbol)

    def _poll_loop(self) -> None:
        """轮询主循环（后台线程）."""
        while not self._stop_event.is_set():
            for symbol in list(self._subscribed_symbols):
                try:
                    tick = self._fetch_tick(symbol)
                    if tick is not None:
                        self._emit_tick(tick)
                except Exception as exc:
                    logger.warning("AKShareDataProvider poll error", symbol=symbol, error=str(exc))
            self._stop_event.wait(timeout=self.interval)

    def _fetch_tick(self, symbol: str) -> Optional[TickData]:
        """获取单只股票实时行情并转换为 TickData."""
        import akshare as ak  # lazy import

        # 标准化代码：去除交易所后缀，保留纯数字代码
        raw_code = symbol.split(".")[0]
        try:
            df = ak.stock_bid_ask_em(symbol=raw_code)
        except Exception as exc:
            logger.warning("akshare fetch failed", symbol=symbol, error=str(exc))
            return None

        if df is None or df.empty:
            return None

        # stock_bid_ask_em 返回 item/value 两列
        try:
            row = df.set_index("item")["value"]

            def _safe_float(key: str) -> float:
                try:
                    return float(row.get(key, 0) or 0)
                except (ValueError, TypeError):
                    return 0.0

            last_price = _safe_float("最新")
            if last_price == 0.0:
                last_price = _safe_float("现价")

            return TickData(
                symbol=symbol,
                timestamp=datetime.now(),
                last_price=last_price,
                volume=_safe_float("总手"),
                bid_price=_safe_float("买一价"),
                ask_price=_safe_float("卖一价"),
                bid_volume=_safe_float("买一量"),
                ask_volume=_safe_float("卖一量"),
            )
        except Exception as exc:
            logger.warning("AKShareDataProvider parse error", symbol=symbol, error=str(exc))
            return None


# ---------------------------------------------------------------------------
# WebSocket Data Provider Base
# ---------------------------------------------------------------------------

class WebSocketDataProvider(BaseDataProvider):
    """
    WebSocket 实时数据提供者基类
    
    子类需要实现:
    - _get_ws_url(): WebSocket URL
    - _build_subscribe_message(): 订阅消息
    - _parse_message(): 解析行情消息
    """
    
    def __init__(self, event_engine: Optional[EventEngine] = None):
        super().__init__(event_engine)
        self._ws = None
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False
    
    @abstractmethod
    def _get_ws_url(self) -> str:
        """Get WebSocket URL."""
        pass
    
    @abstractmethod
    def _build_subscribe_message(self, symbols: List[str]) -> str:
        """Build subscription message."""
        pass
    
    @abstractmethod
    def _parse_message(self, message: str) -> Optional[TickData]:
        """Parse WebSocket message to TickData."""
        pass
    
    def connect(self) -> bool:
        """Connect to WebSocket."""
        try:
            import websocket
        except ImportError:
            logger.error("websocket-client not installed")
            return False
        
        url = self._get_ws_url()
        logger.info("Connecting to WebSocket", url=url)
        
        self._ws = websocket.WebSocketApp(
            url,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        
        self._running = True
        self._ws_thread = threading.Thread(target=self._ws.run_forever, daemon=True)
        self._ws_thread.start()
        
        return True
    
    def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._running = False
        if self._ws:
            self._ws.close()
        if self._ws_thread:
            self._ws_thread.join(timeout=2)
        self._connected = False
    
    def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to symbols."""
        for symbol in symbols:
            self._subscribed_symbols.add(symbol)
        
        if self._connected and self._ws:
            message = self._build_subscribe_message(symbols)
            self._ws.send(message)
    
    def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from symbols."""
        for symbol in symbols:
            self._subscribed_symbols.discard(symbol)
    
    def _on_ws_open(self, ws):
        """Handle WebSocket open."""
        logger.info("WebSocket connected")
        self._connected = True
        
        # Subscribe to symbols
        if self._subscribed_symbols:
            message = self._build_subscribe_message(list(self._subscribed_symbols))
            ws.send(message)
    
    def _on_ws_message(self, ws, message):
        """Handle WebSocket message."""
        try:
            tick = self._parse_message(message)
            if tick:
                self._emit_tick(tick)
        except Exception as e:
            logger.error("Error parsing message", error=str(e))
    
    def _on_ws_error(self, ws, error):
        """Handle WebSocket error."""
        logger.error("WebSocket error", error=str(error))
    
    def _on_ws_close(self, ws, close_status, close_msg):
        """Handle WebSocket close."""
        logger.warning("WebSocket closed", status=close_status, close_msg=close_msg)
        self._connected = False


# ---------------------------------------------------------------------------
# Real-time Data Manager
# ---------------------------------------------------------------------------

class RealtimeDataManager:
    """
    实时数据管理器
    
    统一管理多个数据源，提供:
    - 多源数据订阅
    - Tick/Bar 数据回调
    - K线聚合
    - 数据缓存
    
    Usage:
        >>> dm = RealtimeDataManager()
        >>> dm.add_provider(DataSource.SIMULATION, SimulationDataProvider())
        >>> 
        >>> dm.subscribe(["600519.SH", "000333.SZ"])
        >>> dm.on_tick(lambda t: print(t))
        >>> dm.on_bar(lambda b: print(b), interval=1)
        >>> 
        >>> dm.start()
    """
    
    def __init__(self, event_engine: Optional[EventEngine] = None):
        """Initialize data manager."""
        self.event_engine = event_engine
        
        # Providers
        self._providers: Dict[DataSource, BaseDataProvider] = {}
        self._active_provider: Optional[DataSource] = None
        
        # Bar builders
        self._bar_builders: Dict[str, Dict[int, BarBuilder]] = defaultdict(dict)
        
        # Callbacks
        self._tick_callbacks: List[Callable[[TickData], None]] = []
        self._bar_callbacks: Dict[int, List[Callable[[BarData], None]]] = defaultdict(list)
        
        # Data cache
        self._latest_ticks: Dict[str, TickData] = {}
        self._latest_bars: Dict[str, Dict[int, BarData]] = defaultdict(dict)
        
        # State
        self._running = False
    
    def add_provider(self, source: DataSource, provider: BaseDataProvider) -> None:
        """Add data provider."""
        self._providers[source] = provider
        provider.on_tick(self._on_tick)
        logger.info("Data provider added", source=source.value)
    
    def set_active_provider(self, source: DataSource) -> None:
        """Set active data provider."""
        if source not in self._providers:
            raise ValueError(f"Provider not found: {source}")
        self._active_provider = source
    
    def get_provider(self, source: Optional[DataSource] = None) -> Optional[BaseDataProvider]:
        """Get data provider."""
        source = source or self._active_provider
        return self._providers.get(source) if source else None
    
    # ---------------------------------------------------------------------------
    # Subscription
    # ---------------------------------------------------------------------------
    
    def subscribe(
        self,
        symbols: List[str],
        source: Optional[DataSource] = None,
        bar_intervals: Optional[List[int]] = None
    ) -> None:
        """
        Subscribe to symbols.
        
        Args:
            symbols: Symbols to subscribe
            source: Data source (uses active if None)
            bar_intervals: Bar intervals in minutes to build
        """
        provider = self.get_provider(source)
        if not provider:
            raise ValueError("No active provider")
        
        provider.subscribe(symbols)
        
        # Setup bar builders
        bar_intervals = bar_intervals or [1, 5]
        for symbol in symbols:
            for interval in bar_intervals:
                if interval not in self._bar_builders[symbol]:
                    self._bar_builders[symbol][interval] = BarBuilder(symbol, interval)
        
        logger.info("Subscribed", symbols=symbols, intervals=bar_intervals)
    
    def unsubscribe(self, symbols: List[str], source: Optional[DataSource] = None) -> None:
        """Unsubscribe from symbols."""
        provider = self.get_provider(source)
        if provider:
            provider.unsubscribe(symbols)
        
        for symbol in symbols:
            self._bar_builders.pop(symbol, None)
            self._latest_ticks.pop(symbol, None)
            self._latest_bars.pop(symbol, None)
    
    # ---------------------------------------------------------------------------
    # Callbacks
    # ---------------------------------------------------------------------------
    
    def on_tick(self, callback: Callable[[TickData], None]) -> None:
        """Register tick callback."""
        self._tick_callbacks.append(callback)
    
    def on_bar(self, callback: Callable[[BarData], None], interval: int = 1) -> None:
        """
        Register bar callback.
        
        Args:
            callback: Bar callback function
            interval: Bar interval in minutes
        """
        self._bar_callbacks[interval].append(callback)
    
    def _on_tick(self, tick: TickData) -> None:
        """Internal tick handler."""
        symbol = tick.symbol
        
        # Cache latest tick
        self._latest_ticks[symbol] = tick
        
        # Emit to callbacks
        for callback in self._tick_callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.error("Tick callback error", error=str(e))
        
        # Build bars
        if symbol in self._bar_builders:
            for interval, builder in self._bar_builders[symbol].items():
                bar = builder.update(tick)
                if bar:
                    self._latest_bars[symbol][interval] = bar
                    
                    for callback in self._bar_callbacks.get(interval, []):
                        try:
                            callback(bar)
                        except Exception as e:
                            logger.error("Bar callback error", error=str(e))
                    
                    if self.event_engine:
                        self.event_engine.put(Event(DataEvent.BAR.value, bar))
    
    # ---------------------------------------------------------------------------
    # Control
    # ---------------------------------------------------------------------------
    
    def start(self) -> None:
        """Start all providers."""
        for source, provider in self._providers.items():
            if not provider.is_connected():
                provider.connect()
            
            if isinstance(provider, SimulationDataProvider):
                provider.start()
        
        self._running = True
        logger.info("Data manager started")
    
    def stop(self) -> None:
        """Stop all providers."""
        for provider in self._providers.values():
            if isinstance(provider, SimulationDataProvider):
                provider.stop()
            provider.disconnect()
        
        self._running = False
        logger.info("Data manager stopped")
    
    def is_running(self) -> bool:
        return self._running
    
    # ---------------------------------------------------------------------------
    # Data Access
    # ---------------------------------------------------------------------------
    
    def get_latest_tick(self, symbol: str) -> Optional[TickData]:
        """Get latest tick for symbol."""
        return self._latest_ticks.get(symbol)
    
    def get_latest_bar(self, symbol: str, interval: int = 1) -> Optional[BarData]:
        """Get latest bar for symbol."""
        return self._latest_bars.get(symbol, {}).get(interval)
    
    def get_current_bar(self, symbol: str, interval: int = 1) -> Optional[BarData]:
        """Get current incomplete bar."""
        builders = self._bar_builders.get(symbol, {})
        builder = builders.get(interval)
        return builder.get_current_bar() if builder else None
    
    def get_bars(self, symbol: str, interval: int = 1, count: int = 100) -> List[BarData]:
        """Get recent bars."""
        builders = self._bar_builders.get(symbol, {})
        builder = builders.get(interval)
        return builder.get_bars(count) if builder else []
    
    def get_all_latest_ticks(self) -> Dict[str, TickData]:
        """Get all latest ticks."""
        return self._latest_ticks.copy()
    
    def get_prices(self) -> Dict[str, float]:
        """Get all latest prices."""
        return {
            symbol: tick.last_price
            for symbol, tick in self._latest_ticks.items()
        }


# ---------------------------------------------------------------------------
# Signal Generator
# ---------------------------------------------------------------------------

class SignalType(str, Enum):
    """Signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """Trading signal."""
    symbol: str
    signal_type: SignalType
    timestamp: datetime
    price: float
    strength: float = 1.0  # 0-1
    reason: str = ""
    strategy: str = ""


class RealtimeSignalGenerator:
    """
    实时信号生成器
    
    基于实时数据流生成交易信号。
    
    Usage:
        >>> generator = RealtimeSignalGenerator(data_manager)
        >>> 
        >>> # 添加信号规则
        >>> generator.add_rule("ma_cross", ma_cross_rule)
        >>> 
        >>> # 注册信号回调
        >>> generator.on_signal(lambda s: print(f"Signal: {s}"))
        >>> 
        >>> # 启动
        >>> generator.start()
    """
    
    def __init__(self, data_manager: RealtimeDataManager):
        """Initialize signal generator."""
        self.data_manager = data_manager
        
        # Signal rules
        self._rules: Dict[str, Callable[[str, TickData, List[BarData]], Optional[Signal]]] = {}
        
        # Callbacks
        self._signal_callbacks: List[Callable[[Signal], None]] = []
        
        # State
        self._enabled = False
    
    def add_rule(
        self,
        name: str,
        rule: Callable[[str, TickData, List[BarData]], Optional[Signal]]
    ) -> None:
        """
        Add signal rule.
        
        Args:
            name: Rule name
            rule: Rule function (symbol, tick, bars) -> Optional[Signal]
        """
        self._rules[name] = rule
    
    def remove_rule(self, name: str) -> None:
        """Remove signal rule."""
        self._rules.pop(name, None)
    
    def on_signal(self, callback: Callable[[Signal], None]) -> None:
        """Register signal callback."""
        self._signal_callbacks.append(callback)
    
    def start(self) -> None:
        """Start signal generation."""
        self._enabled = True
        self.data_manager.on_tick(self._process_tick)
        logger.info("Signal generator started")
    
    def stop(self) -> None:
        """Stop signal generation."""
        self._enabled = False
    
    def _process_tick(self, tick: TickData) -> None:
        """Process tick and generate signals."""
        if not self._enabled:
            return
        
        symbol = tick.symbol
        bars = self.data_manager.get_bars(symbol, interval=1, count=100)
        
        for rule_name, rule in self._rules.items():
            try:
                signal = rule(symbol, tick, bars)
                if signal:
                    signal.strategy = rule_name
                    self._emit_signal(signal)
            except Exception as e:
                logger.error("Signal rule error", rule=rule_name, error=str(e))
    
    def _emit_signal(self, signal: Signal) -> None:
        """Emit signal to callbacks."""
        logger.info(
            "Signal generated",
            symbol=signal.symbol,
            type=signal.signal_type.value,
            price=signal.price,
            strategy=signal.strategy
        )
        
        for callback in self._signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error("Signal callback error", error=str(e))


# ---------------------------------------------------------------------------
# Built-in Signal Rules
# ---------------------------------------------------------------------------

def create_ma_cross_rule(fast_period: int = 5, slow_period: int = 20):
    """
    Create moving average crossover signal rule.
    
    Args:
        fast_period: Fast MA period
        slow_period: Slow MA period
    """
    def rule(symbol: str, tick: TickData, bars: List[BarData]) -> Optional[Signal]:
        if len(bars) < slow_period + 1:
            return None
        
        # Calculate MAs
        closes = [b.close for b in bars[-slow_period-1:]]
        fast_ma = sum(closes[-fast_period:]) / fast_period
        slow_ma = sum(closes[-slow_period:]) / slow_period
        
        prev_closes = closes[:-1]
        prev_fast_ma = sum(prev_closes[-fast_period:]) / fast_period
        prev_slow_ma = sum(prev_closes[-slow_period:]) / slow_period
        
        # Check crossover
        if prev_fast_ma <= prev_slow_ma and fast_ma > slow_ma:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                timestamp=tick.timestamp,
                price=tick.last_price,
                strength=min(1.0, (fast_ma - slow_ma) / slow_ma * 100),
                reason=f"MA{fast_period} crossed above MA{slow_period}"
            )
        elif prev_fast_ma >= prev_slow_ma and fast_ma < slow_ma:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                timestamp=tick.timestamp,
                price=tick.last_price,
                strength=min(1.0, (slow_ma - fast_ma) / slow_ma * 100),
                reason=f"MA{fast_period} crossed below MA{slow_period}"
            )
        
        return None
    
    return rule


def create_price_breakout_rule(lookback: int = 20):
    """
    Create price breakout signal rule.
    
    Args:
        lookback: Lookback period for high/low
    """
    def rule(symbol: str, tick: TickData, bars: List[BarData]) -> Optional[Signal]:
        if len(bars) < lookback + 1:
            return None
        
        recent_bars = bars[-lookback-1:-1]  # Exclude current bar
        high = max(b.high for b in recent_bars)
        low = min(b.low for b in recent_bars)
        
        price = tick.last_price
        
        if price > high:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                timestamp=tick.timestamp,
                price=price,
                strength=min(1.0, (price - high) / high * 100),
                reason=f"Breakout above {lookback}-bar high {high:.2f}"
            )
        elif price < low:
            return Signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                timestamp=tick.timestamp,
                price=price,
                strength=min(1.0, (low - price) / low * 100),
                reason=f"Breakdown below {lookback}-bar low {low:.2f}"
            )
        
        return None
    
    return rule


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Core classes
    'RealtimeDataManager',
    'RealtimeQuote',
    'BarBuilder',
    'MultiFreqBarChain',
    'StreamDispatcher',

    # Providers
    'BaseDataProvider',
    'SimulationDataProvider',
    'SinaDataProvider',
    'AKShareDataProvider',
    'WebSocketDataProvider',

    # Signal generation
    'RealtimeSignalGenerator',
    'Signal',
    'SignalType',

    # Signal rules
    'create_ma_cross_rule',
    'create_price_breakout_rule',

    # Enums
    'DataSource',
    'DataType',
    'DataEvent',
]


# ---------------------------------------------------------------------------
# V5.0-B-4: Multi-frequency bar chain
# ---------------------------------------------------------------------------

class MultiFreqBarChain:
    """Chain of BarBuilders that aggregate ticks into multiple frequencies.

    Example usage:
        chain = MultiFreqBarChain("600519.SH", [1, 5, 15, 60])
        chain.on_bar(1, lambda bar: print("1min bar", bar))
        chain.on_bar(5, lambda bar: print("5min bar", bar))
        for tick in tick_stream:
            chain.update(tick)
    """

    def __init__(self, symbol: str, intervals: Optional[List[int]] = None) -> None:
        self.symbol = symbol
        self.intervals = intervals or [1, 5, 15, 60]
        self._builders: Dict[int, BarBuilder] = {}
        self._callbacks: Dict[int, List[Callable]] = defaultdict(list)
        for iv in self.intervals:
            self._builders[iv] = BarBuilder(symbol, interval_minutes=iv)

    def on_bar(self, interval: int, callback: Callable[[BarData], None]) -> None:
        """Register a callback for a specific bar interval."""
        self._callbacks[interval].append(callback)

    def update(self, tick: TickData) -> Dict[int, Optional[BarData]]:
        """Feed a tick through all builders, fire callbacks for completed bars."""
        results: Dict[int, Optional[BarData]] = {}
        for iv, builder in self._builders.items():
            bar = builder.update(tick)
            results[iv] = bar
            if bar:
                for cb in self._callbacks.get(iv, []):
                    try:
                        cb(bar)
                    except Exception as e:
                        logger.error("bar_callback_error", interval=iv, error=str(e))
        return results

    @property
    def current_bars(self) -> Dict[int, Optional[BarData]]:
        """Get the current (incomplete) bar for each interval."""
        return {iv: b._current_bar for iv, b in self._builders.items()}

    def get_history(self, interval: int, limit: int = 100) -> List[BarData]:
        """Get completed bar history for a given interval."""
        builder = self._builders.get(interval)
        if not builder:
            return []
        return builder._bars[-limit:]


# ---------------------------------------------------------------------------
# V5.0-B-4: Stream dispatcher (pub/sub for market data)
# ---------------------------------------------------------------------------

class StreamDispatcher:
    """Pub/sub dispatcher for real-time market data streams.

    Decouples data producers (providers) from consumers (strategies, UI, storage).
    Supports topic-based routing: 'tick.{symbol}', 'bar.{interval}.{symbol}'.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._stats: Dict[str, int] = defaultdict(int)

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic pattern."""
        with self._lock:
            self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Unsubscribe from a topic."""
        with self._lock:
            subs = self._subscribers.get(topic, [])
            if callback in subs:
                subs.remove(callback)

    def publish(self, topic: str, data: Any) -> int:
        """Publish data to a topic and all matching subscribers.

        Returns:
            Number of subscribers notified.
        """
        with self._lock:
            direct = list(self._subscribers.get(topic, []))
            # Wildcard matching: 'tick.*' matches 'tick.600519.SH'
            wildcard_matches = []
            for pat, subs in self._subscribers.items():
                if pat.endswith("*") and topic.startswith(pat[:-1]):
                    wildcard_matches.extend(subs)

        count = 0
        for cb in direct + wildcard_matches:
            try:
                cb(data)
                count += 1
            except Exception as e:
                logger.error("dispatch_error", topic=topic, error=str(e))
        self._stats[topic] += 1
        return count

    def publish_tick(self, tick: TickData) -> int:
        """Convenience: publish a tick event."""
        return self.publish(f"tick.{tick.symbol}", tick)

    def publish_bar(self, bar: BarData, interval: int) -> int:
        """Convenience: publish a bar event."""
        return self.publish(f"bar.{interval}.{bar.symbol}", bar)

    @property
    def stats(self) -> Dict[str, int]:
        """Message counts per topic."""
        return dict(self._stats)

    @property
    def subscriber_count(self) -> int:
        """Total number of subscriptions."""
        with self._lock:
            return sum(len(s) for s in self._subscribers.values())

