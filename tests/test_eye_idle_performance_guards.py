from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
EYE_WIDGET = REPO / "Applications" / "sifta_what_alice_sees_widget.py"


def _source() -> str:
    return EYE_WIDGET.read_text(encoding="utf-8")


def test_eye_frame_path_uses_low_stress_defaults() -> None:
    src = _source()

    assert 'SIFTA_EYE_FRAME_PERIOD_S", 1.0' in src
    assert 'SIFTA_KERNEL_VISION_HEARTBEAT_PERIOD_S", 5.0' in src
    assert "_LEDGER_PERIOD_S = _EYE_FRAME_PERIOD_S" in src


def test_eye_frame_path_does_not_parse_full_focus_context() -> None:
    src = _source()

    assert "from System.swarm_app_focus import get_focus_context" not in src
    assert "def _cached_app_focus" in src
    assert "def _read_last_jsonl_dict" in src


def test_eye_widget_does_not_tail_own_visual_ledger_by_default() -> None:
    src = _source()

    assert 'SIFTA_EYE_TAIL_SELF_LEDGER", "0"' in src
    assert 'if fname == "visual_stigmergy.jsonl" and not tail_self:' in src
    assert "self._poll_timer.timeout.connect(self._poll_ledgers)" not in src
    assert "self.make_timer(1000, self._poll_ledgers)" in src


def test_eye_widget_boots_to_live_camera_unless_explicitly_disabled() -> None:
    src = _source()

    assert 'SIFTA_EYE_BOOT_OFF", "0"' in src
    assert "default_idx = 0 if _EYE_BOOT_OFF else min(1, self._cam_combo.count() - 1)" in src
    assert "SIFTA_ALICE_UNIFIED_DEFER_EYE=1 or SIFTA_EYE_BOOT_OFF=1" in src
