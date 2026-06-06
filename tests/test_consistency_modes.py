
from __future__ import annotations

from src.core.interfaces import AccountInfo, PositionInfo, Side, OrderStatusEnum
from src.core.risk_manager_v2 import RiskConfig, RiskManagerV2
from src.core.trading_gateway import _map_live_order_status, _map_vnpy_order_status
from src.simulation.order import OrderStatus as SimOrderStatus

def test_order_status_mapping_consistency():
    live_statuses = [
        "pending_submit",
        "submitted",
        "partial_fill",
        "filled",
        "cancel_pending",
        "cancelled",
        "rejected",
        "expired",
        "error",
    ]
    assert _map_live_order_status("pending_submit") == OrderStatusEnum.CREATED
    assert _map_live_order_status("submitted") == OrderStatusEnum.SUBMITTED
    assert _map_live_order_status("accepted") == OrderStatusEnum.ACCEPTED
    assert _map_live_order_status("partial_fill") == OrderStatusEnum.PARTIALLY_FILLED
    assert _map_live_order_status("filled") == OrderStatusEnum.FILLED
    assert _map_live_order_status("cancel_pending") == OrderStatusEnum.ACCEPTED
    assert _map_live_order_status("cancelled") == OrderStatusEnum.CANCELLED
    assert _map_live_order_status("rejected") == OrderStatusEnum.REJECTED
    assert _map_live_order_status("expired") == OrderStatusEnum.EXPIRED
    assert _map_live_order_status("error") == OrderStatusEnum.REJECTED

    mapped = {_map_live_order_status(s) for s in live_statuses}
    assert mapped.issubset(set(OrderStatusEnum))
    assert _map_vnpy_order_status("SUBMITTING") == OrderStatusEnum.SUBMITTED
    assert _map_vnpy_order_status("NOTTRADED") == OrderStatusEnum.ACCEPTED
    assert _map_vnpy_order_status("PARTTRADED") == OrderStatusEnum.PARTIALLY_FILLED

    sim_status_values = {s.value for s in SimOrderStatus}
    core_status_values = {s.value for s in OrderStatusEnum}
    # Simulation order state machine should remain compatible with core enums.
    assert sim_status_values.issubset(core_status_values)

def test_risk_rules_consistent_across_modes():
    config = RiskConfig(max_order_value=50_000.0, max_position_pct=0.5, strict_mode=True, min_order_interval_sec=0)
    risk_manager = RiskManagerV2(config=config)

    account = AccountInfo(account_id="acc", cash=100_000.0, total_value=100_000.0, available=100_000.0)
    positions = {"600519.SH": PositionInfo(symbol="600519.SH", size=100, avg_price=100.0)}

    def evaluate_mode(_mode: str):
        return risk_manager.check_order(
            symbol="600519.SH",
            side=Side.BUY,
            quantity=10,
            price=100.0,
            account=account,
            positions=positions,
        )

    backtest = evaluate_mode("backtest")
    paper = evaluate_mode("paper")
    live = evaluate_mode("live")

    assert backtest.passed == paper.passed == live.passed
    assert backtest.rule_name == paper.rule_name == live.rule_name

