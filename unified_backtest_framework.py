# unified_backtest_framework.py
"""
Unified Backtest Framework

Integrates the legacy akshare/yfinance/tushare demos into a single, modular
backtesting script. The default data source is akshare, with optional fallbacks
to yfinance and tushare. Strategies are registered via a pluggable registry so
new algorithms can be added without touching the engine.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import time
import warnings
import concurrent.futures
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type

import numpy as np
import pandas as pd
import pickle
import math
import tempfile

try:
    import backtrader as bt
except ImportError as exc:  # pragma: no cover
    raise ImportError("backtrader is required: pip install backtrader") from exc

# Import new modular strategy registry
from src.strategies.backtrader_registry import BACKTRADER_STRATEGY_REGISTRY

CACHE_DEFAULT = "./cache"

# --- globals for process workers (avoid re-sending big data blobs) --------
_G_DATA_MAP: Optional[Dict[str, pd.DataFrame]] = None
_G_BENCH_NAV: Optional[pd.Series] = None

def _grid_worker_init(data_path: str, bench_path: Optional[str]) -> None:
    """Process initializer to load shared data into globals once per worker."""
    import pickle as _pkl
    global _G_DATA_MAP, _G_BENCH_NAV
    with open(data_path, "rb") as f:
        _G_DATA_MAP = _pkl.load(f)
    if bench_path and os.path.exists(bench_path):
        with open(bench_path, "rb") as f:
            _G_BENCH_NAV = _pkl.load(f)
    else:
        _G_BENCH_NAV = None

# ---------------------------------------------------------------------------
# Data providers
# ---------------------------------------------------------------------------
class DataProviderError(RuntimeError):
    """Raised when a data provider fails."""

class DataProviderUnavailable(DataProviderError):
    """Raised when an optional dependency is missing."""

class DataProvider:
    """Abstract base for OHLCV data providers."""

    name: str = "unknown"

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        """Return OHLCV history in a consistent pandas format."""
        raise NotImplementedError

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        """Return a benchmark NAV series aligned with the date range."""
        raise NotImplementedError

    @staticmethod
    def _ensure_cache(cache_dir: str) -> None:
        """Create the cache directory if it does not already exist."""
        os.makedirs(cache_dir, exist_ok=True)

    @staticmethod
    def _validate_dates(start: str, end: str) -> Tuple[str, str]:
        """Ensure provider-friendly YYYYMMDD date strings."""
        if not start or not end:
            raise ValueError("start and end dates are required (YYYY-MM-DD)")
        return start.replace("-", ""), end.replace("-", "")

# --- Normalisation helpers -------------------------------------------------
_STOCK_COLUMN_ALIASES = {
    "datetime": "datetime",
    "date": "datetime",
    "trade_date": "datetime",
    "\u65e5\u671f": "datetime",
    "\u4ea4\u6613\u65e5\u671f": "datetime",
    "open": "open",
    "\u5f00\u76d8": "open",
    "high": "high",
    "\u6700\u9ad8": "high",
    "low": "low",
    "\u6700\u4f4e": "low",
    "close": "close",
    "\u6536\u76d8": "close",
    "\u6536\u76d8\u4ef7": "close",
    "volume": "volume",
    "vol": "volume",
    "\u6210\u4ea4\u91cf": "volume",
}

_INDEX_COLUMN_ALIASES = {
    "datetime": "datetime",
    "date": "datetime",
    "trade_date": "datetime",
    "\u65e5\u671f": "datetime",
    "\u4ea4\u6613\u65e5\u671f": "datetime",
    "close": "close",
    "\u6536\u76d8": "close",
    "\u6536\u76d8\u4ef7": "close",
}

_REQUIRED_OHLCV = ["datetime", "open", "high", "low", "close", "volume"]

def _standardize_stock_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise provider-specific stock frames into our canonical schema."""
    renamed = df.rename(columns=_STOCK_COLUMN_ALIASES)
    missing = [col for col in _REQUIRED_OHLCV if col not in renamed.columns]
    if missing:
        raise DataProviderError(f"Stock data missing columns {missing}: {df.columns.tolist()}")
    out = renamed[_REQUIRED_OHLCV].copy()
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
    out = out.dropna(subset=["datetime"])
    for key in ["open", "high", "low", "close", "volume"]:
        out[key] = pd.to_numeric(out[key], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    out["volume"] = out["volume"].fillna(0.0)
    out = out.set_index("datetime").sort_index()
    return out

def _standardize_index_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Convert index OHLC data into a datetime-indexed frame with close prices."""
    renamed = df.rename(columns=_INDEX_COLUMN_ALIASES)
    missing = [col for col in ["datetime", "close"] if col not in renamed.columns]
    if missing:
        raise DataProviderError(f"Index data missing columns {missing}: {df.columns.tolist()}")
    out = renamed[["datetime", "close"]].copy()
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
    out = out.dropna(subset=["datetime"])
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["close"])
    out = out.set_index("datetime").sort_index()
    return out

def _nav_from_close(close: pd.Series) -> pd.Series:
    """Derive a NAV series from close prices using simple compounding."""
    ret = close.pct_change().fillna(0.0)
    nav = (1 + ret).cumprod()
    nav.name = getattr(close, "name", "nav")
    return nav

# --- Akshare provider ------------------------------------------------------
class AkshareProvider(DataProvider):
    """Data provider that wraps akshare for A-share equity and index endpoints."""
    name = "akshare"

    def __init__(self) -> None:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise DataProviderUnavailable(
                "akshare provider requires `pip install akshare`."
            ) from exc
        self.ak = ak

    @staticmethod
    def _stock_symbol(ts_code: str) -> str:
        return ts_code.split(".")[0] if "." in ts_code else ts_code

    @staticmethod
    def _index_symbol(ts_code: str) -> str:
        if "." not in ts_code:
            return ts_code
        num, exch = ts_code.split(".")
        prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(exch.upper(), exch.lower())
        return f"{prefix}{num}"

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        self._ensure_cache(cache_dir)
        start_str, end_str = self._validate_dates(start, end)
        adj_code = {
            None: "",
            "": "",
            "none": "",
            "noadj": "",
            "bfq": "",
            "qfq": "qfq",
            "hfq": "hfq",
        }.get(str(adj).lower() if adj is not None else None, "")
        out: Dict[str, pd.DataFrame] = {}
        for code in symbols:
            cache_name = f"ak_{code}_{start}_{end}_{adj_code or 'noadj'}.csv"
            cache_path = os.path.join(cache_dir, cache_name)
            if os.path.exists(cache_path):
                raw = pd.read_csv(cache_path)
            else:
                raw = self.ak.stock_zh_a_hist(
                    symbol=self._stock_symbol(code),
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust=adj_code,
                )
                if raw is None or raw.empty:
                    raise DataProviderError(f"akshare returned empty frame for {code}")
                raw.to_csv(cache_path, index=False)
            out[code] = _standardize_stock_frame(raw)
        return out

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        self._ensure_cache(cache_dir)
        start_str, end_str = self._validate_dates(start, end)
        cache_path = os.path.join(cache_dir, f"ak_index_{index_code}_{start}_{end}.csv")
        if os.path.exists(cache_path):
            raw = pd.read_csv(cache_path)
        else:
            raw = self.ak.index_zh_a_hist(
                symbol=self._index_symbol(index_code),
                period="daily",
                start_date=start_str,
                end_date=end_str,
            )
            if raw is None or raw.empty:
                raise DataProviderError(f"akshare index data empty for {index_code}")
            raw.to_csv(cache_path, index=False)
        close = _standardize_index_frame(raw)["close"].astype(float)
        close.name = index_code
        return _nav_from_close(close)

# --- yfinance provider -----------------------------------------------------
def _standardize_yf(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise yfinance downloads into the canonical OHLCV ordering."""
    if df.empty:
        raise DataProviderError("yfinance returned empty frame")
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance uses a MultiIndex of (ticker, field). For single tickers we
        # can safely drop the outer level; for multiple tickers we join levels
        # with underscores so the column scanner below can still recognise the
        # OHLCV tokens (e.g. ``AAPL_Close`` -> ``close``).
        if df.columns.nlevels == 2 and len(df.columns.levels[0]) == 1:
            df = df.droplevel(0, axis=1)
        else:
            flat_cols = ["_".join(str(part) for part in col if part)
                         for col in df.columns]
            df = pd.DataFrame(df.values, index=df.index, columns=flat_cols)
    col_map = {}
    for col in df.columns:
        key = str(col).lower().replace(" ", "")
        if "open" in key:
            col_map[col] = "open"
        elif "high" in key:
            col_map[col] = "high"
        elif "low" in key:
            col_map[col] = "low"
        elif "close" in key and "adj" not in key:
            col_map[col] = "close"
        elif "adj" in key and "close" in key and "close" not in col_map.values():
            col_map[col] = "close"
        elif "volume" in key or key.endswith("vol"):
            col_map[col] = "volume"
    renamed = df.rename(columns=col_map)
    missing = [c for c in ["open", "high", "low", "close", "volume"] if c not in renamed.columns]
    if missing:
        raise DataProviderError(f"yfinance missing columns {missing}: {df.columns.tolist()}")
    out = renamed[["open", "high", "low", "close", "volume"]].copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, errors="coerce")
    out = out.sort_index()
    cleaned = out.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        series = cleaned[col]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        cleaned[col] = pd.to_numeric(series, errors="coerce")
    cleaned = cleaned.dropna(subset=["open", "high", "low", "close"])
    cleaned["volume"] = cleaned["volume"].fillna(0.0)
    cleaned.index.name = "datetime"
    return cleaned

class YFinanceProvider(DataProvider):
    """Data provider built on top of the public yfinance API."""
    name = "yfinance"

    def __init__(self) -> None:
        try:
            import yfinance as yf  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise DataProviderUnavailable(
                "yfinance provider requires `pip install yfinance`."
            ) from exc
        self.yf = yf

    @staticmethod
    def _ticker(ts_code: str) -> str:
        if "." not in ts_code:
            return ts_code
        num, exch = ts_code.split(".")
        suffix = {"SH": "SS", "SZ": "SZ"}.get(exch.upper(), exch.upper())
        return f"{num}.{suffix}"

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        self._ensure_cache(cache_dir)
        out: Dict[str, pd.DataFrame] = {}
        for code in symbols:
            cache_path = os.path.join(cache_dir, f"yf_{code}_{start}_{end}.csv")
            if os.path.exists(cache_path):
                try:
                    std = pd.read_csv(cache_path, parse_dates=["datetime"])
                    if "datetime" in std.columns:
                        std = std.set_index("datetime")
                    else:
                        raise ValueError
                except Exception:
                    raw = pd.read_csv(cache_path, index_col=0)
                    std = _standardize_yf(raw)
                    std.reset_index().to_csv(cache_path, index=False)
            else:
                raw = self.yf.download(
                    self._ticker(code),
                    start=start,
                    end=end,
                    progress=False,
                    auto_adjust=False,
                )
                if raw is None or raw.empty:
                    raise DataProviderError(f"yfinance returned empty data for {code}")
                std = _standardize_yf(raw)
                std.reset_index().to_csv(cache_path, index=False)
            out[code] = std
        return out

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        self._ensure_cache(cache_dir)
        cache_path = os.path.join(cache_dir, f"yf_index_{index_code}_{start}_{end}.csv")
        if os.path.exists(cache_path):
            try:
                std = pd.read_csv(cache_path, parse_dates=["datetime"])
                if "datetime" in std.columns:
                    std = std.set_index("datetime")
                else:
                    raise ValueError
            except Exception:
                raw = pd.read_csv(cache_path, index_col=0)
                std = _standardize_yf(raw)
                std.reset_index().to_csv(cache_path, index=False)
        else:
            raw = self.yf.download(
                self._ticker(index_code),
                start=start,
                end=end,
                progress=False,
                auto_adjust=False,
            )
            if raw is None or raw.empty:
                raise DataProviderError(f"yfinance index data empty for {index_code}")
            std = _standardize_yf(raw)
            std.reset_index().to_csv(cache_path, index=False)
        close = std["close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = pd.to_numeric(close, errors="coerce")
        close.name = index_code
        return _nav_from_close(close)

# --- Tushare provider ------------------------------------------------------
class TuShareProvider(DataProvider):
    """Data provider that consumes the TuShare pro API."""
    name = "tushare"

    def __init__(self) -> None:
        token = os.getenv("TUSHARE_TOKEN")
        if not token:
            raise DataProviderUnavailable(
                "TUSHARE_TOKEN environment variable is required for tushare provider."
            )
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise DataProviderUnavailable(
                "tushare provider requires `pip install tushare`."
            ) from exc
        ts.set_token(token)
        self.pro = ts.pro_api(token)

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        self._ensure_cache(cache_dir)
        start_str, end_str = self._validate_dates(start, end)
        out: Dict[str, pd.DataFrame] = {}
        for code in symbols:
            cache_name = f"ts_{code}_{start}_{end}_{adj or 'noadj'}.csv"
            cache_path = os.path.join(cache_dir, cache_name)
            if os.path.exists(cache_path):
                raw = pd.read_csv(cache_path)
            else:
                raw = self.pro.daily(ts_code=code, start_date=start_str, end_date=end_str)
                if raw is None or raw.empty:
                    raise DataProviderError(f"tushare returned empty data for {code}")
                raw.to_csv(cache_path, index=False)
            std = _standardize_stock_frame(raw)
            out[code] = std
        return out

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        self._ensure_cache(cache_dir)
        start_str, end_str = self._validate_dates(start, end)
        cache_path = os.path.join(cache_dir, f"ts_index_{index_code}_{start}_{end}.csv")
        if os.path.exists(cache_path):
            raw = pd.read_csv(cache_path)
        else:
            raw = self.pro.index_daily(ts_code=index_code, start_date=start_str, end_date=end_str)
            if raw is None or raw.empty:
                raise DataProviderError(f"tushare index data empty for {index_code}")
            raw.to_csv(cache_path, index=False)
        close = _standardize_index_frame(raw)["close"].astype(float)
        close.name = index_code
        return _nav_from_close(close)

# Map user-facing provider keys to the factory callables used by the engine.
_PROVIDER_FACTORIES: Dict[str, Callable[[], DataProvider]] = {
    "akshare": AkshareProvider,
    "yfinance": YFinanceProvider,
    "tushare": TuShareProvider,
}

def get_provider(name: str) -> DataProvider:
    key = name.lower()
    if key not in _PROVIDER_FACTORIES:
        raise KeyError(f"Unknown data provider: {name}")
    return _PROVIDER_FACTORIES[key]()

# ---------------------------------------------------------------------------
# Strategy modules
# ---------------------------------------------------------------------------
class GenericPandasData(bt.feeds.PandasData):
    """Backtrader data feed that expects the normalised pandas structure."""
    params = (("datetime", None), ("open", -1), ("high", -1), ("low", -1), ("close", -1), ("volume", -1), ("openinterest", -1))

# --- Turning point helper utilities ---------------------------------------
def rolling_vwap(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Compute a rolling VWAP to help with mean-reversion style filters."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * df["volume"]
    denom = df["volume"].rolling(window, min_periods=1).sum().replace(0, np.nan)
    vwap = pv.rolling(window, min_periods=1).sum() / denom
    return vwap.bfill().ffill()

def compute_signal_frame(
    df: pd.DataFrame,
    gap_th: float = 0.015,
    intraday_rev_th: float = 0.003,
    vol_surge: float = 1.3,
    vwap_window: int = 20,
) -> pd.DataFrame:
    """Derive the turning-point scoring frame used by the multi-symbol strategy."""
    out = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        series = out[col]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        out[col] = pd.to_numeric(series, errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    out["volume"] = out["volume"].fillna(0.0)
    out["prev_close"] = out["close"].shift(1)
    out["gap_up"] = (out["open"] >= out["prev_close"] * (1 + gap_th)).astype(int)
    out["gap_down"] = (out["open"] <= out["prev_close"] * (1 - gap_th)).astype(int)
    out["bearish_reversal"] = (
        (out["gap_up"] == 1)
        & ((out["close"] < out["open"] * (1 - intraday_rev_th)) | (out["close"] < out["prev_close"]))
    ).astype(int)
    out["bullish_reversal"] = (
        (out["gap_down"] == 1)
        & ((out["close"] > out["open"] * (1 + intraday_rev_th)) | (out["close"] > out["prev_close"]))
    ).astype(int)
    vol_mean = out["volume"].rolling(20, min_periods=1).mean()
    out["vol_surge_flag"] = (out["volume"] >= vol_mean * vol_surge).astype(int)
    out["vwap"] = rolling_vwap(out, vwap_window)
    out["long_ok"] = (
        (out["bullish_reversal"] == 1)
        & (out["close"] > out["vwap"])
        & (out["vol_surge_flag"] == 1)
    ).astype(int)
    out["short_ok"] = (
        (out["bearish_reversal"] == 1)
        & (out["close"] < out["vwap"])
        & (out["vol_surge_flag"] == 1)
    ).astype(int)
    body_strength = (out["close"] - out["open"]).abs() / out["prev_close"].replace(0, np.nan)
    vol_score = (out["volume"] / vol_mean.replace(0, np.nan)).clip(upper=3)
    vwap_bonus = 0.5 * ((out["long_ok"] == 1) | (out["short_ok"] == 1))
    out["score"] = body_strength.fillna(0) + vol_score.fillna(0) + vwap_bonus.astype(float)
    return out

@dataclass
class StrategyModule:
    """Metadata wrapper describing how a strategy integrates with the engine."""
    name: str
    description: str
    strategy_cls: Type[bt.Strategy]
    param_names: Sequence[str]
    defaults: Dict[str, Any]
    multi_symbol: bool = False
    grid_defaults: Dict[str, Sequence[Any]] = field(default_factory=dict)
    coercer: Callable[[Dict[str, Any]], Dict[str, Any]] = staticmethod(lambda p: p)

    def coerce(self, params: Dict[str, Any]) -> Dict[str, Any]:
        merged = {**self.defaults, **params}
        return self.coercer(dict(merged))

    def add_data(self, cerebro: bt.Cerebro, data_map: Dict[str, pd.DataFrame]) -> None:
        if self.multi_symbol:
            for sym in sorted(data_map.keys()):
                feed = GenericPandasData(dataname=data_map[sym])
                cerebro.adddata(feed, name=sym)
        else:
            sym = next(iter(sorted(data_map.keys())))
            feed = GenericPandasData(dataname=data_map[sym])
            cerebro.adddata(feed, name=sym)

    def add_strategy(self, cerebro: bt.Cerebro, params: Dict[str, Any]) -> None:
        cerebro.addstrategy(self.strategy_cls, **params)

def _convert_backtrader_registry_to_legacy() -> Dict[str, StrategyModule]:
    """
    Convert new backtrader registry to legacy StrategyModule format.
    This maintains compatibility while using the new modular strategies.
    """
    legacy_registry = {}
    
    for name, module in BACKTRADER_STRATEGY_REGISTRY.items():
        # Convert new module to legacy format
        legacy_module = StrategyModule(
            name=module.name,
            description=module.description,
            strategy_cls=module.strategy_cls,
            param_names=module.param_names,
            defaults=module.defaults,
            multi_symbol=module.multi_symbol,
            grid_defaults=module.grid_defaults,
            coercer=module.coercer
        )
        legacy_registry[name] = legacy_module
    
    return legacy_registry

def _add_legacy_specific_strategies(registry: Dict[str, StrategyModule]) -> None:
    """Add strategies that are specific to this framework and not in the new registry."""
    # Add TURNING_POINT_MODULE if it's defined
    if 'TURNING_POINT_MODULE' in globals():
        registry["turning_point"] = TURNING_POINT_MODULE
    
    # RISK_PARITY_MODULE will be added later when it's found

# --- Turning point strategy -----------------------------------------------
class IntentLogger(bt.Analyzer):
    """Analyzer that keeps a day-by-day record of portfolio intents."""

    def start(self) -> None:
        self.logs: List[Tuple[pd.Timestamp, Dict[str, str]]] = []

    def next(self) -> None:
        strat = self.strategy
        record: Dict[str, str] = {}
        for data in strat.datas:
            pos = strat.getposition(data)
            record[data._name] = "pos>0" if pos.size > 0 else "flat"
        dt = bt.num2date(self.strategy.datas[0].datetime[0])
        self.logs.append((pd.Timestamp(dt), record))

    def get_analysis(self) -> Dict[str, Any]:
        return {"logs": self.logs}

class TurningPointBT(bt.Strategy):
    """Backtrader implementation of the signal-engine driven turning point play."""
    params = dict(
        topn=2,
        gap=0.015,
        reversal=0.003,
        vol_surge=1.3,
        vwap_window=20,
        allow_short=False,
        risk_per_trade=0.1,
        # --- 新增风险控制/过滤 ---
        atr_period=14, atr_sl=2.0, atr_tp=None,
        use_atr_position_sizing=True,
        max_pos_value_frac=0.3,
        bull_filter=False,
        bull_filter_benchmark=False,
        benchmark_data_name="__benchmark__",
        regime_period=200, regime_use_slope=False, regime_slope_period=20,
        min_holding_bars=0, cooldown_bars=0,
    )

    def __init__(self) -> None:
        # name -> data feed
        self._names = {data._name or f"sym{idx}": data for idx, data in enumerate(self.datas)}
        # 预计算全量信号，避免在 next() 里重复滚动计算（大幅提速）
        self._sig_map: Dict[str, pd.DataFrame] = {}
        for name, data in self._names.items():
            try:
                # 我们在 add_data 时传入的是 PandasData(dataname=<pd.DataFrame>)
                base_df = getattr(data, "_dataname", None)
                if isinstance(base_df, pd.DataFrame):
                    df_full = base_df[["open", "high", "low", "close", "volume"]].copy()
                    sig_full = compute_signal_frame(
                        df_full,
                        gap_th=self.p.gap,
                        intraday_rev_th=self.p.reversal,
                        vol_surge=self.p.vol_surge,
                        vwap_window=self.p.vwap_window,
                    )
                    # 只保留决策需要的列，减小内存
                    self._sig_map[name] = sig_full[["long_ok", "short_ok", "score"]].copy()
                else:
                    # 回退：如果拿不到原始 DataFrame，则留给 next() 的旧逻辑处理
                    self._sig_map[name] = None  # type: ignore
            except Exception:
                self._sig_map[name] = None  # type: ignore

    def next(self) -> None:
        # 当前 bar 的时间戳
        cur_dt = bt.num2date(self.datas[0].datetime[0])
        cur_ts = pd.Timestamp(cur_dt)

        # 如果已经预计算信号，则直接按时间查表并决策
        if any(self._sig_map.get(n) is not None for n in self._names):
            sig_map_today: Dict[str, Tuple[float, int, int]] = {}
            for name, data in self._names.items():
                sig = self._sig_map.get(name)
                if sig is None or sig.empty:
                    continue
                try:
                    # 找到 <= 当前时点的最近一条信号
                    loc = sig.index.get_loc(cur_ts, method="pad")
                    row = sig.iloc[loc]
                except Exception:
                    # 若索引不含当日则跳过
                    continue
                score = float(row.get("score", 0.0))
                long_ok = int(row.get("long_ok", 0))
                short_ok = int(row.get("short_ok", 0))
                sig_map_today[name] = (score, long_ok, short_ok)
            if not sig_map_today:
                return
            intents = decide_orders_from_signals(
                sig_map_today,
                topn=self.p.topn,
                allow_short=self.p.allow_short,
            )
        else:
            # 回退到旧路径（不建议，性能较差）
            df_map: Dict[str, pd.DataFrame] = {}
            for name, data in self._names.items():
                if len(data) < 30:
                    continue
                df_map[name] = pd.DataFrame(
                    {
                        "open": data.open.get(size=30),
                        "high": data.high.get(size=30),
                        "low": data.low.get(size=30),
                        "close": data.close.get(size=30),
                        "volume": data.volume.get(size=30),
                    }
                )
            if not df_map:
                return
            intents = decide_orders(
                df_map,
                topn=self.p.topn,
                allow_short=self.p.allow_short,
                gap=self.p.gap,
                reversal=self.p.reversal,
                vol_surge=self.p.vol_surge,
                vwap_window=self.p.vwap_window,
            )
        # 价格/ATR等
        atr_ind = bt.indicators.ATR(self.datas[0], period=self.p.atr_period)
        ema200 = bt.indicators.EMA(self.datas[0].close, period=self.p.regime_period)
        # 基准 EMA200
        bench = next((d for d in self.datas if getattr(d, "_name", "") == self.p.benchmark_data_name), None)
        bench_ema200 = bt.indicators.EMA(bench.close, period=self.p.regime_period) if bench is not None else None
        for intent in intents:
            data = self._names.get(intent.symbol)
            if data is None:
                continue
            pos = self.getposition(data)
            price = data.close[0]
            atr = float(atr_ind[0]) if atr_ind[0] else 0.0
            if not self.p.bull_filter:
                bullish = True
            else:
                if self.p.bull_filter_benchmark and bench_ema200 is not None and bench is not None:
                    bench_close = float(bench.close[0])
                    ema_now = float(bench_ema200[0])
                    if self.p.regime_use_slope and len(bench_ema200) > self.p.regime_slope_period:
                        ema_past = float(bench_ema200[-self.p.regime_slope_period])
                        bullish = (bench_close > ema_now) and (ema_now > ema_past)
                    else:
                        bullish = bench_close > ema_now
                else:
                    ema_now = float(ema200[0])
                    if self.p.regime_use_slope and len(ema200) > self.p.regime_slope_period:
                        ema_past = float(ema200[-self.p.regime_slope_period])
                        bullish = (float(price) > ema_now) and (ema_now > ema_past)
                    else:
                        bullish = float(price) > ema_now
            # sizing：ATR 倒数
            if self.p.use_atr_position_sizing and atr > 0:
                risk_amt = float(self.broker.getvalue()) * float(self.p.risk_per_trade)
                risk_per_share = float((self.p.atr_sl or 1.0) * atr)
                size = int(max(0, risk_amt / max(risk_per_share, 1e-8)))
            else:
                size = int(self.broker.getvalue() * self.p.risk_per_trade / max(price, 1e-8))
            if self.p.max_pos_value_frac and float(price) > 0:
                cap_shares = int(self.broker.getvalue() * float(self.p.max_pos_value_frac) / float(price))
                size = max(0, min(size, cap_shares))
            if intent.side == "long" and pos.size <= 0 and bullish:
                if pos.size < 0:
                    self.close(data=data)
                if size > 0:
                    self.buy(data=data, size=size)
            elif intent.side == "short" and self.p.allow_short and pos.size >= 0:
                if pos.size > 0:
                    self.close(data=data)
                if size > 0:
                    self.sell(data=data, size=size)
            elif intent.side == "flat" and pos.size != 0:
                # 最小持仓限制：达到才允许平仓
                if getattr(self, "_tp_hold", 0) >= int(self.p.min_holding_bars):
                    self.close(data=data)
            # 统一风险退出（仅对持仓）
            if pos.size != 0 and atr > 0:
                entry = float(pos.price)
                if self.p.atr_sl and float(price) <= entry - float(self.p.atr_sl) * atr and getattr(self, "_tp_hold", 0) >= int(self.p.min_holding_bars):
                    self.close(data=data)
                if self.p.atr_tp and float(price) >= entry + float(self.p.atr_tp) * atr and getattr(self, "_tp_hold", 0) >= int(self.p.min_holding_bars):
                    self.close(data=data)
                self._tp_hold = getattr(self, "_tp_hold", 0) + 1

@dataclass
class OrderIntent:
    """Simple container publishing the target side for each symbol."""
    symbol: str
    side: str

def decide_orders(
    df_map: Dict[str, pd.DataFrame],
    topn: int = 2,
    allow_short: bool = False,
    gap: float = 0.015,
    reversal: float = 0.003,
    vol_surge: float = 1.3,
    vwap_window: int = 20,
) -> List[OrderIntent]:
    """Convert recent price action into position intents for each symbol."""
    scored: List[Tuple[str, float, int, int]] = []
    for sym, df in df_map.items():
        sig = compute_signal_frame(df, gap_th=gap, intraday_rev_th=reversal, vol_surge=vol_surge, vwap_window=vwap_window)
        today = sig.iloc[-1]
        score = float(today["score"]) if (today["long_ok"] or today["short_ok"]) else 0.0
        scored.append((sym, score, int(today["long_ok"]), int(today["short_ok"])))
    selected = [x for x in scored if x[1] > 0]
    selected.sort(key=lambda x: x[1], reverse=True)
    keep = {sym for sym, *_ in selected[:topn]}
    intents: List[OrderIntent] = []
    for sym, score, long_ok, short_ok in scored:
        if sym in keep:
            if long_ok:
                intents.append(OrderIntent(symbol=sym, side="long"))
            elif allow_short and short_ok:
                intents.append(OrderIntent(symbol=sym, side="short"))
            else:
                intents.append(OrderIntent(symbol=sym, side="flat"))
        else:
            intents.append(OrderIntent(symbol=sym, side="flat"))
    return intents

def decide_orders_from_signals(
    sig_map_today: Dict[str, Tuple[float, int, int]],
    topn: int = 2,
    allow_short: bool = False,
) -> List[OrderIntent]:
    """
    根据已经预计算的当日信号（score/long_ok/short_ok）做多空/空仓决策。
    sig_map_today[sym] = (score, long_ok, short_ok)
    """
    selected = [(sym, s, l, sh) for sym, (s, l, sh) in sig_map_today.items() if s > 0]
    selected.sort(key=lambda x: x[1], reverse=True)
    keep = {sym for sym, *_ in selected[:max(1, int(topn))]}
    intents: List[OrderIntent] = []
    for sym, (score, long_ok, short_ok) in ((k, sig_map_today[k]) for k in sig_map_today.keys()):
        if sym in keep:
            if long_ok:
                intents.append(OrderIntent(symbol=sym, side="long"))
            elif allow_short and short_ok:
                intents.append(OrderIntent(symbol=sym, side="short"))
            else:
                intents.append(OrderIntent(symbol=sym, side="flat"))
        else:
            intents.append(OrderIntent(symbol=sym, side="flat"))
    return intents

def _coerce_turning(params: Dict[str, Any]) -> Dict[str, Any]:
    """Force user-supplied turning-point params into safe numeric ranges."""
    params["topn"] = max(1, int(round(params.get("topn", 2))))
    params["vwap_window"] = max(1, int(round(params.get("vwap_window", 20))))
    params["gap"] = float(params.get("gap", 0.015))
    params["reversal"] = float(params.get("reversal", 0.003))
    params["vol_surge"] = float(params.get("vol_surge", 1.3))
    params["risk_per_trade"] = min(1.0, max(0.001, float(params.get("risk_per_trade", 0.1))))
    params["allow_short"] = bool(params.get("allow_short", False))
    return params

# Strategy registry entries are declared below. Each module describes how
# parameters should be coerced, the default grid, and the associated strategy class.
TURNING_POINT_MODULE = StrategyModule(
    name="turning_point",
    description="Multi-symbol turning point selector with gap/volume filters",
    strategy_cls=TurningPointBT,
    param_names=["topn", "gap", "reversal", "vol_surge", "vwap_window", "allow_short", "risk_per_trade"],
    defaults=dict(topn=2, gap=0.015, reversal=0.003, vol_surge=1.3, vwap_window=20, allow_short=False, risk_per_trade=0.1),
    multi_symbol=True,
    grid_defaults={
        "topn": [1, 2, 3],
        "gap": [0.01, 0.015, 0.02],
        "reversal": [0.002, 0.003, 0.004],
        "vol_surge": [1.2, 1.3, 1.5],
        "vwap_window": [10, 20, 30],
    },
    coercer=_coerce_turning,
)

# --- Indicator strategies (from akshare_demo) ------------------------------

# --- Keltner Channel mean reversion ---------------------------------------

# --- ZScore mean reversion -------------------------------------------------

# --- Donchian Channel 趋势突破（修订版） ---

# --- Triple Moving Average 多头排列趋势 --------------------------------------

# --- ADX 趋势强度过滤 -------------------------------------------------------

# --- 多标的等风险权重（波动率平价）组合层 ------------------------------------
class RiskParityBT(bt.Strategy):
    """
    多标的风险平价：新增基准风控——当基准 < EMA200（或阈值）时整体降权甚至全现金。
    """
    params = dict(
        vol_window=20, rebalance_days=21, max_weight=0.4,
        use_momentum=True, mom_lookback=60, mom_threshold=0.0,
        use_regime=True, regime_period=200,
        allow_cash=True,
        # 新增：基准风控
        use_benchmark_gate=True, benchmark_data_name="__benchmark__", bench_gate_period=200, bench_risk_off_weight=0.0
    )
    def __init__(self) -> None:
        self._last_reb = -999
        self._names = [d._name or f"sym{i}" for i, d in enumerate(self.datas) if getattr(d, "_name", "") != self.p.benchmark_data_name]
        self._rets = {n: bt.indicators.PctChange(d.close) for n, d in zip(self._names, self.datas) if getattr(d, "_name", "") != self.p.benchmark_data_name}
        self._vol  = {n: bt.indicators.StdDev(self._rets[n], period=self.p.vol_window) for n in self._names}
        self._ema200 = {n: bt.indicators.EMA(d.close, period=self.p.regime_period) for n, d in zip(self._names, self.datas) if getattr(d, "_name", "") != self.p.benchmark_data_name}
        self._mom = {n: (d.close - bt.indicators.SMA(d.close, period=self.p.mom_lookback)) for n, d in zip(self._names, self.datas) if getattr(d, "_name", "") != self.p.benchmark_data_name}
        # 基准 EMA
        self._bench = next((d for d in self.datas if getattr(d, "_name", "") == self.p.benchmark_data_name), None)
        self._bench_ema = bt.indicators.EMA(self._bench.close, period=self.p.bench_gate_period) if self._bench is not None else None

    def _eligible(self, name: str, data) -> bool:
        ok = True
        if self.p.use_momentum: ok &= (float(self._mom[name][0]) > float(self.p.mom_threshold))
        if self.p.use_regime:   ok &= (float(data.close[0]) > float(self._ema200[name][0]))
        return bool(ok)

    def next(self) -> None:
        bar = len(self.datas[0]); 
        if bar - self._last_reb < int(self.p.rebalance_days): return
        self._last_reb = bar

        # —— 基准风控：风险开关 —— 
        gate_on = True
        if self.p.use_benchmark_gate and (self._bench is not None) and (self._bench_ema is not None):
            gate_on = float(self._bench.close[0]) >= float(self._bench_ema[0])

        vols, elig = {}, {}
        for d in self.datas:
            n = d._name
            if n == self.p.benchmark_data_name: continue
            v = float(self._vol[n][0]); vols[n] = v if v == v and v > 1e-9 else float("inf")
            elig[n] = self._eligible(n, d) and gate_on  # gate 直接参与资格

        inv = {n: (1.0/vols[n]) if (elig[n] and vols[n] < float("inf")) else 0.0 for n in self._names}
        # 若 gate 关闭但允许部分暴露，按 bench_risk_off_weight 缩放
        gate_scale = 1.0 if gate_on else float(self.p.bench_risk_off_weight)

        if sum(inv.values()) <= 0.0 or gate_scale <= 0.0:
            if self.p.allow_cash:
                for d in self.datas:
                    if d._name == self.p.benchmark_data_name: continue
                    if self.getposition(d).size != 0: self.close(data=d)
                return

        weights = {n: gate_scale * (inv[n] / sum(inv.values())) for n in self._names}
        for d in self.datas:
            n = d._name
            if n == self.p.benchmark_data_name: continue
            tgt_w = min(float(self.p.max_weight), float(weights.get(n, 0.0)))
            port_val = float(self.broker.getvalue()); price = float(d.close[0])
            tgt_shares = int((port_val * tgt_w) / max(price, 1e-8))
            cur_pos = self.getposition(d).size; delta = tgt_shares - cur_pos
            if delta > 0: self.buy(data=d, size=delta)
            elif delta < 0: self.sell(data=d, size=abs(delta))

def _coerce_rp(p: Dict[str, Any]) -> Dict[str, Any]:
    p["vol_window"] = max(10, int(round(float(p.get("vol_window", 20)))))
    p["rebalance_days"] = max(5, int(round(float(p.get("rebalance_days", 21)))))
    p["max_weight"] = float(min(0.9, max(0.05, float(p.get("max_weight", 0.4)))))
    p["use_momentum"] = bool(p.get("use_momentum", True))
    p["mom_lookback"] = max(20, int(round(float(p.get("mom_lookback", 60)))))
    p["mom_threshold"] = float(p.get("mom_threshold", 0.0))
    p["use_regime"] = bool(p.get("use_regime", True))
    p["allow_cash"] = bool(p.get("allow_cash", True))
    return p

RISK_PARITY_MODULE = StrategyModule(
    name="risk_parity",
    description="Multi-asset risk parity (inverse-vol) portfolio, periodic rebalance",
    strategy_cls=RiskParityBT,
    param_names=["vol_window", "rebalance_days", "max_weight", "use_momentum", "mom_lookback", "mom_threshold", "use_regime", "allow_cash"],
    defaults={"vol_window": 20, "rebalance_days": 21, "max_weight": 0.4, "use_momentum": True, "mom_lookback": 60, "mom_threshold": 0.0, "use_regime": True, "allow_cash": True},
    grid_defaults={"vol_window": [20, 30], "rebalance_days": [21], "max_weight": [0.3, 0.4, 0.5]},
    coercer=_coerce_rp,
    multi_symbol=True,
)

# Initialize the complete strategy registry after all modules are defined
STRATEGY_REGISTRY: Dict[str, StrategyModule] = {}
STRATEGY_REGISTRY.update(_convert_backtrader_registry_to_legacy())
STRATEGY_REGISTRY["turning_point"] = TURNING_POINT_MODULE
STRATEGY_REGISTRY["risk_parity"] = RISK_PARITY_MODULE

# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------
class BacktestEngine:
    """Facade responsible for orchestrating data loading and optimisation."""

    def __init__(
        self,
        *,
        source: str = "akshare",
        benchmark_source: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> None:
        self.source = source
        self.benchmark_source = benchmark_source or source
        self.cache_dir = cache_dir

    def _load_data(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        adj: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data using the configured provider."""
        provider = get_provider(self.source)
        return provider.load_stock_daily(symbols, start, end, adj=adj, cache_dir=self.cache_dir)

    def _load_benchmark(self, index_code: str, start: str, end: str) -> pd.Series:
        """Fetch the benchmark NAV series from the benchmark provider."""
        provider = get_provider(self.benchmark_source)
        tried: list[tuple[str, str]] = []
        provider_candidates = []
        for cand in [self.benchmark_source, self.source, "akshare", "yfinance", "tushare"]:
            if cand and cand not in provider_candidates:
                provider_candidates.append(cand)
        for name in provider_candidates:
            try:
                provider = get_provider(name)
            except DataProviderUnavailable as err:
                tried.append((name, f"unavailable: {err}"))
                continue
            try:
                return provider.load_index_nav(index_code, start, end, cache_dir=self.cache_dir)
            except DataProviderError as err:
                tried.append((name, str(err)))
                continue
            except Exception as err:
                tried.append((name, str(err)))
                continue
        warnings.warn(
            "All benchmark providers failed for %s; falling back to flat NAV. Errors: %s"
            % (index_code, "; ".join(f"{n}: {e}" for n, e in tried))
        )
        date_index = pd.bdate_range(start=start, end=end)
        if date_index.empty:
            date_index = pd.Index([pd.to_datetime(start)])
        nav = pd.Series(1.0, index=date_index, name=index_code)
        return nav

    @staticmethod
    def _run_module(
        module: StrategyModule,
        data_map: Dict[str, pd.DataFrame],
        params: Dict[str, Any],
        *,
        cash: float,
        commission: float,
        slippage: float,
        benchmark_nav: Optional[pd.Series],
    ) -> Tuple[pd.Series, Dict[str, Any]]:
        """Internal helper that executes a single backtest run."""
        cerebro = bt.Cerebro(stdstats=False)
        cerebro.broker.setcash(cash)
        cerebro.broker.setcommission(commission=commission)
        if slippage:
            cerebro.broker.set_slippage_perc(slippage)
        module.add_data(cerebro, data_map)
        # 如有基准，追加一条名为 "__benchmark__" 的数据馈送供策略做大势过滤
        if benchmark_nav is not None and not benchmark_nav.empty:
            # 把 NAV 序列转成最简 OHLCV（open/high/low=close, volume=0）
            bench_df = pd.DataFrame(
                {
                    "open": benchmark_nav.values,
                    "high": benchmark_nav.values,
                    "low": benchmark_nav.values,
                    "close": benchmark_nav.values,
                    "volume": 0.0,
                },
                index=pd.to_datetime(benchmark_nav.index),
            )
            bench_df.index.name = "datetime"
            bench_feed = GenericPandasData(dataname=bench_df)
            cerebro.adddata(bench_feed, name="__benchmark__")
        module.add_strategy(cerebro, params)
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timeret")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        if module is TURNING_POINT_MODULE:
            cerebro.addanalyzer(IntentLogger, _name="intent_log")
        # 更快的执行路径
        results = cerebro.run(runonce=True, preload=True)
        strat = results[0]
        timeret = pd.Series(strat.analyzers.timeret.get_analysis())
        nav = (1 + timeret.fillna(0)).cumprod()
        nav.index = pd.to_datetime(nav.index)
        nav.name = "strategy"
        metrics: Dict[str, Any] = {
            "cum_return": float(nav.iloc[-1] - 1) if len(nav) else float("nan"),
            "final_value": float(cerebro.broker.getvalue()),
        }
        try:
            sharpe_val = strat.analyzers.sharpe.get_analysis().get("sharperatio")
        except Exception:
            sharpe_val = None
        # —— 指标增强：稳健 Sharpe 备选 + 年化收益/波动 + 正向 MDD ——
        ann_factor = 252.0
        avg = float(timeret.mean()) if len(timeret) else float("nan")
        std = float(timeret.std(ddof=1)) if len(timeret) > 1 else float("nan")
        sharpe_calc = (avg / std * math.sqrt(ann_factor)) if (std and std == std and std > 0) else float("nan")
        metrics["sharpe"] = float(sharpe_val) if sharpe_val is not None else sharpe_calc
        metrics["ann_return"] = float((1 + timeret).prod() ** (ann_factor / max(len(timeret), 1)) - 1) if len(timeret) else float("nan")
        metrics["ann_vol"] = float(std * math.sqrt(ann_factor)) if std == std else float("nan")
        # 统一 MDD 口径：正的小数（0.23=23%）
        metrics["mdd"] = float(-((nav / nav.cummax()) - 1).min()) if len(nav) else float("nan")
        # ---- 交易统计增强（尽量健壮地从 TradeAnalyzer 提取） ----
        try:
            ta = strat.analyzers.trades.get_analysis()
            def _dig(d, *keys, default=float("nan")):
                cur = d
                for k in keys:
                    if not isinstance(cur, dict) or k not in cur:
                        return default
                    cur = cur[k]
                return cur
            total_closed = float(_dig(ta, "total", "closed", default=0.0))
            won_total   = float(_dig(ta, "won", "total", default=0.0))
            lost_total  = float(_dig(ta, "lost", "total", default=0.0))
            gross_won   = float(_dig(ta, "pnl", "gross", "won", default=0.0))
            gross_lost  = float(_dig(ta, "pnl", "gross", "lost", default=0.0))
            avg_win     = float(_dig(ta, "won", "pnl", "average", default=float("nan")))
            avg_loss    = float(_dig(ta, "lost", "pnl", "average", default=float("nan")))
            avg_len_tot = float(_dig(ta, "len", "avg", "total", default=float("nan")))
            win_rate = (won_total / total_closed) if total_closed > 0 else float("nan")
            profit_factor = (gross_won / abs(gross_lost)) if gross_lost != 0 else (float("inf") if gross_won > 0 else float("nan"))
            payoff_ratio = (avg_win / abs(avg_loss)) if (avg_win == avg_win and avg_loss and avg_loss < 0) else float("nan")
            expectancy = (win_rate * avg_win + (1 - win_rate) * avg_loss) if (win_rate == win_rate and avg_win == avg_win and avg_loss == avg_loss) else float("nan")
            exposure_ratio = float((np.abs(timeret.values) > 0).sum() / max(1, len(timeret))) if len(timeret) else float("nan")
            trade_freq = float(total_closed / max(1, len(timeret))) if len(timeret) else float("nan")
            metrics.update({
                "trades": int(total_closed),
                "win_rate": float(win_rate) if win_rate == win_rate else float("nan"),
                "profit_factor": float(profit_factor),
                "avg_hold_bars": float(avg_len_tot),
                "avg_win": float(avg_win) if avg_win == avg_win else float("nan"),
                "avg_loss": float(avg_loss) if avg_loss == avg_loss else float("nan"),
                "payoff_ratio": float(payoff_ratio),
                "expectancy": float(expectancy),
                "exposure_ratio": float(exposure_ratio),
                "trade_freq": float(trade_freq),
            })
        except Exception:
            metrics.update({
                "trades": int(0),
                "win_rate": float("nan"),
                "profit_factor": float("nan"),
                "avg_hold_bars": float("nan"),
                "avg_win": float("nan"),
                "avg_loss": float("nan"),
                "payoff_ratio": float("nan"),
                "expectancy": float("nan"),
                "exposure_ratio": float("nan"),
                "trade_freq": float("nan"),
            })
        # Calmar（年化回报 / MDD）
        metrics["calmar"] = float(metrics["ann_return"] / metrics["mdd"]) if (metrics.get("mdd") and metrics["mdd"] > 0) else float("nan")
        if benchmark_nav is not None:
            combined = pd.concat(
                [nav.to_frame("strategy"), benchmark_nav.to_frame("benchmark")],
                axis=1,
            ).dropna()
            if not combined.empty:
                metrics["bench_return"] = float(combined["benchmark"].iloc[-1] - 1)
                # 基准 MDD 同样统一为正的小数
                metrics["bench_mdd"] = float(-((combined["benchmark"] / combined["benchmark"].cummax()) - 1).min())
                metrics["excess_return"] = float(combined["strategy"].iloc[-1] - combined["benchmark"].iloc[-1])
            else:
                metrics["bench_return"] = float("nan")
                metrics["bench_mdd"] = float("nan")
                metrics["excess_return"] = float("nan")
        return nav, metrics

    def _execute_strategy(
        self,
        module: StrategyModule,
        data_map: Dict[str, pd.DataFrame],
        params: Dict[str, Any],
        *,
        cash: float,
        commission: float,
        slippage: float,
        benchmark_nav: Optional[pd.Series],
        out_dir: Optional[str] = None,
        label: Optional[str] = None,
    ) -> Tuple[pd.Series, Dict[str, Any]]:
        """Run a backtest for the supplied strategy module and capture metrics."""
        nav, metrics = self._run_module(
            module,
            data_map,
            params,
            cash=cash,
            commission=commission,
            slippage=slippage,
            benchmark_nav=benchmark_nav,
        )
        if benchmark_nav is not None and out_dir:
            os.makedirs(out_dir, exist_ok=True)
            combined = pd.concat(
                [nav.to_frame("strategy"), benchmark_nav.to_frame("benchmark")],
                axis=1,
            ).dropna()
            combined_path = os.path.join(out_dir, f"{label or module.name}_nav_vs_benchmark.csv")
            combined.to_csv(combined_path)
            if not combined.empty:
                import matplotlib.pyplot as plt  # local import

                plt.figure()
                combined.plot()
                plt.title(f"{module.name} vs benchmark")
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, f"{label or module.name}_nav_vs_benchmark.png"))
                plt.close()
        elif out_dir:
            os.makedirs(out_dir, exist_ok=True)
            nav.to_frame("strategy").to_csv(os.path.join(out_dir, f"{label or module.name}_nav.csv"))
        return nav, metrics

    def run_strategy(
        self,
        strategy: str,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        cash: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.001,
        benchmark: Optional[str] = None,
        adj: Optional[str] = None,
        out_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convenience wrapper returning both metrics and NAV for a single run."""
        if strategy not in STRATEGY_REGISTRY:
            raise KeyError(f"Unknown strategy: {strategy}")
        module = STRATEGY_REGISTRY[strategy]
        if not symbols:
            raise ValueError("At least one symbol is required")
        data_map = self._load_data(symbols, start, end, adj=adj)
        bench_nav = self._load_benchmark(benchmark, start, end) if benchmark else None
        param_dict = module.coerce(params or {})
        nav, metrics = self._execute_strategy(
            module,
            data_map,
            param_dict,
            cash=cash,
            commission=commission,
            slippage=slippage,
            benchmark_nav=bench_nav,
            out_dir=out_dir,
            label="run",
        )
        metrics.update({"strategy": strategy, **param_dict})
        metrics["nav"] = nav
        return metrics

    def grid_search(
        self,
        strategy: str,
        grid: Dict[str, Sequence[Any]],
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        cash: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.001,
        benchmark: Optional[str] = None,
        adj: Optional[str] = None,
        data_map: Optional[Dict[str, pd.DataFrame]] = None,
        bench_nav: Optional[pd.Series] = None,
        max_workers: int = 1,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Evaluate the Cartesian product of parameters and return the score grid."""
        if strategy not in STRATEGY_REGISTRY:
            raise KeyError(f"Unknown strategy: {strategy}")
        module = STRATEGY_REGISTRY[strategy]
        local_data_map = data_map if data_map is not None else self._load_data(symbols, start, end, adj=adj)
        local_bench_nav = bench_nav if bench_nav is not None else (self._load_benchmark(benchmark, start, end) if benchmark else None)
        keys = list(grid.keys())
        combos = list(itertools.product(*grid.values()))
        rows: List[Dict[str, Any]] = []
        broker_conf = dict(cash=cash, commission=commission, slippage=slippage)
        max_workers = max(1, max_workers)

        if max_workers > 1 and len(combos) > 1:
            # 将大对象持久化一次，并在进程启动时加载到全局变量，避免每个任务重复传输
            os.makedirs(self.cache_dir, exist_ok=True)
            data_path = os.path.join(self.cache_dir, f"_grid_data_{int(time.time()*1000)}.pkl")
            bench_path = os.path.join(self.cache_dir, f"_grid_bench_{int(time.time()*1000)}.pkl") if local_bench_nav is not None else None
            with open(data_path, "wb") as f:
                pickle.dump(local_data_map, f, protocol=pickle.HIGHEST_PROTOCOL)
            if bench_path:
                with open(bench_path, "wb") as f:
                    pickle.dump(local_bench_nav, f, protocol=pickle.HIGHEST_PROTOCOL)
            tasks = []
            param_dicts = []
            for combo in combos:
                raw_params = dict(zip(keys, combo))
                param_dict = module.coerce(raw_params)
                if extra_params:
                    # 统一注入额外参数（如 bull_filter_benchmark）
                    param_dict.update(extra_params)
                param_dicts.append(param_dict)
                tasks.append((module.name, param_dict, broker_conf))
            metrics_list: List[Dict[str, Any]] = []
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=max_workers,
                initializer=_grid_worker_init,
                initargs=(data_path, bench_path),
            ) as pool:
                for metrics in pool.map(_grid_worker_task, tasks):
                    metrics_list.append(metrics)
            # 清理临时文件
            try:
                os.remove(data_path)
                if bench_path:
                    os.remove(bench_path)
            except Exception:
                pass
            for param_dict, metrics in zip(param_dicts, metrics_list):
                rows.append({"strategy": strategy, **param_dict, **metrics})
        else:
            for combo in combos:
                raw_params = dict(zip(keys, combo))
                param_dict = module.coerce(raw_params)
                if extra_params:
                    param_dict.update(extra_params)
                try:
                    _, metrics = self._run_module(
                        module,
                        local_data_map,
                        param_dict,
                        cash=cash,
                        commission=commission,
                        slippage=slippage,
                        benchmark_nav=local_bench_nav,
                    )
                except Exception as err:
                    metrics = {
                        "cum_return": float("nan"),
                        "final_value": float("nan"),
                        "sharpe": float("nan"),
                        "mdd": float("nan"),
                        "bench_return": float("nan"),
                        "bench_mdd": float("nan"),
                        "excess_return": float("nan"),
                        "error": str(err),
                    }
                rows.append({"strategy": strategy, **param_dict, **metrics})
        return pd.DataFrame(rows)

    def auto_pipeline(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        strategies: Optional[List[str]] = None,
        benchmark: str = "000300.SH",
        top_n: int = 5,
        min_trades: int = 1,
        cash: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.001,
        adj: Optional[str] = None,
        out_dir: str = "./reports_auto",
        workers: int = 1,
        hot_only: bool = False,
        use_benchmark_regime: bool = False,
        regime_scope: str = "trend",
    ) -> None:
        """Run optimisation for each strategy, combine results, and replay top picks."""
        strategies = strategies or ["ema","macd","bollinger","rsi","turning_point","keltner","zscore","donchian","triple_ma","adx_trend","risk_parity"]
        os.makedirs(out_dir, exist_ok=True)
        start_ts = time.perf_counter()
        data_map = self._load_data(symbols, start, end, adj=adj)
        bench_nav = self._load_benchmark(benchmark, start, end)
        all_rows: List[pd.DataFrame] = []
        for name in strategies:
            module = STRATEGY_REGISTRY.get(name)
            if not module:
                raise KeyError(f"Unknown strategy in auto pipeline: {name}")
            # 使用热区窄网格（可选）
            grid = self._hot_grid(module) if hot_only else module.grid_defaults
            # 若启用“指数判势”，为支持该特性的策略注入统一参数
            extras: Optional[Dict[str, Any]] = None
            if use_benchmark_regime:
                # 只有 turning_point 策略支持这些参数，其他新模块化策略暂不支持
                if name == "turning_point":
                    if regime_scope == "all":
                        extras = {"bull_filter": True, "bull_filter_benchmark": True}
                    elif regime_scope == "none":
                        extras = None
                    else:  # "trend"
                        extras = {"bull_filter": True, "bull_filter_benchmark": True}
            df = self.grid_search(
                name,
                grid,
                symbols,
                start,
                end,
                cash=cash,
                commission=commission,
                slippage=slippage,
                benchmark=benchmark,
                adj=adj,
                data_map=data_map,
                bench_nav=bench_nav,
                max_workers=workers,
                extra_params=extras,
            )
            csv_path = os.path.join(out_dir, f"opt_{name}.csv")
            df.to_csv(csv_path, index=False)
            self._save_heatmap(module, df, out_dir)
            all_rows.append(df)
        big = pd.concat(all_rows, ignore_index=True)
        big.to_csv(os.path.join(out_dir, "opt_all.csv"), index=False)
        pareto = pareto_front(big)
        pareto.to_csv(os.path.join(out_dir, "pareto_front.csv"), index=False)
        self._rerun_top_n(
            pareto,
            symbols,
            start,
            end,
            bench_nav,
            data_map,
            top_n,
            min_trades,
            cash,
            commission,
            slippage,
            out_dir,
            workers=workers,
        )

        elapsed = time.perf_counter() - start_ts
        ordered = big.sort_values(["sharpe", "cum_return", "mdd"], ascending=[False, False, True]).reset_index(drop=True)
        # 统计无交易样本占比，用于提示
        if "trades" in ordered.columns:
            zero_trade_ratio = float((ordered["trades"].fillna(0) <= 0).mean())
            print(f"Zero-trade ratio in grid: {zero_trade_ratio:.1%}")
        top_overall = ordered.head(min(top_n, len(ordered)))

        print(f"Symbols: {', '.join(symbols)} | Benchmark: {benchmark}")
        print(f"Date range: {start} -> {end} | Strategies evaluated: {len(strategies)}")
        print(f"Parameter evaluations: {len(ordered)} | Elapsed: {elapsed:.1f}s")
        print(f"Workers used: {workers}")
        if hot_only:
            print("Grid mode: HOT-ONLY (narrow ranges around empirically good zones)")
        if use_benchmark_regime:
            print(f"Regime filter: BENCHMARK EMA200 (scope={regime_scope})")
        print("\nMetrics legend (rule of thumb):")
        print("  - Sharpe: <0 差; 0~0.5 弱; 0.5~1 尚可; 1~1.5 良好; >1.5 很好")
        print("  - MDD: <0.10 低; 0.10~0.20 中; >0.20 高  （数值为比例，如 0.23=23%）")
        print("  - ProfitFactor: <1 亏损; 1~1.3 边缘; >1.5 稳健; >2 强")
        print("  - WinRate 需结合盈亏比一起看，单看胜率没有意义")
        print("  - PayoffRatio(平均盈亏比): >1 佳; >1.5 很好")
        print("  - Expectancy(单笔期望): >0 代表长期正期望")
        print("  - Calmar: 年化收益/MDD，>0.5 尚可; >1 佳")
        print("  - ExposureRatio: 持仓/暴露时间比例（0~1），越高越主动")
        print("  - TradeFreq: 交易频率 = trades/样本天数（越高越频繁）")
        if not top_overall.empty:
            print("Top configurations (ordered by Sharpe, return, drawdown):")
            for idx, row in top_overall.iterrows():
                info = [f"strategy={row['strategy']}"]
                for key in ["topn", "gap", "reversal", "vol_surge", "vwap_window", "period", "fast", "slow", "signal", "devfactor", "upper", "lower"]:
                    if key in row and pd.notna(row[key]):
                        val = row[key]
                        if isinstance(val, bool):
                            info.append(f"{key}={val}")
                        elif isinstance(val, (int, float)):
                            info.append(f"{key}={float(val):.3f}")
                        else:
                            info.append(f"{key}={val}")
                sharpe_val = row["sharpe"]
                sharpe_str = f"{sharpe_val:.3f}" if pd.notna(sharpe_val) else "nan"
                extras = []
                for k in ["ann_return","ann_vol","win_rate","profit_factor","trades","payoff_ratio","expectancy","calmar","exposure_ratio","trade_freq","bench_return","bench_mdd","excess_return"]:
                    if k in row and pd.notna(row[k]):
                        try:
                            extras.append(f"{k}={float(row[k]):.3f}")
                        except Exception:
                            extras.append(f"{k}={row[k]}")
                metrics = f"sharpe={sharpe_str}, cum_return={row['cum_return']:.3f}, mdd={row['mdd']:.3f}" + (", " + ", ".join(extras) if extras else "")
                print(f"  - {'; '.join(info)} | {metrics}")
        best_by_strategy = ordered.groupby('strategy', sort=False).head(1)
        if not best_by_strategy.empty:
            print("Best per strategy:")
            for _, row in best_by_strategy.iterrows():
                sharpe_val = row['sharpe']
                sharpe_str = f"{sharpe_val:.3f}" if pd.notna(sharpe_val) else "nan"
                msg = f"  * {row['strategy']}: sharpe={sharpe_str}, cum_return={row['cum_return']:.3f}, mdd={row['mdd']:.3f}"
                for k in ["win_rate","profit_factor","trades","payoff_ratio","expectancy","calmar"]:
                    if k in row and pd.notna(row[k]):
                        try:
                            msg += f", {k}={float(row[k]):.3f}"
                        except Exception:
                            msg += f", {k}={row[k]}"
                error_msg = row.get("error")
                if isinstance(error_msg, str) and error_msg:
                    short_err = error_msg if len(error_msg) <= 80 else error_msg[:77] + "..."
                    msg += f", error={short_err}"
                print(msg)
        print(f"Reports written to {out_dir}\n")

    @staticmethod
    def _hot_grid(module: StrategyModule) -> Dict[str, Sequence[Any]]:
        """Return a narrowed parameter grid for known strategies (hot zones)."""
        if module.name == "bollinger":
            # Filter to only include supported parameters
            return {"period": [10, 12, 14, 16], "devfactor": [2.2, 2.5],
                    "entry_mode": ["pierce", "close_below"], "exit_mode": ["mid"]}
        if module.name == "macd":
            return {"fast": [10, 11, 12, 13], "slow": [13, 14, 15, 16, 17], "signal": [9]}
        if module.name == "rsi":
            # Only include supported parameters (no bull_filter, min_holding_bars, cooldown_bars)
            return {"period": [14, 18, 20, 22], "upper": [70, 75], "lower": [25, 30]}
        if module.name == "keltner":
            return {"ema_period": [12, 16, 20], "atr_period": [14], "kc_mult": [1.8, 2.0, 2.2],
                    "entry_mode": ["pierce", "close_below"], "exit_mode": ["mid"]}
        if module.name == "zscore":
            return {"period": [14, 18, 22], "z_entry": [-1.8, -2.0, -2.2], "z_exit": [-0.7, -0.4]}
        if module.name == "donchian":
            # Only include supported parameters
            return {"upper": [18,20,22], "lower": [8,10,12]}
        if module.name == "triple_ma":
            return {"fast":[5,8], "mid":[18,20,22], "slow":[55,60,65]}
        if module.name == "adx_trend":
            # Only include supported parameters
            return {"adx_period":[12,14,16], "adx_th":[20,25,30]}
        if module.name == "risk_parity":
            return {"vol_window":[20,30], "rebalance_days":[21], "max_weight":[0.3,0.4,0.5],
                    "use_benchmark_gate": [True], "bench_gate_period": [150, 200], "bench_risk_off_weight": [0.0, 0.3]}
        # 其余保持默认
        return dict(module.grid_defaults)

    @staticmethod
    def _save_heatmap(module: StrategyModule, df: pd.DataFrame, out_dir: str) -> None:
        """Persist quick-look visualisations for optimisation surfaces."""
        import matplotlib.pyplot as plt  # local import
        import numpy as np
        import os
        
        def _safe_imshow(piv_val: pd.DataFrame, piv_tr: pd.DataFrame, title: str,
                         xlab: str, ylab: str, out_path: str) -> None:
            vals = piv_val.copy()
            # 对齐 trades 表
            mask = None
            if piv_tr is not None and piv_tr.shape == vals.shape:
                mask = (piv_tr.values.astype(float) <= 0)
            arr = vals.values.astype(float)
            if mask is not None:
                arr = np.ma.masked_where(mask, arr)
            # 处理单行/单列：用 extent+aspect 避免 identical x/y lims 告警
            fig, ax = plt.subplots()
            nrow, ncol = arr.shape
            extent = [0, max(ncol, 1), 0, max(nrow, 1)]
            im = ax.imshow(arr, aspect="auto", origin="lower", extent=extent)
            ax.set_title(title); ax.set_xlabel(xlab); ax.set_ylabel(ylab)
            # 友好刻度（即使只有一列/一行也正常显示标签）
            ax.set_xticks(np.arange(ncol) + 0.5)
            ax.set_yticks(np.arange(nrow) + 0.5)
            ax.set_xticklabels(list(vals.columns))
            ax.set_yticklabels(list(vals.index))
            fig.colorbar(im)
            fig.tight_layout(); fig.savefig(out_path); plt.close(fig)

        def _mask_zero_trades(piv_val: pd.DataFrame, piv_tr: pd.DataFrame) -> np.ndarray:
            arr = piv_val.values.astype(float)
            if piv_tr is not None:
                # 确保两个数组的形状一致
                if piv_tr.shape == piv_val.shape:
                    mask = (piv_tr.values.astype(float) <= 0)
                    arr = np.ma.masked_where(mask, arr)
            return arr

        # 优先用 expectancy（更能反映单位交易质量），否则用 cum_return
        val_key = "expectancy" if "expectancy" in df.columns else "cum_return"
        if module.name == "ema" and "period" in df.columns:
            df_sorted = df.sort_values("period")
            plt.figure()
            plt.plot(df_sorted["period"], df_sorted[val_key])
            # 在 trades==0 的点位上标注“×”，方便一眼定位“无成交参数”
            if "trades" in df_sorted.columns:
                z = df_sorted["trades"].fillna(0) <= 0
                if z.any():
                    plt.scatter(df_sorted.loc[z, "period"], df_sorted.loc[z, val_key], marker="x")
            plt.title(f"EMA period vs {val_key}")
            plt.xlabel("period")
            plt.ylabel(val_key)
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "heat_ema.png"))
            plt.close()
        elif module.name == "macd" and {"fast", "slow"}.issubset(df.columns):
            piv = df.pivot_table(index="fast", columns="slow", values=val_key, aggfunc="mean")
            piv_tr = df.pivot_table(index="fast", columns="slow", values="trades", aggfunc="sum") if "trades" in df.columns else None
            _safe_imshow(piv, piv_tr, f"MACD {val_key}", "slow", "fast", os.path.join(out_dir, "heat_macd.png"))
        elif module.name == "bollinger" and {"period", "devfactor"}.issubset(df.columns):
            piv = df.pivot_table(index="period", columns="devfactor", values=val_key, aggfunc="mean")
            piv_tr = df.pivot_table(index="period", columns="devfactor", values="trades", aggfunc="sum") if "trades" in df.columns else None
            _safe_imshow(piv, piv_tr, f"Bollinger {val_key}", "devfactor", "period", os.path.join(out_dir, "heat_bollinger.png"))
        elif module.name == "rsi" and {"period", "upper"}.issubset(df.columns):
            piv = df.pivot_table(index="period", columns="upper", values=val_key, aggfunc="mean")
            piv_tr = df.pivot_table(index="period", columns="upper", values="trades", aggfunc="sum") if "trades" in df.columns else None
            _safe_imshow(piv, piv_tr, f"RSI {val_key}", "upper", "period", os.path.join(out_dir, "heat_rsi.png"))
        elif module.name == "zscore" and "period" in df.columns:
            df_sorted = df.sort_values("period")
            plt.figure()
            plt.plot(df_sorted["period"], df_sorted[val_key])
            if "trades" in df_sorted.columns:
                z = df_sorted["trades"].fillna(0) <= 0
                if z.any():
                    plt.scatter(df_sorted.loc[z, "period"], df_sorted.loc[z, val_key], marker="x")
            plt.title(f"ZScore period vs {val_key}")
            plt.xlabel("period"); plt.ylabel(val_key)
            plt.tight_layout(); plt.savefig(os.path.join(out_dir, "heat_zscore.png")); plt.close()
        elif module.name == "donchian" and {"upper","lower"}.issubset(df.columns):
            piv = df.pivot_table(index="lower", columns="upper", values=val_key, aggfunc="mean")
            piv_tr = df.pivot_table(index="lower", columns="upper", values="trades", aggfunc="sum") if "trades" in df.columns else None
            _safe_imshow(piv, piv_tr, f"Donchian {val_key}", "upper", "lower", os.path.join(out_dir, "heat_donchian.png"))
        elif module.name == "triple_ma" and {"fast","mid","slow"}.issubset(df.columns):
            # 用 fast 对 mid 的剖面（slow 取均值）
            piv = df.pivot_table(index="fast", columns="mid", values=val_key, aggfunc="mean")
            piv_tr = df.pivot_table(index="fast", columns="mid", values="trades", aggfunc="sum") if "trades" in df.columns else None
            _safe_imshow(piv, piv_tr, f"TripleMA {val_key}", "mid", "fast", os.path.join(out_dir, "heat_triple_ma.png"))
        elif module.name == "adx_trend" and {"adx_period","adx_th"}.issubset(df.columns):
            piv = df.pivot_table(index="adx_period", columns="adx_th", values=val_key, aggfunc="mean")
            piv_tr = df.pivot_table(index="adx_period", columns="adx_th", values="trades", aggfunc="sum") if "trades" in df.columns else None
            _safe_imshow(piv, piv_tr, f"ADX {val_key}", "adx_th", "adx_period", os.path.join(out_dir, "heat_adx.png"))
        elif module.name == "risk_parity" and "vol_window" in df.columns:
            if "max_weight" in df.columns:
                piv = df.pivot_table(index="vol_window", columns="max_weight", values=val_key, aggfunc="mean")
                piv_tr = df.pivot_table(index="vol_window", columns="max_weight", values="trades", aggfunc="sum") if "trades" in df.columns else None
                _safe_imshow(piv, piv_tr, f"RiskParity {val_key}", "max_weight", "vol_window", os.path.join(out_dir, "heat_risk_parity.png"))
            else:
                df_sorted = df.sort_values("vol_window")
                plt.figure(); plt.plot(df_sorted["vol_window"], df_sorted[val_key])
                plt.title(f"RiskParity vol_window vs {val_key}"); plt.xlabel("vol_window"); plt.ylabel(val_key)
                plt.tight_layout(); plt.savefig(os.path.join(out_dir, "heat_risk_parity.png")); plt.close()
        # 控制台提示零交易占比，帮助判断“图为何很平”
        if "trades" in df.columns and len(df) > 0:
            zero_ratio = float((df["trades"].fillna(0) <= 0).mean())
            print(f"[{module.name}] zero-trade cells: {zero_ratio:.1%}")
    def _rerun_top_n(
        self,
        pareto_df: pd.DataFrame,
        symbols: Sequence[str],
        start: str,
        end: str,
        bench_nav: pd.Series,
        data_map: Dict[str, pd.DataFrame],
        top_n: int,
        min_trades: int,
        cash: float,
        commission: float,
        slippage: float,
        out_dir: str,
        workers: int,
    ) -> None:
        """Replay the best candidates from the Pareto frontier to produce NAV curves."""
        if pareto_df.empty:
            return
        df = pareto_df.copy()
        # 1) 先过滤掉“无成交/无暴露”的解，确保画出的曲线不是贴 1 的直线
        if "trades" in df.columns:
            df1 = df[(df["trades"].fillna(0) >= float(min_trades)) & (df.get("exposure_ratio", 0).astype(float) > 0)]
        else:
            df1 = df
        # 2) 如果太少，放宽为 trades>0
        if len(df1) < top_n and "trades" in df.columns:
            df2 = df[(df["trades"].fillna(0) > 0)]
            df1 = pd.concat([df1, df2]).drop_duplicates().head(max(top_n, len(df1)))
        filtered_out = len(df) - len(df1)
        if filtered_out > 0:
            print(f"Filtered {filtered_out} zero-trade/zero-exposure configs before Top-N replay.")
        head = df1.sort_values(["sharpe", "cum_return"], ascending=[False, False]).head(top_n)
        tasks = []
        for idx, row in head.iterrows():
            name = str(row["strategy"])
            module = STRATEGY_REGISTRY.get(name)
            if not module:
                continue
            params = {key: row[key] for key in module.param_names if key in row and not pd.isna(row[key])}
            params = module.coerce(params)
            tasks.append((f"{name}_{idx}", module, params))
        if not tasks:
            return

        def _run_single(label: str, module: StrategyModule, params: Dict[str, Any]) -> Tuple[str, pd.Series]:
            local_map = {sym: df.copy(deep=False) for sym, df in data_map.items()}
            nav, _ = self._run_module(
                module,
                local_map,
                params,
                cash=cash,
                commission=commission,
                slippage=slippage,
                benchmark_nav=bench_nav,
            )
            return label, nav

        nav_dict: Dict[str, pd.Series] = {}
        if workers > 1 and len(tasks) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(_run_single, label, module, params): label for label, module, params in tasks}
                for future in concurrent.futures.as_completed(future_map):
                    label, nav = future.result()
                    nav_dict[label] = nav
        else:
            for label, module, params in tasks:
                label, nav = _run_single(label, module, params)
                nav_dict[label] = nav

        if nav_dict:
            combined = pd.concat([series.rename(label) for label, series in nav_dict.items()], axis=1).dropna()
            combined.to_csv(os.path.join(out_dir, "topN_navs.csv"))
            import matplotlib.pyplot as plt  # local import

            plt.figure()
            combined.plot()
            plt.title("Top-N strategies NAV")
            plt.tight_layout()
            plt.savefig(os.path.join(out_dir, "topN_navs.png"))
            plt.close()

def _grid_worker_task(payload: tuple) -> Dict[str, Any]:
    """Process-pool worker used by `grid_search` to evaluate a parameter set."""
    module_name, params, broker_conf = payload
    data_map = _G_DATA_MAP
    benchmark_nav = _G_BENCH_NAV
    module = STRATEGY_REGISTRY[module_name]
    try:
        _, metrics = BacktestEngine._run_module(
            module,
            data_map,
            params,
            cash=broker_conf["cash"],
            commission=broker_conf["commission"],
            slippage=broker_conf["slippage"],
            benchmark_nav=benchmark_nav,
        )
        return metrics
    except Exception as err:  # pragma: no cover - safety net for worker failures
        return {
            "cum_return": float("nan"),
            "final_value": float("nan"),
            "sharpe": float("nan"),
            "mdd": float("nan"),
            "bench_return": float("nan"),
            "bench_mdd": float("nan"),
            "excess_return": float("nan"),
            "error": str(err),
        }

# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------
def pareto_front(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out dominated configurations based on Sharpe, return, and drawdown."""
    needed = ["sharpe", "cum_return", "mdd"]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"pareto_front missing required column: {col}")
    vals = df[needed].astype(float).values
    dominated = np.zeros(len(df), dtype=bool)
    for i, (si, ri, di) in enumerate(vals):
        for j, (sj, rj, dj) in enumerate(vals):
            if i == j:
                continue
            if (sj >= si) and (rj >= ri) and (dj <= di) and ((sj > si) or (rj > ri) or (dj < di)):
                dominated[i] = True
                break
    return df.loc[~dominated]

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    """Build the CLI interface and return parsed arguments."""
    parser = argparse.ArgumentParser(description="Unified akshare/yfinance/tushare backtest framework")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a single strategy backtest")
    run_p.add_argument("--strategy", default="turning_point", choices=sorted(STRATEGY_REGISTRY.keys()))
    run_p.add_argument("--symbols", nargs="+", required=True)
    run_p.add_argument("--start", required=True)
    run_p.add_argument("--end", required=True)
    run_p.add_argument("--source", default="akshare", choices=sorted(_PROVIDER_FACTORIES.keys()))
    run_p.add_argument("--benchmark", default=None)
    run_p.add_argument("--benchmark_source", default=None)
    run_p.add_argument("--params", default=None, help="JSON string of strategy params")
    run_p.add_argument("--cash", type=float, default=100000)
    run_p.add_argument("--commission", type=float, default=0.001)
    run_p.add_argument("--slippage", type=float, default=0.001)
    run_p.add_argument("--adj", default=None)
    run_p.add_argument("--out_dir", default=None)
    run_p.add_argument("--cache_dir", default=CACHE_DEFAULT)

    grid_p = sub.add_parser("grid", help="Run grid search for a strategy")
    grid_p.add_argument("--strategy", required=True, choices=sorted(STRATEGY_REGISTRY.keys()))
    grid_p.add_argument("--symbols", nargs="+", required=True)
    grid_p.add_argument("--start", required=True)
    grid_p.add_argument("--end", required=True)
    grid_p.add_argument("--grid", required=False, default=None, help="JSON like {'period':[10,20]} (defaults to module grid)")
    grid_p.add_argument("--source", default="akshare", choices=sorted(_PROVIDER_FACTORIES.keys()))
    grid_p.add_argument("--benchmark", default=None)
    grid_p.add_argument("--benchmark_source", default=None)
    grid_p.add_argument("--cash", type=float, default=100000)
    grid_p.add_argument("--commission", type=float, default=0.001)
    grid_p.add_argument("--slippage", type=float, default=0.001)
    grid_p.add_argument("--adj", default=None)
    grid_p.add_argument("--cache_dir", default=CACHE_DEFAULT)
    grid_p.add_argument("--out_csv", default=None)
    grid_p.add_argument("--workers", type=int, default=1)

    auto_p = sub.add_parser("auto", help="Run multi-strategy optimisation + Pareto + Top-N")
    auto_p.add_argument("--symbols", nargs="+", required=True)
    auto_p.add_argument("--start", required=True)
    auto_p.add_argument("--end", required=True)
    auto_p.add_argument("--source", default="akshare", choices=sorted(_PROVIDER_FACTORIES.keys()))
    auto_p.add_argument("--benchmark", default="000300.SH")
    auto_p.add_argument("--benchmark_source", default=None)
    auto_p.add_argument("--strategies", nargs="*", default=None, choices=sorted(STRATEGY_REGISTRY.keys()))
    auto_p.add_argument("--top_n", type=int, default=5)
    auto_p.add_argument("--min_trades", type=int, default=1,
                        help="Require at least this many closed trades when selecting Top-N for replay/plot")
    auto_p.add_argument("--cash", type=float, default=100000)
    auto_p.add_argument("--commission", type=float, default=0.001)
    auto_p.add_argument("--slippage", type=float, default=0.001)
    auto_p.add_argument("--adj", default=None)
    auto_p.add_argument("--cache_dir", default=CACHE_DEFAULT)
    auto_p.add_argument("--out_dir", default="./reports_auto")
    auto_p.add_argument("--workers", type=int, default=1)
    auto_p.add_argument("--hot_only", action="store_true", help="Use narrowed hot-zone parameter grids for strategies")
    auto_p.add_argument("--use_benchmark_regime", action="store_true",
                        help="Use benchmark EMA200 as bull regime filter (see --regime_scope)")
    auto_p.add_argument("--regime_scope", default="trend", choices=["trend", "all", "none"],
                        help="Apply regime filter to: trend strategies only (ema/macd/turning_point), or all, or none.")
    sub.add_parser("list", help="List registered strategies")

    return parser.parse_args()

def main() -> None:
    """Entrypoint used by the console script or direct module execution."""
    args = parse_args()
    if args.command == "list":
        print("Available strategies:")
        for name, module in STRATEGY_REGISTRY.items():
            print(f"- {name}: {module.description}")
        return

    if args.command == "run":
        params = json.loads(args.params) if args.params else None
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
        )
        metrics = engine.run_strategy(
            args.strategy,
            args.symbols,
            args.start,
            args.end,
            params=params,
            cash=args.cash,
            commission=args.commission,
            slippage=args.slippage,
            benchmark=args.benchmark,
            adj=args.adj,
            out_dir=args.out_dir,
        )
        nav = metrics.pop("nav")
        print(json.dumps({k: v for k, v in metrics.items() if k != "nav"}, indent=2, default=float))
        if args.out_dir:
            os.makedirs(args.out_dir, exist_ok=True)
            nav.to_csv(os.path.join(args.out_dir, f"{args.strategy}_nav.csv"))
        return

    if args.command == "grid":
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
        )
        module = STRATEGY_REGISTRY[args.strategy]
        grid = json.loads(args.grid) if args.grid else module.grid_defaults
        df = engine.grid_search(
            args.strategy,
            grid,
            args.symbols,
            args.start,
            args.end,
            cash=args.cash,
            commission=args.commission,
            slippage=args.slippage,
            benchmark=args.benchmark,
            adj=args.adj,
            max_workers=args.workers,
        )
        if args.out_csv:
            df.to_csv(args.out_csv, index=False)
        else:
            print(df.head())
        return

    if args.command == "auto":
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
        )
        engine.auto_pipeline(
            args.symbols,
            args.start,
            args.end,
            strategies=args.strategies,
            benchmark=args.benchmark,
            top_n=args.top_n,
            min_trades=args.min_trades,
            cash=args.cash,
            commission=args.commission,
            slippage=args.slippage,
            adj=args.adj,
            out_dir=args.out_dir,
            workers=args.workers,
            hot_only=args.hot_only,
            use_benchmark_regime=args.use_benchmark_regime,
            regime_scope=args.regime_scope,
        )
        print(f"Pipeline completed. Results saved to {args.out_dir}")
        return

if __name__ == "__main__":  # pragma: no cover
    main()
