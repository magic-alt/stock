"""Repository-wide pytest defaults.

Existing endpoint tests predate the Gate 0 FastAPI v2 authentication boundary.
They exercise business behavior rather than authentication, so they explicitly
run the application in local-development auth-disabled mode.  Dedicated auth
contract tests override this setting and verify fail-closed production behavior.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _explicit_local_api_auth_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_API_AUTH_DISABLED", "1")
    monkeypatch.setenv("PLATFORM_AUDIT_LOG", str(tmp_path / "api-v2-audit.log"))
