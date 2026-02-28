"""
Tests for DR failover, drill runner, and snapshot store extensions.
"""
import json
import os
import tempfile
import time

import pytest

from src.core.ha import (
    ComponentRegistry,
    DrillReport,
    DrillRunner,
    FailoverManager,
    SnapshotStore,
)


def _make_component(name, state=None):
    """Create a simple component with snapshot/restore/health_check hooks."""
    data = {"state": state or {"value": name}}

    def health_check():
        return {"ok": True, "name": name}

    def snapshot():
        return dict(data["state"])

    def restore(payload):
        data["state"] = payload

    return health_check, snapshot, restore, data


# ---------------------------------------------------------------------------
# SnapshotStore extensions
# ---------------------------------------------------------------------------


class TestSnapshotStoreExtensions:
    def test_validate_snapshot_integrity(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir, retention=5)
            store.save("comp", {"key": "value"})
            assert store.validate("comp") is True

    def test_validate_missing_component(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            assert store.validate("nonexistent") is False

    def test_validate_corrupt_snapshot_fails(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            store.save("comp", {"k": "v"})
            snapshots = store.list_snapshots("comp")
            # Corrupt the file
            with open(snapshots[-1], "w") as f:
                f.write("not valid json{{{")
            assert store.validate("comp") is False

    def test_list_snapshots(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir, retention=5)
            store.save("comp", {"v": 1})
            time.sleep(0.01)
            store.save("comp", {"v": 2})
            snapshots = store.list_snapshots("comp")
            assert len(snapshots) == 2
            assert all(s.endswith(".json") for s in snapshots)

    def test_load_version_by_index(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir, retention=5)
            store.save("comp", {"version": 1})
            time.sleep(0.01)
            store.save("comp", {"version": 2})
            oldest = store.load_version("comp", 0)
            newest = store.load_version("comp", 1)
            assert oldest["version"] == 1
            assert newest["version"] == 2

    def test_load_version_out_of_range(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            store.save("comp", {"v": 1})
            assert store.load_version("comp", 99) is None


# ---------------------------------------------------------------------------
# FailoverManager tests
# ---------------------------------------------------------------------------


class TestFailoverManager:
    def test_trigger_failover_success(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            hc_p, snap_p, restore_p, data_p = _make_component("primary")
            hc_s, snap_s, restore_s, data_s = _make_component("standby")

            registry.register("primary", health_check=hc_p, snapshot=snap_p, restore=restore_p)
            registry.register("standby", health_check=hc_s, snapshot=snap_s, restore=restore_s)

            fm = FailoverManager(registry, "primary", "standby")
            result = fm.trigger_failover()
            assert result["status"] == "failover_complete"
            assert result["active"] == "standby"
            assert data_s["state"] == {"value": "primary"}

    def test_failback_success(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            hc_p, snap_p, restore_p, data_p = _make_component("primary")
            hc_s, snap_s, restore_s, data_s = _make_component("standby")

            registry.register("primary", health_check=hc_p, snapshot=snap_p, restore=restore_p)
            registry.register("standby", health_check=hc_s, snapshot=snap_s, restore=restore_s)

            fm = FailoverManager(registry, "primary", "standby")
            fm.trigger_failover()
            result = fm.failback()
            assert result["status"] == "failback_complete"
            assert result["active"] == "primary"

    def test_failover_status(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            hc_p, snap_p, restore_p, _ = _make_component("primary")
            hc_s, snap_s, restore_s, _ = _make_component("standby")

            registry.register("primary", health_check=hc_p, snapshot=snap_p, restore=restore_p)
            registry.register("standby", health_check=hc_s, snapshot=snap_s, restore=restore_s)

            fm = FailoverManager(registry, "primary", "standby")
            status = fm.status()
            assert status["active"] == "primary"
            assert status["primary_healthy"] is True
            assert status["standby_healthy"] is True

    def test_failover_with_unhealthy_standby(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            hc_p, snap_p, restore_p, _ = _make_component("primary")

            def bad_health():
                return {"ok": False}

            registry.register("primary", health_check=hc_p, snapshot=snap_p, restore=restore_p)
            registry.register(
                "standby",
                health_check=bad_health,
                snapshot=lambda: {},
                restore=lambda p: None,
            )

            fm = FailoverManager(registry, "primary", "standby")
            with pytest.raises(RuntimeError, match="health check failed"):
                fm.trigger_failover()


# ---------------------------------------------------------------------------
# DrillRunner tests
# ---------------------------------------------------------------------------


class TestDrillRunner:
    def test_drill_success(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            hc, snap, restore, _ = _make_component("app")
            registry.register("app", health_check=hc, snapshot=snap, restore=restore)

            runner = DrillRunner(registry)
            reports = runner.run_drill()
            assert len(reports) == 1
            assert reports[0].component == "app"
            assert reports[0].snapshot_ok is True
            assert reports[0].restore_ok is True
            assert reports[0].verify_ok is True
            assert reports[0].duration_ms >= 0

    def test_drill_report_fields(self):
        report = DrillReport(
            component="test",
            snapshot_ok=True,
            restore_ok=True,
            verify_ok=False,
            duration_ms=12.5,
        )
        assert report.component == "test"
        assert report.verify_ok is False
        assert report.duration_ms == 12.5

    def test_drill_with_restore_failure(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            def bad_restore(_payload):
                raise RuntimeError("restore failed")

            registry.register(
                "broken",
                health_check=lambda: {"ok": True},
                snapshot=lambda: {"state": "data"},
                restore=bad_restore,
            )

            runner = DrillRunner(registry)
            reports = runner.run_drill()
            assert reports[0].snapshot_ok is True
            assert reports[0].restore_ok is False
            assert reports[0].verify_ok is False

    def test_drill_multiple_components(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            for name in ["oms", "risk", "data"]:
                hc, snap, restore, _ = _make_component(name)
                registry.register(name, health_check=hc, snapshot=snap, restore=restore)

            runner = DrillRunner(registry)
            reports = runner.run_drill()
            assert len(reports) == 3
            assert all(r.verify_ok for r in reports)

    def test_drill_unknown_component_fails(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            runner = DrillRunner(registry)
            reports = runner.run_drill(["nonexistent"])
            assert len(reports) == 1
            assert reports[0].snapshot_ok is False


# ---------------------------------------------------------------------------
# Full DR cycle integration
# ---------------------------------------------------------------------------


class TestDRIntegration:
    def test_full_dr_cycle(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir)
            registry = ComponentRegistry(store=store)

            hc_p, snap_p, restore_p, data_p = _make_component("primary", {"orders": [1, 2, 3]})
            hc_s, snap_s, restore_s, data_s = _make_component("standby", {"orders": []})

            registry.register("primary", health_check=hc_p, snapshot=snap_p, restore=restore_p)
            registry.register("standby", health_check=hc_s, snapshot=snap_s, restore=restore_s)

            fm = FailoverManager(registry, "primary", "standby")

            # 1. Snapshot all
            paths = registry.snapshot_all()
            assert "primary" in paths

            # 2. Failover
            fm.trigger_failover()
            assert fm._active == "standby"
            assert data_s["state"]["orders"] == [1, 2, 3]

            # 3. Verify
            health = registry.health_check_all()
            assert health["standby"].ok

            # 4. Failback
            fm.failback()
            assert fm._active == "primary"

    def test_snapshot_retention_with_dr(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            store = SnapshotStore(root=tmpdir, retention=2)
            for i in range(5):
                store.save("comp", {"v": i})
                time.sleep(0.01)
            snapshots = store.list_snapshots("comp")
            assert len(snapshots) <= 2
