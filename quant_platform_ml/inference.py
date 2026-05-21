"""Inference services re-exported from :mod:`src.mlops.inference`."""
from __future__ import annotations

from src.mlops.inference import BatchInferenceRunner, InferenceService

__all__ = ["BatchInferenceRunner", "InferenceService"]
