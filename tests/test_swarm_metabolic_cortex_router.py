#!/usr/bin/env python3
"""
tests/test_swarm_metabolic_cortex_router.py — r498 acceptance.

- deterministic pick
- budget respected (mock resident high -> avoid big MLX)
- owner override wins
- receipt written to ledger
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# import after path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from System import swarm_metabolic_cortex_router as router_mod


def _reset_ledger(tmp: Path):
    p = tmp / "cortex_route_receipts.jsonl"
    if p.exists():
        p.unlink()
    return p


def test_owner_override_wins(tmp_path):
    with patch("System.swarm_metabolic_cortex_router.STATE", tmp_path):
        p = _reset_ledger(tmp_path)
        res = router_mod.route_cortex({"owner_override": "alice-m5-cortex-8b-6.3gb:latest", "has_images": True})
        assert "alice-m5-cortex-8b" in res["model"]
        assert "owner_explicit_override" in res["reason"]
        # receipt written
        lines = p.read_text().splitlines() if p.exists() else []
        assert any("owner_explicit_override" in l for l in lines)


def test_budget_respected_prefers_warm_cheap(tmp_path):
    with patch("System.swarm_metabolic_cortex_router.STATE", tmp_path):
        p = _reset_ledger(tmp_path)
        # mock high resident so 12B would violate; warm 8B capable
        with patch("System.swarm_metabolic_cortex_router._get_warm_resident", return_value={"alice-m5-cortex-8b-6.3gb:latest"}):
            with patch("System.swarm_metabolic_cortex_router._get_installed_capable", return_value=[
                {"id": "alice-m5-cortex-8b-6.3gb:latest", "is_vision_capable": True, "is_tool_capable": True},
                {"id": "some-27b-mlx", "is_vision_capable": True, "is_tool_capable": True},
            ]):
                res = router_mod.route_cortex({"has_images": True})
                assert "8b" in res["model"]
                assert "warm" in res["reason"].lower()


def test_cold_route_prefers_faster_cheaper_capable_model(tmp_path):
    with patch("System.swarm_metabolic_cortex_router.STATE", tmp_path):
        with patch("System.swarm_metabolic_cortex_router._get_warm_resident", return_value=set()):
            with patch("System.swarm_metabolic_cortex_router._get_installed_capable", return_value=[
                {"id": "alice-m5-cortex-8b-6.3gb:latest", "is_vision_capable": True, "is_tool_capable": True},
                {"id": "some-27b-mlx", "is_vision_capable": True, "is_tool_capable": True},
            ]):
                res = router_mod.route_cortex({"has_images": True})
                assert "8b" in res["model"]
                assert "27b" not in res["model"]


def test_deterministic_and_receipt(tmp_path):
    with patch("System.swarm_metabolic_cortex_router.STATE", tmp_path):
        p = _reset_ledger(tmp_path)
        res1 = router_mod.route_cortex({"task_type": "text only"})
        res2 = router_mod.route_cortex({"task_type": "text only"})
        assert res1["model"] == res2["model"]
        lines = p.read_text().splitlines() if p.exists() else []
        assert len(lines) >= 2
        assert all("receipt_id" in json.loads(l) for l in lines[-2:])


def test_receipt_has_required_fields(tmp_path):
    with patch("System.swarm_metabolic_cortex_router.STATE", tmp_path):
        p = _reset_ledger(tmp_path)
        res = router_mod.route_cortex({"has_images": True, "needs_tools": True})
        assert "model" in res and "reason" in res and "receipt_id" in res
        lines = p.read_text().splitlines() if p.exists() else []
        last = json.loads(lines[-1]) if lines else {}
        assert last.get("chosen_model") == res["model"]
        assert "capability" in last.get("reason", "").lower() or "warm" in last.get("reason", "").lower()
