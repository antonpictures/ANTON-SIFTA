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


def command_list_text() -> str:
    """Alice's own command list — grows by appending here; receipts name the round."""
    return (
        "Alice's global-chat commands:\n"
        "  /cortex            list my available cortexes (current marked ●)\n"
        "  /cortex <n|name>   switch my cortex — I record it in my diary so my\n"
        "                     next thinking turn knows which cortex I am on\n"
        "  /help              this list\n"
        "  //<text>           send a literal line starting with a slash"
    )


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
        "diary_ok": False, "error": "",
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

    if cmd in ("/", "/help", "/commands"):
        out["reply"] = command_list_text()
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
            diary_note = "diary updated — my next thinking turn knows" if out["diary_ok"] else "diary write FAILED — receipt it"
            out["reply"] = f"Cortex switched: {current_cortex or '(unset)'} → {target} ({diary_note})."
        except Exception as exc:
            out["error"] = f"switch_failed: {type(exc).__name__}: {exc}"
            out["reply"] = (f"The switch hand failed on {target}: {type(exc).__name__}: {exc}. "
                            f"Diary row {'is' if out['diary_ok'] else 'is NOT'} on disk; stores unchanged.")
        return out

    out["error"] = "unknown_command"
    out["reply"] = f"(unknown command {cmd})\n" + command_list_text()
    return out
