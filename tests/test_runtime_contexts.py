"""Tests for V6 runtime contexts."""

from __future__ import annotations

from src.core.contracts import CONTRACT_VERSION, MetricsPort, TracerPort
from src.core.monitoring import MetricCollector, Tracer
from src.runtime import BacktestRuntime, LiveRuntime, RuntimeState, SandboxRuntime

def test_runtime_modes_declare_adapter_policy() -> None:
    backtest = BacktestRuntime()
    sandbox = SandboxRuntime()
    live = LiveRuntime()

    assert backtest.info()["contract_version"] == CONTRACT_VERSION
    assert backtest.info()["historical_data"] is True
    assert backtest.info()["simulated_execution"] is True
    assert sandbox.info()["realtime_data"] is True
    assert sandbox.info()["simulated_execution"] is True
    assert live.info()["realtime_data"] is True
    assert live.info()["live_execution"] is True

def test_runtime_boot_registers_shared_kernel_services() -> None:
    runtime = BacktestRuntime()

    runtime.boot()

    assert runtime.state is RuntimeState.BOOTED
    assert runtime.kernel.names() == ["runtime", "metrics", "tracer", "plugin_registry"]

def test_runtime_start_and_shutdown_drive_kernel_lifecycle() -> None:
    metrics = MetricCollector()
    tracer = Tracer()
    runtime = SandboxRuntime(metrics=metrics, tracer=tracer)

    runtime.start()

    assert runtime.state is RuntimeState.STARTED
    assert runtime.info()["components"] == [
        "runtime",
        "metrics",
        "tracer",
        "plugin_registry",
    ]
    exported = metrics.export()
    assert exported["counters"]["runtime_start_total.runtime.sandbox"] == 1.0
    assert any(
        span["name"] == "runtime.sandbox.start" for span in tracer.get_completed_spans()
    )

    runtime.shutdown()

    assert runtime.state is RuntimeState.SHUTDOWN

def test_observability_singletons_satisfy_ports() -> None:
    metrics = MetricCollector()
    tracer = Tracer()

    assert isinstance(metrics, MetricsPort)
    assert isinstance(tracer, TracerPort)

    metrics.incr("orders", tags={"runtime": "backtest"})
    metrics.gauge("queue_depth", 2, tags={"runtime": "backtest"})
    metrics.timing("latency_ms", 12.5, tags={"runtime": "backtest"})

    with tracer.start_span("port.span", attributes={"runtime": "backtest"}) as span:
        assert span.attributes["runtime"] == "backtest"

    exported = metrics.export()
    assert exported["counters"]["orders.runtime.backtest"] == 1.0
    assert exported["gauges"]["queue_depth.runtime.backtest"] == 2
    assert exported["histograms"]["latency_ms.runtime.backtest"]["count"] == 1
    assert tracer.get_completed_spans()[0]["attributes"]["runtime"] == "backtest"
