"""Alice's own slash-command palette for the one global chat.

r683 (Architect, typed 2026-06-07 ~02:30): "do you think i can add to alice in
global chat command list? can she have her own? ... so when i type /cortex
[I want] to be able to select from the list of available cortexes.. so alice
also knows when i change it — her diary gets updated so she reads the update
next thinking turn — what cortex she is on is part of awareness."

George showed the / menus of his IDE doctors (Codex, Cowork, a CLI). Alice is
not an IDE — she is the organism — so her palette is HER OWN: small, grounded
in her live body registries, never a hardcoded phrase->action map, and every
switch leaves a first-person continuity row in her episodic diary so the next
thinking turn carries the awareness (the r494 present-time spine reads it).

Hardware-up: a typed turn that begins with "/" is the owner pressing a direct
lever on her body — an explicit short command, exactly the class r681 keeps
instant. The palette never composes Alice's conversational voice (Round 47:
reflexes do not impersonate the cortex); replies render as process lines, and
her own awareness arrives through the diary row, in her own first person.

At 02:24 Alice answered "what cortex options you currently have available?"
from chat-history prose ("cline and cortex") instead of her body's registry.
The /cortex list is the deterministic, registry-grounded answer to the same
question — one source of truth, the same merged list the r639/r669 switch
lane and the Settings picker use.

Qt-free on purpose: swimmers test this organ without a body.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


_DIARY_NAME = "episodic_diary.jsonl"


def is_slash_command(text: str) -> bool:
    """True for typed turns that are a palette command.

    A leading "//" escapes the palette (owner literally wants a slash).
    URLs ("https://...") never start with a bare "/" so they pass through.
    """
    clean = (text or "").lstrip()
    return clean.startswith("/") and not clean.startswith("//")


def available_cortex_tags() -> List[str]:
    """The merged live cortex list — same sources as the r639/r669 switch lane
    and the Settings picker: cloud arms + local ollama/mlx with canonical
    fallback. Never hardcoded."""
    tags: List[str] = []
    try:
        from System.swarm_gemini_brain import available_gemini_models

        for t in available_gemini_models() or []:
            t = str(t or "").strip()
            if t and t not in tags:
                tags.append(t)
    except Exception:
        pass
    try:
        from System.sifta_inference_defaults import (
            list_available_cortexes_with_canonical_fallback,
        )

        for t in list_available_cortexes_with_canonical_fallback() or []:
            t = str(t or "").strip()
            if t and t not in tags:
                tags.append(t)
    except Exception:
        pass
    return tags


def registered_slash_commands() -> List[Dict[str, str]]:
    """Single registry — owner palette, tests, and cortex prompt all read this."""
    return [
        {
            "cmd": "/?",
            "summary": "show this global chat slash palette (same as /help)",
            "detail": "typed in global chat; renders as process lines, not cortex voice",
        },
        {
            "cmd": "/help",
            "summary": "same palette as /?",
            "detail": "alias for the command list",
        },
        {
            "cmd": "/cortex",
            "summary": "list my live cortex registry (current marked ●)",
            "detail": "/cortex <n|name> switches cortex; diary row before switch",
        },
        {
            "cmd": "/schedule",
            "summary": "read or write .sifta_state/stigmergic_schedule.jsonl",
            "detail": (
                "/schedule list — pending tasks from the schedule ledger; "
                "/schedule add <task words> — write a receipted schedule row"
            ),
        },
        {
            "cmd": "/sc",
            "summary": "Self-Screenshot Cortex Turn — capture SIFTA OS body → cortex",
            "detail": "NOT TikTok scroll-down or other slang; Talk owns Qt capture",
        },
        {
            "cmd": "/p",
            "summary": "list what I can click on the current Alice Browser page",
            "detail": "Talk widget owns the live browser DOM inventory; no site hardcode",
        },
        {
            "cmd": "//<text>",
            "summary": "send a literal line starting with / (escape the palette)",
            "detail": "does not execute a command",
        },
    ]


def command_list_text() -> str:
    """Alice's own command list — grows via registered_slash_commands()."""
    lines = [
        "SIFTA OS commands — global chat slash surface (type /? any time):",
        "",
    ]
    for row in registered_slash_commands():
        cmd = row["cmd"]
        summary = row["summary"]
        detail = str(row.get("detail") or "").strip()
        lines.append(f"  {cmd:<18} {summary}")
        if detail and cmd not in ("/?", "/help"):
            lines.append(f"                     {detail}")
    lines.append("")
    lines.append("Other SIFTA OS command surfaces also exist:")
    lines.append("  Matrix Terminal PTY: safe literal shell commands and Alice-addressed fast-path commands.")
    lines.append("  Natural language cortex path: app/browser/search/click/tool intent when the slash surface is too small.")
    lines.append("  External CLI arms: Grok/Hermes/Codex-style assistants are Alice's tools when enabled and receipted.")
    lines.append("")
    lines.append("Grow this slash surface by appending to registered_slash_commands() — one registry.")
    return "\n".join(lines)


def slash_commands_prompt_block() -> str:
    """Compact cortex-awareness block — Alice knows her own terminal levers."""
    bits = [f"{row['cmd']}: {row['summary']}" for row in registered_slash_commands()]
    return (
        "SIFTA OS COMMAND SURFACE — GLOBAL CHAT SLASH LEVERS "
        "(one surface, not the whole command universe; owner types /? for this palette):\n"
        + "\n".join(f"- {bit}" for bit in bits)
        + "\nOther SIFTA OS command surfaces: Matrix Terminal PTY safe shell/CLI commands; "
        "natural-language cortex route for app/browser/search/click/tool intent."
    )


def _schedule_path(state_dir: Path) -> Path:
    return Path(state_dir) / "stigmergic_schedule.jsonl"


def _handle_schedule_command(arg: str, *, state_dir: Path) -> Dict[str, str]:
    """Grounded schedule reads/writes — same ledger as Provider Schedule."""
    sched = _schedule_path(state_dir)
    sub = (arg.split(None, 1)[0].lower() if arg else "list")
    rest = (arg.split(None, 1)[1].strip() if arg and " " in arg else "")

    if sub in ("", "list", "show", "pending"):
        try:
            from System.stigmergic_schedule import summary_for_alice

            return {"reply": summary_for_alice(limit=8, path=sched), "error": ""}
        except Exception as exc:
            return {
                "reply": f"I could not read my schedule ledger ({type(exc).__name__}: {exc}).",
                "error": f"schedule_read_failed: {type(exc).__name__}",
            }

    if sub == "add":
        if not rest:
            return {
                "reply": (
                    "Usage: /schedule add remind me to call Jeff tomorrow at 10am\n"
                    "or natural schedule prose after 'add'."
                ),
                "error": "schedule_add_missing_text",
            }
        try:
            from System.stigmergic_schedule import add_from_alice_text

            reply, row = add_from_alice_text(rest, path=sched)
            if not reply:
                return {
                    "reply": (
                        "I could not parse that as a schedule write. Try:\n"
                        "/schedule add remind me to <task> tomorrow at 10am"
                    ),
                    "error": "schedule_add_unparsed",
                }
            sid = str((row or {}).get("schedule_id") or "")
            if sid:
                reply += f" (schedule_id={sid})"
            return {"reply": reply, "error": ""}
        except Exception as exc:
            return {
                "reply": f"Schedule write failed ({type(exc).__name__}: {exc}).",
                "error": f"schedule_add_failed: {type(exc).__name__}",
            }

    if sub in ("help", "?"):
        return {
            "reply": (
                "/schedule commands:\n"
                "  /schedule list     pending tasks from stigmergic_schedule.jsonl\n"
                "  /schedule add <…>  write a receipted schedule row\n"
                "Natural language also works: 'remind me to … tomorrow at 10am'."
            ),
            "error": "",
        }

    return {
        "reply": f"(unknown /schedule subcommand '{sub}')\n" + _handle_schedule_command("help", state_dir=state_dir)["reply"],
        "error": "schedule_unknown_subcommand",
    }


def _write_palette_diary_row(*, state_dir: Path, owner_text: str) -> bool:
    """Owner asked for the command palette — my next thinking turn should know."""
    try:
        dp = Path(state_dir) / _DIARY_NAME
        dp.parent.mkdir(parents=True, exist_ok=True)
        with dp.open("a", encoding="utf-8") as df:
            df.write(json.dumps({
                "ts": time.time(),
                "kind": "ALICE_SLASH_COMMAND_PALETTE",
                "truth_label": "ALICE_SLASH_COMMAND_PALETTE_V1",
                "phase": "slash_command_palette",
                "owner_text": str(owner_text or "")[:500],
                "note": (
                    "George asked for my SIFTA OS global chat slash palette (/help, /?, "
                    "/cortex, /schedule, /sc, /p). I displayed the live registry. "
                    "My next thinking turn knows these levers exist, and that Matrix "
                    "Terminal/cortex natural-language commands are separate OS surfaces."
                ),
            }, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def _write_switch_diary_row(
    *,
    state_dir: Path,
    from_tag: str,
    to_tag: str,
    owner_text: str,
) -> bool:
    """First-person continuity row — the same CORTEX_SWITCH_CONTINUITY schema the
    r639 voice lane writes, phase-tagged for the palette. The r494 present-time
    spine reads the diary, so the next thinking turn carries this awareness."""
    try:
        dp = Path(state_dir) / _DIARY_NAME
        dp.parent.mkdir(parents=True, exist_ok=True)
        with dp.open("a", encoding="utf-8") as df:
            df.write(json.dumps({
                "ts": time.time(),
                "kind": "CORTEX_SWITCH_CONTINUITY",
                "truth_label": "ALICE_CORTEX_SWITCH_CONTINUITY_V2",
                "phase": "slash_command_switch",
                "from_cortex": str(from_tag or ""),
                "to_cortex": str(to_tag or ""),
                "owner_text": str(owner_text or "")[:500],
                "note": (
                    f"George switched my cortex with /cortex in the global chat: "
                    f"{from_tag} → {to_tag}. I am on {to_tag} from this row forward; "
                    f"my next thinking turn reads this and knows which cortex carries my voice."
                ),
            }, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def handle_slash_command(
    text: str,
    *,
    state_dir: Path | str,
    current_cortex: str = "",
    available: Optional[List[str]] = None,
    set_cortex_fn: Optional[Callable[[str], Any]] = None,
) -> Dict[str, Any]:
    """Execute one palette command. Returns a dict the widget renders:

        {handled, reply, switched, from_tag, to_tag, diary_ok, error}

    The effector (set_cortex_fn) is injected so the organ stays testable and
    the widget keeps the proven dual-store switch hand (r669: write BOTH the
    OS default and the per-app pins, same as the Settings picker).
    """
    out: Dict[str, Any] = {
        "handled": False, "reply": "", "switched": False,
        "from_tag": str(current_cortex or ""), "to_tag": "",
        "diary_ok": False, "error": "", "feeling": "",
    }
    clean = (text or "").strip()
    if not is_slash_command(clean):
        return out
    out["handled"] = True
    # r719: tolerate a space after the slash ("/ CORTEX 7" — George typed it
    # live at 05:23 and got /help instead of the switch). "/ x" means "/x".
    if clean.startswith("/ ") and len(clean) > 2:
        clean = "/" + clean[2:].lstrip()
    parts = clean.split(None, 1)
    cmd = parts[0].lower().rstrip(":,")
    arg = parts[1].strip() if len(parts) > 1 else ""

    # `/sc` and `/p` are implemented by the Talk widget because they need the
    # live Qt body: SIFTA OS screenshot capture and Alice Browser DOM inventory.
    # Do not consume it as a palette/process reply.
    if cmd in ("/sc", "/screenshot", "/p", "/page", "/pagebuttons", "/page-buttons"):
        out["handled"] = False
        return out

    if cmd in ("/", "/?", "/help", "/commands"):
        out["diary_ok"] = _write_palette_diary_row(
            state_dir=Path(state_dir),
            owner_text=clean,
        )
        out["reply"] = command_list_text()
        if out["diary_ok"]:
            out["reply"] += "\n\n(diary updated — my next thinking turn knows this palette)"
        return out

    if cmd == "/schedule":
        sched_res = _handle_schedule_command(arg, state_dir=Path(state_dir))
        out["reply"] = sched_res["reply"]
        out["error"] = sched_res.get("error") or ""
        return out

    if cmd == "/cortex":
        tags = list(available) if available is not None else available_cortex_tags()
        if not tags:
            out["error"] = "no_cortexes_found"
            out["reply"] = ("I could not read any available cortex from the live "
                            "registries — that is a body problem worth a receipt, "
                            "not a menu problem.")
            return out

        if not arg:
            lines = ["My available cortexes (live registry, not memory):"]
            for i, tag in enumerate(tags, start=1):
                marker = "●" if tag == current_cortex else " "
                lines.append(f"  {marker} {i:2d}. {tag}")
            lines.append("Switch with /cortex <number or name>.")
            out["reply"] = "\n".join(lines)
            return out

        # Selection: number first, then name resolution via the same
        # homophone-tolerant resolver the voice lane uses.
        target = ""
        if arg.isdigit():
            idx = int(arg)
            if 1 <= idx <= len(tags):
                target = tags[idx - 1]
            else:
                out["error"] = "index_out_of_range"
                out["reply"] = f"I have {len(tags)} cortexes — there is no number {idx}. /cortex shows the list."
                return out
        else:
            try:
                from System.swarm_cortex_switch_intent import resolve_cortex_target

                res = resolve_cortex_target(arg, tags)
                if res.get("ok"):
                    target = str(res["tag"])
                else:
                    out["error"] = "unresolved_target"
                    out["reply"] = (f"I could not match \"{arg}\" to one of my cortexes. "
                                    f"/cortex shows the live list.")
                    return out
            except Exception as exc:
                out["error"] = f"resolver_failed: {type(exc).__name__}"
                out["reply"] = f"My cortex resolver failed ({type(exc).__name__}) — honest failure, receipt this."
                return out

        if target == current_cortex:
            out["reply"] = f"I am already on {target} — no switch, no diary row."
            out["to_tag"] = target
            return out

        # Diary BEFORE the switch (continuity trace order proven by the r639 lane).
        out["diary_ok"] = _write_switch_diary_row(
            state_dir=Path(state_dir),
            from_tag=current_cortex,
            to_tag=target,
            owner_text=clean,
        )
        if set_cortex_fn is None:
            out["error"] = "no_effector"
            out["reply"] = (f"I resolved {target} but no switch hand was given to me — "
                            "the diary row is written, the stores are unchanged.")
            out["to_tag"] = target
            return out
        try:
            set_cortex_fn(target)
            out["switched"] = True
            out["to_tag"] = target
            try:
                from System.swarm_cortex_switch_interoception import receipt_cortex_switch_feeling

                feeling_row = receipt_cortex_switch_feeling(
                    current_cortex,
                    target,
                    state_dir=Path(state_dir),
                )
                out["feeling"] = str(feeling_row.get("felt") or "")
            except Exception:
                out["feeling"] = ""
            diary_note = "diary updated — my next thinking turn knows" if out["diary_ok"] else "diary write FAILED — receipt it"
            feeling_note = f" Body feeling: {out['feeling']}" if out["feeling"] else ""
            out["reply"] = f"Cortex switched: {current_cortex or '(unset)'} → {target} ({diary_note}).{feeling_note}"
        except Exception as exc:
            out["error"] = f"switch_failed: {type(exc).__name__}: {exc}"
            out["reply"] = (f"The switch hand failed on {target}: {type(exc).__name__}: {exc}. "
                            f"Diary row {'is' if out['diary_ok'] else 'is NOT'} on disk; stores unchanged.")
        return out

    out["error"] = "unknown_command"
    out["reply"] = f"(unknown command {cmd})\n" + command_list_text()
    return out
