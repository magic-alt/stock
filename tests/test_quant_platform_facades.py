"""V6 Phase 7/8 fill-out tests for ``quant_platform_*`` facade packages.

These tests lock in that the distribution facades expose meaningful Python
attributes and that each attribute resolves to the exact same object as the
canonical ``src.*`` implementation.
"""
from __future__ import annotations

import importlib


def test_adapters_cn_reexports_canonical_subpackages():
    facade = importlib.import_module("quant_platform_adapters_cn")
    from src.adapters import broker, data, messaging, ml, realtime, storage

    assert facade.broker is broker
    assert facade.data is data
    assert facade.messaging is messaging
    assert facade.ml is ml
    assert facade.realtime is realtime
    assert facade.storage is storage

    # Sub-attribute spot check: real classes resolve identically.
    from src.adapters.data import DataPortal

    assert facade.data.DataPortal is DataPortal


def test_adapters_cn_groups_constant_lists_real_modules():
    facade = importlib.import_module("quant_platform_adapters_cn")
    for name in facade.ADAPTER_GROUPS:
        assert hasattr(facade, name), f"missing facade attribute {name!r}"


def test_ml_facade_reexports_canonical_mlops_surface():
    facade = importlib.import_module("quant_platform_ml")
    from src.mlops import (
        BatchInferenceRunner,
        InferenceService,
        ModelMetadata,
        ModelRegistry,
        SignalSchema,
    )

    assert facade.ModelRegistry is ModelRegistry
    assert facade.ModelMetadata is ModelMetadata
    assert facade.InferenceService is InferenceService
    assert facade.BatchInferenceRunner is BatchInferenceRunner
    assert facade.SignalSchema is SignalSchema


def test_ml_facade_exposes_adapters_namespace():
    facade = importlib.import_module("quant_platform_ml")
    from src.adapters import ml as adapters_ml

    assert facade.adapters is adapters_ml


def test_ml_facade_submodules_importable():
    training = importlib.import_module("quant_platform_ml.training")
    registry = importlib.import_module("quant_platform_ml.registry")
    inference = importlib.import_module("quant_platform_ml.inference")

    from src.mlops.model_registry import ModelRegistry
    from src.mlops.inference import InferenceService
    from src.mlops.training import register_trained_model

    assert registry.ModelRegistry is ModelRegistry
    assert inference.InferenceService is InferenceService
    assert training.register_trained_model is register_trained_model


def test_core_facade_still_exposes_contract_version():
    facade = importlib.import_module("quant_platform_core")
    assert facade.__contract_version__ == "0.1.0"


def test_sdk_facade_exposes_plugin_registry():
    facade = importlib.import_module("quant_platform_sdk")
    from src.core.plugin_registry import PluginRegistry

    assert facade.PluginRegistry is PluginRegistry


def test_cli_and_web_entry_points_still_resolve():
    cli = importlib.import_module("quant_platform_cli")
    web_cli = importlib.import_module("quant_platform_web.cli")
    assert callable(cli.main)
    assert callable(web_cli.main)
