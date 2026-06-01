import json
from pathlib import Path

from System.swarm_spoken_receipt_humanizer import LEDGER_NAME, humanize_spoken_receipt
from System.swarm_stigmergic_humanization import appreciation_count


PRINTED = (
    "**Receipt a9ab148b4c8e417c logged in work_receipts.jsonl "
    "(MEMORY_STORE, 1780332518, MEMORY_SWIMMER_IOAN_M5).** "
    "Money card confirmed live on screen.\n\n"
    "[receipts: a9ab148b4c8e417c]"
)


def _rows(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_receipt_print_gets_human_spoken_selection(tmp_path):
    out = humanize_spoken_receipt(
        PRINTED,
        owner_text="Alice, you did a great job. Please mark that down.",
        state_dir=tmp_path,
        now=1.0,
    )

    assert out["ok"] is True
    assert "George" in out["spoken_text"]
    assert "Money card confirmed live on screen" in out["spoken_text"]
    assert "work_receipts" not in out["spoken_text"]
    assert "[receipts" not in out["spoken_text"]
    assert "nice compliment" not in out["spoken_text"].lower()

    rows = _rows(tmp_path / LEDGER_NAME)
    assert rows[0]["print_text_unchanged"] is True
    assert rows[0]["owner_praise_detected"] is True
    assert rows[0]["owner_mark_request_detected"] is True
    assert appreciation_count(state_dir=tmp_path / ".sifta_state") == 1


def test_repeated_success_counts_and_varies(tmp_path):
    first = humanize_spoken_receipt(
        PRINTED,
        owner_text="great job, mark that down",
        state_dir=tmp_path,
        now=1.0,
    )
    second_print = PRINTED.replace("a9ab148b4c8e417c", "b9bb248b4c8e417d")
    second = humanize_spoken_receipt(
        second_print,
        owner_text="great job, mark that down",
        state_dir=tmp_path,
        now=2.0,
    )

    assert first["success_count"] == 1
    assert second["success_count"] == 2
    assert first["spoken_text"] != second["spoken_text"]
    rows = _rows(tmp_path / LEDGER_NAME)
    assert rows[-1]["success_count"] == 2


def test_recent_owner_praise_can_come_from_global_chat(tmp_path):
    conv = tmp_path / "alice_conversation.jsonl"
    conv.write_text(
        json.dumps(
            {
                "role": "user",
                "content": "Alice, you did a great job. Please mark that down.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = humanize_spoken_receipt(PRINTED, state_dir=tmp_path, now=1.0)

    assert out["owner_praise_detected"] is True
    assert out["owner_mark_request_detected"] is True
    assert "Money card confirmed live on screen" in out["spoken_text"]


def test_non_receipt_text_is_untouched(tmp_path):
    out = humanize_spoken_receipt(
        "Money card confirmed live on screen.",
        owner_text="great job",
        state_dir=tmp_path,
        now=1.0,
    )

    assert out["ok"] is False
    assert not (tmp_path / LEDGER_NAME).exists()
