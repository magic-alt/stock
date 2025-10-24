"""
Gateway Protocol Module

Defines unified interfaces for data and trading operations,
inspired by vn.py's Gateway architecture.

This allows seamless switching between:
- Backtest (historical data + simulated broker)
- Paper trading (real-time data + simulated broker)  
- Live trading (real-time data + real broker)

Reference: https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py
"""
from __future__ import annotations

from typing import Protocol, Iterable, Dict, Any, Optional
import pandas as pd


class HistoryGateway(Protocol):
    """
    Protocol for historical data providers.
    
    Implementations:
    - BacktestGateway: Uses existing data_sources providers
    - PaperGateway: Fetches real-time historical snapshots
    """
    
    def load_bars(
        self, 
        symbols: Iterable[str], 
        start: str, 
        end: str, 
        adj: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV bar data for multiple symbols.
        
        Args:
            symbols: List of symbols (e.g., ["600519.SH", "000333.SZ"])
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format
            adj: Adjustment type ("hfq", "qfq", "noadj", None)
            
        Returns:
            Dictionary mapping symbol to DataFrame with columns:
            [date, open, high, low, close, volume]
        """
        ...
    
    def load_index_nav(
        self, 
        index_code: str, 
        start: str, 
        end: str
    ) -> pd.Series:
        """
        Load index NAV (Net Asset Value) series for benchmark comparison.
        
        Args:
            index_code: Index symbol (e.g., "000300.SH", "000300.SS")
            start: Start date
            end: End date
            
        Returns:
            Series with DatetimeIndex and NAV values
        """
        ...


class TradeGateway(Protocol):
    """
    Protocol for order execution and account queries.
    
    Implementations:
    - BacktestGateway: Uses Backtrader broker
    - PaperGateway: Simulated matching engine
    - LiveGateway: Real broker API (IB/CTP/Binance)
    """
    
    def send_order(
        self, 
        symbol: str, 
        side: str, 
        size: int, 
        price: Optional[float] = None,
        order_type: str = "limit"
    ) -> Any:
        """
        Send a new order.
        
        Args:
            symbol: Symbol to trade
            side: "buy" or "sell"
            size: Order size (shares for stocks, contracts for futures)
            price: Limit price (None for market orders)
            order_type: "limit", "market", "stop", etc.
            
        Returns:
            Order ID or order object
        """
        ...
    
    def cancel_order(self, order_id: Any) -> None:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order identifier returned by send_order()
        """
        ...
    
    def query_account(self) -> Dict[str, Any]:
        """
        Query account information.
        
        Returns:
            Dictionary with keys: balance, available, frozen, etc.
        """
        ...
    
    def query_position(self, symbol: str) -> Dict[str, Any]:
        """
        Query position for a specific symbol.
        
        Args:
            symbol: Symbol to query
            
        Returns:
            Dictionary with keys: symbol, size, avg_price, unrealized_pnl, etc.
        """
        ...


class BacktestGateway:
    """
    Backtest gateway that wraps existing data_sources providers.
    
    This is the default gateway for historical backtesting, maintaining
    backward compatibility with the current system.
    """
    
    def __init__(self, source: str = "akshare", cache_dir: str = "./cache") -> None:
        """
        Initialize backtest gateway.
        
        Args:
            source: Data provider name ("akshare", "yfinance", "tushare")
            cache_dir: Directory for caching downloaded data
        """
        from src.data_sources.providers import get_provider
        self._prov = get_provider(source)
        self._cache = cache_dir
        self._source = source

    def load_bars(
        self, 
        symbols: Iterable[str], 
        start: str, 
        end: str, 
        adj: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load historical bar data using configured provider.
        
        This method wraps the existing provider.load_stock_daily() to maintain
        compatibility with the current data loading system.
        """
        return self._prov.load_stock_daily(
            symbols, 
            start, 
            end, 
            adj=adj, 
            cache_dir=self._cache
        )

    def load_index_nav(
        self, 
        index_code: str, 
        start: str, 
        end: str
    ) -> pd.Series:
        """
        Load benchmark index NAV series.
        
        Uses the provider's load_index_nav() method if available,
        falls back to load_stock_daily() for compatibility.
        """
        try:
            # Try dedicated index loading method
            if hasattr(self._prov, 'load_index_nav'):
                return self._prov.load_index_nav(
                    index_code, 
                    start, 
                    end, 
                    cache_dir=self._cache
                )
            else:
                # Fallback: load as regular symbol and extract close price
                data = self._prov.load_stock_daily(
                    [index_code], 
                    start, 
                    end, 
                    cache_dir=self._cache
                )
                if index_code in data and not data[index_code].empty:
                    df = data[index_code]
                    nav = (1 + df['close'].pct_change().fillna(0)).cumprod()
                    nav.name = index_code
                    return nav
                else:
                    raise ValueError(f"Failed to load index {index_code}")
        except Exception as e:
            # Return flat NAV as fallback
            import warnings
            warnings.warn(f"Failed to load index {index_code}: {e}. Using flat NAV.")
            date_range = pd.bdate_range(start=start, end=end)
            if date_range.empty:
                date_range = pd.Index([pd.to_datetime(start)])
            return pd.Series(1.0, index=date_range, name=index_code)


# Future implementations (placeholder for documentation)

class PaperGateway:
    """
    Paper trading gateway (to be implemented).
    
    Features:
    - Real-time or delayed market data
    - Simulated order matching
    - Realistic slippage and fill models
    - No real money at risk
    
    Usage:
        >>> gateway = PaperGateway(source="yfinance")
        >>> gateway.subscribe(["AAPL", "TSLA"])
        >>> gateway.send_order("AAPL", "buy", 100, 150.0)
    """
    pass


class LiveGateway:
    """
    Live trading gateway (to be implemented).
    
    Implementations per broker:
    - IBGateway: Interactive Brokers
    - CTPGateway: CTP futures (China)
    - BinanceGateway: Binance crypto
    
    Features:
    - Real-time order execution
    - Position and account synchronization
    - Risk management hooks
    - Error handling and reconnection
    """
    pass
