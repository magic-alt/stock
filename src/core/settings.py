"""Typed runtime settings single source of truth.

Gate 1 resolves runtime configuration exactly once with this precedence::

    CLI overrides > environment > config.yaml > safe defaults

The existing :mod:`src.core.config` models remain the schema for research,
backtest, risk and strategy configuration.  ``PlatformSettings`` composes that
schema with API/runtime settings and owns all runtime source precedence.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import yaml
from pydantic import BaseModel, Field, PrivateAttr, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.config import GlobalConfig


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ValueError(f"expected boolean value, got {value!r}")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _identity(value: str) -> str:
    return value


def _integer(value: str) -> int:
    return int(value)


def _float(value: str) -> float:
    return float(value)


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _set_nested(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cursor = target
    for key in path[:-1]:
        child = cursor.get(key)
        if not isinstance(child, dict):
            child = {}
            cursor[key] = child
        cursor = child
    cursor[path[-1]] = value


class ApiRuntimeSettings(BaseModel):
    """FastAPI/bootstrap settings that are shared by CLI and deployments."""

    host: str = "0.0.0.0"
    port: int = Field(8000, ge=1, le=65535)
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    frontend_dist: str = ""
    auth_disabled: bool = False
    token: SecretStr = Field(default_factory=lambda: SecretStr(""))
    token_subject: str = "bootstrap-admin"
    token_role: str = "admin"
    token_account_group: str = ""
    token_strategy_id: str = ""
    token_account_id: str = ""
    audit_log: str = "./logs/audit.log"

    @field_validator("host", "token_subject", "token_role", "audit_log")
    @classmethod
    def _required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class PlatformSettings(BaseSettings):
    """Resolved application settings plus source metadata.

    ``BaseSettings`` is deliberately used as the typed settings boundary, while
    source merging is explicit so the repository has one documented precedence
    contract rather than framework defaults plus ad-hoc ``os.getenv`` calls.
    """

    config: GlobalConfig = Field(default_factory=GlobalConfig)
    api: ApiRuntimeSettings = Field(default_factory=ApiRuntimeSettings)
    config_path: Optional[str] = None

    model_config = SettingsConfigDict(
        extra="forbid",
        validate_assignment=True,
        env_prefix="__QUANT_PLATFORM_SETTINGS_RESOLVED__",
    )

    _sources: dict[str, str] = PrivateAttr(default_factory=dict)

    @property
    def platform(self):
        return self.config.platform

    @property
    def database(self):
        return self.config.database

    @property
    def data(self):
        return self.config.data

    @property
    def ai(self):
        return self.config.ai

    def source_for(self, dotted_path: str) -> str:
        return self._sources.get(dotted_path, "default")

    def effective_dict(self, *, redact_secrets: bool = True) -> dict[str, Any]:
        payload = self.config.model_dump()
        payload["api"] = self.api.model_dump(mode="json")
        payload["config_path"] = self.config_path
        if redact_secrets:
            if payload["api"].get("token"):
                payload["api"]["token"] = "********"
            if payload.get("ai", {}).get("api_key"):
                payload["ai"]["api_key"] = "********"
            providers = payload.get("data", {}).get("providers", {})
            for provider in providers.values():
                if isinstance(provider, dict) and provider.get("token"):
                    provider["token"] = "********"
        return payload

    def doctor(self) -> tuple[list[str], list[str]]:
        """Return ``(errors, warnings)`` for cross-setting runtime conflicts."""
        errors: list[str] = []
        warnings: list[str] = list(self.config.validate_all())

        token = self.api.token.get_secret_value().strip()
        if not self.api.auth_disabled and not token:
            errors.append("API authentication is enabled but PLATFORM_API_TOKEN is empty")
        if self.api.auth_disabled and token:
            warnings.append("PLATFORM_API_TOKEN is configured but authentication is disabled")

        remote_store = self.platform.job_store.startswith(("redis://", "postgres://", "postgresql://"))
        if remote_store and self.platform.job_store_fallback:
            warnings.append("remote platform.job_store has fallback enabled; production should fail closed")

        if "*" in self.api.allowed_origins:
            warnings.append("api.allowed_origins contains '*' while the API enables credentialed CORS")
        return errors, warnings


# Exact public environment names are part of the deployment contract.  Legacy
# BACKTEST_* aliases remain supported here so old callers do not retain a second
# resolver in ConfigManager.
_ENV_BINDINGS: dict[str, tuple[tuple[str, ...], Callable[[str], Any]]] = {
    "PLATFORM_API_HOST": (("api", "host"), _identity),
    "PLATFORM_API_PORT": (("api", "port"), _integer),
    "PORT": (("api", "port"), _integer),
    "PLATFORM_ALLOWED_ORIGINS": (("api", "allowed_origins"), _csv),
    "PLATFORM_FRONTEND_DIST": (("api", "frontend_dist"), _identity),
    "PLATFORM_API_AUTH_DISABLED": (("api", "auth_disabled"), _bool),
    "PLATFORM_API_TOKEN": (("api", "token"), _identity),
    "PLATFORM_API_TOKEN_SUBJECT": (("api", "token_subject"), _identity),
    "PLATFORM_API_TOKEN_ROLE": (("api", "token_role"), _identity),
    "PLATFORM_API_TOKEN_ACCOUNT_GROUP": (("api", "token_account_group"), _identity),
    "PLATFORM_API_TOKEN_STRATEGY_ID": (("api", "token_strategy_id"), _identity),
    "PLATFORM_API_TOKEN_ACCOUNT_ID": (("api", "token_account_id"), _identity),
    "PLATFORM_AUDIT_LOG": (("api", "audit_log"), _identity),
    "PLATFORM_JOB_STORE": (("platform", "job_store"), _identity),
    "PLATFORM_JOB_STORE_FALLBACK": (("platform", "job_store_fallback"), _bool),
    "PLATFORM_JOB_MAX_WORKERS": (("platform", "job_max_workers"), _integer),
    "MARKET_DATA_DUCKDB_PATH": (("database", "duckdb_path"), _identity),
    "OPENAI_API_KEY": (("ai", "api_key"), _identity),
    "OPENAI_BASE_URL": (("ai", "base_url"), _identity),
    "OPENAI_MODEL": (("ai", "model"), _identity),
    "BACKTEST_DATA_PROVIDER": (("data", "provider"), _identity),
    "BACKTEST_DATA_CACHE_DIR": (("data", "cache_dir"), _identity),
    "BACKTEST_INITIAL_CASH": (("backtest", "initial_cash"), _float),
    "BACKTEST_BACKTEST_CASH": (("backtest", "initial_cash"), _float),
    "BACKTEST_BACKTEST_COMMISSION": (("backtest", "commission"), _float),
    "BACKTEST_RISK_MAX_POSITION": (("risk", "max_position_pct"), _float),
    "BACKTEST_EXECUTION_GATEWAY": (("execution", "gateway"), _identity),
    "BACKTEST_LOG_LEVEL": (("logging", "level"), _identity),
}


def _yaml_payload(path: Optional[str]) -> tuple[dict[str, Any], Optional[str]]:
    if not path:
        return {}, None
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return {}, str(config_path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"configuration root must be a mapping: {config_path}")
    return payload, str(config_path)


def _default_config_path(environ: Mapping[str, str]) -> Optional[str]:
    explicit = environ.get("PLATFORM_CONFIG", "").strip()
    if explicit:
        return explicit
    for candidate in ("config.yaml", "config/config.yaml", str(Path.home() / ".backtest" / "config.yaml")):
        if Path(candidate).expanduser().exists():
            return candidate
    return None


def load_platform_settings(
    *,
    config_path: Optional[str] = None,
    cli_overrides: Optional[Mapping[str, Any]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> PlatformSettings:
    """Resolve settings with ``CLI > env > YAML > safe defaults`` precedence."""
    import os

    env = dict(os.environ if environ is None else environ)
    cli = dict(cli_overrides or {})

    cli_config_path = cli.pop("config_path", None)
    selected_path = cli_config_path or config_path or _default_config_path(env)

    defaults = GlobalConfig().model_dump()
    defaults["api"] = ApiRuntimeSettings().model_dump(mode="python")
    merged = defaults
    sources: dict[str, str] = {}

    yaml_payload, resolved_path = _yaml_payload(selected_path)
    if yaml_payload:
        merged = _deep_merge(merged, yaml_payload)
        for section, values in yaml_payload.items():
            if isinstance(values, Mapping):
                for key in values:
                    sources[f"{section}.{key}"] = "yaml"
            else:
                sources[str(section)] = "yaml"

    for env_name, (path, converter) in _ENV_BINDINGS.items():
        raw = env.get(env_name)
        if raw is None:
            continue
        # Preserve the older BACKTEST_INITIAL_CASH > BACKTEST_BACKTEST_CASH
        # preference by not replacing an already-resolved legacy alias.
        dotted = ".".join(path)
        if env_name == "BACKTEST_BACKTEST_CASH" and sources.get(dotted) == "env:BACKTEST_INITIAL_CASH":
            continue
        _set_nested(merged, path, converter(raw))
        sources[dotted] = f"env:{env_name}"

    if cli:
        merged = _deep_merge(merged, cli)
        for section, values in cli.items():
            if isinstance(values, Mapping):
                for key in values:
                    sources[f"{section}.{key}"] = "cli"
            else:
                sources[str(section)] = "cli"

    api_payload = merged.pop("api", {})
    settings = PlatformSettings(
        config=GlobalConfig(**merged),
        api=ApiRuntimeSettings(**api_payload),
        config_path=resolved_path,
    )
    settings._sources = sources
    return settings


__all__ = ["ApiRuntimeSettings", "PlatformSettings", "load_platform_settings"]
