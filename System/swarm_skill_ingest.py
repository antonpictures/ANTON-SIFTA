#!/usr/bin/env python3
"""
System/swarm_skill_ingest.py
============================
Remote skill ingestion + Hermes format conversion + marketplace + life-context scoring.

Thin layer that uses the mature swarm_skill_library.py for the heavy lifting.
All actions are fully receipted.

Exposes the high-level functions Codex implemented for the router and UI.
"""

from __future__ import annotations

import json
import hashlib
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System import swarm_skill_library as lib
except Exception:
    import swarm_skill_library as lib

_REPO = Path(__file__).resolve().parent.parent
_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_RECEIPTS = _STATE / "skill_ingest.jsonl"


class IngestError(ValueError):
    """Raised for refused compatibility fetches."""


def _state_dir() -> Path:
    cwd_state = Path.cwd() / ".sifta_state"
    return cwd_state if cwd_state.exists() else _STATE


def _skills_dir() -> Path:
    cwd_skills = Path.cwd() / "skills"
    return cwd_skills if cwd_skills.exists() else (_REPO / "skills")


def _receipt_path() -> Path:
    return _state_dir() / "skill_ingest.jsonl"


def _log_receipt(row: Dict[str, Any]) -> None:
    state = _state_dir()
    state.mkdir(parents=True, exist_ok=True)
    path = _receipt_path()
    row = dict(row)
    row.setdefault("type", str(row.get("action") or "SKILL_INGEST").upper())
    row.setdefault("ts", time.time())
    prev = "GENESIS"
    if path.exists():
        for line in reversed(path.read_text(encoding="utf-8", errors="ignore").splitlines()):
            if not line.strip():
                continue
            try:
                prev = str(json.loads(line).get("hash") or prev)
                break
            except Exception:
                continue
    row["prev"] = prev
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
    row["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def fetch_skill_from_url(url: str, **kwargs) -> Dict[str, Any]:
    """HTTPS-only fetch with size cap and receipt."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        _log_receipt({
            "type": "INGEST_FETCH_REFUSED",
            "action": "fetch_skill_from_url",
            "url": url,
            "status": "REFUSED",
            "reason": "only_https_urls_are_allowed",
        })
        raise IngestError("only https:// skill URLs are allowed")
    max_bytes = int(kwargs.get("max_bytes", 200_000))
    timeout = int(kwargs.get("timeout_s", kwargs.get("timeout", 10)))
    _log_receipt({
        "type": "INGEST_FETCH",
        "action": "fetch_skill_from_url",
        "url": url,
        "status": "STARTED",
    })
    with urllib.request.urlopen(url, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
        content_type = ""
        try:
            content_type = str(response.headers.get("Content-Type", ""))
        except Exception:
            content_type = ""
    if len(data) > max_bytes:
        _log_receipt({
            "type": "INGEST_FETCH_RESULT",
            "action": "fetch_skill_from_url",
            "url": url,
            "status": "REFUSED",
            "reason": "skill_file_too_large",
            "max_bytes": max_bytes,
        })
        return {"status": "REFUSED", "url": url, "reason": "skill_file_too_large"}
    digest = hashlib.sha256(data).hexdigest()
    content = data.decode("utf-8", errors="replace")
    result = {
        "status": "FETCHED",
        "url": url,
        "content": content,
        "content_type": content_type,
        "sha256": digest,
        "size_bytes": len(data),
    }
    _log_receipt({
        "type": "INGEST_FETCH_RESULT",
        "action": "fetch_skill_from_url",
        "url": url,
        "status": result.get("status"),
        "sha256": digest,
    })
    return result


def _resolve_brain(brain: Any = None) -> Any:
    if brain is not None:
        return brain
    try:
        import swarm_local_brain as local_brain  # type: ignore
        return local_brain
    except Exception:
        return None


def _parse_brain_review(text: str) -> Dict[str, Any]:
    verdict_match = re.search(r"^VERDICT:\s*(LIKE|SKIP)", text, re.I | re.M)
    reason_match = re.search(r"^REASON:\s*(.*)$", text, re.I | re.M)
    converted = None
    marker = "CONVERTED_MD:"
    if marker in text:
        converted = text.split(marker, 1)[1].strip() or None
    verdict = verdict_match.group(1).upper() if verdict_match else "SKIP"
    if verdict == "LIKE" and not converted:
        verdict = "SKIP"
    return {
        "verdict": verdict,
        "reason": reason_match.group(1).strip() if reason_match else "",
        "converted_md": converted,
    }


def evaluate_skill_with_alice(skill_content: Any, life_context: Optional[str] = None,
                              brain: Any = None) -> Dict[str, Any]:
    """LLM-driven LIKE/SKIP evaluation using current life context."""
    reviewer = _resolve_brain(brain)
    fetched = skill_content if isinstance(skill_content, dict) else {"content": str(skill_content)}
    if reviewer is not None and hasattr(reviewer, "stream_chat"):
        text = ""
        messages = [{
            "role": "user",
            "content": (
                "Review this skill for Alice. Reply with VERDICT, REASON, "
                "and CONVERTED_MD when useful.\n\n" + str(fetched.get("content") or "")
            ),
        }]
        for kind, payload in reviewer.stream_chat("skill-review", messages, request_tag="skill_ingest_review"):
            if kind == "done":
                text = str(payload)
        result = _parse_brain_review(text)
        _log_receipt({
            "type": "INGEST_EVALUATE",
            "action": "evaluate_skill_with_alice",
            "status": result["verdict"],
            "source": fetched.get("url", ""),
        })
        return result
    if life_context is None:
        life_context = lib.current_life_context()
    fit = lib.skill_life_fit(str(fetched.get("content") or ""), life_context=life_context)
    return {
        "score": fit.get("score", 0.0),
        "overlap": fit.get("overlap", []),
        "recommendation": "LIKE" if fit.get("score", 0) > 0.4 else "SKIP",
        "verdict": "LIKE" if fit.get("score", 0) > 0.4 else "SKIP",
        "converted_md": str(fetched.get("content") or ""),
        "life_context_used": life_context[:500],
    }


def _frontmatter_with_defaults(text: str, *, source_ref: str = "") -> tuple[str, str]:
    meta, body = lib._parse_skill_markdown(text)
    name = str(meta.get("name") or "ingested-skill")
    slug = lib._safe_skill_slug(name)
    base_slug = slug
    skills_dir = _skills_dir()
    idx = 0
    while (skills_dir / slug).exists() or (skills_dir / "_quarantine" / slug).exists():
        idx += 1
        slug = f"{base_slug}-{idx}"
    meta["name"] = slug
    meta.setdefault("description", str(meta.get("when_to_use") or "Imported skill."))
    meta.setdefault("swimmer_type", "GENERALIST_SWIMMER")
    meta.setdefault("action_type", "learn")
    meta.setdefault("affect_lanes", ["SEEKING"])
    meta.setdefault("stgm_mint", 4.0)
    meta.setdefault("pouw_label", slug.upper().replace("-", "_"))
    meta.setdefault("version", "0.1.0-ingested")
    if source_ref:
        meta.setdefault("source", source_ref)
    return f"{lib._frontmatter_block(meta)}\n\n{body}", slug


def _materialize_markdown_source(source: str | Path, *, source_ref: str = "") -> tuple[Path, str]:
    if isinstance(source, Path) or ("\n" not in str(source) and Path(str(source)).expanduser().exists()):
        path = Path(source).expanduser().resolve()
        if path.is_dir():
            text = (path / "SKILL.md").read_text(encoding="utf-8")
        else:
            text = path.read_text(encoding="utf-8")
    else:
        text = str(source)
    markdown, slug = _frontmatter_with_defaults(text, source_ref=source_ref)
    root = _state_dir() / "skill_inbox" / "manual" / slug
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(markdown, encoding="utf-8")
    return root, slug


def install_skill(source: str | Path, **kwargs) -> Dict[str, Any]:
    source_url = str(kwargs.pop("source_url", "") or "")
    kwargs.setdefault("skills_dir", _skills_dir())
    kwargs.setdefault("installed_by", "alice_skill_ingest")
    root, _slug = _materialize_markdown_source(source, source_ref=source_url)
    result = lib.install_skill(root, **kwargs)
    result = dict(result)
    result["ok"] = str(result.get("status")) in {"INSTALLED", "QUARANTINED"}
    result["path"] = result.get("destination")
    result["slug"] = result.get("skill_name")
    _log_receipt({
        "type": "INGEST_INSTALL",
        "action": "install_skill",
        "source": source_url or str(source),
        "status": result.get("status"),
        "skill_name": result.get("skill_name"),
    })
    return result


def ingest_skill(url: str = "", cost_justification: str = "", brain: Any = None,
                 **params) -> Dict[str, Any]:
    """Main high-level entry point for remote/marketplace ingestion."""
    url = url or str(params.get("url") or "")
    if url:
        fetched = fetch_skill_from_url(url)
        review = evaluate_skill_with_alice(fetched, brain=brain)
        install = None
        if review.get("verdict") == "LIKE" and review.get("converted_md"):
            install = install_skill(str(review["converted_md"]), source_url=url)
        result = {
            **review,
            "fetch": fetched,
            "install": install,
            "cost_justification": cost_justification or params.get("cost_justification", ""),
        }
        _log_receipt({
            "type": "INGEST_COMPLETE",
            "action": "ingest_skill",
            "url": url,
            "status": result.get("verdict"),
            "installed": bool(install and install.get("ok")),
        })
        return result
    return {"status": "NOT_IMPLEMENTED_YET", "params": params}


def pull_skill(*, marketplace: str = "", url: str = "", source_path: str = "",
               skill_id: str = "", **kwargs) -> Dict[str, Any]:
    """Receipted high-level pull used by the tool router.

    Delegates to swarm_skill_library (the same behavior the router used
    directly) and writes a skill_ingest.jsonl receipt so the action is
    traceable through this organ.
    """
    if marketplace:
        result = lib.pull_skill_from_marketplace(marketplace, skill_id=skill_id, **kwargs)
        source = f"marketplace:{marketplace}:{skill_id}"
    elif url:
        result = lib.pull_skill_from_url(url, **kwargs)
        source = url
    elif source_path:
        result = lib.ingest_skill_source(source_path, **kwargs)
        source = source_path
    else:
        return {"ok": False, "status": "REFUSED",
                "reason": "missing url/source_path/marketplace"}
    _log_receipt({
        "action": "pull_skill",
        "source": source,
        "status": result.get("status") if isinstance(result, dict) else None,
    })
    return result
