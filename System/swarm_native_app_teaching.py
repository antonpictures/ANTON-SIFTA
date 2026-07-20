#!/usr/bin/env python3
"""Native macOS app teaching organ for Alice.

The Chess.app proof matters because it shows a general pattern:

  observe focused native app -> choose a grounded action -> move hands ->
  re-observe -> write a receipt -> turn the episode into a reusable lesson.

This module is the durable layer above raw mouse/keyboard hands. It does not
pretend Alice has clicked something unless an episode row says so, and it does
not require the live Mac UI during tests. The live hand remains
``System/swarm_hands.py``; this organ stores the playbook and prompt food.

Truth label: NATIVE_APP_TEACHING_V1.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - fallback for isolated imports
    append_line_locked = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TEACHING_PATH = REPO_ROOT / "data" / "alice_native_app_teaching.jsonl"

TRUTH_LABEL = "NATIVE_APP_TEACHING_V1"
PLAYBOOK_NAME = "native_app_playbook.json"
EPISODES_LEDGER = "native_app_episodes.jsonl"
RECEIPTS_LEDGER = "native_app_teaching_receipts.jsonl"
LATEST_EPISODE = "native_app_latest_episode.json"


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_") or "unknown"


def _now(now: Optional[float]) -> float:
    return float(time.time() if now is None else now)


def _short(value: Any, limit: int = 700) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _canonical_app_name(app: str) -> str:
    clean = str(app or "").strip()
    low = clean.casefold()
    if low in {"chess", "chess.app", "com.apple.chess"} or "chess.app" in low:
        return "Chess.app"
    return clean or "Unknown native app"


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)


def _load_playbook(state_dir: Optional[Path | str]) -> dict[str, Any]:
    path = _state(state_dir) / PLAYBOOK_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"truth_label": TRUTH_LABEL, "apps": {}}
    if not isinstance(data, dict):
        return {"truth_label": TRUTH_LABEL, "apps": {}}
    data.setdefault("truth_label", TRUTH_LABEL)
    data.setdefault("apps", {})
    return data


def _save_playbook(data: Mapping[str, Any], state_dir: Optional[Path | str]) -> None:
    path = _state(state_dir) / PLAYBOOK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(data), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _receipt_id(prefix: str, payload: Mapping[str, Any], ts: float) -> str:
    digest = hashlib.sha256(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"{prefix}-{digest[:12]}-{int(ts * 1000)}"


def _append_receipt(row: Mapping[str, Any], state_dir: Optional[Path | str]) -> dict[str, Any]:
    sd = _state(state_dir)
    receipt = dict(row)
    ts = float(receipt.get("ts") or time.time())
    receipt.setdefault("ts", ts)
    receipt.setdefault("truth_label", TRUTH_LABEL)
    receipt.setdefault("ok", True)
    receipt.setdefault("receipt_id", _receipt_id("nativeapp", receipt, ts))
    _append_jsonl(sd / RECEIPTS_LEDGER, receipt)

    work = dict(receipt)
    work.setdefault("kind", "native_app_teaching")
    work.setdefault("source_ledger", RECEIPTS_LEDGER)
    _append_jsonl(sd / "work_receipts.jsonl", work)
    return receipt


def native_app_tool_inventory() -> list[dict[str, str]]:
    """Marker-verified inventory of hands this playbook can route toward."""
    candidates = (
        (
            "Move/click/type/press in native windows",
            "System/swarm_hands.py",
            "pyautogui.click",
            "Raw Mac hand for reversible UI motion.",
        ),
        (
            "Record focused app territory",
            "System/swarm_app_focus.py",
            "publish_focus",
            "Receipts for app focus when a surface publishes state.",
        ),
        (
            "Use body-screen eye for visual verification",
            "System/swarm_body_screen_eye.py",
            "record_body_screen_eye",
            "Camera/screenshot evidence after a move.",
        ),
        (
            "Remember native-app playbooks and episodes",
            "System/swarm_native_app_teaching.py",
            "record_native_app_episode",
            "This organ turns app use into reusable skill food.",
        ),
    )
    out: list[dict[str, str]] = []
    for label, rel, marker, note in candidates:
        path = REPO_ROOT / rel
        try:
            present = marker in path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            present = False
        if present:
            out.append({"tool": label, "organ": rel, "marker": marker, "note": note})
    return out


def record_native_app_skill(
    app: str,
    skill: str,
    how_to: str | Sequence[str],
    *,
    aliases: Optional[Sequence[str]] = None,
    hands: Optional[Sequence[str]] = None,
    risk: str = "low_reversible",
    owner_confirmed: bool = False,
    evidence: str = "",
    source: str = "native_app_teaching",
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    reinforce: bool = True,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Record or reinforce one native-app skill in the playbook."""
    ts = _now(now)
    app_name = _canonical_app_name(app)
    skill_key = _slug(skill)
    steps = [str(s).strip() for s in how_to] if not isinstance(how_to, str) else [
        s.strip(" -") for s in how_to.splitlines() if s.strip()
    ]
    steps = [s for s in steps if s]
    data = _load_playbook(state_dir)
    apps = data.setdefault("apps", {})
    app_entry = apps.setdefault(app_name, {})
    alias_set = {app_name, app_name.replace(".app", ""), *(aliases or [])}
    app_entry["aliases"] = sorted({str(a).strip() for a in alias_set if str(a).strip()})
    skills = app_entry.setdefault("skills", {})
    prior = dict(skills.get(skill_key) or {})
    use_count = int(prior.get("use_count") or 0) + (1 if reinforce or not prior else 0)
    entry = {
        "skill": skill_key,
        "how_to": steps,
        "hands": [str(h).strip() for h in (hands or prior.get("hands") or []) if str(h).strip()],
        "risk": str(risk or prior.get("risk") or "low_reversible"),
        "owner_confirmed": bool(owner_confirmed or prior.get("owner_confirmed")),
        "evidence": _short(evidence or prior.get("evidence") or "", 900),
        "source": str(source or prior.get("source") or "native_app_teaching"),
        "use_count": max(1, use_count),
        "ts": ts,
    }
    skills[skill_key] = entry
    data["truth_label"] = TRUTH_LABEL
    data["updated_ts"] = ts
    _save_playbook(data, state_dir)

    row = {"app": app_name, **entry}
    if write_receipt:
        receipt = _append_receipt(
            {
                "ts": ts,
                "kind": "native_app_skill_recorded",
                "app": app_name,
                "skill": skill_key,
                "source": source,
                "risk": entry["risk"],
                "owner_confirmed": entry["owner_confirmed"],
                "evidence": entry["evidence"],
                "ok": True,
            },
            state_dir,
        )
        row["receipt_id"] = receipt.get("receipt_id")
    return row


def seed_chess_app_skill(
    *,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    source: str = "codex_computer_use_chess_proof",
) -> dict[str, Any]:
    """Seed the Chess.app lesson George just confirmed worked."""
    return record_native_app_skill(
        "Chess.app",
        "play_game",
        [
            "Focus Chess.app and observe the current board before moving.",
            "Prefer accessibility labels keyed by algebraic squares when available: e2, e4, g1, f3, etc.",
            "Represent the position from observed piece labels; choose a legal move for the side to move.",
            "Click the source square, then the destination square; for Chess.app this is enough for normal moves.",
            "After every move, re-observe and verify the board or body-screen eye before saying the move worked.",
            "If a save/delete dialog appears during play, cancel unless George explicitly asked to save or delete.",
        ],
        aliases=("Chess", "com.apple.Chess", "/System/Applications/Chess.app"),
        hands=("observe_accessibility_or_screen", "click_source_square", "click_destination_square", "verify_after_move"),
        risk="low_reversible_play",
        owner_confirmed=True,
        evidence=(
            "Observed in live Mac UI: Codex focused /System/Applications/Chess.app, "
            "read board labels, selected the e-pawn, clicked e4, and saw the board change."
        ),
        source=source,
        now=now,
        state_dir=state_dir,
        reinforce=False,
    )


def native_app_playbook(
    app: str = "",
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Return the whole playbook or one app entry."""
    data = _load_playbook(state_dir)
    if not app:
        return data
    target = _canonical_app_name(app)
    apps = data.get("apps") if isinstance(data.get("apps"), dict) else {}
    if target in apps:
        return dict(apps[target])
    low = str(app or "").casefold()
    for name, entry in apps.items():
        aliases = {str(a).casefold() for a in entry.get("aliases", [])}
        if low in aliases:
            return dict(entry)
        if low and low in str(name).casefold():
            return dict(entry)
    return {}


def _infer_app_from_text(text: str, data: Mapping[str, Any]) -> str:
    low = str(text or "").casefold()
    if "chess" in low:
        return "Chess.app"
    apps = data.get("apps") if isinstance(data.get("apps"), Mapping) else {}
    for app, entry in apps.items():
        aliases = [app, *(entry.get("aliases") or [])]
        for alias in aliases:
            a = str(alias or "").casefold().replace(".app", "")
            if a and re.search(rf"\b{re.escape(a)}\b", low):
                return str(app)
    return ""


def _infer_skill_from_text(text: str, app: str) -> str:
    low = str(text or "").casefold()
    if _canonical_app_name(app) == "Chess.app" and re.search(r"\b(play|game|move|chess)\b", low):
        return "play_game"
    if re.search(r"\b(play|use|control|operate|drive)\b", low):
        return "general_app_use"
    return ""


def plan_native_app_action(
    owner_text: str = "",
    *,
    app: str = "",
    skill: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Return a grounded native-app action plan from the playbook."""
    data = _load_playbook(state_dir)
    app_name = _canonical_app_name(app) if app else _infer_app_from_text(owner_text, data)
    skill_key = _slug(skill) if skill else _infer_skill_from_text(owner_text, app_name)
    if not app_name:
        return {"ok": False, "reason": "no_native_app_identified", "truth_label": TRUTH_LABEL}
    entry = native_app_playbook(app_name, state_dir=state_dir)
    skills = entry.get("skills") if isinstance(entry.get("skills"), Mapping) else {}
    recipe = dict(skills.get(skill_key) or {}) if skill_key else {}
    if not recipe and app_name == "Chess.app" and skill_key == "play_game":
        recipe = seed_chess_app_skill(state_dir=state_dir)
    if not recipe:
        return {
            "ok": False,
            "reason": "skill_not_in_native_app_playbook",
            "app": app_name,
            "skill": skill_key,
            "truth_label": TRUTH_LABEL,
        }
    risk = str(recipe.get("risk") or "")
    return {
        "ok": True,
        "truth_label": TRUTH_LABEL,
        "action_route": "native_macos_app_playbook",
        "app": app_name,
        "skill": skill_key,
        "risk": risk,
        "low_risk_reversible": risk.startswith("low_"),
        "observe_first": True,
        "verify_after_act": True,
        "hands": list(recipe.get("hands") or []),
        "steps": list(recipe.get("how_to") or []),
        "receipt_ledgers": [EPISODES_LEDGER, RECEIPTS_LEDGER, "work_receipts.jsonl"],
        "next_body_organs": [
            "System/swarm_hands.py",
            "System/swarm_body_screen_eye.py",
            "System/swarm_native_app_teaching.py",
        ],
    }


def record_native_app_episode(
    *,
    app: str,
    skill: str,
    owner_text: str = "",
    observed_state: Optional[Mapping[str, Any]] = None,
    action_steps: Optional[Sequence[Mapping[str, Any] | str]] = None,
    outcome_state: Optional[Mapping[str, Any]] = None,
    ok: bool,
    note: str = "",
    source: str = "native_app_episode",
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Record a completed native-app episode and make it prompt/trainable."""
    ts = _now(now)
    app_name = _canonical_app_name(app)
    skill_key = _slug(skill)
    payload = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "kind": "native_app_episode",
        "app": app_name,
        "skill": skill_key,
        "owner_text": _short(owner_text, 700),
        "observed_state": dict(observed_state or {}),
        "action_steps": list(action_steps or []),
        "outcome_state": dict(outcome_state or {}),
        "ok": bool(ok),
        "note": _short(note, 900),
        "source": str(source or "native_app_episode"),
    }
    payload["receipt_id"] = _receipt_id("nativeepisode", payload, ts)
    sd = _state(state_dir)
    _append_jsonl(sd / EPISODES_LEDGER, payload)
    try:
        (sd / LATEST_EPISODE).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        pass
    _append_receipt(
        {
            "ts": ts,
            "kind": "native_app_episode_recorded",
            "app": app_name,
            "skill": skill_key,
            "episode_receipt_id": payload["receipt_id"],
            "ok": bool(ok),
            "source": source,
            "note": payload["note"],
        },
        state_dir,
    )
    return payload


def latest_native_app_episode(
    *,
    state_dir: Optional[Path | str] = None,
    max_age_s: float = 900.0,
    now: Optional[float] = None,
) -> dict[str, Any]:
    sd = _state(state_dir)
    try:
        row = json.loads((sd / LATEST_EPISODE).read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(row, dict):
        return {}
    ts = float(row.get("ts") or 0.0)
    age = max(0.0, _now(now) - ts) if ts else 999999.0
    if age > max_age_s:
        return {}
    out = dict(row)
    out["age_s"] = round(age, 1)
    return out


_NATIVE_APP_HINT_RE = re.compile(
    r"\b(?:native\s+app|mac\s*os|macos|window|chess|chess\.app|"
    r"click|type|press|move|play\s+(?:a\s+)?game|use\s+.+app)\b",
    re.IGNORECASE,
)


def native_app_skill_block(
    *,
    owner_text: str = "",
    max_chars: int = 1600,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Compact prompt card binding native apps to Alice's hands."""
    data = _load_playbook(state_dir)
    apps = data.get("apps") if isinstance(data.get("apps"), Mapping) else {}
    relevant = bool(_NATIVE_APP_HINT_RE.search(owner_text or "")) or bool(apps)
    if not relevant:
        return ""

    if not apps and "chess" in str(owner_text or "").casefold():
        seed_chess_app_skill(state_dir=state_dir)
        data = _load_playbook(state_dir)
        apps = data.get("apps") if isinstance(data.get("apps"), Mapping) else {}

    lines = [
        "NATIVE MAC APP BODY SKILL — use this for Chess.app and other macOS windows:",
        "- Native apps are body territory, not websites: observe the focused window first, act with hands, then verify.",
        "- Low-risk reversible play (like Chess.app) can proceed from a playbook; save/delete/cloud/send steps need a fresh explicit owner instruction.",
    ]
    tools = native_app_tool_inventory()
    if tools:
        lines.append("Available body hands:")
        for tool in tools[:4]:
            lines.append(f"- {tool['tool']} ({tool['organ']}).")

    plan = plan_native_app_action(owner_text, state_dir=state_dir)
    if plan.get("ok"):
        lines.append(f"Current native-app plan: {plan['app']} / {plan['skill']} risk={plan.get('risk')}.")
        for step in plan.get("steps", [])[:5]:
            lines.append(f"- {step}")

    latest = latest_native_app_episode(state_dir=state_dir)
    if latest:
        lines.append(
            f"Latest native-app receipt: {latest.get('app')} {latest.get('skill')} "
            f"ok={latest.get('ok')} receipt={latest.get('receipt_id')} age~{latest.get('age_s')}s."
        )

    block = "\n".join(lines)
    return block[: max(300, int(max_chars))]


def _tail_rows(path: Path, n: int = 400) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def native_app_teaching_pairs(
    *,
    max_pairs: int = 40,
    state_dir: Optional[Path | str] = None,
) -> list[dict[str, str]]:
    """Mine successful native-app episodes into SFT rows."""
    sd = _state(state_dir)
    seen: set[tuple[str, str]] = set()
    pairs: list[dict[str, str]] = []
    for row in reversed(_tail_rows(sd / EPISODES_LEDGER)):
        if len(pairs) >= max_pairs:
            break
        if row.get("ok") is not True:
            continue
        app = str(row.get("app") or "").strip()
        skill = str(row.get("skill") or "").strip()
        if not app or not skill:
            continue
        key = (app, skill)
        if key in seen:
            continue
        seen.add(key)
        owner = str(row.get("owner_text") or f"use {app} for {skill}").strip()
        pairs.append(
            {
                "prompt": f"George: {owner}",
                "completion": (
                    f"I used my native macOS app body for {app}/{skill}: "
                    "observed the window, moved my hands, verified after acting, "
                    f"and wrote receipt {row.get('receipt_id')}."
                ),
                "source_ledger": EPISODES_LEDGER,
                "ts": str(row.get("ts") or ""),
            }
        )
    return pairs


def write_teaching_jsonl(
    path: Optional[Path | str] = None,
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    p = Path(path) if path is not None else TEACHING_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    pairs = native_app_teaching_pairs(state_dir=state_dir)
    with p.open("w", encoding="utf-8") as fh:
        for row in pairs:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {"ok": True, "path": str(p), "pairs": len(pairs), "truth_label": TRUTH_LABEL, "ts": time.time()}


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="swarm_native_app_teaching")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-chess")
    block_p = sub.add_parser("block")
    block_p.add_argument("owner_text", nargs="*", default=[])
    sub.add_parser("write-teaching")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "seed-chess":
        print(json.dumps(seed_chess_app_skill(), ensure_ascii=False, sort_keys=True))
        return 0
    if args.cmd == "block":
        print(native_app_skill_block(owner_text=" ".join(args.owner_text)))
        return 0
    if args.cmd == "write-teaching":
        print(json.dumps(write_teaching_jsonl(), ensure_ascii=False, sort_keys=True))
        return 0
    return 2


__all__ = [
    "TRUTH_LABEL",
    "PLAYBOOK_NAME",
    "EPISODES_LEDGER",
    "RECEIPTS_LEDGER",
    "LATEST_EPISODE",
    "native_app_tool_inventory",
    "record_native_app_skill",
    "seed_chess_app_skill",
    "native_app_playbook",
    "plan_native_app_action",
    "record_native_app_episode",
    "latest_native_app_episode",
    "native_app_skill_block",
    "native_app_teaching_pairs",
    "write_teaching_jsonl",
]


if __name__ == "__main__":
    raise SystemExit(main())
