"""
High availability / disaster recovery helpers.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class HealthCheckResult:
    component: str
    ok: bool
    details: Dict[str, Any]
    timestamp: str


class SnapshotStore:
    """Stores component snapshots on disk with retention."""

    def __init__(self, root: str = "./dr_snapshots", retention: int = 5) -> None:
        self.root = root
        self.retention = retention
        os.makedirs(root, exist_ok=True)

    def save(self, component: str, payload: Dict[str, Any]) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        comp_dir = os.path.join(self.root, component)
        os.makedirs(comp_dir, exist_ok=True)
        path = os.path.join(comp_dir, f"{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self._prune(comp_dir)
        return path

    def load_latest(self, component: str) -> Optional[Dict[str, Any]]:
        comp_dir = os.path.join(self.root, component)
        if not os.path.exists(comp_dir):
            return None
        files = sorted([f for f in os.listdir(comp_dir) if f.endswith(".json")])
        if not files:
            return None
        path = os.path.join(comp_dir, files[-1])
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _prune(self, comp_dir: str) -> None:
        files = sorted([f for f in os.listdir(comp_dir) if f.endswith(".json")])
        while len(files) > self.retention:
            old = files.pop(0)
            try:
                os.remove(os.path.join(comp_dir, old))
            except OSError:
                break


    def validate(self, component: str) -> bool:
        """Check that the latest snapshot for component is parseable and non-empty."""
        comp_dir = os.path.join(self.root, component)
        if not os.path.exists(comp_dir):
            return False
        files = sorted([f for f in os.listdir(comp_dir) if f.endswith(".json")])
        if not files:
            return False
        path = os.path.join(comp_dir, files[-1])
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return isinstance(data, dict) and len(data) > 0
        except (json.JSONDecodeError, OSError):
            return False

    def load_version(self, component: str, index: int) -> Optional[Dict[str, Any]]:
        """Load a specific snapshot version by index (0 = oldest)."""
        comp_dir = os.path.join(self.root, component)
        if not os.path.exists(comp_dir):
            return None
        files = sorted([f for f in os.listdir(comp_dir) if f.endswith(".json")])
        if index < 0 or index >= len(files):
            return None
        path = os.path.join(comp_dir, files[index])
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_snapshots(self, component: str) -> List[str]:
        """Return sorted list of snapshot file paths for a component."""
        comp_dir = os.path.join(self.root, component)
        if not os.path.exists(comp_dir):
            return []
        return [
            os.path.join(comp_dir, f)
            for f in sorted(os.listdir(comp_dir))
            if f.endswith(".json")
        ]


class ComponentRegistry:
    """Registry for health checks and snapshot/restore hooks."""

    def __init__(self, store: Optional[SnapshotStore] = None) -> None:
        self.store = store or SnapshotStore()
        self._components: Dict[str, Dict[str, Callable]] = {}

    def register(
        self,
        name: str,
        *,
        health_check: Callable[[], Dict[str, Any]],
        snapshot: Callable[[], Dict[str, Any]],
        restore: Callable[[Dict[str, Any]], None],
    ) -> None:
        self._components[name] = {
            "health_check": health_check,
            "snapshot": snapshot,
            "restore": restore,
        }

    def snapshot_all(self) -> Dict[str, str]:
        paths: Dict[str, str] = {}
        for name, hooks in self._components.items():
            payload = hooks["snapshot"]()
            path = self.store.save(name, payload)
            paths[name] = path
        return paths

    def health_check_all(self) -> Dict[str, HealthCheckResult]:
        results: Dict[str, HealthCheckResult] = {}
        for name, hooks in self._components.items():
            details = hooks["health_check"]()
            ok = bool(details.get("ok", True))
            results[name] = HealthCheckResult(
                component=name,
                ok=ok,
                details=details,
                timestamp=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            )
        return results

    def restore_if_needed(self) -> Dict[str, bool]:
        restored: Dict[str, bool] = {}
        for name, hooks in self._components.items():
            details = hooks["health_check"]()
            ok = bool(details.get("ok", True))
            if ok:
                restored[name] = False
                continue
            snapshot = self.store.load_latest(name)
            if snapshot is None:
                restored[name] = False
                continue
            hooks["restore"](snapshot)
            restored[name] = True
        return restored


def simple_health_check(ok: bool = True, **details: Any) -> Dict[str, Any]:
    return {"ok": ok, **details}


# ---------------------------------------------------------------------------
# V4.0-D: Failover & DR Drill
# ---------------------------------------------------------------------------


@dataclass
class DrillReport:
    """Result of a disaster recovery drill for one component."""
    component: str
    snapshot_ok: bool
    restore_ok: bool
    verify_ok: bool
    duration_ms: float


class FailoverManager:
    """Manage primary/standby failover using ComponentRegistry."""

    def __init__(
        self,
        registry: ComponentRegistry,
        primary_id: str,
        standby_id: str,
    ) -> None:
        self.registry = registry
        self.primary_id = primary_id
        self.standby_id = standby_id
        self._active = primary_id

    def status(self) -> Dict[str, Any]:
        health = self.registry.health_check_all()
        primary_ok = health[self.primary_id].ok if self.primary_id in health else False
        standby_ok = health[self.standby_id].ok if self.standby_id in health else False
        return {
            "active": self._active,
            "primary_id": self.primary_id,
            "standby_id": self.standby_id,
            "primary_healthy": primary_ok,
            "standby_healthy": standby_ok,
        }

    def trigger_failover(self) -> Dict[str, Any]:
        """Failover: snapshot primary, restore to standby, verify."""
        store = self.registry.store
        # Snapshot primary
        primary_hooks = self.registry._components.get(self.primary_id)
        standby_hooks = self.registry._components.get(self.standby_id)
        if not primary_hooks or not standby_hooks:
            raise RuntimeError("Primary or standby component not registered")

        payload = primary_hooks["snapshot"]()
        store.save(self.primary_id, payload)

        # Restore to standby
        standby_hooks["restore"](payload)

        # Verify standby health
        health = standby_hooks["health_check"]()
        if not health.get("ok", False):
            raise RuntimeError("Standby health check failed after failover")

        self._active = self.standby_id
        return {
            "status": "failover_complete",
            "active": self._active,
        }

    def failback(self) -> Dict[str, Any]:
        """Failback: snapshot standby, restore to primary, verify."""
        store = self.registry.store
        primary_hooks = self.registry._components.get(self.primary_id)
        standby_hooks = self.registry._components.get(self.standby_id)
        if not primary_hooks or not standby_hooks:
            raise RuntimeError("Primary or standby component not registered")

        payload = standby_hooks["snapshot"]()
        store.save(self.standby_id, payload)

        primary_hooks["restore"](payload)

        health = primary_hooks["health_check"]()
        if not health.get("ok", False):
            raise RuntimeError("Primary health check failed after failback")

        self._active = self.primary_id
        return {
            "status": "failback_complete",
            "active": self._active,
        }


class DrillRunner:
    """Automated DR drill: snapshot -> restore -> verify for each component."""

    def __init__(self, registry: ComponentRegistry) -> None:
        self.registry = registry

    def run_drill(self, components: Optional[List[str]] = None) -> List[DrillReport]:
        """Run snapshot-restore-verify drill for given components (or all)."""
        names = components or list(self.registry._components.keys())
        reports: List[DrillReport] = []

        for name in names:
            start = time.time()
            hooks = self.registry._components.get(name)
            if not hooks:
                reports.append(DrillReport(
                    component=name,
                    snapshot_ok=False,
                    restore_ok=False,
                    verify_ok=False,
                    duration_ms=0.0,
                ))
                continue

            # Snapshot
            snapshot_ok = True
            try:
                payload = hooks["snapshot"]()
                self.registry.store.save(name, payload)
            except Exception:
                snapshot_ok = False

            # Restore
            restore_ok = True
            if snapshot_ok:
                try:
                    latest = self.registry.store.load_latest(name)
                    if latest is not None:
                        hooks["restore"](latest)
                    else:
                        restore_ok = False
                except Exception:
                    restore_ok = False

            # Verify
            verify_ok = False
            if restore_ok:
                try:
                    health = hooks["health_check"]()
                    verify_ok = bool(health.get("ok", False))
                except Exception:
                    verify_ok = False

            duration_ms = (time.time() - start) * 1000.0
            reports.append(DrillReport(
                component=name,
                snapshot_ok=snapshot_ok,
                restore_ok=restore_ok,
                verify_ok=verify_ok,
                duration_ms=round(duration_ms, 2),
            ))

        return reports
