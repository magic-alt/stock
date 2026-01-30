"""
Simple JSON-backed model registry for MLOps workflows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import uuid
from typing import Any, Dict, List, Optional

from src.core.defaults import PATHS
from .license_policy import LicensePolicy, normalize_license


@dataclass
class ModelMetadata:
    model_id: str
    name: str
    version: str
    framework: str
    license: str
    artifact_path: str
    created_at: str
    status: str = "staging"
    signature: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    training_config: Dict[str, Any] = field(default_factory=dict)
    data_fingerprint: str = ""
    tags: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ModelMetadata":
        return cls(**payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "version": self.version,
            "framework": self.framework,
            "license": self.license,
            "artifact_path": self.artifact_path,
            "created_at": self.created_at,
            "status": self.status,
            "signature": self.signature,
            "metrics": self.metrics,
            "training_config": self.training_config,
            "data_fingerprint": self.data_fingerprint,
            "tags": self.tags,
        }


class ModelRegistry:
    """JSON-backed registry stored in cache."""

    def __init__(
        self,
        registry_path: Optional[str] = None,
        artifact_dir: Optional[str] = None,
        license_policy: Optional[LicensePolicy] = None,
    ) -> None:
        base_cache = PATHS.get("cache", "./cache")
        self.registry_path = registry_path or os.path.join(base_cache, "mlops", "model_registry.json")
        self.artifact_dir = artifact_dir or os.path.join(base_cache, "mlops", "artifacts")
        self.license_policy = license_policy or LicensePolicy.default()
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        os.makedirs(self.artifact_dir, exist_ok=True)

    def _load(self) -> List[ModelMetadata]:
        if not os.path.exists(self.registry_path):
            return []
        with open(self.registry_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [ModelMetadata.from_dict(item) for item in data]

    def _save(self, models: List[ModelMetadata]) -> None:
        with open(self.registry_path, "w", encoding="utf-8") as fh:
            json.dump([m.to_dict() for m in models], fh, indent=2, ensure_ascii=False)

    def register_model(
        self,
        *,
        name: str,
        framework: str,
        license_id: str,
        artifact_path: str,
        version: Optional[str] = None,
        signature: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        training_config: Optional[Dict[str, Any]] = None,
        data_fingerprint: str = "",
        tags: Optional[Dict[str, Any]] = None,
    ) -> ModelMetadata:
        if not self.license_policy.is_allowed(license_id):
            raise ValueError(f"License not allowed: {license_id}")
        models = self._load()
        if not version:
            existing = [m for m in models if m.name == name]
            version = f"v{len(existing) + 1}"
        model = ModelMetadata(
            model_id=str(uuid.uuid4()),
            name=name,
            version=version,
            framework=framework,
            license=normalize_license(license_id),
            artifact_path=artifact_path,
            created_at=datetime.now(timezone.utc).isoformat(),
            signature=signature or {},
            metrics=metrics or {},
            training_config=training_config or {},
            data_fingerprint=data_fingerprint,
            tags=tags or {},
        )
        models.append(model)
        self._save(models)
        return model

    def list_models(self, *, name: Optional[str] = None, status: Optional[str] = None) -> List[ModelMetadata]:
        models = self._load()
        if name:
            models = [m for m in models if m.name == name]
        if status:
            models = [m for m in models if m.status == status]
        return models

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        for model in self._load():
            if model.model_id == model_id:
                return model
        return None

    def promote_model(self, model_id: str, *, status: str = "production") -> ModelMetadata:
        models = self._load()
        target: Optional[ModelMetadata] = None
        for idx, model in enumerate(models):
            if model.model_id == model_id:
                model.status = status
                models[idx] = model
                target = model
                break
        if target is None:
            raise KeyError(f"Model not found: {model_id}")
        self._save(models)
        return target

    def latest(self, *, name: str, status: Optional[str] = None) -> Optional[ModelMetadata]:
        candidates = self.list_models(name=name, status=status)
        if not candidates:
            return None
        return sorted(candidates, key=lambda m: m.created_at)[-1]

    def resolve(self, *, name: str, prefer_status: str = "production") -> Optional[ModelMetadata]:
        preferred = self.latest(name=name, status=prefer_status)
        if preferred:
            return preferred
        return self.latest(name=name)
