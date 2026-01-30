"""
Training and export helpers for AI framework integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Callable, Dict, Optional, Protocol, Tuple, Union

from src.core.defaults import PATHS
from .model_registry import ModelRegistry, ModelMetadata

TrainOutput = Union["TrainingArtifact", Tuple[object, Dict[str, Any]], Tuple[object, Dict[str, Any], Dict[str, Any], str]]
TrainFn = Callable[[], TrainOutput]
ExportFn = Callable[[object, str], str]


@dataclass
class TrainingArtifact:
    artifact_path: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    signature: Dict[str, Any] = field(default_factory=dict)
    training_config: Dict[str, Any] = field(default_factory=dict)
    data_fingerprint: str = ""


class TrainerProtocol(Protocol):
    name: str
    framework: str
    license_id: str

    def train(self) -> TrainingArtifact:
        ...


def _default_artifact_dir() -> str:
    return os.path.join(PATHS.get("cache", "./cache"), "mlops", "artifacts")


def build_artifact_path(artifact_dir: str, name: str, suffix: str = "bin") -> str:
    os.makedirs(artifact_dir, exist_ok=True)
    safe_name = name.replace(" ", "_")
    return os.path.join(artifact_dir, f"{safe_name}.{suffix}")


class BaseTrainerAdapter:
    """
    Adapter that wraps a train function and optional export function.
    """

    def __init__(
        self,
        *,
        name: str,
        framework: str,
        license_id: str,
        train_fn: TrainFn,
        export_fn: Optional[ExportFn] = None,
        artifact_dir: Optional[str] = None,
        signature: Optional[Dict[str, Any]] = None,
        training_config: Optional[Dict[str, Any]] = None,
        data_fingerprint: str = "",
    ) -> None:
        self.name = name
        self.framework = framework
        self.license_id = license_id
        self._train_fn = train_fn
        self._export_fn = export_fn
        self._artifact_dir = artifact_dir or _default_artifact_dir()
        self._signature = signature or {}
        self._training_config = training_config or {}
        self._data_fingerprint = data_fingerprint

    def train(self) -> TrainingArtifact:
        result = self._train_fn()
        if isinstance(result, TrainingArtifact):
            return result

        if isinstance(result, tuple):
            model = result[0]
            metrics = result[1] if len(result) > 1 else {}
            signature = result[2] if len(result) > 2 else self._signature
            data_fingerprint = result[3] if len(result) > 3 else self._data_fingerprint
        else:
            model = result
            metrics = {}
            signature = self._signature
            data_fingerprint = self._data_fingerprint

        if self._export_fn is None:
            raise ValueError("export_fn is required when train_fn does not return TrainingArtifact")

        artifact_path = self._export_fn(model, self._artifact_dir)
        return TrainingArtifact(
            artifact_path=artifact_path,
            metrics=metrics,
            signature=signature,
            training_config=self._training_config,
            data_fingerprint=data_fingerprint,
        )


class FinRLTrainerAdapter(BaseTrainerAdapter):
    """Convenience adapter for FinRL workflows (MIT license)."""

    def __init__(self, *, name: str, train_fn: TrainFn, export_fn: Optional[ExportFn] = None, **kwargs) -> None:
        super().__init__(
            name=name,
            framework="finrl",
            license_id="MIT",
            train_fn=train_fn,
            export_fn=export_fn,
            **kwargs,
        )


class QlibTrainerAdapter(BaseTrainerAdapter):
    """Convenience adapter for Qlib workflows (MIT license)."""

    def __init__(self, *, name: str, train_fn: TrainFn, export_fn: Optional[ExportFn] = None, **kwargs) -> None:
        super().__init__(
            name=name,
            framework="qlib",
            license_id="MIT",
            train_fn=train_fn,
            export_fn=export_fn,
            **kwargs,
        )


def register_trained_model(
    trainer: TrainerProtocol,
    registry: Optional[ModelRegistry] = None,
    *,
    model_name: Optional[str] = None,
    version: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
) -> ModelMetadata:
    registry = registry or ModelRegistry()
    artifact = trainer.train()
    return registry.register_model(
        name=model_name or trainer.name,
        framework=trainer.framework,
        license_id=trainer.license_id,
        artifact_path=artifact.artifact_path,
        version=version,
        signature=artifact.signature,
        metrics=artifact.metrics,
        training_config=artifact.training_config,
        data_fingerprint=artifact.data_fingerprint,
        tags=tags,
    )
