"""Structural tests for ``src.engines`` (V6 Phase 3)."""

from __future__ import annotations

import importlib

import pytest


ENGINE_SUBPACKAGES = (
    "src.engines.data",
    "src.engines.execution",
    "src.engines.risk",
    "src.engines.portfolio",
    "src.engines.backtest",
    "src.engines.research",
    "src.engines.report",
)


def test_engines_top_level_imports_cleanly() -> None:
    """``import src.engines`` must succeed without loading subpackages."""
    mod = importlib.import_module("src.engines")
    assert set(mod.__all__) == {
        "data",
        "execution",
        "risk",
        "portfolio",
        "backtest",
        "research",
        "report",
    }


@pytest.mark.parametrize("dotted", ENGINE_SUBPACKAGES)
def test_engine_subpackage_imports(dotted: str) -> None:
    """Every engine subpackage must import without raising."""
    mod = importlib.import_module(dotted)
    assert isinstance(mod.__all__, tuple)
    assert mod.__all__, f"{dotted} should export at least one symbol"


@pytest.mark.parametrize("dotted", ENGINE_SUBPACKAGES)
def test_engine_all_resolves(dotted: str) -> None:
    """Every name listed in ``__all__`` must resolve on the subpackage."""
    mod = importlib.import_module(dotted)
    for name in mod.__all__:
        assert hasattr(mod, name), f"{dotted}.{name} is in __all__ but is missing"
        assert getattr(mod, name) is not None


def test_data_engine_reexports_are_identity() -> None:
    from src.data_sources.providers import DataProvider as Original
    from src.engines.data import DataProvider as Reexport

    assert Reexport is Original


def test_execution_engine_reexports_are_identity() -> None:
    from src.core.order_manager import OrderManager as Original
    from src.engines.execution import OrderManager as Reexport
    from src.simulation.matching_engine import MatchingEngine as MEOrig
    from src.engines.execution import MatchingEngine as MEReexport

    assert Reexport is Original
    assert MEReexport is MEOrig


def test_risk_engine_reexports_are_identity() -> None:
    from src.core.risk_manager_v2 import RiskManagerV2 as Original
    from src.engines.risk import RiskManagerV2 as Reexport

    assert Reexport is Original


def test_portfolio_engine_reexports_are_identity() -> None:
    from src.core.portfolio import PortfolioManager as Original
    from src.engines.portfolio import PortfolioManager as Reexport

    assert Reexport is Original


def test_backtest_engine_reexports_are_identity() -> None:
    from src.backtest.engine import BacktestEngine as Original
    from src.engines.backtest import BacktestEngine as Reexport

    assert Reexport is Original


def test_research_engine_reexports_are_identity() -> None:
    from src.mlops.model_registry import ModelRegistry as Original
    from src.engines.research import ModelRegistry as Reexport

    assert Reexport is Original


def test_report_engine_reexports_are_identity() -> None:
    from src.backtest.report_generator import InteractiveReportGenerator as Original
    from src.engines.report import InteractiveReportGenerator as Reexport

    assert Reexport is Original


def test_risk_v5_result_aliased_to_avoid_dto_collision() -> None:
    """The V5 ``risk_manager_v2.RiskCheckResult`` is exposed under an
    alias so it does not shadow the V6 SSOT DTO of the same name."""
    from src.core.contracts.dto import RiskCheckResult as ContractDTO
    from src.core.risk_manager_v2 import RiskCheckResult as V5Outcome
    from src.engines.risk import RiskCheckOutcome

    assert RiskCheckOutcome is V5Outcome
    assert RiskCheckOutcome is not ContractDTO
