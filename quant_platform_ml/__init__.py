"""Compatibility facade for the ``quant-platform-ml`` distribution.

Re-exports the canonical MLOps surface from ``src.mlops`` together with the
``src.adapters.ml`` namespace so downstream callers can write::

    from quant_platform_ml import ModelRegistry, InferenceService
    from quant_platform_ml import adapters as ml_adapters
    from quant_platform_ml.training import register_trained_model

Optional ML SDK dependencies (qlib, finrl, torch) are not imported eagerly;
the underlying ``src.mlops`` package handles graceful degradation.
"""
from __future__ import annotations

from src import mlops as _mlops
from src.adapters import ml as adapters
from src.mlops import *  # noqa: F401,F403
from src.mlops import __all__ as _mlops_all

ML_GROUPS = ("qlib", "finrl", "inference", "training", "registry")

__all__ = [*_mlops_all, "ML_GROUPS", "adapters"]
