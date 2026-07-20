from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from unittest.mock import patch

from System import swarm_metabolic_cortex_router as router_mod
from System import swarm_travel_mode as travel
from System.swarm_macbook_survival_swimmer import decide_survival


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_schedule(state: Path, *rows: dict) -> None:
    state.mkdir(parents=True, exist_ok=True)
    with (state / "stigmergic_schedule.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_territory_shift_receipted_when_clock_lands_in_bucharest(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    now = 1780000000.0

    first = travel.sample_travel_mode(
        state_dir=state,
        write=True,
        force=True,
        now=now,
        clock={"ok": True, "timezone": "PDT", "local_iso": "2026-07-15T22:00:00-07:00"},
        network={"ok": True, "active_interface": "en0", "ipv4": "192.0.2.4"},
        power={"ok": True, "source_kind": "ac", "percent": 100},
    )
    second = travel.sample_travel_mode(
        state_dir=state,
        write=True,
        force=True,
        now=now + 3600,
        clock={"ok": True, "timezone": "EEST", "local_iso": "2026-07-16T08:00:00+03:00"},
        network={"ok": True, "active_interface": "en0", "ipv4": "192.0.2.5"},
        power={"ok": True, "source_kind": "ac", "percent": 98},
    )

    assert first["territory"] == "current_os_timezone"
    assert second["territory"] == "romania"
    assert second["territory_changed"] is True
    ledger = _rows(state / "travel_mode.jsonl")
    assert len(ledger) == 2
    assert ledger[-1]["status"] == "landed_romania_timezone"
    assert (state / "alice_first_person_journal.jsonl").exists()


def test_local_only_cortex_route_blocks_cloud_when_network_offline(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    now = 1780000100.0

    with patch(
        "System.swarm_travel_mode._installed_local_models",
        return_value=["alice-m5-cortex-8b-6.3gb:latest"],
    ):
        with patch(
            "System.swarm_travel_mode.sample_travel_mode",
            return_value={
                "route_local_only": True,
                "cloud_blocked_reason": "network_offline_or_unproven",
                "receipt_id": "travel_test",
            },
        ):
            route = travel.local_only_cortex_route(
                "grok:grok-4.3",
                state_dir=state,
                query_text="tell me from the plane",
                now=now,
                write=True,
            )

    assert route["override"] is True
    assert route["model"] == "alice-m5-cortex-8b-6.3gb:latest"
    rows = _rows(state / "travel_cortex_routes.jsonl")
    assert rows[-1]["from_model"] == "grok:grok-4.3"
    assert rows[-1]["chosen_model"] == "alice-m5-cortex-8b-6.3gb:latest"


def test_metabolic_router_honors_travel_local_only_for_current_cloud_model(tmp_path: Path):
    with patch("System.swarm_metabolic_cortex_router.STATE", tmp_path):
        with patch(
            "System.swarm_metabolic_cortex_router._get_installed_capable",
            return_value=[
                {"id": "alice-m5-cortex-8b-6.3gb:latest", "is_vision_capable": True, "is_tool_capable": True},
            ],
        ):
            with patch(
                "System.swarm_travel_mode.sample_travel_mode",
                return_value={
                    "route_local_only": True,
                    "cloud_blocked_reason": "network_offline_or_unproven",
                    "receipt_id": "travel_router",
                },
            ):
                with patch(
                    "System.swarm_travel_mode._installed_local_models",
                    return_value=["alice-m5-cortex-8b-6.3gb:latest"],
                ):
                    res = router_mod.route_cortex(
                        {
                            "current_model": "claude:claude-code-cli-default",
                            "query_text": "offline cabin turn",
                        }
                    )

    assert res["model"] == "alice-m5-cortex-8b-6.3gb:latest"
    assert "travel/offline" in res["reason"]
    route_rows = _rows(tmp_path / "cortex_route_receipts.jsonl")
    assert route_rows[-1]["signals"]["travel_route_local_only"] is True


def test_boot_travel_greeting_mentions_near_flight_and_consulate(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    now = 1780000200.0
    _write_schedule(
        state,
        {
            "text": "Turkish Airlines flight to Bucharest",
            "due_ts": now + 4 * 3600,
            "created": now - 100,
            "done": False,
            "schedule_id": "flight",
        },
        {
            "text": "Romanian consulate passport check",
            "due_ts": now + 7 * 3600,
            "created": now - 90,
            "done": False,
            "schedule_id": "consulate",
        },
    )

    greeting = travel.boot_travel_greeting(state_dir=state, now=now)

    assert "flight" in greeting.lower()
    assert "consulate" in greeting.lower()
    assert "local/offline cortex" in greeting


def test_survival_decision_sees_long_haul_battery_watch():
    decision = decide_survival(
        power={"ok": True, "source_kind": "battery", "percent": 74},
        thermal={"ok": True},
        camera={"ok": True},
        display_light={"ok": True},
        travel={
            "status": "travel_planned",
            "long_haul_battery_watch": True,
            "route_local_only": True,
        },
    )

    assert decision["action_kind"] == "charge_before_travel"
    assert "travel_long_haul_battery_watch" in decision["reasons"]
    assert decision["travel_route_local_only"] is True


def test_talk_current_brain_model_uses_travel_local_override(monkeypatch, tmp_path: Path):
    path = Path(__file__).resolve().parents[1] / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_travel_m6", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "resolve_ollama_model", lambda **_kw: "grok:grok-4.3")
    monkeypatch.setattr(mod, "_state_root", lambda: tmp_path / ".sifta_state")
    monkeypatch.setattr(
        "System.swarm_travel_mode.local_only_cortex_route",
        lambda model, **_kw: {
            "override": True,
            "model": "alice-m5-cortex-8b-6.3gb:latest",
            "reason": "network_offline_or_unproven",
        },
    )

    assert (
        mod.TalkToAliceWidget._current_brain_model(object(), "plane mode please")
        == "alice-m5-cortex-8b-6.3gb:latest"
    )
