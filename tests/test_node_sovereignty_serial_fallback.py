"""Covenant §3: no node may stamp another node's hardware identity.

Carlos Nevarez installed a SIFTA node on 2026-07-24. Any registry row written
on his machine without an explicit serial used to inherit the literal
"GTH4921YP3" — the Architect's M5. These tests hold that door shut.
"""
from __future__ import annotations

import json

from System.bootstrap_ide_model_registry import local_homeworld_serial

ARCHITECT_M5_SERIAL = "GTH4921YP3"


def test_serial_resolves_from_this_nodes_own_genesis(tmp_path, monkeypatch):
    genesis = tmp_path / "owner_genesis.json"
    genesis.write_text(
        json.dumps({"event": "OWNER_GENESIS", "silicon": "CARLOS9ABC1", "owner_name": "Carlos Nevarez"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("System.bootstrap_ide_model_registry._GENESIS", genesis)

    assert local_homeworld_serial() == "CARLOS9ABC1"


def test_missing_genesis_never_falls_back_to_the_architects_serial(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.bootstrap_ide_model_registry._GENESIS", tmp_path / "does_not_exist.json"
    )
    # No genesis file: the hardware probe answers, or the honest unknown does.
    # Either way it must never be the Architect's machine.
    def _no_hardware_probe(*args, **kwargs):
        raise OSError("no system_profiler on this node")

    monkeypatch.setattr("subprocess.run", _no_hardware_probe)

    assert local_homeworld_serial() == "UNKNOWN_SERIAL"


def test_corrupt_genesis_does_not_borrow_an_identity(tmp_path, monkeypatch):
    genesis = tmp_path / "owner_genesis.json"
    genesis.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setattr("System.bootstrap_ide_model_registry._GENESIS", genesis)
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked"))
    )

    assert local_homeworld_serial() == "UNKNOWN_SERIAL"


def test_empty_silicon_field_is_not_treated_as_an_identity(tmp_path, monkeypatch):
    genesis = tmp_path / "owner_genesis.json"
    genesis.write_text(json.dumps({"event": "OWNER_GENESIS", "silicon": "   "}), encoding="utf-8")
    monkeypatch.setattr("System.bootstrap_ide_model_registry._GENESIS", genesis)
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked"))
    )

    assert local_homeworld_serial() == "UNKNOWN_SERIAL"


def test_the_architects_serial_is_no_longer_a_source_literal():
    """The fallback itself must not contain another node's hardware id."""
    import inspect

    from System import bootstrap_ide_model_registry as mod

    source = inspect.getsource(mod.local_homeworld_serial)
    # The docstring names the serial as the thing being removed; the executable
    # body must not return it.
    body = source.split('"""')[-1]
    assert ARCHITECT_M5_SERIAL not in body
