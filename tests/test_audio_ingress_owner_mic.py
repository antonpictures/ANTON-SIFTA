from __future__ import annotations

from System import audio_ingress as ingress


def test_embedded_owner_mic_detection():
    assert ingress.is_embedded_owner_microphone("MacBook Pro Microphone")
    assert ingress.is_embedded_owner_microphone("Built-in Microphone")
    assert not ingress.is_embedded_owner_microphone("iPhone Microphone")


def test_no_microphone_allowlist_gate_exports_remain():
    assert not hasattr(ingress, "is_allowed_owner_body_microphone")
    assert not hasattr(ingress, "enumerate_allowed_owner_body_microphones")
    assert not hasattr(ingress, "resolve_owner_body_microphone")


def test_default_microphone_rank_embedded_before_wireless_and_usb():
    assert ingress.default_microphone_rank("MacBook Pro Microphone") < ingress.default_microphone_rank(
        "DELL PROFESSIONAL SOUND BAR AE515"
    )
    assert ingress.default_microphone_rank("MacBook Pro Microphone") < ingress.default_microphone_rank(
        "iPhone Microphone"
    )
    assert ingress.default_microphone_rank("USB Audio Device") < ingress.default_microphone_rank(
        "iPhone Microphone"
    )


def test_rank_input_microphones_puts_macbook_pro_first():
    class FakeSd:
        @staticmethod
        def query_devices():
            return [
                {"name": "iPhone Microphone", "max_input_channels": 1},
                {"name": "DELL PROFESSIONAL SOUND BAR AE515", "max_input_channels": 2},
                {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            ]

    rows = ingress.rank_input_microphones(FakeSd())
    assert [name for _idx, name in rows] == [
        "MacBook Pro Microphone",
        "DELL PROFESSIONAL SOUND BAR AE515",
        "iPhone Microphone",
    ]
