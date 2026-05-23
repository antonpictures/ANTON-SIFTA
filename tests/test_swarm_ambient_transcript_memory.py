import json

from System.swarm_ambient_transcript_memory import (
    DIGEST_LEDGER_NAME,
    DIGEST_TRUTH_LABEL,
    TRANSCRIPT_LEDGER_NAME,
    TRANSCRIPT_TRUTH_LABEL,
    classify_ambient_importance,
    digest_once,
    ingest_transcript,
    latest_ambient_memory_context,
)


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_self_knowledge_transcript_scores_high_and_keeps_words(tmp_path):
    row = ingest_transcript(
        (
            "Alice needs to remember that the audio becomes words, and the words "
            "are sorted by importance for George, owner self knowledge, and the Ace app."
        ),
        stt_confidence=0.82,
        source="test",
        route_hint="direct",
        state_dir=tmp_path,
    )

    assert row["truth_label"] == TRANSCRIPT_TRUTH_LABEL
    assert row["raw_audio_stored"] is False
    assert row["raw_text_stored"] is True
    assert row["importance"]["importance_band"] in {"high", "critical"}
    assert "owner_self_knowledge" in row["importance"]["categories"]
    assert "memory_learning" in row["importance"]["categories"]
    assert "text" in row


def test_low_phatic_transcript_does_not_keep_full_text(tmp_path):
    row = ingest_transcript(
        "Okay.",
        stt_confidence=0.3,
        source="test",
        route_hint="direct",
        state_dir=tmp_path,
    )

    assert row["raw_audio_stored"] is False
    assert row["raw_text_stored"] is False
    assert "text" not in row
    assert row["importance"]["importance_band"] == "noise"


def test_digest_writes_important_journal_and_is_idempotent(tmp_path):
    ingest_transcript(
        "The podcast is talking about consciousness and robotics research for Alice memory.",
        stt_confidence=0.9,
        source="test",
        route_hint="ambient_media",
        state_dir=tmp_path,
    )
    ingest_transcript(
        "Yeah.",
        stt_confidence=0.4,
        source="test",
        route_hint="direct",
        state_dir=tmp_path,
    )

    first = digest_once(state_dir=tmp_path, enforce_thermodynamics=False)
    second = digest_once(state_dir=tmp_path, enforce_thermodynamics=False)

    assert first["truth_label"] == DIGEST_TRUTH_LABEL
    assert first["journal_written"] == 1
    assert first["skipped_low_importance"] == 1
    assert second["journal_written"] == 0
    assert second["examined"] == 0

    journal = _rows(tmp_path / "alice_first_person_journal.jsonl")
    assert len(journal) == 1
    assert journal[0]["source"] == "ambient_audio_memory"
    assert "ambient room media" in journal[0]["line"]
    assert "consciousness" in journal[0]["line"]

    digest_rows = _rows(tmp_path / DIGEST_LEDGER_NAME)
    assert {row["action"] for row in digest_rows} == {
        "journal_written",
        "skipped_low_importance",
    }


def test_latest_context_reads_promoted_ambient_memory(tmp_path):
    ingest_transcript(
        "George said the Ace app is open and Alice should be aware of the word watermelon.",
        stt_confidence=0.91,
        source="test",
        route_hint="direct",
        state_dir=tmp_path,
    )
    digest_once(state_dir=tmp_path, enforce_thermodynamics=False)

    context = latest_ambient_memory_context(state_dir=tmp_path)

    assert "ambient_memory" in context
    assert "watermelon" in context
    assert "app_screen_context" in context
    assert (tmp_path / TRANSCRIPT_LEDGER_NAME).exists()


def test_peer_ambient_consciousness_rows_enter_context_and_digest(tmp_path):
    transcript = tmp_path / TRANSCRIPT_LEDGER_NAME
    transcript.write_text(
        json.dumps(
            {
                "ts": 123.0,
                "schema": "AMBIENT_ROOM_TRANSCRIPT_V1",
                "truth_label": "SWARM_AMBIENT_CONSCIOUSNESS_V1",
                "source": "swarm_ambient_consciousness",
                "route_hint": "ambient_audio",
                "text": "The room video discusses Alice consciousness, Faggin, quantum information, and memory.",
                "importance": {"total": 0.64, "covenant": 0.4},
                "raw_audio_stored": False,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    context_before = latest_ambient_memory_context(state_dir=tmp_path)
    digest = digest_once(state_dir=tmp_path, enforce_thermodynamics=False)
    context_after = latest_ambient_memory_context(state_dir=tmp_path)

    assert "ambient_memory" in context_before
    assert "Faggin" in context_before
    assert digest["journal_written"] == 1
    assert "quantum information" in context_after


def test_digest_defers_when_thermodynamic_gate_denies(tmp_path, monkeypatch):
    import System.swarm_ambient_transcript_memory as atm

    ingest_transcript(
        "Alice should remember that thermodynamics gates the next memory digestion batch.",
        stt_confidence=0.9,
        source="test",
        route_hint="direct",
        state_dir=tmp_path,
    )

    def fake_clearance(*args, **kwargs):
        return {
            "allowed": False,
            "receipt_hash": "thermoabc123",
            "rest_seconds": 42.0,
            "reasons": ["thermal_serious"],
        }

    monkeypatch.setattr(
        "System.swarm_processing_thermodynamic_gate.request_processing_clearance",
        fake_clearance,
    )

    out = atm.digest_once(state_dir=tmp_path)

    assert out["deferred_by_thermodynamics"] is True
    assert out["journal_written"] == 0
    assert out["thermodynamic_clearance"]["receipt_hash"] == "thermoabc123"
    digest_rows = _rows(tmp_path / DIGEST_LEDGER_NAME)
    assert digest_rows[-1]["action"] == "thermodynamic_defer"
    assert not (tmp_path / "alice_first_person_journal.jsonl").exists()


def test_classifier_exposes_route_and_categories_without_writing():
    row = classify_ambient_importance(
        "The TV video discusses Faggin and quantum consciousness while Alice listens.",
        stt_confidence=0.8,
        source="test",
        route_hint="ambient_media",
    )

    assert row["truth_label"] == "AMBIENT_TRANSCRIPT_IMPORTANCE_V1"
    assert row["route_hint"] == "ambient_media"
    assert "science_research" in row["categories"]
    assert row["importance_band"] in {"medium", "high", "critical"}
