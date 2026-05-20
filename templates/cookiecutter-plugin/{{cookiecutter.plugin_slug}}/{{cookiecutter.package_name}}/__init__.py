"""{{ cookiecutter.project_name }}."""
from __future__ import annotations

from typing import Any, Mapping

from src.sdk import CONTRACT_VERSION, BasePlugin, PluginManifest


class {{ cookiecutter.entry_class }}(BasePlugin):
    """Minimal plugin implementation for local SDK testing.

    Keep only the methods that match your selected plugin kind before
    publishing the package.
    """

    @property
    def venue(self) -> str:
        return "{{ cookiecutter.plugin_id }}"

    @property
    def rule_id(self) -> str:
        return "{{ cookiecutter.plugin_id }}"

    @property
    def format(self) -> str:
        return "json"

    def generate_signals(self, data: Mapping[str, Any]) -> Mapping[str, float]:
        return {symbol: 0.0 for symbol in data}

    def compute(self, data: Any, **params: Any) -> Any:
        return data

    def get_instrument(self, instrument_id: str) -> None:
        return None

    def get_bars(self, instrument_id: str, start: Any, end: Any, interval: str = "1d") -> list:
        return []

    def list_instruments(self, *, exchange: str | None = None, asset_class: str | None = None) -> list:
        return []

    def submit(self, order: Any) -> Any:
        return order

    def cancel(self, client_order_id: str) -> bool:
        return False

    def query_order(self, client_order_id: str) -> None:
        return None

    def check_signal(self, signal: Any, *, account: Any) -> Any:
        return None

    def check_order(self, order: Any, *, account: Any) -> Any:
        return None

    def fill_against_bar(self, order: Any, bar: Any) -> list:
        return []

    def fill_against_book(self, order: Any, book: Any) -> list:
        return []

    def render(self, payload: Mapping[str, Any], output_dir: str) -> str:
        return output_dir


MANIFEST = PluginManifest(
    id="{{ cookiecutter.plugin_id }}",
    name="{{ cookiecutter.plugin_name }}",
    version="{{ cookiecutter.version }}",
    kind="{{ cookiecutter.plugin_kind }}",
    entry_point="{{ cookiecutter.package_name }}:{{ cookiecutter.entry_class }}",
    contract_version=CONTRACT_VERSION,
    author="{{ cookiecutter.author }}",
)


__all__ = ["MANIFEST", "{{ cookiecutter.entry_class }}"]
