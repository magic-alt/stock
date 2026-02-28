"""
Live Trading Runner

Connects BaseStrategy + RealtimeDataManager + TradingGateway.
Features: bar-driven execution, error recovery, periodic position sync, audit logging.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Event
from typing import Any, Callable, Dict, List, Optional
import time
import traceback

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
    errors: int = 0
    position_syncs: int = 0


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
    on_error: str = "skip",  # "skip" | "retry" | "halt"
    max_bar_retries: int = 2,
    position_sync_interval: float = 60.0,
    audit_logger=None,
) -> LiveRunResult:
    """Run a strategy in live mode with error recovery and position sync."""
    started_at = datetime.now().isoformat(timespec="seconds")
    bar_count = 0
    error_count = 0
    sync_count = 0

    ctx = LiveStrategyContext(
        gateway=gateway,
        data_map=warmup_data,
        symbols=symbols,
        history_limit=history_limit,
    )

    if auto_connect and not gateway.is_connected():
        gateway.connect()

    if audit_logger:
        audit_logger.log("live_runner.start", resource=f"strategy:{strategy.__class__.__name__}", details={"symbols": symbols})

    strategy.on_init(ctx)
    strategy.on_start(ctx)

    last_sync_time = time.monotonic()

    def _handle_bar(bar: BarData) -> None:
        nonlocal bar_count, error_count
        attempts = 0
        while attempts <= max_bar_retries:
            try:
                ctx.set_datetime(bar.timestamp)
                ctx.set_current_bar(bar.symbol, bar)
                ctx.append_bar(bar)
                strategy.on_bar(ctx, bar)
                if on_bar:
                    on_bar(bar.symbol, bar)
                bar_count += 1
                return
            except Exception as exc:
                attempts += 1
                error_count += 1
                logger.error(
                    "live_bar_error",
                    symbol=bar.symbol,
                    error=str(exc),
                    attempt=attempts,
                    traceback=traceback.format_exc(),
                )
                if audit_logger:
                    audit_logger.log(
                        "live_runner.bar_error",
                        resource=f"bar:{bar.symbol}",
                        details={"error": str(exc), "attempt": attempts},
                    )
                if on_error == "halt":
                    raise
                if on_error == "retry" and attempts <= max_bar_retries:
                    time.sleep(0.1 * attempts)
                    continue
                # on_error == "skip" or retries exhausted
                return

    def _sync_positions() -> None:
        nonlocal sync_count
        try:
            gateway_positions = gateway.get_positions()
            cached_positions = ctx.positions
            mismatch = False
            for sym in set(list(gateway_positions.keys()) + list(cached_positions.keys())):
                gp = gateway_positions.get(sym)
                cp = cached_positions.get(sym)
                g_size = gp.size if gp else 0
                c_size = cp.size if cp else 0
                if g_size != c_size:
                    mismatch = True
                    logger.warning(
                        "position_sync_mismatch",
                        symbol=sym,
                        gateway_size=g_size,
                        cached_size=c_size,
                    )
            sync_count += 1
            if mismatch and audit_logger:
                audit_logger.log("live_runner.position_mismatch", resource="positions", details={
                    "gateway": {s: p.size for s, p in gateway_positions.items()},
                    "cached": {s: p.size for s, p in cached_positions.items()},
                })
        except Exception as exc:
            logger.error("position_sync_error", error=str(exc))

    data_manager.on_bar(_handle_bar, interval=bar_interval)
    data_manager.subscribe(symbols, bar_intervals=[bar_interval])
    data_manager.start()

    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            # Periodic position sync
            now = time.monotonic()
            if now - last_sync_time >= position_sync_interval:
                _sync_positions()
                last_sync_time = now
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.warning("live_runner_interrupted")
    except Exception as exc:
        error_count += 1
        logger.error("live_runner_fatal", error=str(exc), traceback=traceback.format_exc())
        if audit_logger:
            audit_logger.log("live_runner.fatal", resource="runner", details={"error": str(exc)})
    finally:
        data_manager.stop()
        strategy.on_stop(ctx)
        if audit_logger:
            audit_logger.log("live_runner.stop", resource=f"strategy:{strategy.__class__.__name__}", details={
                "bars": bar_count, "errors": error_count, "syncs": sync_count
            })

    stopped_at = datetime.now().isoformat(timespec="seconds")
    return LiveRunResult(
        status="stopped",
        started_at=started_at,
        stopped_at=stopped_at,
        bars=bar_count,
        errors=error_count,
        position_syncs=sync_count,
    )


__all__ = [
    "LiveStrategyContext",
    "LiveRunResult",
    "run_live",
]
