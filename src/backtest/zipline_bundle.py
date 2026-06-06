"""Custom Zipline data bundle that ingests data from the project's existing providers.

This module lets users feed historical OHLCV data they already fetch through
:func:`src.data_sources.providers.get_provider` (akshare / tushare / yfinance /
qlib) into ``~/.zipline/`` so that the
:class:`src.backtest.backends.zipline_backend.ZiplineBackend` can run real
``zipline-reloaded`` algorithms when the optional dependency is installed.

Usage
-----

Programmatic registration (in your Python entrypoint or notebook)::

    from src.backtest.zipline_bundle import register_project_bundle

    register_project_bundle(
        bundle_name="project-cn",
        source="akshare",
        symbols=["600519.SH", "000001.SZ"],
        start="2020-01-01",
        end="2024-12-31",
    )

Then run::

    zipline ingest -b project-cn
    zipline run -f my_algo.py --bundle project-cn ...

If ``zipline-reloaded`` is not installed, ``register_project_bundle`` is a
no-op and emits a structured warning so unit tests can run without the
optional dependency. The :class:`ZiplineBackend` itself does **not** require
this bundle — it uses an in-memory vectorised simulation by default.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional, Sequence

import pandas as pd

logger = logging.getLogger(__name__)


def _zipline_bundles_available() -> bool:
    try:
        from zipline.data.bundles import register  # noqa: F401
        return True
    except Exception:
        return False


def _to_zipline_symbol(sym: str) -> str:
    """Strip Chinese exchange suffix so zipline sees a plain ticker."""
    if "." in sym:
        return sym.split(".")[0]
    return sym


def _load_ohlcv(
    source: str,
    symbols: Sequence[str],
    start: str,
    end: str,
    adj: Optional[str] = None,
) -> dict:
    """Load OHLCV frames using the framework's provider abstraction."""
    from src.data_sources.providers import get_provider

    provider = get_provider(source)
    out = {}
    for sym in symbols:
        try:
            df = provider.fetch(sym, start=start, end=end, adj=adj)
            if df is not None and not df.empty:
                out[sym] = df
        except Exception as exc:  # noqa: BLE001
            logger.warning("zipline_bundle_fetch_failed", extra={"symbol": sym, "error": str(exc)})
    return out


def _make_ingest_func(
    source: str,
    symbols: Sequence[str],
    start: str,
    end: str,
    adj: Optional[str] = None,
):
    """Build a Zipline ingest callable that writes OHLCV from our providers."""

    def _ingest(
        environ,
        asset_db_writer,
        minute_bar_writer,
        daily_bar_writer,
        adjustment_writer,
        calendar,
        start_session,
        end_session,
        cache,
        show_progress,
        output_dir,
    ):
        data_map = _load_ohlcv(source, symbols, start, end, adj=adj)
        if not data_map:
            logger.warning("zipline_bundle_empty")
            return

        zipline_symbols = [_to_zipline_symbol(s) for s in sorted(data_map.keys())]
        metadata = pd.DataFrame(
            {
                "symbol": zipline_symbols,
                "asset_name": zipline_symbols,
                "exchange": "PROJECT",
                "start_date": [pd.Timestamp(start) for _ in zipline_symbols],
                "end_date": [pd.Timestamp(end) for _ in zipline_symbols],
                "first_traded": [pd.Timestamp(start) for _ in zipline_symbols],
                "auto_close_date": [pd.Timestamp(end) for _ in zipline_symbols],
            }
        )

        sid_map = {sym: sid for sid, sym in enumerate(zipline_symbols)}

        def _bar_iter() -> Iterable:
            for original_sym, df in sorted(data_map.items()):
                zsym = _to_zipline_symbol(original_sym)
                # Ensure expected columns for zipline daily writer.
                frame = df.rename(columns=str.lower).copy()
                expected = ["open", "high", "low", "close", "volume"]
                for col in expected:
                    if col not in frame.columns:
                        frame[col] = 0.0
                frame = frame[expected]
                frame.index = pd.DatetimeIndex(frame.index).tz_localize(None)
                yield sid_map[zsym], frame

        daily_bar_writer.write(_bar_iter(), show_progress=show_progress)

        # zipline expects an "exchange" frame.
        exchanges = pd.DataFrame({"exchange": ["PROJECT"], "country_code": ["CN"]})
        asset_db_writer.write(equities=metadata, exchanges=exchanges)

        # Empty adjustment data — provider already supplies adjusted prices
        # when ``adj`` is set, so we do not emit splits/dividends here.
        adjustment_writer.write()

        logger.info(
            "zipline_bundle_ingested",
            extra={
                "symbols": zipline_symbols,
                "start": start,
                "end": end,
                "source": source,
            },
        )

    return _ingest


def register_project_bundle(
    *,
    bundle_name: str = "project-cn",
    source: str = "akshare",
    symbols: Sequence[str],
    start: str,
    end: str,
    adj: Optional[str] = None,
    calendar_name: str = "XSHG",
) -> bool:
    """Register a custom Zipline bundle backed by the project's providers.

    Returns ``True`` when the bundle is registered, ``False`` when
    ``zipline-reloaded`` is unavailable (in which case the call is a no-op).
    """
    if not _zipline_bundles_available():
        logger.warning(
            "zipline_bundle_register_skipped: zipline-reloaded is not installed; "
            "ZiplineBackend will use its vectorised fallback."
        )
        return False

    from zipline.data.bundles import register

    register(
        bundle_name,
        _make_ingest_func(source, list(symbols), start, end, adj=adj),
        calendar_name=calendar_name,
        start_session=pd.Timestamp(start),
        end_session=pd.Timestamp(end),
    )
    logger.info(
        "zipline_bundle_registered: %s (%s symbols, %s..%s)",
        bundle_name,
        len(symbols),
        start,
        end,
    )
    return True


__all__ = ["register_project_bundle"]
