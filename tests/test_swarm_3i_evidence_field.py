from __future__ import annotations

import json

from System import swarm_3i_evidence_field as field


def test_seed_public_evidence_and_snapshot(tmp_path):
    written = field.seed_public_evidence_deposits(state_dir=tmp_path)

    assert len(written) >= 6
    assert all(row["truth_label"] == field.TRUTH_LABEL for row in written)
    assert all(row["receipt"] for row in written)

    snapshot = field.field_snapshot(state_dir=tmp_path, now=written[-1]["ts"])
    assert snapshot["object_id"] == field.OBJECT_ID
    assert snapshot["deposit_count"] == len(written)
    assert snapshot["by_lane"]["orbit_dynamics"] > 0
    assert snapshot["by_lane"]["chemistry"] > 0
    assert snapshot["by_source_type"]["JPL_HORIZONS"] > 0
    assert snapshot["total_stgm_reward_hint"] > 0
    assert snapshot["swimmer_actions"]


def test_add_claim_and_falsification_change_field(tmp_path):
    claim = field.add_claim(
        "non_grav_acceleration",
        "Sideways acceleration needs a residual refit before it is promoted.",
        state_dir=tmp_path,
    )
    falsification = field.add_falsification(
        lane="non_grav_acceleration",
        title="Toy refit rejects unsupported anomaly wording",
        claim="Residuals are consistent with published non-gravitational comet parameters in this toy check.",
        confidence=0.8,
        state_dir=tmp_path,
    )

    rows = field.deposits(state_dir=tmp_path, now=falsification["ts"])
    assert {row.kind for row in rows} == {"CLAIM", "FALSIFICATION"}
    snapshot = field.field_snapshot(state_dir=tmp_path, now=falsification["ts"])
    assert snapshot["by_lane"]["non_grav_acceleration"] < claim["confidence"]


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _n):
        return b'{"result":"$$SOE\\n2450000.5, 1.0, 2.0, 3.0\\n$$EOE"}'


def test_fetch_jpl_horizons_receipt_is_hash_bound(monkeypatch, tmp_path):
    def fake_urlopen(_request, timeout):
        assert timeout == 3.0
        return _FakeResponse()

    monkeypatch.setattr(field, "urlopen", fake_urlopen)
    row = field.fetch_jpl_horizons(state_dir=tmp_path, timeout_s=3.0)

    assert row["kind"] == "FETCH_RECEIPT"
    assert row["source_type"] == "JPL_HORIZONS"
    assert row["payload"]["ok"] is True
    assert row["payload"]["result_sha256"] == field.evidence_hash(_FakeResponse().read(0).decode())
    assert field.field_snapshot(state_dir=tmp_path)["latest_fetch"]["receipt"] == row["receipt"]


def test_manifest_registers_interstellar_crucible():
    manifest = json.loads((field._REPO / "Applications" / "apps_manifest.json").read_text())
    app = manifest["SIFTA Interstellar Evidence Crucible"]

    assert app["entry_point"] == "Applications/sifta_interstellar_evidence_crucible.py"
    assert app["widget_class"] == "InterstellarEvidenceCrucibleApp"
    assert app["truth_label"] == field.TRUTH_LABEL
