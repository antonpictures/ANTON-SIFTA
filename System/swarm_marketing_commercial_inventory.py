#!/usr/bin/env python3
"""System/swarm_marketing_commercial_inventory.py — sellable docs + Philippe status.

Truth label: ``MARKETING_COMMERCIAL_INVENTORY_V1``.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_DATA = _REPO / "data" / "eval" / "marketing_commercial_inventory.json"
_TRUTH = "MARKETING_COMMERCIAL_INVENTORY_V1"


def _exists(rel: str) -> bool:
    return (_REPO / rel).exists()


def _philippe_status() -> dict[str, Any]:
    demo = _REPO / "demo" / "alice_demo_for_philippe.py"
    readme = _REPO / "demo" / "README_PHILIPPE.md"
    pdf = _REPO / "outputs" / "PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-14.pdf"
    pytest_ok: bool | None = None
    pytest_detail = ""
    if demo.exists():
        try:
            proc = subprocess.run(
                ["python3", "-m", "pytest", "tests/test_philippe_demo.py", "-q"],
                cwd=str(_REPO),
                capture_output=True,
                text=True,
                timeout=120,
            )
            pytest_ok = proc.returncode == 0
            pytest_detail = (proc.stdout or proc.stderr or "").strip().splitlines()[-1]
        except Exception as exc:
            pytest_detail = f"{type(exc).__name__}: {exc}"
    spinal_rows = 0
    spinal_path = _REPO / ".sifta_state" / "spinal_cord_cycles.jsonl"
    if spinal_path.exists():
        try:
            spinal_rows = sum(1 for ln in spinal_path.read_text(encoding="utf-8").splitlines() if ln.strip())
        except OSError:
            pass
    return {
        "buyer": "Philippe",
        "demo_script": "demo/alice_demo_for_philippe.py",
        "demo_readme": "demo/README_PHILIPPE.md",
        "one_pager_pdf": "outputs/PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-14.pdf",
        "demo_present": demo.exists(),
        "readme_present": readme.exists(),
        "pdf_present": pdf.exists(),
        "pytest_green": pytest_ok,
        "pytest_tail": pytest_detail,
        "spinal_cycle_rows": spinal_rows,
        "truth_summary": (
            "OPERATIONAL: demo + README + one-pager + pytest (steps 1–5). "
            "HYPOTHESIS: full kept spinal patch until MiMo provider auth completes."
        ),
        "receipt_ids": ["r1127-codex-philippe-commercial-response-pdf", "r1131-codex-audit-fix-mimo-borg-philippe-demo"],
    }


def marketing_assets() -> list[dict[str, Any]]:
    """Canonical sellable/marketing assets grouped for BD."""
    rows: list[dict[str, Any]] = [
        {
            "category": "mega_catalog",
            "path": "Documents/MARKETING_UNIQUE_SIFTA_PRODUCTS_MEGA_2026-06-13.md",
            "product": "23 Unique SIFTA Products (mega catalog)",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "philippe_packet",
            "path": "outputs/PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-14.pdf",
            "product": "Philippe commercial-viability one-pager",
            "label": "OPERATIONAL",
        },
        {
            "category": "philippe_packet",
            "path": "demo/alice_demo_for_philippe.py",
            "product": "Philippe runnable 6-step demo",
            "label": "OPERATIONAL",
        },
        {
            "category": "agent_trust",
            "path": "Documents/MARKETING_ROBOTICS_PROOF_FIGUERA_JONGERIUS_2026-06-13.md",
            "product": "Robotics proof — Figuera/Jongerius outreach",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "agent_trust",
            "path": "Documents/SIFTA_CONTACT_TARGETS_AGENT_TRUST_2026-06-13.md",
            "product": "Agent trust BD targets",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "fieldsight",
            "path": "Documents/SIFTA_FIELDSIGHT_PRODUCT_VALUE_BRIEF.md",
            "product": "SIFTA FieldSight",
            "label": "SIFTA_FIELDSIGHT_V0",
        },
        {
            "category": "fieldsight",
            "path": "Documents/SIFTA_FIELDSIGHT_CARLTON_BRIEF_V2.pdf",
            "product": "FieldSight Carlton deck v2",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "chorum",
            "path": "Documents/MARKETING_CHORUM_GATE_JOHN_DEERE_2026-05-11.md",
            "product": "Chorum Gate (John Deere / defense)",
            "label": "OPERATIONAL",
        },
        {
            "category": "chorum",
            "path": "Documents/MARKETING_CHORUM_GATE_AGRICULTURE_2026-05-11.md",
            "product": "Chorum Gate (agriculture short)",
            "label": "OPERATIONAL",
        },
        {
            "category": "field_physics",
            "path": "Documents/MARKETING_STIGMERGIC_FIELD_BREAKTHROUGH_2026-05-11.md",
            "product": "Bell / Field Scheduler breakthrough",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "field_physics",
            "path": "Documents/MARKETING_ALLOSTATIC_FIELD_REGULATOR_2026-05-11.md",
            "product": "Allostatic Field Regulator",
            "label": "OPERATIONAL",
        },
        {
            "category": "stigmergicode",
            "path": "Documents/MARKETING_STIGMERGICODE_COMPANY_APPLICATIONS_2026-05-10.md",
            "product": "Stigmergicode company applications map",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "fractals",
            "path": "Documents/SIFTA_FRACTALS_CARLTON_MARKETING_2026-05-18.pdf",
            "product": "Stigmergic Fractals sales one-pager",
            "label": "OPERATIONAL",
        },
        {
            "category": "fractals",
            "path": "Documents/STIGMERGIC_FRACTALS_ONE_PAGER.md",
            "product": "Stigmergic Fractals markdown source",
            "label": "OPERATIONAL",
        },
        {
            "category": "seed_fundraising",
            "path": "Documents/SIFTA_SEED_PROPOSAL_KOLE_2026-05-18.pdf",
            "product": "Seed proposal (Kole)",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "seed_fundraising",
            "path": "Documents/SIFTA_SEVEN_GROWTH_LANES_KOLE_2026-05-18.pdf",
            "product": "Seven growth lanes",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "founder",
            "path": "Documents/SIFTA_AI_NATIVE_ONE_FOUNDER_BRIEF.pdf",
            "product": "AI-native one-founder brief",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "founder",
            "path": "Documents/SIFTA_Technical_Brief.pdf",
            "product": "SIFTA technical brief (engineering review)",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "lawyer_stack",
            "path": "SIFTA_Lawyer_Real_Product_Stack_Consequence.pdf",
            "product": "Lawyer real product stack",
            "label": "OPERATIONAL",
        },
        {
            "category": "lawyer_stack",
            "path": "SIFTA_Sellable_Products_OnePage_Lawyer_v2_2026-06-05.pdf",
            "product": "Lawyer sellable products v2 one-pager",
            "label": "REGENERATE",
        },
        {
            "category": "winwin_flyer",
            "path": "outputs/WIN-WIN_10x10_sebastian_final.pdf",
            "product": "WIN-WIN Solution flyer (Sebastian final)",
            "label": "OPERATIONAL",
        },
        {
            "category": "winwin_flyer",
            "path": "Applications/sifta_pdf_forge_app.py",
            "product": "PDF Forge — receipted WIN-WIN forge organ",
            "label": "OPERATIONAL",
        },
        {
            "category": "outreach",
            "path": "Documents/MARKETING_OUTREACH_PURNOMO_ATENCIO_2026-06-13.md",
            "product": "Purnomo/Atencio robotics outreach",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "outreach",
            "path": "Documents/MARKETING_X_POST_SOVEREIGN_NODE_VS_CLOUD_2026-06-13.md",
            "product": "Sovereign node vs cloud X post",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "competitive",
            "path": "Documents/ISSUE_BRIEF_CHINA_EMBODIED_AI_VS_SIFTA_2026-12-13.md",
            "product": "China embodied-AI vs SIFTA",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "farsight",
            "path": "Documents/STIGMERGIC_FARSIGHT_CARLTON_BRIEF_V4_SOVEREIGN.pdf",
            "product": "Stigmergic FarSight v4 sovereign deck",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "farsight",
            "path": "Documents/STIGMERGIC_FARSIGHT_BUSINESS_CALL_BRIEF_2026-05-18.pdf",
            "product": "FarSight business call brief",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "robotics_proof",
            "path": "System/stigmerobotics_irb2400_ik.py",
            "product": "E49/E50 IRB2400 virtual effector lane",
            "label": "OPERATIONAL",
        },
        {
            "category": "apps_tour",
            "path": "Documents/SIFTA_FOUR_FLAGSHIP_APPS.md",
            "product": "Four flagship apps tour",
            "label": "MARKETING_BRIEF",
        },
        {
            "category": "economy",
            "path": "Documents/CRYPTO_ECONOMY.md",
            "product": "STGM / crypto economy narrative",
            "label": "MARKETING_BRIEF",
        },
    ]
    for row in rows:
        row["on_disk"] = _exists(str(row["path"]))
    return rows


def build_inventory(*, write_json: bool = True) -> dict[str, Any]:
    assets = marketing_assets()
    philippe = _philippe_status()
    present = sum(1 for a in assets if a.get("on_disk"))
    payload = {
        "schema": _TRUTH,
        "ts": time.time(),
        "philippe_report": philippe,
        "summary": {
            "total_assets": len(assets),
            "on_disk": present,
            "missing": len(assets) - present,
            "categories": sorted({str(a.get("category")) for a in assets}),
        },
        "assets": assets,
    }
    if write_json:
        _DATA.parent.mkdir(parents=True, exist_ok=True)
        _DATA.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_inventory() -> dict[str, Any]:
    if _DATA.exists():
        try:
            return json.loads(_DATA.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return build_inventory(write_json=True)


__all__ = ["build_inventory", "load_inventory", "marketing_assets"]