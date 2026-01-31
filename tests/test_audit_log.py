import json
import tempfile

from src.core.audit import AuditLogger


def test_audit_log_hash_chain():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="user1", action="order.create", resource="order:1", result="ok", details={"symbol": "AAA"})
        logger.log(actor="user1", action="order.submit", resource="order:1", result="ok", details={"price": 10})

        assert logger.verify() is True

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2
        record = json.loads(lines[0])
        assert record["action"] == "order.create"
