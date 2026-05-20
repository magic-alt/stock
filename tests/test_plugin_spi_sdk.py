"""V6 Phase 5 plugin SPI and SDK tests."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


EXAMPLE_PLUGIN_ROOT = Path("examples/plugins/simple_momentum_plugin")


def test_sdk_reexports_contract_and_registry():
    from src.sdk import CONTRACT_VERSION, PluginManifest, PluginRegistry

    manifest = PluginManifest(
        id="tests.echo_strategy",
        name="Echo Strategy",
        version="0.1.0",
        kind="strategy",
        entry_point="tests.fake:EchoStrategy",
        contract_version=CONTRACT_VERSION,
    )

    registry = PluginRegistry()
    validation = registry.validate_manifest(manifest)

    assert validation.ok is True
    assert manifest.contract_version == CONTRACT_VERSION


def test_plugin_registry_rejects_unallowed_permissions():
    from src.sdk import CONTRACT_VERSION, PluginManifest, PluginRegistry

    manifest = PluginManifest(
        id="tests.needs_network",
        name="Needs Network",
        version="0.1.0",
        kind="strategy",
        entry_point="tests.fake:NetworkStrategy",
        contract_version=CONTRACT_VERSION,
        permissions=("network.outbound",),
    )

    result = PluginRegistry().validate_manifest(manifest)

    assert result.ok is False
    assert "permissions not allowed: network.outbound" in result.errors
    assert PluginRegistry(allowed_permissions=("network.outbound",)).validate_manifest(manifest).ok is True


def test_example_strategy_plugin_passes_registry_conformance(monkeypatch):
    from src.sdk import PluginRegistry, load_manifest

    monkeypatch.syspath_prepend(str(EXAMPLE_PLUGIN_ROOT.resolve()))
    manifest = load_manifest("simple_momentum_plugin:MANIFEST")
    result = PluginRegistry().test_plugin(manifest)

    assert result.ok is True
    assert result.errors == ()
    assert result.manifest.id == "examples.simple_momentum"
    assert "SimpleMomentumStrategy" in result.loaded_object


def test_quant_platform_plugin_test_cli_outputs_json():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.cli.main",
            "plugin",
            "test",
            "simple_momentum_plugin:MANIFEST",
            "--path",
            str(EXAMPLE_PLUGIN_ROOT),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["plugin"]["id"] == "examples.simple_momentum"
    assert payload["errors"] == []


def test_cookiecutter_plugin_template_declares_entry_point():
    template_root = Path("templates/cookiecutter-plugin")

    assert (template_root / "cookiecutter.json").exists()
    pyproject_template = (
        template_root / "{{cookiecutter.plugin_slug}}" / "pyproject.toml"
    ).read_text(encoding="utf-8")
    plugin_template = (
        template_root
        / "{{cookiecutter.plugin_slug}}"
        / "{{cookiecutter.package_name}}"
        / "__init__.py"
    ).read_text(encoding="utf-8")

    assert "[project.entry-points.\"quant_platform.{{ cookiecutter.plugin_kind }}\"]" in pyproject_template
    assert "PluginManifest(" in plugin_template
    assert "MANIFEST" in plugin_template


def test_pyproject_exposes_quant_platform_console_script():
    pytest.importorskip("tomllib")
    import tomllib

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["quant-platform"] == "src.cli.main:main"
