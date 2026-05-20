"""V6 contract conformance test skeleton.

These tests are the FROZEN baseline of the V6 open-platform SDK surface
(see :mod:`src.core.contracts.version`). They are split into three layers:

* :mod:`test_dto_invariants` — every DTO is frozen, validates on construct,
  round-trips through ``to_dict``;
* :mod:`test_manifest` — :class:`PluginManifest` field validation and
  contract-compatibility helper;
* :mod:`test_port_protocols` — every port in
  :data:`src.core.contracts.ports.ALL_PORTS` is a runtime-checkable Protocol;
  a reference in-memory implementation demonstrates structural conformance.

Adapter authors are encouraged to copy ``test_port_protocols.py`` and run
``isinstance(MyAdapter, FooPort)`` against their own classes — that single
assertion is sufficient to prove they speak the SDK surface.
"""
