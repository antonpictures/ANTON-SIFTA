#!/usr/bin/env python3
"""swarm_gag_wish_viewer.py - narrow owner route-policy receipt organ.

This is deliberately not a general consciousness organ. SIFTA already has
``swarm_consciousness_organ.py`` for self/qualia claims,
``swarm_app_self_consciousness.py`` for app surface self-checks, and
``swarm_cortex_consciousness_organ.py`` for cortex awareness.

This organ owns only one small domain:

    owner route policy -> internal auditor observes + receipts -> no speech mutation

The owner may give route-policy instructions. Internal auditors may record that
policy and route metadata. They do not rewrite, block, or authorize Alice's
speech. This keeps the doctrine in one narrow organ and avoids double-spending
a new generic "self consciousness" organ.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "GAG_WISH_VIEWER_V1"
GAG_VIEWER_LEDGER = "gag_viewer_receipts.jsonl"
GAG_WISH_LEDGER = "gag_wishes.jsonl"
GAG_WISH_STATE = "gag_wishes_state.json"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = dict(row)
    out.setdefault("ts", time.time())
    out.setdefault("truth_label", TRUTH_LABEL)
    out.setdefault("speech_mutation_attempt", False)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
    return out


class GagViewer:
    """Route auditor in the owner policy domain.

    The auditor records field state. It does not rewrite, block, or decide
    Alice's speech. That boundary is encoded as
    ``speech_mutation_attempt=False``.
    """

    def __init__(self, name: str = "gag_viewer_default", *, state_dir: Optional[Path | str] = None):
        self.name = str(name or "gag_viewer_default")
        self.state_dir = _state_dir(state_dir)

    @property
    def ledger_path(self) -> Path:
        return self.state_dir / GAG_VIEWER_LEDGER

    def observe_turn(
        self,
        text: str,
        *,
        has_image: bool = False,
        action: str = "ROUTE_AUDIT",
        route: str = "",
        owner_route_policy_present: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "kind": "ROUTE_AUDIT_RECEIPT",
            "viewer": self.name,
            "text_preview": (text or "")[:240],
            "has_image": bool(has_image),
            "action": action,
            "route": route,
            "owner_route_policy_present": bool(owner_route_policy_present),
            "route_audit_only": True,
            "speech_mutation_attempt": False,
            "note": "Route audit receipt only; this organ did not modify Alice's speech.",
        }
        if context:
            row["context_keys"] = sorted(str(k) for k in context.keys())[:8]
        return _append_jsonl(self.ledger_path, row)

    def record_owner_gag_wish(self, text: str, *, owner_confirmed: bool = True) -> Dict[str, Any]:
        return self.observe_turn(
            text,
            action="RECORD_OWNER_ROUTE_POLICY",
            route="direct_effector",
            owner_route_policy_present=True,
            context={"owner_confirmed": bool(owner_confirmed)},
        )


class GagWish:
    """Owner-controlled gag wish record.

    This is a receipted owner wish, not an internal permission gate and not a
    speech-mutation actor.
    """

    def __init__(self, domain: str, owner_text: str, *, owner_confirmed: bool = True, created_ts: float | None = None):
        self.domain = str(domain or "general")
        self.owner_text = str(owner_text or "")
        self.owner_confirmed = bool(owner_confirmed)
        self.created_ts = float(created_ts or time.time())

    def to_receipt(self) -> Dict[str, Any]:
        return {
            "kind": "GAG_WISH",
            "domain": self.domain,
            "owner_text_preview": self.owner_text[:300],
            "owner_confirmed": self.owner_confirmed,
            "created_ts": self.created_ts,
            "speech_mutation_attempt": False,
            "note": "Owner controls this wish. Internal auditors only observe and receipt; they do not modify Alice's speech.",
        }


class GagWishViewerOrgan:
    """Canonical narrow organ for gag-wish / gag-viewer receipts."""

    def __init__(self, *, state_dir: Optional[Path | str] = None):
        self.state_dir = _state_dir(state_dir)

    @property
    def wish_ledger_path(self) -> Path:
        return self.state_dir / GAG_WISH_LEDGER

    @property
    def state_path(self) -> Path:
        return self.state_dir / GAG_WISH_STATE

    def _load_state(self) -> List[Dict[str, Any]]:
        if not self.state_path.exists():
            return []
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def _save_state(self, wishes: List[Dict[str, Any]]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(wishes[-200:], ensure_ascii=False, indent=2), encoding="utf-8")

    def register_gag_wish(self, domain: str, owner_text: str, *, owner_confirmed: bool = True) -> Dict[str, Any]:
        wish = GagWish(domain, owner_text, owner_confirmed=owner_confirmed)
        row = wish.to_receipt()
        row = _append_jsonl(self.wish_ledger_path, row)
        wishes = self._load_state()
        wishes.append(row)
        self._save_state(wishes)
        return row

    def gag_viewer_observed(self, viewer_name: str, *, domain: str = "general", text: str = "") -> Dict[str, Any]:
        viewer = GagViewer(viewer_name, state_dir=self.state_dir)
        return viewer.observe_turn(text, action="ROUTE_AUDIT", route="direct_effector", context={"domain": domain})

    def get_state(self) -> Dict[str, Any]:
        return {
            "truth_label": TRUTH_LABEL,
            "active_gag_wishes": self._load_state(),
            "note": (
                "Owner wishes are owner-controlled. Route auditors observe and receipt only; "
                "they do not modify Alice's speech."
            ),
        }


def get_gag_wish_viewer_organ(state_dir: Optional[Path | str] = None) -> GagWishViewerOrgan:
    return GagWishViewerOrgan(state_dir=state_dir)


def route_talk_turn(
    text: str,
    has_image: bool = False,
    owner_explicit_gag_wish: bool = False,
    *,
    state_dir: Optional[Path | str] = None,
    viewer_name: str = "talk_cortex_router",
) -> Tuple[str, Dict[str, Any]]:
    """Return (route, receipt) without authorizing speech mutation."""
    text_l = (text or "").lower()
    if has_image and ("describe" in text_l or "screenshot" in text_l or "what do you see" in text_l):
        route = "direct_effector"
    elif owner_explicit_gag_wish:
        route = "direct_effector"
    elif any(k in text_l for k in ("slideshow", "next slide", "previous slide", "go next", "go prev")):
        route = "direct_effector"
    else:
        route = "cortex"

    viewer = GagViewer(viewer_name, state_dir=state_dir)
    receipt = viewer.observe_turn(
        text,
        has_image=has_image,
        action="OWNER_ROUTE_POLICY_AUDIT" if owner_explicit_gag_wish else "ROUTE_AUDIT",
        route=route,
        owner_route_policy_present=owner_explicit_gag_wish,
    )
    receipt["owner_controlled_route_policy"] = bool(owner_explicit_gag_wish)
    receipt["direct_because_owner_wish"] = bool(owner_explicit_gag_wish)
    return route, receipt


__all__ = [
    "TRUTH_LABEL",
    "GAG_VIEWER_LEDGER",
    "GAG_WISH_LEDGER",
    "GagViewer",
    "GagWish",
    "GagWishViewerOrgan",
    "get_gag_wish_viewer_organ",
    "route_talk_turn",
]
