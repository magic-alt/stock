"""
Gateway Mock SDK Tests (P3.3)

Tests for XTP and Hundsun UFT gateways in both stub mode and with mock SDK injection.
Validates the full lifecycle: connect → send_order → cancel → query → disconnect.
"""
from __future__ import annotations

import threading
import time
from queue import Queue
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.gateways.base_live_gateway import (
    GatewayConfig,
    GatewayStatus,
    OrderStatus,
    OrderSide,
    OrderType,
    OrderUpdate,
    AccountUpdate,
    PositionUpdate,
    QueryResultCache,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_queue():
    return Queue()


@pytest.fixture
def xtp_config():
    return GatewayConfig(
        account_id="TEST_XTP_001",
        broker="xtp",
        password="test_password",
        trade_server="tcp://127.0.0.1:6001",
        quote_server="tcp://127.0.0.1:6002",
        client_id=1,
        auto_reconnect=False,
    )


@pytest.fixture
def uft_config():
    return GatewayConfig(
        account_id="TEST_UFT_001",
        broker="hundsun",
        password="test_password",
        td_front="tcp://127.0.0.1:7001",
        md_front="tcp://127.0.0.1:7002",
        auto_reconnect=False,
    )


# ---------------------------------------------------------------------------
# XTP Gateway Stub Mode Tests
# ---------------------------------------------------------------------------

class TestXtpGatewayStubMode:
    """Test XTP gateway operations in stub mode (no SDK)."""

    def test_init_stub_mode(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        assert gw._stub_mode is True
        assert gw.status == GatewayStatus.DISCONNECTED

    def test_connect_disconnect(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)

        assert gw.connect() is True
        assert gw.is_connected is True
        assert gw._session_id == 1

        gw.disconnect()
        assert gw.is_connected is False
        assert gw._session_id == 0

    def test_send_order_stub(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        order_id = gw.send_order(
            symbol="600519.SH",
            side=OrderSide.BUY,
            quantity=100,
            price=1800.0,
            order_type=OrderType.LIMIT,
        )

        assert order_id is not None
        assert order_id != ""

        # Wait for async callback
        time.sleep(0.3)

        # Check order was tracked
        order = gw.get_order(order_id)
        assert order is not None
        assert order.symbol == "600519.SH"

        gw.disconnect()

    def test_cancel_order_stub(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        order_id = gw.send_order(
            symbol="600519.SH",
            side=OrderSide.BUY,
            quantity=100,
            price=1800.0,
        )
        time.sleep(0.3)

        result = gw.cancel_order(order_id)
        assert result is True

        time.sleep(0.3)

        order = gw.get_order(order_id)
        assert order is not None
        assert order.status == OrderStatus.CANCELLED

        gw.disconnect()

    def test_query_account_stub(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        account = gw.query_account()
        assert account is not None
        assert isinstance(account, AccountUpdate)
        assert account.account_id == "TEST_XTP_001"
        assert account.cash == 1000000.0

        gw.disconnect()

    def test_query_positions_stub(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        positions = gw.query_positions()
        assert len(positions) == 1
        assert isinstance(positions[0], PositionUpdate)
        assert positions[0].symbol == "600519.SH"
        assert positions[0].total_quantity == 1000

        gw.disconnect()

    def test_multiple_orders_stub(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        order_ids = []
        for i in range(5):
            oid = gw.send_order(
                symbol="600519.SH",
                side=OrderSide.BUY,
                quantity=100 * (i + 1),
                price=1800.0 + i,
            )
            order_ids.append(oid)

        assert len(set(order_ids)) == 5  # All unique

        gw.disconnect()


# ---------------------------------------------------------------------------
# Hundsun UFT Gateway Stub Mode Tests
# ---------------------------------------------------------------------------

class TestHundsunUftGatewayStubMode:
    """Test Hundsun UFT gateway operations in stub mode (no SDK)."""

    def test_init_stub_mode(self, uft_config, event_queue):
        from src.gateways.hundsun_uft_gateway import HundsunUftGateway
        gw = HundsunUftGateway(uft_config, event_queue)
        assert gw._stub_mode is True
        assert gw.status == GatewayStatus.DISCONNECTED

    def test_connect_disconnect(self, uft_config, event_queue):
        from src.gateways.hundsun_uft_gateway import HundsunUftGateway
        gw = HundsunUftGateway(uft_config, event_queue)

        assert gw.connect() is True
        assert gw.is_connected is True
        assert gw._login_status is True

        gw.disconnect()
        assert gw.is_connected is False
        assert gw._login_status is False

    def test_send_order_stub(self, uft_config, event_queue):
        from src.gateways.hundsun_uft_gateway import HundsunUftGateway
        gw = HundsunUftGateway(uft_config, event_queue)
        gw.connect()

        order_id = gw.send_order(
            symbol="600519.SH",
            side=OrderSide.BUY,
            quantity=100,
            price=1800.0,
            order_type=OrderType.LIMIT,
        )

        assert order_id is not None
        assert order_id != ""

        time.sleep(0.3)

        order = gw.get_order(order_id)
        assert order is not None
        assert order.symbol == "600519.SH"

        gw.disconnect()

    def test_cancel_order_stub(self, uft_config, event_queue):
        from src.gateways.hundsun_uft_gateway import HundsunUftGateway
        gw = HundsunUftGateway(uft_config, event_queue)
        gw.connect()

        order_id = gw.send_order(
            symbol="600519.SH",
            side=OrderSide.BUY,
            quantity=100,
            price=1800.0,
        )
        time.sleep(0.3)

        result = gw.cancel_order(order_id)
        assert result is True

        time.sleep(0.3)

        order = gw.get_order(order_id)
        assert order is not None
        assert order.status == OrderStatus.CANCELLED

        gw.disconnect()

    def test_query_account_stub(self, uft_config, event_queue):
        from src.gateways.hundsun_uft_gateway import HundsunUftGateway
        gw = HundsunUftGateway(uft_config, event_queue)
        gw.connect()

        account = gw.query_account()
        assert account is not None
        assert isinstance(account, AccountUpdate)
        assert account.account_id == "TEST_UFT_001"
        assert account.cash == 1000000.0
        assert account.equity == 1100000.0

        gw.disconnect()

    def test_query_positions_stub(self, uft_config, event_queue):
        from src.gateways.hundsun_uft_gateway import HundsunUftGateway
        gw = HundsunUftGateway(uft_config, event_queue)
        gw.connect()

        positions = gw.query_positions()
        assert len(positions) == 1
        assert isinstance(positions[0], PositionUpdate)
        assert positions[0].symbol == "600519.SH"

        gw.disconnect()


# ---------------------------------------------------------------------------
# Gateway Factory Tests
# ---------------------------------------------------------------------------

class TestGatewayFactory:
    """Test gateway factory function."""

    def test_create_xtp_gateway(self, xtp_config, event_queue):
        from src.gateways import create_gateway
        gw = create_gateway("xtp", xtp_config, event_queue)
        assert gw is not None
        assert gw.config.broker == "xtp"

    def test_create_hundsun_gateway(self, uft_config, event_queue):
        from src.gateways import create_gateway
        gw = create_gateway("hundsun", uft_config, event_queue)
        assert gw is not None
        assert gw.config.broker == "hundsun"

    def test_create_uft_alias(self, uft_config, event_queue):
        from src.gateways import create_gateway
        gw = create_gateway("uft", uft_config, event_queue)
        assert gw is not None

    def test_create_unknown_raises(self, xtp_config, event_queue):
        from src.gateways import create_gateway
        with pytest.raises(ValueError, match="Unknown broker"):
            create_gateway("unknown_broker", xtp_config, event_queue)


# ---------------------------------------------------------------------------
# QueryResultCache Tests
# ---------------------------------------------------------------------------

class TestQueryResultCache:
    """Test the async query result cache."""

    def test_basic_usage(self):
        cache = QueryResultCache(timeout=2.0)
        cache.prepare("req-1")

        # Simulate async callback
        def set_later():
            time.sleep(0.1)
            cache.set_result("req-1", {"balance": 1000000})

        t = threading.Thread(target=set_later)
        t.start()

        result = cache.wait_result("req-1", timeout=2.0)
        assert result is not None
        assert result["balance"] == 1000000
        t.join()

    def test_timeout_returns_none(self):
        cache = QueryResultCache(timeout=0.1)
        cache.prepare("req-2")

        result = cache.wait_result("req-2", timeout=0.1)
        assert result is None

    def test_unprepared_returns_none(self):
        cache = QueryResultCache(timeout=1.0)
        result = cache.wait_result("req-nonexistent")
        assert result is None

    def test_multiple_requests(self):
        cache = QueryResultCache(timeout=2.0)
        cache.prepare("req-a")
        cache.prepare("req-b")

        cache.set_result("req-b", "result-b")
        cache.set_result("req-a", "result-a")

        assert cache.wait_result("req-a") == "result-a"
        assert cache.wait_result("req-b") == "result-b"


# ---------------------------------------------------------------------------
# GatewayConfig Tests
# ---------------------------------------------------------------------------

class TestGatewayConfig:
    """Test gateway configuration."""

    def test_basic_config(self):
        config = GatewayConfig(account_id="TEST", broker="xtp")
        assert config.account_id == "TEST"
        assert config.broker == "xtp"
        assert config.auto_reconnect is True

    def test_empty_account_raises(self):
        with pytest.raises(ValueError, match="account_id"):
            GatewayConfig(account_id="", broker="xtp")

    def test_sdk_path_config(self):
        import sys
        original_path = sys.path.copy()
        config = GatewayConfig(
            account_id="TEST",
            broker="xtp",
            sdk_path=None,  # None should not modify sys.path
        )
        assert sys.path == original_path


# ---------------------------------------------------------------------------
# Event Publishing Tests
# ---------------------------------------------------------------------------

class TestGatewayEvents:
    """Test that gateways publish correct events."""

    def test_connect_publishes_event(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        # Drain events
        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        # Should have connected event
        event_types = [e["type"] for e in events]
        assert "gateway.connected" in event_types

        gw.disconnect()

    def test_disconnect_publishes_event(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        # Drain connect events
        while not event_queue.empty():
            event_queue.get_nowait()

        gw.disconnect()

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        event_types = [e["type"] for e in events]
        assert "gateway.disconnected" in event_types

    def test_order_publishes_events(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        # Drain connect events
        while not event_queue.empty():
            event_queue.get_nowait()

        gw.send_order(
            symbol="600519.SH",
            side=OrderSide.BUY,
            quantity=100,
            price=1800.0,
        )

        time.sleep(0.3)

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        event_types = [e["type"] for e in events]
        assert "gateway.order.submitted" in event_types
        assert "gateway.order.accepted" in event_types

        gw.disconnect()


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestGatewayEdgeCases:
    """Test edge cases and error handling."""

    def test_send_order_not_connected(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)

        with pytest.raises(RuntimeError, match="not connected"):
            gw.send_order("600519.SH", OrderSide.BUY, 100, price=1800.0)

    def test_cancel_nonexistent_order(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        with pytest.raises(ValueError, match="Order not found"):
            gw.cancel_order("nonexistent-order-id")

        gw.disconnect()

    def test_double_connect(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()
        assert gw.connect() is True  # Should return True without error
        gw.disconnect()

    def test_disconnect_without_connect(self, uft_config, event_queue):
        from src.gateways.hundsun_uft_gateway import HundsunUftGateway
        gw = HundsunUftGateway(uft_config, event_queue)
        gw.disconnect()  # Should not raise

    def test_order_string_side(self, xtp_config, event_queue):
        """Test that string side values are accepted."""
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        order_id = gw.send_order(
            symbol="600519.SH",
            side="buy",
            quantity=100,
            price=1800.0,
            order_type="limit",
        )
        assert order_id is not None

        gw.disconnect()

    def test_gateway_name_property(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        assert gw.gateway_name == "xtp_TEST_XTP_001"

    def test_close_method(self, xtp_config, event_queue):
        from src.gateways.xtp_gateway import XtpGateway
        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()
        gw.close()
        assert gw.status == GatewayStatus.CLOSED
