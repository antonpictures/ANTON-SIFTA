#!/usr/bin/env python3
"""Field-driven skill proposals for Alice.

This organ scans local SIFTA traces for repeated successful actions, health
warnings, and public-distro/OOBE blockers.  It writes proposals to an
append-only JSONL ledger.  Pulling or extracting skills is supported, but it is
opt-in via ``allow_pull`` or ``SIFTA_SKILL_AUTO_PULL=1``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "skill_autoproposals.jsonl"
_HEAD = _STATE / "skill_autoproposals_head.json"
_SKILLS_DIR = _REPO / "skills"

TRACE_SCHEMA = "SIFTA_SKILL_AUTOPROPOSAL_TRACE_V1"
TRUTH_LABEL = "SIFTA_FIELD_SKILL_AUTOPROPOSAL_V1"

DEFAULT_TRACE_FILES = (
    "tool_router_trace.jsonl",
    "work_receipts.jsonl",
    "consumer_surface_trace.jsonl",
    "nanobot_skill_receipts.jsonl",
    "organ_field_vector.jsonl",
    "organism_doctor_trace.jsonl",
)

IGNORED_REPEAT_TOOLS = {
    "LLM_REGISTRATION",
    "LLM_SIGNOUT",
    "WORK_INTENT_RECEIPT",
    "TOOL_CALL_PRE_FLIGHT",
    "AGENT_ARM_RESEARCH",
    "CONSUMER_SURFACE_STATUS",
    "ORGAN_REGISTRY_LOOKUP",
    "SELF_IMPROVEMENT_STATUS",
    "SKILL_LIBRARY_STATUS",
    "SKILL_PULL",
    "SKILL_EXTRACT_FROM_TRACE",
    "SKILL_AUTOPROPOSAL_SCAN",
    "EDGE_DEMO_FIELD_STATE",
}


def _skill_library():
    try:
        from System import swarm_skill_library as lib

        return lib
    except Exception:
        import swarm_skill_library as lib

        return lib


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_slug(value: str) -> str:
    lib = _skill_library()
    if hasattr(lib, "_safe_skill_slug"):
        return str(lib._safe_skill_slug(value))
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "skill"


def _jsonl_tail(path: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = [line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _row_success(row: dict[str, Any]) -> bool:
    if bool(row.get("ok")) or bool(row.get("executed")):
        return True
    result = row.get("result")
    if isinstance(result, dict) and (result.get("ok") or result.get("executed")):
        return True
    status = str(row.get("status") or row.get("type") or "").upper()
    event = str(row.get("event") or "").upper()
    return (
        "SUCCESS" in status
        or "EXECUTED" in status
        or status.endswith("_OK")
        or (event.endswith("POST_FLIGHT") and str(row.get("ok")).lower() == "true")
    )


def _row_failure(row: dict[str, Any]) -> bool:
    if bool(row.get("error")):
        return True
    if row.get("ok") is False:
        return True
    status = str(row.get("status") or row.get("type") or "").upper()
    event = str(row.get("event") or "").upper()
    bad_tokens = ("FAIL", "ERROR", "WARN", "CRITICAL", "VETO", "REJECTED", "QUARANTINED")
    return any(token in status for token in bad_tokens) or any(token in event for token in bad_tokens)


def _tool_name(row: dict[str, Any]) -> str:
    value = row.get("tool") or row.get("tool_name") or row.get("action") or row.get("type") or ""
    if value:
        return str(value)
    params = row.get("params")
    if isinstance(params, dict):
        return str(params.get("tool") or "")
    return ""


def _trace_id(row: dict[str, Any]) -> str:
    for key in ("trace_id", "receipt_id", "kernel_process_receipt_id", "hash", "id"):
        value = row.get(key)
        if value:
            return str(value)
    digest = hashlib.sha256(
        json.dumps(row, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def _last_hash(state_dir: Path) -> str:
    data = _safe_json(state_dir / _HEAD.name)
    return str(data.get("last_hash") or "genesis")


def _write_head(state_dir: Path, new_hash: str) -> None:
    path = state_dir / _HEAD.name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"last_hash": new_hash}, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _write_receipt(
    *,
    action: str,
    payload: dict[str, Any],
    state_dir: Path = _STATE,
) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": TRACE_SCHEMA,
        "truth_label": TRUTH_LABEL,
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "action": action,
        "payload": payload,
        "prev_hash": _last_hash(state_dir),
    }
    row["hash"] = hashlib.sha256(
        json.dumps(row, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    line = json.dumps(row, sort_keys=True, default=str) + "\n"
    trace = state_dir / _TRACE.name
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(trace, line)
    except Exception:
        with trace.open("a", encoding="utf-8") as f:
            f.write(line)
    _write_head(state_dir, row["hash"])
    return row


def _recent_dedupe_keys(state_dir: Path, *, limit: int = 80) -> set[str]:
    keys: set[str] = set()
    for row in _jsonl_tail(state_dir / _TRACE.name, limit=limit):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        for proposal in payload.get("proposals", []) or []:
            if isinstance(proposal, dict) and proposal.get("dedupe_key"):
                keys.add(str(proposal["dedupe_key"]))
        for proposal in payload.get("actions", []) or []:
            if isinstance(proposal, dict) and proposal.get("dedupe_key"):
                keys.add(str(proposal["dedupe_key"]))
    return keys


def _known_skill_names(skills_dir: Path) -> set[str]:
    try:
        return {str(row.get("name") or "").lower() for row in _skill_library().build_skill_index(skills_dir)}
    except Exception:
        return set()


def _life_context(state_dir: Path, *, limit: int = 120) -> str:
    chunks: list[str] = []
    for name in DEFAULT_TRACE_FILES:
        path = state_dir / name
        for row in _jsonl_tail(path, limit=limit):
            chunks.append(f"{name}: {json.dumps(row, sort_keys=True, default=str)[:600]}")
    if chunks:
        return "\n".join(chunks)[-7000:]
    try:
        return str(_skill_library().current_life_context())
    except Exception:
        return ""


def _repeat_success_proposals(
    *,
    rows_by_file: dict[str, list[dict[str, Any]]],
    min_repeat: int,
    skills_dir: Path,
    existing_keys: set[str],
    allow_pull: bool,
    state_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for trace_name, rows in rows_by_file.items():
        for row in rows:
            if not _row_success(row):
                continue
            tool = _tool_name(row)
            if not tool:
                continue
            if tool.upper() in IGNORED_REPEAT_TOOLS:
                continue
            grouped[tool].append((trace_name, row))

    known = _known_skill_names(skills_dir)
    proposals: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    for tool, hits in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(hits) < min_repeat:
            continue
        skill_name = _safe_slug(f"repeat_{tool}")
        dedupe_key = f"repeat:{tool}:{len(hits)}"
        if dedupe_key in existing_keys or skill_name in known:
            continue
        trace_name, latest = hits[-1]
        proposal = {
            "proposal_id": str(uuid.uuid4()),
            "proposal_type": "EXTRACT_TRACE_SKILL",
            "dedupe_key": dedupe_key,
            "title": f"Extract repeated successful {tool} into a skill",
            "reason": (
                f"{tool} succeeded {len(hits)} times in recent field traces. "
                "This is a learned-life pattern, not a hardcoded agent."
            ),
            "confidence": min(1.0, round(len(hits) / float(max(min_repeat, 1) * 2), 3)),
            "tool_name": tool,
            "repeated_count": len(hits),
            "source_trace_file": trace_name,
            "source_trace_id": _trace_id(latest),
            "suggested_skill_name": skill_name,
            "suggested_tool_call": (
                "[TOOL_CALL: skill_extract_from_trace | "
                f"trace_file={trace_name} | trace_id={_trace_id(latest)} | name={skill_name} | "
                "cost_justification=Alice saw this successful action repeat in the local field]"
            ),
            "auto_executed": False,
        }
        if allow_pull:
            try:
                installed = _skill_library().extract_skill_from_trace(
                    trace_file=state_dir / trace_name,
                    trace_id=_trace_id(latest),
                    name=skill_name,
                    skills_dir=skills_dir,
                    allow_overwrite=False,
                    installed_by="alice_autoproposal",
                )
                proposal["auto_executed"] = True
                proposal["install_result"] = installed
                actions.append(proposal)
            except Exception as exc:
                proposal["auto_error"] = f"{type(exc).__name__}: {exc}"
                proposals.append(proposal)
        else:
            proposals.append(proposal)
    return proposals, actions


def _health_proposals(
    *,
    rows_by_file: dict[str, list[dict[str, Any]]],
    existing_keys: set[str],
) -> list[dict[str, Any]]:
    failures: Counter[str] = Counter()
    samples: dict[str, dict[str, Any]] = {}
    for trace_name, rows in rows_by_file.items():
        for row in rows:
            if not _row_failure(row):
                continue
            key = str(row.get("organ") or row.get("organ_id") or _tool_name(row) or trace_name)
            if key.upper() in IGNORED_REPEAT_TOOLS:
                continue
            failures[key] += 1
            samples[key] = row

    proposals: list[dict[str, Any]] = []
    for key, count in failures.most_common(5):
        dedupe_key = f"health:{key}:{count}"
        if dedupe_key in existing_keys or count < 2:
            continue
        proposals.append(
            {
                "proposal_id": str(uuid.uuid4()),
                "proposal_type": "HEALTH_SKILL_NEED",
                "dedupe_key": dedupe_key,
                "title": f"Find or build repair skill for {key}",
                "reason": f"{key} emitted {count} warning/error rows in the recent field.",
                "confidence": min(1.0, round(count / 8.0, 3)),
                "source_trace_id": _trace_id(samples[key]),
                "suggested_tool_call": (
                    "[TOOL_CALL: skill_library_status | "
                    "cost_justification=Alice needs to inspect available skills for a repeated health drop]"
                ),
                "auto_executed": False,
            }
        )
    return proposals


def _load_marketplace(source: str | Path | dict[str, Any]) -> tuple[dict[str, Any], str]:
    if isinstance(source, dict):
        return dict(source), "inline_manifest"
    source_s = str(source)
    parsed = urllib.parse.urlparse(source_s)
    if parsed.scheme in {"http", "https"}:
        ok, reason = _allowed_fetch_url(source_s)
        if not ok:
            raise ValueError(reason)
        with urllib.request.urlopen(source_s, timeout=10) as response:
            data = response.read(300_000)
        return json.loads(data.decode("utf-8")), source_s
    path = Path(source_s).expanduser().resolve()
    return json.loads(path.read_text(encoding="utf-8")), str(path)


def _allowed_fetch_url(url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        return False, "only_https_marketplace_urls_are_allowed"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing_host"
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"} or host.endswith(".local"):
        return False, "local_or_metadata_hosts_refused"
    return True, ""


def _marketplace_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("skills", manifest.get("entries", []))
    if isinstance(raw, dict):
        raw = list(raw.values())
    return [dict(row) for row in raw if isinstance(row, dict)]


def _marketplace_proposals(
    *,
    marketplace: str | Path | dict[str, Any] | None,
    life_context: str,
    allow_pull: bool,
    min_market_fit: float,
    skills_dir: Path,
    existing_keys: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not marketplace:
        return [], []
    proposals: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    try:
        manifest, manifest_ref = _load_marketplace(marketplace)
    except Exception as exc:
        return [
            {
                "proposal_id": str(uuid.uuid4()),
                "proposal_type": "MARKETPLACE_DISCOVERY_ERROR",
                "dedupe_key": f"market:error:{hashlib.sha256(str(marketplace).encode()).hexdigest()[:12]}",
                "title": "Marketplace could not be read",
                "reason": f"{type(exc).__name__}: {exc}",
                "confidence": 0.0,
                "auto_executed": False,
            }
        ], []

    lib = _skill_library()
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for entry in _marketplace_entries(manifest):
        text = " ".join(str(entry.get(key, "")) for key in ("id", "name", "title", "description", "summary", "tags"))
        fit = lib.skill_life_fit(text, life_context=life_context, explicit_request=False)
        scored.append((float(fit.get("score") or 0.0), entry, fit))
    scored.sort(key=lambda item: item[0], reverse=True)

    for score, entry, fit in scored[:3]:
        if score <= 0.0:
            continue
        identity = str(entry.get("id") or entry.get("name") or entry.get("title") or "market_skill")
        dedupe_key = f"market:{manifest_ref}:{identity}"
        if dedupe_key in existing_keys:
            continue
        proposal = {
            "proposal_id": str(uuid.uuid4()),
            "proposal_type": "MARKETPLACE_PULL",
            "dedupe_key": dedupe_key,
            "title": f"Pull marketplace skill: {identity}",
            "reason": "Marketplace entry matched recent local field context.",
            "confidence": round(score, 4),
            "marketplace": manifest_ref,
            "marketplace_choice": entry,
            "life_fit": fit,
            "suggested_tool_call": (
                "[TOOL_CALL: skill_pull | "
                f"marketplace={manifest_ref} | skill_id={identity} | "
                "cost_justification=Alice matched this marketplace skill to current local field needs]"
            ),
            "auto_executed": False,
        }
        if allow_pull and score >= min_market_fit:
            try:
                pulled = lib.pull_skill_from_marketplace(
                    marketplace,
                    skill_id=identity,
                    skills_dir=skills_dir,
                    life_context=life_context,
                    min_fit_score=min_market_fit,
                    force_install=False,
                    allow_overwrite=False,
                    installed_by="alice_autoproposal",
                )
                proposal["auto_executed"] = True
                proposal["install_result"] = pulled
                actions.append(proposal)
            except Exception as exc:
                proposal["auto_error"] = f"{type(exc).__name__}: {exc}"
                proposals.append(proposal)
        else:
            proposals.append(proposal)
    return proposals, actions


def _distro_proposals(repo_root: Path, existing_keys: set[str]) -> list[dict[str, Any]]:
    try:
        from System import swarm_consumer_surface as surface

        distro = surface.distro_status(repo_root)
    except Exception:
        return []
    blockers = list(distro.get("blockers") or [])
    if not blockers:
        return []
    digest = hashlib.sha256("\n".join(blockers).encode("utf-8")).hexdigest()[:12]
    dedupe_key = f"distro:{digest}"
    if dedupe_key in existing_keys:
        return []
    return [
        {
            "proposal_id": str(uuid.uuid4()),
            "proposal_type": "DISTRO_OOBE_GAP",
            "dedupe_key": dedupe_key,
            "title": "Close public distro/OOBE blockers",
            "reason": "Normal-human install path is not ready: " + "; ".join(blockers[:3]),
            "confidence": 1.0,
            "distro_status": distro.get("status"),
            "blockers": blockers,
            "suggested_tool_call": (
                "[TOOL_CALL: consumer_surface_status | page=distro | "
                "cost_justification=Alice needs the current distro blockers before public release work]"
            ),
            "auto_executed": False,
        }
    ]


def scan_field_for_skill_needs(
    *,
    marketplace: str | Path | dict[str, Any] | None = None,
    allow_pull: bool | None = None,
    min_repeat: int = 3,
    min_market_fit: float = 0.05,
    limit: int = 200,
    repo_root: str | Path | None = None,
    state_dir: str | Path | None = None,
    skills_dir: str | Path | None = None,
    dedupe: bool = True,
) -> dict[str, Any]:
    """Scan the local field and write skill proposals.

    ``allow_pull`` defaults to ``SIFTA_SKILL_AUTO_PULL=1``.  When false, this
    function only writes proposal receipts and suggested tool calls.
    """
    root = Path(repo_root) if repo_root is not None else _REPO
    state = Path(state_dir) if state_dir is not None else _STATE
    skill_root = Path(skills_dir) if skills_dir is not None else _SKILLS_DIR
    auto = bool(os.environ.get("SIFTA_SKILL_AUTO_PULL") == "1") if allow_pull is None else bool(allow_pull)
    state.mkdir(parents=True, exist_ok=True)
    skill_root.mkdir(parents=True, exist_ok=True)

    rows_by_file: dict[str, list[dict[str, Any]]] = {
        name: _jsonl_tail(state / name, limit=limit) for name in DEFAULT_TRACE_FILES
    }
    existing_keys = _recent_dedupe_keys(state) if dedupe else set()
    life_context = _life_context(state, limit=limit)

    proposals: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    repeat_proposals, repeat_actions = _repeat_success_proposals(
        rows_by_file=rows_by_file,
        min_repeat=max(2, int(min_repeat)),
        skills_dir=skill_root,
        existing_keys=existing_keys,
        allow_pull=auto,
        state_dir=state,
    )
    proposals.extend(repeat_proposals)
    actions.extend(repeat_actions)
    proposals.extend(_health_proposals(rows_by_file=rows_by_file, existing_keys=existing_keys))

    market_proposals, market_actions = _marketplace_proposals(
        marketplace=marketplace,
        life_context=life_context,
        allow_pull=auto,
        min_market_fit=float(min_market_fit),
        skills_dir=skill_root,
        existing_keys=existing_keys,
    )
    proposals.extend(market_proposals)
    actions.extend(market_actions)
    proposals.extend(_distro_proposals(root, existing_keys))

    payload = {
        "status": "AUTO_PULLED" if actions else ("PROPOSED" if proposals else "NO_FIELD_NEEDS_DETECTED"),
        "allow_pull": auto,
        "min_repeat": max(2, int(min_repeat)),
        "min_market_fit": float(min_market_fit),
        "scanned_files": {name: len(rows) for name, rows in rows_by_file.items()},
        "life_context_chars": len(life_context),
        "proposal_count": len(proposals),
        "action_count": len(actions),
        "proposals": proposals,
        "actions": actions,
    }
    receipt = _write_receipt(action="field_scan", payload=payload, state_dir=state)
    return {
        "ok": True,
        **payload,
        "receipt_id": receipt["trace_id"],
        "receipt_hash": receipt["hash"],
        "trace_file": str(state / _TRACE.name),
        "alice_summary": (
            f"skill_autoproposal_scan {payload['status']}: "
            f"{len(proposals)} proposals, {len(actions)} automatic actions"
        ),
    }


def latest_proposals(*, limit: int = 12, state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    state = Path(state_dir) if state_dir is not None else _STATE
    out: list[dict[str, Any]] = []
    for row in reversed(_jsonl_tail(state / _TRACE.name, limit=max(20, limit * 5))):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        receipt_id = str(row.get("trace_id") or "")
        receipt_hash = str(row.get("hash") or "")
        for section in ("actions", "proposals"):
            for proposal in payload.get(section, []) or []:
                if not isinstance(proposal, dict):
                    continue
                item = dict(proposal)
                item["receipt_id"] = receipt_id
                item["receipt_hash"] = receipt_hash
                item["receipt_status"] = payload.get("status")
                out.append(item)
                if len(out) >= limit:
                    return out
    return out


def run_once(**kwargs: Any) -> dict[str, Any]:
    return scan_field_for_skill_needs(**kwargs)


def run_daemon(*, interval_s: float = 60.0, **kwargs: Any) -> None:
    while True:
        scan_field_for_skill_needs(**kwargs)
        time.sleep(max(5.0, float(interval_s)))


def _main() -> int:
    parser = argparse.ArgumentParser(description="Scan SIFTA field traces for skill proposals.")
    parser.add_argument("--marketplace", default="", help="optional marketplace manifest path or HTTPS URL")
    parser.add_argument("--allow-pull", action="store_true", help="install/extract matching skills instead of proposing only")
    parser.add_argument("--min-repeat", type=int, default=3)
    parser.add_argument("--min-market-fit", type=float, default=0.05)
    parser.add_argument("--watch", action="store_true", help="keep scanning on an interval")
    parser.add_argument("--interval", type=float, default=60.0)
    args = parser.parse_args()
    kwargs = {
        "marketplace": args.marketplace or None,
        "allow_pull": args.allow_pull,
        "min_repeat": args.min_repeat,
        "min_market_fit": args.min_market_fit,
    }
    if args.watch:
        run_daemon(interval_s=args.interval, **kwargs)
        return 0
    print(json.dumps(scan_field_for_skill_needs(**kwargs), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
