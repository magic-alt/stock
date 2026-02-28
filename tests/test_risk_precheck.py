"""
Tests for PaperGateway risk pre-check integration (A-2).

Covers:
- Risk check called on every send_order when risk_manager is set
- Valid orders (passed=True) proceed to matching engine
- Rejected orders (passed=False) raise ValueError before creating order state
- RISK_WARNING event published on rejection
- Gateway without risk_manager allows all orders unconditionally
- Correct data (symbol, side, price, account, positions) forwarded to check_order
- Integration tests with a real RiskManagerV2 instance
"""
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pass_result():
    """Return a real RiskCheckResult that evaluates to True."""
    from src.core.risk_manager_v2 import RiskCheckResult, RiskLevel
    return RiskCheckResult(passed=True, reason="OK", level=RiskLevel.INFO, rule_name="all_checks")


def _make_fail_result(reason="Position too large", rule_name="max_position_pct"):
    """Return a real RiskCheckResult that evaluates to False."""
    from src.core.risk_manager_v2 import RiskCheckResult, RiskLevel
    return RiskCheckResult(passed=False, reason=reason, level=RiskLevel.WARNING, rule_name=rule_name)


def _build_gateway(events, risk_manager=None, initial_cash=100_000.0):
    """
    Helper that builds a PaperGateway while patching out the heavy simulation
    components (MatchingEngine, FixedSlippage) so tests don't need real
    sortedcontainers / simulation infrastructure.

    The returned gateway's ``matching_engine`` attribute is a MagicMock, so
    ``submit_order`` calls are no-ops by default.
    """
    with patch("src.core.paper_gateway_v3.MatchingEngine") as mock_me_cls, \
         patch("src.core.paper_gateway_v3.FixedSlippage") as mock_slip_cls:
        mock_me_cls.return_value = MagicMock()
        mock_slip_cls.return_value = MagicMock()

        from src.core.paper_gateway_v3 import PaperGateway
        gw = PaperGateway(
            events,
            initial_cash=initial_cash,
            risk_manager=risk_manager,
        )
    # matching_engine is now a MagicMock; submit_order calls are captured
    return gw


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestRiskPrecheckInPaperGateway:
    """Unit-level tests for risk pre-check integration in PaperGateway."""

    # -- fixtures ------------------------------------------------------------

    @pytest.fixture
    def mock_events(self):
        """Mock EventEngine whose put() and register() calls are captured."""
        events = MagicMock()
        events.register = MagicMock()
        events.put = MagicMock()
        return events

    @pytest.fixture
    def mock_risk_manager(self):
        """Mock RiskManagerV2 that returns passed=True by default."""
        rm = MagicMock()
        rm.check_order.return_value = _make_pass_result()
        return rm

    @pytest.fixture
    def gateway_with_risk(self, mock_events, mock_risk_manager):
        return _build_gateway(mock_events, risk_manager=mock_risk_manager)

    @pytest.fixture
    def gateway_no_risk(self, mock_events):
        return _build_gateway(mock_events)

    # -- basic pass / reject -------------------------------------------------

    def test_valid_order_passes_risk_check(self, gateway_with_risk, mock_risk_manager):
        """check_order passes → send_order returns a valid order ID."""
        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        oid = gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        assert oid is not None
        assert oid.startswith("PAPER-")
        assert mock_risk_manager.check_order.called

    def test_order_rejected_raises_value_error(self, gateway_with_risk, mock_risk_manager):
        """check_order fails → send_order raises ValueError."""
        mock_risk_manager.check_order.return_value = _make_fail_result(
            reason="Position too large", rule_name="max_position_pct"
        )
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        with pytest.raises(ValueError, match="Order rejected by risk check"):
            gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

    def test_rejected_error_message_contains_rule_and_reason(self, gateway_with_risk, mock_risk_manager):
        """ValueError message embeds rule name and human-readable reason."""
        mock_risk_manager.check_order.return_value = _make_fail_result(
            reason="Daily limit breached", rule_name="daily_loss_limit"
        )
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        with pytest.raises(ValueError) as exc_info:
            gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        msg = str(exc_info.value)
        assert "daily_loss_limit" in msg
        assert "Daily limit breached" in msg

    # -- event publishing ----------------------------------------------------

    def test_risk_warning_event_published_on_reject(
        self, gateway_with_risk, mock_risk_manager, mock_events
    ):
        """RISK_WARNING event is put onto the event engine when rejected."""
        from src.core.events import EventType

        mock_risk_manager.check_order.return_value = _make_fail_result(
            reason="Exceeds daily loss", rule_name="daily_loss_limit"
        )
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        with pytest.raises(ValueError):
            gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        # At least one call to events.put with type == RISK_WARNING
        risk_calls = [
            c for c in mock_events.put.call_args_list
            if c.args[0].type == EventType.RISK_WARNING
        ]
        assert len(risk_calls) == 1

    def test_risk_warning_event_payload(
        self, gateway_with_risk, mock_risk_manager, mock_events
    ):
        """RISK_WARNING event payload contains symbol, reason and rule."""
        from src.core.events import EventType

        mock_risk_manager.check_order.return_value = _make_fail_result(
            reason="Too fat finger", rule_name="max_order_value"
        )
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        with pytest.raises(ValueError):
            gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        risk_evt = next(
            c.args[0]
            for c in mock_events.put.call_args_list
            if c.args[0].type == EventType.RISK_WARNING
        )
        assert risk_evt.data["symbol"] == "600519.SH"
        assert risk_evt.data["reason"] == "Too fat finger"
        assert risk_evt.data["rule"] == "max_order_value"

    def test_no_event_published_on_pass(
        self, gateway_with_risk, mock_risk_manager, mock_events
    ):
        """No RISK_WARNING event when check passes."""
        from src.core.events import EventType

        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        risk_calls = [
            c for c in mock_events.put.call_args_list
            if c.args[0].type == EventType.RISK_WARNING
        ]
        assert len(risk_calls) == 0

    # -- no risk manager ------------------------------------------------------

    def test_no_risk_manager_allows_all_orders(self, gateway_no_risk):
        """Gateway without risk_manager allows all orders (no check_order call)."""
        gateway_no_risk._last_prices["600519.SH"] = 1850.0
        oid = gateway_no_risk.send_order("600519.SH", "buy", 100, order_type="market")
        assert oid is not None
        assert oid.startswith("PAPER-")

    # -- state isolation on rejection ----------------------------------------

    def test_rejected_order_not_added_to_orders_dict(
        self, gateway_with_risk, mock_risk_manager
    ):
        """A rejected order must not appear in _orders (state stays clean)."""
        mock_risk_manager.check_order.return_value = _make_fail_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        initial_count = len(gateway_with_risk._orders)

        with pytest.raises(ValueError):
            gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        assert len(gateway_with_risk._orders) == initial_count

    def test_rejected_order_id_counter_not_incremented(
        self, gateway_with_risk, mock_risk_manager
    ):
        """Order ID counter must not advance on rejection."""
        mock_risk_manager.check_order.return_value = _make_fail_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        counter_before = gateway_with_risk._oid_counter

        with pytest.raises(ValueError):
            gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        assert gateway_with_risk._oid_counter == counter_before

    # -- arguments forwarded to check_order ----------------------------------

    def test_check_order_called_with_correct_symbol(
        self, gateway_with_risk, mock_risk_manager
    ):
        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0
        gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        assert kwargs["symbol"] == "600519.SH"

    def test_check_order_receives_buy_side_enum(
        self, gateway_with_risk, mock_risk_manager
    ):
        from src.core.interfaces import Side

        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0
        gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        assert kwargs["side"] == Side.BUY

    def test_check_order_receives_sell_side_enum(
        self, gateway_with_risk, mock_risk_manager
    ):
        from src.core.interfaces import Side

        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0
        gateway_with_risk.send_order("600519.SH", "sell", 50, order_type="market")

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        assert kwargs["side"] == Side.SELL

    def test_limit_order_price_forwarded_to_check_order(
        self, gateway_with_risk, mock_risk_manager
    ):
        """Explicit limit price should be passed as the risk-check price."""
        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0

        gateway_with_risk.send_order(
            "600519.SH", "buy", 100, price=1870.0, order_type="limit"
        )

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        assert kwargs["price"] == 1870.0

    def test_market_order_uses_last_price_for_check(
        self, gateway_with_risk, mock_risk_manager
    ):
        """For market orders with no explicit price, last known price is used."""
        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1920.0

        gateway_with_risk.send_order("600519.SH", "buy", 100, order_type="market")

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        assert kwargs["price"] == 1920.0

    def test_check_order_receives_account_info_object(
        self, gateway_with_risk, mock_risk_manager
    ):
        """check_order account arg must be an AccountInfo with correct cash."""
        from src.core.interfaces import AccountInfo

        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0
        gateway_with_risk.send_order("600519.SH", "buy", 10, order_type="market")

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        account = kwargs["account"]
        assert isinstance(account, AccountInfo)
        assert account.account_id == "PAPER"
        # initial_cash=100_000, no trades yet → balance == 100_000
        assert account.cash == pytest.approx(100_000.0)
        assert account.total_value == pytest.approx(100_000.0)

    def test_check_order_receives_empty_positions_on_fresh_gateway(
        self, gateway_with_risk, mock_risk_manager
    ):
        """positions dict is empty when no trades have occurred."""
        mock_risk_manager.check_order.return_value = _make_pass_result()
        gateway_with_risk._last_prices["600519.SH"] = 1850.0
        gateway_with_risk.send_order("600519.SH", "buy", 10, order_type="market")

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        assert isinstance(kwargs["positions"], dict)
        assert len(kwargs["positions"]) == 0

    def test_check_order_receives_existing_positions(
        self, gateway_with_risk, mock_risk_manager
    ):
        """Existing open positions are reflected in the positions dict."""
        from src.core.interfaces import PositionInfo
        from src.core.paper_gateway_v3 import _Position

        # Manually plant an open position
        gateway_with_risk._positions["600519.SH"] = _Position(
            size=200.0, avg_price=1800.0, realized_pnl=0.0
        )
        gateway_with_risk._last_prices["600519.SH"] = 1850.0
        mock_risk_manager.check_order.return_value = _make_pass_result()

        gateway_with_risk.send_order("600519.SH", "buy", 10, order_type="market")

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        positions = kwargs["positions"]
        assert "600519.SH" in positions
        pos = positions["600519.SH"]
        assert isinstance(pos, PositionInfo)
        assert pos.size == 200.0
        assert pos.avg_price == 1800.0

    def test_zero_size_position_excluded_from_positions(
        self, gateway_with_risk, mock_risk_manager
    ):
        """Positions with size==0 are excluded from the risk check dict."""
        from src.core.paper_gateway_v3 import _Position

        gateway_with_risk._positions["600519.SH"] = _Position(
            size=0.0, avg_price=0.0, realized_pnl=50.0
        )
        gateway_with_risk._last_prices["600519.SH"] = 1850.0
        mock_risk_manager.check_order.return_value = _make_pass_result()

        gateway_with_risk.send_order("600519.SH", "buy", 10, order_type="market")

        kwargs = mock_risk_manager.check_order.call_args.kwargs
        assert "600519.SH" not in kwargs["positions"]


# ---------------------------------------------------------------------------
# Integration tests with real RiskManagerV2
# ---------------------------------------------------------------------------

class TestRiskPrecheckIntegration:
    """Integration tests coupling PaperGateway with a real RiskManagerV2."""

    def _build_real_gw(self, config, initial_cash=100_000.0):
        from src.core.risk_manager_v2 import RiskManagerV2
        from src.core.events import EventEngine

        events = EventEngine()
        rm = RiskManagerV2(config)

        with patch("src.core.paper_gateway_v3.MatchingEngine") as mock_me_cls, \
             patch("src.core.paper_gateway_v3.FixedSlippage") as mock_slip_cls:
            mock_me_cls.return_value = MagicMock()
            mock_slip_cls.return_value = MagicMock()

            from src.core.paper_gateway_v3 import PaperGateway
            gw = PaperGateway(events, initial_cash=initial_cash, risk_manager=rm)

        return gw

    def test_small_order_passes_position_limit(self):
        """Order well within position limit should pass."""
        from src.core.risk_manager_v2 import RiskConfig

        config = RiskConfig(
            max_position_pct=0.30,   # 30 % of equity
            max_order_value=500_000.0,
            max_order_pct=0.50,
            enabled=True,
        )
        gw = self._build_real_gw(config, initial_cash=100_000.0)
        gw._last_prices["600519.SH"] = 100.0
        # 10 shares @ 100 = 1 000 → 1 % of equity (well under 30 %)
        oid = gw.send_order("600519.SH", "buy", 10, price=100.0, order_type="limit")
        assert oid.startswith("PAPER-")

    def test_oversized_order_rejected_by_position_limit(self):
        """Order exceeding max_position_pct should raise ValueError."""
        from src.core.risk_manager_v2 import RiskConfig

        config = RiskConfig(
            max_position_pct=0.05,   # Only 5 % of equity allowed per position
            max_order_value=500_000.0,
            max_order_pct=0.50,
            enabled=True,
        )
        gw = self._build_real_gw(config, initial_cash=100_000.0)
        gw._last_prices["600519.SH"] = 100.0
        # 200 shares @ 100 = 20 000 → 20 % of equity (over 5 % limit)
        with pytest.raises(ValueError, match="max_position_pct"):
            gw.send_order("600519.SH", "buy", 200, price=100.0, order_type="limit")

    def test_disabled_risk_manager_allows_oversized(self):
        """When risk config has enabled=False all orders are let through."""
        from src.core.risk_manager_v2 import RiskConfig

        config = RiskConfig(
            max_position_pct=0.01,   # Would normally reject almost everything
            enabled=False,
        )
        gw = self._build_real_gw(config, initial_cash=100_000.0)
        gw._last_prices["600519.SH"] = 100.0
        oid = gw.send_order("600519.SH", "buy", 999, price=100.0, order_type="limit")
        assert oid.startswith("PAPER-")

    def test_daily_loss_limit_rejected_when_stats_set(self):
        """Daily loss limit halts trading when daily stats show a loss."""
        from src.core.risk_manager_v2 import RiskConfig, RiskManagerV2
        from src.core.events import EventEngine

        config = RiskConfig(
            daily_loss_limit_pct=0.02,    # 2 % daily loss limit
            max_position_pct=0.99,
            max_order_value=1_000_000.0,
            max_order_pct=0.99,
            enabled=True,
        )
        events = EventEngine()
        rm = RiskManagerV2(config)
        # Simulate having started the day at 100 000 and now at 97 000 (3 % loss)
        rm.start_new_day(100_000.0)
        rm.update_equity(97_000.0)

        with patch("src.core.paper_gateway_v3.MatchingEngine") as mock_me_cls, \
             patch("src.core.paper_gateway_v3.FixedSlippage") as mock_slip_cls:
            mock_me_cls.return_value = MagicMock()
            mock_slip_cls.return_value = MagicMock()

            from src.core.paper_gateway_v3 import PaperGateway
            gw = PaperGateway(events, initial_cash=100_000.0, risk_manager=rm)

        gw._last_prices["600519.SH"] = 100.0
        # Trading should be halted due to daily loss → order must be rejected
        with pytest.raises(ValueError):
            gw.send_order("600519.SH", "buy", 10, price=100.0, order_type="limit")
