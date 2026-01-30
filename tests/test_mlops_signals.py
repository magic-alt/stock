from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.core.interfaces import AccountInfo, BarData, PositionInfo
from src.mlops.signals import SignalAction, SignalSchema, normalize_signal_output
from src.mlops.strategy_adapter import AISignalStrategy


class DummyContext:
    def __init__(self) -> None:
        self._positions: dict[str, PositionInfo] = {}
        self._orders: list[tuple[str, str, float | None]] = []
        self._account = AccountInfo()
        self._history = pd.DataFrame(
            {
                "open": [10, 11, 12],
                "high": [11, 12, 13],
                "low": [9, 10, 11],
                "close": [10, 11, 12],
                "volume": [100, 120, 140],
            }
        )

    @property
    def account(self) -> AccountInfo:
        return self._account

    @property
    def positions(self) -> dict[str, PositionInfo]:
        return self._positions

    def current_price(self, symbol: str, field: str = "close") -> float | None:
        return 12.0

    def get_bar(self, symbol: str) -> BarData | None:
        return None

    def history(self, symbol: str, fields: list[str], periods: int, frequency: str = "1d") -> pd.DataFrame:
        return self._history[fields].tail(periods)

    def buy(self, symbol: str, size: float | None = None, price: float | None = None, order_type: str = "market") -> str:
        self._orders.append(("buy", symbol, size))
        self._positions[symbol] = PositionInfo(symbol=symbol, size=(size or 1))
        return "order-buy"

    def sell(self, symbol: str, size: float | None = None, price: float | None = None, order_type: str = "market") -> str:
        self._orders.append(("sell", symbol, size))
        self._positions[symbol] = PositionInfo(symbol=symbol, size=0)
        return "order-sell"

    def cancel(self, order_id: str) -> bool:
        return True

    def log(self, message: str, level: str = "info") -> None:
        return None

    def get_datetime(self) -> datetime:
        return datetime.utcnow()


class DummyProvider:
    def __init__(self, output):
        self.output = output

    def predict(self, features: pd.DataFrame, symbol: str, timestamp: datetime):
        return self.output


def test_normalize_signal_output_scalar() -> None:
    ts = datetime(2024, 1, 1)
    out = normalize_signal_output(1, "TEST", ts)
    assert out[0].action == SignalAction.BUY
    out = normalize_signal_output(-1, "TEST", ts)
    assert out[0].action == SignalAction.SELL
    out = normalize_signal_output(0, "TEST", ts)
    assert out[0].action == SignalAction.HOLD


def test_normalize_signal_output_frame() -> None:
    ts = datetime(2024, 1, 1)
    df = pd.DataFrame({"signal": [0, 1], "score": [0.2, 0.8], "confidence": [0.1, 0.9]})
    out = normalize_signal_output(df, "TEST", ts)
    assert out[0].action == SignalAction.BUY
    assert out[0].confidence == 0.9


def test_ai_signal_strategy_executes_buy() -> None:
    ctx = DummyContext()
    bar = BarData(symbol="TEST", timestamp=datetime(2024, 1, 2), open=10, high=12, low=9, close=11, volume=100)
    provider = DummyProvider(SignalSchema(symbol="TEST", timestamp=bar.timestamp, action=SignalAction.BUY, size=5))
    strat = AISignalStrategy(provider)
    strat.on_init(ctx)
    strat.on_bar(ctx, bar)
    assert ctx.positions["TEST"].is_long
    assert ("buy", "TEST", 5) in ctx._orders
