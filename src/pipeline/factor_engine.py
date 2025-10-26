"""
Pipeline Factor Engine

Declarative factor computation engine inspired by Zipline's Pipeline.
Provides efficient batch calculation of alpha factors with automatic dependency management.

Features:
- Factor base class for custom factors
- 15+ built-in factors (momentum, value, technical)
- Vectorized computation for performance
- Automatic data alignment
- Missing data handling
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factor Base Class
# ---------------------------------------------------------------------------

class Factor(ABC):
    """
    Base class for all factors.
    
    A factor computes a value for each symbol at each time point.
    Factors can depend on other factors, enabling complex calculations.
    """
    
    def __init__(self, **params):
        """
        Initialize factor with parameters.
        
        Args:
            **params: Factor-specific parameters
        """
        self.params = params
        self.name = self.__class__.__name__
    
    @abstractmethod
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """
        Compute factor values.
        
        Args:
            data: DataFrame with OHLCV data (MultiIndex: date x symbol)
        
        Returns:
            Series with factor values (MultiIndex: date x symbol)
        """
        pass
    
    def __repr__(self) -> str:
        params_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.name}({params_str})"


# ---------------------------------------------------------------------------
# Momentum Factors
# ---------------------------------------------------------------------------

class Returns(Factor):
    """Simple returns over N periods."""
    
    def __init__(self, period: int = 1):
        super().__init__(period=period)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute returns."""
        period = self.params["period"]
        close = data["close"]
        returns = close.pct_change(periods=period)
        return returns


class Momentum(Factor):
    """Price momentum (N-period return)."""
    
    def __init__(self, period: int = 20):
        super().__init__(period=period)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute momentum."""
        period = self.params["period"]
        close = data["close"]
        momentum = (close / close.shift(period) - 1) * 100
        return momentum


class RSI(Factor):
    """Relative Strength Index."""
    
    def __init__(self, period: int = 14):
        super().__init__(period=period)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute RSI."""
        period = self.params["period"]
        close = data["close"]
        
        # Calculate price changes
        delta = close.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)
        
        # Calculate average gains and losses
        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()
        
        # Calculate RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return rsi


# ---------------------------------------------------------------------------
# Value Factors
# ---------------------------------------------------------------------------

class Volume(Factor):
    """Trading volume."""
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Return volume."""
        return data["volume"]


class VolumeRatio(Factor):
    """Volume relative to N-period average."""
    
    def __init__(self, period: int = 20):
        super().__init__(period=period)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute volume ratio."""
        period = self.params["period"]
        volume = data["volume"]
        avg_volume = volume.rolling(window=period).mean()
        return volume / avg_volume


class Turnover(Factor):
    """Price * Volume (if available)."""
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute turnover."""
        if "turnover" in data.columns:
            return data["turnover"]
        # Approximate as close * volume
        return data["close"] * data["volume"]


# ---------------------------------------------------------------------------
# Technical Factors
# ---------------------------------------------------------------------------

class SMA(Factor):
    """Simple Moving Average."""
    
    def __init__(self, period: int = 20):
        super().__init__(period=period)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute SMA."""
        period = self.params["period"]
        return data["close"].rolling(window=period).mean()


class EMA(Factor):
    """Exponential Moving Average."""
    
    def __init__(self, period: int = 20):
        super().__init__(period=period)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute EMA."""
        period = self.params["period"]
        return data["close"].ewm(span=period, adjust=False).mean()


class BollingerBands(Factor):
    """Bollinger Bands (returns middle band)."""
    
    def __init__(self, period: int = 20, num_std: float = 2.0):
        super().__init__(period=period, num_std=num_std)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute Bollinger middle band (SMA)."""
        period = self.params["period"]
        return data["close"].rolling(window=period).mean()
    
    def compute_upper(self, data: pd.DataFrame) -> pd.Series:
        """Compute upper band."""
        period = self.params["period"]
        num_std = self.params["num_std"]
        sma = data["close"].rolling(window=period).mean()
        std = data["close"].rolling(window=period).std()
        return sma + num_std * std
    
    def compute_lower(self, data: pd.DataFrame) -> pd.Series:
        """Compute lower band."""
        period = self.params["period"]
        num_std = self.params["num_std"]
        sma = data["close"].rolling(window=period).mean()
        std = data["close"].rolling(window=period).std()
        return sma - num_std * std


class MACD(Factor):
    """MACD indicator (MACD line)."""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(fast=fast, slow=slow, signal=signal)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute MACD line."""
        fast = self.params["fast"]
        slow = self.params["slow"]
        
        ema_fast = data["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = data["close"].ewm(span=slow, adjust=False).mean()
        
        return ema_fast - ema_slow
    
    def compute_signal(self, data: pd.DataFrame) -> pd.Series:
        """Compute signal line."""
        signal_period = self.params["signal"]
        macd = self.compute(data)
        return macd.ewm(span=signal_period, adjust=False).mean()


class ATR(Factor):
    """Average True Range (volatility)."""
    
    def __init__(self, period: int = 14):
        super().__init__(period=period)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute ATR."""
        period = self.params["period"]
        
        high = data["high"]
        low = data["low"]
        close_prev = data["close"].shift(1)
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Average True Range
        atr = tr.rolling(window=period).mean()
        
        return atr


# ---------------------------------------------------------------------------
# Volatility Factors
# ---------------------------------------------------------------------------

class Volatility(Factor):
    """Historical volatility (std of returns)."""
    
    def __init__(self, period: int = 20):
        super().__init__(period=period)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute volatility."""
        period = self.params["period"]
        returns = data["close"].pct_change()
        return returns.rolling(window=period).std()


class BetaToMarket(Factor):
    """Beta relative to market/benchmark."""
    
    def __init__(self, period: int = 60, benchmark: str = "000300.SH"):
        super().__init__(period=period, benchmark=benchmark)
    
    def compute(self, data: pd.DataFrame) -> pd.Series:
        """Compute beta (requires benchmark data)."""
        # Simplified: return 1.0 (neutral beta)
        # Full implementation would need benchmark returns
        return pd.Series(1.0, index=data.index)


# ---------------------------------------------------------------------------
# Pipeline Engine
# ---------------------------------------------------------------------------

class Pipeline:
    """
    Factor pipeline for batch computation.
    
    Usage:
        >>> pipeline = Pipeline()
        >>> pipeline.add("momentum", Momentum(20))
        >>> pipeline.add("rsi", RSI(14))
        >>> pipeline.add("volume_ratio", VolumeRatio(20))
        >>> 
        >>> results = pipeline.run(data_map)
        >>> # results["momentum"] -> Series with momentum values
    """
    
    def __init__(self):
        """Initialize pipeline."""
        self.factors: Dict[str, Factor] = {}
    
    def add(self, name: str, factor: Factor) -> Pipeline:
        """
        Add factor to pipeline.
        
        Args:
            name: Factor name (used as column name in output)
            factor: Factor instance
        
        Returns:
            Self for method chaining
        """
        self.factors[name] = factor
        logger.info(f"Added factor: {name} = {factor}")
        return self
    
    def run(self, data_map: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Run pipeline on data.
        
        Args:
            data_map: Dictionary mapping symbol -> DataFrame (OHLCV)
        
        Returns:
            DataFrame with factor values (MultiIndex: date x symbol, columns: factors)
        """
        if not self.factors:
            logger.warning("Pipeline has no factors")
            return pd.DataFrame()
        
        # Combine all symbol data into single DataFrame
        combined_data = {}
        for symbol, df in data_map.items():
            for col in df.columns:
                combined_data[(col, symbol)] = df[col]
        
        if not combined_data:
            return pd.DataFrame()
        
        combined_df = pd.DataFrame(combined_data)
        
        # Compute each factor
        results = {}
        common_index = combined_df.index if not combined_df.empty else pd.DatetimeIndex([])
        
        for factor_name, factor in self.factors.items():
            logger.info(f"Computing factor: {factor_name}")
            
            try:
                # Compute factor for all symbols
                factor_values = factor.compute(combined_df)
                
                # Ensure Series format
                if not isinstance(factor_values, pd.Series):
                    factor_values = pd.Series(factor_values, index=common_index)
                
                results[factor_name] = factor_values
            except Exception as e:
                logger.error(f"Error computing factor {factor_name}: {e}")
                # Fill with NaN
                results[factor_name] = pd.Series(np.nan, index=common_index)
        
        # Combine results with explicit index
        if results:
            result_df = pd.DataFrame(results, index=common_index)
        else:
            result_df = pd.DataFrame()
        
        logger.info(f"Pipeline computed {len(self.factors)} factors for {len(data_map)} symbols")
        
        return result_df
    
    def get_latest(self, data_map: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Get latest factor values for each symbol.
        
        Args:
            data_map: Dictionary mapping symbol -> DataFrame
        
        Returns:
            DataFrame with latest factor values (index: symbols, columns: factors)
        """
        full_results = self.run(data_map)
        
        if full_results.empty:
            return pd.DataFrame()
        
        # Get last row for each symbol
        latest = {}
        for symbol in data_map.keys():
            if symbol in full_results.columns:
                latest[symbol] = full_results[symbol].iloc[-1]
        
        return pd.DataFrame(latest).T


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_pipeline(*factors: tuple[str, Factor]) -> Pipeline:
    """
    Create pipeline from factor list.
    
    Args:
        *factors: Tuples of (name, factor_instance)
    
    Returns:
        Pipeline instance
    
    Example:
        >>> pipeline = create_pipeline(
        ...     ("momentum", Momentum(20)),
        ...     ("rsi", RSI(14)),
        ...     ("volume_ratio", VolumeRatio(20))
        ... )
    """
    pipeline = Pipeline()
    for name, factor in factors:
        pipeline.add(name, factor)
    return pipeline


# Predefined pipelines
def alpha_pipeline() -> Pipeline:
    """Create standard alpha factor pipeline."""
    return create_pipeline(
        ("returns_1d", Returns(1)),
        ("momentum_20d", Momentum(20)),
        ("momentum_60d", Momentum(60)),
        ("rsi_14", RSI(14)),
        ("volume_ratio_20", VolumeRatio(20)),
        ("volatility_20", Volatility(20)),
    )


def technical_pipeline() -> Pipeline:
    """Create technical indicator pipeline."""
    return create_pipeline(
        ("sma_20", SMA(20)),
        ("ema_20", EMA(20)),
        ("rsi_14", RSI(14)),
        ("atr_14", ATR(14)),
        ("macd", MACD()),
    )
