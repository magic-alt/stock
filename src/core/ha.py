"""
High availability / disaster recovery helpers.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional


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
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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
