import pandas as pd
import pytest

from src.optimizer.combo_optimizer import (
    PortfolioResult,
    _weight_grid,
    load_nav_series,
    optimize_portfolio,
)


def _nav_from_returns(returns):
    return (1 + pd.Series(returns)).cumprod()


def test_optimize_prefers_higher_sharpe():
    nav_map = {
        "slow": _nav_from_returns([0.001] * 40),
        "fast": _nav_from_returns([0.003, -0.002] * 20),
    }
    res = optimize_portfolio(nav_map, step=0.5, objective="sharpe")
    assert isinstance(res, PortfolioResult)
    # 仅有 (1,0)、(0.5,0.5)、(0,1) 三种组合，稳定策略应获胜
    assert res.weights["slow"] >= 0.5
    assert res.stats["sharpe"] > 0


def test_optimize_handles_other_objectives():
    nav_map = {
        "low_dd": _nav_from_returns([0.0, 0.001, 0.0, 0.001]),
        "high_dd": _nav_from_returns([0.02, -0.05, 0.02, 0.01]),
    }
    res_return = optimize_portfolio(nav_map, step=0.5, objective="return")
    assert res_return.weights  # picks any feasible combo

    res_dd = optimize_portfolio(nav_map, step=0.5, objective="drawdown")
    assert res_dd.stats["max_drawdown"] >= res_return.stats["max_drawdown"]


def test_load_nav_series_recovers_nav_column(tmp_path):
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "nav": [1.0, 1.01, 1.015, 1.02, 1.018],
        }
    )
    path = tmp_path / "nav.csv"
    df.to_csv(path, index=False)

    nav = load_nav_series(str(path))
    assert nav.iloc[0] == 1.0
    assert len(nav) == 5


def test_load_nav_series_missing_column(tmp_path):
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=3), "price": [1, 2, 3]})
    path = tmp_path / "broken.csv"
    df.to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_nav_series(str(path))


def test_load_nav_series_fallback_index(tmp_path):
    df = pd.DataFrame({"x": ["bad", "index"], "nav": [1.0, 1.1]})
    path = tmp_path / "nav2.csv"
    df.to_csv(path, index=False)
    nav = load_nav_series(str(path))
    assert isinstance(nav.index, pd.RangeIndex)


def test_optimize_guardrails_and_invalid_objective(tmp_path):
    nav_map = {
        "a": _nav_from_returns([0.0, 0.01, -0.005]),
        "b": _nav_from_returns([0.0, 0.005, 0.002]),
    }
    with pytest.raises(ValueError):
        optimize_portfolio({}, step=0.5)
    with pytest.raises(ValueError):
        optimize_portfolio(nav_map, step=0)
    with pytest.raises(ValueError):
        optimize_portfolio(nav_map, step=1.5)
    with pytest.raises(ValueError):
        optimize_portfolio(nav_map, step=1.0, objective="unknown")

    with pytest.raises(ValueError):
        next(_weight_grid(2, 0, False, 1.0))
