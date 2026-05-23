import json

from System.swarm_mammal_token_ecology import (
    BindingSwimmer,
    ContradictionSwimmer,
    DreamReplaySwimmer,
    InflammationSwimmer,
    MemorySwimmer,
    MutationSwimmer,
    ScalarProjector,
    ToxicitySwimmer,
    TRUTH_LABEL,
    default_token_swimmers,
    run_mammal_token_ecology,
    run_token_ecology,
    token_metabolism,
)
from System.swarm_organ_tokenizer import (
    TT_GENERAL,
    TT_ORGAN,
    TT_SCALAR,
    TT_TOKEN,
    OrganToken,
)


def tok(tt, organ, value, field="field", ts=1.0):
    return OrganToken(type=tt, organ=organ, value=value, ts=ts, field=field)


def test_scalar_projector_is_deterministic_and_fixed_dim():
    p = ScalarProjector(dim=6)
    a = p.project("work_value", 12.5)
    b = p.project("work_value", 12.5)
    c = p.project("latency_ms", 12.5)
    assert a.vector == b.vector
    assert len(a.vector) == 6
    assert a.vector != c.vector


def test_default_pool_has_all_requested_swimmers():
    names = {type(s).__name__ for s in default_token_swimmers()}
    assert names == {
        "BindingSwimmer",
        "ContradictionSwimmer",
        "InflammationSwimmer",
        "MutationSwimmer",
        "ToxicitySwimmer",
        "MemorySwimmer",
        "DreamReplaySwimmer",
    }


def test_binding_swimmer_deposits_on_scalar_near_context():
    tokens = [
        tok(TT_ORGAN, "WORK", "WORK", "_organ"),
        tok(TT_TOKEN, "WORK", "MEMORY_STORE", "kind"),
        tok(TT_SCALAR, "WORK", 42.0, "work_value"),
    ]
    result = run_token_ecology(tokens, swimmers=[BindingSwimmer()])
    assert result["pheromones_by_type"]["BINDING_TRAIL"] == 1
    assert result["n_scalar_projections"] == 1


def test_named_swimmers_detect_expected_ecology_markers():
    tokens = [
        tok(TT_TOKEN, "TALK", "FORBIDDEN", "truth_label"),
        tok(TT_GENERAL, "KERNEL", "camera degraded exception", "payload"),
        tok(TT_GENERAL, "WORK", "patch changed the app", "description"),
        tok(TT_GENERAL, "BIO", "ClinTox toxicity cluster", "payload"),
        tok(TT_GENERAL, "DREAM", "dream replay reinforced", "line"),
    ]
    swimmers = [
        ContradictionSwimmer(),
        InflammationSwimmer(),
        MutationSwimmer(),
        ToxicitySwimmer(),
        DreamReplaySwimmer(),
    ]
    result = run_token_ecology(tokens, swimmers=swimmers)
    by_type = result["pheromones_by_type"]
    assert by_type["CONTRADICTION_STORM"] >= 1
    assert by_type["INFLAMMATION_SIGNAL"] >= 1
    assert by_type["MUTATION_ZONE"] >= 1
    assert by_type["TOXICITY_CLUSTER"] >= 1
    assert by_type["REPLAY_REINFORCED"] >= 1


def test_memory_swimmer_turns_repetition_into_memory_well():
    tokens = [
        tok(TT_GENERAL, "BIO", "EGFR", "gene"),
        tok(TT_GENERAL, "BIO", "EGFR", "gene"),
        tok(TT_GENERAL, "BIO", "EGFR", "gene"),
    ]
    result = run_token_ecology(tokens, swimmers=[MemorySwimmer()])
    assert result["pheromones_by_type"]["MEMORY_WELL"] == 3
    assert result["metabolism"]["stabilized_tokens"] >= 1


def test_token_metabolism_evaporates_unreinforced_and_stabilizes_reinforced():
    tokens = [tok(TT_GENERAL, "BIO", "one"), tok(TT_GENERAL, "BIO", "two")]
    low = token_metabolism(tokens, [])
    high = token_metabolism(tokens, [
        type("P", (), {"token_index": 0, "strength": 1.0})(),
        type("P", (), {"token_index": 1, "strength": 1.0})(),
    ])
    assert high["mean_energy"] > low["mean_energy"]
    assert high["stabilized_tokens"] >= low["stabilized_tokens"]


def test_run_mammal_token_ecology_from_temp_ledgers_writes_receipt(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "work_receipts.jsonl").write_text(
        json.dumps({"ts": 1.0, "kind": "MEMORY_STORE", "work_value": 5.0, "description": "patch changed EGFR token"}) + "\n",
        encoding="utf-8",
    )
    result = run_mammal_token_ecology(state_root=state, last_n_per_ledger=5, write=True)
    assert result["truth_label"] == TRUTH_LABEL
    assert result["n_tokens"] > 0
    assert result["n_pheromones"] > 0
    ledger = state / "mammal_token_ecology_receipts.jsonl"
    assert ledger.exists()
    row = json.loads(ledger.read_text().splitlines()[-1])
    assert row["truth_label"] == TRUTH_LABEL
