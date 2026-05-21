"""Thin runtime contexts that boot the kernel for each execution mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from src.core.contracts import CONTRACT_VERSION, MetricsPort, TracerPort
from src.core.kernel import PlatformKernel
from src.core.monitoring import (
    MetricCollector,
    Tracer,
    get_metric_collector,
    get_tracer,
)
from src.core.plugin_registry import PluginRegistry


class RuntimeMode(str, Enum):
    """Supported platform runtime contexts."""

    BACKTEST = "backtest"
    SANDBOX = "sandbox"
    LIVE = "live"


class RuntimeState(str, Enum):
    """Coarse runtime lifecycle state."""

    CREATED = "created"
    BOOTED = "booted"
    STARTED = "started"
    STOPPED = "stopped"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime wiring policy.

    The runtime classes are intentionally thin. They declare which adapter
    policy a host should use, boot shared observability/plugin services into
    the kernel, and leave concrete engine/adapters unchanged during V6.
    """

    mode: RuntimeMode
    historical_data: bool
    realtime_data: bool
    simulated_execution: bool
    live_execution: bool
    config: Mapping[str, Any] = field(default_factory=dict)


class BaseRuntime:
    """Base class for backtest, sandbox and live runtime contexts."""

    mode: RuntimeMode

    def __init__(
        self,
        *,
        kernel: Optional[PlatformKernel] = None,
        metrics: Optional[MetricsPort] = None,
        tracer: Optional[TracerPort] = None,
        plugin_registry: Optional[PluginRegistry] = None,
        config: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.kernel = kernel or PlatformKernel()
        self.metrics = metrics or get_metric_collector()
        self.tracer = tracer or get_tracer()
        self.plugin_registry = plugin_registry or PluginRegistry(
            contract_version=CONTRACT_VERSION
        )
        self.config = self._build_config(config or {})
        self.state = RuntimeState.CREATED

    def boot(self) -> "BaseRuntime":
        """Register shared runtime services in the kernel."""
        if self.state in {RuntimeState.BOOTED, RuntimeState.STARTED}:
            return self
        self._register_once(
            "runtime",
            self,
            start=self._on_start,
            stop=self._on_stop,
            tags=("runtime", self.mode.value),
        )
        self._register_once("metrics", self.metrics, tags=("observability", "metrics"))
        self._register_once("tracer", self.tracer, tags=("observability", "tracer"))
        self._register_once("plugin_registry", self.plugin_registry, tags=("plugins",))
        self.state = RuntimeState.BOOTED
        return self

    def start(self) -> "BaseRuntime":
        """Boot and start all registered kernel components."""
        self.boot()
        self.kernel.start_all()
        self.state = RuntimeState.STARTED
        return self

    def stop(self) -> "BaseRuntime":
        """Stop registered kernel components without disposing the kernel."""
        if self.state in {RuntimeState.CREATED, RuntimeState.SHUTDOWN}:
            return self
        self.kernel.stop_all()
        self.state = RuntimeState.STOPPED
        return self

    def shutdown(self) -> None:
        """Stop, dispose and close the underlying kernel."""
        if self.state == RuntimeState.SHUTDOWN:
            return
        self.kernel.shutdown()
        self.state = RuntimeState.SHUTDOWN

    def info(self) -> dict:
        """Return a JSON-friendly runtime summary."""
        return {
            "runtime": self.mode.value,
            "state": self.state.value,
            "contract_version": CONTRACT_VERSION,
            "historical_data": self.config.historical_data,
            "realtime_data": self.config.realtime_data,
            "simulated_execution": self.config.simulated_execution,
            "live_execution": self.config.live_execution,
            "components": self.kernel.names(),
        }

    def _build_config(self, config: Mapping[str, Any]) -> RuntimeConfig:
        raise NotImplementedError

    def _register_once(self, name: str, component: Any, **kwargs: Any) -> None:
        if not self.kernel.has(name):
            self.kernel.register(name, component, **kwargs)

    def _on_start(self) -> None:
        self.state = RuntimeState.STARTED
        if isinstance(self.metrics, MetricCollector):
            self.metrics.incr("runtime_start_total", tags={"runtime": self.mode.value})
        if isinstance(self.tracer, Tracer):
            with self.tracer.start_span(
                f"runtime.{self.mode.value}.start",
                attributes={"runtime": self.mode.value},
            ):
                pass

    def _on_stop(self) -> None:
        self.state = RuntimeState.STOPPED
        if isinstance(self.metrics, MetricCollector):
            self.metrics.incr("runtime_stop_total", tags={"runtime": self.mode.value})


class BacktestRuntime(BaseRuntime):
    """Historical-data runtime with simulated execution."""

    mode = RuntimeMode.BACKTEST

    def _build_config(self, config: Mapping[str, Any]) -> RuntimeConfig:
        return RuntimeConfig(
            mode=self.mode,
            historical_data=True,
            realtime_data=False,
            simulated_execution=True,
            live_execution=False,
            config=config,
        )


class SandboxRuntime(BaseRuntime):
    """Realtime/paper runtime with simulated execution."""

    mode = RuntimeMode.SANDBOX

    def _build_config(self, config: Mapping[str, Any]) -> RuntimeConfig:
        return RuntimeConfig(
            mode=self.mode,
            historical_data=False,
            realtime_data=True,
            simulated_execution=True,
            live_execution=False,
            config=config,
        )


class LiveRuntime(BaseRuntime):
    """Realtime runtime with live broker execution."""

    mode = RuntimeMode.LIVE

    def _build_config(self, config: Mapping[str, Any]) -> RuntimeConfig:
        return RuntimeConfig(
            mode=self.mode,
            historical_data=False,
            realtime_data=True,
            simulated_execution=False,
            live_execution=True,
            config=config,
        )


__all__ = [
    "BacktestRuntime",
    "BaseRuntime",
    "LiveRuntime",
    "RuntimeConfig",
    "RuntimeMode",
    "RuntimeState",
    "SandboxRuntime",
]
