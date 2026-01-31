import pandas as pd

from src.mlops.model_registry import ModelRegistry
from src.mlops.qlib_inference import (
    extract_instrument_scores,
    from_qlib_symbol,
    resolve_registry_model,
    to_qlib_symbol,
)


def test_symbol_roundtrip():
    assert to_qlib_symbol("600519.SH") == "SH600519"
    assert to_qlib_symbol("000001.SZ") == "SZ000001"
    assert from_qlib_symbol("SH600519") == "600519.SH"
    assert from_qlib_symbol("SZ000001") == "000001.SZ"


def test_resolve_registry_model(tmp_path):
    registry = ModelRegistry(
        registry_path=str(tmp_path / "registry.json"),
        artifact_dir=str(tmp_path / "artifacts"),
    )
    model = registry.register_model(
        name="qlib-demo",
        framework="qlib",
        license_id="MIT",
        artifact_path="dummy.pkl",
    )
    resolved = resolve_registry_model(model_name="qlib-demo", registry=registry)
    assert resolved.model_id == model.model_id
    resolved_by_id = resolve_registry_model(model_id=model.model_id, registry=registry)
    assert resolved_by_id.model_id == model.model_id


def test_extract_instrument_scores():
    idx = pd.MultiIndex.from_product(
        [["SH600519"], pd.date_range("2020-01-01", periods=3, freq="D")],
        names=["instrument", "datetime"],
    )
    scores = pd.Series([0.1, -0.2, 0.0], index=idx)
    out = extract_instrument_scores(scores, "SH600519")
    assert isinstance(out.index, pd.DatetimeIndex)
    assert len(out) == 3
