"""One-shot Gate 1 integration patch. Deleted by its workflow after success."""
from __future__ import annotations

from pathlib import Path
import re


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise RuntimeError(f"expected block not found in {path}: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: str, pattern: str, replacement: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE | re.DOTALL)
    if count != 1:
        raise RuntimeError(f"pattern matched {count} times in {path}: {pattern[:120]!r}")
    file_path.write_text(updated, encoding="utf-8")


def patch_config_manager() -> None:
    path = "src/core/config.py"
    replace_once(
        path,
        '''        if self._config_path is not None:
            loaded = self.__class__.load_from_file(self._config_path)
            # Use the .config property so that a missing file still yields defaults
            self._config = loaded.config
            return self._config

        # No path: build from env vars (falls back to defaults automatically)
        loaded = self.__class__.load_from_env()
        self._config = loaded._config
        return self._config''',
        '''        from src.core.settings import load_platform_settings

        settings = load_platform_settings(config_path=self._config_path)
        self._config = settings.config
        return self._config''',
    )

    regex_once(
        path,
        r'''    @classmethod\n    def load_from_env\(cls, prefix: str = "BACKTEST_"\) -> "ConfigManager":.*?(?=\n    def save_to_file\(self, path: str\) -> None:)''',
        '''    @classmethod
    def load_from_env(cls, prefix: str = "BACKTEST_") -> "ConfigManager":
        """Load environment overrides through the canonical settings resolver.

        ``prefix`` is retained for API compatibility. The historical
        ``BACKTEST_*`` aliases are resolved inside ``PlatformSettings`` so
        environment precedence is defined in one place.
        """
        if prefix != "BACKTEST_":
            logger.warning("custom config env prefix is deprecated: %s", prefix)
        from src.core.settings import load_platform_settings

        return cls(config=load_platform_settings().config)
''',
    )

    regex_once(
        path,
        r'''def get_config\(\) -> ConfigManager:.*?(?=\n\ndef set_config\(config: ConfigManager\))''',
        '''def get_config() -> ConfigManager:
    """Return the global domain config resolved through PlatformSettings."""
    global _global_config

    if _global_config is None:
        from src.core.settings import load_platform_settings

        _global_config = ConfigManager(config=load_platform_settings().config)
        logger.info("Resolved configuration through PlatformSettings")
    return _global_config
''',
    )

    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    text = text.replace(
        "    # New V4.0 fields\n",
        "    # Runtime/domain sections retained for backward-compatible model access.\n",
        1,
    )
    file_path.write_text(text, encoding="utf-8")


def patch_api_v2() -> None:
    path = "src/platform/api_v2.py"
    replace_once(
        path,
        "from src.core.monitoring import TraceContext, get_metric_collector, get_tracer\n",
        "from src.core.monitoring import TraceContext, get_metric_collector, get_tracer\n"
        "from src.core.settings import PlatformSettings, load_platform_settings\n",
    )

    regex_once(
        path,
        r'''    def _resolve_allowed_origins\(allowed_origins: Optional\[List\[str\]\]\) -> List\[str\]:.*?(?=\n    def _open_local_market_data_store)''',
        '''    def _resolve_allowed_origins(
        allowed_origins: Optional[List[str]], settings: PlatformSettings
    ) -> List[str]:
        return list(allowed_origins) if allowed_origins is not None else list(settings.api.allowed_origins)

    def _resolve_frontend_dist(settings: PlatformSettings) -> Optional[Path]:
        raw_path = settings.api.frontend_dist.strip()
        frontend_dist = Path(raw_path) if raw_path else PROJECT_ROOT / "frontend" / "dist"
        index_file = frontend_dist / "index.html"
        if frontend_dist.is_dir() and index_file.is_file():
            return frontend_dist.resolve()
        return None

    def _resolve_market_data_duckdb_path(settings: Optional[PlatformSettings] = None) -> str:
        resolved = settings or load_platform_settings()
        return resolved.database.duckdb_path
''',
    )

    replace_once(
        path,
        '''    def create_app(
        *,
        enable_cors: bool = True,
        allowed_origins: Optional[List[str]] = None,
    ) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(''',
        '''    def create_app(
        *,
        enable_cors: bool = True,
        allowed_origins: Optional[List[str]] = None,
        settings: Optional[PlatformSettings] = None,
    ) -> FastAPI:
        """Create and configure the FastAPI application from one resolved settings object."""
        resolved_settings = settings or load_platform_settings()
        app = FastAPI(''',
    )

    replace_once(
        path,
        '''        app.state.job_queue = JobQueue(
            store=JobStore(path=os.environ.get("PLATFORM_JOB_STORE", "./cache/platform/jobs.json")),
            max_workers=int(os.environ.get("PLATFORM_JOB_MAX_WORKERS", "2")),
        )''',
        '''        app.state.settings = resolved_settings
        app.state.job_queue = JobQueue(
            store=JobStore(
                path=resolved_settings.platform.job_store,
                allow_fallback=resolved_settings.platform.job_store_fallback,
            ),
            max_workers=resolved_settings.platform.job_max_workers,
        )''',
    )
    replace_once(
        path,
        "        app.state.local_market_data_db_path = _resolve_market_data_duckdb_path()\n",
        "        app.state.local_market_data_db_path = _resolve_market_data_duckdb_path(resolved_settings)\n",
    )
    replace_once(
        path,
        "                allow_origins=_resolve_allowed_origins(allowed_origins),\n",
        "                allow_origins=_resolve_allowed_origins(allowed_origins, resolved_settings),\n",
    )

    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    text = text.replace(
        "_resolve_frontend_dist()",
        "_resolve_frontend_dist(app.state.settings)",
    )
    file_path.write_text(text, encoding="utf-8")


def patch_api_auth() -> None:
    path = "src/platform/api_auth.py"
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    text = text.replace("import os\n", "", 1)
    text = text.replace(
        "from src.core.logger import get_logger\n",
        "from src.core.logger import get_logger\nfrom src.core.settings import PlatformSettings, load_platform_settings\n",
        1,
    )
    file_path.write_text(text, encoding="utf-8")

    regex_once(
        path,
        r'''def load_api_auth_settings\(\) -> ApiAuthSettings:.*?(?=\n\ndef _route\()''',
        '''def load_api_auth_settings(settings: Optional[PlatformSettings] = None) -> ApiAuthSettings:
    """Resolve bootstrap auth from the canonical PlatformSettings object."""
    runtime = settings or load_platform_settings()
    api = runtime.api
    return ApiAuthSettings(
        disabled=api.auth_disabled,
        token=api.token.get_secret_value().strip(),
        subject_id=api.token_subject,
        role=api.token_role.strip().lower(),
        account_group=api.token_account_group,
        strategy_id=api.token_strategy_id,
        account_id=api.token_account_id,
        audit_log_path=api.audit_log,
    )
''',
    )
    replace_once(
        path,
        "    settings = load_api_auth_settings()\n",
        '    settings = load_api_auth_settings(getattr(app.state, "settings", None))\n',
    )


def patch_cli() -> None:
    replace_once(
        "src/cli/main.py",
        '''    def cli():
        """Unified Quant Platform — CLI v2"""
        pass

    # -----------------------------------------------------------------------
    # backtest group''',
        '''    def cli():
        """Unified Quant Platform — CLI v2"""
        pass

    from src.cli.config_commands import config_group
    cli.add_command(config_group)

    # -----------------------------------------------------------------------
    # backtest group''',
    )


if __name__ == "__main__":
    patch_config_manager()
    patch_api_v2()
    patch_api_auth()
    patch_cli()
