from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from System.sifta_nvidia_join import (
    NVIDIA_ASSETS,
    probe_assets,
    readiness_summary,
    recommended_next_step,
    write_probe_receipt,
)


def _cosmos_rcpt(tmp_path: Path) -> Path:
    """Isolated ledger so tests never read the Architect's real inference receipts."""
    return tmp_path / "cosmos_test_receipts.jsonl"


def test_nvidia_asset_catalog_has_required_public_surfaces():
    keys = {asset.key for asset in NVIDIA_ASSETS}
    assert keys == {
        "groot_n17_3b",
        "groot_x_embodiment_sim",
        "isaac_lab",
        "curobo",
        "warp",
        "cosmos",
    }
    assert all(asset.official_url.startswith("https://") for asset in NVIDIA_ASSETS)
    assert any("IsaacStigmergicStub" in asset.sifta_hook for asset in NVIDIA_ASSETS)


def test_probe_assets_does_not_fake_real_on_clean_macos_cache(tmp_path):
    probes = probe_assets(
        cache_root=tmp_path,
        import_checker=lambda _module: False,
        platform_name="Darwin",
        gecko_probe=lambda: {"truth": "STUB", "version": None, "device": "cpu", "error": None},
        cosmos_receipts_path=_cosmos_rcpt(tmp_path),
    )
    by_key = {probe.key: probe for probe in probes}

    assert by_key["groot_n17_3b"].local_truth == "ONLINE"
    assert by_key["groot_x_embodiment_sim"].local_truth == "ONLINE"
    assert by_key["isaac_lab"].local_truth == "STUB"
    assert by_key["curobo"].local_truth == "BLOCKED"
    assert by_key["warp"].local_truth == "ONLINE"
    assert by_key["cosmos"].local_truth == "ONLINE"
    assert readiness_summary(probes) == {"REAL": 0, "STUB": 1, "ONLINE": 4, "BLOCKED": 1}


def test_probe_assets_marks_local_cache_and_imports_real(tmp_path):
    (tmp_path / "hub" / "models--nvidia--GR00T-N1.7-3B").mkdir(parents=True)
    (tmp_path / "hub" / "datasets--nvidia--PhysicalAI-Robotics-GR00T-X-Embodiment-Sim").mkdir(parents=True)
    # Cosmos-Reason1 weights alone do not promote to REAL without inference receipt.
    (tmp_path / "hub" / "models--nvidia--Cosmos-Reason1-7B").mkdir(parents=True)

    probes = probe_assets(
        cache_root=tmp_path,
        import_checker=lambda module: module in {"warp", "curobo", "isaaclab"},
        platform_name="Linux",
        gecko_probe=lambda: {"truth": "STUB", "version": None, "device": "cpu", "error": None},
        cosmos_receipts_path=_cosmos_rcpt(tmp_path),
    )
    by_key = {probe.key: probe for probe in probes}

    assert by_key["groot_n17_3b"].local_truth == "REAL"
    assert by_key["groot_x_embodiment_sim"].local_truth == "REAL"
    assert by_key["isaac_lab"].local_truth == "REAL"
    assert by_key["curobo"].local_truth == "REAL"
    assert by_key["warp"].local_truth == "REAL"
    assert by_key["cosmos"].local_truth == "ONLINE"
    assert "inference" in by_key["cosmos"].local_detail.lower()
    assert readiness_summary(probes)["REAL"] == 5


def test_probe_assets_uses_gecko_warp_truth_when_available(tmp_path):
    probes = probe_assets(
        cache_root=tmp_path,
        import_checker=lambda _module: False,
        platform_name="Darwin",
        gecko_probe=lambda: {
            "truth": "REAL_CPU",
            "version": "1.12.1",
            "device": "cpu",
            "cuda_reported": False,
            "error": None,
        },
        cosmos_receipts_path=_cosmos_rcpt(tmp_path),
    )
    warp = {probe.key: probe for probe in probes}["warp"]

    assert warp.local_truth == "REAL"
    assert "REAL_CPU" in warp.local_detail
    assert "warp 1.12.1" in warp.local_detail


def test_probe_assets_marks_broken_gecko_probe_blocked(tmp_path):
    probes = probe_assets(
        cache_root=tmp_path,
        import_checker=lambda _module: False,
        platform_name="Darwin",
        gecko_probe=lambda: {"truth": "BROKEN", "error": "kernel smoke failed"},
        cosmos_receipts_path=_cosmos_rcpt(tmp_path),
    )
    warp = {probe.key: probe for probe in probes}["warp"]

    assert warp.local_truth == "BLOCKED"
    assert "kernel smoke failed" in warp.local_detail


def test_write_probe_receipt_is_jsonl_and_explains_truth(tmp_path):
    probes = probe_assets(
        cache_root=tmp_path,
        import_checker=lambda _module: False,
        platform_name="Darwin",
        gecko_probe=lambda: {"truth": "STUB", "version": None, "device": "cpu", "error": None},
        cosmos_receipts_path=_cosmos_rcpt(tmp_path),
    )
    receipt = write_probe_receipt(probes, path=tmp_path / "nvidia_join_receipts.jsonl", writer="pytest")

    line = (tmp_path / "nvidia_join_receipts.jsonl").read_text(encoding="utf-8").strip()
    decoded = json.loads(line)
    assert decoded == receipt
    assert decoded["writer"] == "pytest"
    assert "ONLINE is not runtime access" in decoded["truth_note"]
    assert len(decoded["assets"]) == len(NVIDIA_ASSETS)


def test_recommended_next_step_prefers_local_warp(tmp_path):
    probes = probe_assets(
        cache_root=tmp_path,
        import_checker=lambda module: module == "warp",
        platform_name="Darwin",
        gecko_probe=lambda: {"truth": "STUB", "version": None, "device": "cpu", "error": None},
        cosmos_receipts_path=_cosmos_rcpt(tmp_path),
    )
    msg = recommended_next_step(probes)
    assert msg.startswith("Warp is REAL") and "Cosmos" in msg


_QT_APP: QApplication | None = None


def _app() -> QApplication:
    global _QT_APP
    existing = QApplication.instance()
    if existing is not None:
        return existing
    _QT_APP = QApplication([])
    return _QT_APP


def test_nvidia_join_widget_smoke(tmp_path, monkeypatch):
    from Applications import sifta_nvidia_join_widget as appmod

    fake_receipt = {
        "summary": {"REAL": 0, "STUB": 1, "ONLINE": 4, "BLOCKED": 1},
        "truth_note": "REAL means local package/cache exists; ONLINE is not runtime access.",
        "assets": [
            {
                "key": "isaac_lab",
                "name": "Isaac Lab",
                "asset_type": "robotics RL / simulation framework",
                "local_truth": "STUB",
                "official_url": "https://github.com/isaac-sim/IsaacLab",
                "local_probe": "python_import:isaaclab|omni.isaac.core",
                "local_detail": "SIFTA IsaacStigmergicStub present; vendor runtime missing",
                "sifta_hook": "replace IsaacStigmergicStub with scene stepper when runtime exists",
                "next_step": "keep STUB on macOS unless Isaac runtime is installed",
                "risk_note": "vendor simulator; no physical actuator control without safety review",
            }
        ],
    }
    receipt_path = tmp_path / "nvidia_join_receipts.jsonl"
    receipt_path.write_text(json.dumps(fake_receipt) + "\n", encoding="utf-8")

    monkeypatch.setattr(appmod, "DEFAULT_RECEIPT_PATH", receipt_path)
    monkeypatch.setattr(appmod, "probe_and_write_receipt", lambda *, writer: fake_receipt)
    monkeypatch.setattr(appmod, "publish_focus", lambda *args, **kwargs: None)

    _app()
    widget = appmod.NvidiaJoinWidget()
    try:
        assert widget._gci_visible is False
        assert widget._summary.text() == "REAL=0 STUB=1 ONLINE=4 BLOCKED=1"
        assert widget._table.rowCount() == 1
        assert widget._table.item(0, 0).text() == "STUB"
        assert "Isaac Lab" in widget._receipts.toPlainText()
    finally:
        widget.close()


def test_nvidia_join_manifest_row():
    repo = Path(__file__).resolve().parent.parent
    manifest = json.loads((repo / "Applications" / "apps_manifest.json").read_text(encoding="utf-8"))
    row = manifest["NVIDIA \u00d7 SIFTA"]

    assert row["category"] == "Developer"
    assert row["entry_point"] == "Applications/sifta_nvidia_join_widget.py"
    assert row["widget_class"] == "NvidiaJoinWidget"
    assert "GR00T" in row["description"]
    assert "REAL" in row["description"]
    assert "NVIDIA Joins SIFTA" not in manifest
