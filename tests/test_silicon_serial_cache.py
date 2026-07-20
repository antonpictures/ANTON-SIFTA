from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from System import silicon_serial


def test_read_apple_serial_caches_ioreg_result(monkeypatch):
    monkeypatch.delenv("SIFTA_HOMEWORLD_SERIAL", raising=False)
    silicon_serial.reset_serial_cache_for_test()
    proc = SimpleNamespace(stdout='"IOPlatformSerialNumber" = "GTH4921YP3"\n')

    with patch("System.silicon_serial.subprocess.run", return_value=proc) as run:
        assert silicon_serial.read_apple_serial() == "GTH4921YP3"
        assert silicon_serial.read_apple_serial() == "GTH4921YP3"

    run.assert_called_once()


def test_read_apple_serial_uses_env_override_without_ioreg(monkeypatch):
    silicon_serial.reset_serial_cache_for_test()
    monkeypatch.setenv("SIFTA_HOMEWORLD_SERIAL", "TEST_SERIAL")

    with patch("System.silicon_serial.subprocess.run") as run:
        assert silicon_serial.read_apple_serial() == "TEST_SERIAL"

    run.assert_not_called()
