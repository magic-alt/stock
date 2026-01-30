"""
License policy utilities for AI framework integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Set


def normalize_license(license_id: str) -> str:
    return license_id.strip().upper().replace(" ", "-")


@dataclass(frozen=True)
class LicensePolicy:
    """Allow/deny list for framework licenses."""
    allowed: Set[str]
    denied: Set[str]

    @classmethod
    def default(cls) -> "LicensePolicy":
        return cls(
            allowed={"MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE"},
            denied={"GPL-3.0", "AGPL-3.0"},
        )

    def is_allowed(self, license_id: str) -> bool:
        norm = normalize_license(license_id)
        if norm in self.denied:
            return False
        if self.allowed:
            return norm in self.allowed
        return True
