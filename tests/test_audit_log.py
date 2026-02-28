import json
import os
import tempfile

from src.core.audit import AuditLogger, RetentionPolicy


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


# ---------------------------------------------------------------------------
# Archival tests (V4.0-D)
# ---------------------------------------------------------------------------


def test_archive_creates_archived_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="u", action="a", resource="r", result="ok")
        archived = logger.archive()
        assert archived.endswith(".archived")
        assert os.path.exists(archived)
        assert not os.path.exists(path)


def test_archive_resets_chain():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="u", action="a", resource="r", result="ok")
        logger.archive()
        # New log should start fresh
        logger.log(actor="u", action="b", resource="r", result="ok")
        assert logger.verify() is True


def test_new_log_starts_after_archive():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="u", action="a", resource="r", result="ok")
        logger.archive()
        logger.log(actor="u", action="b", resource="r", result="ok")
        with open(path, "r") as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["prev_hash"] == ""


def test_list_archives():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)

        logger.log(actor="u", action="a", resource="r", result="ok")
        logger.archive()
        logger.log(actor="u", action="b", resource="r", result="ok")
        logger.archive()

        archives = logger.list_archives()
        assert len(archives) == 2
        assert all(a.endswith(".archived") for a in archives)


# ---------------------------------------------------------------------------
# Signature tests (V4.0-D)
# ---------------------------------------------------------------------------


def test_sign_produces_hmac():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="u", action="a", resource="r", result="ok")
        sig = logger.sign("my-secret")
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA256 hex


def test_verify_signature_correct_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="u", action="a", resource="r", result="ok")
        sig = logger.sign("secret-key")
        assert logger.verify_signature("secret-key", sig) is True


def test_verify_signature_wrong_key_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="u", action="a", resource="r", result="ok")
        sig = logger.sign("correct-key")
        assert logger.verify_signature("wrong-key", sig) is False


def test_tampered_log_fails_signature():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="u", action="a", resource="r", result="ok")
        sig = logger.sign("key")
        # Tamper
        with open(path, "a") as f:
            f.write("extra line\n")
        assert logger.verify_signature("key", sig) is False


# ---------------------------------------------------------------------------
# Retention policy tests (V4.0-D)
# ---------------------------------------------------------------------------


def test_apply_retention_max_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        # Create multiple archives
        for i in range(5):
            logger.log(actor="u", action=f"a{i}", resource="r", result="ok")
            logger.archive()
        archives_before = logger.list_archives()
        assert len(archives_before) == 5

        policy = RetentionPolicy(max_files=2)
        deleted = logger.apply_retention(policy)
        assert deleted == 3
        assert len(logger.list_archives()) == 2


def test_retention_preserves_recent():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        for i in range(3):
            logger.log(actor="u", action=f"a{i}", resource="r", result="ok")
            logger.archive()
        policy = RetentionPolicy(max_files=10)
        deleted = logger.apply_retention(policy)
        assert deleted == 0
        assert len(logger.list_archives()) == 3


# ---------------------------------------------------------------------------
# Compliance export tests (V4.0-D)
# ---------------------------------------------------------------------------


def test_export_by_date_range():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        logger.log(actor="u", action="a1", resource="r", result="ok")
        logger.log(actor="u", action="a2", resource="r", result="ok")
        events = logger.export_for_compliance()
        assert len(events) == 2
        assert events[0].action == "a1"


def test_export_empty_range():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/audit.log"
        logger = AuditLogger(path=path, chain_hash=True)
        events = logger.export_for_compliance()
        assert events == []
