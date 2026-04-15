"""
Unified Configuration System

Type-safe configuration management using Pydantic with YAML support.
Provides centralized settings for backtest, data, risk, and execution.
"""
from __future__ import annotations

import os
import yaml
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "DataConfig",
    "BacktestConfig",
    "RiskConfig",
    "ExecutionConfig",
    "StrategyConfig",
    "LoggingConfig",
    "LiveTradingConfig",
    "RealtimeDataConfig",
    "PortfolioConfig",
    "GlobalConfig",
    "ConfigManager",
    "get_config",
    "set_config",
]


# ---------------------------------------------------------------------------
# Configuration Models
# ---------------------------------------------------------------------------

class DataConfig(BaseModel):
    """Data source configuration."""
    provider: str = Field("akshare", description="Data provider (akshare/yfinance/tushare)")
    cache_dir: str = Field("./cache", description="Cache directory path")
    adj: Optional[str] = Field(None, description="Adjustment type (qfq/hfq/None)")
    start_date: str = Field("2024-01-01", description="Default start date")
    end_date: str = Field("2024-12-31", description="Default end date")


class BacktestConfig(BaseModel):
    """Backtest engine configuration."""
    initial_cash: float = Field(100000.0, description="Initial cash", gt=0)
    commission: float = Field(0.001, description="Commission rate", ge=0, le=0.1)
    slippage: float = Field(0.0, description="Slippage (fixed or percentage)", ge=0)
    slippage_type: str = Field("fixed", description="Slippage type (fixed/percentage/volume)")

    @validator("commission")
    def validate_commission(cls, v):
        if v < 0 or v > 0.1:
            raise ValueError("Commission must be between 0 and 0.1 (10%)")
        return v


class RiskConfig(BaseModel):
    """Risk management configuration."""
    enabled: bool = Field(True, description="Enable risk checks")
    strict_mode: bool = Field(True, description="Reject order on any rule failure")
    max_position_pct: float = Field(0.3, description="Max position as % of portfolio", gt=0, le=1.0)
    max_daily_loss_pct: float = Field(0.05, description="Max daily loss %", gt=0, le=1.0)
    max_order_size: float = Field(10000.0, description="Max order size", gt=0)
    max_price_deviation_pct: float = Field(0.05, description="Max price deviation %", gt=0, le=1.0)


class ExecutionConfig(BaseModel):
    """Execution configuration."""
    gateway: str = Field("paper", description="Gateway type (paper/backtest/live)")
    mode: str = Field("vectorized", description="Execution mode (vectorized/event)")
    enable_matching: bool = Field(True, description="Enable order matching simulation")
    enable_slippage: bool = Field(True, description="Enable slippage simulation")


class StrategyConfig(BaseModel):
    """Strategy configuration."""
    name: str = Field("default", description="Strategy name")
    symbols: List[str] = Field(default_factory=list, description="Trading symbols")
    params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field("INFO", description="Log level (DEBUG/INFO/WARNING/ERROR)")
    file: Optional[str] = Field(None, description="Log file path")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )

    @validator("level")
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()


class LiveTradingConfig(BaseModel):
    """Live trading configuration."""
    enabled: bool = False
    broker: str = "xtp"  # xtp, hundsun, xtquant
    account_id: str = ""
    gateway_type: str = "xtp"  # xtp, hundsun, xtquant
    sdk_path: str = ""
    sdk_log_path: str = ""
    auto_reconnect: bool = True
    max_orders_per_second: float = 10.0

    @validator("broker")
    def broker_must_be_valid(cls, v):
        valid = {"xtp", "hundsun", "xtquant", "paper"}
        if v not in valid:
            raise ValueError(f"broker must be one of {valid}")
        return v

    @validator("max_orders_per_second")
    def max_orders_positive(cls, v):
        if v <= 0:
            raise ValueError("max_orders_per_second must be positive")
        return v

    class Config:
        extra = "forbid"


class RealtimeDataConfig(BaseModel):
    """Real-time data configuration."""
    provider: str = "simulation"  # simulation, akshare, sina, eastmoney, tencent
    symbols: List[str] = Field(default_factory=list)
    fallback_providers: List[str] = Field(default_factory=list)
    interval_seconds: float = 3.0
    request_timeout_seconds: float = 5.0
    bar_intervals: List[int] = Field(default_factory=lambda: [1, 5])

    @validator("provider")
    def provider_must_be_valid(cls, v):
        valid = {"simulation", "akshare", "sina", "eastmoney", "tencent"}
        if v not in valid:
            raise ValueError(f"provider must be one of {valid}")
        return v

    @validator("fallback_providers", each_item=True)
    def fallback_provider_must_be_valid(cls, v):
        valid = {"simulation", "akshare", "sina", "eastmoney", "tencent"}
        if v not in valid:
            raise ValueError(f"fallback provider must be one of {valid}")
        return v

    @validator("interval_seconds")
    def interval_positive(cls, v):
        if v <= 0:
            raise ValueError("interval_seconds must be positive")
        return v

    @validator("request_timeout_seconds")
    def timeout_positive(cls, v):
        if v <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        return v

    class Config:
        extra = "forbid"


class PortfolioConfig(BaseModel):
    """Portfolio-level configuration."""
    strategies: List[str] = Field(default_factory=list)
    rebalance_interval_days: int = 21
    max_weight_per_strategy: float = 0.4
    min_weight_per_strategy: float = 0.05
    optimization_objective: str = "sharpe"  # sharpe, min_vol, equal_risk

    @validator("max_weight_per_strategy")
    def max_weight_valid(cls, v):
        if not 0 < v <= 1.0:
            raise ValueError("max_weight_per_strategy must be between 0 and 1")
        return v

    @validator("optimization_objective")
    def objective_must_be_valid(cls, v):
        valid = {"sharpe", "min_vol", "equal_risk"}
        if v not in valid:
            raise ValueError(f"optimization_objective must be one of {valid}")
        return v

    class Config:
        extra = "forbid"


class GlobalConfig(BaseModel):
    """Global configuration container."""
    data: DataConfig = Field(default_factory=DataConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    # New V4.0 fields
    live_trading: LiveTradingConfig = Field(default_factory=LiveTradingConfig)
    realtime_data: RealtimeDataConfig = Field(default_factory=RealtimeDataConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)

    class Config:
        """Pydantic config."""
        validate_assignment = True  # Validate on attribute assignment
        extra = "forbid"  # Forbid extra fields

    def validate_all(self) -> List[str]:
        """
        Validate cross-field consistency.

        Returns:
            List of warning/error messages (empty if all OK)
        """
        warnings = []

        # Check: live trading enabled requires account_id
        if self.live_trading.enabled and not self.live_trading.account_id:
            warnings.append("live_trading.enabled=True but account_id is empty")

        # Check: commission rate sanity
        if self.backtest.commission > 0.01:
            warnings.append(
                f"commission_rate={self.backtest.commission} seems high (>1%)"
            )

        # Check: initial cash > 0
        if self.backtest.initial_cash <= 0:
            warnings.append(
                f"backtest.initial_cash={self.backtest.initial_cash} must be positive"
            )

        # Check: portfolio max weight consistency
        if (
            self.portfolio.strategies
            and len(self.portfolio.strategies) * self.portfolio.min_weight_per_strategy > 1.0
        ):
            warnings.append("portfolio: min_weight_per_strategy * num_strategies > 1.0")

        return warnings


# ---------------------------------------------------------------------------
# Configuration Manager
# ---------------------------------------------------------------------------

class ConfigManager:
    """
    Configuration manager with YAML support.

    Usage:
        >>> # Load from YAML file
        >>> manager = ConfigManager("config.yaml")
        >>> config = manager.load()
        >>>
        >>> # Load from environment variables
        >>> manager = ConfigManager()
        >>> config = manager.load()
        >>>
        >>> # Access settings
        >>> print(config.backtest.initial_cash)
        >>> print(config.data.provider)
        >>>
        >>> # Update settings
        >>> config.backtest.initial_cash = 200000.0
        >>>
        >>> # Save config to the path used at construction
        >>> manager.save(config)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config: Optional[GlobalConfig] = None,
    ):
        """
        Initialize config manager.

        Args:
            config_path: Optional path to a YAML config file.
            config: Optional pre-built GlobalConfig instance.
        """
        self._config_path = config_path
        self._config = config

    # ------------------------------------------------------------------
    # Instance-based API (new V4.0)
    # ------------------------------------------------------------------

    def load(self) -> GlobalConfig:
        """
        Load configuration.

        If a config_path was provided at construction and the file exists,
        load from that file.  Otherwise apply environment-variable overrides
        on top of the defaults.

        Returns:
            GlobalConfig instance
        """
        if self._config_path is not None:
            loaded = self.__class__.load_from_file(self._config_path)
            # Use the .config property so that a missing file still yields defaults
            self._config = loaded.config
            return self._config

        # No path: build from env vars (falls back to defaults automatically)
        loaded = self.__class__.load_from_env()
        self._config = loaded._config
        return self._config

    def save(self, config: GlobalConfig) -> None:
        """
        Persist *config* to the path supplied at construction.

        Args:
            config: GlobalConfig instance to save.

        Raises:
            ValueError: if no config_path was provided at construction.
        """
        self._config = config
        if self._config_path is None:
            raise ValueError("No config_path was set; cannot save without a target path.")
        self.save_to_file(self._config_path)

    @property
    def config(self) -> GlobalConfig:
        """Return the current GlobalConfig, initialising to defaults if needed."""
        if self._config is None:
            self._config = GlobalConfig()
        return self._config

    # ------------------------------------------------------------------
    # Class-method API (original)
    # ------------------------------------------------------------------

    @classmethod
    def load_from_file(cls, path: str) -> "ConfigManager":
        """
        Load configuration from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            ConfigManager instance
        """
        path_obj = Path(path)

        if not path_obj.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            return cls()

        try:
            with open(path_obj, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                data = {}

            config = GlobalConfig(**data)
            logger.info(f"Loaded configuration from {path}")

            return cls(config_path=path, config=config)

        except Exception as e:
            logger.error(f"Error loading config from {path}: {e}")
            raise

    @classmethod
    def load_from_env(cls, prefix: str = "BACKTEST_") -> "ConfigManager":
        """
        Load configuration from environment variables.

        Args:
            prefix: Environment variable prefix

        Returns:
            ConfigManager instance
        """
        config_data: Dict[str, Any] = {}

        # Map environment variables to config structure
        env_mapping = {
            f"{prefix}DATA_PROVIDER": ("data", "provider"),
            f"{prefix}DATA_CACHE_DIR": ("data", "cache_dir"),
            f"{prefix}INITIAL_CASH": ("backtest", "initial_cash"),
            f"{prefix}BACKTEST_CASH": ("backtest", "initial_cash"),
            f"{prefix}BACKTEST_COMMISSION": ("backtest", "commission"),
            f"{prefix}RISK_MAX_POSITION": ("risk", "max_position_pct"),
            f"{prefix}EXECUTION_GATEWAY": ("execution", "gateway"),
            f"{prefix}LOG_LEVEL": ("logging", "level"),
        }

        for env_var, (section, key) in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                if section not in config_data:
                    config_data[section] = {}

                # Type conversion
                if key in ["initial_cash", "commission", "max_position_pct"]:
                    value = float(value)  # type: ignore[assignment]

                # Later entries in the dict win; avoid overwriting once set
                if key not in config_data[section]:
                    config_data[section][key] = value

        if config_data:
            logger.info(f"Loaded {len(config_data)} config sections from environment")

        try:
            config = GlobalConfig(**config_data)
            return cls(config=config)
        except Exception as e:
            logger.error(f"Error loading config from environment: {e}")
            raise

    def save_to_file(self, path: str) -> None:
        """
        Save configuration to YAML file.

        Args:
            path: Output file path
        """
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path_obj, "w", encoding="utf-8") as f:
                yaml.dump(
                    self.config.dict(),
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

            logger.info(f"Saved configuration to {path}")

        except Exception as e:
            logger.error(f"Error saving config to {path}: {e}")
            raise

    def update(self, **kwargs) -> None:
        """
        Update configuration values.

        Args:
            **kwargs: Nested dictionary of updates

        Example:
            >>> manager.update(backtest={"initial_cash": 200000.0})
            >>> manager.update(risk={"max_position_pct": 0.4})
        """
        for section, values in kwargs.items():
            if hasattr(self.config, section):
                section_config = getattr(self.config, section)
                for key, value in values.items():
                    if hasattr(section_config, key):
                        setattr(section_config, key, value)
                        logger.info(f"Updated {section}.{key} = {value}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.config.dict()

    def __getattr__(self, name: str):
        """Delegate attribute access to config."""
        if name in ("_config", "_config_path"):
            raise AttributeError(name)
        return getattr(self.config, name)


# ---------------------------------------------------------------------------
# Global Instance
# ---------------------------------------------------------------------------

# Global configuration instance (lazy loaded)
_global_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """
    Get global configuration instance.

    Returns:
        ConfigManager instance
    """
    global _global_config

    if _global_config is None:
        # Try to load from default paths
        default_paths = [
            "config.yaml",
            "config/config.yaml",
            os.path.expanduser("~/.backtest/config.yaml"),
        ]

        for path in default_paths:
            if os.path.exists(path):
                _global_config = ConfigManager.load_from_file(path)
                break

        # If no file found, use defaults
        if _global_config is None:
            _global_config = ConfigManager()
            logger.info("Using default configuration")

    return _global_config


def set_config(config: ConfigManager) -> None:
    """Set global configuration instance."""
    global _global_config
    _global_config = config


# ---------------------------------------------------------------------------
# Example Configuration Template
# ---------------------------------------------------------------------------

EXAMPLE_CONFIG_YAML = """
# Data Configuration
data:
  provider: akshare
  cache_dir: ./cache
  adj: qfq  # qfq (forward adjusted), hfq (backward adjusted), null (no adjustment)
  start_date: "2024-01-01"
  end_date: "2024-12-31"

# Backtest Configuration
backtest:
  initial_cash: 100000.0
  commission: 0.001  # 0.1%
  slippage: 0.0
  slippage_type: fixed  # fixed, percentage, volume

# Risk Configuration
risk:
  enabled: true
  strict_mode: true
  max_position_pct: 0.3  # 30% max per position
  max_daily_loss_pct: 0.05  # 5% max daily loss
  max_order_size: 10000.0
  max_price_deviation_pct: 0.05  # 5% max deviation from market

# Execution Configuration
execution:
  gateway: paper  # paper, backtest, live
  mode: vectorized  # vectorized, event
  enable_matching: true
  enable_slippage: true

# Strategy Configuration
strategy:
  name: my_strategy
  symbols:
    - 600519.SH
    - 000858.SZ
  params:
    period: 20
    threshold: 0.02

# Logging Configuration
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: ./logs/backtest.log
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
"""


def create_example_config(path: str = "config_example.yaml") -> None:
    """Create example configuration file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(EXAMPLE_CONFIG_YAML)

    logger.info("Created example configuration", path=path)
