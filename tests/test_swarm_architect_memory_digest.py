from __future__ import annotations

import json
from pathlib import Path

from System import swarm_architect_memory_digest as digest


def _append_jsonl(path: Path, *rows: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_architect_memory_digest_reads_reflections_receipts_and_docs(tmp_path: Path):
    repo = tmp_path
    state = repo / ".sifta_state"
    docs = repo / "Documents"
    docs.mkdir(parents=True)
    now = 1_778_999_000.0
    since = now - 3600

    (docs / "TEACHING_Alice_as_a_Different_Creature.md").write_text(
        "# Teaching\n\n"
        "The Architect taught Alice that memory symbiosis matters because George forgets, "
        "and receipts let tomorrow reopen the work without guessing.\n",
        encoding="utf-8",
    )
    _append_jsonl(
        state / "os_consciousness" / "alice_self_reflections.jsonl",
        {
            "ts": now - 120,
            "source": "alice_self",
            "reflection": (
                "The Architect is forgetting, so Alice must become a reliable external "
                "memory with receipts and purpose."
            ),
            "tags": ["architect_memory"],
        },
    )
    _append_jsonl(
        state / "work_receipts.jsonl",
        {
            "ts": now - 60,
            "kind": "CODEX_WORK_RECEIPT",
            "action": "CODEX_APP_HELP_SELF_CONTINUITY_TALK_WIRING",
            "doctor": "Codex",
            "receipt_id": "r1",
            "summary": "Wired app help, continuity, social field, and thermodynamic risk into Alice Talk.",
        },
    )

    out = digest.build_architect_memory_digest(
        repo_root=repo,
        state_dir=state,
        since_ts=since,
        until_ts=now,
        now=now,
        max_items=8,
    )

    assert out["ok"] is True
    assert out["status"] == "ARCHITECT_MEMORY_DIGEST_READY"
    assert "What George Taught Alice Today" in out["markdown"]
    assert "Current Alice Self Vector" in out["markdown"]
    assert "memory symbiosis" in out["markdown"].casefold()
    assert "CODEX_APP_HELP_SELF_CONTINUITY_TALK_WIRING" in out["markdown"]
    assert Path(out["latest_path"]).exists()
    assert Path(out["artifact_path"]).exists()
    receipt_path = Path(out["receipt_path"])
    assert receipt_path.exists()
    assert "ARCHITECT_MEMORY_DIGEST" in receipt_path.read_text(encoding="utf-8")


def test_architect_memory_digest_handles_empty_sources(tmp_path: Path):
    out = digest.build_architect_memory_digest(
        repo_root=tmp_path,
        state_dir=tmp_path / ".sifta_state",
        since_ts=100.0,
        until_ts=200.0,
        now=200.0,
        write_artifact=False,
    )

    assert out["ok"] is True
    assert "No matching work receipts" in out["markdown"]
    assert "No Alice self-reflection rows" in out["markdown"]
    assert "latest_path" not in out


def test_architect_memory_digest_stays_bounded(tmp_path: Path):
    repo = tmp_path
    state = repo / ".sifta_state"
    docs = repo / "Documents"
    docs.mkdir(parents=True)
    now = 1_778_999_000.0
    (docs / "TEACHING_Alice_as_a_Different_Creature.md").write_text(
        "\n".join(
            f"Memory symbiosis receipt teaching line {i}. George taught Alice purpose."
            for i in range(100)
        ),
        encoding="utf-8",
    )
    for i in range(80):
        _append_jsonl(
            state / "work_receipts.jsonl",
            {
                "ts": now - i,
                "action": f"RECEIPT_{i}",
                "summary": "Alice memory receipt purpose teaching continuity " * 5,
            },
        )

    out = digest.build_architect_memory_digest(
        repo_root=repo,
        state_dir=state,
        since_ts=now - 1000,
        until_ts=now,
        now=now,
        max_items=6,
        write_artifact=False,
    )

    assert len(out["markdown"].splitlines()) < 120
    assert out["counts"]["receipts"] <= 6
