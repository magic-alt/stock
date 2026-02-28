"""
Repository Pattern (V5.0-E-3) — Abstract storage layer.

Provides:
- Repository protocol (get/list/save/delete)
- SQLiteRepository: current default backend
- DuckDBRepository: OLAP-optimized (V5.0)
- MemoryRepository: in-memory for testing

Usage:
    >>> from src.core.repository import create_repository
    >>> repo = create_repository("memory")
    >>> repo.save({"id": "1", "name": "test"})
    '1'
    >>> repo.get("1")
    {'id': '1', 'name': 'test'}
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Repository Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Repository(Protocol):
    """Abstract repository interface following the Repository pattern."""

    def get(self, entity_id: str) -> Optional[dict]: ...
    def list(self, filters: Optional[dict] = None, limit: int = 100, offset: int = 0) -> List[dict]: ...
    def save(self, entity: dict) -> str: ...
    def delete(self, entity_id: str) -> bool: ...
    def count(self, filters: Optional[dict] = None) -> int: ...


# ---------------------------------------------------------------------------
# MemoryRepository
# ---------------------------------------------------------------------------

class MemoryRepository:
    """In-memory repository for testing and prototyping."""

    def __init__(self):
        self._store: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def get(self, entity_id: str) -> Optional[dict]:
        with self._lock:
            return self._store.get(entity_id)

    def list(self, filters: Optional[dict] = None, limit: int = 100, offset: int = 0) -> List[dict]:
        with self._lock:
            items = list(self._store.values())
            if filters:
                items = [
                    i for i in items
                    if all(i.get(k) == v for k, v in filters.items())
                ]
            return items[offset: offset + limit]

    def save(self, entity: dict) -> str:
        entity_id = entity.get("id") or str(uuid.uuid4())
        entity["id"] = entity_id
        with self._lock:
            self._store[entity_id] = entity
        return entity_id

    def delete(self, entity_id: str) -> bool:
        with self._lock:
            return self._store.pop(entity_id, None) is not None

    def count(self, filters: Optional[dict] = None) -> int:
        return len(self.list(filters=filters, limit=999999))

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# ---------------------------------------------------------------------------
# SQLiteRepository
# ---------------------------------------------------------------------------

class SQLiteRepository:
    """SQLite-backed repository with JSON serialization."""

    def __init__(self, db_path: str = ":memory:", table: str = "entities"):
        self._db_path = db_path
        self._table = table
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

    def get(self, entity_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                f"SELECT data FROM {self._table} WHERE id = ?", (entity_id,)
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def list(self, filters: Optional[dict] = None, limit: int = 100, offset: int = 0) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT data FROM {self._table} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        items = [json.loads(r[0]) for r in rows]
        if filters:
            items = [
                i for i in items
                if all(i.get(k) == v for k, v in filters.items())
            ]
        return items

    def save(self, entity: dict) -> str:
        entity_id = entity.get("id") or str(uuid.uuid4())
        entity["id"] = entity_id
        data_json = json.dumps(entity, default=str)
        with self._lock:
            self._conn.execute(
                f"""INSERT OR REPLACE INTO {self._table} (id, data, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)""",
                (entity_id, data_json),
            )
            self._conn.commit()
        return entity_id

    def delete(self, entity_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                f"DELETE FROM {self._table} WHERE id = ?", (entity_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def count(self, filters: Optional[dict] = None) -> int:
        if filters:
            return len(self.list(filters=filters, limit=999999))
        with self._lock:
            row = self._conn.execute(f"SELECT COUNT(*) FROM {self._table}").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# DuckDBRepository
# ---------------------------------------------------------------------------

class DuckDBRepository:
    """DuckDB-backed repository for OLAP-optimized storage."""

    def __init__(self, db_path: str = ":memory:", table: str = "entities"):
        try:
            import duckdb
        except ImportError:
            raise ImportError("DuckDBRepository requires duckdb: pip install duckdb")
        self._table = table
        self._conn = duckdb.connect(db_path)
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id VARCHAR PRIMARY KEY,
                data VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._lock = threading.Lock()

    def get(self, entity_id: str) -> Optional[dict]:
        with self._lock:
            result = self._conn.execute(
                f"SELECT data FROM {self._table} WHERE id = ?", [entity_id]
            ).fetchone()
        if result is None:
            return None
        return json.loads(result[0])

    def list(self, filters: Optional[dict] = None, limit: int = 100, offset: int = 0) -> List[dict]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT data FROM {self._table} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [limit, offset],
            ).fetchall()
        items = [json.loads(r[0]) for r in rows]
        if filters:
            items = [
                i for i in items
                if all(i.get(k) == v for k, v in filters.items())
            ]
        return items

    def save(self, entity: dict) -> str:
        entity_id = entity.get("id") or str(uuid.uuid4())
        entity["id"] = entity_id
        data_json = json.dumps(entity, default=str)
        with self._lock:
            # DuckDB doesn't support INSERT OR REPLACE directly
            self._conn.execute(f"DELETE FROM {self._table} WHERE id = ?", [entity_id])
            self._conn.execute(
                f"INSERT INTO {self._table} (id, data) VALUES (?, ?)",
                [entity_id, data_json],
            )
        return entity_id

    def delete(self, entity_id: str) -> bool:
        with self._lock:
            before = self._conn.execute(
                f"SELECT COUNT(*) FROM {self._table} WHERE id = ?", [entity_id]
            ).fetchone()[0]
            self._conn.execute(f"DELETE FROM {self._table} WHERE id = ?", [entity_id])
        return before > 0

    def count(self, filters: Optional[dict] = None) -> int:
        if filters:
            return len(self.list(filters=filters, limit=999999))
        with self._lock:
            row = self._conn.execute(f"SELECT COUNT(*) FROM {self._table}").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_repository(backend: str = "memory", **kwargs) -> Repository:
    """Create a repository instance.

    Args:
        backend: "memory", "sqlite", or "duckdb".
    """
    if backend == "memory":
        return MemoryRepository()
    elif backend == "sqlite":
        return SQLiteRepository(**kwargs)
    elif backend == "duckdb":
        return DuckDBRepository(**kwargs)
    else:
        raise ValueError(f"Unknown repository backend: {backend}")


__all__ = [
    "Repository",
    "MemoryRepository",
    "SQLiteRepository",
    "DuckDBRepository",
    "create_repository",
]
