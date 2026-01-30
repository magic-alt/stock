"""
Qlib training integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.mlops.model_registry import ModelRegistry
from src.mlops.training import TrainingArtifact, QlibTrainerAdapter, register_trained_model, build_artifact_path


@dataclass
class QlibTrainingConfig:
    provider_uri: str
    region: str = "cn"
    market: str = "csi300"
    experiment_name: str = "qlib_lgbm"
    artifact_dir: Optional[str] = None
    label: str = "Ref($close, -1) / $close - 1"
    train_start: str = "2008-01-01"
    train_end: str = "2014-12-31"
    valid_start: str = "2015-01-01"
    valid_end: str = "2016-12-31"
    test_start: str = "2017-01-01"
    test_end: str = "2018-12-31"


def build_qlib_task(config: QlibTrainingConfig) -> Dict[str, Any]:
    return {
        "model": {
            "class": "LGBModel",
            "module_path": "qlib.contrib.model.gbdt",
            "kwargs": {
                "loss": "mse",
                "colsample_bytree": 0.8879,
                "learning_rate": 0.05,
                "subsample": 0.8789,
                "lambda_l1": 205.6999,
                "lambda_l2": 580.9768,
                "max_depth": 8,
                "num_leaves": 210,
                "num_threads": 20,
            },
        },
        "dataset": {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": {
                    "class": "Alpha158",
                    "module_path": "qlib.contrib.data.handler",
                    "kwargs": {
                        "start_time": config.train_start,
                        "end_time": config.test_end,
                        "fit_start_time": config.train_start,
                        "fit_end_time": config.train_end,
                        "instruments": config.market,
                        "label": [config.label],
                    },
                },
                "segments": {
                    "train": (config.train_start, config.train_end),
                    "valid": (config.valid_start, config.valid_end),
                    "test": (config.test_start, config.test_end),
                },
            },
        },
    }


def train_qlib_model(config: QlibTrainingConfig) -> TrainingArtifact:
    try:
        import qlib
        from qlib.utils import init_instance_by_config, flatten_dict
        from qlib.workflow import R
    except Exception as exc:
        raise ImportError("Qlib dependencies not available. Install pyqlib first.") from exc

    qlib.init(provider_uri=config.provider_uri, region=config.region)
    task = build_qlib_task(config)
    model = init_instance_by_config(task["model"])
    dataset = init_instance_by_config(task["dataset"])

    with R.start(experiment_name=config.experiment_name):
        R.log_params(**flatten_dict(task))
        model.fit(dataset)
        R.save_objects(trained_model=model)

    artifact_dir = config.artifact_dir or "./cache/mlops/artifacts"
    artifact_path = build_artifact_path(artifact_dir, f"qlib_{config.market}", "pkl")
    import pickle
    with open(artifact_path, "wb") as fh:
        pickle.dump(model, fh)

    return TrainingArtifact(
        artifact_path=artifact_path,
        metrics={"market": config.market},
        signature={"label": config.label},
        training_config={"provider_uri": config.provider_uri, "market": config.market},
        data_fingerprint=f"{config.provider_uri}:{config.market}",
    )


def train_and_register_qlib(config: QlibTrainingConfig, registry: Optional[ModelRegistry] = None):
    trainer = QlibTrainerAdapter(
        name=f"qlib-{config.market}",
        train_fn=lambda: train_qlib_model(config),
        training_config={"provider_uri": config.provider_uri, "market": config.market},
        data_fingerprint=f"{config.provider_uri}:{config.market}",
    )
    return register_trained_model(trainer, registry=registry)
