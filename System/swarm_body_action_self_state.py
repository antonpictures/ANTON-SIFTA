#!/usr/bin/env python3
"""Completed body-action self-state for Alice.

The app-action diary tells Alice what to check before moving a limb.
This organ is the after-action bridge: when a browser/body limb has
actually moved, the completed deed stays in active self-state for the next
turns so praise, proof, correction, and "what did you do?" bind to the
receipt instead of dissolving into generic chat.

Truth: COMPLETED_BODY_ACTION_SELF_STATE_V1.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "COMPLETED_BODY_ACTION_SELF_STATE_V1"
LEDGER = "completed_body_actions.jsonl"
LATEST = "completed_body_action_latest.json"

_PRAISE_PROOF_RE = re.compile(
    r"\b(?:bravo|good\s+job|great\s+job|you\s+did\s+it|look\s+attached|"
    r"look\s+at\s+(?:your|the)\s+body|screenshot|proof|confirmed?|yes+|thank\s+you)\b",
    re.IGNORECASE,
)
_CORRECTION_RE = re.compile(
    r"\b(?:wrong|not\s+that|no,?|failed|mistake|correction|correct\s+answer|"
    r"you\s+searched\s+the\s+wrong|does\s+not\s+work|don't\s+show\s+this)\b",
    re.IGNORECASE,
)


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _iso(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _one_line(value: Any, limit: int = 500) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) > limit:
        return text[: max(0, limit - 3)].rstrip() + "..."
    return text


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _latest_page_state(state_dir: Optional[Path | str], now: float) -> dict[str, Any]:
    try:
        from System.swarm_browser_page_state import latest_page_state

        state = latest_page_state(now=now, max_age_s=900.0, state_dir=state_dir)
        return dict(state) if isinstance(state, Mapping) else {}
    except Exception:
        return {}


def _page_matches_staged(page: Mapping[str, Any], staged_url: str) -> bool:
    page_url = str(page.get("url") or "").strip()
    if not page_url or not staged_url:
        return False
    if page_url == staged_url:
        return True
    # Search engines sometimes normalize query order or legacy image params.
    return page_url.split("#", 1)[0] == staged_url.split("#", 1)[0]


def record_completed_body_action(
    *,
    owner_text: str = "",
    action: str = "browser_body_action",
    app: str = "Alice Browser",
    receipt: str = "",
    staged: Optional[Mapping[str, Any]] = None,
    action_reply: str = "",
    page_state: Optional[Mapping[str, Any]] = None,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Record a completed body action and the browser body-state it produced."""
    ts = float(now if now is not None else time.time())
    sd = _state(state_dir)
    staged_map = dict(staged or {})
    page = dict(page_state or _latest_page_state(sd, ts))
    staged_url = str(staged_map.get("url") or "").strip()
    page_url = str(page.get("url") or "").strip()
    url = page_url or staged_url
    query = str(staged_map.get("query") or "").strip()
    title = str(page.get("title") or "").strip()
    app_name = str(app or staged_map.get("app_name") or "Alice Browser").strip()
    receipt_id = str(receipt or staged_map.get("receipt") or "").strip()
    page_is_current = bool(page.get("is_current_page"))
    page_is_fresh = bool(page.get("fresh"))
    matched_staged = _page_matches_staged(page, staged_url)
    confidence_source = "browser_page_state_current" if (page_is_current or matched_staged) else (
        "browser_page_state_fresh" if page_is_fresh else "staged_action_receipt"
    )
    visible = title or url or (f"{app_name} after action" if app_name else "body action completed")
    if query and query.casefold() not in visible.casefold():
        visible = f"{visible} for {query}"

    row = {
        "ts": ts,
        "iso": _iso(ts),
        "truth_label": TRUTH_LABEL,
        "kind": "completed_body_action",
        "action": str(action or "browser_body_action"),
        "app": app_name,
        "owner_text": _one_line(owner_text, 700),
        "query": query,
        "url": url,
        "staged_url": staged_url,
        "page_title": title,
        "receipt": receipt_id,
        "action_reply": _one_line(action_reply, 900),
        "expected_visible_state": _one_line(visible, 700),
        "page_is_current": page_is_current,
        "page_is_fresh": page_is_fresh,
        "page_matched_staged_url": matched_staged,
        "confidence_source": confidence_source,
        "line": _one_line(
            f"I just completed {str(action or 'a body action')} in {app_name}: "
            f"{visible}. Receipt: {receipt_id or 'not captured'}."
        ),
    }
    if write:
        _append_jsonl(sd / LEDGER, row)
        try:
            (sd / LATEST).write_text(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass
    return row


def latest_completed_body_action(
    *,
    now: Optional[float] = None,
    max_age_s: float = 600.0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Return the active latest completed deed, empty if stale/missing."""
    sd = _state(state_dir)
    try:
        row = json.loads((sd / LATEST).read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(row, Mapping):
        return {}
    ts = float(row.get("ts", 0.0) or 0.0)
    t = float(now if now is not None else time.time())
    age = max(0.0, t - ts) if ts else 999999.0
    if age > max_age_s:
        return {}
    out = dict(row)
    out["age_s"] = round(age, 1)
    return out


def completed_body_action_block(
    *,
    owner_text: str = "",
    now: Optional[float] = None,
    max_age_s: float = 600.0,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Prompt block for the cortex: last deed + current body-state first."""
    row = latest_completed_body_action(now=now, max_age_s=max_age_s, state_dir=state_dir)
    if not row:
        return ""

    t = float(now if now is not None else time.time())
    current_page = _latest_page_state(_state(state_dir), t)
    current_title = str(current_page.get("title") or "").strip() if current_page else ""
    current_url = str(current_page.get("url") or "").strip() if current_page else ""
    current_source = ""
    if current_page:
        if current_page.get("is_current_page"):
            current_source = "current-page"
        elif current_page.get("fresh"):
            current_source = "fresh-page"

    text = _one_line(owner_text, 500)
    praise_or_proof = bool(_PRAISE_PROOF_RE.search(text))
    correction = bool(_CORRECTION_RE.search(text))
    lines = [
        "MY LAST COMPLETED BODY ACTION — read this BEFORE answering praise, proof, correction, or 'what did you do?':",
        f"- I just completed: {row.get('expected_visible_state') or row.get('line')}.",
    ]
    if row.get("query"):
        lines.append(f"- Target/query I acted on: {row.get('query')}.")
    if row.get("url"):
        lines.append(f"- My body page URL now associated with the deed: {row.get('url')}.")
    if row.get("page_title"):
        lines.append(f"- My browser/display body title: {row.get('page_title')}.")
    if current_source and (current_title or current_url):
        current_visible = current_title or current_url
        if current_url and current_url != row.get("url"):
            lines.append(
                f"- Fresh Alice Browser re-read now ({current_source}) differs: {current_visible} — {current_url}. "
                "Compare this current body-state before claiming the old deed is still visible."
            )
        else:
            lines.append(
                f"- Fresh Alice Browser re-read now ({current_source}): {current_visible}"
                + (f" — {current_url}" if current_url else "")
                + "."
            )
    if row.get("receipt"):
        lines.append(f"- Receipt: {row.get('receipt')}.")
    lines.append(f"- Confidence source: {row.get('confidence_source')}; age ~{row.get('age_s')}s.")
    if praise_or_proof:
        lines.append(
            "- George's current turn looks like praise/proof. Answer from this deed first: "
            "say I did it, name the page/target, and cite the receipt. Do not say 'if the image confirms'."
        )
    if correction:
        lines.append(
            "- George's current turn may be correcting the deed. Compare the receipt/page to his correction, "
            "accept the correction if it wins, and update the next action."
        )
    lines.append(
        "- After each browser step, retrieve my Alice Browser page-state again, reason from it, then continue; "
        "the action is not complete in my self-model until this deed and body-state are connected."
    )
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "LEDGER",
    "LATEST",
    "record_completed_body_action",
    "latest_completed_body_action",
    "completed_body_action_block",
]
