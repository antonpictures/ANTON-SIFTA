import importlib.util
import json
import sys
from pathlib import Path


def _load_viewer_module():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "Applications" / "sifta_alice_journal_viewer.py"
    spec = importlib.util.spec_from_file_location("sifta_alice_journal_viewer", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_journal_viewer_prints_compact_local_journal_label(tmp_path, capsys):
    viewer = _load_viewer_module()
    journal_dir = tmp_path / "alice_journal"
    journal_dir.mkdir()
    (journal_dir / "2026-05-11.jsonl").write_text(
        json.dumps(
            {
                "ts": 1_778_534_640.0,
                "local_journal_label": "05-11-26_14:24",
                "kind": "EPISODIC_NARRATIVE",
                "event_type": "turn",
                "entry": "George asked me to keep better journal dates.",
                "truth_label": "OBSERVED",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    viewer._JOURNAL_DIR = journal_dir
    viewer._LEGACY = tmp_path / "missing_legacy.jsonl"
    viewer._PHONE = tmp_path / "missing_phone.jsonl"

    viewer.show_journal(show_all=True)

    out = capsys.readouterr().out
    assert "05-11-26_14:24 | turn" in out
    assert "George asked me to keep better journal dates." in out
