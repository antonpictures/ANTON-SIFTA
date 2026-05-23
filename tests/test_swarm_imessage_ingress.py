import importlib.util
import json
from pathlib import Path

from System import swarm_imessage_receptor as ingress


SECRET = "test-imessage-ingress-secret"


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_imessage", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_signed_inbox_row_validates():
    row = ingress.build_inbox_row(
        "bring up the ledger",
        rowid=42,
        handle_id=7,
        secret=SECRET,
        ts=123.0,
    )

    ok, reason = ingress.validate_inbox_row(row, secret=SECRET)

    assert ok is True
    assert reason == "ok"
    assert row["schema"] == ingress.INBOX_SCHEMA
    assert row["source"] == ingress.INBOX_SOURCE
    assert len(row["signature"]) == 64


def test_tampered_or_legacy_rows_are_rejected():
    row = ingress.build_inbox_row("valid text", rowid=43, handle_id=7, secret=SECRET)
    tampered = dict(row)
    tampered["text"] = "changed after signing"

    ok, reason = ingress.validate_inbox_row(tampered, secret=SECRET)

    assert ok is False
    assert reason in {"message_hash_mismatch", "signature_mismatch"}
    ok, reason = ingress.validate_inbox_row({"text": "legacy row", "processed": False}, secret=SECRET)
    assert ok is False
    assert reason == "schema_mismatch"


def test_consume_valid_message_writes_processed_receipt(tmp_path):
    inbox = tmp_path / "imessage_inbox.jsonl"
    receipts = tmp_path / "imessage_ingress_receipts.jsonl"
    row = ingress.build_inbox_row(
        "run the dry check first",
        rowid=44,
        handle_id=9,
        secret=SECRET,
        ts=100.0,
    )
    inbox.write_text(json.dumps(row) + "\n", encoding="utf-8")

    result = ingress.consume_next_inbox_message(
        inbox,
        receipt_file=receipts,
        secret=SECRET,
        now=200.0,
    )

    assert result["accepted"] is True
    assert result["text"] == "run the dry check first"
    stored = json.loads(inbox.read_text(encoding="utf-8"))
    assert stored["processed"] is True
    assert stored["processed_status"] == "accepted"
    assert stored["consume_receipt_hash"] == result["receipt"]["receipt_hash"]
    receipt = json.loads(receipts.read_text(encoding="utf-8"))
    assert receipt["event_kind"] == "IMESSAGE_INGRESS_CONSUME"
    assert receipt["consumer"] == ingress.INBOX_CONSUMER


def test_consume_ignores_invalid_and_prevents_duplicate_replay(tmp_path):
    inbox = tmp_path / "imessage_inbox.jsonl"
    receipts = tmp_path / "receipts.jsonl"
    valid = ingress.build_inbox_row("one shot", rowid=45, handle_id=11, secret=SECRET)
    duplicate = dict(valid)
    invalid = {"schema": ingress.INBOX_SCHEMA, "source": "forged", "text": "bad"}
    inbox.write_text(
        "\n".join(json.dumps(row) for row in (invalid, valid, duplicate)) + "\n",
        encoding="utf-8",
    )

    first = ingress.consume_next_inbox_message(inbox, receipt_file=receipts, secret=SECRET)
    second = ingress.consume_next_inbox_message(inbox, receipt_file=receipts, secret=SECRET)

    assert first["accepted"] is True
    assert first["text"] == "one shot"
    assert second["accepted"] is False
    assert second["reason"] == "no_valid_unprocessed_message"
    rows = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["source"] == "forged"
    assert rows[1]["processed_status"] == "accepted"
    assert rows[2]["processed_status"] == "duplicate"
    assert len(receipts.read_text(encoding="utf-8").splitlines()) == 1


def test_dry_run_does_not_mutate_inbox_or_receipts(tmp_path):
    inbox = tmp_path / "imessage_inbox.jsonl"
    receipts = tmp_path / "receipts.jsonl"
    row = ingress.build_inbox_row("simulate only", rowid=46, handle_id=13, secret=SECRET)
    original = json.dumps(row) + "\n"
    inbox.write_text(original, encoding="utf-8")

    result = ingress.consume_next_inbox_message(
        inbox,
        receipt_file=receipts,
        dry_run=True,
        secret=SECRET,
    )

    assert result["accepted"] is True
    assert result["dry_run"] is True
    assert inbox.read_text(encoding="utf-8") == original
    assert not receipts.exists()


def test_widget_dry_run_appends_but_does_not_start_brain(monkeypatch):
    widget = _load_widget_module()

    class Dummy:
        _busy = False
        _imessage_ingress_dry_run = True

        def __init__(self):
            self.lines = []
            self.started = False

        def _append_user_line(self, text):
            self.lines.append(text)

        def _set_pill(self, *_args):
            raise AssertionError("dry-run should not touch thinking state")

        def _start_brain(self, *_args):
            self.started = True

    monkeypatch.setattr(
        ingress,
        "consume_next_inbox_message",
        lambda **kwargs: {
            "accepted": True,
            "text": "authorized text",
            "dry_run": kwargs.get("dry_run"),
        },
    )
    dummy = Dummy()

    widget.TalkToAliceWidget._poll_imessage_inbox(dummy)

    assert dummy.lines == ["[iMessage]: authorized text"]
    assert dummy.started is False
