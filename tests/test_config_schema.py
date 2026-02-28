"""
Tests for config schema validation (A-4).

Covers:
- GlobalConfig default construction and field access
- Validation of nested model constraints
- Extra-field rejection (extra = "forbid")
- LiveTradingConfig, RealtimeDataConfig, PortfolioConfig validators
- GlobalConfig.validate_all() cross-field checks
- ConfigManager path-based load / save / reload round-trip
- ConfigManager environment-variable override
"""
import os
import pytest
import yaml
from pydantic import ValidationError

from src.core.config import (
    GlobalConfig,
    LiveTradingConfig,
    RealtimeDataConfig,
    PortfolioConfig,
    BacktestConfig,
    ConfigManager,
)


# ---------------------------------------------------------------------------
# TestGlobalConfig
# ---------------------------------------------------------------------------

class TestGlobalConfig:
    def test_default_config_valid(self):
        """Default GlobalConfig must pass construction with sane defaults."""
        config = GlobalConfig()
        assert config.backtest.initial_cash > 0
        assert config.live_trading.broker == "xtp"
        assert config.realtime_data.provider == "simulation"
        assert config.portfolio.optimization_objective == "sharpe"

    def test_invalid_commission_rejected(self):
        """BacktestConfig.commission > 0.1 (10%) must raise ValidationError."""
        with pytest.raises(ValidationError):
            BacktestConfig(commission=0.2)

    def test_zero_commission_accepted(self):
        """A commission of exactly 0.0 is on the boundary and must be accepted."""
        cfg = BacktestConfig(commission=0.0)
        assert cfg.commission == 0.0

    def test_extra_fields_rejected(self):
        """GlobalConfig has extra='forbid'; an unknown top-level key must raise."""
        with pytest.raises(ValidationError):
            GlobalConfig(unknown_field="value")

    def test_live_trading_config_validation(self):
        """Valid broker values are accepted; invalid ones raise ValidationError."""
        # Valid
        cfg = LiveTradingConfig(broker="xtp", account_id="TEST123")
        assert cfg.broker == "xtp"
        assert cfg.account_id == "TEST123"

        # Invalid broker name
        with pytest.raises(ValidationError):
            LiveTradingConfig(broker="unknown_broker")

    def test_live_trading_config_paper_broker_accepted(self):
        """'paper' is a valid broker value."""
        cfg = LiveTradingConfig(broker="paper")
        assert cfg.broker == "paper"

    def test_live_trading_max_orders_positive(self):
        """max_orders_per_second must be > 0."""
        with pytest.raises(ValidationError):
            LiveTradingConfig(max_orders_per_second=0.0)
        with pytest.raises(ValidationError):
            LiveTradingConfig(max_orders_per_second=-5.0)

    def test_live_trading_extra_fields_rejected(self):
        """LiveTradingConfig also has extra='forbid'."""
        with pytest.raises(ValidationError):
            LiveTradingConfig(nonexistent_key="oops")

    def test_realtime_data_config_validation(self):
        """Valid providers accepted; invalid ones and bad interval values rejected."""
        cfg = RealtimeDataConfig(provider="akshare", interval_seconds=5.0)
        assert cfg.provider == "akshare"

        # Invalid provider
        with pytest.raises(ValidationError):
            RealtimeDataConfig(provider="invalid_provider")

        # Non-positive interval
        with pytest.raises(ValidationError):
            RealtimeDataConfig(interval_seconds=-1)

        with pytest.raises(ValidationError):
            RealtimeDataConfig(interval_seconds=0)

    def test_realtime_data_default_bar_intervals(self):
        """Default bar_intervals list must not be shared across instances."""
        cfg1 = RealtimeDataConfig()
        cfg2 = RealtimeDataConfig()
        assert cfg1.bar_intervals == [1, 5]
        cfg1.bar_intervals.append(15)
        assert cfg2.bar_intervals == [1, 5], "default_factory must create independent lists"

    def test_portfolio_config_default_weights(self):
        """Default max_weight_per_strategy must be in (0, 1]."""
        cfg = PortfolioConfig()
        assert 0 < cfg.max_weight_per_strategy <= 1.0
        assert cfg.min_weight_per_strategy > 0

    def test_portfolio_config_invalid_objective(self):
        """Unknown optimization_objective must raise ValidationError."""
        with pytest.raises(ValidationError):
            PortfolioConfig(optimization_objective="invalid")

    def test_portfolio_max_weight_boundary(self):
        """max_weight_per_strategy=0 should be rejected (must be > 0)."""
        with pytest.raises(ValidationError):
            PortfolioConfig(max_weight_per_strategy=0.0)
        # Exactly 1.0 is allowed
        cfg = PortfolioConfig(max_weight_per_strategy=1.0)
        assert cfg.max_weight_per_strategy == 1.0

    def test_validate_all_clean(self):
        """Default config should produce an empty (or warnings-only) list."""
        config = GlobalConfig()
        warnings = config.validate_all()
        assert isinstance(warnings, list)
        # Default commission (0.001) is <= 0.01, so no commission warning
        assert not any("commission" in w for w in warnings)
        # Default live_trading.enabled is False, so no account_id warning
        assert not any("account_id" in w for w in warnings)

    def test_validate_all_detects_live_trading_missing_account(self):
        """Enabling live trading without account_id should produce a warning."""
        config = GlobalConfig()
        config.live_trading.enabled = True
        config.live_trading.account_id = ""
        warnings = config.validate_all()
        assert any("account_id" in w for w in warnings)

    def test_validate_all_detects_high_commission(self):
        """commission > 0.01 should trigger a warning from validate_all."""
        config = GlobalConfig()
        # commission=0.05 (5%) is valid per BacktestConfig (le=0.1) but high per validate_all
        config.backtest.commission = 0.05
        warnings = config.validate_all()
        assert any("commission" in w for w in warnings)

    def test_validate_all_detects_portfolio_weight_overflow(self):
        """min_weight * num_strategies > 1.0 should warn."""
        config = GlobalConfig()
        # 25 strategies * 0.05 = 1.25 > 1.0
        config.portfolio.strategies = [f"strat_{i}" for i in range(25)]
        config.portfolio.min_weight_per_strategy = 0.05
        warnings = config.validate_all()
        assert any("min_weight_per_strategy" in w for w in warnings)

    def test_validate_all_returns_list(self):
        """validate_all() must always return a list, never None."""
        config = GlobalConfig()
        result = config.validate_all()
        assert result is not None
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# TestConfigManager
# ---------------------------------------------------------------------------

class TestConfigManager:
    def test_load_from_yaml(self, tmp_path):
        """ConfigManager should load a minimal YAML file correctly."""
        yaml_content = {
            "backtest": {"initial_cash": 500000},
            "live_trading": {"enabled": False, "broker": "paper"},
        }
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(yaml_content))

        manager = ConfigManager(str(cfg_file))
        config = manager.load()
        assert config.backtest.initial_cash == 500000
        assert config.live_trading.broker == "paper"

    def test_load_missing_file_uses_defaults(self, tmp_path):
        """If the file does not exist, load() must fall back to defaults."""
        missing = str(tmp_path / "does_not_exist.yaml")
        manager = ConfigManager(missing)
        config = manager.load()
        # Must return a valid GlobalConfig with defaults
        assert config.backtest.initial_cash == 100000.0

    def test_save_and_reload(self, tmp_path):
        """Saving a config and reloading it must preserve field values."""
        config = GlobalConfig()
        config.live_trading.enabled = False
        config.realtime_data.provider = "akshare"

        cfg_file = tmp_path / "config_saved.yaml"
        manager = ConfigManager(str(cfg_file))
        manager.save(config)

        manager2 = ConfigManager(str(cfg_file))
        loaded = manager2.load()
        assert loaded.realtime_data.provider == "akshare"

    def test_save_without_path_raises(self):
        """Calling save() on a ConfigManager with no path must raise ValueError."""
        manager = ConfigManager()
        with pytest.raises(ValueError, match="config_path"):
            manager.save(GlobalConfig())

    def test_save_creates_yaml_file(self, tmp_path):
        """save() must create the YAML file on disk."""
        cfg_file = tmp_path / "sub" / "config.yaml"
        manager = ConfigManager(str(cfg_file))
        manager.save(GlobalConfig())
        assert cfg_file.exists()

    def test_env_override(self, monkeypatch, tmp_path):
        """BACKTEST_INITIAL_CASH env var must override backtest.initial_cash."""
        monkeypatch.setenv("BACKTEST_INITIAL_CASH", "999999")
        manager = ConfigManager()
        config = manager.load()
        assert config.backtest.initial_cash == 999999

    def test_env_override_log_level(self, monkeypatch):
        """BACKTEST_LOG_LEVEL env var must override logging.level."""
        monkeypatch.setenv("BACKTEST_LOG_LEVEL", "DEBUG")
        manager = ConfigManager()
        config = manager.load()
        assert config.logging.level == "DEBUG"

    def test_config_property_returns_defaults_when_not_loaded(self):
        """Accessing .config before load() must still give a valid GlobalConfig."""
        manager = ConfigManager()
        assert isinstance(manager.config, GlobalConfig)
        assert manager.config.backtest.initial_cash == 100000.0

    def test_load_from_file_classmethod(self, tmp_path):
        """load_from_file classmethod must return a ConfigManager with loaded config."""
        yaml_content = {"backtest": {"initial_cash": 123456}}
        cfg_file = tmp_path / "cfg.yaml"
        cfg_file.write_text(yaml.dump(yaml_content))

        mgr = ConfigManager.load_from_file(str(cfg_file))
        assert mgr.config.backtest.initial_cash == 123456

    def test_load_from_file_missing_returns_defaults(self, tmp_path):
        """load_from_file with a missing path must silently use defaults."""
        mgr = ConfigManager.load_from_file(str(tmp_path / "missing.yaml"))
        assert mgr.config.backtest.initial_cash == 100000.0

    def test_save_and_reload_all_v4_fields(self, tmp_path):
        """V4.0 fields (live_trading, realtime_data, portfolio) survive a round-trip."""
        config = GlobalConfig()
        config.live_trading.broker = "hundsun"
        config.live_trading.max_orders_per_second = 20.0
        config.realtime_data.provider = "sina"
        config.realtime_data.interval_seconds = 1.5
        config.portfolio.optimization_objective = "min_vol"
        config.portfolio.rebalance_interval_days = 30

        cfg_file = tmp_path / "v4_roundtrip.yaml"
        mgr = ConfigManager(str(cfg_file))
        mgr.save(config)

        mgr2 = ConfigManager(str(cfg_file))
        loaded = mgr2.load()

        assert loaded.live_trading.broker == "hundsun"
        assert loaded.live_trading.max_orders_per_second == 20.0
        assert loaded.realtime_data.provider == "sina"
        assert loaded.realtime_data.interval_seconds == 1.5
        assert loaded.portfolio.optimization_objective == "min_vol"
        assert loaded.portfolio.rebalance_interval_days == 30
