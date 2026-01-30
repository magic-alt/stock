"""
Minimal training + registry demo using BaseTrainerAdapter.
"""
from __future__ import annotations

from pathlib import Path

from src.mlops.training import BaseTrainerAdapter, TrainingArtifact, register_trained_model
from src.mlops.model_registry import ModelRegistry


def dummy_train() -> TrainingArtifact:
    artifact_path = Path("./cache/mlops/artifacts/dummy.bin")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("dummy model")
    return TrainingArtifact(
        artifact_path=str(artifact_path),
        metrics={"sharpe": 1.0},
        signature={"inputs": ["open", "high", "low", "close", "volume"]},
        training_config={"algo": "dummy"},
        data_fingerprint="demo",
    )


def demo() -> None:
    trainer = BaseTrainerAdapter(
        name="finrl-demo",
        framework="finrl",
        license_id="MIT",
        train_fn=dummy_train,
    )
    registry = ModelRegistry()
    model = register_trained_model(trainer, registry=registry)
    print("Registered model:", model.model_id, model.name, model.version)


if __name__ == "__main__":
    demo()
