"""
Default Configuration Values

V3.1.0: Centralized configuration parameters for the quantitative trading platform.
Replaces hardcoded values scattered across the codebase.

Usage:
    >>> from src.core.defaults import DEFAULT_CONFIG, PATHS, FEES
    >>> 
    >>> # Access default values
    >>> initial_cash = DEFAULT_CONFIG['backtest']['initial_cash']
    >>> db_path = PATHS['database']
"""
from __future__ import annotations

import os
from typing import Dict, Any


# ---------------------------------------------------------------------------
# Path Configuration
# ---------------------------------------------------------------------------

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
LOG_DIR = os.path.join(BASE_DIR, "logs")

PATHS: Dict[str, str] = {
    "base": BASE_DIR,
    "cache": CACHE_DIR,
    "reports": REPORT_DIR,
    "logs": LOG_DIR,
    "database": os.path.join(CACHE_DIR, "stock_data.db"),
    "config": os.path.join(BASE_DIR, "config.yaml"),
}


# ---------------------------------------------------------------------------
# Fee Configuration (China A-Share Market)
# ---------------------------------------------------------------------------

FEES: Dict[str, float] = {
    # Commission rates
    "commission_rate": 0.0003,      # 万三 (3 basis points)
    "commission_min": 5.0,          # 最低佣金 5元
    
    # Stamp duty (印花税) - sell only
    "stamp_duty": 0.001,            # 千分之一
    
    # Transfer fee (过户费)
    "transfer_fee": 0.00001,        # 万分之0.1
    
    # Slippage estimation
    "slippage_default": 0.001,      # 千分之一
    "slippage_high_vol": 0.002,     # 高波动品种
}


# ---------------------------------------------------------------------------
# Backtest Configuration
# ---------------------------------------------------------------------------

BACKTEST_CONFIG: Dict[str, Any] = {
    "initial_cash": 200000.0,       # 初始资金 20万
    "commission": FEES["commission_rate"],
    "slippage": FEES["slippage_default"],
    "min_trade_unit": 100,          # A股最小交易单位 100股
    "allow_short": False,           # A股不允许做空
}


# ---------------------------------------------------------------------------
# Risk Management Configuration
# ---------------------------------------------------------------------------

RISK_CONFIG: Dict[str, Any] = {
    # Position limits
    "max_position_pct": 0.30,       # 单只股票最大仓位 30%
    "max_positions": 10,            # 最大持仓数量
    
    # Loss limits
    "daily_loss_limit": 0.05,       # 日亏损限制 5%
    "max_drawdown_limit": 0.20,     # 最大回撤限制 20%
    
    # Order limits
    "max_order_value": 100000.0,    # 单笔最大订单金额
    "min_order_value": 1000.0,      # 单笔最小订单金额
}


# ---------------------------------------------------------------------------
# Data Source Configuration
# ---------------------------------------------------------------------------

DATA_CONFIG: Dict[str, Any] = {
    "default_provider": "akshare",
    "providers": {
        "akshare": {
            "enabled": True,
            "rate_limit": 0.5,      # 每秒最多2次请求
        },
        "yfinance": {
            "enabled": True,
            "rate_limit": 1.0,
        },
        "tushare": {
            "enabled": False,       # 需要 token
            "token": "",
        },
    },
    "cache_enabled": True,
    "cache_expire_days": 1,         # 缓存过期天数
}


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

LOGGING_CONFIG: Dict[str, Any] = {
    "level": "INFO",
    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "json_format": False,           # Production mode uses JSON
    "log_file": os.path.join(LOG_DIR, "quant.log"),
}


# ---------------------------------------------------------------------------
# Strategy Default Parameters
# ---------------------------------------------------------------------------

STRATEGY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "ema": {
        "period": 20,
        "slope_lookback": 5,
        "atr_period": 14,
        "stop_mult": 2.0,
        "risk_pct": 0.02,
    },
    "macd": {
        "fast": 12,
        "slow": 26,
        "signal": 9,
        "atr_period": 14,
        "stop_mult": 2.0,
    },
    "bollinger": {
        "period": 20,
        "devfactor": 2.0,
        "entry_mode": "pierce",
        "exit_mode": "mid",
    },
    "rsi": {
        "period": 14,
        "upper": 70,
        "lower": 30,
        "trend_ma": 50,
    },
    "zscore": {
        "period": 20,
        "z_entry": -2.0,
        "z_exit": -0.5,
        "trend_ma": 200,
    },
    "triple_ma": {
        "fast": 5,
        "mid": 20,
        "slow": 60,
    },
    "keltner": {
        "ema_period": 20,
        "atr_period": 14,
        "kc_mult": 2.0,
    },
    "donchian": {
        "upper_period": 20,
        "lower_period": 10,
    },
    "adx": {
        "period": 14,
        "threshold": 25,
        "atr_period": 14,
        "trail_mult": 2.0,
    },
}


# ---------------------------------------------------------------------------
# Combined Default Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "paths": PATHS,
    "fees": FEES,
    "backtest": BACKTEST_CONFIG,
    "risk": RISK_CONFIG,
    "data": DATA_CONFIG,
    "logging": LOGGING_CONFIG,
    "strategies": STRATEGY_DEFAULTS,
}


def get_config(key: str, default: Any = None) -> Any:
    """
    Get configuration value by dot-notation key.
    
    Args:
        key: Configuration key (e.g., "backtest.initial_cash")
        default: Default value if key not found
    
    Returns:
        Configuration value
    
    Example:
        >>> cash = get_config("backtest.initial_cash")
        >>> provider = get_config("data.default_provider")
    """
    keys = key.split(".")
    value = DEFAULT_CONFIG
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    
    return value


def ensure_directories() -> None:
    """Ensure all required directories exist."""
    for name, path in PATHS.items():
        if name != "database" and name != "config":
            os.makedirs(path, exist_ok=True)
