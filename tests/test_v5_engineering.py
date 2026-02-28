"""
Tests for V5.0-F: Engineering Efficiency Upgrade.

Covers:
- F-1: Exception hierarchy completeness and error codes
- F-2: pyproject.toml (already tested in V5.0-C)
- F-3: Scaffold generator (already tested in V5.0-D)
- F-4: MkDocs configuration
- GitHub Actions CI workflow validation
"""
import os
import pytest
from pathlib import Path


# ===========================================================================
# F-1: Exception system completeness tests
# ===========================================================================

class TestExceptionHierarchy:
    """Validate exception hierarchy is complete and consistent."""

    def test_base_error_has_error_code(self):
        from src.core.exceptions import QuantBaseError
        err = QuantBaseError("test")
        assert err.error_code == "QUANT_ERROR"
        assert err.message == "test"

    def test_base_error_to_dict(self):
        from src.core.exceptions import QuantBaseError
        err = QuantBaseError("test", context={"key": "val"})
        d = err.to_dict()
        assert d["error_code"] == "QUANT_ERROR"
        assert d["message"] == "test"
        assert d["context"]["key"] == "val"
        assert "timestamp" in d

    def test_all_error_categories_exist(self):
        from src.core import exceptions as exc
        categories = [
            exc.ConfigurationError,
            exc.DataError,
            exc.StrategyError,
            exc.OrderError,
            exc.GatewayError,
            exc.RiskError,
            exc.BacktestError,
        ]
        for cls in categories:
            assert issubclass(cls, exc.QuantBaseError)

    def test_data_errors(self):
        from src.core.exceptions import (
            DataProviderError, DataValidationError,
            DataNotFoundError, InsufficientDataError,
        )
        e1 = DataProviderError("akshare", "timeout")
        assert "akshare" in str(e1)

        e2 = DataNotFoundError("600519.SH", "2024-01-01", "2024-12-31")
        assert "600519.SH" in str(e2)
        assert e2.error_code == "DATA_NOT_FOUND"

        e3 = InsufficientDataError("600519.SH", 100, 50)
        assert "100" in str(e3) and "50" in str(e3)

    def test_strategy_errors(self):
        from src.core.exceptions import (
            StrategyNotFoundError, StrategyInitializationError,
            StrategyExecutionError, StrategyValidationError,
        )
        e = StrategyNotFoundError("macd", available=["rsi", "boll"])
        assert "macd" in str(e)
        assert e.error_code == "STRATEGY_NOT_FOUND"

    def test_order_errors(self):
        from src.core.exceptions import (
            OrderValidationError, OrderRejectedError,
            InsufficientFundsError, DuplicateOrderError,
        )
        e = InsufficientFundsError(10000, 5000, symbol="600519.SH")
        assert e.error_code == "INSUFFICIENT_FUNDS"

    def test_gateway_errors(self):
        from src.core.exceptions import (
            GatewayConnectionError, GatewayTimeoutError,
            GatewayAuthError, GatewayNotReadyError,
        )
        e = GatewayTimeoutError("xtp", "login", 30.0)
        assert e.error_code == "GATEWAY_TIMEOUT"
        assert "30" in str(e)

    def test_risk_errors(self):
        from src.core.exceptions import (
            RiskLimitExceeded, PositionLimitExceeded, DrawdownLimitExceeded,
        )
        e = DrawdownLimitExceeded(0.15, 0.10)
        assert e.error_code == "DRAWDOWN_LIMIT_EXCEEDED"

    def test_classify_exception(self):
        from src.core.exceptions import (
            classify_exception, DataError, StrategyError,
            OrderError, GatewayError, RiskError,
        )
        assert classify_exception(DataError("x")) == "data"
        assert classify_exception(StrategyError("x")) == "strategy"
        assert classify_exception(OrderError("x")) == "order"
        assert classify_exception(GatewayError("x")) == "gateway"
        assert classify_exception(RiskError("x")) == "risk"
        assert classify_exception(ValueError("x")) == "unknown"

    def test_wrap_exception(self):
        from src.core.exceptions import wrap_exception, QuantBaseError, DataError
        # Wrapping a standard exception
        orig = ValueError("bad value")
        wrapped = wrap_exception(orig, DataError)
        assert isinstance(wrapped, DataError)
        assert wrapped.__cause__ is orig

        # Wrapping a QuantBaseError returns it unchanged
        q_err = QuantBaseError("already wrapped")
        assert wrap_exception(q_err) is q_err

    def test_error_code_map(self):
        from src.core.exceptions import ERROR_CODE_MAP, get_exception_by_code
        assert len(ERROR_CODE_MAP) > 10  # Should have many error codes
        cls = get_exception_by_code("DATA_NOT_FOUND")
        assert cls is not None
        assert get_exception_by_code("NONEXISTENT") is None

    def test_exception_chaining(self):
        from src.core.exceptions import QuantBaseError
        cause = ConnectionError("network down")
        err = QuantBaseError("connection failed", cause=cause)
        assert err.__cause__ is cause


class TestPerformanceModule:
    """Test performance module utilities."""

    def test_import_performance_module(self):
        from src.core.performance import cached, profile, batch_process
        assert callable(cached)
        assert callable(profile)
        assert callable(batch_process)

    def test_cached_decorator(self):
        from src.core.performance import cached
        call_count = 0

        @cached(ttl=60)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive(5) == 10
        assert expensive(5) == 10  # Should use cache
        assert call_count == 1

    def test_batch_process(self):
        from src.core.performance import batch_process
        results = batch_process(
            items=list(range(10)),
            process_func=lambda x: x * 2,
            batch_size=3,
        )
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]


# ===========================================================================
# F-4: MkDocs configuration tests
# ===========================================================================

class TestMkDocsConfig:
    """Validate mkdocs.yml structure."""

    @pytest.fixture
    def mkdocs_config(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        path = Path(__file__).parent.parent / "mkdocs.yml"
        if not path.exists():
            pytest.skip("mkdocs.yml not found")
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_site_name(self, mkdocs_config):
        assert mkdocs_config["site_name"] == "Unified Quant Platform"

    def test_theme_material(self, mkdocs_config):
        assert mkdocs_config["theme"]["name"] == "material"

    def test_theme_language_zh(self, mkdocs_config):
        assert mkdocs_config["theme"]["language"] == "zh"

    def test_nav_structure(self, mkdocs_config):
        nav = mkdocs_config["nav"]
        nav_titles = [list(item.keys())[0] if isinstance(item, dict) else item for item in nav]
        assert "Home" in nav_titles
        assert "Getting Started" in nav_titles
        assert "API Reference" in nav_titles

    def test_search_plugin(self, mkdocs_config):
        plugins = mkdocs_config.get("plugins", [])
        plugin_names = []
        for p in plugins:
            if isinstance(p, str):
                plugin_names.append(p)
            elif isinstance(p, dict):
                plugin_names.extend(p.keys())
        assert "search" in plugin_names

    def test_markdown_extensions(self, mkdocs_config):
        exts = mkdocs_config.get("markdown_extensions", [])
        ext_names = []
        for e in exts:
            if isinstance(e, str):
                ext_names.append(e)
            elif isinstance(e, dict):
                ext_names.extend(e.keys())
        assert "admonition" in ext_names
        assert "tables" in ext_names

    def test_dark_mode_support(self, mkdocs_config):
        palette = mkdocs_config["theme"]["palette"]
        schemes = [p.get("scheme") for p in palette]
        assert "slate" in schemes  # dark mode
        assert "default" in schemes  # light mode


# ===========================================================================
# GitHub Actions CI workflow tests
# ===========================================================================

class TestCIWorkflow:
    """Validate GitHub Actions CI workflow."""

    @pytest.fixture
    def ci_config(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        if not path.exists():
            pytest.skip("ci.yml not found")
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_workflow_name(self, ci_config):
        assert "name" in ci_config

    def test_trigger_on_push_and_pr(self, ci_config):
        # PyYAML parses YAML 'on:' key as boolean True
        triggers = ci_config.get(True, ci_config.get("on", {}))
        assert "push" in triggers
        assert "pull_request" in triggers

    def test_test_job_exists(self, ci_config):
        jobs = ci_config.get("jobs", {})
        assert "test" in jobs

    def test_test_uses_python312(self, ci_config):
        test_job = ci_config["jobs"]["test"]
        matrix = test_job.get("strategy", {}).get("matrix", {})
        versions = matrix.get("python-version", [])
        assert "3.12" in [str(v) for v in versions]

    def test_security_scan_job(self, ci_config):
        jobs = ci_config.get("jobs", {})
        assert "security-scan" in jobs

    def test_code_quality_job(self, ci_config):
        jobs = ci_config.get("jobs", {})
        assert "code-quality" in jobs

    def test_uses_checkout_action(self, ci_config):
        test_job = ci_config["jobs"]["test"]
        steps = test_job.get("steps", [])
        has_checkout = any("checkout" in str(s.get("uses", "")) for s in steps)
        assert has_checkout

    def test_multi_os_matrix(self, ci_config):
        test_job = ci_config["jobs"]["test"]
        matrix = test_job.get("strategy", {}).get("matrix", {})
        os_list = matrix.get("os", [])
        assert len(os_list) >= 2  # At least ubuntu + windows
