from __future__ import annotations

import json
from datetime import datetime, timezone

from System.swarm_seed_deal_milestones import (
    DEFAULT_MILESTONES,
    evaluate_seed_deal_milestones,
    format_posterior_for_crucible,
)


def _append(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_seed_deal_milestones_match_receipt_evidence(tmp_path):
    state = tmp_path / ".sifta_state"
    _append(
        state / "work_receipts.jsonl",
        {
            "kind": "MILESTONE_DONE",
            "description": "Malibu lease executed for 3966 Las Flores Canyon Road.",
        },
    )

    post = evaluate_seed_deal_milestones(
        root=tmp_path,
        now=datetime(2026, 5, 18, tzinfo=timezone.utc),
        write_ledger=False,
    )
    lease = next(s for s in post.swimmers if s.milestone_id == "malibu_lease")

    assert lease.evidence_hits == 1
    assert lease.complete_p > lease.at_risk_p
    assert lease.evidence_refs == ("work_receipts.jsonl",)
    assert post.summary["COMPLETE"] >= 1


def test_seed_deal_posterior_is_append_only_and_fresh_swimmers(tmp_path):
    first = evaluate_seed_deal_milestones(
        root=tmp_path,
        milestones=DEFAULT_MILESTONES[:2],
        now=datetime(2026, 5, 18, tzinfo=timezone.utc),
        write_ledger=True,
    )
    second = evaluate_seed_deal_milestones(
        root=tmp_path,
        milestones=DEFAULT_MILESTONES[:2],
        now=datetime(2026, 5, 18, tzinfo=timezone.utc),
        write_ledger=True,
    )

    ledger = tmp_path / ".sifta_state" / "seed_deal_milestone_posteriors.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]

    assert len(rows) == 2
    assert first.posterior_id != second.posterior_id
    assert {s.swimmer_id for s in first.swimmers}.isdisjoint({s.swimmer_id for s in second.swimmers})


def test_seed_deal_posterior_format_is_owner_readable(tmp_path):
    post = evaluate_seed_deal_milestones(
        root=tmp_path,
        milestones=DEFAULT_MILESTONES[:1],
        now=datetime(2026, 5, 18, tzinfo=timezone.utc),
        write_ledger=False,
    )
    text = format_posterior_for_crucible(post)

    assert "MILESTONE SWIMMERS LIVE" in text
    assert "Execute Malibu LAB lease" in text
    assert "P[c/o/r]" in text
