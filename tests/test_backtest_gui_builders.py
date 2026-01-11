import sys

import pytest

from scripts.backtest_gui import (
    AutoConfig,
    ComboConfig,
    CommandBuilder,
    GridConfig,
    RunConfig,
)


def test_run_command_builder_includes_fee_and_benchmark_source():
    cfg = RunConfig(
        strategy="ema",
        symbols=["600519.SH"],
        start="2023-01-01",
        end="2023-06-01",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="yfinance",
        params_json='{"fast":12}',
        cash="100000",
        commission="0.0002",
        slippage="0.0003",
        adj="qfq",
        out_dir="./out",
        cache_dir="./cache_test",
        plot=True,
        fee_config="cn_stock",
        fee_params='{"commission_rate":0.0001}',
    )

    cmd = CommandBuilder.build_run(cfg)

    assert cmd[:3] == [sys.executable, "unified_backtest_framework.py", "run"]
    assert cmd[cmd.index("--strategy") + 1] == "ema"
    assert cmd[cmd.index("--benchmark_source") + 1] == "yfinance"
    assert "--plot" in cmd
    assert cmd[cmd.index("--fee-config") + 1] == "cn_stock"
    assert "--fee-params" in cmd
    assert cfg.cache_dir in cmd


def test_grid_command_builder_rejects_bad_json():
    cfg = GridConfig(
        strategy="macd",
        symbols=["000001.SZ"],
        start="2023-01-01",
        end="2023-03-01",
        source="akshare",
        grid_json="{bad}",
        cache_dir="./cache_grid",
    )

    with pytest.raises(ValueError):
        CommandBuilder.build_grid(cfg)


def test_auto_command_builder_flags_scope_and_benchmark_source():
    cfg = AutoConfig(
        symbols=["600519.SH"],
        start="2023-01-01",
        end="2023-02-01",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        strategies=["ema", "macd"],
        top_n="3",
        min_trades="2",
        cache_dir="./cache_auto",
        workers="2",
        hot_only=True,
        use_benchmark_regime=True,
        regime_scope="all",
    )

    cmd = CommandBuilder.build_auto(cfg)

    assert "--hot_only" in cmd
    assert "--use_benchmark_regime" in cmd
    assert cmd[cmd.index("--regime_scope") + 1] == "all"
    assert cmd[cmd.index("--benchmark_source") + 1] == "akshare"
    # strategies are appended correctly
    assert cmd[cmd.index("--strategies") + 1 : cmd.index("--strategies") + 3] == ["ema", "macd"]


def test_combo_command_builder_handles_allow_short_and_output(tmp_path):
    nav1 = tmp_path / "a.csv"
    nav2 = tmp_path / "b.csv"
    nav1.write_text("nav\n1\n1.01\n")
    nav2.write_text("nav\n1\n0.99\n")

    cfg = ComboConfig(
        navs=[str(nav1), str(nav2)],
        objective="return",
        step="0.5",
        allow_short=True,
        max_weight="1.0",
        risk_free="0.0",
        out=str(tmp_path / "combo.csv"),
    )

    cmd = CommandBuilder.build_combo(cfg)
    assert "combo" in cmd
    assert "--allow_short" in cmd
    assert cmd[cmd.index("--objective") + 1] == "return"
    assert cmd[cmd.index("--out") + 1].endswith("combo.csv")
