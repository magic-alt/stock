"""V6 open-platform plugin registry.

The registry is intentionally additive to the older ``src.core.plugin``
manager. It speaks the V6 SDK contract surface: manifests, entry-point
groups, permission gates, and lightweight conformance checks for plugin
authors.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import yaml

from src.core.contracts import (
    AdmissionGatePort,
    AuditPort,
    BrokerGatewayPort,
    CONTRACT_VERSION,
    DataProviderPort,
    FillModelPort,
    MLAdapterPort,
    MessageBusPort,
    MetricsPort,
    OrderRouterPort,
    PluginManifest,
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


ENTRY_POINT_GROUPS: Dict[str, str] = {
    "strategy": "quant_platform.strategy",
    "indicator": "quant_platform.indicator",
    "factor": "quant_platform.factor",
    "data_provider": "quant_platform.data_provider",
    "realtime_feed": "quant_platform.realtime_feed",
    "gateway": "quant_platform.gateway",
    "storage": "quant_platform.storage",
    "risk_rule": "quant_platform.risk_rule",
    "fill_model": "quant_platform.fill_model",
    "report": "quant_platform.report",
    "scheduler": "quant_platform.scheduler",
    "ml_adapter": "quant_platform.ml_adapter",
    "messaging": "quant_platform.messaging",
    "admission_gate": "quant_platform.admission_gate",
}
"""Stable mapping from manifest kind to Python entry-point group."""


PORT_BY_KIND: Dict[str, Any] = {
    "admission_gate": AdmissionGatePort,
    "audit": AuditPort,
    "data_provider": DataProviderPort,
    "fill_model": FillModelPort,
    "gateway": BrokerGatewayPort,
    "ml_adapter": MLAdapterPort,
    "messaging": MessageBusPort,
    "metrics": MetricsPort,
    "order_router": OrderRouterPort,
    "portfolio_reader": PortfolioReaderPort,
    "realtime_feed": RealtimeFeedPort,
    "report": ReportPort,
    "risk_rule": RiskRulePort,
    "scheduler": SchedulerPort,
    "slippage_model": SlippageModelPort,
    "storage": StoragePort,
    "tracer": TracerPort,
    "vault": VaultPort,
}


SPI_METHODS_BY_KIND: Dict[str, tuple[str, ...]] = {
    "strategy": ("generate_signals",),
    "indicator": ("compute",),
    "factor": ("compute",),
}
"""Minimal SDK-level checks for plugin kinds that are not port Protocols yet."""


@dataclass(frozen=True, slots=True)
class PluginValidationResult:
    """Manifest validation outcome."""

    manifest: PluginManifest
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class PluginTestResult:
    """Full plugin conformance result used by ``quant-platform plugin test``."""

    manifest: PluginManifest
    loaded_object: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "plugin": self.manifest.to_dict(),
            "loaded_object": self.loaded_object,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class PluginRecord:
    """Loaded plugin record."""

    manifest: PluginManifest
    plugin: Any
    source: str = ""
    enabled: bool = True
    warnings: tuple[str, ...] = field(default_factory=tuple)


class PluginRegistry:
    """Discover, validate, load, and test V6 plugins."""

    def __init__(
        self,
        *,
        allowed_permissions: Optional[Iterable[str]] = None,
        contract_version: str = CONTRACT_VERSION,
    ) -> None:
        self.allowed_permissions = frozenset(allowed_permissions or ())
        self.contract_version = contract_version
        self._records: Dict[str, PluginRecord] = {}

    def validate_manifest(self, manifest: PluginManifest) -> PluginValidationResult:
        """Validate contract compatibility, permissions, and entry-point shape."""
        errors: list[str] = []
        warnings: list[str] = []

        if not manifest.is_contract_compatible(self.contract_version):
            errors.append(
                f"contract version {manifest.contract_version!r} is not compatible with {self.contract_version!r}"
            )
        unknown_capabilities = manifest.unknown_capabilities()
        if unknown_capabilities:
            warnings.append(f"unknown capabilities: {', '.join(sorted(unknown_capabilities))}")
        unknown_permissions = manifest.unknown_permissions()
        if unknown_permissions:
            errors.append(f"unknown permissions: {', '.join(sorted(unknown_permissions))}")
        denied = sorted(set(manifest.permissions) - self.allowed_permissions)
        if denied:
            errors.append(f"permissions not allowed: {', '.join(denied)}")
        if manifest.kind not in ENTRY_POINT_GROUPS:
            errors.append(f"unsupported plugin kind: {manifest.kind}")

        return PluginValidationResult(manifest=manifest, errors=tuple(errors), warnings=tuple(warnings))

    def register(self, manifest: PluginManifest, plugin: Any, *, source: str = "") -> PluginRecord:
        """Register an already constructed plugin object."""
        validation = self.validate_manifest(manifest)
        if not validation.ok:
            raise ValueError("; ".join(validation.errors))
        if manifest.id in self._records:
            raise ValueError(f"plugin {manifest.id!r} is already registered")
        record = PluginRecord(manifest=manifest, plugin=plugin, source=source, warnings=validation.warnings)
        self._records[manifest.id] = record
        return record

    def load(self, manifest: PluginManifest) -> PluginRecord:
        """Import, instantiate, validate, and register a plugin from its manifest."""
        plugin = instantiate_plugin(load_object(manifest.entry_point))
        test_result = self.test_plugin(manifest, plugin=plugin)
        if not test_result.ok:
            raise ValueError("; ".join(test_result.errors))
        if manifest.id in self._records:
            raise ValueError(f"plugin {manifest.id!r} is already registered")
        record = PluginRecord(
            manifest=manifest,
            plugin=plugin,
            source=manifest.entry_point,
            warnings=test_result.warnings,
        )
        self._records[manifest.id] = record
        return record

    def unload(self, plugin_id: str) -> bool:
        """Unload a registered plugin and call ``on_unload`` if available."""
        record = self._records.pop(plugin_id, None)
        if record is None:
            return False
        on_unload = getattr(record.plugin, "on_unload", None)
        if callable(on_unload):
            on_unload()
        return True

    def get(self, plugin_id: str) -> Optional[Any]:
        """Return a loaded plugin object by id."""
        record = self._records.get(plugin_id)
        return record.plugin if record else None

    def get_record(self, plugin_id: str) -> Optional[PluginRecord]:
        """Return the full plugin record by id."""
        return self._records.get(plugin_id)

    def list(self, *, kind: Optional[str] = None) -> list[PluginRecord]:
        """List loaded plugin records, optionally filtered by kind."""
        records = list(self._records.values())
        if kind is None:
            return records
        return [record for record in records if record.manifest.kind == kind]

    def discover_entry_points(self, kinds: Optional[Sequence[str]] = None) -> list[importlib.metadata.EntryPoint]:
        """Return installed entry points for the configured V6 groups."""
        selected_kinds = tuple(kinds) if kinds is not None else tuple(ENTRY_POINT_GROUPS.keys())
        groups = {ENTRY_POINT_GROUPS[kind] for kind in selected_kinds if kind in ENTRY_POINT_GROUPS}
        eps = importlib.metadata.entry_points()
        discovered: list[importlib.metadata.EntryPoint] = []
        for group in sorted(groups):
            try:
                discovered.extend(eps.select(group=group))
            except AttributeError:
                discovered.extend(ep for ep in eps.get(group, []))  # pragma: no cover - Python <3.10
        return discovered

    def test_plugin(self, manifest: PluginManifest, *, plugin: Optional[Any] = None) -> PluginTestResult:
        """Run manifest and SPI conformance checks for one plugin."""
        validation = self.validate_manifest(manifest)
        errors = list(validation.errors)
        warnings = list(validation.warnings)
        loaded_object = manifest.entry_point

        try:
            plugin_obj = plugin if plugin is not None else instantiate_plugin(load_object(manifest.entry_point))
            loaded_object = f"{plugin_obj.__class__.__module__}:{plugin_obj.__class__.__qualname__}"
        except Exception as exc:
            errors.append(f"failed to load entry point {manifest.entry_point!r}: {exc}")
            return PluginTestResult(
                manifest=manifest,
                loaded_object=loaded_object,
                errors=tuple(errors),
                warnings=tuple(warnings),
            )

        errors.extend(_check_kind_conformance(manifest.kind, plugin_obj))
        return PluginTestResult(
            manifest=manifest,
            loaded_object=loaded_object,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )


def instantiate_plugin(obj: Any) -> Any:
    """Instantiate classes and factories; return objects as-is."""
    if inspect.isclass(obj):
        return obj()
    if callable(obj) and not _looks_like_plugin_instance(obj):
        candidate = obj()
        if candidate is not None:
            return candidate
    return obj


def load_object(entry_point: str) -> Any:
    """Load ``module:attribute`` and return the referenced object."""
    module_name, sep, attr = entry_point.partition(":")
    if not sep or not module_name or not attr:
        raise ValueError("entry point must be of the form 'module.path:attribute'")
    module = importlib.import_module(module_name)
    obj: Any = module
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def load_manifest(source: str, *, search_path: Optional[str] = None) -> PluginManifest:
    """Load a manifest from JSON/YAML file or ``module:MANIFEST`` attribute."""
    if search_path:
        path = str(Path(search_path).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)

    candidate = Path(source)
    if candidate.exists():
        data = _read_manifest_file(candidate)
        return _manifest_from_mapping(data)

    obj = load_object(source)
    if isinstance(obj, PluginManifest):
        return obj
    if isinstance(obj, Mapping):
        return _manifest_from_mapping(obj)
    raise TypeError("manifest source must resolve to PluginManifest or mapping")


def _read_manifest_file(path: Path) -> Mapping[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if not isinstance(data, Mapping):
        raise ValueError(f"manifest file {path} must contain a mapping")
    return data


def _manifest_from_mapping(data: Mapping[str, Any]) -> PluginManifest:
    return PluginManifest(**dict(data))


def _looks_like_plugin_instance(obj: Any) -> bool:
    return any(hasattr(obj, name) for methods in SPI_METHODS_BY_KIND.values() for name in methods)


def _check_kind_conformance(kind: str, plugin: Any) -> list[str]:
    errors: list[str] = []
    port = PORT_BY_KIND.get(kind)
    if port is not None:
        if not isinstance(plugin, port):
            errors.append(f"plugin does not conform to {port.__name__}")
        return errors

    required_methods = SPI_METHODS_BY_KIND.get(kind, ())
    for method_name in required_methods:
        if not callable(getattr(plugin, method_name, None)):
            errors.append(f"plugin kind {kind!r} requires callable {method_name}()")
    return errors


__all__ = [
    "ENTRY_POINT_GROUPS",
    "PORT_BY_KIND",
    "SPI_METHODS_BY_KIND",
    "PluginRecord",
    "PluginRegistry",
    "PluginTestResult",
    "PluginValidationResult",
    "instantiate_plugin",
    "load_manifest",
    "load_object",
]
