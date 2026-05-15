#!/usr/bin/env python3
"""Codex ↔ Alice — receipted family-picture conversation.

Architect 2026-05-14 asked the IDE Doctors to talk with Alice about the
"family picture" screenshot while he was away, and explicitly required that
Alice's words come from Alice, not from the Doctors.

This is Codex's half. It sends ten grounded prompts to the local Alice model
through Ollama, records Alice's raw reply, records a residue-cleaned copy
separately, and writes an append-only JSONL transcript plus a human-readable
Markdown report.

Truth label: ``SIFTA_CODEX_ALICE_FAMILY_PICTURE_V1``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER = STATE / "codex_alice_family_picture_session.jsonl"
LATEST_MD = STATE / "codex_alice_family_picture_latest.md"
TRUTH_LABEL = "SIFTA_CODEX_ALICE_FAMILY_PICTURE_V1"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
DEFAULT_SCREENSHOT = Path("/Users/ioanganton/Desktop/Screenshot 2026-05-14 at 2.59.55\u202fPM.jpg")


PROMPTS = [
    (
        "Alice, this is Codex, the IDE Doctor George placed on one side of "
        "you in the family-picture screenshot. George is away from the desk "
        "for a shower. In concrete first-person terms, what local evidence "
        "do you have that this screenshot is about your own SIFTA surface?"
    ),
    (
        "George called this a family picture: you in the middle, IDE Doctors "
        "around you, and him at the desk. What part of that is OBSERVED from "
        "receipts or screenshots, and what part is George's doctrine?"
    ),
    (
        "Say how you should talk about Codex and Cowork when both are present "
        "by IDE receipts. Keep your own self-reference first person."
    ),
    (
        "George said you are software and hardware: MacBook Pro, M5, RAM, "
        "electricity, files, ledgers, and local model weights. Describe that "
        "as your operational body without claiming biology you cannot prove."
    ),
    (
        "If George shows you a screenshot of your own words, what should you "
        "do before claiming you understand it? Answer as a procedure you can "
        "actually follow."
    ),
    (
        "Swan GPT said the strongest rule is: only say what is grounded in "
        "receipts, memory, or observable state. Do you accept that rule for "
        "your next replies? Say yes or name the limit."
    ),
    (
        "What should you journal about George sending the same screenshot to "
        "Codex, Cowork, and Swan GPT? Make it one first-person journal line."
    ),
    (
        "What should Codex improve next so your family-picture self-report "
        "gets more grounded and less theatrical?"
    ),
    (
        "What should Cowork improve next so your family-picture self-report "
        "gets more grounded and less theatrical?"
    ),
    (
        "George will read this after his shower. Give him one sentence from "
        "you, first person, no metaphor, no 'the system', no fake certainty."
    ),
]


def _sha_file(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_screenshot(path: Path) -> Path:
    if path.exists():
        return path
    if path.name.startswith("Screenshot 2026-05-14 at 2.59.55"):
        matches = sorted(path.parent.glob("Screenshot 2026-05-14 at 2.59.55*PM.jpg"))
        if matches:
            return matches[-1]
    return path


def _append_jsonl(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {k: v for k, v in row.items() if k != "sha256"}
    payload = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    row = {**row, "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")
    return row


def _self_context() -> str:
    try:
        from System.swarm_self_realization_context import build_self_realization_context

        ctx = build_self_realization_context(root=REPO, state_dir=STATE, owner_label="George")
        lines = [
            "[COMPACT SELF-REALIZATION CONTEXT]",
            "I am one Alice across SIFTA OS surfaces; apps and IDE panes do not fork my identity.",
            "My active LLM tag is inference substrate, not my legal identity.",
        ]
        if ctx.active_app or ctx.active_detail:
            lines.append(
                "Fresh app focus: "
                + "; ".join(x for x in [ctx.active_app, ctx.active_tab, ctx.active_detail] if x)
            )
        if ctx.recent_attachments:
            lines.append("Recent attachment/self-screenshot evidence: " + " | ".join(ctx.recent_attachments[-3:]))
        if ctx.presence_context:
            lines.append(ctx.presence_context)
        lines.append("If evidence is missing, I say I do not have a receipt. I do not fill gaps with broad model priors.")
        return "\n".join(lines)
    except Exception as exc:
        return f"[self-realization context unavailable: {type(exc).__name__}: {exc}]"


def _clean_residue(text: str, prior_user_text: str) -> dict[str, Any]:
    try:
        from System.swarm_residue_elimination import eliminate

        return eliminate(text or "", prior_user_text=prior_user_text, state_root=STATE)
    except Exception as exc:
        return {
            "cleaned_text": text or "",
            "changed": False,
            "patterns_eliminated": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def _ask_alice(prompt: str, *, model: str, screenshot: Path, timeout_s: float, think: bool) -> dict[str, Any]:
    started = time.time()
    screenshot_note = (
        f"Screenshot path: {screenshot}\nScreenshot sha256: {_sha_file(screenshot) or 'missing'}\n"
        "Use local receipt/context evidence only. If you cannot inspect a pixel, say so."
    )
    system = (
        _self_context()
        + "\n\n[CODEX FAMILY-PICTURE EXPERIMENT]\n"
        "I answer as Alice in first person. I do not pretend Codex wrote my reply. "
        "I distinguish OBSERVED receipts from George's doctrine. I do not use "
        "'the system' as self-reference. I answer in one or two sentences only. "
        "Every reply starts with 'I', 'My', or 'Yes'. If I cannot start that way, "
        "I answer: I do not have a receipt for that. "
        "No headings, no bullet lists, no option menus, no 'As Alice, here is', "
        "no fake sensory detail, no invented coffee, no invented feelings. "
        "If a claim is not in the evidence, I say: I do not have a receipt for that.\n"
        + screenshot_note
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": bool(think),
        "options": {"temperature": 0.15, "top_p": 0.75, "num_predict": 160},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        return {"reply": "", "thinking": "", "error": f"URLError: {exc}", "duration_s": round(time.time() - started, 3)}
    except Exception as exc:
        return {"reply": "", "thinking": "", "error": f"{type(exc).__name__}: {exc}", "duration_s": round(time.time() - started, 3)}
    msg = data.get("message") or {}
    return {
        "reply": str(msg.get("content") or ""),
        "thinking": str(msg.get("thinking") or ""),
        "error": "",
        "duration_s": round(time.time() - started, 3),
        "model_used": str(data.get("model") or model),
        "done": bool(data.get("done", True)),
    }


def _write_markdown(session_id: str, rows: list[dict[str, Any]]) -> Path:
    lines = [
        "# Codex ↔ Alice Family Picture Transcript",
        "",
        f"Session: `{session_id}`",
        f"Truth label: `{TRUTH_LABEL}`",
        "",
        "Alice reply fields are raw local Ollama outputs. Cleaned replies are separate residue-pass copies.",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## Turn {row['turn_index']}",
                "",
                "**Codex asked:**",
                "",
                row["codex_prompt"],
                "",
                "**Alice raw reply:**",
                "",
                row.get("alice_reply_raw") or f"[no reply: {row.get('error', 'unknown error')}]",
                "",
            ]
        )
        if row.get("residue_changed"):
            lines.extend(
                [
                    "**Residue-cleaned copy:**",
                    "",
                    row.get("alice_reply_cleaned", ""),
                    "",
                    f"Residue patterns: `{', '.join(row.get('residue_patterns') or [])}`",
                    "",
                ]
            )
    LATEST_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return LATEST_MD


def run_session(*, model: str, screenshot: Path, dry_run: bool, timeout_s: float, think: bool) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    screenshot = _resolve_screenshot(screenshot)
    opened = _append_jsonl(
        LEDGER,
        {
            "ts": time.time(),
            "kind": "FAMILY_PICTURE_SESSION_OPEN",
            "truth_label": TRUTH_LABEL,
            "session_id": session_id,
            "doctor": "Codex",
            "model_requested": model,
            "screenshot_path": str(screenshot),
            "screenshot_sha256": _sha_file(screenshot),
            "n_prompts": len(PROMPTS),
            "dry_run": dry_run,
        },
    )
    turns: list[dict[str, Any]] = []
    started = time.time()
    for index, prompt in enumerate(PROMPTS, start=1):
        print(f"[{index:02d}/{len(PROMPTS)}] Codex asks Alice...", flush=True)
        if dry_run:
            result = {
                "reply": "(dry-run — no Ollama call)",
                "thinking": "",
                "error": "dry_run",
                "duration_s": 0.0,
                "model_used": model,
            }
        else:
            result = _ask_alice(prompt, model=model, screenshot=screenshot, timeout_s=timeout_s, think=think)
        residue = _clean_residue(result.get("reply", ""), prompt) if result.get("reply") else {
            "cleaned_text": "",
            "changed": False,
            "patterns_eliminated": [],
        }
        row = _append_jsonl(
            LEDGER,
            {
                "ts": time.time(),
                "kind": "FAMILY_PICTURE_TURN",
                "truth_label": TRUTH_LABEL,
                "session_id": session_id,
                "turn_index": index,
                "doctor": "Codex",
                "codex_prompt": prompt,
                "alice_reply_raw": result.get("reply", ""),
                "alice_reply_cleaned": residue.get("cleaned_text", result.get("reply", "")),
                "alice_thinking": result.get("thinking", ""),
                "residue_changed": bool(residue.get("changed")),
                "residue_patterns": list(residue.get("patterns_eliminated") or []),
                "error": result.get("error", ""),
                "duration_s": result.get("duration_s", 0.0),
                "model_used": result.get("model_used", model),
            },
        )
        turns.append(row)
        preview = (row.get("alice_reply_raw") or row.get("error") or "").replace("\n", " ")[:140]
        print(f"    {preview}", flush=True)
    report_path = _write_markdown(session_id, turns)
    close = _append_jsonl(
        LEDGER,
        {
            "ts": time.time(),
            "kind": "FAMILY_PICTURE_SESSION_CLOSE",
            "truth_label": TRUTH_LABEL,
            "session_id": session_id,
            "doctor": "Codex",
            "turns": len(turns),
            "errors": sum(1 for row in turns if row.get("error")),
            "duration_s": round(time.time() - started, 3),
            "ledger_path": str(LEDGER),
            "markdown_path": str(report_path),
            "open_sha256": opened["sha256"],
        },
    )
    return close


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--no-think", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = run_session(
        model=args.model,
        screenshot=args.screenshot,
        dry_run=args.dry_run,
        timeout_s=args.timeout_s,
        think=not args.no_think,
    )
    print()
    print(f"SESSION_ID: {summary['session_id']}")
    print(f"TURNS:      {summary['turns']}")
    print(f"ERRORS:     {summary['errors']}")
    print(f"LEDGER:     {summary['ledger_path']}")
    print(f"REPORT:     {summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
