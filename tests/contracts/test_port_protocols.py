"""Structural conformance checks for every V6 port Protocol.

The kernel intentionally uses ``typing.Protocol`` (runtime-checkable) so
adapters never need to inherit from the SDK. These tests pin that promise:
each port MUST work with ``isinstance()``, and an in-memory reference
implementation MUST satisfy every documented method without inheriting.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator, Iterable, Mapping, Optional, Sequence

from src.core.contracts import (
    AccountSnapshot,
    Bar,
    Fill,
    Instrument,
    Order,
    OrderBookSnapshot,
    OrderStatus,
    Position,
    RiskCheckResult,
    RiskDecision,
    Side,
    Signal,
    Tick,
)
from src.core.contracts.ports import (
    ALL_PORTS,
    AdmissionGatePort,
    AuditPort,
    BrokerGatewayPort,
    DataProviderPort,
    FillModelPort,
    MLAdapterPort,
    MessageBusPort,
    MetricsPort,
    OrderRouterPort,
    PortfolioReaderPort,
    RealtimeFeedPort,
    ReportPort,
    RiskRulePort,
    SchedulerPort,
    SlippageModelPort,
    StoragePort,
    TracerPort,
    VaultPort,
)


UTC = timezone.utc


# ---------------------------------------------------------------------------
# Port-level invariants
# ---------------------------------------------------------------------------


def test_every_port_is_runtime_checkable():
    """Each port must support ``isinstance`` — a non-Protocol port would raise."""
    for port in ALL_PORTS:
        # ``isinstance(object(), Protocol)`` raises TypeError if the Protocol is
        # not runtime-checkable; pass an empty object to trigger the check.
        try:
            isinstance(object(), port)
        except TypeError as exc:  # pragma: no cover - regression guard
            raise AssertionError(f"{port.__name__} is not runtime-checkable") from exc


def test_all_ports_unique():
    assert len(ALL_PORTS) == len(set(ALL_PORTS))


# ---------------------------------------------------------------------------
# Reference implementations: a single class per port, no inheritance.
# ---------------------------------------------------------------------------


class _MemDataProvider:
    def get_instrument(self, instrument_id: str) -> Optional[Instrument]:
        return None

    def get_bars(self, instrument_id: str, start: datetime, end: datetime, interval: str = "1d") -> Sequence[Bar]:
        return []

    def list_instruments(self, *, exchange: Optional[str] = None, asset_class: Optional[str] = None) -> Sequence[Instrument]:
        return []


class _MemRealtimeFeed:
    def subscribe(self, instrument_ids: Iterable[str]) -> None:
        return None

    def unsubscribe(self, instrument_ids: Iterable[str]) -> None:
        return None

    async def stream_ticks(self) -> AsyncIterator[Tick]:
        if False:  # pragma: no cover - generator stub
            yield  # type: ignore[unreachable]

    async def stream_books(self) -> AsyncIterator[OrderBookSnapshot]:
        if False:  # pragma: no cover - generator stub
            yield  # type: ignore[unreachable]


class _MemStorage:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], Any] = {}

    def put(self, namespace: str, key: str, value: Any) -> None:
        self._data[(namespace, key)] = value

    def get(self, namespace: str, key: str) -> Optional[Any]:
        return self._data.get((namespace, key))

    def delete(self, namespace: str, key: str) -> bool:
        return self._data.pop((namespace, key), None) is not None

    def list_keys(self, namespace: str, prefix: str = "") -> Sequence[str]:
        return [k for (ns, k) in self._data if ns == namespace and k.startswith(prefix)]


class _MemPortfolioReader:
    def get_account(self, account_id: str) -> Optional[AccountSnapshot]:
        return None

    def get_position(self, account_id: str, instrument_id: str) -> Optional[Position]:
        return None

    def list_open_orders(self, account_id: str) -> Sequence[Order]:
        return []

    def list_fills_since(self, account_id: str, since: datetime) -> Sequence[Fill]:
        return []


class _MemBroker:
    venue = "MEM"

    def submit(self, order: Order) -> Order:
        return order

    def cancel(self, client_order_id: str) -> bool:
        return True

    def query_order(self, client_order_id: str) -> Optional[Order]:
        return None


class _MemRouter:
    def route(self, order: Order, *, hints: Optional[Mapping[str, str]] = None) -> str:
        return "MEM"

    def list_venues(self) -> Sequence[str]:
        return ("MEM",)


class _MemFillModel:
    def fill_against_bar(self, order: Order, bar: Bar) -> Sequence[Fill]:
        return []

    def fill_against_book(self, order: Order, book: OrderBookSnapshot) -> Sequence[Fill]:
        return []


class _MemSlippage:
    def adjust(self, side: Side, reference_price: float, quantity: float) -> float:
        return reference_price


class _MemRiskRule:
    rule_id = "mem-noop"

    def check_signal(self, signal: Signal, *, account: AccountSnapshot) -> RiskCheckResult:
        return RiskCheckResult(decision=RiskDecision.APPROVED, rule_id=self.rule_id)

    def check_order(self, order: Order, *, account: AccountSnapshot) -> RiskCheckResult:
        return RiskCheckResult(decision=RiskDecision.APPROVED, rule_id=self.rule_id)


class _MemAdmission:
    def required_artifacts(self, target_stage: str) -> Sequence[str]:
        return ()

    def evaluate(self, strategy_id: str, target_stage: str, artifacts: dict) -> RiskCheckResult:
        return RiskCheckResult(decision=RiskDecision.APPROVED, rule_id="mem-admission")


class _MemMetrics:
    def incr(self, name: str, value: float = 1.0, *, tags: Optional[Mapping[str, str]] = None) -> None:
        return None

    def gauge(self, name: str, value: float, *, tags: Optional[Mapping[str, str]] = None) -> None:
        return None

    def timing(self, name: str, ms: float, *, tags: Optional[Mapping[str, str]] = None) -> None:
        return None


class _MemTracer:
    def start_span(self, name: str, *, attributes: Optional[Mapping[str, Any]] = None) -> Any:
        class _Span:
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *exc): return False
        return _Span()


class _MemAudit:
    def __init__(self) -> None:
        self._head: Optional[str] = None

    def append(self, actor: str, action: str, payload: Mapping[str, Any]) -> str:
        self._head = f"{actor}:{action}:{len(payload)}"
        return self._head

    def head(self) -> Optional[str]:
        return self._head


class _MemBus:
    def publish(self, topic: str, payload: Any, *, source: Optional[str] = None) -> int:
        return 0

    def subscribe(self, topic: str, handler) -> str:
        return "sub-0"

    def unsubscribe(self, subscription_id: str) -> bool:
        return True

    def close(self) -> None:
        return None


class _MemScheduler:
    def schedule_cron(self, expr: str, callback, *, job_id: Optional[str] = None) -> str:
        return job_id or "j1"

    def schedule_at(self, when: datetime, callback, *, job_id: Optional[str] = None) -> str:
        return job_id or "j1"

    def cancel(self, job_id: str) -> bool:
        return True

    def list_jobs(self) -> Sequence[str]:
        return ()


class _MemVault:
    def get_secret(self, name: str) -> Optional[str]:
        return None

    def set_secret(self, name: str, value: str) -> None:
        return None

    def delete_secret(self, name: str) -> bool:
        return False

    def list_secrets(self) -> Sequence[str]:
        return ()


class _MemMLAdapter:
    model_id = "mem-model"

    def predict(self, features: Mapping[str, Any]) -> float:
        return 0.0

    def batch_predict(self, batch: Sequence[Mapping[str, Any]]) -> Sequence[float]:
        return [0.0 for _ in batch]


class _MemReport:
    format = "html"

    def render(self, payload: Mapping[str, Any], output_dir: str) -> str:
        return f"{output_dir}/report.html"


# ---------------------------------------------------------------------------
# Conformance assertions
# ---------------------------------------------------------------------------


REFERENCE_IMPLS = [
    (_MemDataProvider(), DataProviderPort),
    (_MemRealtimeFeed(), RealtimeFeedPort),
    (_MemStorage(), StoragePort),
    (_MemPortfolioReader(), PortfolioReaderPort),
    (_MemBroker(), BrokerGatewayPort),
    (_MemRouter(), OrderRouterPort),
    (_MemFillModel(), FillModelPort),
    (_MemSlippage(), SlippageModelPort),
    (_MemRiskRule(), RiskRulePort),
    (_MemAdmission(), AdmissionGatePort),
    (_MemMetrics(), MetricsPort),
    (_MemTracer(), TracerPort),
    (_MemAudit(), AuditPort),
    (_MemBus(), MessageBusPort),
    (_MemScheduler(), SchedulerPort),
    (_MemVault(), VaultPort),
    (_MemMLAdapter(), MLAdapterPort),
    (_MemReport(), ReportPort),
]


def test_reference_implementations_satisfy_their_port():
    for impl, port in REFERENCE_IMPLS:
        assert isinstance(impl, port), f"{type(impl).__name__} does not conform to {port.__name__}"


def test_reference_impl_coverage_matches_all_ports():
    ports_under_test = {port for _, port in REFERENCE_IMPLS}
    assert ports_under_test == set(ALL_PORTS), (
        "REFERENCE_IMPLS must cover exactly the ports declared in ALL_PORTS"
    )


def test_storage_round_trip_via_protocol():
    impl: StoragePort = _MemStorage()
    impl.put("ns", "k1", {"v": 1})
    assert impl.get("ns", "k1") == {"v": 1}
    assert list(impl.list_keys("ns")) == ["k1"]
    assert impl.delete("ns", "k1") is True
    assert impl.get("ns", "k1") is None


def test_audit_chain_head_tracking():
    impl: AuditPort = _MemAudit()
    assert impl.head() is None
    h = impl.append("alice", "submit_order", {"order_id": "c1"})
    assert h == impl.head()


def test_realtime_feed_supports_async_iteration():
    impl: RealtimeFeedPort = _MemRealtimeFeed()
    impl.subscribe(["X"])
    async def _drain():
        async for _ in impl.stream_ticks():  # pragma: no cover - empty stream
            return False
        return True
    assert asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_drain())
