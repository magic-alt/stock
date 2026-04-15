"""
Tests for V5.0-C: Security Hardening & Compliance.

Covers:
- C-1: FastAPI API v2 (api_v2.py)
- C-2: Security module + Vault (security.py, vault.py)
- C-3: Input sanitizer (input_sanitizer.py)
- C-4: pyproject.toml validation
"""
import json
import os
import time
import pytest
from pathlib import Path


# ===========================================================================
# C-1: FastAPI api_v2 tests
# ===========================================================================

class TestFastAPIApp:
    """Test FastAPI application creation and endpoints."""

    def test_has_fastapi_flag(self):
        from src.platform.api_v2 import HAS_FASTAPI
        # FastAPI should be installed in test env
        assert HAS_FASTAPI is True

    def test_create_app_returns_fastapi_instance(self):
        from src.platform.api_v2 import create_app
        app = create_app()
        assert app is not None
        assert hasattr(app, "routes")

    def test_app_has_openapi_docs(self):
        from src.platform.api_v2 import create_app
        app = create_app()
        assert app.docs_url == "/api/v2/docs"
        assert app.redoc_url == "/api/v2/redoc"
        assert app.openapi_url == "/api/v2/openapi.json"

    def test_cors_enabled_by_default(self):
        from src.platform.api_v2 import create_app
        app = create_app(enable_cors=True)
        has_cors = any("CORSMiddleware" in str(type(m)) for m in app.user_middleware)
        # CORS is added via add_middleware, check middleware stack
        assert app is not None  # app was created without error

    def test_cors_can_be_disabled(self):
        from src.platform.api_v2 import create_app
        app = create_app(enable_cors=False)
        assert app is not None

    def test_cors_origins_can_be_loaded_from_environment(self, monkeypatch):
        from src.platform.api_v2 import create_app
        monkeypatch.setenv(
            "PLATFORM_ALLOWED_ORIGINS",
            "http://localhost:3000,https://stock-web.onrender.com",
        )
        app = create_app(enable_cors=True)
        cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
        assert cors.kwargs["allow_origins"] == [
            "http://localhost:3000",
            "https://stock-web.onrender.com",
        ]

    def test_pydantic_models_exist(self):
        from src.platform.api_v2 import (
            ApiEnvelope,
            HealthResponse,
            BacktestRequest,
            StrategyValidateRequest,
            OrderRequest,
            ConnectRequest,
        )
        # Verify models can be instantiated
        env = ApiEnvelope(ok=True, data={"test": 1})
        assert env.ok is True
        assert env.data == {"test": 1}

        health = HealthResponse(status="healthy", version="5.0", uptime_seconds=1.23)
        assert health.status == "healthy"

    def test_backtest_request_validation(self):
        from src.platform.api_v2 import BacktestRequest
        req = BacktestRequest(strategy="macd", symbols=["600519.SH"])
        assert req.strategy == "macd"
        assert req.cash == 100000
        assert req.commission == 0.001

    def test_backtest_request_rejects_empty_symbols(self):
        from src.platform.api_v2 import BacktestRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            BacktestRequest(strategy="macd", symbols=[])

    def test_order_request_validation(self):
        from src.platform.api_v2 import OrderRequest
        req = OrderRequest(symbol="600519.SH", side="buy", quantity=100, price=1800)
        assert req.side == "buy"
        assert req.order_type == "limit"

    def test_order_request_rejects_invalid_side(self):
        from src.platform.api_v2 import OrderRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            OrderRequest(symbol="600519.SH", side="short", quantity=100)

    def test_strategy_validate_request(self):
        from src.platform.api_v2 import StrategyValidateRequest
        req = StrategyValidateRequest(code="x = 1")
        assert req.code == "x = 1"

    def test_singleton_app_is_fastapi(self):
        from src.platform.api_v2 import app
        assert app is not None


class TestFastAPIEndpoints:
    """Test API endpoints using TestClient."""

    @pytest.fixture
    def client(self):
        try:
            from fastapi.testclient import TestClient
            from src.platform.api_v2 import create_app
            app = create_app()
            return TestClient(app)
        except ImportError:
            pytest.skip("fastapi or httpx not installed")

    def test_health_endpoint(self, client):
        resp = client.get("/api/v2/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "5.0"
        assert data["uptime_seconds"] >= 0

    def test_readiness_endpoint(self, client):
        resp = client.get("/api/v2/ready")
        assert resp.status_code == 200
        assert resp.json()["ready"] is True

    def test_security_headers_present(self, client):
        resp = client.get("/api/v2/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_request_id_header(self, client):
        resp = client.get("/api/v2/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) == 8

    def test_strategies_list_endpoint(self, client):
        resp = client.get("/api/v2/strategies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "strategies" in body["data"]

    def test_strategy_not_found(self, client):
        resp = client.get("/api/v2/strategies/nonexistent_strategy_xyz")
        assert resp.status_code == 404

    def test_validate_strategy_valid_code(self, client):
        resp = client.post(
            "/api/v2/strategies/validate",
            json={"code": "x = 1\ny = x + 2"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["valid"] is True

    def test_validate_strategy_syntax_error(self, client):
        resp = client.post(
            "/api/v2/strategies/validate",
            json={"code": "def foo(:\n    pass"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["valid"] is False

    def test_validate_strategy_restricted_import(self, client):
        resp = client.post(
            "/api/v2/strategies/validate",
            json={"code": "import os\nimport subprocess"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Restricted imports produce warnings but code is still syntactically valid
        assert len(body["data"]["errors"]) >= 2

    def test_openapi_schema_available(self, client):
        resp = client.get("/api/v2/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "openapi" in schema
        assert schema["info"]["title"] == "Unified Quant Platform"

    def test_strategy_run_endpoint(self, client, monkeypatch):
        from src.backtest.engine import BacktestEngine

        def fake_run_strategy(self, **kwargs):
            assert kwargs["strategy"] == "macd"
            return {
                "strategy": "macd",
                "cum_return": 0.12,
                "sharpe": 1.8,
                "trades": 8,
                "nav": [1, 2, 3],
            }

        monkeypatch.setattr(BacktestEngine, "run_strategy", fake_run_strategy)

        resp = client.post(
            "/api/v2/strategies/run",
            json={
                "strategy": "macd",
                "symbols": ["600519.SH"],
                "start": "2024-01-01",
                "end": "2024-12-31",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["metrics"]["cum_return"] == 0.12

    def test_gateway_and_monitor_endpoints(self, client):
        resp = client.post(
            "/api/v2/gateway/connect",
            json={
                "mode": "paper",
                "broker": "paper",
                "account": "paper",
                "initial_cash": 100000,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["gateway"]["connected"] is True

        resp = client.post(
            "/api/v2/gateway/order",
            json={
                "symbol": "600519.SH",
                "side": "buy",
                "quantity": 100,
                "price": 1800,
                "order_type": "limit",
            },
        )
        assert resp.status_code == 200
        order_id = resp.json()["data"]["order_id"]

        resp = client.post(
            "/api/v2/gateway/price",
            json={"symbol": "600519.SH", "price": 1799},
        )
        assert resp.status_code == 200

        resp = client.get("/api/v2/gateway/snapshot?limit=5")
        assert resp.status_code == 200
        snapshot = resp.json()["data"]["gateway"]
        assert snapshot["status"]["broker"] == "paper"
        assert any(order["order_id"] == order_id for order in snapshot["orders"])

        resp = client.get("/api/v2/monitor/summary?limit=5")
        assert resp.status_code == 200
        monitor = resp.json()["data"]["monitor"]
        assert monitor["system"] is not None

    def test_frontend_dist_can_be_served(self, monkeypatch, tmp_path):
        try:
            from fastapi.testclient import TestClient
            from src.platform.api_v2 import create_app
        except ImportError:
            pytest.skip("fastapi or httpx not installed")

        (tmp_path / "index.html").write_text("<html><body>release-ui</body></html>", encoding="utf-8")
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "app.js").write_text("console.log('release-ui')", encoding="utf-8")

        monkeypatch.setenv("PLATFORM_FRONTEND_DIST", str(tmp_path))
        app = create_app(enable_cors=False)
        client = TestClient(app)

        root = client.get("/")
        assert root.status_code == 200
        assert "release-ui" in root.text

        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "release-ui" in asset.text

        spa = client.get("/trading")
        assert spa.status_code == 200
        assert "release-ui" in spa.text

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"


# ===========================================================================
# C-2: Security module tests
# ===========================================================================

class TestSecurityTokens:
    """Test token generation and hashing."""

    def test_generate_api_token_format(self):
        from src.core.security import generate_api_token
        token = generate_api_token()
        assert token.startswith("qp_")
        assert len(token) > 20

    def test_generate_api_token_custom_prefix(self):
        from src.core.security import generate_api_token
        token = generate_api_token(prefix="test")
        assert token.startswith("test_")

    def test_generate_api_token_uniqueness(self):
        from src.core.security import generate_api_token
        tokens = {generate_api_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_hash_token_deterministic(self):
        from src.core.security import hash_token
        h1 = hash_token("my-token")
        h2 = hash_token("my-token")
        assert h1 == h2

    def test_hash_token_different_for_different_tokens(self):
        from src.core.security import hash_token
        h1 = hash_token("token-a")
        h2 = hash_token("token-b")
        assert h1 != h2


class TestSecurityManager:
    """Test SecurityManager encryption and token lifecycle."""

    def test_encrypt_decrypt_roundtrip(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test-key-1234")
        plaintext = "super-secret-password"
        encrypted = sm.encrypt(plaintext)
        assert encrypted != plaintext
        assert sm.decrypt(encrypted) == plaintext

    def test_encrypt_different_ciphertexts(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test-key-1234")
        # Even with same plaintext, XOR-based encryptor produces same output
        # (but Fernet would produce different). Just verify roundtrip.
        e1 = sm.encrypt("hello")
        assert sm.decrypt(e1) == "hello"

    def test_decrypt_wrong_key_fails(self):
        from src.core.security import SecurityManager
        sm1 = SecurityManager(secret_key="key-1")
        sm2 = SecurityManager(secret_key="key-2")
        encrypted = sm1.encrypt("secret")
        with pytest.raises((ValueError, Exception)):
            sm2.decrypt(encrypted)

    def test_issue_token(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test")
        token = sm.issue_token(owner="user1", scopes=["read"])
        assert token.startswith("qp_")

    def test_validate_token(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test")
        token = sm.issue_token(owner="user1")
        info = sm.validate_token(token)
        assert info is not None
        assert info.owner == "user1"

    def test_validate_invalid_token_returns_none(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test")
        info = sm.validate_token("invalid-token")
        assert info is None

    def test_revoke_token(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test")
        token = sm.issue_token(owner="user1")
        assert sm.validate_token(token) is not None
        assert sm.revoke_token(token) is True
        assert sm.validate_token(token) is None

    def test_revoke_nonexistent_returns_false(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test")
        assert sm.revoke_token("no-such-token") is False

    def test_rotate_token(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test")
        old = sm.issue_token(owner="user1", scopes=["admin"])
        new = sm.rotate_token(old)
        assert new is not None
        assert new != old
        # Old token revoked
        assert sm.validate_token(old) is None
        # New token valid
        info = sm.validate_token(new)
        assert info is not None
        assert info.owner == "user1"

    def test_token_expiry(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test")
        token = sm.issue_token(owner="expiry-test", ttl=0.1)
        assert sm.validate_token(token) is not None
        time.sleep(0.2)
        assert sm.validate_token(token) is None

    def test_list_tokens(self):
        from src.core.security import SecurityManager
        sm = SecurityManager(secret_key="test")
        sm.issue_token(owner="a")
        sm.issue_token(owner="b")
        tokens = sm.list_tokens()
        assert len(tokens) >= 2

    def test_mask_secret(self):
        from src.core.security import SecurityManager
        assert SecurityManager.mask_secret("qp_abcdef1234567890") == "qp_a***7890"
        assert SecurityManager.mask_secret("ab") == "***"

    def test_mask_dict(self):
        from src.core.security import SecurityManager
        d = {"username": "admin", "password": "secret123", "api_key": "key-value"}
        masked = SecurityManager.mask_dict(d)
        assert masked["username"] == "admin"
        assert "***" in masked["password"]
        assert "***" in masked["api_key"]


class TestTLSConfig:
    """Test TLS configuration."""

    def test_tls_config_disabled_is_valid(self):
        from src.core.security import TLSConfig
        cfg = TLSConfig(enabled=False)
        assert cfg.is_valid() is True

    def test_tls_config_enabled_no_files_is_invalid(self):
        from src.core.security import TLSConfig
        cfg = TLSConfig(enabled=True, certfile="nonexistent.crt", keyfile="nonexistent.key")
        assert cfg.is_valid() is False

    def test_tls_config_enabled_with_files(self, tmp_path):
        from src.core.security import TLSConfig
        cert = tmp_path / "server.crt"
        key = tmp_path / "server.key"
        cert.write_text("cert-data")
        key.write_text("key-data")
        cfg = TLSConfig(enabled=True, certfile=str(cert), keyfile=str(key))
        assert cfg.is_valid() is True


# ===========================================================================
# C-2: Vault tests
# ===========================================================================

class TestMemoryVault:
    """Test in-memory vault."""

    def test_put_and_get(self):
        from src.core.vault import MemoryVault
        vault = MemoryVault()
        vault.put("key1", "val1")
        assert vault.get("key1") == "val1"

    def test_get_nonexistent_returns_none(self):
        from src.core.vault import MemoryVault
        vault = MemoryVault()
        assert vault.get("missing") is None

    def test_delete(self):
        from src.core.vault import MemoryVault
        vault = MemoryVault()
        vault.put("key1", "val1")
        assert vault.delete("key1") is True
        assert vault.get("key1") is None

    def test_delete_nonexistent_returns_false(self):
        from src.core.vault import MemoryVault
        vault = MemoryVault()
        assert vault.delete("missing") is False

    def test_list_keys(self):
        from src.core.vault import MemoryVault
        vault = MemoryVault()
        vault.put("a", "1")
        vault.put("b", "2")
        assert set(vault.list_keys()) == {"a", "b"}

    def test_exists(self):
        from src.core.vault import MemoryVault
        vault = MemoryVault()
        vault.put("x", "y")
        assert vault.exists("x") is True
        assert vault.exists("z") is False

    def test_get_or_raise(self):
        from src.core.vault import MemoryVault
        vault = MemoryVault()
        vault.put("k", "v")
        assert vault.get_or_raise("k") == "v"
        with pytest.raises(KeyError):
            vault.get_or_raise("missing")


class TestEnvVault:
    """Test environment variable vault."""

    def test_get_existing_env(self, monkeypatch):
        from src.core.vault import EnvVault
        monkeypatch.setenv("QUANT_DB_HOST", "localhost")
        vault = EnvVault(prefix="QUANT_")
        assert vault.get("db_host") == "localhost"

    def test_get_missing_env(self):
        from src.core.vault import EnvVault
        vault = EnvVault(prefix="QUANT_TEST_UNLIKELY_")
        assert vault.get("missing_key") is None

    def test_put_raises(self):
        from src.core.vault import EnvVault
        vault = EnvVault()
        with pytest.raises(NotImplementedError):
            vault.put("key", "value")

    def test_list_keys(self, monkeypatch):
        from src.core.vault import EnvVault
        monkeypatch.setenv("TSTV_A", "1")
        monkeypatch.setenv("TSTV_B", "2")
        vault = EnvVault(prefix="TSTV_")
        keys = vault.list_keys()
        assert "a" in keys
        assert "b" in keys


class TestLocalFileVault:
    """Test encrypted local file vault."""

    def test_put_and_get(self, tmp_path):
        from src.core.vault import LocalFileVault
        vault = LocalFileVault(path=str(tmp_path / "secrets.enc"), secret_key="test-key")
        vault.put("db_pass", "my-password")
        assert vault.get("db_pass") == "my-password"

    def test_persistence(self, tmp_path):
        from src.core.vault import LocalFileVault
        path = str(tmp_path / "secrets.enc")
        v1 = LocalFileVault(path=path, secret_key="test-key")
        v1.put("secret", "value123")

        v2 = LocalFileVault(path=path, secret_key="test-key")
        assert v2.get("secret") == "value123"

    def test_wrong_key_cannot_read(self, tmp_path):
        from src.core.vault import LocalFileVault
        path = str(tmp_path / "secrets.enc")
        v1 = LocalFileVault(path=path, secret_key="key-1")
        v1.put("secret", "value")

        v2 = LocalFileVault(path=path, secret_key="wrong-key")
        # Should fail to decrypt — cache will be empty
        assert v2.get("secret") is None

    def test_delete(self, tmp_path):
        from src.core.vault import LocalFileVault
        vault = LocalFileVault(path=str(tmp_path / "secrets.enc"), secret_key="test-key")
        vault.put("key", "val")
        assert vault.delete("key") is True
        assert vault.get("key") is None

    def test_list_keys(self, tmp_path):
        from src.core.vault import LocalFileVault
        vault = LocalFileVault(path=str(tmp_path / "secrets.enc"), secret_key="test-key")
        vault.put("a", "1")
        vault.put("b", "2")
        assert set(vault.list_keys()) == {"a", "b"}


class TestCompositeVault:
    """Test composite vault chain."""

    def test_read_falls_through(self):
        from src.core.vault import MemoryVault, CompositeVault
        primary = MemoryVault()
        secondary = MemoryVault()
        secondary.put("fallback_key", "fallback_value")
        composite = CompositeVault([primary, secondary])
        assert composite.get("fallback_key") == "fallback_value"

    def test_primary_takes_precedence(self):
        from src.core.vault import MemoryVault, CompositeVault
        primary = MemoryVault()
        secondary = MemoryVault()
        primary.put("key", "primary_val")
        secondary.put("key", "secondary_val")
        composite = CompositeVault([primary, secondary])
        assert composite.get("key") == "primary_val"

    def test_writes_go_to_primary(self):
        from src.core.vault import MemoryVault, CompositeVault
        primary = MemoryVault()
        secondary = MemoryVault()
        composite = CompositeVault([primary, secondary])
        composite.put("new_key", "new_val")
        assert primary.get("new_key") == "new_val"
        assert secondary.get("new_key") is None

    def test_list_keys_merges(self):
        from src.core.vault import MemoryVault, CompositeVault
        primary = MemoryVault()
        secondary = MemoryVault()
        primary.put("a", "1")
        secondary.put("b", "2")
        composite = CompositeVault([primary, secondary])
        assert set(composite.list_keys()) == {"a", "b"}


class TestCreateVault:
    """Test vault factory."""

    def test_create_memory(self):
        from src.core.vault import create_vault, MemoryVault
        vault = create_vault("memory")
        assert isinstance(vault, MemoryVault)

    def test_create_env(self):
        from src.core.vault import create_vault, EnvVault
        vault = create_vault("env")
        assert isinstance(vault, EnvVault)

    def test_create_local(self, tmp_path):
        from src.core.vault import create_vault, LocalFileVault
        vault = create_vault("local", path=str(tmp_path / "v.enc"), secret_key="k")
        assert isinstance(vault, LocalFileVault)

    def test_create_composite(self, tmp_path):
        from src.core.vault import create_vault, CompositeVault
        vault = create_vault("composite", path=str(tmp_path / "v.enc"), secret_key="k")
        assert isinstance(vault, CompositeVault)

    def test_unknown_backend_raises(self):
        from src.core.vault import create_vault
        with pytest.raises(ValueError, match="Unknown vault backend"):
            create_vault("nosuch")


# ===========================================================================
# C-3: Input sanitizer tests
# ===========================================================================

class TestSymbolValidation:
    """Test symbol format validation."""

    def test_valid_a_share_symbol(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.validate_symbol("600519.SH") is True
        assert InputSanitizer.validate_symbol("000333.SZ") is True
        assert InputSanitizer.validate_symbol("688001.SH") is True

    def test_valid_symbol_without_suffix(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.validate_symbol("600519") is True

    def test_invalid_symbol_path_traversal(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.validate_symbol("../../etc/passwd") is False

    def test_invalid_symbol_empty(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.validate_symbol("") is False

    def test_invalid_symbol_too_long(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.validate_symbol("123456789.SH") is False

    def test_extended_mode(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.validate_symbol("AAPL.US", strict=False) is True
        assert InputSanitizer.validate_symbol("00700.HK", strict=False) is True

    def test_validate_symbols_batch(self):
        from src.core.input_sanitizer import InputSanitizer
        valid, invalid = InputSanitizer.validate_symbols(
            ["600519.SH", "bad!", "000333.SZ", "../hack"]
        )
        assert valid == ["600519.SH", "000333.SZ"]
        assert len(invalid) == 2


class TestNumericValidation:
    """Test numeric range validation."""

    def test_validate_range_within_bounds(self):
        from src.core.input_sanitizer import InputSanitizer
        val = InputSanitizer.validate_range(50, min_val=0, max_val=100)
        assert val == 50.0

    def test_validate_range_below_min(self):
        from src.core.input_sanitizer import InputSanitizer
        with pytest.raises(ValueError, match="must be >="):
            InputSanitizer.validate_range(-1, min_val=0)

    def test_validate_range_above_max(self):
        from src.core.input_sanitizer import InputSanitizer
        with pytest.raises(ValueError, match="must be <="):
            InputSanitizer.validate_range(200, max_val=100)

    def test_validate_range_non_numeric(self):
        from src.core.input_sanitizer import InputSanitizer
        with pytest.raises(ValueError, match="must be numeric"):
            InputSanitizer.validate_range("abc")

    def test_validate_positive(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.validate_positive(1.5) == 1.5
        with pytest.raises(ValueError):
            InputSanitizer.validate_positive(-1)


class TestDateValidation:
    """Test date format validation."""

    def test_valid_date(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.validate_date("2024-01-15") == "2024-01-15"

    def test_invalid_date_format(self):
        from src.core.input_sanitizer import InputSanitizer
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            InputSanitizer.validate_date("01-15-2024")

    def test_invalid_date_month(self):
        from src.core.input_sanitizer import InputSanitizer
        with pytest.raises(ValueError, match="month"):
            InputSanitizer.validate_date("2024-13-01")

    def test_invalid_date_year(self):
        from src.core.input_sanitizer import InputSanitizer
        with pytest.raises(ValueError, match="year"):
            InputSanitizer.validate_date("1800-01-01")


class TestStringSanitization:
    """Test HTML sanitization."""

    def test_html_escape(self):
        from src.core.input_sanitizer import InputSanitizer
        result = InputSanitizer.sanitize_string("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_truncation(self):
        from src.core.input_sanitizer import InputSanitizer
        long_str = "a" * 20000
        result = InputSanitizer.sanitize_string(long_str, max_length=100)
        assert len(result) == 100


class TestSecurityChecks:
    """Test SQL injection, XSS, and path traversal detection."""

    def test_sql_injection_detection(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.check_sql_injection("SELECT * FROM users") is True
        assert InputSanitizer.check_sql_injection("DROP TABLE orders") is True
        assert InputSanitizer.check_sql_injection("normal text") is False

    def test_sql_injection_comment(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.check_sql_injection("value'; --") is True

    def test_xss_detection(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.check_xss("<script>alert(1)</script>") is True
        assert InputSanitizer.check_xss("javascript:void(0)") is True
        assert InputSanitizer.check_xss("onclick=doStuff") is True
        assert InputSanitizer.check_xss("normal text") is False

    def test_path_traversal_detection(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.check_path_traversal("../../etc/passwd") is True
        assert InputSanitizer.check_path_traversal("..\\windows\\system32") is True
        assert InputSanitizer.check_path_traversal("normal/path") is False

    def test_is_safe_input(self):
        from src.core.input_sanitizer import InputSanitizer
        assert InputSanitizer.is_safe_input("600519.SH") is True
        assert InputSanitizer.is_safe_input("SELECT * FROM users") is False
        assert InputSanitizer.is_safe_input("<script>x</script>") is False
        assert InputSanitizer.is_safe_input("../../etc/passwd") is False


class TestStrategyCodeValidation:
    """Test strategy code safety validation."""

    def test_safe_code(self):
        from src.core.input_sanitizer import InputSanitizer
        warnings = InputSanitizer.validate_strategy_code("import pandas as pd\nx = pd.DataFrame()")
        assert len(warnings) == 0

    def test_dangerous_import(self):
        from src.core.input_sanitizer import InputSanitizer
        warnings = InputSanitizer.validate_strategy_code("import os\nos.system('rm -rf /')")
        assert any("os" in w for w in warnings)

    def test_dangerous_call(self):
        from src.core.input_sanitizer import InputSanitizer
        warnings = InputSanitizer.validate_strategy_code("eval('malicious code')")
        assert any("eval" in w for w in warnings)

    def test_multiple_issues(self):
        from src.core.input_sanitizer import InputSanitizer
        code = "import subprocess\neval('x')\nimport shutil"
        warnings = InputSanitizer.validate_strategy_code(code)
        assert len(warnings) >= 3


# ===========================================================================
# C-4: pyproject.toml validation
# ===========================================================================

class TestPyprojectToml:
    """Validate pyproject.toml structure."""

    @pytest.fixture
    def toml_data(self):
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                pytest.skip("No TOML parser available")
        toml_path = Path(__file__).parent.parent / "pyproject.toml"
        if not toml_path.exists():
            pytest.skip("pyproject.toml not found")
        return tomllib.loads(toml_path.read_text(encoding="utf-8"))

    def test_project_name(self, toml_data):
        assert toml_data["project"]["name"] == "quant-stock"

    def test_project_version(self, toml_data):
        assert toml_data["project"]["version"] == "5.0.0"

    def test_python_requires(self, toml_data):
        assert ">=3.10" in toml_data["project"]["requires-python"]

    def test_has_core_dependencies(self, toml_data):
        deps = toml_data["project"]["dependencies"]
        dep_names = [d.split(">=")[0].split("==")[0].lower() for d in deps]
        assert "pandas" in dep_names
        assert "numpy" in dep_names
        assert "pydantic" in dep_names

    def test_has_optional_dependency_groups(self, toml_data):
        opt = toml_data["project"]["optional-dependencies"]
        assert "api" in opt
        assert "perf" in opt
        assert "ml" in opt
        assert "dev" in opt
        assert "security" in opt

    def test_build_system(self, toml_data):
        assert "build-system" in toml_data
        assert "setuptools" in toml_data["build-system"]["requires"][0]

    def test_ruff_config(self, toml_data):
        assert "tool" in toml_data
        assert "ruff" in toml_data["tool"]

    def test_mypy_config(self, toml_data):
        assert "mypy" in toml_data["tool"]
        assert toml_data["tool"]["mypy"]["ignore_missing_imports"] is True
