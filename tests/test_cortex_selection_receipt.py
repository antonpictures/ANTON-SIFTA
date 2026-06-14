"""r948 — pre-dispatch cortex honesty receipt (codex r947 finding).

George selects Claude/Fable; a vision turn silently ran Gemma first. The
receipt must name selected vs worker_first and flag the mismatch out loud.
"""
import json

from System.swarm_cortex_selection_receipt import (
    LEDGER_NAME,
    decode_family_for_model,
    write_cortex_selection_receipt,
)


def _rows(state_dir):
    p = state_dir / LEDGER_NAME
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_mismatch_flagged_and_spoken(tmp_path):
    # Claude selected, but the vision ladder puts a local VLM first.
    row = write_cortex_selection_receipt(
        "claude:claude-code-cli-default",
        ["mlx-vlm:gemma-4-e2b-it", "claude:claude-code-cli-default", "alice-m5-cortex-8b-6.3gb:latest"],
        route_reason="vision_local_first",
        state_dir=tmp_path,
    )
    assert row["mismatch"] is True
    assert row["kind"] == "CORTEX_SELECTION_MISMATCH"
    assert "CORTEX_SELECTION_MISMATCH" in row["spoken_line"]
    assert row["selected_model"] == "claude:claude-code-cli-default"
    assert row["worker_first"] == "mlx-vlm:gemma-4-e2b-it"
    assert row["ledger_ok"] is True
    rows = _rows(tmp_path)
    assert len(rows) == 1 and rows[0]["mismatch"] is True


def test_aligned_dispatch_is_quiet(tmp_path):
    row = write_cortex_selection_receipt(
        "claude:claude-code-cli-default",
        ["claude:claude-code-cli-default", "alice-m5-cortex-8b-6.3gb:latest"],
        route_reason="talk_default_ladder",
        state_dir=tmp_path,
    )
    assert row["mismatch"] is False
    assert "spoken_line" not in row
    assert _rows(tmp_path)[0]["worker_first"] == "claude:claude-code-cli-default"
    assert row["decode_family"] == "autoregressive"
    assert row["selected_decode_family"] == "autoregressive"


def test_diffusiongemma_receipt_marks_usd_decode_family(tmp_path):
    row = write_cortex_selection_receipt(
        "mlx:diffusiongemma-26B-A4B-it-4bit",
        ["mlx:diffusiongemma-26B-A4B-it-4bit"],
        route_reason="diffusiongemma_phase0_probe",
        state_dir=tmp_path,
    )

    assert decode_family_for_model("diffusion:mlx-community/diffusiongemma-26B-A4B-it-4bit") == "usd"
    assert decode_family_for_model("alice-m5-cortex-8b-6.3gb:latest") == "autoregressive"
    assert row["decode_family"] == "usd"
    assert row["selected_decode_family"] == "usd"
    assert row["worker_first_decode_family"] == "usd"
    assert row["candidate_decode_families"]["mlx:diffusiongemma-26B-A4B-it-4bit"] == "usd"
    assert _rows(tmp_path)[0]["decode_family"] == "usd"


def test_pin_then_dispatch_honesty_r947(tmp_path, monkeypatch):
    # After the explicit Claude pin is set, a non-vision dispatch with claude
    # first must receipt aligned, and a vision reroute must receipt the truth.
    import os
    from System.swarm_alice_slash_commands import handle_slash_command

    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
    r = handle_slash_command("/cortex pin claude 1", state_dir=tmp_path, current_cortex="c")
    assert r["switched"] and os.environ["SIFTA_CLAUDE_ARM_MODEL"] == "claude-fable-5"
    aligned = write_cortex_selection_receipt(
        "claude:claude-code-cli-default",
        ["claude:claude-code-cli-default"],
        route_reason="talk_default_ladder",
        state_dir=tmp_path,
    )
    rerouted = write_cortex_selection_receipt(
        "claude:claude-code-cli-default",
        ["mlx-vlm:gemma-4-e2b-it", "claude:claude-code-cli-default"],
        route_reason="vision_local_first",
        state_dir=tmp_path,
    )
    assert aligned["mismatch"] is False
    assert rerouted["mismatch"] is True and "who is thinking" in rerouted["spoken_line"]
    monkeypatch.delenv("SIFTA_CLAUDE_ARM_MODEL", raising=False)
