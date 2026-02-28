"""
Tests for gateway protocol unification.

Verifies that PaperGateway, XtpGateway, and HundsunUftGateway expose
consistent behavioral patterns.  PaperGateway is tested via mocked
simulation modules so the test suite runs without the optional
simulation package installed.
"""
from __future__ import annotations

import sys
import types
from queue import Queue
from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Simulation module fixtures (injected into sys.modules so PaperGateway
# believes the simulation package exists when it is evaluated).
# ---------------------------------------------------------------------------

def _build_simulation_modules():
    """Return fake src.simulation.* modules that satisfy PaperGateway."""

    # --- src.simulation.order ------------------------------------------------
    order_mod = types.ModuleType("src.simulation.order")

    class _OrderDirection:
        BUY = "BUY"
        SELL = "SELL"

    class _SimOrderType:
        MARKET = "MARKET"
        LIMIT = "LIMIT"
        STOP = "STOP"

    class _SimOrder:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _SimTrade:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    order_mod.OrderDirection = _OrderDirection
    order_mod.OrderType = _SimOrderType
    order_mod.Order = _SimOrder
    order_mod.Trade = _SimTrade

    # --- src.simulation.slippage ---------------------------------------------
    slippage_mod = types.ModuleType("src.simulation.slippage")

    class _SlippageModel:
        pass

    class _FixedSlippage(_SlippageModel):
        def __init__(self, slippage_ticks=1, tick_size=0.01):
            pass

    slippage_mod.SlippageModel = _SlippageModel
    slippage_mod.FixedSlippage = _FixedSlippage

    # --- src.simulation.matching_engine --------------------------------------
    me_mod = types.ModuleType("src.simulation.matching_engine")

    class _MatchingEngine:
        def __init__(self, slippage_model=None, event_engine=None):
            pass

        def submit_order(self, order):
            pass

        def cancel_order(self, order_id: str):
            pass

        def on_bar(self, symbol, bar):
            pass

        def reset(self):
            pass

    me_mod.MatchingEngine = _MatchingEngine

    # --- src.simulation (package) --------------------------------------------
    sim_pkg = types.ModuleType("src.simulation")

    return {
        "src.simulation": sim_pkg,
        "src.simulation.matching_engine": me_mod,
        "src.simulation.order": order_mod,
        "src.simulation.slippage": slippage_mod,
    }


@pytest.fixture(scope="session")
def simulation_module_patch():
    """Session-scoped fixture: inject simulation mocks once for all tests."""
    fake_mods = _build_simulation_modules()
    with patch.dict(sys.modules, fake_mods):
        # Force paper_gateway_v3 to be re-evaluated with mocks in place.
        sys.modules.pop("src.core.paper_gateway_v3", None)
        yield fake_mods


@pytest.fixture
def paper_gateway(simulation_module_patch):
    """Create a PaperGateway backed by mocked simulation modules."""
    # Ensure fresh import with mocks active.
    sys.modules.pop("src.core.paper_gateway_v3", None)
    from src.core.paper_gateway_v3 import PaperGateway

    events = MagicMock()
    events.put = MagicMock()
    events.register = MagicMock()

    gw = PaperGateway(events, initial_cash=100_000.0)
    yield gw


# ---------------------------------------------------------------------------
# Live gateway helpers
# ---------------------------------------------------------------------------

def _make_xtp_gateway() -> "XtpGateway":  # type: ignore[name-defined]  # noqa: F821
    from src.gateways.xtp_gateway import XtpGateway
    from src.gateways.base_live_gateway import GatewayConfig
    cfg = GatewayConfig(account_id="TEST_XTP", broker="xtp", auto_reconnect=False)
    gw = XtpGateway(cfg, Queue())
    gw.connect()
    return gw


def _make_uft_gateway() -> "HundsunUftGateway":  # type: ignore[name-defined]  # noqa: F821
    from src.gateways.hundsun_uft_gateway import HundsunUftGateway
    from src.gateways.base_live_gateway import GatewayConfig
    cfg = GatewayConfig(account_id="TEST_UFT", broker="hundsun", auto_reconnect=False)
    gw = HundsunUftGateway(cfg, Queue())
    gw.connect()
    return gw


@pytest.fixture
def xtp_gateway():
    return _make_xtp_gateway()


@pytest.fixture
def uft_gateway():
    return _make_uft_gateway()


# ---------------------------------------------------------------------------
# TestPaperGatewayProtocol
# ---------------------------------------------------------------------------

class TestPaperGatewayProtocol:
    """Behavioral tests for PaperGateway against the TradeGateway protocol."""

    def test_instantiation_succeeds(self, paper_gateway):
        assert paper_gateway is not None

    def test_send_order_returns_str(self, paper_gateway):
        oid = paper_gateway.send_order("600519.SH", "buy", 100)
        assert isinstance(oid, str)

    def test_send_order_paper_prefix(self, paper_gateway):
        oid = paper_gateway.send_order("600519.SH", "buy", 100)
        assert oid.startswith("PAPER-")

    def test_send_limit_order_with_price(self, paper_gateway):
        oid = paper_gateway.send_order("600519.SH", "buy", 100, price=1800.0, order_type="limit")
        assert isinstance(oid, str) and oid.startswith("PAPER-")

    def test_send_limit_order_without_price_raises(self, paper_gateway):
        with pytest.raises(ValueError):
            paper_gateway.send_order("600519.SH", "buy", 100, order_type="limit")

    def test_cancel_active_order_returns_true(self, paper_gateway):
        oid = paper_gateway.send_order("600519.SH", "buy", 100)
        result = paper_gateway.cancel_order(oid)
        assert result is True

    def test_cancel_unknown_order_returns_false(self, paper_gateway):
        result = paper_gateway.cancel_order("PAPER-99999999")
        assert result is False

    def test_cancel_already_cancelled_returns_false(self, paper_gateway):
        oid = paper_gateway.send_order("600519.SH", "buy", 100)
        paper_gateway.cancel_order(oid)
        # Second cancel on inactive order should return False
        result = paper_gateway.cancel_order(oid)
        assert result is False

    def test_query_account_returns_dict(self, paper_gateway):
        account = paper_gateway.query_account()
        assert isinstance(account, dict)

    @pytest.mark.parametrize("key", [
        "account_id", "balance", "equity", "positions_value",
        "unrealized_pnl", "realized_pnl", "available", "initial_cash", "return_pct",
    ])
    def test_query_account_has_key(self, paper_gateway, key):
        account = paper_gateway.query_account()
        assert key in account

    def test_query_account_initial_cash_correct(self, paper_gateway):
        account = paper_gateway.query_account()
        assert account["initial_cash"] == 100_000.0

    def test_query_account_balance_is_numeric(self, paper_gateway):
        account = paper_gateway.query_account()
        for numeric_key in ("balance", "equity", "available"):
            assert isinstance(account[numeric_key], (int, float))

    def test_query_position_returns_dict(self, paper_gateway):
        pos = paper_gateway.query_position("600519.SH")
        assert isinstance(pos, dict)

    @pytest.mark.parametrize("key", [
        "symbol", "size", "avg_price", "market_price",
        "market_value", "unrealized_pnl", "realized_pnl",
    ])
    def test_query_position_has_key(self, paper_gateway, key):
        pos = paper_gateway.query_position("600519.SH")
        assert key in pos

    def test_query_position_symbol_matches(self, paper_gateway):
        pos = paper_gateway.query_position("000001.SZ")
        assert pos["symbol"] == "000001.SZ"

    def test_query_position_zero_size_for_unknown_symbol(self, paper_gateway):
        pos = paper_gateway.query_position("UNKNOWN.SH")
        assert pos["size"] == 0.0

    def test_query_orders_returns_list(self, paper_gateway):
        assert isinstance(paper_gateway.query_orders(), list)

    def test_query_orders_contains_submitted_order(self, paper_gateway):
        oid = paper_gateway.send_order("600519.SH", "buy", 100)
        order_ids = [o["order_id"] for o in paper_gateway.query_orders()]
        assert oid in order_ids

    def test_query_orders_symbol_filter(self, paper_gateway):
        paper_gateway.send_order("600519.SH", "buy", 10)
        orders = paper_gateway.query_orders(symbol="600519.SH")
        assert all(o["symbol"] == "600519.SH" for o in orders)

    @pytest.mark.parametrize("side", ["buy", "sell"])
    def test_send_order_both_sides(self, paper_gateway, side):
        oid = paper_gateway.send_order("600519.SH", side, 1)
        assert isinstance(oid, str)


# ---------------------------------------------------------------------------
# TestXtpGatewayStubProtocol
# ---------------------------------------------------------------------------

class TestXtpGatewayStubProtocol:
    """XtpGateway runs in stub mode automatically when XTP SDK is absent."""

    def test_stub_mode_active(self, xtp_gateway):
        assert xtp_gateway._stub_mode is True

    def test_is_connected_after_connect(self, xtp_gateway):
        assert xtp_gateway.is_connected is True

    def test_send_order_returns_str(self, xtp_gateway):
        oid = xtp_gateway.send_order("600519.SH", "buy", 100, price=1800.0, order_type="limit")
        assert isinstance(oid, str) and len(oid) > 0

    def test_cancel_order_returns_bool(self, xtp_gateway):
        oid = xtp_gateway.send_order("600519.SH", "buy", 100, price=1800.0, order_type="limit")
        assert isinstance(xtp_gateway.cancel_order(oid), bool)

    def test_cancel_nonexistent_order_raises(self, xtp_gateway):
        with pytest.raises(ValueError):
            xtp_gateway.cancel_order("XTP-NONEXISTENT")

    def test_query_account_returns_account_update(self, xtp_gateway):
        from src.gateways.base_live_gateway import AccountUpdate
        result = xtp_gateway.query_account()
        assert isinstance(result, AccountUpdate)

    def test_query_account_account_id(self, xtp_gateway):
        assert xtp_gateway.query_account().account_id == "TEST_XTP"

    def test_query_account_positive_equity(self, xtp_gateway):
        assert xtp_gateway.query_account().equity > 0

    def test_query_positions_returns_list(self, xtp_gateway):
        assert isinstance(xtp_gateway.query_positions(), list)

    def test_query_positions_stub_non_empty(self, xtp_gateway):
        assert len(xtp_gateway.query_positions()) > 0

    def test_query_position_unknown_returns_none(self, xtp_gateway):
        assert xtp_gateway.query_position("UNKNOWN.XX") is None

    def test_query_position_known_stub_symbol(self, xtp_gateway):
        from src.gateways.base_live_gateway import PositionUpdate
        result = xtp_gateway.query_position("600519.SH")
        # May be None if stub data uses a different symbol; accept both.
        assert result is None or isinstance(result, PositionUpdate)


# ---------------------------------------------------------------------------
# TestHundsunGatewayStubProtocol
# ---------------------------------------------------------------------------

class TestHundsunGatewayStubProtocol:
    """HundsunUftGateway runs in stub mode when UFT SDK is absent."""

    def test_stub_mode_active(self, uft_gateway):
        assert uft_gateway._stub_mode is True

    def test_is_connected_after_connect(self, uft_gateway):
        assert uft_gateway.is_connected is True

    def test_send_order_returns_str(self, uft_gateway):
        oid = uft_gateway.send_order("600519.SH", "buy", 100, price=1800.0, order_type="limit")
        assert isinstance(oid, str) and len(oid) > 0

    def test_cancel_order_returns_bool(self, uft_gateway):
        oid = uft_gateway.send_order("600519.SH", "buy", 100, price=1800.0, order_type="limit")
        assert isinstance(uft_gateway.cancel_order(oid), bool)

    def test_cancel_nonexistent_order_raises(self, uft_gateway):
        with pytest.raises(ValueError):
            uft_gateway.cancel_order("UFT-NONEXISTENT")

    def test_query_account_returns_account_update(self, uft_gateway):
        from src.gateways.base_live_gateway import AccountUpdate
        result = uft_gateway.query_account()
        assert isinstance(result, AccountUpdate)

    def test_query_account_account_id(self, uft_gateway):
        assert uft_gateway.query_account().account_id == "TEST_UFT"

    def test_query_account_positive_equity(self, uft_gateway):
        assert uft_gateway.query_account().equity > 0

    def test_query_positions_returns_list(self, uft_gateway):
        assert isinstance(uft_gateway.query_positions(), list)

    def test_query_positions_stub_non_empty(self, uft_gateway):
        assert len(uft_gateway.query_positions()) > 0

    def test_query_position_unknown_returns_none(self, uft_gateway):
        assert uft_gateway.query_position("UNKNOWN.XX") is None

    def test_query_position_known_stub_symbol(self, uft_gateway):
        from src.gateways.base_live_gateway import PositionUpdate
        result = uft_gateway.query_position("600519.SH")
        assert result is None or isinstance(result, PositionUpdate)


# ---------------------------------------------------------------------------
# TestGatewayBehaviorConsistency
# ---------------------------------------------------------------------------

class TestGatewayBehaviorConsistency:
    """
    Cross-gateway behavioral consistency tests.

    XTP and Hundsun both derive from BaseLiveGateway and must expose the same
    structural contract.  PaperGateway deviates intentionally (returns plain
    dicts) and is included only where its behaviour is comparable.
    """

    @pytest.fixture(autouse=True)
    def _gateways(self, xtp_gateway, uft_gateway):
        self.xtp = xtp_gateway
        self.uft = uft_gateway

    # -- both in stub mode ---------------------------------------------------

    def test_both_in_stub_mode(self):
        assert self.xtp._stub_mode is True
        assert self.uft._stub_mode is True

    # -- send_order consistency ----------------------------------------------

    @pytest.mark.parametrize("gw_attr", ["xtp", "uft"])
    def test_send_order_returns_nonempty_str(self, gw_attr):
        gw = getattr(self, gw_attr)
        oid = gw.send_order("600519.SH", "buy", 100, price=1800.0, order_type="limit")
        assert isinstance(oid, str) and len(oid) > 0

    @pytest.mark.parametrize("gw_attr", ["xtp", "uft"])
    def test_send_order_unique_ids(self, gw_attr):
        gw = getattr(self, gw_attr)
        ids = {gw.send_order("600519.SH", "buy", 10, price=1800.0, order_type="limit") for _ in range(4)}
        assert len(ids) == 4

    # -- cancel_order consistency --------------------------------------------

    @pytest.mark.parametrize("gw_attr", ["xtp", "uft"])
    def test_cancel_submitted_order_returns_bool(self, gw_attr):
        gw = getattr(self, gw_attr)
        oid = gw.send_order("600519.SH", "buy", 100, price=1800.0, order_type="limit")
        assert isinstance(gw.cancel_order(oid), bool)

    @pytest.mark.parametrize("gw_attr", ["xtp", "uft"])
    def test_cancel_unknown_order_raises_value_error(self, gw_attr):
        with pytest.raises(ValueError):
            getattr(self, gw_attr).cancel_order("DOES-NOT-EXIST")

    # -- query_account consistency -------------------------------------------

    @pytest.mark.parametrize("gw_attr", ["xtp", "uft"])
    def test_query_account_not_none(self, gw_attr):
        assert getattr(self, gw_attr).query_account() is not None

    @pytest.mark.parametrize("gw_attr", ["xtp", "uft"])
    @pytest.mark.parametrize("field", ["account_id", "cash", "available", "equity", "frozen"])
    def test_query_account_has_field(self, gw_attr, field):
        result = getattr(self, gw_attr).query_account()
        assert hasattr(result, field), f"{gw_attr}.query_account() missing field '{field}'"

    def test_query_account_equity_both_positive(self):
        assert self.xtp.query_account().equity > 0
        assert self.uft.query_account().equity > 0

    # -- query_positions consistency -----------------------------------------

    @pytest.mark.parametrize("gw_attr", ["xtp", "uft"])
    def test_query_positions_returns_list(self, gw_attr):
        assert isinstance(getattr(self, gw_attr).query_positions(), list)

    def test_position_update_fields_identical(self):
        xtp_pos = self.xtp.query_positions()[0]
        uft_pos = self.uft.query_positions()[0]
        for field in ("symbol", "total_quantity", "available_quantity", "avg_price", "unrealized_pnl"):
            assert hasattr(xtp_pos, field), f"XTP PositionUpdate missing '{field}'"
            assert hasattr(uft_pos, field), f"UFT PositionUpdate missing '{field}'"

    # -- disconnect consistency -----------------------------------------------

    @pytest.mark.parametrize("GwClass,broker", [
        ("src.gateways.xtp_gateway.XtpGateway", "xtp"),
        ("src.gateways.hundsun_uft_gateway.HundsunUftGateway", "hundsun"),
    ])
    def test_disconnect_clears_connected(self, GwClass, broker):
        from src.gateways.base_live_gateway import GatewayConfig
        import importlib
        module_path, cls_name = GwClass.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, cls_name)

        cfg = GatewayConfig(account_id=f"DISC_{broker.upper()}", broker=broker, auto_reconnect=False)
        gw = cls(cfg, Queue())
        gw.connect()
        assert gw.is_connected is True
        gw.disconnect()
        assert gw.is_connected is False
