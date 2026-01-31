import numpy as np
import pandas as pd

from src.backtest.attribution import (
    compute_var_es,
    compute_tracking_error,
    compute_information_ratio,
    compute_capm_metrics,
    compute_style_exposure,
    compute_concentration_metrics,
    compute_sector_exposure,
)


def test_var_es_basic():
    returns = pd.Series([0.01, -0.02, 0.005, -0.03, 0.02])
    var_95, es_95 = compute_var_es(returns, level=0.95)
    assert var_95 >= 0
    assert es_95 >= 0


def test_capm_metrics():
    rng = np.random.default_rng(42)
    bench = pd.Series(rng.normal(0.0005, 0.01, 200))
    strat = bench * 1.2 + rng.normal(0.0, 0.005, 200)
    metrics = compute_capm_metrics(strat, bench)
    assert metrics["beta"] > 0
    assert "alpha_annual" in metrics


def test_tracking_error_and_info_ratio():
    strat = pd.Series([0.01, 0.0, -0.005, 0.02])
    bench = pd.Series([0.008, 0.002, -0.006, 0.018])
    te = compute_tracking_error(strat, bench, annual_factor=252)
    ir = compute_information_ratio(strat, bench, annual_factor=252)
    assert te >= 0 or np.isnan(te)
    assert not np.isnan(ir)


def test_style_exposure():
    series = pd.Series([0.01, 0.0, -0.005, 0.02, 0.01, -0.01, 0.0, 0.005, 0.002, -0.003] * 3)
    exposure = compute_style_exposure(series, series)
    assert "market_corr" in exposure


def test_concentration_and_sector_exposure():
    weights = {"AAA": 0.4, "BBB": 0.3, "CCC": 0.3}
    sector_map = {"AAA": "Tech", "BBB": "Tech", "CCC": "Finance"}
    conc = compute_concentration_metrics(weights)
    assert conc["max_weight"] >= 0.3
    sector = compute_sector_exposure(weights, sector_map)
    assert "Tech" in sector and "Finance" in sector
