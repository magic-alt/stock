"""Helpers for serializing backtest chart series for platform APIs."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _point_label(index_value: Any, fallback: int) -> str:
    if hasattr(index_value, "strftime"):
        return index_value.strftime("%Y-%m-%d")
    if index_value is None:
        return str(fallback)
    return str(index_value)


def build_curve_points(series: Any) -> List[Dict[str, float | str]]:
    """Convert a pandas Series/list/dict into frontend chart points."""
    if series is None:
        return []
    if isinstance(series, dict):
        items = list(series.items())
    elif hasattr(series, "items"):
        items = list(series.items())
    elif isinstance(series, (list, tuple)):
        items = list(enumerate(series))
    else:
        return []

    points: List[Dict[str, float | str]] = []
    for fallback, (index_value, raw_value) in enumerate(items):
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        points.append({"date": _point_label(index_value, fallback), "value": round(value, 6)})
    return points


def build_drawdown_points(curve: List[Dict[str, float | str]]) -> List[Dict[str, float | str]]:
    """Build drawdown points from normalized NAV chart points."""
    peak = 0.0
    drawdown: List[Dict[str, float | str]] = []
    for point in curve:
        value = float(point["value"])
        peak = max(peak, value)
        dd = 0.0 if peak <= 0 else value / peak - 1.0
        drawdown.append({"date": str(point["date"]), "value": round(dd, 6)})
    return drawdown


def build_nav_chart_payload(nav: Any) -> Dict[str, List[Dict[str, float | str]]]:
    """Return equity and drawdown curves derived from a backtest NAV series."""
    equity_curve = build_curve_points(nav)
    return {
        "equity_curve": equity_curve,
        "drawdown_curve": build_drawdown_points(equity_curve),
    }


def _finite_or_none(value: Any, digits: int = 6) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return round(numeric, digits)


def _series_values(series: Any, digits: int = 6) -> List[Optional[float]]:
    return [_finite_or_none(value, digits=digits) for value in series]


def _prepare_ohlcv_frame(raw_df: Any) -> Any:
    try:
        import pandas as pd
    except ImportError:
        return None
    if raw_df is None or not hasattr(raw_df, "copy"):
        return None
    df = raw_df.copy()
    required = ["open", "high", "low", "close"]
    if any(column not in df.columns for column in required):
        return None
    for column in ["open", "high", "low", "close", "volume"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df.dropna(subset=required)
    df["volume"] = df["volume"].fillna(0.0)
    return df


def _build_indicator_payload(df: Any) -> Dict[str, Any]:
    close = df["close"]
    high = df["high"]
    low = df["low"]

    ma = {
        "ma5": _series_values(close.rolling(5, min_periods=5).mean()),
        "ma10": _series_values(close.rolling(10, min_periods=10).mean()),
        "ma20": _series_values(close.rolling(20, min_periods=20).mean()),
        "ma30": _series_values(close.rolling(30, min_periods=30).mean()),
    }
    boll_mid = close.rolling(20, min_periods=20).mean()
    boll_std = close.rolling(20, min_periods=20).std(ddof=0)

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    hist = macd - signal

    low_min = low.rolling(9, min_periods=9).min()
    high_max = high.rolling(9, min_periods=9).max()
    rsv = (close - low_min) / (high_max - low_min).replace(0, float("nan")) * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False, min_periods=1).mean()
    d = k.ewm(alpha=1 / 3, adjust=False, min_periods=1).mean()
    j = 3 * k - 2 * d

    return {
        "ma": ma,
        "boll": {
            "upper": _series_values(boll_mid + 2 * boll_std),
            "mid": _series_values(boll_mid),
            "lower": _series_values(boll_mid - 2 * boll_std),
        },
        "rsi": _series_values(rsi),
        "macd": {
            "dif": _series_values(macd),
            "signal": _series_values(signal),
            "hist": _series_values(hist),
        },
        "kdj": {
            "k": _series_values(k),
            "d": _series_values(d),
            "j": _series_values(j),
        },
    }


def _extract_trade_markers(cerebro: Any) -> List[Dict[str, Any]]:
    markers: List[Dict[str, Any]] = []
    try:
        import backtrader as bt
    except ImportError:
        return markers
    try:
        strat = cerebro.runstrats[0][0]
    except Exception:
        return markers

    for order in getattr(strat, "_orders", []) or []:
        try:
            if order.status != order.Completed:
                continue
            executed = order.executed
            executed_date = bt.num2date(executed.dt)
            price = _finite_or_none(executed.price, digits=4)
            size = _finite_or_none(executed.size, digits=2)
            if price is None:
                continue
            markers.append(
                {
                    "date": executed_date.strftime("%Y-%m-%d"),
                    "type": "BUY" if order.isbuy() else "SELL",
                    "price": price,
                    "size": size,
                    "symbol": getattr(getattr(order, "data", None), "_name", ""),
                }
            )
        except Exception:
            continue

    if markers:
        return sorted(markers, key=lambda item: str(item.get("date", "")))

    for item in getattr(strat, "order_log", []) or []:
        if not isinstance(item, dict):
            continue
        raw_date = item.get("date")
        price = _finite_or_none(item.get("price"), digits=4)
        if raw_date is None or price is None:
            continue
        markers.append(
            {
                "date": raw_date.strftime("%Y-%m-%d") if hasattr(raw_date, "strftime") else str(raw_date),
                "type": str(item.get("type", "")).upper(),
                "price": price,
                "size": _finite_or_none(item.get("size"), digits=2),
                "symbol": str(item.get("symbol", "")),
            }
        )
    return sorted(markers, key=lambda item: str(item.get("date", "")))


def build_technical_chart_payload_from_frame(raw_df: Any, *, symbol: str = "") -> Dict[str, Any]:
    """Serialize OHLCV and indicators from a pandas frame for CLI-style web charts."""
    empty = {"technical_chart": None}
    df = _prepare_ohlcv_frame(raw_df)
    if df is None or df.empty:
        return empty

    dates = [_point_label(index_value, fallback) for fallback, index_value in enumerate(df.index)]
    ohlc = [
        [
            _finite_or_none(row["open"], digits=4),
            _finite_or_none(row["close"], digits=4),
            _finite_or_none(row["low"], digits=4),
            _finite_or_none(row["high"], digits=4),
        ]
        for _, row in df.iterrows()
    ]
    volumes = [_finite_or_none(value, digits=2) or 0.0 for value in df["volume"]]

    return {
        "technical_chart": {
            "symbol": symbol or "data0",
            "dates": dates,
            "ohlc": ohlc,
            "volumes": volumes,
            "trades": [],
            **_build_indicator_payload(df),
        }
    }


def build_technical_chart_payload(cerebro: Any) -> Dict[str, Any]:
    """Serialize Backtrader OHLCV, indicators, and trades for CLI-style web charts."""
    empty = {"technical_chart": None}
    if cerebro is None or not getattr(cerebro, "datas", None):
        return empty
    data = cerebro.datas[0]
    payload = build_technical_chart_payload_from_frame(
        getattr(data, "_dataname", None),
        symbol=getattr(data, "_name", "") or "data0",
    )
    if payload.get("technical_chart"):
        payload["technical_chart"]["trades"] = _extract_trade_markers(cerebro)
    return payload