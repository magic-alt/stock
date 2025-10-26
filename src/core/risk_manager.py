"""
Risk Manager - Pre-Trade Risk Control

Implements order-level risk checks before submission to prevent:
- Insufficient funds
- Position limit violations
- Price deviation from market
- Maximum order size violations
- Daily loss limits

Designed as middleware that can be integrated into Gateway or Strategy.
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from src.core.objects import OrderData, AccountData, PositionData, Direction, OrderStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk Check Result
# ---------------------------------------------------------------------------

@dataclass
class RiskCheckResult:
    """Result of risk check."""
    passed: bool
    reason: str = ""
    severity: str = "info"  # "info", "warning", "error"
    
    def __bool__(self) -> bool:
        return self.passed


# ---------------------------------------------------------------------------
# Risk Rules
# ---------------------------------------------------------------------------

class RiskRule:
    """Base class for risk rules."""
    
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
    
    def check(
        self,
        order: OrderData,
        account: AccountData,
        positions: Dict[str, PositionData],
        current_price: float,
    ) -> RiskCheckResult:
        """
        Check if order passes risk rule.
        
        Args:
            order: Order to check
            account: Account information
            positions: Current positions
            current_price: Current market price
        
        Returns:
            RiskCheckResult
        """
        if not self.enabled:
            return RiskCheckResult(True, "Rule disabled")
        
        return self._do_check(order, account, positions, current_price)
    
    def _do_check(
        self,
        order: OrderData,
        account: AccountData,
        positions: Dict[str, PositionData],
        current_price: float,
    ) -> RiskCheckResult:
        """Implement actual check logic."""
        raise NotImplementedError


class CashCheckRule(RiskRule):
    """Check if sufficient cash for order."""
    
    def __init__(self, margin_ratio: float = 1.0):
        super().__init__("CashCheck")
        self.margin_ratio = margin_ratio
    
    def _do_check(self, order, account, positions, current_price) -> RiskCheckResult:
        if order.direction == Direction.SHORT:
            # Selling doesn't require cash
            return RiskCheckResult(True)
        
        # Calculate required cash
        required = order.volume * (order.price if order.price > 0 else current_price) * self.margin_ratio
        
        if account.available < required:
            return RiskCheckResult(
                False,
                f"Insufficient cash: need {required:.2f}, available {account.available:.2f}",
                "error"
            )
        
        return RiskCheckResult(True)


class PositionLimitRule(RiskRule):
    """Check position limits."""
    
    def __init__(self, max_position_pct: float = 0.3):
        """
        Args:
            max_position_pct: Maximum position as % of portfolio (0.3 = 30%)
        """
        super().__init__("PositionLimit")
        self.max_position_pct = max_position_pct
    
    def _do_check(self, order, account, positions, current_price) -> RiskCheckResult:
        # Calculate new position value after order
        current_pos = positions.get(order.symbol, PositionData(symbol=order.symbol))
        
        if order.direction == Direction.LONG:
            new_volume = current_pos.volume + order.volume
        else:
            new_volume = max(0, current_pos.volume - order.volume)
        
        new_value = new_volume * current_price
        max_allowed = account.total_value * self.max_position_pct
        
        if new_value > max_allowed:
            return RiskCheckResult(
                False,
                f"Position limit exceeded: {new_value:.2f} > {max_allowed:.2f} ({self.max_position_pct*100}%)",
                "error"
            )
        
        return RiskCheckResult(True)


class PriceDeviationRule(RiskRule):
    """Check if order price deviates too much from market."""
    
    def __init__(self, max_deviation_pct: float = 0.05):
        """
        Args:
            max_deviation_pct: Maximum price deviation (0.05 = 5%)
        """
        super().__init__("PriceDeviation")
        self.max_deviation_pct = max_deviation_pct
    
    def _do_check(self, order, account, positions, current_price) -> RiskCheckResult:
        if order.price <= 0:
            # Market order, no price to check
            return RiskCheckResult(True)
        
        if current_price <= 0:
            return RiskCheckResult(False, "Invalid current price", "warning")
        
        deviation = abs(order.price - current_price) / current_price
        
        if deviation > self.max_deviation_pct:
            return RiskCheckResult(
                False,
                f"Price deviation too large: {deviation*100:.1f}% > {self.max_deviation_pct*100:.1f}%",
                "warning"
            )
        
        return RiskCheckResult(True)


class OrderSizeRule(RiskRule):
    """Check maximum order size."""
    
    def __init__(self, max_order_size: float = 10000):
        super().__init__("OrderSize")
        self.max_order_size = max_order_size
    
    def _do_check(self, order, account, positions, current_price) -> RiskCheckResult:
        if order.volume > self.max_order_size:
            return RiskCheckResult(
                False,
                f"Order size too large: {order.volume} > {self.max_order_size}",
                "error"
            )
        
        return RiskCheckResult(True)


class DailyLossLimitRule(RiskRule):
    """Check daily loss limit."""
    
    def __init__(self, max_daily_loss_pct: float = 0.03):
        """
        Args:
            max_daily_loss_pct: Maximum daily loss (0.03 = 3%)
        """
        super().__init__("DailyLossLimit")
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_pnl: float = 0.0
        self.reset_date: Optional[datetime] = None
    
    def update_pnl(self, pnl: float, current_date: datetime):
        """Update daily P&L."""
        if self.reset_date is None or current_date.date() != self.reset_date.date():
            # New day, reset
            self.daily_pnl = 0.0
            self.reset_date = current_date
        
        self.daily_pnl += pnl
    
    def _do_check(self, order, account, positions, current_price) -> RiskCheckResult:
        if self.daily_pnl >= 0:
            # Not in loss
            return RiskCheckResult(True)
        
        loss_pct = abs(self.daily_pnl) / account.balance
        max_loss = account.balance * self.max_daily_loss_pct
        
        if abs(self.daily_pnl) > max_loss:
            return RiskCheckResult(
                False,
                f"Daily loss limit reached: {self.daily_pnl:.2f} ({loss_pct*100:.1f}%) > {self.max_daily_loss_pct*100:.1f}%",
                "error"
            )
        
        return RiskCheckResult(True)


# ---------------------------------------------------------------------------
# Risk Manager
# ---------------------------------------------------------------------------

class RiskManager:
    """
    Risk manager with configurable rules.
    
    Usage:
        >>> manager = RiskManager()
        >>> manager.add_rule(CashCheckRule())
        >>> manager.add_rule(PositionLimitRule(max_position_pct=0.2))
        >>> manager.add_rule(PriceDeviationRule(max_deviation_pct=0.03))
        >>> 
        >>> # Check order
        >>> result = manager.check_order(order, account, positions, current_price)
        >>> if not result.passed:
        ...     print(f"Order rejected: {result.reason}")
    """
    
    def __init__(self):
        """Initialize risk manager."""
        self.rules: List[RiskRule] = []
        self.strict_mode: bool = True  # Reject on any failure
        self.log_all_checks: bool = False
    
    def add_rule(self, rule: RiskRule) -> RiskManager:
        """Add risk rule."""
        self.rules.append(rule)
        logger.info(f"Added risk rule: {rule.name}")
        return self
    
    def check_order(
        self,
        order: OrderData,
        account: AccountData,
        positions: Dict[str, PositionData],
        current_price: float,
    ) -> RiskCheckResult:
        """
        Check if order passes all risk rules.
        
        Args:
            order: Order to check
            account: Account information
            positions: Current positions
            current_price: Current market price
        
        Returns:
            RiskCheckResult (passed if all rules pass)
        """
        if not self.rules:
            logger.warning("No risk rules configured")
            return RiskCheckResult(True, "No rules configured")
        
        failed_checks = []
        
        for rule in self.rules:
            result = rule.check(order, account, positions, current_price)
            
            if self.log_all_checks or not result.passed:
                logger.info(f"Risk check {rule.name}: {'PASS' if result.passed else 'FAIL'} - {result.reason}")
            
            if not result.passed:
                failed_checks.append(f"{rule.name}: {result.reason}")
                
                if self.strict_mode:
                    # Fail immediately
                    return RiskCheckResult(False, result.reason, result.severity)
        
        if failed_checks:
            return RiskCheckResult(False, "; ".join(failed_checks), "error")
        
        return RiskCheckResult(True, "All checks passed")


# ---------------------------------------------------------------------------
# Predefined Configurations
# ---------------------------------------------------------------------------

def create_conservative_risk_manager() -> RiskManager:
    """Create risk manager with conservative rules."""
    manager = RiskManager()
    manager.add_rule(CashCheckRule(margin_ratio=1.0))
    manager.add_rule(PositionLimitRule(max_position_pct=0.2))  # 20% max position
    manager.add_rule(PriceDeviationRule(max_deviation_pct=0.02))  # 2% max deviation
    manager.add_rule(OrderSizeRule(max_order_size=5000))
    manager.add_rule(DailyLossLimitRule(max_daily_loss_pct=0.02))  # 2% max daily loss
    return manager


def create_moderate_risk_manager() -> RiskManager:
    """Create risk manager with moderate rules."""
    manager = RiskManager()
    manager.add_rule(CashCheckRule(margin_ratio=1.0))
    manager.add_rule(PositionLimitRule(max_position_pct=0.3))  # 30% max position
    manager.add_rule(PriceDeviationRule(max_deviation_pct=0.05))  # 5% max deviation
    manager.add_rule(OrderSizeRule(max_order_size=10000))
    manager.add_rule(DailyLossLimitRule(max_daily_loss_pct=0.05))  # 5% max daily loss
    return manager


def create_aggressive_risk_manager() -> RiskManager:
    """Create risk manager with aggressive rules."""
    manager = RiskManager()
    manager.add_rule(CashCheckRule(margin_ratio=1.0))
    manager.add_rule(PositionLimitRule(max_position_pct=0.5))  # 50% max position
    manager.add_rule(PriceDeviationRule(max_deviation_pct=0.10))  # 10% max deviation
    # No order size or daily loss limits
    return manager
