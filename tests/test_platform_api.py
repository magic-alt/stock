"""
Tests for modular API router and middleware.
"""
import pytest

from src.platform.api.router import APIRouter, RequestContext, ResponseContext
from src.platform.api.middleware import (
    RBACMiddleware,
    RateLimiter,
    RequestValidator,
    AuditMiddleware,
)
from src.core.auth import Authorizer, Permission, Role, Subject
from src.core.audit import AuditLogger


# ---------------------------------------------------------------------------
# APIRouter tests
# ---------------------------------------------------------------------------


class TestAPIRouter:
    def test_register_and_dispatch_get(self):
        router = APIRouter()

        @router.get("/api/v1/health")
        def health(req):
            return ResponseContext(status_code=200, body={"ok": True})

        request = RequestContext(method="GET", path="/api/v1/health")
        resp = router.dispatch(request)
        assert resp.status_code == 200
        assert resp.body == {"ok": True}

    def test_register_and_dispatch_post(self):
        router = APIRouter()

        @router.post("/api/v1/jobs")
        def create_job(req):
            return ResponseContext(status_code=201, body={"created": True})

        request = RequestContext(method="POST", path="/api/v1/jobs")
        resp = router.dispatch(request)
        assert resp.status_code == 201

    def test_path_params_extraction(self):
        router = APIRouter()

        @router.get("/api/v1/jobs/{job_id}")
        def get_job(req):
            return ResponseContext(body={"job_id": req.path_params["job_id"]})

        request = RequestContext(method="GET", path="/api/v1/jobs/abc-123")
        resp = router.dispatch(request)
        assert resp.body["job_id"] == "abc-123"

    def test_404_for_unknown_route(self):
        router = APIRouter()
        request = RequestContext(method="GET", path="/no/such/path")
        resp = router.dispatch(request)
        assert resp.status_code == 404

    def test_method_not_allowed(self):
        router = APIRouter()

        @router.get("/api/v1/health")
        def health(req):
            return ResponseContext(body={"ok": True})

        request = RequestContext(method="DELETE", path="/api/v1/health")
        resp = router.dispatch(request)
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# RBACMiddleware tests
# ---------------------------------------------------------------------------


class TestRBACMiddleware:
    def _make_handler(self):
        def handler(req):
            return ResponseContext(body={"ok": True})
        return handler

    def test_public_endpoint_no_auth_required(self):
        auth = Authorizer()
        mw = RBACMiddleware(auth, public_paths={"/health"})
        wrapped = mw(self._make_handler())
        req = RequestContext(method="GET", path="/health")
        resp = wrapped(req)
        assert resp.status_code == 200

    def test_protected_endpoint_requires_token(self):
        auth = Authorizer()
        mw = RBACMiddleware(auth)
        wrapped = mw(self._make_handler())
        req = RequestContext(method="GET", path="/api/v1/jobs", headers={})
        resp = wrapped(req)
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        auth = Authorizer()
        mw = RBACMiddleware(auth)
        wrapped = mw(self._make_handler())
        req = RequestContext(method="GET", path="/api/v1/jobs", headers={"Authorization": "Bearer bad-token"})
        resp = wrapped(req)
        assert resp.status_code == 401

    def test_insufficient_role_returns_403(self):
        auth = Authorizer()
        viewer = Subject(subject_id="v1", role=Role.VIEWER, tenant_id="T1")
        mw = RBACMiddleware(auth)
        mw.register_token("viewer-tok", viewer)
        wrapped = mw(self._make_handler())

        req = RequestContext(method="POST", path="/api/v1/jobs", headers={"Authorization": "Bearer viewer-tok"})
        resp = wrapped(req)
        assert resp.status_code == 403

    def test_subject_injected_into_request(self):
        auth = Authorizer()
        trader = Subject(subject_id="t1", role=Role.TRADER, tenant_id="T1")
        mw = RBACMiddleware(auth)
        mw.register_token("trader-tok", trader)

        captured = {}

        def handler(req):
            captured["subject"] = req.subject
            return ResponseContext(body={"ok": True})

        wrapped = mw(handler)
        req = RequestContext(method="GET", path="/api/v1/jobs", headers={"Authorization": "Bearer trader-tok"})
        resp = wrapped(req)
        assert resp.status_code == 200
        assert captured["subject"].subject_id == "t1"


# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allows_requests_within_limit(self):
        limiter = RateLimiter(max_tokens=5, refill_rate=0)
        handler = lambda req: ResponseContext(body={"ok": True})
        wrapped = limiter(handler)

        for _ in range(5):
            resp = wrapped(RequestContext(method="GET", path="/"))
            assert resp.status_code == 200

    def test_rejects_excess_requests(self):
        limiter = RateLimiter(max_tokens=2, refill_rate=0)
        handler = lambda req: ResponseContext(body={"ok": True})
        wrapped = limiter(handler)

        wrapped(RequestContext(method="GET", path="/"))
        wrapped(RequestContext(method="GET", path="/"))
        resp = wrapped(RequestContext(method="GET", path="/"))
        assert resp.status_code == 429

    def test_refill_after_interval(self):
        import time
        limiter = RateLimiter(max_tokens=1, refill_rate=1000)
        handler = lambda req: ResponseContext(body={"ok": True})
        wrapped = limiter(handler)

        resp = wrapped(RequestContext(method="GET", path="/"))
        assert resp.status_code == 200
        time.sleep(0.01)
        resp = wrapped(RequestContext(method="GET", path="/"))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# RequestValidator tests
# ---------------------------------------------------------------------------


class TestRequestValidator:
    def test_valid_json_body_passes(self):
        validator = RequestValidator(required_fields={"name": str})
        handler = lambda req: ResponseContext(body={"ok": True})
        wrapped = validator(handler)

        req = RequestContext(method="POST", path="/", body={"name": "test"})
        resp = wrapped(req)
        assert resp.status_code == 200

    def test_missing_required_field_returns_400(self):
        validator = RequestValidator(required_fields={"name": str})
        handler = lambda req: ResponseContext(body={"ok": True})
        wrapped = validator(handler)

        req = RequestContext(method="POST", path="/", body={})
        resp = wrapped(req)
        assert resp.status_code == 400

    def test_invalid_type_returns_400(self):
        validator = RequestValidator(required_fields={"count": int})
        handler = lambda req: ResponseContext(body={"ok": True})
        wrapped = validator(handler)

        req = RequestContext(method="POST", path="/", body={"count": "not_int"})
        resp = wrapped(req)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# AuditMiddleware tests
# ---------------------------------------------------------------------------


class TestAuditMiddleware:
    def test_write_operations_logged(self, tmp_path):
        audit = AuditLogger(path=str(tmp_path / "audit.log"))
        handler = lambda req: ResponseContext(body={"ok": True})
        mw = AuditMiddleware(audit)
        wrapped = mw(handler)

        req = RequestContext(method="POST", path="/api/v1/jobs")
        wrapped(req)

        assert audit.verify()
        events = audit.export_for_compliance()
        assert len(events) == 1
        assert events[0].action == "api.post"

    def test_read_operations_not_logged(self, tmp_path):
        audit = AuditLogger(path=str(tmp_path / "audit.log"))
        handler = lambda req: ResponseContext(body={"ok": True})
        mw = AuditMiddleware(audit)
        wrapped = mw(handler)

        req = RequestContext(method="GET", path="/api/v1/jobs")
        wrapped(req)

        events = audit.export_for_compliance()
        assert len(events) == 0
