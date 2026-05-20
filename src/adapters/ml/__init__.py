"""ML adapter exports."""

from src.adapters.ml.data import (
    align_to_trading_calendar,
    build_feature_frame,
    normalize_ohlcv_frame,
)
from src.adapters.ml.finrl import build_finrl_frame
from src.adapters.ml.inference import BatchInferenceRunner, InferenceService
from src.adapters.ml.registry import ModelMetadata, ModelRegistry
from src.adapters.ml.signals import SignalAction, SignalSchema, normalize_signal_output
from src.adapters.ml.strategy import AISignalStrategy, default_feature_builder
from src.adapters.ml.training import (
    BaseTrainerAdapter,
    FinRLTrainerAdapter,
    QlibTrainerAdapter,
    TrainingArtifact,
    register_trained_model,
)
from src.adapters.ml.qlib import build_qlib_frame

__all__ = [
    "AISignalStrategy",
    "BaseTrainerAdapter",
    "BatchInferenceRunner",
    "FinRLTrainerAdapter",
    "InferenceService",
    "ModelMetadata",
    "ModelRegistry",
    "QlibTrainerAdapter",
    "SignalAction",
    "SignalSchema",
    "TrainingArtifact",
    "align_to_trading_calendar",
    "build_feature_frame",
    "build_finrl_frame",
    "build_qlib_frame",
    "default_feature_builder",
    "normalize_ohlcv_frame",
    "normalize_signal_output",
    "register_trained_model",
]
