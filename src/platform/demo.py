"""
Deterministic platform feature demos.

The demo helpers intentionally operate on a caller-provided gateway service so
API endpoints can run them against an isolated paper gateway without touching
the active trading session.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class DemoExecutionError(RuntimeError):
    """Raised when a deterministic demo workflow cannot complete."""


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    return value


def _record_step(
    steps: List[Dict[str, Any]], name: str, details: Optional[Dict[str, Any]] = None
) -> None:
    steps.append(
        {
            "name": name,
            "status": "passed",
            "details": _to_jsonable(details or {}),
        }
    )


def _find_order(orders: List[Dict[str, Any]], order_id: str) -> Dict[str, Any]:
    for order in orders:
        if order.get("order_id") == order_id:
            return order
    raise DemoExecutionError(f"order not found in snapshot: {order_id}")


def _summarize_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    status = snapshot.get("status") or {}
    account = snapshot.get("account") or {}
    positions = snapshot.get("positions") or []
    orders = snapshot.get("orders") or []
    trades = snapshot.get("trades") or []
    open_statuses = {"pending", "submitted", "partial"}

    return {
        "gateway_connected": bool(status.get("connected")),
        "mode": status.get("mode", "-"),
        "broker": status.get("broker", "-"),
        "account_id": account.get("account_id", "-"),
        "cash": account.get("cash", 0.0),
        "total_value": account.get("total_value", 0.0),
        "unrealized_pnl": account.get("unrealized_pnl", 0.0),
        "positions": len(positions),
        "orders": len(orders),
        "open_orders": sum(
            1 for order in orders if order.get("status") in open_statuses
        ),
        "filled_orders": sum(1 for order in orders if order.get("status") == "filled"),
        "cancelled_orders": sum(
            1 for order in orders if order.get("status") == "cancelled"
        ),
        "trades": len(trades),
    }


def run_paper_trading_demo(
    gateway_service: Any,
    *,
    queue: Any = None,
    monitor_service: Any = None,
    metrics: Any = None,
    symbol: str = "600519.SH",
    quantity: float = 100.0,
    entry_price: float = 100.0,
    entry_fill_price: float = 99.5,
    mark_price: float = 101.2,
    exit_limit_price: float = 120.0,
    initial_cash: float = 1_000_000.0,
    commission_rate: float = 0.0003,
    slippage: float = 0.0001,
    limit: int = 20,
) -> Dict[str, Any]:
    """Run an isolated paper-trading workflow and return a display-ready report.

    The workflow covers the user-facing console path: connect, submit order,
    match a paper fill through a price update, submit and cancel an order, and
    collect the final gateway/monitor snapshot.
    """
    if not symbol.strip():
        raise ValueError("symbol is required")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if (
        min(entry_price, entry_fill_price, mark_price, exit_limit_price, initial_cash)
        <= 0
    ):
        raise ValueError("prices and initial_cash must be positive")

    steps: List[Dict[str, Any]] = []
    connect_payload = {
        "mode": "paper",
        "broker": "paper",
        "account": "demo-paper",
        "initial_cash": initial_cash,
        "commission_rate": commission_rate,
        "slippage": slippage,
        "enable_risk_check": True,
    }
    status = gateway_service.connect(connect_payload)
    if not status.get("connected"):
        raise DemoExecutionError(f"paper gateway failed to connect: {status}")
    _record_step(steps, "connect_gateway", {"status": status})

    buy_order = gateway_service.submit_order(
        {
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "price": entry_price,
            "order_type": "limit",
        }
    )
    buy_order_id = str(buy_order["order_id"])
    _record_step(
        steps,
        "submit_buy_limit",
        {"order_id": buy_order_id, "limit_price": entry_price},
    )

    gateway_service.update_price({"symbol": symbol, "price": entry_fill_price})
    orders_after_fill = gateway_service.orders(symbol=symbol)
    filled_order = _find_order(_to_jsonable(orders_after_fill), buy_order_id)
    if filled_order.get("status") != "filled":
        raise DemoExecutionError(f"buy order did not fill: {filled_order}")
    _record_step(
        steps,
        "match_buy_with_paper_price",
        {
            "order_id": buy_order_id,
            "paper_price": entry_fill_price,
            "filled_price": filled_order.get("avg_fill_price"),
        },
    )

    sell_order = gateway_service.submit_order(
        {
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "price": exit_limit_price,
            "order_type": "limit",
        }
    )
    sell_order_id = str(sell_order["order_id"])
    _record_step(
        steps,
        "submit_exit_limit",
        {"order_id": sell_order_id, "limit_price": exit_limit_price},
    )

    cancel_result = gateway_service.cancel_order({"order_id": sell_order_id})
    if not cancel_result.get("cancelled"):
        raise DemoExecutionError(f"exit order was not cancelled: {cancel_result}")
    _record_step(
        steps, "cancel_exit_limit", {"order_id": sell_order_id, "cancelled": True}
    )

    gateway_service.update_price({"symbol": symbol, "price": mark_price})
    _record_step(steps, "mark_to_market", {"symbol": symbol, "price": mark_price})

    snapshot = _to_jsonable(
        gateway_service.snapshot(orders_limit=limit, trades_limit=limit)
    )
    summary = _summarize_snapshot(snapshot)
    _record_step(steps, "collect_gateway_snapshot", summary)

    monitor = None
    if queue is not None and monitor_service is not None and metrics is not None:
        monitor = _to_jsonable(
            monitor_service.summary(
                queue=queue,
                gateway_service=gateway_service,
                metrics=metrics,
                jobs_limit=min(limit, 50),
                orders_limit=limit,
                trades_limit=limit,
            )
        )
        _record_step(
            steps, "collect_monitor_summary", {"status": monitor.get("status")}
        )

    return {
        "ok": True,
        "name": "paper_trading_console",
        "description": "Paper gateway connect/order/fill/cancel/monitor demonstration",
        "input": {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "entry_fill_price": entry_fill_price,
            "mark_price": mark_price,
            "exit_limit_price": exit_limit_price,
        },
        "summary": summary,
        "steps": steps,
        "snapshot": snapshot,
        "monitor": monitor,
    }


def write_demo_report(report: Dict[str, Any], output_path: str | Path) -> Path:
    """Write a demo report as UTF-8 JSON and return the resolved path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path.resolve()


__all__ = ["DemoExecutionError", "run_paper_trading_demo", "write_demo_report"]
