"""
Chinese Stock Market Fee and Sizing Plugins

Implements A-share specific trading rules:
- Commission + Stamp Tax calculation
- Lot-based position sizing (100 shares per lot)
"""
from __future__ import annotations

try:
    import backtrader as bt
except ImportError as exc:
    raise ImportError("backtrader is required: pip install backtrader") from exc

from .base import register_fee, register_sizer, FeePlugin, SizerPlugin


@register_fee("cn_stock")
class CNStockFee(FeePlugin):
    """
    Chinese A-share commission and stamp tax plugin.
    
    Features:
    - Bidirectional commission (buy/sell)
    - Stamp tax (0.05%, sell-only)
    - Optional minimum commission (set to 0 for "免五" mode)
    
    Args:
        commission_rate: Commission rate (default: 0.0001 = 0.01%)
        stamp_tax_rate: Stamp tax rate (default: 0.0005 = 0.05%, sell-only)
        min_commission: Minimum commission per trade (default: 0.0 for "免五")
    
    Example:
        >>> # 免五 mode (no minimum)
        >>> fee = CNStockFee(commission_rate=0.0001, stamp_tax_rate=0.0005, min_commission=0.0)
        >>> # 不免五 mode (5 yuan minimum)
        >>> fee = CNStockFee(commission_rate=0.0001, stamp_tax_rate=0.0005, min_commission=5.0)
    """
    
    def __init__(
        self,
        commission_rate: float = 0.0001,
        stamp_tax_rate: float = 0.0005,
        min_commission: float = 0.0,
    ):
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.min_commission = min_commission

    def register(self, broker: bt.BrokerBase) -> None:
        """Register A-share commission rules with the broker."""
        
        # Capture plugin configuration in closure
        commission_rate = self.commission_rate
        stamp_tax_rate = self.stamp_tax_rate
        min_commission = self.min_commission
        
        class CNStockCommission(bt.CommInfoBase):
            """Chinese A-share commission and stamp tax calculator."""
            
            params = (
                ('commission', commission_rate),
                ('stocklike', True),
                ('commtype', bt.CommInfoBase.COMM_PERC),
                ('percabs', False),
                ('stamp_duty', stamp_tax_rate),
                ('min_commission', min_commission),
                ('mult', 1.0),
                ('margin', None),
            )
            
            def getsize(self, price, cash):
                """
                Calculate maximum shares purchasable (must be multiple of 100).
                
                Conservatively estimates total cost including commission + stamp tax.
                """
                # Conservative estimate: assume 0.06% total cost
                effective_price = price * 1.0006
                max_shares = int(cash / effective_price)
                # Round down to nearest lot (100 shares)
                lots = max_shares // 100
                return lots * 100
            
            def getvaluesize(self, size, price):
                """Return position value (size must be multiple of 100)."""
                return abs(size) * price
            
            def getoperationcost(self, size, price):
                """Return total operation cost (commission + stamp tax)."""
                return self.getcommission(size, price)
            
            def _getcommission(self, size, price, pseudoexec):
                """
                Calculate commission (bidirectional).
                
                免五 mode: charge actual commission rate
                不免五 mode: enforce minimum commission (set min_commission=5.0)
                """
                value = abs(size) * price
                comm = value * self.p.commission
                
                # Enforce minimum commission if configured
                if self.p.min_commission > 0 and comm < self.p.min_commission:
                    comm = self.p.min_commission
                    
                return comm
            
            def getcommission(self, size, price):
                """
                Get total transaction cost (commission + stamp tax).
                
                Commission: charged on both buy and sell
                Stamp tax: charged only on sell (size < 0)
                """
                # Commission (bidirectional)
                comm = self._getcommission(size, price, False)
                
                # Stamp tax (sell-only)
                stamp = 0.0
                if size < 0:  # Sell order
                    stamp = abs(size) * price * self.p.stamp_duty
                
                return comm + stamp
        
        broker.addcommissioninfo(CNStockCommission())


@register_sizer("cn_lot100")
class Lot100Sizer(SizerPlugin):
    """
    Chinese A-share lot-based position sizer.
    
    Enforces trading in multiples of 100 shares (1 lot = 100 shares).
    
    Args:
        lot_size: Number of shares per lot (default: 100)
    
    Example:
        >>> sizer = Lot100Sizer(lot_size=100)
        >>> cerebro.addsizer(sizer.get())
    """
    
    def __init__(self, lot_size: int = 100):
        self.lot_size = lot_size
    
    def get(self) -> bt.Sizer:
        """Return configured lot sizer CLASS (not instance)."""
        
        # Capture lot_size in closure
        lot_size = self.lot_size
        
        class StockLotSizer(bt.Sizer):
            """
            A-share trading rule: minimum 1 lot (100 shares), 
            must be multiple of 100.
            """
            
            params = (
                ('lot_size', lot_size),
            )
            
            def _getsizing(self, comminfo, cash, data, isbuy):
                """
                Calculate order size ensuring multiple of lot_size.
                
                Buy: calculate affordable lots from available cash
                Sell: return full position size (already in lots)
                """
                position = self.broker.getposition(data)
                
                if isbuy:
                    # Buy: calculate affordable lots
                    price = data.close[0]
                    if price <= 0:
                        return 0
                    
                    # Account for commission + stamp tax
                    effective_price = price * 1.0006
                    max_shares = int(cash / effective_price)
                    lots = max_shares // self.p.lot_size
                    return lots * self.p.lot_size
                else:
                    # Sell: return current position (already in lots)
                    # Backtrader's sell() defaults to selling full position
                    return abs(position.size)
        
        return StockLotSizer  # Return CLASS, not instance
