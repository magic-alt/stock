"""
Qlib inference helpers for registered models.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple
import os
import pickle

import pandas as pd

from src.mlops.model_registry import ModelMetadata, ModelRegistry

_QLIB_STATE: Tuple[Optional[str], Optional[str]] = (None, None)


def ensure_qlib_init(provider_uri: str, region: str) -> None:
    """Initialize Qlib once per (provider_uri, region)."""
    global _QLIB_STATE
    if _QLIB_STATE == (provider_uri, region):
        return
    try:
        import qlib  # type: ignore
    except Exception as exc:
        raise ImportError("Qlib is required for registered model inference.") from exc
    qlib.init(provider_uri=provider_uri, region=region)
    _QLIB_STATE = (provider_uri, region)


def to_qlib_symbol(symbol: str) -> str:
    """Convert 600519.SH -> SH600519 (Qlib format)."""
    if not symbol:
        return symbol
    sym = symbol.strip().upper()
    if sym.startswith(("SH", "SZ")) and len(sym) > 2:
        return sym
    if sym.endswith(".SH"):
        return f"SH{sym[:-3]}"
    if sym.endswith(".SZ"):
        return f"SZ{sym[:-3]}"
    return sym


def from_qlib_symbol(symbol: str) -> str:
    """Convert SH600519 -> 600519.SH (backtest format)."""
    if not symbol:
        return symbol
    sym = symbol.strip().upper()
    if sym.startswith("SH"):
        return f"{sym[2:]}.SH"
    if sym.startswith("SZ"):
        return f"{sym[2:]}.SZ"
    return sym


def resolve_registry_model(
    *,
    model_id: Optional[str] = None,
    model_name: Optional[str] = None,
    registry: Optional[ModelRegistry] = None,
) -> ModelMetadata:
    """Resolve a model from the registry by id or name."""
    registry = registry or ModelRegistry()
    if model_id:
        model = registry.get_model(model_id)
        if model is None:
            raise KeyError(f"Model not found: {model_id}")
        return model
    if not model_name:
        raise ValueError("model_id or model_name is required.")
    model = registry.resolve(name=model_name)
    if model is None:
        raise KeyError(f"Model not found: {model_name}")
    return model


def load_qlib_model(model_meta: ModelMetadata) -> object:
    """Load a pickled Qlib model artifact."""
    artifact_path = model_meta.artifact_path
    if not os.path.exists(artifact_path):
        raise FileNotFoundError(f"Qlib artifact not found: {artifact_path}")
    with open(artifact_path, "rb") as fh:
        return pickle.load(fh)


def _normalize_date(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def build_qlib_dataset(
    *,
    instruments: Sequence[str],
    start: str,
    end: str,
    label: str,
) -> object:
    try:
        from qlib.utils import init_instance_by_config  # type: ignore
    except Exception as exc:
        raise ImportError("Qlib is required for dataset construction.") from exc

    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": start,
                    "end_time": end,
                    "fit_start_time": start,
                    "fit_end_time": end,
                    "instruments": list(instruments),
                    "label": [label],
                },
            },
            "segments": {
                "test": (start, end),
            },
        },
    }
    return init_instance_by_config(dataset_config)


def predict_qlib_scores(
    *,
    model_meta: ModelMetadata,
    instruments: Sequence[str],
    start: object,
    end: object,
    provider_uri: Optional[str] = None,
    region: str = "cn",
) -> pd.Series:
    """Return Qlib model predictions as a score series."""
    provider_uri = provider_uri or model_meta.training_config.get("provider_uri") or "./qlib_data"
    ensure_qlib_init(provider_uri, region)
    model = load_qlib_model(model_meta)
    label = model_meta.signature.get("label") or "Ref($close, -1) / $close - 1"
    start_str = _normalize_date(start)
    end_str = _normalize_date(end)
    dataset = build_qlib_dataset(instruments=instruments, start=start_str, end=end_str, label=label)
    scores = model.predict(dataset, segment="test")
    if not isinstance(scores, pd.Series):
        scores = pd.Series(scores)
    return scores


def extract_instrument_scores(scores: pd.Series, instrument: str) -> pd.Series:
    """Filter a multi-index score series to a single instrument."""
    series = scores
    if isinstance(series.index, pd.MultiIndex):
        level = "instrument" if "instrument" in series.index.names else 1
        try:
            series = series.xs(instrument, level=level)
        except KeyError as exc:
            raise KeyError(f"No scores found for instrument: {instrument}") from exc
    series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
    return series.sort_index()
