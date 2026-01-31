"""
Local data lake registry for datasets and artifacts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
import uuid
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DataLakeEntry:
    entry_id: str
    kind: str
    name: str
    path: str
    created_at: str = field(default_factory=_utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataLake:
    """Simple manifest-based data lake registry."""

    def __init__(self, base_dir: str = "./data_lake") -> None:
        self.base_dir = base_dir
        self.manifest_path = os.path.join(base_dir, "manifest.json")
        self._entries: Dict[str, DataLakeEntry] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.manifest_path):
            return
        with open(self.manifest_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for item in data:
            self._entries[item["entry_id"]] = DataLakeEntry(**item)

    def _save(self) -> None:
        os.makedirs(self.base_dir, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump([asdict(e) for e in self._entries.values()], fh, indent=2, ensure_ascii=False)

    def register(self, *, kind: str, name: str, path: str, metadata: Optional[Dict[str, Any]] = None) -> DataLakeEntry:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path does not exist: {path}")
        entry = DataLakeEntry(
            entry_id=str(uuid.uuid4()),
            kind=kind,
            name=name,
            path=path,
            metadata=metadata or {},
        )
        self._entries[entry.entry_id] = entry
        self._save()
        return entry

    def list(self, kind: Optional[str] = None) -> List[DataLakeEntry]:
        entries = list(self._entries.values())
        if kind:
            entries = [e for e in entries if e.kind == kind]
        return entries

    def get(self, entry_id: str) -> Optional[DataLakeEntry]:
        return self._entries.get(entry_id)
