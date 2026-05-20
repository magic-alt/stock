"""Canonical repository adapter exports."""

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
