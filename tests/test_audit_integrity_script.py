import json

from src.core.audit import AuditLogger
from scripts.audit_integrity_check import run_check


def test_audit_integrity_check_ok(tmp_path):
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(path=str(log_path), chain_hash=True)
    logger.log(actor="u1", action="order.submit", resource="gateway", result="ok", details={"x": 1})

    result = run_check(str(log_path), max_age_minutes=5)
    assert result["status"] == "ok"
    assert result["chain_ok"] is True


def test_audit_integrity_check_detects_tamper(tmp_path):
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(path=str(log_path), chain_hash=True)
    logger.log(actor="u1", action="a", resource="r", result="ok", details={"x": 1})
    logger.log(actor="u1", action="b", resource="r", result="ok", details={"x": 2})

    lines = log_path.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["details"]["x"] = 999
    lines[1] = json.dumps(second, ensure_ascii=False)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = run_check(str(log_path), max_age_minutes=5)
    assert result["status"] == "failed"
    assert result["chain_ok"] is False
