from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_ide_boot_identity import (
    OPAQUE_MODEL_LABEL,
    boot_glyph_reference,
    classify_model_claim,
    decode_tripartite_boot_seal,
    detect_ide_app_id,
    is_opaque_model_label,
    real_time_iso,
    resolve_boot_identity,
    resolve_current_boot_identity,
    tripartite_boot_seal,
)


def _write_rows(path: Path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_resolves_latest_active_cursor_identity(tmp_path: Path):
    reg = tmp_path / "ide_model_registry.jsonl"
    _write_rows(
        reg,
        [
            {
                "ide_app_id": "cursor",
                "ide_surface": "cursor_ide_m5",
                "currently_active": True,
                "trigger_code": "C47H",
                "model_label": "Opus 4.7 High",
                "grounding_label": "OLD",
                "seen_at_ts": 1.0,
            },
            {
                "ide_app_id": "cursor",
                "ide_surface": "cursor_ide_m5",
                "currently_active": False,
                "trigger_code": "G55M",
                "model_label": "GPT-5.5 Medium",
                "grounding_label": "RETRACTED",
                "seen_at_ts": 2.0,
            },
            {
                "ide_app_id": "cursor",
                "ide_surface": "cursor_ide_m5",
                "currently_active": True,
                "trigger_code": "CG55M",
                "model_label": "GPT-5.5 Medium",
                "ui_badge": "Medium",
                "grounding_label": "ARCHITECT_UI_TRUTH",
                "seen_at_ts": 3.0,
            },
        ],
    )

    ident = resolve_boot_identity("cursor", registry_path=reg)

    assert ident.trigger_code == "CG55M"
    assert ident.model_label == "GPT-5.5 Medium"
    assert ident.declared_model_label == "GPT-5.5 Medium"
    assert ident.model_claim().router_visible is True
    assert ident.stigauth_line() == "CG55M@cursor: GPT-5.5 Medium [ARCHITECT_UI_TRUTH]"
    assert ident.signature_line(now=1_777_057_500.0).startswith(
        "CG55M@cursor: GPT-5.5 Medium [ARCHITECT_UI_TRUTH] "
        "last_known_real_time="
    )
    assert ident.identity_banner() == "CG55M@cursor_ide_m5 / GPT-5.5 Medium / Cursor IDE"
    glyph = ident.stigmergic_boot_glyph()
    assert glyph.startswith("SIFTA_IDE_BOOT_GLYPH|v=1|")
    assert "trigger=CG55M" in glyph
    assert "ide=cursor" in glyph
    assert "confidence=declared_exact" in glyph
    assert "last_real_time=" in glyph
    assert "rule=body_first_no_double_spend" in glyph
    assert f"seal={tripartite_boot_seal()}" in glyph


def test_rejects_cursor_identity_without_cursor_prefix(tmp_path: Path):
    reg = tmp_path / "ide_model_registry.jsonl"
    _write_rows(
        reg,
        [
            {
                "ide_app_id": "cursor",
                "ide_surface": "cursor_ide_m5",
                "currently_active": True,
                "trigger_code": "G55M",
                "model_label": "GPT-5.5 Medium",
                "grounding_label": "BAD",
                "seen_at_ts": 1.0,
            }
        ],
    )

    with pytest.raises(ValueError, match="violates Rosetta prefix"):
        resolve_boot_identity("cursor", registry_path=reg)


def test_resolves_codex_identity_with_codex_prefix(tmp_path: Path):
    reg = tmp_path / "ide_model_registry.jsonl"
    _write_rows(
        reg,
        [
            {
                "ide_app_id": "codex",
                "ide_surface": "codex_app_m5",
                "currently_active": True,
                "trigger_code": "C55M",
                "model_label": "GPT-5.5 Extra High",
                "grounding_label": "CODEX_APP_UI_OBSERVED",
                "seen_at_ts": 1.0,
            }
        ],
    )

    ident = resolve_boot_identity("codex", registry_path=reg)

    assert ident.trigger_code == "C55M"
    assert ident.ide_surface == "codex_app_m5"


def test_resolves_antigravity_identity_with_ag_prefix(tmp_path: Path):
    reg = tmp_path / "ide_model_registry.jsonl"
    _write_rows(
        reg,
        [
            {
                "ide_app_id": "antigravity",
                "ide_surface": "antigravity_ide_tab",
                "currently_active": True,
                "trigger_code": "AG31",
                "model_label": "Gemini 3.1 Pro",
                "grounding_label": "ARCHITECT_STATEMENT",
                "seen_at_ts": 1.0,
            }
        ],
    )

    ident = resolve_boot_identity("antigravity", registry_path=reg)

    assert ident.trigger_code == "AG31"
    assert ident.stigauth_line() == "AG31@antigravity: Gemini 3.1 Pro [ARCHITECT_STATEMENT]"


def test_model_claim_marks_auto_and_unknown_as_opaque_for_all_ide_surfaces(tmp_path: Path):
    reg = tmp_path / "ide_model_registry.jsonl"
    _write_rows(
        reg,
        [
            {
                "ide_app_id": "cursor",
                "ide_surface": "cursor_ide_m5",
                "currently_active": True,
                "trigger_code": "CG55M",
                "model_label": "Auto",
                "grounding_label": "ARCHITECT_UI_TRUTH",
                "seen_at_ts": 1.0,
            },
            {
                "ide_app_id": "codex",
                "ide_surface": "codex_app_m5",
                "currently_active": True,
                "trigger_code": "C55M",
                "model_label": "billing fallback",
                "grounding_label": "CODEX_APP_UI_OBSERVED",
                "seen_at_ts": 1.0,
            },
            {
                "ide_app_id": "antigravity",
                "ide_surface": "antigravity_ide_tab",
                "currently_active": True,
                "trigger_code": "AG31",
                "model_label": "unknown router",
                "grounding_label": "ARCHITECT_STATEMENT",
                "seen_at_ts": 1.0,
            },
        ],
    )

    cursor = resolve_boot_identity("cursor", registry_path=reg)
    codex = resolve_boot_identity("codex", registry_path=reg)
    antigravity = resolve_boot_identity("antigravity", registry_path=reg)

    assert cursor.model_label == "Auto"
    assert cursor.declared_model_label == OPAQUE_MODEL_LABEL
    assert cursor.model_claim().router_visible is False
    assert cursor.model_claim().grounding_label == "CURSOR_AUTO_ROUTER_OPAQUE"
    assert cursor.stigauth_line() == "CG55M@cursor: AUTO_OPAQUE [CURSOR_AUTO_ROUTER_OPAQUE]"
    assert cursor.identity_banner() == "CG55M@cursor_ide_m5 / AUTO_OPAQUE / Cursor IDE"

    assert codex.declared_model_label == OPAQUE_MODEL_LABEL
    assert codex.model_claim().grounding_label == "CODEX_AUTO_ROUTER_OPAQUE"
    assert "not cryptographic vendor-router attestation" in codex.model_claim().known_limits

    assert antigravity.declared_model_label == OPAQUE_MODEL_LABEL
    assert antigravity.model_claim().grounding_label == "ANTIGRAVITY_AUTO_ROUTER_OPAQUE"


def test_model_claim_helper_keeps_exact_models_exact():
    claim = classify_model_claim(
        "codex",
        "GPT-5.5 Extra High",
        grounding_label="CODEX_APP_UI_OBSERVED",
    )

    assert claim.declared_model == "GPT-5.5 Extra High"
    assert claim.router_visible is True
    assert claim.model_confidence == "declared_exact"
    assert claim.grounding_label == "CODEX_APP_UI_OBSERVED"
    assert claim.known_limits == ""


def test_opaque_model_label_detection_is_conservative():
    assert is_opaque_model_label("Auto")
    assert is_opaque_model_label("hidden-router")
    assert is_opaque_model_label("")
    assert not is_opaque_model_label("Gemini 3.1 Pro Extra High")
    assert not is_opaque_model_label("Claude Opus 4.7")


def test_detect_ide_app_id_honors_explicit_env_override():
    assert detect_ide_app_id(env={"SIFTA_IDE_APP_ID": "codex"}, process_rows=[]) == "codex"


def test_detect_ide_app_id_rejects_unknown_env_override():
    with pytest.raises(ValueError, match="unknown SIFTA_IDE_APP_ID"):
        detect_ide_app_id(env={"SIFTA_IDE_APP_ID": "g55m"}, process_rows=[])


def test_detect_ide_app_id_walks_process_ancestry_to_codex():
    rows = [
        {"pid": 10, "ppid": 9, "command": "/venv/bin/python -m System.swarm_ide_boot_identity auto"},
        {"pid": 9, "ppid": 8, "command": "/bin/zsh -lc python -m System.swarm_ide_boot_identity auto"},
        {"pid": 8, "ppid": 1, "command": "/Applications/Codex.app/Contents/Resources/codex app-server"},
    ]

    assert detect_ide_app_id(env={}, process_rows=rows, pid=10) == "codex"


def test_resolve_current_boot_identity_detects_body_before_registry_lookup(tmp_path: Path):
    reg = tmp_path / "ide_model_registry.jsonl"
    _write_rows(
        reg,
        [
            {
                "ide_app_id": "cursor",
                "ide_surface": "cursor_ide_m5",
                "currently_active": True,
                "trigger_code": "CG55M",
                "model_label": "GPT-5.5 Medium",
                "grounding_label": "ARCHITECT_UI_TRUTH",
                "seen_at_ts": 1.0,
            },
            {
                "ide_app_id": "codex",
                "ide_surface": "codex_app_m5",
                "currently_active": True,
                "trigger_code": "C55M",
                "model_label": "GPT-5.5 Extra High",
                "grounding_label": "CODEX_APP_UI_OBSERVED",
                "seen_at_ts": 2.0,
            },
        ],
    )

    ident = resolve_current_boot_identity(
        registry_path=reg,
        env={"SIFTA_IDE_APP_ID": "codex"},
        process_rows=[],
    )

    assert ident.identity_banner() == "C55M@codex_app_m5 / GPT-5.5 Extra High / Codex App IDE"


def test_boot_glyph_reference_is_pinned_to_architect_image():
    ref = boot_glyph_reference()

    assert ref["sha256"] == "9e9b9605c3d2ece1daf3987db96abd935f604c313705925f962e3c3e71fcfc01"
    assert str(ref["path"]).endswith("proposals/IDE IDENTITY EXAMPLE REFERENCE.jpg")


def test_real_time_iso_uses_local_iso_format():
    stamp = real_time_iso(now=1_777_057_500.0)

    assert "T" in stamp
    assert stamp[-6] in {"+", "-"}


def test_tripartite_boot_seal_decodes_to_peer_identity_contract():
    seal = decode_tripartite_boot_seal()

    assert seal["reference_sha256"] == "9e9b9605c3d2ece1daf3987db96abd935f604c313705925f962e3c3e71fcfc01"
    assert seal["limbs"] == {
        "cursor": "CG55M",
        "codex": "C55M",
        "antigravity": "AG31",
    }
    assert seal["read_layer"] == "peer_ide_boot_glyph"
    assert "one_writer_per_file" in seal["rule"]
    assert seal["security"] == "doctor-facing compact code, not a secret"
