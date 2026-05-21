"""Tests for the V6 Phase 8 legacy compatibility shim layer."""
from __future__ import annotations

import importlib
import logging
import sys
import types
import warnings

import pytest

from src import _legacy
from src._legacy import (
    LEGACY_ALIASES,
    emit_deprecation,
    install_module_alias,
    iter_known_aliases,
    reset_deprecation_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_deprecation_cache()
    yield
    reset_deprecation_cache()


def test_emit_deprecation_emits_warning_with_message():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        emit_deprecation(
            legacy="src.example_legacy",
            replacement="src.engines.backtest",
            removed_in="V7.0",
        )
    assert len(caught) == 1
    warning = caught[0]
    assert issubclass(warning.category, DeprecationWarning)
    text = str(warning.message)
    assert "src.example_legacy" in text
    assert "src.engines.backtest" in text
    assert "V7.0" in text


def test_emit_deprecation_is_one_shot_per_legacy_name():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        for _ in range(5):
            emit_deprecation(
                legacy="src.example_legacy",
                replacement="src.engines.backtest",
            )
    assert len(caught) == 1


def test_emit_deprecation_separate_keys_emit_separately():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        emit_deprecation(legacy="a", replacement="b")
        emit_deprecation(legacy="c", replacement="d")
    assert len(caught) == 2


def test_emit_deprecation_logs_structured_record(caplog):
    caplog.set_level(logging.INFO, logger="quant_platform.legacy")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        emit_deprecation(
            legacy="src.example_legacy_log",
            replacement="src.engines.backtest",
            removed_in="V7.0",
        )
    records = [r for r in caplog.records if r.name == "quant_platform.legacy"]
    assert records, "expected at least one structured log record"
    record = records[-1]
    assert getattr(record, "event", None) == "legacy_import"
    assert getattr(record, "legacy", None) == "src.example_legacy_log"
    assert getattr(record, "replacement", None) == "src.engines.backtest"
    assert getattr(record, "removed_in", None) == "V7.0"


def test_install_module_alias_registers_in_sys_modules():
    canonical = types.ModuleType("quant_platform_legacy_canonical_under_test")
    canonical.value = 42
    try:
        install_module_alias("legacy_alias_under_test", canonical)
        assert sys.modules.get("legacy_alias_under_test") is canonical
        assert importlib.import_module("legacy_alias_under_test") is canonical
    finally:
        sys.modules.pop("legacy_alias_under_test", None)


def test_iter_known_aliases_matches_catalogue():
    triples = list(iter_known_aliases())
    assert len(triples) == len(LEGACY_ALIASES)
    for legacy, canonical, removed_in in triples:
        assert isinstance(legacy, str)
        assert isinstance(canonical, str)
        assert isinstance(removed_in, str)
        assert LEGACY_ALIASES[legacy] == (canonical, removed_in)


def test_public_surface_is_stable():
    assert set(_legacy.__all__) == {
        "LEGACY_ALIASES",
        "emit_deprecation",
        "install_module_alias",
        "iter_known_aliases",
        "reset_deprecation_cache",
    }
