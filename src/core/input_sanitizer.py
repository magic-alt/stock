"""
Input Sanitizer Module (V5.0-C-3) — Unified input validation and sanitization.

Provides:
- Symbol format validation (A-share codes)
- Numeric range checks
- Path traversal protection
- SQL-like injection pattern detection
- General string sanitization

Usage:
    >>> from src.core.input_sanitizer import InputSanitizer
    >>> san = InputSanitizer()
    >>> san.validate_symbol("600519.SH")
    True
    >>> san.validate_symbol("../../etc/passwd")
    False
    >>> san.sanitize_string("<script>alert(1)</script>")
    '&lt;script&gt;alert(1)&lt;/script&gt;'
"""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Symbol validation
# ---------------------------------------------------------------------------

# A-share patterns: 6 digits + optional .SH/.SZ/.BJ suffix
_SYMBOL_PATTERN = re.compile(
    r"^[0-9]{6}(\.(SH|SZ|BJ|sh|sz|bj))?$"
)

# Extended: allow HK (5 digits), US (letters), index (000001.SH)
_SYMBOL_EXTENDED_PATTERN = re.compile(
    r"^[A-Za-z0-9]{1,10}(\.[A-Za-z]{1,4})?$"
)


# ---------------------------------------------------------------------------
# SQL injection detection
# ---------------------------------------------------------------------------

_SQL_PATTERNS = [
    re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|UNION|TRUNCATE)\b)", re.IGNORECASE),
    re.compile(r"(--|;|/\*|\*/|xp_|@@)", re.IGNORECASE),
    re.compile(r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)", re.IGNORECASE),  # OR 1=1
]


# ---------------------------------------------------------------------------
# XSS / HTML patterns
# ---------------------------------------------------------------------------

_XSS_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # onclick=, onload=
    re.compile(r"<iframe", re.IGNORECASE),
    re.compile(r"<object", re.IGNORECASE),
    re.compile(r"<embed", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Path traversal patterns
# ---------------------------------------------------------------------------

_PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\.[/\\]"),
    re.compile(r"[/\\]etc[/\\]"),
    re.compile(r"[/\\]proc[/\\]"),
    re.compile(r"%2e%2e", re.IGNORECASE),
    re.compile(r"%252e", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# HTML entity escaping
# ---------------------------------------------------------------------------

_HTML_ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#x27;",
}


def _html_escape(s: str) -> str:
    for char, entity in _HTML_ESCAPE_MAP.items():
        s = s.replace(char, entity)
    return s


# ---------------------------------------------------------------------------
# InputSanitizer
# ---------------------------------------------------------------------------

class InputSanitizer:
    """Unified input validation and sanitization."""

    # -- Symbol validation ---------------------------------------------------

    @staticmethod
    def validate_symbol(symbol: str, strict: bool = True) -> bool:
        """Validate a trading symbol.

        Args:
            symbol: The symbol string.
            strict: If True, only A-share format allowed.
        """
        if not symbol or not isinstance(symbol, str):
            return False
        pattern = _SYMBOL_PATTERN if strict else _SYMBOL_EXTENDED_PATTERN
        return bool(pattern.match(symbol))

    @staticmethod
    def validate_symbols(symbols: List[str], strict: bool = True) -> Tuple[List[str], List[str]]:
        """Validate a list of symbols.

        Returns:
            Tuple of (valid_symbols, invalid_symbols).
        """
        valid, invalid = [], []
        for s in symbols:
            if InputSanitizer.validate_symbol(s, strict=strict):
                valid.append(s)
            else:
                invalid.append(s)
        return valid, invalid

    # -- Numeric validation --------------------------------------------------

    @staticmethod
    def validate_range(
        value: Any,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        name: str = "value",
    ) -> float:
        """Validate that a numeric value is within range.

        Raises:
            ValueError: If out of range or not numeric.
        """
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be numeric, got {type(value).__name__}")
        if min_val is not None and num < min_val:
            raise ValueError(f"{name} must be >= {min_val}, got {num}")
        if max_val is not None and num > max_val:
            raise ValueError(f"{name} must be <= {max_val}, got {num}")
        return num

    @staticmethod
    def validate_positive(value: Any, name: str = "value") -> float:
        """Validate that value is positive."""
        return InputSanitizer.validate_range(value, min_val=0.0001, name=name)

    # -- Date validation -----------------------------------------------------

    @staticmethod
    def validate_date(date_str: str, name: str = "date") -> str:
        """Validate YYYY-MM-DD format.

        Returns the validated date string.
        """
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            raise ValueError(f"{name} must be YYYY-MM-DD format, got '{date_str}'")
        # Basic range check
        year, month, day = date_str.split("-")
        y, m, d = int(year), int(month), int(day)
        if not (1990 <= y <= 2100):
            raise ValueError(f"{name} year must be 1990-2100, got {y}")
        if not (1 <= m <= 12):
            raise ValueError(f"{name} month must be 1-12, got {m}")
        if not (1 <= d <= 31):
            raise ValueError(f"{name} day must be 1-31, got {d}")
        return date_str

    # -- String sanitization -------------------------------------------------

    @staticmethod
    def sanitize_string(value: str, max_length: int = 10000) -> str:
        """Sanitize a string by escaping HTML entities and truncating."""
        if not isinstance(value, str):
            value = str(value)
        value = value[:max_length]
        return _html_escape(value)

    # -- Security checks -----------------------------------------------------

    @staticmethod
    def check_sql_injection(value: str) -> bool:
        """Check if a string contains SQL injection patterns.

        Returns:
            True if suspicious patterns found.
        """
        for pattern in _SQL_PATTERNS:
            if pattern.search(value):
                return True
        return False

    @staticmethod
    def check_xss(value: str) -> bool:
        """Check if a string contains XSS patterns.

        Returns:
            True if suspicious patterns found.
        """
        for pattern in _XSS_PATTERNS:
            if pattern.search(value):
                return True
        return False

    @staticmethod
    def check_path_traversal(value: str) -> bool:
        """Check if a string contains path traversal patterns.

        Returns:
            True if suspicious patterns found.
        """
        for pattern in _PATH_TRAVERSAL_PATTERNS:
            if pattern.search(value):
                return True
        return False

    @staticmethod
    def is_safe_input(value: str) -> bool:
        """Combined safety check — returns True only if no threats detected."""
        return not (
            InputSanitizer.check_sql_injection(value)
            or InputSanitizer.check_xss(value)
            or InputSanitizer.check_path_traversal(value)
        )

    # -- Strategy code validation --------------------------------------------

    @staticmethod
    def validate_strategy_code(code: str) -> List[str]:
        """Validate strategy Python code for dangerous patterns.

        Returns:
            List of warning messages (empty = safe).
        """
        warnings: List[str] = []
        dangerous_imports = {"os", "subprocess", "shutil", "sys", "socket", "ctypes"}
        dangerous_calls = {"eval", "exec", "compile", "__import__", "open"}

        for i, line in enumerate(code.split("\n"), 1):
            stripped = line.strip()
            # Check imports
            if stripped.startswith("import ") or stripped.startswith("from "):
                for mod in dangerous_imports:
                    if mod in stripped:
                        warnings.append(f"Line {i}: Restricted import '{mod}'")
            # Check dangerous calls
            for call in dangerous_calls:
                if f"{call}(" in stripped:
                    warnings.append(f"Line {i}: Potentially dangerous call '{call}()'")

        return warnings


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "InputSanitizer",
]
