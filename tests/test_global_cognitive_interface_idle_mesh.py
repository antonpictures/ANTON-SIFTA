from __future__ import annotations


def test_relay_tcp_available_parses_websocket_uri(monkeypatch):
    from System import global_cognitive_interface as gci

    calls = []

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_create_connection(addr, timeout):
        calls.append((addr, timeout))
        return FakeSocket()

    monkeypatch.setattr(gci.socket, "create_connection", fake_create_connection)

    assert gci._relay_tcp_available("ws://relay.local:4321", timeout=0.125) is True
    assert calls == [(("relay.local", 4321), 0.125)]


def test_relay_tcp_available_returns_false_when_relay_is_down(monkeypatch):
    from System import global_cognitive_interface as gci

    def fake_create_connection(_addr, _timeout):
        raise OSError("closed")

    monkeypatch.setattr(gci.socket, "create_connection", fake_create_connection)

    assert gci._relay_tcp_available("ws://127.0.0.1:8765") is False


def test_mesh_reconnect_backoff_is_not_100ms_hot_spin():
    from pathlib import Path

    source = Path("System/global_cognitive_interface.py").read_text(encoding="utf-8")
    assert "await asyncio.sleep(0.5)" in source
    assert "await asyncio.sleep(0.1)" not in source
