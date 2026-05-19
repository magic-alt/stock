from __future__ import annotations

import pytest

from src.core.events import EventType
from src.data_sources.level2 import (
    Level2Unavailable,
    StubLevel2Provider,
    XtpLevel2Provider,
    create_level2_provider,
    publish_level2_snapshot,
)


_PAYLOAD = {
    "symbol": "600519.SH",
    "timestamp": "2024-01-02T09:30:00+00:00",
    "last_price": 1688.0,
    "total_volume": 123456.0,
    "bids": [[1687.9, 100], [1687.8, 200], [1688.0, 50]],
    "asks": [[1688.2, 80], [1688.1, 120], [1688.3, 90]],
    "trades": [{"price": 1688.0, "volume": 10, "side": "buy", "trade_id": "t1"}],
}


def test_stub_provider_parses_sorted_top_of_book():
    provider = StubLevel2Provider({"600519.SH": _PAYLOAD})
    snapshot = provider.get_snapshot("600519.SH")

    assert snapshot.symbol == "600519.SH"
    assert snapshot.best_bid.price == pytest.approx(1688.0)
    assert snapshot.best_ask.price == pytest.approx(1688.1)
    assert snapshot.trades[0].trade_id == "t1"
    assert snapshot.to_dict()["bids"][0] == {"price": 1688.0, "volume": 50.0}


def test_provider_limits_depth_to_ten_levels():
    payload = dict(_PAYLOAD)
    payload["bids"] = [[100 - i, i + 1] for i in range(20)]
    payload["asks"] = [[101 + i, i + 1] for i in range(20)]
    snapshot = StubLevel2Provider({"S": payload}).get_snapshot("S")

    assert len(snapshot.bids) == 10
    assert len(snapshot.asks) == 10


def test_sdk_provider_without_sdk_reports_unavailable():
    provider = XtpLevel2Provider()
    with pytest.raises(Level2Unavailable, match="SDK is not configured"):
        provider.get_snapshot("600519.SH")


def test_create_level2_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported Level2 provider"):
        create_level2_provider("unknown")


def test_publish_level2_snapshot_emits_snapshot_and_trade_events():
    class Recorder:
        def __init__(self):
            self.events = []

        def put(self, event):
            self.events.append(event)

    recorder = Recorder()
    snapshot = StubLevel2Provider({"600519.SH": _PAYLOAD}).get_snapshot("600519.SH")
    publish_level2_snapshot(recorder, snapshot)

    assert [event.type for event in recorder.events] == [EventType.LEVEL2_SNAPSHOT, EventType.LEVEL2_TRADE]
    assert recorder.events[0].data["symbol"] == "600519.SH"
