from __future__ import annotations

from pathlib import Path

from src.mlops.model_registry import ModelRegistry
from src.mlops.training import BaseTrainerAdapter, TrainingArtifact, register_trained_model


def test_register_trained_model(tmp_path: Path) -> None:
    artifact_path = tmp_path / "model.bin"
    artifact_path.write_text("model")

    def train_fn() -> TrainingArtifact:
        return TrainingArtifact(
            artifact_path=str(artifact_path),
            metrics={"sharpe": 1.1},
            signature={"inputs": ["close"]},
        )

    registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"), artifact_dir=str(tmp_path / "artifacts"))
    trainer = BaseTrainerAdapter(
        name="finrl-demo",
        framework="finrl",
        license_id="MIT",
        train_fn=train_fn,
    )
    model = register_trained_model(trainer, registry=registry)
    assert model.name == "finrl-demo"
    assert model.metrics["sharpe"] == 1.1


def test_trainer_export_fn(tmp_path: Path) -> None:
    def train_fn():
        return object(), {"accuracy": 0.9}

    def export_fn(model: object, artifact_dir: str) -> str:
        path = Path(artifact_dir) / "export.bin"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("export")
        return str(path)

    trainer = BaseTrainerAdapter(
        name="qlib-demo",
        framework="qlib",
        license_id="MIT",
        train_fn=train_fn,
        export_fn=export_fn,
        artifact_dir=str(tmp_path / "artifacts"),
    )
    artifact = trainer.train()
    assert Path(artifact.artifact_path).exists()
