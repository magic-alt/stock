"""Compatibility facade for the `quant-platform-web` distribution."""
from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPOSITORY_ROOT / "frontend"
STATIC_WEB_DIR = REPOSITORY_ROOT / "src" / "platform" / "web"

__all__ = ["FRONTEND_DIR", "STATIC_WEB_DIR"]
