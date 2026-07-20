from __future__ import annotations

from System import swarm_codex_alice_grok_cocode as cocode


def test_cocode_session_writes_receipt_and_global_chat(monkeypatch, tmp_path):
    logged = []

    monkeypatch.setattr(
        cocode,
        "_log_global_chat",
        lambda role, text, *, model, metadata: logged.append((role, text, model, metadata)) or True,
    )

    row = cocode.run_codex_alice_grok_cocode_session(
        "Please code with Grok while I watch.",
        coded_summary="We Code Together proof lane patched.",
        tests_summary="3 passed",
        grok_status="auth failed but pulse visible",
        receipt_ids=["grok-pulse-test"],
        state_dir=tmp_path,
        now=123.0,
    )

    assert row["truth_label"] == cocode.TRUTH_LABEL
    assert row["action"] == "codex_alice_grok_cocode_session"
    assert row["global_chat_user_logged"] is True
    assert row["global_chat_alice_logged"] is True
    assert logged[0][0] == "user"
    assert logged[1][0] == "alice"
    assert "What I need for more AGI" in logged[1][1]
    assert cocode.latest_cocode_sessions(state_dir=tmp_path)[-1]["receipt_id"] == row["receipt_id"]
