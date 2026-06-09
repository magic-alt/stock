"""Beginner-friendly stock analysis workflow for the platform API.

The service intentionally works without broker SDKs, provider tokens, or
network access when ``source=sample`` is used. Real providers remain available
through the existing data provider factory.
"""

from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.core.logger import get_logger

logger = get_logger("platform.analysis")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE_DATA = PROJECT_ROOT / "sample_data" / "a_share_demo_ohlcv.csv"
SUPPORTED_ANALYSIS_SOURCES = ("sample", "auto", "akshare", "yfinance", "tushare")


@dataclass(frozen=True)
class AnalysisRequestPayload:
    """Validated analysis request used by API and job runners."""

    symbol: str
    days: int = 120
    source: str = "sample"
    strategy: str = "macd"
    include_backtest: bool = True
    use_ai: bool = False
    sample_data_path: Optional[str] = None


def run_stock_analysis_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """JobQueue task runner for stock analysis jobs."""
    return StockAnalysisService().analyze(AnalysisRequestPayload(**payload))


class StockAnalysisService:
    """Build a deterministic stock analysis report from OHLCV history."""

    def __init__(self, sample_data_path: Optional[Path] = None) -> None:
        self.sample_data_path = sample_data_path or DEFAULT_SAMPLE_DATA

    def analyze(self, request: AnalysisRequestPayload) -> Dict[str, Any]:
        symbol = request.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol is required")

        days = max(10, min(int(request.days), 500))
        source = request.source.strip().lower() or "sample"
        if source not in SUPPORTED_ANALYSIS_SOURCES:
            raise ValueError(f"unsupported analysis source: {source}")

        frame, data_quality = self._load_history(
            symbol=symbol,
            days=days,
            source=source,
            sample_data_path=Path(request.sample_data_path) if request.sample_data_path else self.sample_data_path,
        )
        if frame.empty:
            raise LookupError(f"no OHLCV data found for {symbol}")

        frame = frame.tail(days).copy()
        indicators = self._calculate_indicators(frame)
        signal = self._build_signal(frame, indicators)
        chart_data = self._build_chart_payload(frame)
        backtest_preview = (
            self._build_backtest_preview(frame, strategy=request.strategy)
            if request.include_backtest
            else {"enabled": False, "reason": "disabled_by_request"}
        )
        ai_summary = self._build_ai_summary(
            enabled=bool(request.use_ai),
            symbol=symbol,
            signal=signal,
            indicators=indicators,
            data_quality=data_quality,
        )
        price = self._build_price_summary(frame)
        markdown_report = self._build_markdown_report(
            symbol=symbol,
            price=price,
            indicators=indicators,
            signal=signal,
            data_quality=data_quality,
            backtest_preview=backtest_preview,
            ai_summary=ai_summary,
        )

        return {
            "symbol": symbol,
            "as_of": self._last_date(frame),
            "data_quality": data_quality,
            "price": price,
            "indicators": indicators,
            "signal": signal,
            "chart_data": chart_data,
            "backtest_preview": backtest_preview,
            "ai_summary": ai_summary,
            "markdown_report": markdown_report,
        }

    def _load_history(
        self,
        *,
        symbol: str,
        days: int,
        source: str,
        sample_data_path: Path,
    ) -> tuple[pd.DataFrame, Dict[str, Any]]:
        warnings: List[str] = []
        attempted: List[str] = []

        if source == "sample":
            frame = self._load_sample_history(symbol, sample_data_path)
            return self._normalize_frame(frame), {
                "source": "sample",
                "rows": int(len(frame)),
                "warnings": warnings,
                "sample_data": str(sample_data_path),
            }

        providers = ["akshare", "yfinance"] if source == "auto" else [source]
        for provider_name in providers:
            attempted.append(provider_name)
            try:
                frame = self._load_provider_history(symbol, days=days, provider_name=provider_name)
                if not frame.empty:
                    normalized = self._normalize_frame(frame)
                    return normalized, {
                        "source": provider_name,
                        "rows": int(len(normalized)),
                        "warnings": warnings,
                        "attempted_sources": attempted,
                    }
            except Exception as exc:
                message = f"{provider_name} failed: {exc}"
                warnings.append(message)
                logger.warning("analysis_provider_failed", symbol=symbol, provider=provider_name, error=str(exc))

        if source == "auto":
            sample = self._normalize_frame(self._load_sample_history(symbol, sample_data_path))
            if not sample.empty:
                warnings.append("real providers unavailable; fell back to bundled sample data")
                return sample, {
                    "source": "sample",
                    "rows": int(len(sample)),
                    "warnings": warnings,
                    "attempted_sources": attempted,
                    "sample_data": str(sample_data_path),
                }

        return pd.DataFrame(), {"source": source, "rows": 0, "warnings": warnings, "attempted_sources": attempted}

    def _load_sample_history(self, symbol: str, path: Path) -> pd.DataFrame:
        if not path.is_file():
            raise FileNotFoundError(f"sample data not found: {path}")
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if str(row.get("symbol", "")).upper() == symbol:
                    rows.append(row)
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows)
        frame["date"] = pd.to_datetime(frame["date"])
        frame.set_index("date", inplace=True)
        return frame

    def _load_provider_history(self, symbol: str, *, days: int, provider_name: str) -> pd.DataFrame:
        from datetime import timedelta

        from src.data_sources.providers import get_provider

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=int(days * 1.8))).strftime("%Y-%m-%d")
        provider = get_provider(provider_name)
        data_map = provider.load_stock_daily([symbol], start, end)
        return data_map.get(symbol, pd.DataFrame())

    def _normalize_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        out = frame.copy()
        rename = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        out.rename(columns=rename, inplace=True)
        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"])
            out.set_index("date", inplace=True)
        out.index = pd.to_datetime(out.index)
        for column in ["open", "high", "low", "close", "volume"]:
            if column not in out.columns:
                raise ValueError(f"missing OHLCV column: {column}")
            out[column] = pd.to_numeric(out[column], errors="coerce")
        out = out.dropna(subset=["open", "high", "low", "close"]).sort_index()
        out["volume"] = out["volume"].fillna(0.0)
        return out

    def _calculate_indicators(self, frame: pd.DataFrame) -> Dict[str, Any]:
        close = frame["close"]
        high = frame["high"]
        low = frame["low"]
        volume = frame["volume"]
        ma5 = close.rolling(5, min_periods=1).mean()
        ma10 = close.rolling(10, min_periods=1).mean()
        ma20 = close.rolling(20, min_periods=1).mean()
        ema12 = close.ewm(span=12, adjust=False, min_periods=1).mean()
        ema26 = close.ewm(span=26, adjust=False, min_periods=1).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9, adjust=False, min_periods=1).mean()
        macd_hist = macd - macd_signal
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(14, min_periods=1).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - (100 / (1 + rs))).fillna(50.0)
        boll_mid = ma20
        boll_std = close.rolling(20, min_periods=2).std().fillna(0.0)
        boll_upper = boll_mid + boll_std * 2
        boll_lower = boll_mid - boll_std * 2
        atr = pd.concat(
            [
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1).rolling(14, min_periods=1).mean()
        volume_ma20 = volume.rolling(20, min_periods=1).mean()

        latest_close = float(close.iloc[-1])
        return {
            "ma": {
                "ma5": self._round(ma5.iloc[-1]),
                "ma10": self._round(ma10.iloc[-1]),
                "ma20": self._round(ma20.iloc[-1]),
                "trend": "up" if ma5.iloc[-1] >= ma20.iloc[-1] else "down",
            },
            "rsi": self._round(rsi.iloc[-1]),
            "macd": {
                "dif": self._round(macd.iloc[-1]),
                "signal": self._round(macd_signal.iloc[-1]),
                "hist": self._round(macd_hist.iloc[-1]),
                "bias": "bullish" if macd_hist.iloc[-1] >= 0 else "bearish",
            },
            "bollinger": {
                "upper": self._round(boll_upper.iloc[-1]),
                "middle": self._round(boll_mid.iloc[-1]),
                "lower": self._round(boll_lower.iloc[-1]),
                "position": self._round((latest_close - boll_lower.iloc[-1]) / max(boll_upper.iloc[-1] - boll_lower.iloc[-1], 1e-9)),
            },
            "atr14": self._round(atr.iloc[-1]),
            "volume": {
                "latest": self._round(volume.iloc[-1], digits=0),
                "ma20": self._round(volume_ma20.iloc[-1], digits=0),
                "ratio": self._round(volume.iloc[-1] / max(volume_ma20.iloc[-1], 1e-9)),
            },
        }

    def _build_signal(self, frame: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        latest = float(frame["close"].iloc[-1])
        previous = float(frame["close"].iloc[-2]) if len(frame) > 1 else latest
        ma = indicators["ma"]
        macd = indicators["macd"]
        rsi = float(indicators["rsi"])
        boll = indicators["bollinger"]
        volume_ratio = float(indicators["volume"]["ratio"])

        score = 50
        reasons: List[str] = []
        risks: List[str] = []

        if ma["trend"] == "up":
            score += 12
            reasons.append("MA5 is above MA20, showing short-term trend support.")
        else:
            score -= 10
            risks.append("MA5 is below MA20, so the short-term trend is weak.")

        if macd["bias"] == "bullish":
            score += 10
            reasons.append("MACD histogram is positive.")
        else:
            score -= 8
            risks.append("MACD histogram is negative.")

        if 45 <= rsi <= 68:
            score += 8
            reasons.append("RSI is in a constructive neutral zone.")
        elif rsi > 75:
            score -= 12
            risks.append("RSI is overbought and pullback risk is elevated.")
        elif rsi < 35:
            score -= 6
            risks.append("RSI is weak and momentum has not recovered.")

        if latest >= previous:
            score += 5
            reasons.append("Latest close is above the previous close.")
        else:
            score -= 4

        if float(boll["position"]) > 0.9:
            risks.append("Price is near the upper Bollinger band; chase risk is higher.")
            score -= 5
        elif float(boll["position"]) < 0.2:
            risks.append("Price is near the lower Bollinger band; trend confirmation is needed.")

        if volume_ratio >= 1.2:
            reasons.append("Volume is above its 20-day average.")
            score += 4
        elif volume_ratio < 0.7:
            risks.append("Volume is below its 20-day average, reducing signal quality.")
            score -= 3

        score = int(max(0, min(100, score)))
        if score >= 70:
            rating = "buy"
        elif score >= 45:
            rating = "watch"
        else:
            rating = "sell"

        if not reasons:
            reasons.append("No strong bullish confirmation was detected.")
        if not risks:
            risks.append("No major rule-based risk flag was detected.")

        return {
            "score": score,
            "rating": rating,
            "reasons": reasons[:5],
            "risks": risks[:5],
            "disclaimer": "Rule-based educational analysis only; not investment advice.",
        }

    def _build_price_summary(self, frame: pd.DataFrame) -> Dict[str, Any]:
        close = frame["close"]
        latest = float(close.iloc[-1])
        previous = float(close.iloc[-2]) if len(close) > 1 else latest
        window = frame.tail(min(20, len(frame)))
        return {
            "latest": self._round(latest),
            "previous_close": self._round(previous),
            "change": self._round(latest - previous),
            "change_pct": self._round((latest / previous - 1) if previous else 0.0, digits=4),
            "range_20d": {
                "low": self._round(window["low"].min()),
                "high": self._round(window["high"].max()),
            },
        }

    def _build_chart_payload(self, frame: pd.DataFrame) -> Dict[str, Any]:
        return {
            "dates": [self._format_date(index) for index in frame.index],
            "ohlc": [
                [self._round(row.open), self._round(row.close), self._round(row.low), self._round(row.high)]
                for row in frame.itertuples()
            ],
            "volumes": [self._round(value, digits=0) for value in frame["volume"]],
        }

    def _build_backtest_preview(self, frame: pd.DataFrame, *, strategy: str) -> Dict[str, Any]:
        if len(frame) < 10:
            return {"enabled": False, "reason": "not_enough_data"}

        close = frame["close"]
        strategy_name = (strategy or "macd").lower()
        if strategy_name == "sma":
            signal = (close.rolling(5, min_periods=1).mean() > close.rolling(20, min_periods=1).mean()).astype(float)
        else:
            ema12 = close.ewm(span=12, adjust=False, min_periods=1).mean()
            ema26 = close.ewm(span=26, adjust=False, min_periods=1).mean()
            macd = ema12 - ema26
            macd_signal = macd.ewm(span=9, adjust=False, min_periods=1).mean()
            signal = (macd > macd_signal).astype(float)
            strategy_name = "macd"

        returns = close.pct_change().fillna(0.0)
        strategy_returns = returns * signal.shift(1).fillna(0.0)
        equity = (1 + strategy_returns).cumprod()
        cum_return = float(equity.iloc[-1] - 1)
        vol = float(strategy_returns.std(ddof=0))
        sharpe = float((strategy_returns.mean() / vol) * np.sqrt(252)) if vol > 0 else 0.0
        drawdown = equity / equity.cummax() - 1
        trades = int((signal.diff().abs() > 0).sum())
        return {
            "enabled": True,
            "strategy": strategy_name,
            "cum_return": self._round(cum_return, digits=4),
            "sharpe": self._round(sharpe),
            "mdd": self._round(float(drawdown.min()), digits=4),
            "trades": trades,
            "note": "Lightweight preview on the displayed OHLCV window; use Backtest for full engine results.",
        }

    def _build_ai_summary(
        self,
        *,
        enabled: bool,
        symbol: str,
        signal: Dict[str, Any],
        indicators: Dict[str, Any],
        data_quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not enabled:
            return {"enabled": False, "status": "disabled", "text": ""}
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            return {"enabled": False, "status": "missing_api_key", "text": ""}

        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        prompt = (
            "Summarize this rule-based stock analysis in 3 concise bullet points. "
            "Do not provide personalized financial advice.\n"
            f"Symbol: {symbol}\n"
            f"Signal: {json.dumps(signal, ensure_ascii=False)}\n"
            f"Indicators: {json.dumps(indicators, ensure_ascii=False)}\n"
            f"Data quality: {json.dumps(data_quality, ensure_ascii=False)}"
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You summarize quantitative stock diagnostics for educational use."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                body = json.loads(response.read().decode("utf-8"))
            text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"enabled": True, "status": "ok", "model": model, "text": text}
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            logger.warning("analysis_ai_summary_failed", symbol=symbol, error=str(exc))
            return {"enabled": True, "status": "error", "error": str(exc), "text": ""}

    def _build_markdown_report(
        self,
        *,
        symbol: str,
        price: Dict[str, Any],
        indicators: Dict[str, Any],
        signal: Dict[str, Any],
        data_quality: Dict[str, Any],
        backtest_preview: Dict[str, Any],
        ai_summary: Dict[str, Any],
    ) -> str:
        lines = [
            f"# Stock Analysis: {symbol}",
            "",
            f"- Rating: `{signal['rating']}`",
            f"- Score: `{signal['score']}/100`",
            f"- Latest close: `{price['latest']}` ({price['change_pct'] * 100:.2f}%)",
            f"- Data source: `{data_quality.get('source')}` ({data_quality.get('rows', 0)} rows)",
            "",
            "## Reasons",
            "",
        ]
        lines.extend(f"- {item}" for item in signal["reasons"])
        lines.extend(["", "## Risks", ""])
        lines.extend(f"- {item}" for item in signal["risks"])
        lines.extend(
            [
                "",
                "## Indicators",
                "",
                f"- MA trend: `{indicators['ma']['trend']}` (MA5={indicators['ma']['ma5']}, MA20={indicators['ma']['ma20']})",
                f"- RSI14: `{indicators['rsi']}`",
                f"- MACD bias: `{indicators['macd']['bias']}`",
                f"- Volume ratio: `{indicators['volume']['ratio']}`",
            ]
        )
        if backtest_preview.get("enabled"):
            lines.extend(
                [
                    "",
                    "## Backtest Preview",
                    "",
                    f"- Strategy: `{backtest_preview['strategy']}`",
                    f"- Return: `{backtest_preview['cum_return'] * 100:.2f}%`",
                    f"- Sharpe: `{backtest_preview['sharpe']}`",
                    f"- MDD: `{backtest_preview['mdd'] * 100:.2f}%`",
                ]
            )
        if ai_summary.get("text"):
            lines.extend(["", "## AI Summary", "", ai_summary["text"]])
        lines.extend(["", "> Educational analysis only; not investment advice."])
        return "\n".join(lines) + "\n"

    def capabilities(self) -> Dict[str, Any]:
        sample_symbols = sorted(self._sample_symbols(self.sample_data_path))
        return {
            "sources": list(SUPPORTED_ANALYSIS_SOURCES),
            "default_source": "sample",
            "sample_symbols": sample_symbols,
            "strategies": ["macd", "sma"],
            "ai": {
                "optional": True,
                "enabled": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
                "env": ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"],
            },
        }

    def _sample_symbols(self, path: Path) -> List[str]:
        if not path.is_file():
            return []
        symbols = set()
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("symbol"):
                    symbols.add(str(row["symbol"]).upper())
        return sorted(symbols)

    @staticmethod
    def _round(value: Any, digits: int = 2) -> float:
        numeric = float(value)
        if np.isnan(numeric) or np.isinf(numeric):
            return 0.0
        return round(numeric, digits)

    @staticmethod
    def _format_date(value: Any) -> str:
        if hasattr(value, "date"):
            return value.date().isoformat()
        return str(value)

    def _last_date(self, frame: pd.DataFrame) -> str:
        return self._format_date(frame.index[-1])


__all__ = [
    "AnalysisRequestPayload",
    "StockAnalysisService",
    "SUPPORTED_ANALYSIS_SOURCES",
    "run_stock_analysis_task",
]
