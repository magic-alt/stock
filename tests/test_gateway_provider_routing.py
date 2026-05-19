from __future__ import annotations

from types import SimpleNamespace

import pytest


class _Token:
    def __init__(self, name: str):
        self.name = name
        self.value = name


class _Direction:
    LONG = _Token("LONG")
    SHORT = _Token("SHORT")


class _OrderType:
    LIMIT = _Token("LIMIT")
    MARKET = _Token("MARKET")


class _Offset:
    OPEN = _Token("OPEN")


class _Exchange:
    SSE = _Token("SSE")
    SZSE = _Token("SZSE")


class _Status:
    NOTTRADED = _Token("NOTTRADED")


class _OrderRequest:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _CancelRequest:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _EventEngine:
    pass


class _Gateway:
    pass


class _MainEngine:
    def __init__(self, event_engine):
        self.event_engine = event_engine
        self.gateway_cls = None
        self.connected_setting = None
        self.connected_gateway = None
        self.last_order_request = None

    def add_gateway(self, gateway_cls):
        self.gateway_cls = gateway_cls

    def connect(self, setting, gateway_name):
        self.connected_setting = setting
        self.connected_gateway = gateway_name

    def send_order(self, request, gateway_name):
        self.last_order_request = request
        self.last_order_gateway = gateway_name
        return f"{gateway_name}.1"

    def cancel_order(self, request, gateway_name):
        self.last_cancel_request = request
        self.last_cancel_gateway = gateway_name

    def get_all_accounts(self):
        return [SimpleNamespace(accountid="ACC1", balance=1000, available=900, frozen=100)]

    def get_all_positions(self):
        return [SimpleNamespace(vt_symbol="600519.SSE", volume=100, price=12.5, pnl=50)]

    def get_all_active_orders(self):
        return [
            SimpleNamespace(
                vt_orderid="QMT.1",
                vt_symbol="600519.SSE",
                direction=_Direction.LONG,
                type=_OrderType.LIMIT,
                price=12.5,
                volume=100,
                traded=0,
                status=_Status.NOTTRADED,
            )
        ]

    def get_all_trades(self):
        return [
            SimpleNamespace(
                vt_tradeid="TRADE.1",
                vt_orderid="QMT.1",
                vt_symbol="600519.SSE",
                direction=_Direction.LONG,
                price=12.5,
                volume=100,
            )
        ]


def _install_fake_vnpy(monkeypatch):
    import src.core.trading_gateway as trading_gateway

    modules = {
        "vnpy.event": SimpleNamespace(EventEngine=_EventEngine),
        "vnpy.trader.engine": SimpleNamespace(MainEngine=_MainEngine),
        "vnpy.trader.constant": SimpleNamespace(
            Direction=_Direction,
            OrderType=_OrderType,
            Offset=_Offset,
            Exchange=_Exchange,
        ),
        "vnpy.trader.object": SimpleNamespace(OrderRequest=_OrderRequest, CancelRequest=_CancelRequest),
        "custom.qmt": SimpleNamespace(QmtGateway=_Gateway),
    }

    def fake_import_module(name: str):
        if name in modules:
            return modules[name]
        raise ImportError(name)

    monkeypatch.setattr(trading_gateway.importlib, "import_module", fake_import_module)


def test_qmt_defaults_to_self_built_xtquant_adapter():
    from src.core.trading_gateway import BrokerType, GatewayConfig, TradingGateway, TradingMode

    gateway = TradingGateway(GatewayConfig(mode=TradingMode.LIVE, broker=BrokerType.QMT))

    assert gateway._adapter.__class__.__name__ == "XtQuantAdapter"


def test_qmt_can_route_to_vnpy_provider_without_importing_until_connect():
    from src.core.trading_gateway import BrokerType, GatewayConfig, TradingGateway, TradingMode

    gateway = TradingGateway(
        GatewayConfig(
            mode=TradingMode.LIVE,
            broker=BrokerType.QMT,
            gateway_provider="third_party",
            broker_options={"vnpy_gateway_class": "custom.qmt.QmtGateway"},
        )
    )

    assert gateway._adapter.__class__.__name__ == "VnpyGatewayAdapter"
    assert gateway.config.vnpy_gateway == "QMT"


def test_vnpy_adapter_reports_missing_dependency(monkeypatch):
    import src.core.trading_gateway as trading_gateway
    from src.core.trading_gateway import BrokerType, GatewayConfig, TradingMode, VnpyGatewayAdapter

    original_import_module = trading_gateway.importlib.import_module

    def missing_vnpy(name: str):
        if name.startswith("vnpy"):
            raise ImportError(name)
        return original_import_module(name)

    monkeypatch.setattr(trading_gateway.importlib, "import_module", missing_vnpy)
    adapter = VnpyGatewayAdapter(GatewayConfig(mode=TradingMode.LIVE, broker=BrokerType.VNPY, vnpy_gateway="CTP"))

    with pytest.raises(RuntimeError, match="vn.py is not installed"):
        adapter.connect()


def test_vnpy_adapter_maps_order_and_queries(monkeypatch):
    from src.core.interfaces import OrderStatusEnum, Side
    from src.core.trading_gateway import BrokerType, GatewayConfig, TradingMode, VnpyGatewayAdapter

    _install_fake_vnpy(monkeypatch)
    adapter = VnpyGatewayAdapter(
        GatewayConfig(
            mode=TradingMode.LIVE,
            broker=BrokerType.VNPY_QMT,
            vnpy_setting={"account": "ACC1"},
            broker_options={"vnpy_gateway_class": "custom.qmt.QmtGateway"},
        )
    )

    assert adapter.connect() is True
    order_id = adapter.submit_order("600519.SH", Side.BUY, 100, price=12.5)

    request = adapter._main_engine.last_order_request
    assert order_id == "QMT.1"
    assert request.symbol == "600519"
    assert request.exchange.name == "SSE"
    assert request.direction.name == "LONG"
    assert request.type.name == "LIMIT"
    assert adapter.query_account().available == 900
    assert adapter.query_positions()["600519.SSE"].size == 100
    assert adapter.query_orders()[0].status == OrderStatusEnum.ACCEPTED
    assert adapter.query_trades(limit=1)[0].order_id == "QMT.1"


def test_gateway_service_build_config_preserves_provider_fields():
    from src.core.trading_gateway import BrokerType
    from src.platform.api_server import GatewayService

    config = GatewayService()._build_config(
        {
            "mode": "live",
            "broker": "qmt",
            "gateway_provider": "third_party",
            "qmt_provider": "vnpy_qmt",
            "vnpy_gateway": "QMT",
            "vnpy_setting": {"account": "ACC1"},
            "sdk_path": "C:/sdk",
            "sdk_log_path": "C:/logs",
            "broker_options": {"vnpy_gateway_class": "custom.qmt.QmtGateway"},
        }
    )

    assert config.broker == BrokerType.QMT
    assert config.gateway_provider == "third_party"
    assert config.qmt_provider == "vnpy_qmt"
    assert config.vnpy_gateway == "QMT"
    assert config.vnpy_setting == {"account": "ACC1"}
    assert config.sdk_path == "C:/sdk"
    assert config.sdk_log_path == "C:/logs"
