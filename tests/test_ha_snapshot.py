import tempfile

from src.core.ha import SnapshotStore
from src.core.order_manager import OrderManager
from src.core.interfaces import Side, OrderTypeEnum


def test_snapshot_store_roundtrip():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = SnapshotStore(root=tmpdir, retention=2)
        manager = OrderManager()
        order = manager.create_order("AAA", Side.BUY, 10, price=1.0, order_type=OrderTypeEnum.LIMIT)
        manager.on_order_fill(order.order_id, fill_price=1.0, fill_quantity=10, trade_id="TRD-1")

        snapshot = manager.snapshot_state()
        path = store.save("oms", snapshot)
        assert path.endswith(".json")

        restored = OrderManager()
        payload = store.load_latest("oms")
        restored.restore_state(payload)
        assert len(restored.get_order_history()) == 1
        assert len(restored.get_trades()) == 1
