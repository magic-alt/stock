"""
Matching Engine Module

Core simulation matching engine for paper trading.
Supports A-share specific rules: T+1, price limits, suspension.
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Dict, Optional, Set
import pandas as pd

from src.core.events import EventEngine, Event, EventType
from .order import Order, Trade, OrderStatus, OrderType, OrderDirection
from .order_book import OrderBook
from .slippage import SlippageModel, FixedSlippage
from .execution_models import AlwaysFill, FillProbabilityModel, ExecutionDelayModel


class AShareRules:
    """
    A-share market rules for simulation.

    - T+1: shares bought today cannot be sold until next trading day.
    - Price limits: stocks cannot trade beyond +/-10% of previous close
      (ST stocks +/-5%).
    - Suspension: suspended symbols cannot be traded.
    - Lot size: orders must be multiples of 100 shares (except selling all).
    """

    def __init__(self, enabled: bool = True, st_symbols: Optional[Set[str]] = None):
        self.enabled = enabled
        self.st_symbols: Set[str] = st_symbols or set()
        # {symbol: set of date} — dates on which shares were bought
        self._buy_dates: Dict[str, Dict[date, float]] = {}
        # {symbol: prev_close}
        self._prev_close: Dict[str, float] = {}
        # suspended symbols
        self._suspended: Set[str] = set()

    def set_prev_close(self, symbol: str, price: float) -> None:
        if price > 0:
            self._prev_close[symbol] = price

    def set_prev_closes(self, prices: Dict[str, float]) -> None:
        for sym, px in prices.items():
            self.set_prev_close(sym, px)

    def mark_suspended(self, symbol: str) -> None:
        self._suspended.add(symbol)

    def clear_suspended(self, symbol: str) -> None:
        self._suspended.discard(symbol)

    def record_buy(self, symbol: str, qty: float, trade_date: Optional[date] = None) -> None:
        d = trade_date or date.today()
        self._buy_dates.setdefault(symbol, {})
        self._buy_dates[symbol][d] = self._buy_dates[symbol].get(d, 0) + qty

    def sellable_qty(self, symbol: str, position_qty: float, current_date: Optional[date] = None) -> float:
        """Return max qty sellable today (position minus T+1 locked shares)."""
        if not self.enabled:
            return position_qty
        d = current_date or date.today()
        locked = self._buy_dates.get(symbol, {}).get(d, 0)
        return max(0.0, position_qty - locked)

    def check_price_limit(self, symbol: str, price: float) -> Optional[str]:
        """Return rejection reason if price violates limit, else None."""
        if not self.enabled:
            return None
        prev = self._prev_close.get(symbol)
        if prev is None or prev <= 0:
            return None
        limit_pct = 0.05 if symbol in self.st_symbols else 0.10
        upper = round(prev * (1 + limit_pct), 2)
        lower = round(prev * (1 - limit_pct), 2)
        if price > upper:
            return f"Price {price:.2f} exceeds upper limit {upper:.2f} ({limit_pct*100:.0f}%)"
        if price < lower:
            return f"Price {price:.2f} below lower limit {lower:.2f} ({limit_pct*100:.0f}%)"
        return None

    def check_suspension(self, symbol: str) -> Optional[str]:
        if not self.enabled:
            return None
        if symbol in self._suspended:
            return f"Symbol {symbol} is suspended"
        return None

    def check_lot_size(self, qty: float, is_close_all: bool = False) -> Optional[str]:
        if not self.enabled:
            return None
        if is_close_all:
            return None
        if qty <= 0 or qty % 100 != 0:
            return f"Quantity {qty} must be a positive multiple of 100"
        return None

    def cleanup_expired(self, current_date: Optional[date] = None) -> None:
        """Remove buy records older than current_date (no longer locked)."""
        d = current_date or date.today()
        for sym in list(self._buy_dates):
            self._buy_dates[sym] = {dt: q for dt, q in self._buy_dates[sym].items() if dt >= d}
            if not self._buy_dates[sym]:
                del self._buy_dates[sym]


class MatchingEngine:
    """
    仿真撮合引擎
    
    核心功能：
    1. 订单生命周期管理（创建/挂单/成交/撤单）
    2. 市价单立即成交
    3. 限价单价格匹配成交
    4. 止损单触发转市价单
    5. 滑点模型应用
    
    Attributes:
        order_books: 订单簿字典 {symbol: OrderBook}
        slippage_model: 滑点模型
        event_engine: 事件引擎
        active_orders: 活跃订单索引 {order_id: Order}
        _trade_counter: 成交ID计数器
    """
    
    def __init__(
        self,
        slippage_model: Optional[SlippageModel] = None,
        fill_model: Optional[FillProbabilityModel] = None,
        delay_model: Optional[ExecutionDelayModel] = None,
        event_engine: Optional[EventEngine] = None,
        ashare_rules: Optional[AShareRules] = None,
    ):
        """
        初始化撮合引擎

        Args:
            slippage_model: 滑点模型（默认使用固定1跳滑点）
            event_engine: 事件引擎（可选）
            ashare_rules: A股规则引擎（可选，默认禁用）
        """
        self.order_books: Dict[str, OrderBook] = {}
        self.slippage_model = slippage_model or FixedSlippage(slippage_ticks=1, tick_size=0.01)
        self.event_engine = event_engine
        self.fill_model = fill_model or AlwaysFill()
        self.delay_model = delay_model
        self.ashare = ashare_rules or AShareRules(enabled=False)
        
        # 订单索引（快速查找）
        self.active_orders: Dict[str, Order] = {}
        
        # 待撮合的市价单队列（等待下一个 bar）
        self.pending_market_orders: Dict[str, list] = {}  # {symbol: [Order, ...]}
        # 延迟激活订单队列
        self.pending_delayed_orders: Dict[str, list] = {}  # {symbol: [{"order": Order, "remaining": int}]}
        
        # 成交ID计数器
        self._trade_counter = 0
    
    def submit_order(self, order: Order) -> None:
        """
        提交订单到撮合引擎

        根据订单类型分发：
        - 市价单：立即撮合
        - 限价单：加入订单簿
        - 止损单：加入止损队列

        A-share rules applied before routing (if enabled):
        - Suspension check
        - Price limit check (limit orders)
        - Lot size validation
        - T+1 sell restriction

        Args:
            order: 订单对象
        """
        # --- A-share pre-checks ---
        if self.ashare.enabled:
            reason = self.ashare.check_suspension(order.symbol)
            if reason:
                order.status = OrderStatus.REJECTED
                if self.event_engine:
                    self.event_engine.put(Event(EventType.ORDER, order))
                return

            if order.price and order.order_type == OrderType.LIMIT:
                reason = self.ashare.check_price_limit(order.symbol, order.price)
                if reason:
                    order.status = OrderStatus.REJECTED
                    if self.event_engine:
                        self.event_engine.put(Event(EventType.ORDER, order))
                    return

            lot_err = self.ashare.check_lot_size(order.quantity)
            if lot_err:
                order.status = OrderStatus.REJECTED
                if self.event_engine:
                    self.event_engine.put(Event(EventType.ORDER, order))
                return

        # 1. 初始化订单簿（如果不存在）
        if order.symbol not in self.order_books:
            self.order_books[order.symbol] = OrderBook(order.symbol)
        
        order_book = self.order_books[order.symbol]
        
        # 2. 延迟/立即激活
        delay = self.delay_model.delay_bars(order) if self.delay_model else 0
        if delay > 0:
            order.status = OrderStatus.PENDING
            if order.symbol not in self.pending_delayed_orders:
                self.pending_delayed_orders[order.symbol] = []
            self.pending_delayed_orders[order.symbol].append({"order": order, "remaining": delay})
            self.active_orders[order.order_id] = order
        else:
            self._activate_order(order)
        
        # 3. 发布订单事件
        if self.event_engine:
            self.event_engine.put(Event(EventType.ORDER, order))
    
    def cancel_order(self, order_id: str) -> bool:
        """
        撤单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否成功撤单
        """
        if order_id not in self.active_orders:
            return False
        
        order = self.active_orders[order_id]
        order_book = self.order_books.get(order.symbol)
        
        if not order_book:
            return False
        
        # 从订单簿移除
        if order.order_type == OrderType.LIMIT:
            order_book.remove_limit_order(order)
        elif order.order_type == OrderType.STOP:
            order_book.remove_stop_order(order_id)
        # 从延迟队列移除
        if order.symbol in self.pending_delayed_orders:
            self.pending_delayed_orders[order.symbol] = [
                item for item in self.pending_delayed_orders[order.symbol]
                if item["order"].order_id != order_id
            ]
        # 从市价队列移除
        if order.symbol in self.pending_market_orders:
            self.pending_market_orders[order.symbol] = [
                o for o in self.pending_market_orders[order.symbol]
                if o.order_id != order_id
            ]
        
        # 更新状态
        order.status = OrderStatus.CANCELLED
        del self.active_orders[order_id]
        
        # 发布撤单事件
        if self.event_engine:
            self.event_engine.put(Event(EventType.ORDER, order))
        
        return True
    
    def on_bar(self, symbol: str, bar: pd.Series) -> None:
        """
        行情更新时触发撮合
        
        处理流程：
        1. 撮合待处理的市价单
        2. 检查止损单触发
        3. 撮合限价单
        
        Args:
            symbol: 标的代码
            bar: K线数据（包含 open/high/low/close/volume）
        """
        if symbol not in self.order_books:
            return
        
        order_book = self.order_books[symbol]
        current_price = bar['close']
        
        # 0. 激活延迟订单
        if symbol in self.pending_delayed_orders:
            remaining_items = []
            for item in self.pending_delayed_orders[symbol]:
                item["remaining"] -= 1
                if item["remaining"] <= 0:
                    self._activate_order(item["order"])
                else:
                    remaining_items.append(item)
            if remaining_items:
                self.pending_delayed_orders[symbol] = remaining_items
            else:
                del self.pending_delayed_orders[symbol]

        # 1. 撮合待处理的市价单（使用当前价格）
        if symbol in self.pending_market_orders:
            market_orders = self.pending_market_orders.pop(symbol)
            for market_order in market_orders:
                self._match_market_order(market_order, market_price=current_price, bar=bar)
        
        # 2. 检查止损单触发
        triggered_stops = order_book.check_stop_trigger(current_price)
        for stop_order in triggered_stops:
            # 止损单触发后转为市价单
            self._match_market_order(stop_order, market_price=current_price, bar=bar)
        
        # 3. 撮合限价单（使用K线的高低价）
        self._match_limit_orders(symbol, bar)
    
    def _match_market_order(self, order: Order, market_price: Optional[float] = None, bar: Optional[pd.Series] = None) -> None:
        """
        撮合市价单（立即成交）
        
        Args:
            order: 市价订单
            market_price: 市场价格（如果为None，使用对手盘最优价或订单簿中间价）
        """
        order_book = self.order_books[order.symbol]
        
        # 获取市场价格
        if market_price is None:
            if order.direction == OrderDirection.BUY:
                # 优先使用卖一价
                market_price = order_book.get_best_ask()
                if market_price is None:
                    # 无卖单，使用买一价或中间价
                    market_price = order_book.get_best_bid() or order_book.get_mid_price()
            else:
                # 优先使用买一价
                market_price = order_book.get_best_bid()
                if market_price is None:
                    # 无买单，使用卖一价或中间价
                    market_price = order_book.get_best_ask() or order_book.get_mid_price()
        
        # 如果仍无法获取价格，拒绝订单
        if market_price is None or market_price <= 0:
            order.status = OrderStatus.REJECTED
            if self.event_engine:
                self.event_engine.put(Event(EventType.ORDER, order))
            return
        
        # 计算滑点后的实际成交价
        if self.fill_model and not self.fill_model.should_fill(order, bar):
            order.status = OrderStatus.PENDING
            if order.symbol not in self.pending_market_orders:
                self.pending_market_orders[order.symbol] = []
            self.pending_market_orders[order.symbol].append(order)
            self.active_orders[order.order_id] = order
            return

        fill_price = self.slippage_model.calculate_slippage(order, market_price)
        
        # 执行成交
        self._fill_order(order, fill_price, order.quantity)
        if order.order_id in self.active_orders:
            del self.active_orders[order.order_id]
    
    def _match_limit_orders(self, symbol: str, bar: pd.Series) -> None:
        """
        撮合限价单（价格匹配时成交）
        
        使用K线的高低价判断限价单是否可成交：
        - 买单：限价 >= 最低价时成交
        - 卖单：限价 <= 最高价时成交
        
        Args:
            symbol: 标的代码
            bar: K线数据
        """
        order_book = self.order_books[symbol]
        high_price = bar['high']
        low_price = bar['low']
        
        # 撮合买单（限价 >= 最低价）
        for bid_order in list(order_book.bids):
            if bid_order.price >= low_price:
                # 价格匹配，使用限价或更优价格成交
                fill_price = min(bid_order.price, high_price)
                if self.fill_model and not self.fill_model.should_fill(bid_order, bar):
                    continue
                self._fill_order(bid_order, fill_price, bid_order.remaining_qty)
                order_book.remove_limit_order(bid_order)
                if bid_order.order_id in self.active_orders:
                    del self.active_orders[bid_order.order_id]
        
        # 撮合卖单（限价 <= 最高价）
        for ask_order in list(order_book.asks):
            if ask_order.price <= high_price:
                # 价格匹配，使用限价或更优价格成交
                fill_price = max(ask_order.price, low_price)
                if self.fill_model and not self.fill_model.should_fill(ask_order, bar):
                    continue
                self._fill_order(ask_order, fill_price, ask_order.remaining_qty)
                order_book.remove_limit_order(ask_order)
                if ask_order.order_id in self.active_orders:
                    del self.active_orders[ask_order.order_id]
    
    def _fill_order(self, order: Order, fill_price: float, fill_qty: float) -> None:
        """
        执行成交
        
        Args:
            order: 订单对象
            fill_price: 成交价格
            fill_qty: 成交数量
        """
        # 生成成交记录
        self._trade_counter += 1
        trade = Trade(
            trade_id=f"T{self._trade_counter:08d}",
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=fill_qty,
            price=fill_price,
            timestamp=datetime.now(),
            strategy_id=order.strategy_id,
        )
        
        # 更新订单状态
        order.filled_qty += fill_qty
        if order.filled_qty >= order.quantity:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIAL
        
        # 更新平均成交价
        total_value = order.avg_fill_price * (order.filled_qty - fill_qty) + fill_price * fill_qty
        order.avg_fill_price = total_value / order.filled_qty
        
        # 发布成交事件
        if self.event_engine:
            self.event_engine.put(Event(EventType.TRADE, trade))
            self.event_engine.put(Event(EventType.ORDER, order))

        # A-share T+1: record buy for sell-lock
        if self.ashare.enabled and order.direction == OrderDirection.BUY:
            self.ashare.record_buy(order.symbol, fill_qty)
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        查询订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            订单对象，不存在返回None
        """
        return self.active_orders.get(order_id)
    
    def get_order_book(self, symbol: str) -> Optional[OrderBook]:
        """
        获取订单簿
        
        Args:
            symbol: 标的代码
            
        Returns:
            订单簿对象，不存在返回None
        """
        return self.order_books.get(symbol)
    
    def get_active_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """
        获取活跃订单列表
        
        Args:
            symbol: 标的代码（可选，默认返回所有）
            
        Returns:
            活跃订单列表
        """
        if symbol is None:
            return list(self.active_orders.values())
        else:
            return [o for o in self.active_orders.values() if o.symbol == symbol]
    
    def reset(self) -> None:
        """重置撮合引擎（清空所有订单和订单簿）"""
        self.order_books.clear()
        self.active_orders.clear()
        self._trade_counter = 0
        self.pending_market_orders.clear()
        self.pending_delayed_orders.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _activate_order(self, order: Order) -> None:
        """Activate order into book/queue after delay."""
        order_book = self.order_books[order.symbol]
        if order.order_type == OrderType.MARKET:
            order.status = OrderStatus.PENDING
            if order.symbol not in self.pending_market_orders:
                self.pending_market_orders[order.symbol] = []
            self.pending_market_orders[order.symbol].append(order)
            self.active_orders[order.order_id] = order
        elif order.order_type == OrderType.LIMIT:
            order_book.add_limit_order(order)
            self.active_orders[order.order_id] = order
        elif order.order_type == OrderType.STOP:
            order_book.add_stop_order(order)
            self.active_orders[order.order_id] = order
