"""
MLOps utilities for AI signal integration.
"""

from .signals import SignalSchema, SignalAction, normalize_signal_output
from .strategy_adapter import AISignalStrategy, default_feature_builder
from .data_adapter import normalize_ohlcv_frame, align_to_trading_calendar, build_feature_frame
from .license_policy import LicensePolicy
from .model_registry import ModelRegistry, ModelMetadata
from .inference import InferenceService, BatchInferenceRunner
from .validation import population_stability_index, detect_feature_drift, compare_backtest_live_metrics
from .finrl_adapter import build_finrl_frame
from .qlib_adapter import build_qlib_frame
from .training import (
    TrainingArtifact,
    BaseTrainerAdapter,
    FinRLTrainerAdapter,
    QlibTrainerAdapter,
    register_trained_model,
)
from .finrl_training import FinRLTrainingConfig, train_and_register_finrl
from .qlib_training import QlibTrainingConfig, train_and_register_qlib

__all__ = [
    "SignalSchema",
    "SignalAction",
    "normalize_signal_output",
    "AISignalStrategy",
    "default_feature_builder",
    "normalize_ohlcv_frame",
    "align_to_trading_calendar",
    "build_feature_frame",
    "LicensePolicy",
    "ModelRegistry",
    "ModelMetadata",
    "InferenceService",
    "BatchInferenceRunner",
    "population_stability_index",
    "detect_feature_drift",
    "compare_backtest_live_metrics",
    "build_finrl_frame",
    "build_qlib_frame",
    "TrainingArtifact",
    "BaseTrainerAdapter",
    "FinRLTrainerAdapter",
    "QlibTrainerAdapter",
    "register_trained_model",
    "FinRLTrainingConfig",
    "train_and_register_finrl",
    "QlibTrainingConfig",
    "train_and_register_qlib",
]
