"""
Tests for V5.0-E: Extensibility & Ecosystem.

Covers:
- E-1: Plugin system (plugin.py)
- E-2: Message bus (message_bus.py)
- E-3: Repository pattern (repository.py)
- E-4: Strategy hot-loader (strategy_loader.py)
"""
import json
import time
import threading
import pytest
from pathlib import Path


# ===========================================================================
# E-1: Plugin system tests
# ===========================================================================

class TestPluginBase:
    """Test plugin base class."""

    def test_plugin_base_instantiation(self):
        from src.core.plugin import PluginBase
        p = PluginBase()
        assert p.version == "0.1.0"
        assert p.plugin_type == "strategy"

    def test_plugin_base_lifecycle(self):
        from src.core.plugin import PluginBase
        p = PluginBase()
        p.on_load()
        p.on_unload()

    def test_plugin_types_constant(self):
        from src.core.plugin import PLUGIN_TYPES
        assert "strategy" in PLUGIN_TYPES
        assert "datasource" in PLUGIN_TYPES
        assert "gateway" in PLUGIN_TYPES


class TestPluginManager:
    """Test plugin manager."""

    def test_load_plugin(self):
        from src.core.plugin import PluginManager, PluginBase

        class MyPlugin(PluginBase):
            name = "test_plugin"
            version = "1.0.0"
            plugin_type = "strategy"

        pm = PluginManager()
        assert pm.load("p1", MyPlugin) is True
        assert pm.is_loaded("p1") is True

    def test_load_duplicate_fails(self):
        from src.core.plugin import PluginManager, PluginBase

        class MyPlugin(PluginBase):
            name = "dup"

        pm = PluginManager()
        pm.load("p1", MyPlugin)
        assert pm.load("p1", MyPlugin) is False

    def test_unload_plugin(self):
        from src.core.plugin import PluginManager, PluginBase

        class MyPlugin(PluginBase):
            name = "removable"

        pm = PluginManager()
        pm.load("p1", MyPlugin)
        assert pm.unload("p1") is True
        assert pm.is_loaded("p1") is False

    def test_unload_nonexistent(self):
        from src.core.plugin import PluginManager
        pm = PluginManager()
        assert pm.unload("nope") is False

    def test_list_plugins(self):
        from src.core.plugin import PluginManager, PluginBase

        class A(PluginBase):
            name = "a"
            plugin_type = "strategy"

        class B(PluginBase):
            name = "b"
            plugin_type = "indicator"

        pm = PluginManager()
        pm.load("a", A)
        pm.load("b", B)
        plugins = pm.list_plugins()
        assert len(plugins) == 2

    def test_list_by_type(self):
        from src.core.plugin import PluginManager, PluginBase

        class A(PluginBase):
            name = "a"
            plugin_type = "strategy"

        class B(PluginBase):
            name = "b"
            plugin_type = "indicator"

        pm = PluginManager()
        pm.load("a", A)
        pm.load("b", B)
        assert len(pm.list_by_type("strategy")) == 1
        assert len(pm.list_by_type("indicator")) == 1
        assert len(pm.list_by_type("report")) == 0

    def test_get_plugin(self):
        from src.core.plugin import PluginManager, PluginBase

        class MyPlugin(PluginBase):
            name = "getter"

        pm = PluginManager()
        pm.load("p1", MyPlugin)
        assert pm.get("p1") is not None
        assert pm.get("nonexistent") is None

    def test_hooks(self):
        from src.core.plugin import PluginManager
        pm = PluginManager()
        results = []
        pm.register_hook("before_load", lambda **kw: results.append("fired"))
        pm.fire_hook("before_load")
        assert results == ["fired"]

    def test_hook_error_isolation(self):
        from src.core.plugin import PluginManager
        pm = PluginManager()

        def bad_handler(**kw):
            raise RuntimeError("boom")

        pm.register_hook("test", bad_handler)
        results = pm.fire_hook("test")
        assert results == [None]

    def test_clear(self):
        from src.core.plugin import PluginManager, PluginBase

        class MyPlugin(PluginBase):
            name = "clearable"

        pm = PluginManager()
        pm.load("p1", MyPlugin)
        pm.register_hook("x", lambda **kw: None)
        pm.clear()
        assert len(pm.list_plugins()) == 0

    def test_discover_directory(self, tmp_path):
        from src.core.plugin import PluginManager, PluginBase

        # Create a plugin file
        plugin_code = '''
from src.core.plugin import PluginBase

class SamplePlugin(PluginBase):
    name = "sample"
    version = "2.0.0"
    plugin_type = "indicator"
'''
        (tmp_path / "sample_plugin.py").write_text(plugin_code, encoding="utf-8")

        pm = PluginManager()
        infos = pm.discover([str(tmp_path)])
        assert len(infos) == 1
        assert infos[0].name == "sample"
        assert infos[0].version == "2.0.0"

    def test_discover_empty_dir(self, tmp_path):
        from src.core.plugin import PluginManager
        pm = PluginManager()
        infos = pm.discover([str(tmp_path)])
        assert infos == []

    def test_discover_nonexistent_dir(self):
        from src.core.plugin import PluginManager
        pm = PluginManager()
        infos = pm.discover(["/nonexistent/path"])
        assert infos == []


# ===========================================================================
# E-2: Message bus tests
# ===========================================================================

class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        from src.core.message_bus import Message
        m = Message(topic="tick.600519", payload={"price": 1850})
        assert m.topic == "tick.600519"
        assert m.payload["price"] == 1850
        assert m.timestamp > 0

    def test_message_to_dict(self):
        from src.core.message_bus import Message
        m = Message(topic="test", payload=42, source="engine")
        d = m.to_dict()
        assert d["topic"] == "test"
        assert d["payload"] == 42
        assert d["source"] == "engine"

    def test_message_to_json(self):
        from src.core.message_bus import Message
        m = Message(topic="test", payload={"a": 1})
        j = m.to_json()
        parsed = json.loads(j)
        assert parsed["topic"] == "test"

    def test_message_from_dict(self):
        from src.core.message_bus import Message
        m = Message.from_dict({"topic": "t", "payload": 1, "ts": 123, "source": "s"})
        assert m.topic == "t"
        assert m.timestamp == 123


class TestInProcessBackend:
    """Test in-process message bus."""

    def test_subscribe_publish(self):
        from src.core.message_bus import InProcessBackend
        backend = InProcessBackend()
        received = []
        backend.subscribe("test", lambda msg: received.append(msg.payload))
        backend.publish("test", "hello")
        assert received == ["hello"]

    def test_wildcard_subscribe(self):
        from src.core.message_bus import InProcessBackend
        backend = InProcessBackend()
        received = []
        backend.subscribe("tick.*", lambda msg: received.append(msg.topic))
        backend.publish("tick.600519", {})
        backend.publish("tick.000333", {})
        backend.publish("order.new", {})
        assert len(received) == 2

    def test_unsubscribe(self):
        from src.core.message_bus import InProcessBackend
        backend = InProcessBackend()
        received = []
        handler = lambda msg: received.append(1)
        backend.subscribe("topic", handler)
        backend.publish("topic", "a")
        assert len(received) == 1
        assert backend.unsubscribe("topic", handler) is True
        backend.publish("topic", "b")
        assert len(received) == 1

    def test_unsubscribe_nonexistent(self):
        from src.core.message_bus import InProcessBackend
        backend = InProcessBackend()
        assert backend.unsubscribe("nope") is False

    def test_stats(self):
        from src.core.message_bus import InProcessBackend
        backend = InProcessBackend()
        backend.subscribe("x", lambda msg: None)
        backend.publish("x", 1)
        backend.publish("x", 2)
        stats = backend.stats()
        assert stats["published"] == 2
        assert stats["delivered"] == 2

    def test_error_isolation(self):
        from src.core.message_bus import InProcessBackend
        backend = InProcessBackend()
        backend.subscribe("err", lambda msg: (_ for _ in ()).throw(RuntimeError("boom")))
        backend.publish("err", "data")
        assert backend.stats()["errors"] == 1

    def test_close(self):
        from src.core.message_bus import InProcessBackend
        backend = InProcessBackend()
        backend.subscribe("x", lambda msg: None)
        backend.close()
        assert backend.publish("x", 1) == 0


class TestMessageBusFacade:
    """Test MessageBus facade."""

    def test_default_mode(self):
        from src.core.message_bus import MessageBus
        bus = MessageBus()
        assert bus.mode == "inprocess"

    def test_publish_subscribe(self):
        from src.core.message_bus import MessageBus
        bus = MessageBus()
        received = []
        bus.subscribe("events.*", lambda msg: received.append(msg.payload))
        bus.publish("events.trade", {"symbol": "600519"})
        assert len(received) == 1
        bus.close()

    def test_stats(self):
        from src.core.message_bus import MessageBus
        bus = MessageBus()
        bus.subscribe("x", lambda msg: None)
        bus.publish("x", 1)
        assert bus.stats()["published"] == 1
        bus.close()

    def test_unsubscribe(self):
        from src.core.message_bus import MessageBus
        bus = MessageBus()
        handler = lambda msg: None
        bus.subscribe("t", handler)
        assert bus.unsubscribe("t", handler) is True
        bus.close()


# ===========================================================================
# E-3: Repository pattern tests
# ===========================================================================

class TestMemoryRepository:
    """Test in-memory repository."""

    def test_save_and_get(self):
        from src.core.repository import MemoryRepository
        repo = MemoryRepository()
        eid = repo.save({"id": "1", "name": "test"})
        assert eid == "1"
        assert repo.get("1")["name"] == "test"

    def test_auto_id(self):
        from src.core.repository import MemoryRepository
        repo = MemoryRepository()
        eid = repo.save({"name": "auto-id"})
        assert eid is not None
        assert repo.get(eid)["name"] == "auto-id"

    def test_list(self):
        from src.core.repository import MemoryRepository
        repo = MemoryRepository()
        repo.save({"id": "1", "type": "a"})
        repo.save({"id": "2", "type": "b"})
        repo.save({"id": "3", "type": "a"})
        assert len(repo.list()) == 3
        assert len(repo.list(filters={"type": "a"})) == 2

    def test_list_pagination(self):
        from src.core.repository import MemoryRepository
        repo = MemoryRepository()
        for i in range(10):
            repo.save({"id": str(i), "val": i})
        page = repo.list(limit=3, offset=2)
        assert len(page) == 3

    def test_delete(self):
        from src.core.repository import MemoryRepository
        repo = MemoryRepository()
        repo.save({"id": "1"})
        assert repo.delete("1") is True
        assert repo.get("1") is None
        assert repo.delete("1") is False

    def test_count(self):
        from src.core.repository import MemoryRepository
        repo = MemoryRepository()
        repo.save({"id": "1"})
        repo.save({"id": "2"})
        assert repo.count() == 2

    def test_clear(self):
        from src.core.repository import MemoryRepository
        repo = MemoryRepository()
        repo.save({"id": "1"})
        repo.clear()
        assert repo.count() == 0


class TestSQLiteRepository:
    """Test SQLite repository."""

    def test_save_and_get(self):
        from src.core.repository import SQLiteRepository
        repo = SQLiteRepository()
        repo.save({"id": "1", "name": "test"})
        assert repo.get("1")["name"] == "test"

    def test_list_and_filters(self):
        from src.core.repository import SQLiteRepository
        repo = SQLiteRepository()
        repo.save({"id": "1", "type": "a"})
        repo.save({"id": "2", "type": "b"})
        assert len(repo.list()) == 2
        assert len(repo.list(filters={"type": "a"})) == 1

    def test_delete(self):
        from src.core.repository import SQLiteRepository
        repo = SQLiteRepository()
        repo.save({"id": "1"})
        assert repo.delete("1") is True
        assert repo.get("1") is None

    def test_count(self):
        from src.core.repository import SQLiteRepository
        repo = SQLiteRepository()
        repo.save({"id": "1"})
        repo.save({"id": "2"})
        assert repo.count() == 2


class TestDuckDBRepository:
    """Test DuckDB repository."""

    def test_save_and_get(self):
        from src.core.repository import DuckDBRepository
        repo = DuckDBRepository()
        repo.save({"id": "1", "name": "test"})
        assert repo.get("1")["name"] == "test"

    def test_list(self):
        from src.core.repository import DuckDBRepository
        repo = DuckDBRepository()
        repo.save({"id": "1", "val": "a"})
        repo.save({"id": "2", "val": "b"})
        assert len(repo.list()) == 2

    def test_delete(self):
        from src.core.repository import DuckDBRepository
        repo = DuckDBRepository()
        repo.save({"id": "1"})
        assert repo.delete("1") is True
        assert repo.get("1") is None
        assert repo.delete("1") is False

    def test_upsert(self):
        from src.core.repository import DuckDBRepository
        repo = DuckDBRepository()
        repo.save({"id": "1", "val": "v1"})
        repo.save({"id": "1", "val": "v2"})
        assert repo.get("1")["val"] == "v2"
        assert repo.count() == 1


class TestCreateRepository:
    """Test repository factory."""

    def test_create_memory(self):
        from src.core.repository import create_repository, MemoryRepository
        repo = create_repository("memory")
        assert isinstance(repo, MemoryRepository)

    def test_create_sqlite(self):
        from src.core.repository import create_repository, SQLiteRepository
        repo = create_repository("sqlite")
        assert isinstance(repo, SQLiteRepository)

    def test_create_duckdb(self):
        from src.core.repository import create_repository, DuckDBRepository
        repo = create_repository("duckdb")
        assert isinstance(repo, DuckDBRepository)

    def test_unknown_backend(self):
        from src.core.repository import create_repository
        with pytest.raises(ValueError, match="Unknown repository backend"):
            create_repository("cassandra")


# ===========================================================================
# E-4: Strategy hot-loader tests
# ===========================================================================

class TestCodeSafety:
    """Test AST-based safety checker."""

    def test_safe_code(self):
        from src.core.strategy_loader import check_code_safety
        report = check_code_safety("import pandas\nx = 1 + 2")
        assert report.safe is True
        assert len(report.warnings) == 0

    def test_restricted_import(self):
        from src.core.strategy_loader import check_code_safety
        report = check_code_safety("import os\nimport subprocess")
        assert report.safe is False
        assert "os" in report.restricted_imports
        assert "subprocess" in report.restricted_imports

    def test_dangerous_call(self):
        from src.core.strategy_loader import check_code_safety
        report = check_code_safety("x = eval('1+1')")
        assert report.safe is False
        assert "eval" in report.dangerous_calls

    def test_syntax_error(self):
        from src.core.strategy_loader import check_code_safety
        report = check_code_safety("def foo(:\n  pass")
        assert report.safe is False

    def test_from_import_restricted(self):
        from src.core.strategy_loader import check_code_safety
        report = check_code_safety("from os.path import join")
        assert report.safe is False
        assert "os" in report.restricted_imports


class TestStrategyHotLoader:
    """Test strategy hot-loader."""

    def _make_strategy_file(self, tmp_path, name="my_strat", safe=True):
        code = f'''
class {name.title().replace("_", "")}:
    """Test strategy."""
    name = "{name}"

    def generate_signals(self, data):
        return {{}}
'''
        if not safe:
            code = "import os\n" + code
        path = tmp_path / f"{name}.py"
        path.write_text(code, encoding="utf-8")
        return str(path)

    def test_load_from_file(self, tmp_path):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader()
        path = self._make_strategy_file(tmp_path)
        cls = loader.load_from_file(path)
        assert cls is not None
        assert hasattr(cls, "generate_signals")

    def test_load_unsafe_file_blocked(self, tmp_path):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader(sandbox=True)
        path = self._make_strategy_file(tmp_path, safe=False)
        cls = loader.load_from_file(path)
        assert cls is None

    def test_load_without_sandbox(self, tmp_path):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader(sandbox=False)
        path = self._make_strategy_file(tmp_path, safe=False)
        cls = loader.load_from_file(path)
        assert cls is not None

    def test_load_nonexistent_file(self):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader()
        assert loader.load_from_file("/nonexistent/file.py") is None

    def test_load_from_string(self):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader()
        code = '''
class DynamicStrat:
    name = "dynamic"
    def generate_signals(self, data):
        return {}
'''
        cls = loader.load_from_string(code, name="dynamic")
        assert cls is not None
        instance = cls()
        assert instance.generate_signals({}) == {}

    def test_load_from_string_unsafe_blocked(self):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader(sandbox=True)
        code = '''import os
class Bad:
    def generate_signals(self, data):
        return {}
'''
        assert loader.load_from_string(code) is None

    def test_list_loaded(self, tmp_path):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader()
        self._make_strategy_file(tmp_path, name="strat_a")
        self._make_strategy_file(tmp_path, name="strat_b")
        loader.load_from_file(str(tmp_path / "strat_a.py"))
        loader.load_from_file(str(tmp_path / "strat_b.py"))
        loaded = loader.list_loaded()
        assert len(loaded) == 2

    def test_unload(self, tmp_path):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader()
        path = self._make_strategy_file(tmp_path)
        loader.load_from_file(path)
        assert loader.unload("my_strat") is True
        assert loader.unload("my_strat") is False

    def test_get_loaded_metadata(self, tmp_path):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader()
        path = self._make_strategy_file(tmp_path)
        loader.load_from_file(path)
        meta = loader.get_loaded("my_strat")
        assert meta is not None
        assert meta.name == "my_strat"
        assert meta.load_time > 0

    def test_reload(self, tmp_path):
        from src.core.strategy_loader import StrategyHotLoader
        loader = StrategyHotLoader()
        path = self._make_strategy_file(tmp_path)
        loader.load_from_file(path)
        cls = loader.reload("my_strat")
        assert cls is not None
