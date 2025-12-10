"""
Enhanced Risk Management System - 增强风险管理系统

提供多层次风险控制:
- 账户级风控 (总权益保护)
- 策略级风控 (策略隔离)
- 订单级风控 (单笔检查)
- 实时监控 (动态调整)
- 自动止损止盈 (持仓保护)

V3.1.0: Initial release

Usage:
    >>> from src.core.risk_manager_v2 import RiskManagerV2, RiskConfig
    >>> 
    >>> config = RiskConfig(
    ...     max_position_pct=0.3,
    ...     max_single_loss_pct=0.02,
    ...     daily_loss_limit_pct=0.05,
    ...     trailing_stop_pct=0.05
    ... )
    >>> 
    >>> rm = RiskManagerV2(config)
    >>> rm.check_order(order, account, positions, price)
    >>> rm.update_position_stops(symbol, current_price)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from src.core.interfaces import (
    Side, OrderTypeEnum, OrderStatusEnum,
    OrderInfo, PositionInfo, AccountInfo
)
from src.core.logger import get_logger

logger = get_logger("risk_manager")


# ---------------------------------------------------------------------------
# Risk Events
# ---------------------------------------------------------------------------

class RiskEventType(str, Enum):
    """Risk event types."""
    ORDER_REJECTED = "risk.order_rejected"
    POSITION_LIMIT_WARNING = "risk.position_limit_warning"
    DAILY_LOSS_WARNING = "risk.daily_loss_warning"
    DRAWDOWN_WARNING = "risk.drawdown_warning"
    STOP_TRIGGERED = "risk.stop_triggered"
    MARGIN_CALL = "risk.margin_call"
    FORCE_LIQUIDATION = "risk.force_liquidation"


class RiskLevel(str, Enum):
    """Risk severity level."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


# ---------------------------------------------------------------------------
# Risk Configuration
# ---------------------------------------------------------------------------

@dataclass
class RiskConfig:
    """
    Risk management configuration.
    
    账户级参数:
    - max_leverage: 最大杠杆倍数
    - max_drawdown_pct: 最大回撤百分比
    - daily_loss_limit_pct: 单日最大亏损
    - margin_call_level: 保证金警戒线
    - force_liquidation_level: 强制平仓线
    
    仓位级参数:
    - max_position_pct: 单一标的最大仓位比例
    - max_positions: 最大持仓数量
    - max_sector_exposure: 行业最大敞口
    
    订单级参数:
    - max_order_value: 单笔最大金额
    - max_order_pct: 单笔最大占比
    - price_deviation_limit: 价格偏离限制
    
    止损止盈:
    - default_stop_loss_pct: 默认止损百分比
    - default_take_profit_pct: 默认止盈百分比
    - trailing_stop_pct: 移动止损百分比
    - enable_auto_stop: 是否启用自动止损
    """
    # Account level
    max_leverage: float = 1.0
    max_drawdown_pct: float = 0.20
    daily_loss_limit_pct: float = 0.05
    margin_call_level: float = 0.50
    force_liquidation_level: float = 0.30
    
    # Position level
    max_position_pct: float = 0.30
    max_positions: int = 10
    max_sector_exposure: float = 0.50
    min_position_value: float = 1000.0
    
    # Order level
    max_order_value: float = 100_000.0
    max_order_pct: float = 0.10
    price_deviation_limit: float = 0.05
    min_order_interval_sec: int = 1
    
    # Stop loss / Take profit
    default_stop_loss_pct: float = 0.05
    default_take_profit_pct: float = 0.15
    trailing_stop_pct: float = 0.05
    enable_auto_stop: bool = True
    
    # Misc
    enabled: bool = True
    strict_mode: bool = True  # Reject on first failure


# ---------------------------------------------------------------------------
# Risk Check Result
# ---------------------------------------------------------------------------

@dataclass
class RiskCheckResult:
    """Risk check result."""
    passed: bool
    reason: str = ""
    level: RiskLevel = RiskLevel.INFO
    rule_name: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __bool__(self) -> bool:
        return self.passed
    
    @classmethod
    def success(cls, rule_name: str = "") -> "RiskCheckResult":
        return cls(True, "OK", RiskLevel.INFO, rule_name)
    
    @classmethod
    def failure(cls, reason: str, level: RiskLevel = RiskLevel.WARNING, 
                rule_name: str = "", **details) -> "RiskCheckResult":
        return cls(False, reason, level, rule_name, details)


# ---------------------------------------------------------------------------
# Position Stop Management
# ---------------------------------------------------------------------------

@dataclass
class PositionStop:
    """Position stop loss / take profit tracking."""
    symbol: str
    entry_price: float
    entry_time: datetime
    quantity: float
    side: Side
    
    # Stop levels
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    
    # Trailing stop tracking
    highest_price: float = 0.0  # For long positions
    lowest_price: float = float('inf')  # For short positions
    
    # Status
    stop_triggered: bool = False
    trigger_reason: str = ""
    trigger_time: Optional[datetime] = None
    
    def update_price(self, current_price: float, trailing_pct: float = 0.0) -> bool:
        """
        Update price and check stop triggers.
        
        Args:
            current_price: Current market price
            trailing_pct: Trailing stop percentage
            
        Returns:
            True if stop was triggered
        """
        if self.stop_triggered:
            return False
        
        # Update high/low
        if self.side == Side.BUY:
            self.highest_price = max(self.highest_price, current_price)
            
            # Update trailing stop
            if trailing_pct > 0:
                new_trail = self.highest_price * (1 - trailing_pct)
                if self.trailing_stop is None or new_trail > self.trailing_stop:
                    self.trailing_stop = new_trail
            
            # Check stops
            if self.stop_loss and current_price <= self.stop_loss:
                self.stop_triggered = True
                self.trigger_reason = "stop_loss"
                self.trigger_time = datetime.now()
                return True
            
            if self.trailing_stop and current_price <= self.trailing_stop:
                self.stop_triggered = True
                self.trigger_reason = "trailing_stop"
                self.trigger_time = datetime.now()
                return True
            
            if self.take_profit and current_price >= self.take_profit:
                self.stop_triggered = True
                self.trigger_reason = "take_profit"
                self.trigger_time = datetime.now()
                return True
        else:
            # Short position
            self.lowest_price = min(self.lowest_price, current_price)
            
            if trailing_pct > 0:
                new_trail = self.lowest_price * (1 + trailing_pct)
                if self.trailing_stop is None or new_trail < self.trailing_stop:
                    self.trailing_stop = new_trail
            
            if self.stop_loss and current_price >= self.stop_loss:
                self.stop_triggered = True
                self.trigger_reason = "stop_loss"
                self.trigger_time = datetime.now()
                return True
            
            if self.trailing_stop and current_price >= self.trailing_stop:
                self.stop_triggered = True
                self.trigger_reason = "trailing_stop"
                self.trigger_time = datetime.now()
                return True
            
            if self.take_profit and current_price <= self.take_profit:
                self.stop_triggered = True
                self.trigger_reason = "take_profit"
                self.trigger_time = datetime.now()
                return True
        
        return False
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized P&L percentage."""
        if self.entry_price == 0:
            return 0.0
        
        if self.side == Side.BUY:
            return (self.highest_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.lowest_price) / self.entry_price


# ---------------------------------------------------------------------------
# Daily Statistics
# ---------------------------------------------------------------------------

@dataclass
class DailyRiskStats:
    """Daily risk statistics."""
    date: date
    starting_equity: float
    current_equity: float
    high_water_mark: float
    low_water_mark: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    num_trades: int = 0
    num_wins: int = 0
    num_losses: int = 0
    
    @property
    def daily_return(self) -> float:
        if self.starting_equity == 0:
            return 0.0
        return (self.current_equity - self.starting_equity) / self.starting_equity
    
    @property
    def daily_drawdown(self) -> float:
        if self.high_water_mark == 0:
            return 0.0
        return (self.high_water_mark - self.current_equity) / self.high_water_mark
    
    @property
    def win_rate(self) -> float:
        total = self.num_wins + self.num_losses
        if total == 0:
            return 0.0
        return self.num_wins / total


# ---------------------------------------------------------------------------
# Risk Manager V2
# ---------------------------------------------------------------------------

class RiskManagerV2:
    """
    增强风险管理系统
    
    多层次风控:
    1. 账户级: 整体权益保护
    2. 策略级: 策略间隔离
    3. 仓位级: 单一标的控制
    4. 订单级: 单笔交易检查
    
    Features:
    - 实时风控监控
    - 动态止损止盈
    - 移动止损追踪
    - 日损限制
    - 强制平仓机制
    
    Usage:
        >>> rm = RiskManagerV2(config)
        >>> 
        >>> # 订单检查
        >>> result = rm.check_order(order, account, positions, price)
        >>> if not result:
        ...     print(f"Rejected: {result.reason}")
        >>> 
        >>> # 持仓止损
        >>> rm.add_position_stop(symbol, entry_price, quantity, Side.BUY)
        >>> triggered = rm.update_stops({"600519.SH": 1850.0})
        >>> 
        >>> # 日度统计
        >>> stats = rm.get_daily_stats()
    """
    
    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        event_engine = None
    ):
        """
        Initialize risk manager.
        
        Args:
            config: Risk configuration
            event_engine: Event engine for publishing risk events
        """
        self.config = config or RiskConfig()
        self.event_engine = event_engine
        
        # Position stops
        self._position_stops: Dict[str, PositionStop] = {}
        
        # Daily statistics
        self._daily_stats: Optional[DailyRiskStats] = None
        self._historical_stats: List[DailyRiskStats] = []
        
        # Rate limiting
        self._last_order_time: Dict[str, datetime] = {}
        
        # Callbacks
        self._risk_callbacks: List[Callable[[RiskEventType, Dict], None]] = []
        
        # State
        self._trading_halted = False
        self._halt_reason = ""
    
    # ---------------------------------------------------------------------------
    # Order Risk Checks
    # ---------------------------------------------------------------------------
    
    def check_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        price: float,
        account: AccountInfo,
        positions: Dict[str, PositionInfo]
    ) -> RiskCheckResult:
        """
        Comprehensive order risk check.
        
        Args:
            symbol: Trading symbol
            side: Order side
            quantity: Order quantity
            price: Order price
            account: Account info
            positions: Current positions
            
        Returns:
            RiskCheckResult
        """
        if not self.config.enabled:
            return RiskCheckResult.success("risk_disabled")
        
        if self._trading_halted:
            return RiskCheckResult.failure(
                f"Trading halted: {self._halt_reason}",
                RiskLevel.EMERGENCY,
                "trading_halted"
            )
        
        checks = [
            self._check_order_value(symbol, quantity, price, account),
            self._check_position_limit(symbol, side, quantity, price, account, positions),
            self._check_price_deviation(symbol, price),
            self._check_daily_loss(account),
            self._check_drawdown(account),
            self._check_rate_limit(symbol),
            self._check_max_positions(positions),
        ]
        
        for result in checks:
            if not result.passed:
                logger.warning(
                    "Order rejected by risk check",
                    rule=result.rule_name,
                    reason=result.reason,
                    symbol=symbol
                )
                self._publish_risk_event(RiskEventType.ORDER_REJECTED, {
                    "symbol": symbol,
                    "reason": result.reason,
                    "rule": result.rule_name
                })
                
                if self.config.strict_mode:
                    return result
        
        # Update rate limit
        self._last_order_time[symbol] = datetime.now()
        
        return RiskCheckResult.success("all_checks")
    
    def _check_order_value(
        self,
        symbol: str,
        quantity: float,
        price: float,
        account: AccountInfo
    ) -> RiskCheckResult:
        """Check order value limits."""
        order_value = quantity * price
        
        if order_value > self.config.max_order_value:
            return RiskCheckResult.failure(
                f"Order value {order_value:.2f} exceeds limit {self.config.max_order_value:.2f}",
                RiskLevel.WARNING,
                "max_order_value",
                order_value=order_value,
                limit=self.config.max_order_value
            )
        
        order_pct = order_value / account.total_value if account.total_value > 0 else 0
        if order_pct > self.config.max_order_pct:
            return RiskCheckResult.failure(
                f"Order {order_pct*100:.1f}% exceeds limit {self.config.max_order_pct*100:.1f}%",
                RiskLevel.WARNING,
                "max_order_pct",
                order_pct=order_pct
            )
        
        return RiskCheckResult.success("order_value")
    
    def _check_position_limit(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        price: float,
        account: AccountInfo,
        positions: Dict[str, PositionInfo]
    ) -> RiskCheckResult:
        """Check position limits."""
        current_pos = positions.get(symbol, PositionInfo(symbol=symbol))
        
        if side == Side.BUY:
            new_size = current_pos.size + quantity
        else:
            new_size = current_pos.size - quantity
        
        new_value = abs(new_size) * price
        max_value = account.total_value * self.config.max_position_pct
        
        if new_value > max_value:
            return RiskCheckResult.failure(
                f"Position {new_value:.2f} exceeds limit {max_value:.2f} ({self.config.max_position_pct*100:.0f}%)",
                RiskLevel.WARNING,
                "max_position_pct",
                position_value=new_value,
                limit=max_value
            )
        
        return RiskCheckResult.success("position_limit")
    
    def _check_price_deviation(self, symbol: str, price: float) -> RiskCheckResult:
        """Check price deviation from reference."""
        # TODO: Implement price deviation check with market data
        return RiskCheckResult.success("price_deviation")
    
    def _check_daily_loss(self, account: AccountInfo) -> RiskCheckResult:
        """Check daily loss limit."""
        if not self._daily_stats:
            return RiskCheckResult.success("daily_loss")
        
        daily_loss_pct = abs(self._daily_stats.daily_return) if self._daily_stats.daily_return < 0 else 0
        
        if daily_loss_pct > self.config.daily_loss_limit_pct:
            return RiskCheckResult.failure(
                f"Daily loss {daily_loss_pct*100:.2f}% exceeds limit {self.config.daily_loss_limit_pct*100:.1f}%",
                RiskLevel.CRITICAL,
                "daily_loss_limit",
                daily_loss=daily_loss_pct
            )
        
        return RiskCheckResult.success("daily_loss")
    
    def _check_drawdown(self, account: AccountInfo) -> RiskCheckResult:
        """Check drawdown limit."""
        if not self._daily_stats:
            return RiskCheckResult.success("drawdown")
        
        drawdown = self._daily_stats.daily_drawdown
        
        if drawdown > self.config.max_drawdown_pct:
            return RiskCheckResult.failure(
                f"Drawdown {drawdown*100:.2f}% exceeds limit {self.config.max_drawdown_pct*100:.1f}%",
                RiskLevel.CRITICAL,
                "max_drawdown",
                drawdown=drawdown
            )
        
        return RiskCheckResult.success("drawdown")
    
    def _check_rate_limit(self, symbol: str) -> RiskCheckResult:
        """Check order rate limit."""
        last_time = self._last_order_time.get(symbol)
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < self.config.min_order_interval_sec:
                return RiskCheckResult.failure(
                    f"Order too fast, wait {self.config.min_order_interval_sec - elapsed:.1f}s",
                    RiskLevel.INFO,
                    "rate_limit"
                )
        
        return RiskCheckResult.success("rate_limit")
    
    def _check_max_positions(self, positions: Dict[str, PositionInfo]) -> RiskCheckResult:
        """Check maximum positions count."""
        active_positions = sum(1 for p in positions.values() if p.size != 0)
        
        if active_positions >= self.config.max_positions:
            return RiskCheckResult.failure(
                f"Max positions reached: {active_positions}/{self.config.max_positions}",
                RiskLevel.WARNING,
                "max_positions"
            )
        
        return RiskCheckResult.success("max_positions")
    
    # ---------------------------------------------------------------------------
    # Position Stop Management
    # ---------------------------------------------------------------------------
    
    def add_position_stop(
        self,
        symbol: str,
        entry_price: float,
        quantity: float,
        side: Side,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> PositionStop:
        """
        Add position stop tracking.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            quantity: Position quantity
            side: Position side
            stop_loss: Stop loss price (or use default)
            take_profit: Take profit price (or use default)
            
        Returns:
            PositionStop instance
        """
        # Calculate default stops if not provided
        if stop_loss is None and self.config.enable_auto_stop:
            if side == Side.BUY:
                stop_loss = entry_price * (1 - self.config.default_stop_loss_pct)
            else:
                stop_loss = entry_price * (1 + self.config.default_stop_loss_pct)
        
        if take_profit is None and self.config.enable_auto_stop:
            if side == Side.BUY:
                take_profit = entry_price * (1 + self.config.default_take_profit_pct)
            else:
                take_profit = entry_price * (1 - self.config.default_take_profit_pct)
        
        stop = PositionStop(
            symbol=symbol,
            entry_price=entry_price,
            entry_time=datetime.now(),
            quantity=quantity,
            side=side,
            stop_loss=stop_loss,
            take_profit=take_profit,
            highest_price=entry_price,
            lowest_price=entry_price
        )
        
        self._position_stops[symbol] = stop
        
        logger.info(
            "Position stop added",
            symbol=symbol,
            entry=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        return stop
    
    def remove_position_stop(self, symbol: str) -> None:
        """Remove position stop tracking."""
        if symbol in self._position_stops:
            del self._position_stops[symbol]
            logger.info("Position stop removed", symbol=symbol)
    
    def update_stops(self, prices: Dict[str, float]) -> List[PositionStop]:
        """
        Update all position stops with current prices.
        
        Args:
            prices: Symbol to price mapping
            
        Returns:
            List of triggered stops
        """
        triggered = []
        
        for symbol, price in prices.items():
            stop = self._position_stops.get(symbol)
            if stop and not stop.stop_triggered:
                if stop.update_price(price, self.config.trailing_stop_pct):
                    triggered.append(stop)
                    
                    logger.warning(
                        "Stop triggered",
                        symbol=symbol,
                        reason=stop.trigger_reason,
                        price=price,
                        entry=stop.entry_price
                    )
                    
                    self._publish_risk_event(RiskEventType.STOP_TRIGGERED, {
                        "symbol": symbol,
                        "reason": stop.trigger_reason,
                        "price": price,
                        "entry_price": stop.entry_price,
                        "pnl_pct": stop.unrealized_pnl_pct
                    })
        
        return triggered
    
    def get_position_stop(self, symbol: str) -> Optional[PositionStop]:
        """Get position stop info."""
        return self._position_stops.get(symbol)
    
    def get_all_stops(self) -> Dict[str, PositionStop]:
        """Get all position stops."""
        return self._position_stops.copy()
    
    # ---------------------------------------------------------------------------
    # Daily Statistics
    # ---------------------------------------------------------------------------
    
    def start_new_day(self, starting_equity: float) -> None:
        """
        Start new trading day statistics.
        
        Args:
            starting_equity: Starting equity for the day
        """
        # Archive previous day
        if self._daily_stats:
            self._historical_stats.append(self._daily_stats)
        
        self._daily_stats = DailyRiskStats(
            date=date.today(),
            starting_equity=starting_equity,
            current_equity=starting_equity,
            high_water_mark=starting_equity,
            low_water_mark=starting_equity
        )
        
        # Reset trading halt
        self._trading_halted = False
        self._halt_reason = ""
        
        logger.info("New trading day started", equity=starting_equity)
    
    def update_equity(self, current_equity: float) -> None:
        """
        Update current equity and check limits.
        
        Args:
            current_equity: Current account equity
        """
        if not self._daily_stats:
            self.start_new_day(current_equity)
            return
        
        self._daily_stats.current_equity = current_equity
        self._daily_stats.high_water_mark = max(self._daily_stats.high_water_mark, current_equity)
        self._daily_stats.low_water_mark = min(self._daily_stats.low_water_mark, current_equity)
        
        # Check daily loss limit
        if self._daily_stats.daily_return < -self.config.daily_loss_limit_pct:
            self._halt_trading(f"Daily loss limit reached: {self._daily_stats.daily_return*100:.2f}%")
            self._publish_risk_event(RiskEventType.DAILY_LOSS_WARNING, {
                "daily_return": self._daily_stats.daily_return,
                "limit": self.config.daily_loss_limit_pct
            })
        
        # Check drawdown
        if self._daily_stats.daily_drawdown > self.config.max_drawdown_pct:
            self._publish_risk_event(RiskEventType.DRAWDOWN_WARNING, {
                "drawdown": self._daily_stats.daily_drawdown,
                "limit": self.config.max_drawdown_pct
            })
    
    def record_trade(self, pnl: float, is_win: bool) -> None:
        """Record trade result for statistics."""
        if not self._daily_stats:
            return
        
        self._daily_stats.realized_pnl += pnl
        self._daily_stats.num_trades += 1
        
        if is_win:
            self._daily_stats.num_wins += 1
        else:
            self._daily_stats.num_losses += 1
    
    def get_daily_stats(self) -> Optional[DailyRiskStats]:
        """Get current day statistics."""
        return self._daily_stats
    
    def get_historical_stats(self, days: int = 30) -> List[DailyRiskStats]:
        """Get historical statistics."""
        return self._historical_stats[-days:]
    
    # ---------------------------------------------------------------------------
    # Trading Control
    # ---------------------------------------------------------------------------
    
    def _halt_trading(self, reason: str) -> None:
        """Halt trading with reason."""
        self._trading_halted = True
        self._halt_reason = reason
        logger.critical("Trading halted", reason=reason)
    
    def resume_trading(self) -> None:
        """Resume trading."""
        self._trading_halted = False
        self._halt_reason = ""
        logger.info("Trading resumed")
    
    @property
    def is_trading_halted(self) -> bool:
        return self._trading_halted
    
    # ---------------------------------------------------------------------------
    # Events & Callbacks
    # ---------------------------------------------------------------------------
    
    def on_risk_event(self, callback: Callable[[RiskEventType, Dict], None]) -> None:
        """Register risk event callback."""
        self._risk_callbacks.append(callback)
    
    def _publish_risk_event(self, event_type: RiskEventType, data: Dict) -> None:
        """Publish risk event."""
        for callback in self._risk_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error("Risk callback error", error=str(e))
        
        if self.event_engine:
            from src.core.events import Event
            self.event_engine.put(Event(event_type.value, data))
    
    # ---------------------------------------------------------------------------
    # Utility
    # ---------------------------------------------------------------------------
    
    def calculate_position_size(
        self,
        account_value: float,
        price: float,
        stop_loss_pct: Optional[float] = None,
        risk_per_trade_pct: float = 0.02
    ) -> int:
        """
        Calculate position size based on risk.
        
        Args:
            account_value: Total account value
            price: Entry price
            stop_loss_pct: Stop loss percentage (uses default if None)
            risk_per_trade_pct: Risk per trade as % of account
            
        Returns:
            Position size (shares)
        """
        stop_loss_pct = stop_loss_pct or self.config.default_stop_loss_pct
        
        # Risk amount
        risk_amount = account_value * risk_per_trade_pct
        
        # Loss per share
        loss_per_share = price * stop_loss_pct
        
        # Position size
        if loss_per_share > 0:
            size = int(risk_amount / loss_per_share)
        else:
            size = 0
        
        # Check against position limit
        max_size = int((account_value * self.config.max_position_pct) / price)
        size = min(size, max_size)
        
        return max(0, size)
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get risk summary."""
        return {
            "config": {
                "max_position_pct": self.config.max_position_pct,
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "daily_loss_limit_pct": self.config.daily_loss_limit_pct,
                "max_positions": self.config.max_positions
            },
            "trading_halted": self._trading_halted,
            "halt_reason": self._halt_reason,
            "active_stops": len(self._position_stops),
            "triggered_stops": sum(1 for s in self._position_stops.values() if s.stop_triggered),
            "daily_stats": {
                "date": str(self._daily_stats.date) if self._daily_stats else None,
                "daily_return": self._daily_stats.daily_return if self._daily_stats else 0,
                "drawdown": self._daily_stats.daily_drawdown if self._daily_stats else 0,
                "num_trades": self._daily_stats.num_trades if self._daily_stats else 0,
                "win_rate": self._daily_stats.win_rate if self._daily_stats else 0
            } if self._daily_stats else None
        }


# ---------------------------------------------------------------------------
# Predefined Configurations
# ---------------------------------------------------------------------------

def create_conservative_config() -> RiskConfig:
    """Create conservative risk configuration."""
    return RiskConfig(
        max_position_pct=0.15,
        max_positions=5,
        max_order_pct=0.05,
        max_drawdown_pct=0.10,
        daily_loss_limit_pct=0.02,
        default_stop_loss_pct=0.03,
        trailing_stop_pct=0.03
    )


def create_moderate_config() -> RiskConfig:
    """Create moderate risk configuration."""
    return RiskConfig(
        max_position_pct=0.25,
        max_positions=10,
        max_order_pct=0.10,
        max_drawdown_pct=0.15,
        daily_loss_limit_pct=0.05,
        default_stop_loss_pct=0.05,
        trailing_stop_pct=0.05
    )


def create_aggressive_config() -> RiskConfig:
    """Create aggressive risk configuration."""
    return RiskConfig(
        max_position_pct=0.40,
        max_positions=20,
        max_order_pct=0.20,
        max_drawdown_pct=0.25,
        daily_loss_limit_pct=0.10,
        default_stop_loss_pct=0.08,
        trailing_stop_pct=0.08,
        enable_auto_stop=False  # Manual stop management
    )


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    'RiskManagerV2',
    'RiskConfig',
    'RiskCheckResult',
    'RiskEventType',
    'RiskLevel',
    'PositionStop',
    'DailyRiskStats',
    'create_conservative_config',
    'create_moderate_config',
    'create_aggressive_config',
]
