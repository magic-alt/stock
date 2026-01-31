"""
Live Trading Runner

Connects BaseStrategy + RealtimeDataManager + TradingGateway.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Event
from typing import Any, Callable, Dict, List, Optional
import time

import pandas as pd

from src.core.interfaces import BarData, AccountInfo, PositionInfo, StrategyContext, OrderTypeEnum
from src.core.logger import get_logger
from src.core.realtime_data import RealtimeDataManager
from src.core.strategy_base import BaseStrategy
from src.core.trading_gateway import TradingGateway

logger = get_logger("live_runner")


@dataclass
class LiveRunResult:
    status: str
    started_at: str
    stopped_at: str
    bars: int


class LiveStrategyContext(StrategyContext):
    """Strategy context for live trading."""

    def __init__(
        self,
        gateway: TradingGateway,
        data_map: Optional[Dict[str, pd.DataFrame]] = None,
        symbols: Optional[List[str]] = None,
        history_limit: int = 2000,
    ) -> None:
        self.gateway = gateway
        self._data_map = data_map or {}
        self._symbols = symbols or list(self._data_map.keys())
        self._current_dt: Optional[datetime] = None
        self._current_bars: Dict[str, BarData] = {}
        self._history_limit = history_limit

    @property
    def account(self) -> AccountInfo:
        return self.gateway.get_account()

    @property
    def positions(self) -> Dict[str, PositionInfo]:
        return self.gateway.get_positions()

    def set_datetime(self, dt: datetime) -> None:
        self._current_dt = dt

    def set_current_bar(self, symbol: str, bar: BarData) -> None:
        self._current_bars[symbol] = bar

    def append_bar(self, bar: BarData) -> None:
        df = self._data_map.get(bar.symbol)
        row = {
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        if df is None or df.empty:
            df = pd.DataFrame([row], index=[bar.timestamp])
        else:
            df.loc[bar.timestamp] = row
            df = df.sort_index()
        if len(df) > self._history_limit:
            df = df.iloc[-self._history_limit :]
        self._data_map[bar.symbol] = df

    def current_price(self, symbol: str, field: str = "close") -> Optional[float]:
        bar = self._current_bars.get(symbol)
        if bar:
            return getattr(bar, field.lower(), None)
        df = self._data_map.get(symbol)
        if df is None or df.empty:
            return None
        try:
            return float(df.iloc[-1][field])
        except Exception:
            return None

    def get_bar(self, symbol: str) -> Optional[BarData]:
        return self._current_bars.get(symbol)

    def history(
        self,
        symbol: str,
        fields: List[str],
        periods: int,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        df = self._data_map.get(symbol)
        if df is None or df.empty:
            return pd.DataFrame()
        current_slice = df
        if self._current_dt:
            current_slice = df[df.index < self._current_dt]
        result_df = current_slice.tail(periods)
        available_cols = result_df.columns.tolist()
        selected_cols = []
        for field in fields:
            if field in available_cols:
                selected_cols.append(field)
            elif field.lower() in available_cols:
                selected_cols.append(field.lower())
            elif field.capitalize() in available_cols:
                selected_cols.append(field.capitalize())
        return result_df[selected_cols].copy() if selected_cols else result_df.copy()

    def buy(
        self,
        symbol: str,
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> str:
        if size is None:
            size = self._calculate_auto_size(symbol)
        if size <= 0:
            logger.warning("Invalid order size", symbol=symbol, size=size)
            return ""
        otype = OrderTypeEnum.MARKET if price is None else OrderTypeEnum(order_type)
        return self.gateway.buy(symbol, size, price=price, order_type=otype)

    def sell(
        self,
        symbol: str,
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market",
    ) -> str:
        if size is None:
            pos = self.positions.get(symbol)
            size = pos.size if pos else 0
        if size <= 0:
            logger.warning("No position to sell", symbol=symbol)
            return ""
        otype = OrderTypeEnum.MARKET if price is None else OrderTypeEnum(order_type)
        return self.gateway.sell(symbol, size, price=price, order_type=otype)

    def cancel(self, order_id: str) -> bool:
        return self.gateway.cancel(order_id)

    def log(self, message: str, level: str = "info") -> None:
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(message, dt=self._current_dt)

    def get_datetime(self) -> datetime:
        return self._current_dt or datetime.now()

    def _calculate_auto_size(self, symbol: str) -> float:
        account = self.account
        price = self.current_price(symbol)
        if not price or price <= 0:
            return 0
        target_value = account.available * 0.1
        size = int(target_value / price)
        size = (size // 100) * 100
        return max(0, size)


def run_live(
    strategy: BaseStrategy,
    data_manager: RealtimeDataManager,
    gateway: TradingGateway,
    symbols: List[str],
    *,
    bar_interval: int = 1,
    warmup_data: Optional[Dict[str, pd.DataFrame]] = None,
    history_limit: int = 2000,
    on_bar: Optional[Callable[[str, BarData], None]] = None,
    stop_event: Optional[Event] = None,
    poll_interval: float = 1.0,
    auto_connect: bool = True,
) -> LiveRunResult:
    """Run a strategy in live mode using realtime data manager."""
    started_at = datetime.now().isoformat(timespec="seconds")
    bar_count = 0

    ctx = LiveStrategyContext(
        gateway=gateway,
        data_map=warmup_data,
        symbols=symbols,
        history_limit=history_limit,
    )

    if auto_connect and not gateway.is_connected():
        gateway.connect()

    strategy.on_init(ctx)
    strategy.on_start(ctx)

    def _handle_bar(bar: BarData) -> None:
        nonlocal bar_count
        try:
            ctx.set_datetime(bar.timestamp)
            ctx.set_current_bar(bar.symbol, bar)
            ctx.append_bar(bar)
            strategy.on_bar(ctx, bar)
            if on_bar:
                on_bar(bar.symbol, bar)
            bar_count += 1
        except Exception as exc:
            logger.error("live_bar_error", symbol=bar.symbol, error=str(exc))

    data_manager.on_bar(_handle_bar, interval=bar_interval)
    data_manager.subscribe(symbols, bar_intervals=[bar_interval])
    data_manager.start()

    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.warning("live_runner_interrupted")
    finally:
        data_manager.stop()
        strategy.on_stop(ctx)

    stopped_at = datetime.now().isoformat(timespec="seconds")
    return LiveRunResult(
        status="stopped",
        started_at=started_at,
        stopped_at=stopped_at,
        bars=bar_count,
    )


__all__ = [
    "LiveStrategyContext",
    "LiveRunResult",
    "run_live",
]
