"""Research engine — V6 ring wrapper over the MLOps stack.

Re-exports the model registry, training adapters, signal schemas,
inference service and drift validation helpers from :mod:`src.mlops`.
These satisfy the V6 ``ModelRegistryPort`` / ``InferencePort`` /
``SignalProviderPort`` ports declared in
:mod:`src.core.contracts.ports.services`.
"""

from __future__ import annotations

from src.mlops.inference import (
    BatchInferenceRunner,
    InferenceService,
    Predictor,
    benchmark_inference,
)
from src.mlops.model_registry import ModelMetadata, ModelRegistry
from src.mlops.signals import (
    SignalAction,
    SignalProvider,
    SignalSchema,
    normalize_signal_output,
)
from src.mlops.training import (
    BaseTrainerAdapter,
    FinRLTrainerAdapter,
    QlibTrainerAdapter,
    TrainerProtocol,
    TrainingArtifact,
    build_artifact_path,
    register_trained_model,
)
from src.mlops.validation import (
    compare_backtest_live_metrics,
    detect_feature_drift,
    population_stability_index,
)

__all__ = (
    "ModelRegistry",
    "ModelMetadata",
    "TrainerProtocol",
    "BaseTrainerAdapter",
    "FinRLTrainerAdapter",
    "QlibTrainerAdapter",
    "TrainingArtifact",
    "build_artifact_path",
    "register_trained_model",
    "InferenceService",
    "BatchInferenceRunner",
    "Predictor",
    "benchmark_inference",
    "SignalSchema",
    "SignalAction",
    "SignalProvider",
    "normalize_signal_output",
    "population_stability_index",
    "detect_feature_drift",
    "compare_backtest_live_metrics",
)
