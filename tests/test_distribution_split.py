"""V6 Phase 7 distribution split packaging tests."""
from __future__ import annotations

from pathlib import Path
import tomllib


PACKAGE_ROOT = Path("packages")
EXPECTED_DISTRIBUTIONS = {
    "quant_platform_core": "quant-platform-core",
    "quant_platform_sdk": "quant-platform-sdk",
    "quant_platform_adapters_cn": "quant-platform-adapters-cn",
    "quant_platform_ml": "quant-platform-ml",
    "quant_platform_web": "quant-platform-web",
    "quant_platform_cli": "quant-platform-cli",
}


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_distribution_pyprojects_exist_and_use_expected_names():
    for directory, project_name in EXPECTED_DISTRIBUTIONS.items():
        pyproject = PACKAGE_ROOT / directory / "pyproject.toml"
        assert pyproject.exists(), f"missing {pyproject}"
        data = _load_pyproject(pyproject)
        assert data["project"]["name"] == project_name
        assert data["project"]["version"] == "5.0.0"
        assert data["project"]["requires-python"] == ">=3.10"


def test_distribution_dependency_graph_is_layered():
    sdk = _load_pyproject(PACKAGE_ROOT / "quant_platform_sdk" / "pyproject.toml")
    adapters = _load_pyproject(PACKAGE_ROOT / "quant_platform_adapters_cn" / "pyproject.toml")
    ml = _load_pyproject(PACKAGE_ROOT / "quant_platform_ml" / "pyproject.toml")
    web = _load_pyproject(PACKAGE_ROOT / "quant_platform_web" / "pyproject.toml")
    cli = _load_pyproject(PACKAGE_ROOT / "quant_platform_cli" / "pyproject.toml")

    assert "quant-platform-core==5.0.0" in sdk["project"]["dependencies"]
    assert "quant-platform-core==5.0.0" in adapters["project"]["dependencies"]
    assert "quant-platform-core==5.0.0" in ml["project"]["dependencies"]
    assert "quant-platform-adapters-cn==5.0.0" in web["project"]["dependencies"]
    assert "quant-platform-sdk==5.0.0" in cli["project"]["dependencies"]
    assert web["project"]["scripts"]["quant-platform-api"] == "quant_platform_web.cli:main"
    assert cli["project"]["scripts"]["quant-platform"] == "src.cli.main:main"
    assert cli["project"]["scripts"]["quant-backtest"] == "quant_platform_cli.backtest:main"


def test_root_package_includes_distribution_facades():
    pyproject = _load_pyproject(Path("pyproject.toml"))
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "src*" in include
    assert "quant_platform_*" in include


def test_distribution_facades_import_without_optional_sdks():
    import quant_platform_adapters_cn
    import quant_platform_cli
    import quant_platform_core
    import quant_platform_ml
    import quant_platform_sdk
    import quant_platform_web

    assert quant_platform_core.__contract_version__ == "0.1.0"
    assert hasattr(quant_platform_sdk, "PluginRegistry")
    assert "broker" in quant_platform_adapters_cn.ADAPTER_GROUPS
    assert "qlib" in quant_platform_ml.ML_GROUPS
    assert callable(quant_platform_cli.main)
    assert quant_platform_web.FRONTEND_DIR.name == "frontend"


def test_distribution_split_docs_are_discoverable():
    packages_readme = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    for import_name, project_name in EXPECTED_DISTRIBUTIONS.items():
        assert project_name in packages_readme
        assert import_name in readme
    assert "Distribution Split" in packages_readme
    assert "Distribution packages" in readme
