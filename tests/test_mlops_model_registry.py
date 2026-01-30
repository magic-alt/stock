from __future__ import annotations

from pathlib import Path

from src.mlops.license_policy import LicensePolicy
from src.mlops.model_registry import ModelRegistry


def test_license_policy_default() -> None:
    policy = LicensePolicy.default()
    assert policy.is_allowed("MIT") is True
    assert policy.is_allowed("Apache-2.0") is True
    assert policy.is_allowed("AGPL-3.0") is False


def test_model_registry_register_and_promote(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    artifact_dir = tmp_path / "artifacts"
    registry = ModelRegistry(registry_path=str(registry_path), artifact_dir=str(artifact_dir))

    model = registry.register_model(
        name="finrl-demo",
        framework="finrl",
        license_id="MIT",
        artifact_path=str(artifact_dir / "model.onnx"),
        metrics={"sharpe": 1.2},
    )
    assert model.model_id
    assert registry.get_model(model.model_id) is not None

    promoted = registry.promote_model(model.model_id, status="production")
    assert promoted.status == "production"
    resolved = registry.resolve(name="finrl-demo", prefer_status="production")
    assert resolved is not None
