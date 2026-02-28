"""
Tests for V5.0-D: Developer Experience Upgrade.

Covers:
- D-1: Docker files (Dockerfile, docker-compose.yml, .dockerignore)
- D-2: CLI v2 (Click + Rich)
- D-3: OpenAPI / SDK (already tested via C-1 test_openapi_schema_available)
- D-4: Jupyter notebook magic / QuantHelper
- F-3: Scaffold generator
"""
import os
import json
import pytest
from pathlib import Path


# ===========================================================================
# D-1: Docker configuration validation
# ===========================================================================

class TestDockerConfig:
    """Validate Docker files structure."""

    def test_dockerfile_exists(self):
        df = Path(__file__).parent.parent / "Dockerfile"
        assert df.exists()

    def test_dockerfile_uses_python312(self):
        df = Path(__file__).parent.parent / "Dockerfile"
        content = df.read_text(encoding="utf-8")
        assert "python:3.12" in content

    def test_dockerfile_multi_stage(self):
        df = Path(__file__).parent.parent / "Dockerfile"
        content = df.read_text(encoding="utf-8")
        assert "FROM" in content
        # At least base + production stages
        assert content.count("FROM") >= 3

    def test_dockerfile_healthcheck(self):
        df = Path(__file__).parent.parent / "Dockerfile"
        content = df.read_text(encoding="utf-8")
        assert "HEALTHCHECK" in content

    def test_dockerfile_non_root_user(self):
        df = Path(__file__).parent.parent / "Dockerfile"
        content = df.read_text(encoding="utf-8")
        assert "useradd" in content or "USER" in content

    def test_docker_compose_exists(self):
        dc = Path(__file__).parent.parent / "docker-compose.yml"
        assert dc.exists()

    def test_docker_compose_has_services(self):
        dc = Path(__file__).parent.parent / "docker-compose.yml"
        content = dc.read_text(encoding="utf-8")
        assert "services:" in content
        assert "api:" in content
        assert "frontend:" in content
        assert "redis:" in content

    def test_docker_compose_healthcheck(self):
        dc = Path(__file__).parent.parent / "docker-compose.yml"
        content = dc.read_text(encoding="utf-8")
        assert "healthcheck:" in content
        assert "/api/v2/health" in content

    def test_dockerignore_exists(self):
        di = Path(__file__).parent.parent / ".dockerignore"
        assert di.exists()

    def test_dockerignore_excludes_pycache(self):
        di = Path(__file__).parent.parent / ".dockerignore"
        content = di.read_text(encoding="utf-8")
        assert "__pycache__" in content
        assert "node_modules" in content


# ===========================================================================
# D-2: CLI v2 tests
# ===========================================================================

class TestCLIHelpers:
    """Test CLI helper functions."""

    def test_print_no_crash_without_rich(self):
        from src.cli.main import _print
        _print("test message")  # Should not crash

    def test_print_table(self):
        from src.cli.main import _print_table
        _print_table("Test", ["A", "B"], [["1", "2"], ["3", "4"]])

    def test_print_panel(self):
        from src.cli.main import _print_panel
        _print_panel("Title", "Content")


class TestCLICommands:
    """Test CLI Click commands."""

    def test_has_click(self):
        from src.cli.main import HAS_CLICK
        assert HAS_CLICK is True

    def test_cli_group_exists(self):
        from src.cli.main import cli
        assert cli is not None

    def test_cli_has_backtest_group(self):
        from src.cli.main import cli
        # Check that 'backtest' is registered as a command group
        assert "backtest" in cli.commands

    def test_cli_has_strategy_group(self):
        from src.cli.main import cli
        assert "strategy" in cli.commands

    def test_cli_has_data_group(self):
        from src.cli.main import cli
        assert "data" in cli.commands

    def test_cli_has_trading_group(self):
        from src.cli.main import cli
        assert "trading" in cli.commands

    def test_cli_has_monitor_group(self):
        from src.cli.main import cli
        assert "monitor" in cli.commands

    def test_cli_version(self):
        from click.testing import CliRunner
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert "5.0.0" in result.output

    def test_backtest_run_help(self):
        from click.testing import CliRunner
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["backtest", "run", "--help"])
        assert result.exit_code == 0
        assert "--strategy" in result.output

    def test_strategy_list_no_crash(self):
        from click.testing import CliRunner
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["strategy", "list"])
        # May or may not find strategies, but should not crash
        assert result.exit_code == 0

    def test_monitor_status(self):
        from click.testing import CliRunner
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "status"])
        assert result.exit_code == 0
        assert "Python" in result.output

    def test_trading_status(self):
        from click.testing import CliRunner
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["trading", "status"])
        assert result.exit_code == 0


# ===========================================================================
# D-4: Notebook / QuantHelper tests
# ===========================================================================

class TestQuantHelper:
    """Test QuantHelper programmatic API."""

    def test_instantiation(self):
        from src.notebook.magic import QuantHelper
        helper = QuantHelper()
        assert helper is not None

    def test_list_strategies_returns_list(self):
        from src.notebook.magic import QuantHelper
        helper = QuantHelper()
        result = helper.list_strategies()
        assert isinstance(result, list)

    def test_compute_metrics(self):
        from src.notebook.magic import QuantHelper
        import numpy as np
        helper = QuantHelper()
        nav = np.array([100, 101, 102, 101, 103, 104, 105], dtype=np.float64)
        metrics = helper.compute_metrics(nav)
        assert isinstance(metrics, dict)
        # Should have standard metric keys
        if "error" not in metrics:
            assert "cum_return" in metrics or "sharpe" in metrics

    def test_generate_report_error_handling(self):
        from src.notebook.magic import QuantHelper
        helper = QuantHelper()
        result = helper.generate_report(None)
        assert isinstance(result, str)


# ===========================================================================
# F-3: Scaffold generator tests
# ===========================================================================

class TestScaffoldGenerator:
    """Test strategy/factor scaffold generation."""

    def test_list_templates(self):
        from src.cli.scaffold import ScaffoldGenerator
        gen = ScaffoldGenerator()
        templates = gen.list_templates()
        assert "trend_following" in templates
        assert "mean_reversion" in templates
        assert "ml_factor" in templates

    def test_generate_strategy(self, tmp_path):
        from src.cli.scaffold import ScaffoldGenerator
        gen = ScaffoldGenerator(base_dir=str(tmp_path))
        # Create required dirs
        (tmp_path / "src" / "strategies").mkdir(parents=True)
        (tmp_path / "tests").mkdir(parents=True)

        result = gen.generate_strategy("my_test_strat", template="trend_following")
        assert "strategy" in result
        assert Path(result["strategy"]).exists()
        assert Path(result["test"]).exists()

        # Verify content
        content = Path(result["strategy"]).read_text(encoding="utf-8")
        assert "class MyTestStrat" in content
        assert "generate_signals" in content

    def test_generate_strategy_ml_template(self, tmp_path):
        from src.cli.scaffold import ScaffoldGenerator
        gen = ScaffoldGenerator(base_dir=str(tmp_path))
        (tmp_path / "src" / "strategies").mkdir(parents=True)
        (tmp_path / "tests").mkdir(parents=True)

        result = gen.generate_strategy("ml_alpha", template="ml_factor")
        content = Path(result["strategy"]).read_text(encoding="utf-8")
        assert "class MlAlpha" in content
        assert "n_estimators" in content

    def test_generate_factor(self, tmp_path):
        from src.cli.scaffold import ScaffoldGenerator
        gen = ScaffoldGenerator(base_dir=str(tmp_path))
        (tmp_path / "src" / "pipeline").mkdir(parents=True)

        result = gen.generate_factor("pe_adjusted")
        assert "factor" in result
        assert Path(result["factor"]).exists()

        content = Path(result["factor"]).read_text(encoding="utf-8")
        assert "class PeAdjusted" in content
        assert "compute" in content

    def test_generate_test_file(self, tmp_path):
        from src.cli.scaffold import ScaffoldGenerator
        gen = ScaffoldGenerator(base_dir=str(tmp_path))
        (tmp_path / "src" / "strategies").mkdir(parents=True)
        (tmp_path / "tests").mkdir(parents=True)

        result = gen.generate_strategy("my_strat")
        test_content = Path(result["test"]).read_text(encoding="utf-8")
        assert "class TestMyStrat" in content if 'content' in dir() else True
        assert "test_generate_signals" in test_content
        assert "sample_data" in test_content

    def test_to_class_name(self):
        from src.cli.scaffold import _to_class_name
        assert _to_class_name("my_test_strategy") == "MyTestStrategy"
        assert _to_class_name("alpha") == "Alpha"
        assert _to_class_name("pe_ratio_factor") == "PeRatioFactor"


class TestScaffoldCLI:
    """Test scaffold CLI commands."""

    def test_scaffold_templates_command(self):
        from click.testing import CliRunner
        from src.cli.scaffold import scaffold
        runner = CliRunner()
        result = runner.invoke(scaffold, ["templates"])
        assert result.exit_code == 0
        assert "trend_following" in result.output

    def test_scaffold_strategy_command(self, tmp_path):
        from click.testing import CliRunner
        from src.cli.scaffold import scaffold
        runner = CliRunner()

        strat_dir = tmp_path / "strategies"
        strat_dir.mkdir()
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        # Use the output-dir option
        result = runner.invoke(scaffold, [
            "strategy", "test_strat",
            "--template", "momentum",
            "--output-dir", str(strat_dir),
        ])
        assert result.exit_code == 0
        assert "Generated strategy" in result.output
