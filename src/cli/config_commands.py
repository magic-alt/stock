"""Configuration inspection commands for the quant-platform CLI."""
from __future__ import annotations

import json
from typing import Any

import click

from src.core.settings import load_platform_settings


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            dotted = f"{prefix}.{key}" if prefix else key
            rows.extend(_flatten(value[key], dotted))
    else:
        rows.append((prefix, value))
    return rows


@click.group("config")
def config_group() -> None:
    """Inspect and validate effective runtime configuration."""


@config_group.command("doctor")
@click.option("--config", "config_path", type=click.Path(dir_okay=False), default=None, help="YAML configuration file.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def config_doctor(config_path: str | None, as_json: bool) -> None:
    """Resolve settings, redact secrets, and validate incompatible values."""
    try:
        settings = load_platform_settings(config_path=config_path)
        errors, warnings = settings.doctor()
    except Exception as exc:
        if as_json:
            click.echo(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        else:
            click.echo(f"Configuration error: {exc}", err=True)
        raise click.exceptions.Exit(1) from exc

    payload = {
        "ok": not errors,
        "config_path": settings.config_path,
        "precedence": ["cli", "environment", "config.yaml", "safe defaults"],
        "effective": settings.effective_dict(redact_secrets=True),
        "sources": {
            path: settings.source_for(path)
            for path, _ in _flatten(settings.effective_dict(redact_secrets=True))
        },
        "errors": errors,
        "warnings": warnings,
    }

    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    else:
        click.echo("Configuration precedence: CLI > environment > config.yaml > safe defaults")
        click.echo(f"Config file: {settings.config_path or '(none; defaults/env only)'}")
        click.echo("\nEffective non-secret configuration:")
        for path, value in _flatten(payload["effective"]):
            click.echo(f"  {path} = {value!r} [{settings.source_for(path)}]")
        if warnings:
            click.echo("\nWarnings:")
            for warning in warnings:
                click.echo(f"  - {warning}")
        if errors:
            click.echo("\nErrors:", err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
        else:
            click.echo("\nConfiguration OK")

    if errors:
        raise click.exceptions.Exit(1)


__all__ = ["config_group"]
