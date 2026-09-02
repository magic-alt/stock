"""Gate 1 contract tests for the typed runtime settings SSOT."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.settings import PlatformSettings, load_platform_settings


def _write_config(path: Path) -> None:
    path.write_text(
        """
api:
  host: 127.0.0.2
  port: 8123
  auth_disabled: true
  audit_log: ./from-yaml-audit.log
platform:
  job_store: ./from-yaml-jobs.json
  job_store_fallback: false
  job_max_workers: 3
database:
  duckdb_path: ./from-yaml-market.duckdb
backtest:
  initial_cash: 123456
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_settings_precedence_cli_over_env_over_yaml_over_defaults(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    env = {
        "PLATFORM_JOB_STORE": "./from-env-jobs.json",
        "PLATFORM_JOB_MAX_WORKERS": "5",
        "PLATFORM_API_PORT": "8222",
        "PLATFORM_API_AUTH_DISABLED": "1",
    }

    settings = load_platform_settings(
        config_path=str(config_path),
        environ=env,
        cli_overrides={
            "api": {"port": 8333},
            "platform": {"job_store": "./from-cli-jobs.json"},
        },
    )

    assert isinstance(settings, PlatformSettings)
    assert settings.api.host == "127.0.0.2"  # YAML beats default
    assert settings.api.port == 8333  # CLI beats environment
    assert settings.platform.job_store == "./from-cli-jobs.json"
    assert settings.platform.job_max_workers == 5  # environment beats YAML
    assert settings.database.duckdb_path == "./from-yaml-market.duckdb"
    assert settings.config.backtest.initial_cash == 123456
    assert settings.source_for("api.port") == "cli"
    assert settings.source_for("platform.job_max_workers") == "env:PLATFORM_JOB_MAX_WORKERS"
    assert settings.source_for("database.duckdb_path") == "yaml"


def test_platform_config_env_overrides_documented_yaml(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    settings = load_platform_settings(
        environ={
            "PLATFORM_CONFIG": str(config_path),
            "PLATFORM_JOB_STORE": "sqlite:///env-jobs.db",
            "MARKET_DATA_DUCKDB_PATH": "./env-market.duckdb",
            "PLATFORM_API_AUTH_DISABLED": "true",
        }
    )
    assert settings.config_path == str(config_path)
    assert settings.platform.job_store == "sqlite:///env-jobs.db"
    assert settings.database.duckdb_path == "./env-market.duckdb"


def test_legacy_backtest_environment_aliases_resolve_through_same_layer():
    settings = load_platform_settings(
        environ={
            "BACKTEST_INITIAL_CASH": "999999",
            "BACKTEST_BACKTEST_CASH": "111111",
            "BACKTEST_LOG_LEVEL": "debug",
            "PLATFORM_API_AUTH_DISABLED": "1",
        }
    )
    assert settings.config.backtest.initial_cash == 999999
    assert settings.config.logging.level == "DEBUG"


def test_secrets_are_redacted_and_doctor_is_fail_closed():
    missing = load_platform_settings(environ={})
    errors, _ = missing.doctor()
    assert any("PLATFORM_API_TOKEN" in error for error in errors)

    configured = load_platform_settings(
        environ={
            "PLATFORM_API_TOKEN": "super-secret-token",
            "OPENAI_API_KEY": "super-secret-ai-key",
        }
    )
    payload = json.dumps(configured.effective_dict(redact_secrets=True))
    assert "super-secret-token" not in payload
    assert "super-secret-ai-key" not in payload
    assert "********" in payload
    errors, _ = configured.doctor()
    assert errors == []


def test_invalid_typed_environment_value_is_rejected():
    with pytest.raises((ValueError, TypeError)):
        load_platform_settings(environ={"PLATFORM_API_PORT": "not-an-int"})


def test_fastapi_factory_consumes_pre_resolved_settings(tmp_path):
    pytest.importorskip("fastapi")
    from src.platform.api_v2 import create_app

    settings = load_platform_settings(
        environ={"PLATFORM_API_AUTH_DISABLED": "1"},
        cli_overrides={
            "platform": {
                "job_store": str(tmp_path / "jobs.json"),
                "job_store_fallback": False,
                "job_max_workers": 1,
            },
            "database": {"duckdb_path": str(tmp_path / "market.duckdb")},
            "api": {"allowed_origins": ["https://example.test"]},
        },
    )

    app = create_app(settings=settings)
    try:
        assert app.state.settings is settings
        assert app.state.job_queue.store.path == str(tmp_path / "jobs.json")
        assert app.state.local_market_data_db_path == str(tmp_path / "market.duckdb")
        assert app.state.api_auth_settings.disabled is True
    finally:
        app.state.job_queue.shutdown()


def test_deployment_contract_uses_canonical_setting_names():
    root = Path(__file__).resolve().parents[1]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    deployment = (root / "deploy/k8s/platform-api-deployment.yaml").read_text(encoding="utf-8")

    for content in (compose, deployment):
        assert "PLATFORM_API_HOST" in content
        assert "PLATFORM_API_PORT" in content
        assert "PLATFORM_JOB_STORE" in content
        assert "PLATFORM_JOB_STORE_FALLBACK" in content
        assert "MARKET_DATA_DUCKDB_PATH" in content
        assert "PLATFORM_AUDIT_LOG" in content
    assert "scripts/run_platform_api.py" in dockerfile
    assert "PLATFORM_API_PORT=8000" in dockerfile
