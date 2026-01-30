from __future__ import annotations

from src.mlops.qlib_training import QlibTrainingConfig, build_qlib_task


def test_qlib_task_builder() -> None:
    config = QlibTrainingConfig(provider_uri="./qlib_data")
    task = build_qlib_task(config)
    assert task["model"]["class"] == "LGBModel"
    assert task["dataset"]["class"] == "DatasetH"
