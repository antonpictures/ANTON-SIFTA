"""Tournament append anchor uniqueness (r1021 C1)."""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ANCHOR_RE = re.compile(r"\[r[0-9a-z][\w-]*-[a-f0-9]{8}\]", re.IGNORECASE)
_ROUND_HEADER_RE = re.compile(r"^(##\s+)(.+)$", re.MULTILINE)


def make_anchor(*, round_id: str, seed: str | None = None) -> str:
    """Return unique anchor token e.g. [r1021-fable-9504d7ac]."""
    rid = (round_id or "r0000").strip().lower()
    rid = rid.replace(" ", "-")[:32]
    token = (seed or uuid.uuid4().hex)[:8].lower()
    return f"[{rid}-{token}]"


def extract_anchor_from_round_header(round_header: str) -> str:
    m = _ANCHOR_RE.search(round_header or "")
    return m.group(0) if m else ""


def list_anchors(text: str) -> List[str]:
    return _ANCHOR_RE.findall(text or "")


def anchor_positions(text: str) -> List[Tuple[str, int]]:
    """Return (anchor, line_number) for duplicate detection."""
    out: List[Tuple[str, int]] = []
    for i, line in enumerate((text or "").splitlines(), start=1):
        for m in _ANCHOR_RE.finditer(line):
            out.append((m.group(0), i))
    return out


def validate_unique_anchors(text: str) -> Dict[str, Any]:
    positions = anchor_positions(text)
    seen: Dict[str, int] = {}
    duplicates: List[Dict[str, Any]] = []
    for anchor, line in positions:
        if anchor in seen:
            duplicates.append({"anchor": anchor, "first_line": seen[anchor], "dup_line": line})
        else:
            seen[anchor] = line
    return {
        "ok": not duplicates,
        "anchor_count": len(positions),
        "unique_count": len(seen),
        "duplicates": duplicates,
    }


def format_round_header(title: str, *, round_id: str, anchor: str | None = None) -> str:
    """Build ## line with mandatory unique anchor suffix."""
    anchor_token = anchor or make_anchor(round_id=round_id)
    if _ANCHOR_RE.search(title):
        return f"## {title.strip()}"
    return f"## {title.strip()} {anchor_token}"


def append_tournament_section(
    doc_path: Path | str,
    *,
    title: str,
    round_id: str,
    body_md: str,
    anchor: str | None = None,
) -> Dict[str, Any]:
    """Append-only tournament section with unique anchor (C1)."""
    path = Path(doc_path)
    anchor_token = anchor or make_anchor(round_id=round_id)
    header = format_round_header(title, round_id=round_id, anchor=anchor_token)
    block = f"\n---\n\n{header}\n\n{body_md.strip()}\n"
    existing = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    check = validate_unique_anchors(existing)
    if anchor_token in list_anchors(existing):
        return {"ok": False, "reason": "anchor_already_present", "anchor": anchor_token}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(block)
    merged = existing + block
    post = validate_unique_anchors(merged)
    return {
        "ok": True,
        "anchor": anchor_token,
        "path": str(path),
        "pre_duplicates": check.get("duplicates"),
        "post_ok": post.get("ok"),
    }