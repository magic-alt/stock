"""
Vault Module (V5.0-C-2) — Abstract secret storage with pluggable backends.

Provides a unified interface for storing and retrieving secrets (API keys,
tokens, credentials) with support for multiple backends:

- **LocalFileVault**: Encrypted JSON file on disk (default for single-node).
- **EnvVault**: Read-only vault backed by environment variables.
- **MemoryVault**: In-memory vault for testing.

Usage:
    >>> from src.core.vault import create_vault
    >>> vault = create_vault("local", path="secrets.enc", secret_key="my-key")
    >>> vault.put("db_password", "super-secret")
    >>> vault.get("db_password")
    'super-secret'
"""
from __future__ import annotations

import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from src.core.logger import get_logger
from src.core.security import SecurityManager

logger = get_logger("vault")


# ---------------------------------------------------------------------------
# Abstract Vault
# ---------------------------------------------------------------------------

class BaseVault(ABC):
    """Abstract interface for secret storage."""

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Retrieve a secret by key. Returns None if not found."""

    @abstractmethod
    def put(self, key: str, value: str) -> None:
        """Store a secret."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a secret. Returns True if it existed."""

    @abstractmethod
    def list_keys(self) -> List[str]:
        """List all secret keys (not values)."""

    def get_or_raise(self, key: str) -> str:
        """Get a secret or raise KeyError."""
        val = self.get(key)
        if val is None:
            raise KeyError(f"Secret not found: {key}")
        return val

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return self.get(key) is not None


# ---------------------------------------------------------------------------
# In-memory vault (testing)
# ---------------------------------------------------------------------------

class MemoryVault(BaseVault):
    """In-memory vault — data lost on restart. Suitable for tests."""

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            return self._store.get(key)

    def put(self, key: str, value: str) -> None:
        with self._lock:
            self._store[key] = value

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def list_keys(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())


# ---------------------------------------------------------------------------
# Environment variable vault (read-only)
# ---------------------------------------------------------------------------

class EnvVault(BaseVault):
    """Read-only vault backed by environment variables.

    Keys are mapped to env vars by converting to uppercase and prepending
    an optional prefix.  Example: ``EnvVault(prefix="QUANT_")`` maps key
    ``db_password`` to env var ``QUANT_DB_PASSWORD``.
    """

    def __init__(self, prefix: str = "QUANT_") -> None:
        self.prefix = prefix

    def _env_key(self, key: str) -> str:
        return f"{self.prefix}{key.upper()}"

    def get(self, key: str) -> Optional[str]:
        return os.environ.get(self._env_key(key))

    def put(self, key: str, value: str) -> None:
        raise NotImplementedError("EnvVault is read-only")

    def delete(self, key: str) -> bool:
        raise NotImplementedError("EnvVault is read-only")

    def list_keys(self) -> List[str]:
        prefix = self.prefix
        return [
            k[len(prefix):].lower()
            for k in os.environ
            if k.startswith(prefix)
        ]


# ---------------------------------------------------------------------------
# Local encrypted file vault
# ---------------------------------------------------------------------------

class LocalFileVault(BaseVault):
    """Encrypted JSON file vault.

    Secrets are stored as ``{key: encrypted_value}`` in a JSON file.
    Encryption is handled by :class:`SecurityManager`.
    """

    def __init__(self, path: str = "secrets.enc", secret_key: str = "") -> None:
        self._path = Path(path)
        self._sm = SecurityManager(secret_key=secret_key)
        self._lock = threading.Lock()
        self._cache: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Load encrypted store from disk."""
        if not self._path.exists():
            self._cache = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._cache = {k: self._sm.decrypt(v) for k, v in raw.items()}
        except Exception as exc:
            logger.warning("vault_load_failed", path=str(self._path), error=str(exc))
            self._cache = {}

    def _save(self) -> None:
        """Save encrypted store to disk."""
        encrypted = {k: self._sm.encrypt(v) for k, v in self._cache.items()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(encrypted, indent=2), encoding="utf-8")

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            return self._cache.get(key)

    def put(self, key: str, value: str) -> None:
        with self._lock:
            self._cache[key] = value
            self._save()

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = key in self._cache
            self._cache.pop(key, None)
            if existed:
                self._save()
            return existed

    def list_keys(self) -> List[str]:
        with self._lock:
            return list(self._cache.keys())


# ---------------------------------------------------------------------------
# Composite vault (chain of vaults)
# ---------------------------------------------------------------------------

class CompositeVault(BaseVault):
    """Chain multiple vaults — first match wins on read.

    Writes go to the *primary* vault (first in the chain).
    """

    def __init__(self, vaults: List[BaseVault]) -> None:
        if not vaults:
            raise ValueError("At least one vault is required")
        self._vaults = vaults

    @property
    def primary(self) -> BaseVault:
        return self._vaults[0]

    def get(self, key: str) -> Optional[str]:
        for vault in self._vaults:
            val = vault.get(key)
            if val is not None:
                return val
        return None

    def put(self, key: str, value: str) -> None:
        self.primary.put(key, value)

    def delete(self, key: str) -> bool:
        return self.primary.delete(key)

    def list_keys(self) -> List[str]:
        seen: set = set()
        keys: List[str] = []
        for vault in self._vaults:
            for k in vault.list_keys():
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
        return keys


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_vault(
    backend: str = "memory",
    *,
    path: str = "secrets.enc",
    secret_key: str = "",
    env_prefix: str = "QUANT_",
) -> BaseVault:
    """Create a vault instance.

    Args:
        backend: One of ``"memory"``, ``"env"``, ``"local"``, ``"composite"``.
        path: File path for ``local`` backend.
        secret_key: Encryption key for ``local`` backend.
        env_prefix: Prefix for ``env`` backend.
    """
    if backend == "memory":
        return MemoryVault()
    elif backend == "env":
        return EnvVault(prefix=env_prefix)
    elif backend == "local":
        return LocalFileVault(path=path, secret_key=secret_key)
    elif backend == "composite":
        return CompositeVault([
            LocalFileVault(path=path, secret_key=secret_key),
            EnvVault(prefix=env_prefix),
        ])
    else:
        raise ValueError(f"Unknown vault backend: {backend}")


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "BaseVault",
    "MemoryVault",
    "EnvVault",
    "LocalFileVault",
    "CompositeVault",
    "create_vault",
]
