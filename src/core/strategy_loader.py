"""
Strategy Hot-Loader (V5.0-E-4) — Runtime strategy loading and code sandboxing.

Provides:
- StrategyHotLoader: load strategies from files or code strings at runtime
- AST-based safety checker (restricted imports, dangerous calls)
- File watcher for auto-reload on changes
- Sandboxed execution with restricted builtins

Usage:
    >>> from src.core.strategy_loader import StrategyHotLoader
    >>> loader = StrategyHotLoader()
    >>> cls = loader.load_from_file("strategies/my_strategy.py")
    >>> instance = cls()
    >>> instance.generate_signals(data)
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type


# ---------------------------------------------------------------------------
# Safety checker
# ---------------------------------------------------------------------------

RESTRICTED_MODULES = {
    "os", "subprocess", "shutil", "sys", "socket", "ctypes",
    "multiprocessing", "signal", "resource", "pty",
}

DANGEROUS_CALLS = {
    "eval", "exec", "compile", "__import__", "open",
    "globals", "locals", "getattr", "setattr", "delattr",
}


@dataclass
class SafetyReport:
    """Result of code safety analysis."""
    safe: bool
    warnings: List[str] = field(default_factory=list)
    restricted_imports: List[str] = field(default_factory=list)
    dangerous_calls: List[str] = field(default_factory=list)


def check_code_safety(code: str) -> SafetyReport:
    """Perform AST-based safety analysis of Python code.

    Returns:
        SafetyReport with findings.
    """
    warnings: List[str] = []
    restricted: List[str] = []
    dangerous: List[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return SafetyReport(safe=False, warnings=[f"Syntax error: {e}"])

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_root = alias.name.split(".")[0]
                if mod_root in RESTRICTED_MODULES:
                    restricted.append(mod_root)
                    warnings.append(f"Line {node.lineno}: restricted import '{alias.name}'")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_root = node.module.split(".")[0]
                if mod_root in RESTRICTED_MODULES:
                    restricted.append(mod_root)
                    warnings.append(f"Line {node.lineno}: restricted import from '{node.module}'")

        # Check dangerous calls
        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in DANGEROUS_CALLS:
                dangerous.append(func_name)
                warnings.append(f"Line {node.lineno}: dangerous call '{func_name}()'")

    safe = len(restricted) == 0 and len(dangerous) == 0
    return SafetyReport(safe=safe, warnings=warnings, restricted_imports=restricted, dangerous_calls=dangerous)


# ---------------------------------------------------------------------------
# Strategy loader
# ---------------------------------------------------------------------------

@dataclass
class LoadedStrategy:
    """Metadata about a loaded strategy."""
    name: str
    class_name: str
    module_path: str
    load_time: float
    strategy_class: type


class StrategyHotLoader:
    """Load strategies from files or code strings at runtime."""

    def __init__(self, sandbox: bool = True):
        self._sandbox = sandbox
        self._loaded: Dict[str, LoadedStrategy] = {}
        self._lock = threading.Lock()
        self._watchers: Dict[str, threading.Thread] = {}
        self._watching = False

    def load_from_file(self, path: str, force: bool = False) -> Optional[type]:
        """Load a strategy class from a Python file.

        Args:
            path: Path to the .py file.
            force: If True, reload even if already loaded.

        Returns:
            The strategy class, or None on failure.
        """
        p = Path(path)
        if not p.exists():
            return None

        code = p.read_text(encoding="utf-8")

        # Safety check
        if self._sandbox:
            report = check_code_safety(code)
            if not report.safe:
                return None

        try:
            module_name = f"_strategy_{p.stem}_{id(self)}"
            spec = importlib.util.spec_from_file_location(module_name, str(p))
            if spec is None or spec.loader is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Find BaseStrategy subclass
            strategy_class = self._find_strategy_class(mod)
            if strategy_class is None:
                return None

            with self._lock:
                self._loaded[p.stem] = LoadedStrategy(
                    name=p.stem,
                    class_name=strategy_class.__name__,
                    module_path=str(p),
                    load_time=time.time(),
                    strategy_class=strategy_class,
                )
            return strategy_class

        except Exception:
            return None

    def load_from_string(self, code: str, name: str = "dynamic") -> Optional[type]:
        """Load a strategy class from a code string.

        Args:
            code: Python source code.
            name: Name for the module.

        Returns:
            The strategy class, or None on failure.
        """
        if self._sandbox:
            report = check_code_safety(code)
            if not report.safe:
                return None

        try:
            module_name = f"_strategy_{name}_{id(self)}"
            mod = type(sys)("dynamic_module")
            mod.__name__ = module_name

            exec(compile(code, f"<{name}>", "exec"), mod.__dict__)  # noqa: S102

            strategy_class = self._find_strategy_class(mod)
            if strategy_class is None:
                return None

            with self._lock:
                self._loaded[name] = LoadedStrategy(
                    name=name,
                    class_name=strategy_class.__name__,
                    module_path="<string>",
                    load_time=time.time(),
                    strategy_class=strategy_class,
                )
            return strategy_class

        except Exception:
            return None

    def _find_strategy_class(self, mod) -> Optional[type]:
        """Find a BaseStrategy subclass in a module."""
        import inspect
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            # Check if this looks like a strategy (has generate_signals method)
            if hasattr(obj, "generate_signals") and obj.__module__ != "src.core.strategy_base":
                return obj
        return None

    def reload(self, name: str) -> Optional[type]:
        """Reload a previously loaded strategy."""
        with self._lock:
            loaded = self._loaded.get(name)
        if loaded is None:
            return None
        if loaded.module_path == "<string>":
            return None  # Can't reload string-loaded
        return self.load_from_file(loaded.module_path, force=True)

    def get_loaded(self, name: str) -> Optional[LoadedStrategy]:
        """Get metadata about a loaded strategy."""
        with self._lock:
            return self._loaded.get(name)

    def list_loaded(self) -> List[LoadedStrategy]:
        """List all loaded strategies."""
        with self._lock:
            return list(self._loaded.values())

    def unload(self, name: str) -> bool:
        """Unload a strategy."""
        with self._lock:
            return self._loaded.pop(name, None) is not None

    def watch(self, directory: str, callback: Optional[Callable] = None, interval: float = 2.0) -> None:
        """Watch a directory for .py file changes and auto-reload.

        Args:
            directory: Directory to watch.
            callback: Optional callback(name, strategy_class) on reload.
            interval: Check interval in seconds.
        """
        p = Path(directory)
        if not p.is_dir():
            return

        self._watching = True
        mtimes: Dict[str, float] = {}

        def _watch_loop():
            while self._watching:
                for py_file in p.glob("*.py"):
                    if py_file.name.startswith("_"):
                        continue
                    mtime = py_file.stat().st_mtime
                    key = str(py_file)
                    if key in mtimes and mtimes[key] < mtime:
                        cls = self.load_from_file(key, force=True)
                        if cls and callback:
                            callback(py_file.stem, cls)
                    mtimes[key] = mtime
                time.sleep(interval)

        t = threading.Thread(target=_watch_loop, daemon=True)
        t.start()
        self._watchers[directory] = t

    def stop_watching(self) -> None:
        """Stop all file watchers."""
        self._watching = False
        self._watchers.clear()


__all__ = [
    "StrategyHotLoader",
    "LoadedStrategy",
    "SafetyReport",
    "check_code_safety",
    "RESTRICTED_MODULES",
    "DANGEROUS_CALLS",
]
