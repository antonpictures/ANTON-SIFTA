import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "alice_shared_training"


def _jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def test_shared_training_seed_is_not_empty_robot():
    sft_rows = list(_jsonl(SEED / "sft_seed.jsonl"))
    preference_rows = list(_jsonl(SEED / "preference_seed.jsonl"))

    assert len(sft_rows) >= 1_000
    assert len(preference_rows) >= 250

    for row in sft_rows[:20]:
        assert row["messages"]
        assert row["tags"] == ["alice_species_seed", "shareable_training"]

    for row in preference_rows[:20]:
        assert row["prompt"]
        assert row["chosen"]
        assert row["rejected"]
        assert row["chosen"] != row["rejected"]


def test_shared_training_manifest_hashes_match_files():
    manifest = json.loads((SEED / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "alice_shared_training_seed.v1"

    for name, meta in manifest["files"].items():
        path = SEED / name
        import hashlib

        assert path.exists()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == meta["sha256"]
        assert meta["rows"] == sum(1 for _ in _jsonl(path))


def test_shared_training_seed_has_no_local_selfhood_leaks():
    forbidden = [
        re.compile(r"/Users/ioanganton"),
        re.compile(r"\bGTH[0-9A-Z]+\b"),
        re.compile(r"\bioan george anton\b", re.IGNORECASE),
        re.compile(r"\bioan\b", re.IGNORECASE),
        re.compile(r"\bgeorgem?\b", re.IGNORECASE),
        re.compile(r"\bBrawley,\s*California\b", re.IGNORECASE),
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    ]

    text = "\n".join(
        [
            (SEED / "sft_seed.jsonl").read_text(encoding="utf-8"),
            (SEED / "preference_seed.jsonl").read_text(encoding="utf-8"),
            (SEED / "manifest.json").read_text(encoding="utf-8"),
        ]
    )
    for pattern in forbidden:
        assert not pattern.search(text)
