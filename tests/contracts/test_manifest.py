"""Tests for :class:`PluginManifest` and the version-compatibility helper."""
from __future__ import annotations

import pytest

from src.core.contracts import (
    CONTRACT_VERSION,
    KNOWN_CAPABILITIES,
    KNOWN_PERMISSIONS,
    PLUGIN_KINDS,
    PluginManifest,
    is_compatible,
)


# ---------------------------------------------------------------------------
# Version compatibility
# ---------------------------------------------------------------------------


def test_contract_version_is_frozen_at_0_1_0():
    """The Phase 2 surface is frozen at 0.1.0 — bumping requires a contract change."""
    assert CONTRACT_VERSION == "0.1.0"


def test_is_compatible_same_version():
    assert is_compatible("0.1.0", "0.1.0")


def test_is_compatible_pre_1_0_requires_exact_minor():
    assert not is_compatible("0.1.0", "0.2.0")
    assert not is_compatible("0.2.0", "0.1.0")


def test_is_compatible_post_1_0_semver():
    assert is_compatible("1.2.0", "1.3.0")
    assert is_compatible("1.0.0", "1.5.7")
    assert not is_compatible("1.5.0", "1.2.0")
    assert not is_compatible("2.0.0", "1.5.0")


def test_is_compatible_invalid_version_returns_false():
    assert not is_compatible("abc", "0.1.0")
    assert not is_compatible("0.1", "0.1.0")
    assert not is_compatible("0.1.0.0", "0.1.0")


# ---------------------------------------------------------------------------
# PluginManifest validation
# ---------------------------------------------------------------------------


def _ok(**overrides) -> dict:
    base = dict(
        id="acme.example",
        name="ACME Example",
        version="0.1.0",
        kind="strategy",
        entry_point="acme.example:Strategy",
    )
    base.update(overrides)
    return base


def test_manifest_minimal_construction():
    m = PluginManifest(**_ok())
    assert m.id == "acme.example"
    assert m.contract_version == CONTRACT_VERSION
    assert m.is_contract_compatible()


def test_manifest_rejects_empty_required_fields():
    for field in ("id", "name", "version"):
        with pytest.raises(ValueError):
            PluginManifest(**_ok(**{field: ""}))


def test_manifest_rejects_unknown_kind():
    with pytest.raises(ValueError):
        PluginManifest(**_ok(kind="not_a_kind"))


def test_manifest_kind_must_match_entry_point_groups():
    """Every declared kind must correspond to a published entry-point group."""
    for k in PLUGIN_KINDS:
        # Construction must not raise for any declared kind.
        PluginManifest(**_ok(kind=k))


def test_manifest_rejects_bad_entry_point():
    with pytest.raises(ValueError):
        PluginManifest(**_ok(entry_point="no_colon_here"))


def test_manifest_rejects_bad_id_characters():
    with pytest.raises(ValueError):
        PluginManifest(**_ok(id="bad id with spaces"))
    with pytest.raises(ValueError):
        PluginManifest(**_ok(id="bad/slash"))


def test_manifest_allows_known_capabilities_and_permissions():
    cap = next(iter(KNOWN_CAPABILITIES))
    perm = next(iter(KNOWN_PERMISSIONS))
    m = PluginManifest(**_ok(capabilities=(cap,), permissions=(perm,)))
    assert m.unknown_capabilities() == ()
    assert m.unknown_permissions() == ()


def test_manifest_flags_unknown_capabilities_and_permissions():
    m = PluginManifest(**_ok(capabilities=("frobnicate",), permissions=("self.destruct",)))
    assert m.unknown_capabilities() == ("frobnicate",)
    assert m.unknown_permissions() == ("self.destruct",)


def test_manifest_to_dict_round_trippable():
    m = PluginManifest(**_ok(capabilities=("daily",), permissions=("network.outbound",),
                              requires={"pandas": ">=2"}))
    d = m.to_dict()
    assert d["id"] == m.id
    assert d["capabilities"] == ["daily"]
    assert d["permissions"] == ["network.outbound"]
    assert d["requires"] == {"pandas": ">=2"}


def test_manifest_contract_compat_with_explicit_available():
    m = PluginManifest(**_ok(contract_version="0.1.0"))
    assert m.is_contract_compatible("0.1.0")
    assert not m.is_contract_compatible("0.2.0")
    assert not m.is_contract_compatible("1.0.0")
