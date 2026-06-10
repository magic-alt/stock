"""History gateway backed by the platform's verified market-data loader."""
from __future__ import annotations

from typing import Dict, Iterable, Optional

import pandas as pd

from src.data_sources.providers import CACHE_DEFAULT, get_provider, normalize_a_share_symbol
from src.platform.analysis_service import StockAnalysisService


class VerifiedHistoryGateway:
    """Load historical bars through the same verified auto-source path as analysis."""

    def __init__(
        self,
        *,
        source: str = "auto",
        benchmark_source: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> None:
        self.source = (source or "auto").strip().lower()
        self.benchmark_source = (benchmark_source or self.source or "auto").strip().lower()
        self.cache_dir = cache_dir
        self.data_quality: Dict[str, Dict[str, object]] = {}
        self._service = StockAnalysisService()

    def load_bars(
        self,
        symbols: Iterable[str],
        start: str,
        end: str,
        adj: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        data: Dict[str, pd.DataFrame] = {}
        for raw_symbol in symbols:
            symbol = normalize_a_share_symbol(str(raw_symbol))
            frame, quality = self._service.load_history_range(
                symbol=symbol,
                start=start,
                end=end,
                source=self.source,
            )
            self.data_quality[symbol] = quality
            if frame is not None and not frame.empty:
                data[symbol] = frame
                if symbol != raw_symbol:
                    data[str(raw_symbol)] = frame
        return data

    def load_index_nav(self, index_code: str, start: str, end: str) -> pd.Series:
        provider_source = "sina" if self.benchmark_source == "auto" else self.benchmark_source
        try:
            provider = get_provider(provider_source, cache_dir=self.cache_dir)
            return provider.load_index_nav(index_code, start, end, cache_dir=self.cache_dir)
        except Exception:
            return pd.Series(dtype=float, name=index_code)


__all__ = ["VerifiedHistoryGateway"]
