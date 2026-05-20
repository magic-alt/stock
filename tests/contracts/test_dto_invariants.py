"""DTO invariants & round-trip tests for V6 contracts."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.contracts import (
    AccountSnapshot,
    AssetClass,
    Bar,
    BacktestResult,
    BookLevel,
    Fill,
    Instrument,
    Order,
    OrderBookSnapshot,
    OrderStatus,
    OrderType,
    Position,
    RiskCheckResult,
    RiskDecision,
    Side,
    Signal,
    Tick,
    TimeInForce,
)


UTC = timezone.utc


# ---------------------------------------------------------------------------
# Instrument
# ---------------------------------------------------------------------------


def test_instrument_basic():
    ins = Instrument(symbol="600519", exchange="XSHG", name="Moutai")
    assert ins.instrument_id == "600519.XSHG"
    assert ins.asset_class is AssetClass.EQUITY
    assert ins.lot_size == 100


def test_instrument_validation():
    with pytest.raises(ValueError):
        Instrument(symbol="", exchange="XSHG")
    with pytest.raises(ValueError):
        Instrument(symbol="600519", exchange="")
    with pytest.raises(ValueError):
        Instrument(symbol="600519", exchange="XSHG", lot_size=0)
    with pytest.raises(ValueError):
        Instrument(symbol="600519", exchange="XSHG", tick_size=Decimal("0"))


def test_instrument_frozen():
    ins = Instrument(symbol="600519", exchange="XSHG")
    with pytest.raises(FrozenInstanceError):
        ins.symbol = "000001"  # type: ignore[misc]


def test_instrument_to_dict_roundtrip_friendly():
    ins = Instrument(symbol="600519", exchange="XSHG", expiry=datetime(2030, 1, 1, tzinfo=UTC))
    d = ins.to_dict()
    assert d["symbol"] == "600519"
    assert d["asset_class"] == "equity"
    assert d["expiry"].startswith("2030-01-01")


# ---------------------------------------------------------------------------
# Bar / Tick / OrderBook
# ---------------------------------------------------------------------------


def _ts(year: int = 2024, month: int = 1, day: int = 2) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_bar_valid_ohlc():
    bar = Bar(
        instrument_id="600519.XSHG",
        ts=_ts(),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("95"),
        close=Decimal("105"),
        volume=Decimal("1000"),
    )
    assert bar.close == Decimal("105")
    assert bar.interval == "1d"


def test_bar_rejects_invalid_ohlc():
    with pytest.raises(ValueError):
        Bar(instrument_id="X", ts=_ts(), open=Decimal("100"), high=Decimal("90"),
            low=Decimal("95"), close=Decimal("92"), volume=Decimal("1"))
    with pytest.raises(ValueError):
        Bar(instrument_id="X", ts=_ts(), open=Decimal("200"), high=Decimal("110"),
            low=Decimal("95"), close=Decimal("100"), volume=Decimal("1"))
    with pytest.raises(ValueError):
        Bar(instrument_id="X", ts=_ts(), open=Decimal("100"), high=Decimal("110"),
            low=Decimal("95"), close=Decimal("105"), volume=Decimal("-1"))


def test_bar_rejects_naive_datetime():
    with pytest.raises(ValueError):
        Bar(instrument_id="X", ts=datetime(2024, 1, 2), open=Decimal("1"),
            high=Decimal("1"), low=Decimal("1"), close=Decimal("1"), volume=Decimal("0"))


def test_tick_valid():
    t = Tick(instrument_id="X", ts=_ts(), price=Decimal("10"), volume=Decimal("100"),
             bid=Decimal("9.99"), ask=Decimal("10.01"))
    assert t.price == Decimal("10")


def test_tick_rejects_negative():
    with pytest.raises(ValueError):
        Tick(instrument_id="X", ts=_ts(), price=Decimal("-1"), volume=Decimal("0"))


def test_order_book_sorting_enforced():
    bids = (BookLevel(price=Decimal("10"), size=Decimal("100")),
            BookLevel(price=Decimal("9"), size=Decimal("50")))
    asks = (BookLevel(price=Decimal("11"), size=Decimal("100")),
            BookLevel(price=Decimal("12"), size=Decimal("50")))
    snap = OrderBookSnapshot(instrument_id="X", ts=_ts(), bids=bids, asks=asks)
    assert snap.bids[0].price == Decimal("10")

    with pytest.raises(ValueError):
        OrderBookSnapshot(
            instrument_id="X", ts=_ts(),
            bids=(BookLevel(price=Decimal("9"), size=Decimal("1")),
                  BookLevel(price=Decimal("10"), size=Decimal("1"))),
        )
    with pytest.raises(ValueError):
        OrderBookSnapshot(
            instrument_id="X", ts=_ts(),
            asks=(BookLevel(price=Decimal("12"), size=Decimal("1")),
                  BookLevel(price=Decimal("11"), size=Decimal("1"))),
        )


# ---------------------------------------------------------------------------
# Order / Fill
# ---------------------------------------------------------------------------


def test_market_order_basic():
    o = Order(client_order_id="c1", instrument_id="X", side=Side.BUY,
              quantity=Decimal("100"))
    assert o.is_active
    assert o.remaining_quantity == Decimal("100")
    assert o.status is OrderStatus.PENDING


def test_limit_order_requires_price():
    with pytest.raises(ValueError):
        Order(client_order_id="c1", instrument_id="X", side=Side.BUY,
              quantity=Decimal("100"), order_type=OrderType.LIMIT)
    o = Order(client_order_id="c1", instrument_id="X", side=Side.BUY,
              quantity=Decimal("100"), order_type=OrderType.LIMIT,
              limit_price=Decimal("9.5"))
    assert o.limit_price == Decimal("9.5")


def test_stop_limit_requires_both_prices():
    with pytest.raises(ValueError):
        Order(client_order_id="c1", instrument_id="X", side=Side.BUY,
              quantity=Decimal("100"), order_type=OrderType.STOP_LIMIT,
              limit_price=Decimal("10"))
    with pytest.raises(ValueError):
        Order(client_order_id="c1", instrument_id="X", side=Side.BUY,
              quantity=Decimal("100"), order_type=OrderType.STOP_LIMIT,
              stop_price=Decimal("10"))


def test_order_overfill_rejected():
    with pytest.raises(ValueError):
        Order(client_order_id="c1", instrument_id="X", side=Side.BUY,
              quantity=Decimal("100"), filled_quantity=Decimal("101"))


def test_order_inactive_when_terminal():
    o = Order(client_order_id="c1", instrument_id="X", side=Side.BUY,
              quantity=Decimal("100"), status=OrderStatus.FILLED,
              filled_quantity=Decimal("100"))
    assert not o.is_active


def test_order_time_in_force_default():
    o = Order(client_order_id="c1", instrument_id="X", side=Side.BUY,
              quantity=Decimal("100"))
    assert o.time_in_force is TimeInForce.DAY


def test_fill_validation():
    Fill(fill_id="f1", client_order_id="c1", instrument_id="X",
         side=Side.BUY, quantity=Decimal("10"), price=Decimal("9.5"), ts=_ts())
    with pytest.raises(ValueError):
        Fill(fill_id="f1", client_order_id="c1", instrument_id="X",
             side=Side.BUY, quantity=Decimal("0"), price=Decimal("9.5"), ts=_ts())
    with pytest.raises(ValueError):
        Fill(fill_id="f1", client_order_id="c1", instrument_id="X",
             side=Side.BUY, quantity=Decimal("1"), price=Decimal("9.5"), ts=_ts(),
             commission=Decimal("-0.1"))


# ---------------------------------------------------------------------------
# Position / Account
# ---------------------------------------------------------------------------


def test_position_valid():
    p = Position(account_id="a1", instrument_id="X",
                 quantity=Decimal("100"), avg_cost=Decimal("9.5"))
    assert p.quantity == Decimal("100")


def test_position_rejects_negative_cost():
    with pytest.raises(ValueError):
        Position(account_id="a1", instrument_id="X",
                 quantity=Decimal("100"), avg_cost=Decimal("-1"))


def test_account_snapshot_valid():
    pos = Position(account_id="a1", instrument_id="X",
                   quantity=Decimal("100"), avg_cost=Decimal("9.5"))
    snap = AccountSnapshot(
        account_id="a1", ts=_ts(), cash=Decimal("100000"),
        equity=Decimal("100950"), buying_power=Decimal("100000"),
        positions=(pos,),
    )
    assert snap.positions[0].quantity == Decimal("100")
    assert snap.currency == "CNY"


def test_account_snapshot_rejects_negative():
    with pytest.raises(ValueError):
        AccountSnapshot(account_id="a1", ts=_ts(), cash=Decimal("0"),
                        equity=Decimal("-1"), buying_power=Decimal("0"))


# ---------------------------------------------------------------------------
# Signal / Risk / Backtest
# ---------------------------------------------------------------------------


def test_signal_strength_bounds():
    Signal(strategy_id="s1", instrument_id="X", side=Side.BUY, strength=1.0)
    Signal(strategy_id="s1", instrument_id="X", side=Side.SELL, strength=-1.0)
    with pytest.raises(ValueError):
        Signal(strategy_id="s1", instrument_id="X", side=Side.BUY, strength=1.5)
    with pytest.raises(ValueError):
        Signal(strategy_id="s1", instrument_id="X", side=Side.BUY, strength=-1.5)


def test_risk_check_result_decision_helper():
    approved = RiskCheckResult(decision=RiskDecision.APPROVED, rule_id="r1")
    rejected = RiskCheckResult(decision=RiskDecision.REJECTED, rule_id="r1", reason="too big")
    assert approved.approved
    assert not rejected.approved


def test_backtest_result_total_return():
    r = BacktestResult(
        strategy_id="s1",
        start=_ts(2024, 1, 1),
        end=_ts(2024, 12, 31),
        initial_capital=Decimal("100000"),
        final_equity=Decimal("120000"),
        contract_version="0.1.0",
    )
    assert r.total_return == Decimal("0.2")


def test_backtest_result_rejects_end_before_start():
    with pytest.raises(ValueError):
        BacktestResult(strategy_id="s1", start=_ts(2024, 12, 31),
                       end=_ts(2024, 1, 1), initial_capital=Decimal("1"),
                       final_equity=Decimal("1"))


# ---------------------------------------------------------------------------
# to_dict round-trips
# ---------------------------------------------------------------------------


def test_to_dict_is_json_friendly():
    """Every DTO's to_dict output must contain only JSON-friendly leaves."""
    import json

    bar = Bar(instrument_id="X", ts=_ts(), open=Decimal("1"), high=Decimal("2"),
              low=Decimal("1"), close=Decimal("1.5"), volume=Decimal("10"))
    json.dumps(bar.to_dict())

    order = Order(client_order_id="c", instrument_id="X", side=Side.BUY,
                  quantity=Decimal("1"))
    json.dumps(order.to_dict())

    snap = AccountSnapshot(account_id="a", ts=_ts(), cash=Decimal("0"),
                           equity=Decimal("0"), buying_power=Decimal("0"))
    json.dumps(snap.to_dict())
