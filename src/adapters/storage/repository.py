"""Canonical repository adapter exports."""

from __future__ import annotations

from src.core.repository import (
    DuckDBRepository,
    MemoryRepository,
    Repository,
    SQLiteRepository,
    create_repository,
)

__all__ = [
    "DuckDBRepository",
    "MemoryRepository",
    "Repository",
    "SQLiteRepository",
    "create_repository",
]
