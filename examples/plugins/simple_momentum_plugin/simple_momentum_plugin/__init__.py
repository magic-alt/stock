"""Example V6 strategy plugin."""
from __future__ import annotations

from typing import Any, Mapping

from src.sdk import CONTRACT_VERSION, BaseStrategyPlugin, PluginManifest


class SimpleMomentumStrategy(BaseStrategyPlugin):
    """Minimal strategy plugin used by SDK conformance tests."""

    def generate_signals(self, data: Mapping[str, Any]) -> Mapping[str, float]:
        signals: dict[str, float] = {}
        for symbol, frame in data.items():
            try:
                close = frame["close"]
                first = float(close.iloc[0] if hasattr(close, "iloc") else close[0])
                last = float(close.iloc[-1] if hasattr(close, "iloc") else close[-1])
            except Exception:
                signals[symbol] = 0.0
                continue
            if first <= 0:
                signals[symbol] = 0.0
            else:
                momentum = (last - first) / first
                signals[symbol] = max(-1.0, min(1.0, momentum))
        return signals


MANIFEST = PluginManifest(
    id="examples.simple_momentum",
    name="Simple Momentum Strategy",
    version="0.1.0",
    kind="strategy",
    entry_point="simple_momentum_plugin:SimpleMomentumStrategy",
    contract_version=CONTRACT_VERSION,
    description="Example strategy plugin for the V6 SDK.",
    author="Quant Platform Team",
    capabilities=("daily", "cn_a_share"),
)


__all__ = ["MANIFEST", "SimpleMomentumStrategy"]
