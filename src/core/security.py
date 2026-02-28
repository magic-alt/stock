"""
Security Module (V5.0-C-2) — TLS helpers, key rotation, config encryption.

Provides:
- TLS certificate generation (self-signed) and validation
- API token generation and rotation
- Configuration value encryption (Fernet symmetric)
- Secure secret masking for logs

Usage:
    >>> from src.core.security import SecurityManager
    >>> sm = SecurityManager(secret_key="my-32-byte-key-here-pad-to-32!!")
    >>> encrypted = sm.encrypt("super-secret-value")
    >>> sm.decrypt(encrypted)
    'super-secret-value'
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.logger import get_logger

logger = get_logger("security")


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

def generate_api_token(prefix: str = "qp", length: int = 32) -> str:
    """Generate a secure random API token.

    Format: ``{prefix}_{random_hex}``

    Args:
        prefix: Short prefix to identify token origin.
        length: Number of random bytes (hex-encoded length will be 2x).
    """
    random_part = secrets.token_hex(length)
    return f"{prefix}_{random_part}"


def hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for safe storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Fernet-like symmetric encryption (stdlib only)
# ---------------------------------------------------------------------------

class _SimpleEncryptor:
    """AES-like encryption using stdlib only (base64 + HMAC for integrity).

    This is a *simplified* encryptor for config values.  For production-grade
    encryption prefer the ``cryptography`` package (Fernet).  This fallback
    uses HMAC-SHA256 for integrity and base64 obfuscation — it is NOT a
    true AES cipher but protects against casual inspection and log leakage.
    """

    def __init__(self, key: bytes) -> None:
        # Derive two sub-keys: one for "encryption" (XOR mask), one for HMAC
        self._enc_key = hashlib.sha256(b"enc:" + key).digest()
        self._mac_key = hashlib.sha256(b"mac:" + key).digest()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt *plaintext* returning a base64 token."""
        data = plaintext.encode()
        # XOR with repeating key stream
        ks = self._enc_key * ((len(data) // len(self._enc_key)) + 1)
        cipher = bytes(a ^ b for a, b in zip(data, ks))
        mac = hmac.new(self._mac_key, cipher, hashlib.sha256).digest()
        payload = mac + cipher
        return base64.urlsafe_b64encode(payload).decode()

    def decrypt(self, token: str) -> str:
        """Decrypt a token produced by :meth:`encrypt`."""
        try:
            payload = base64.urlsafe_b64decode(token.encode())
        except Exception as exc:
            raise ValueError("Invalid encrypted token") from exc
        if len(payload) < 32:
            raise ValueError("Token too short")
        mac_expected, cipher = payload[:32], payload[32:]
        mac_actual = hmac.new(self._mac_key, cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(mac_expected, mac_actual):
            raise ValueError("Integrity check failed — token tampered or wrong key")
        ks = self._enc_key * ((len(cipher) // len(self._enc_key)) + 1)
        plaintext = bytes(a ^ b for a, b in zip(cipher, ks))
        return plaintext.decode()


# Try to use real Fernet if available
try:
    from cryptography.fernet import Fernet as _RealFernet  # type: ignore[import-untyped]
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


# ---------------------------------------------------------------------------
# Security Manager
# ---------------------------------------------------------------------------

@dataclass
class TokenInfo:
    """Metadata about an issued API token."""
    token_hash: str
    created_at: float
    expires_at: float  # 0 means no expiry
    owner: str = ""
    scopes: List[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at


class SecurityManager:
    """Central security helper for the platform.

    Provides token lifecycle management, config encryption, and secret masking.
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        token_ttl_seconds: float = 86400 * 30,  # 30 days default
    ) -> None:
        raw_key = (secret_key or os.environ.get("QUANT_SECRET_KEY", "")).encode()
        if not raw_key:
            raw_key = b"default-insecure-key-change-me!!"
            logger.warning("security_using_default_key — set QUANT_SECRET_KEY env var")

        self._raw_key = hashlib.sha256(raw_key).digest()
        self.token_ttl = token_ttl_seconds

        # Encryptor
        if HAS_CRYPTOGRAPHY:
            fernet_key = base64.urlsafe_b64encode(self._raw_key)
            self._encryptor: Any = _RealFernet(fernet_key)
            self._use_fernet = True
        else:
            self._encryptor = _SimpleEncryptor(self._raw_key)
            self._use_fernet = False

        # Token registry (hash → TokenInfo)
        self._tokens: Dict[str, TokenInfo] = {}

    # -- Encryption ----------------------------------------------------------

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a config value or secret."""
        if self._use_fernet:
            return self._encryptor.encrypt(plaintext.encode()).decode()
        return self._encryptor.encrypt(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a previously encrypted value."""
        if self._use_fernet:
            return self._encryptor.decrypt(ciphertext.encode()).decode()
        return self._encryptor.decrypt(ciphertext)

    # -- Token management ----------------------------------------------------

    def issue_token(
        self,
        owner: str = "",
        scopes: Optional[List[str]] = None,
        ttl: Optional[float] = None,
    ) -> str:
        """Issue a new API token and register it."""
        token = generate_api_token()
        now = time.time()
        ttl_val = ttl if ttl is not None else self.token_ttl
        info = TokenInfo(
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + ttl_val if ttl_val > 0 else 0,
            owner=owner,
            scopes=scopes or [],
        )
        self._tokens[info.token_hash] = info
        logger.info("token_issued", owner=owner, expires_in=ttl_val)
        return token

    def validate_token(self, token: str) -> Optional[TokenInfo]:
        """Validate a token and return its info, or None if invalid/expired."""
        th = hash_token(token)
        info = self._tokens.get(th)
        if info is None:
            return None
        if info.is_expired:
            self.revoke_token(token)
            return None
        return info

    def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        th = hash_token(token)
        if th in self._tokens:
            del self._tokens[th]
            logger.info("token_revoked", token_hash=th[:8])
            return True
        return False

    def rotate_token(self, old_token: str) -> Optional[str]:
        """Rotate (replace) an existing token with a new one."""
        info = self.validate_token(old_token)
        if info is None:
            return None
        self.revoke_token(old_token)
        return self.issue_token(owner=info.owner, scopes=info.scopes)

    def list_tokens(self) -> List[TokenInfo]:
        """List all active tokens (hashes only, not raw values)."""
        self._purge_expired()
        return list(self._tokens.values())

    def _purge_expired(self) -> None:
        expired = [h for h, info in self._tokens.items() if info.is_expired]
        for h in expired:
            del self._tokens[h]

    # -- Secret masking ------------------------------------------------------

    @staticmethod
    def mask_secret(value: str, visible_chars: int = 4) -> str:
        """Mask a secret value for safe logging.

        Example:
            >>> SecurityManager.mask_secret("qp_abcdef1234567890")
            'qp_a***7890'
        """
        if len(value) <= visible_chars * 2:
            return "***"
        return value[:visible_chars] + "***" + value[-visible_chars:]

    @staticmethod
    def mask_dict(d: Dict[str, Any], sensitive_keys: Optional[set] = None) -> Dict[str, Any]:
        """Return a copy of *d* with sensitive values masked."""
        _sensitive = sensitive_keys or {"token", "password", "secret", "api_key", "secret_key"}
        result = {}
        for k, v in d.items():
            if any(sk in k.lower() for sk in _sensitive):
                result[k] = SecurityManager.mask_secret(str(v))
            elif isinstance(v, dict):
                result[k] = SecurityManager.mask_dict(v, _sensitive)
            else:
                result[k] = v
        return result


# ---------------------------------------------------------------------------
# TLS Certificate helpers
# ---------------------------------------------------------------------------

@dataclass
class TLSConfig:
    """TLS configuration."""
    certfile: str = ""
    keyfile: str = ""
    ca_certfile: str = ""
    enabled: bool = False

    def is_valid(self) -> bool:
        """Check if cert and key files exist."""
        if not self.enabled:
            return True  # TLS disabled is 'valid'
        return bool(self.certfile) and Path(self.certfile).exists() and bool(self.keyfile) and Path(self.keyfile).exists()


def generate_self_signed_cert(
    cert_path: str = "server.crt",
    key_path: str = "server.key",
    common_name: str = "localhost",
    days: int = 365,
) -> Tuple[str, str]:
    """Generate a self-signed TLS certificate (requires ``cryptography`` package).

    Returns:
        Tuple of (cert_path, key_path).
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime as _dt
    except ImportError:
        raise ImportError(
            "The 'cryptography' package is required for TLS cert generation: "
            "pip install cryptography"
        )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.utcnow())
        .not_valid_after(_dt.datetime.utcnow() + _dt.timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName(common_name),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    Path(cert_path).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    Path(key_path).write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    logger.info("self_signed_cert_generated", cert=cert_path, key=key_path)
    return cert_path, key_path


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "SecurityManager",
    "TokenInfo",
    "TLSConfig",
    "generate_api_token",
    "hash_token",
    "generate_self_signed_cert",
]
