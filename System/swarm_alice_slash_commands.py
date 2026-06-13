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
import os
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


def last_thinking_models(state_dir: Path | str, *, n: int = 8) -> List[Dict[str, str]]:
    """Newest-last thinking turns with the model that actually ran each one.

    r985 — the ledger-grounded answer to "which model did you use last round?".
    Reads `alice_conversation.jsonl` (handles both the hash-chained wrapped
    rows {event_id, ts, payload{...}} and legacy flat rows), keeps alice turns
    whose `model` is a real cortex tag (palette/system rows excluded), and
    returns [{when, ts, model, text_head}]. Never raises.
    """
    out: List[Dict[str, str]] = []
    try:
        import time as _time

        ledger = Path(state_dir) / "alice_conversation.jsonl"
        if not ledger.exists():
            return []
        turns: List[Dict[str, str]] = []
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            if not isinstance(payload, dict) or payload.get("role") != "alice":
                continue
            model = str(payload.get("model") or "").strip()
            if not model or model in ("slash_command_palette", "deterministic", "system"):
                continue
            try:
                ts = float(payload.get("ts") or 0.0)
            except (TypeError, ValueError):
                ts = 0.0
            text = " ".join(str(payload.get("text") or "").split())
            turns.append({
                "ts": f"{ts:.3f}",
                "when": _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts)) if ts else "(no ts)",
                "model": model,
                "text_head": text[:60],
            })
        out = turns[-max(1, int(n)):]
    except Exception:
        return []
    return out


def _norm_cortex_tag(tag: str) -> str:
    """Compare cortex tags by their core: provider arms by prefix (claude:,
    cline:), local weights by their model stem. So a 'claude:...' selection
    matches a 'claude-fable-5' thinking turn, and an
    'alice-m5-cortex-8b-6.3gb:latest' selection matches the same thinking tag."""
    t = str(tag or "").strip().lower()
    if not t:
        return ""
    for prov in ("claude", "cline", "mimo", "codex", "grok", "qwen", "antigravity", "gemini"):
        if t.startswith(prov + ":") or t.startswith(prov + "-"):
            return prov
    return t.split(":", 1)[0]


def cortex_selection_mismatches(state_dir: Path | str, *, n: int = 6) -> List[Dict[str, str]]:
    """r988 (r985 carried): where did the model that ACTUALLY thought diverge
    from the cortex George last selected? The 13:53 incident: /cortex 9 picked
    the 4.4GB e2b, but the next thinking turns are receipted on the 8B. This
    reads the selection-receipt ledger + the conversation ledger and reports
    each thinking turn whose model does not match the selection active at that
    time. Newest last. Pure read, never raises. Rows decide (§6)."""
    out: List[Dict[str, str]] = []
    try:
        import time as _time

        sd = Path(state_dir)
        sels: List[tuple] = []  # (ts, normalized_selected)
        sel_path = sd / "cortex_selection_receipts.jsonl"
        if sel_path.exists():
            for line in sel_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sels.append((float(r.get("ts") or 0.0), _norm_cortex_tag(r.get("selected_model") or "")))
        sels.sort()

        def _selected_at(ts: float) -> str:
            active = ""
            for sts, sval in sels:
                if sts <= ts:
                    active = sval
                else:
                    break
            return active

        for turn in last_thinking_models(sd, n=max(n * 4, 24)):
            try:
                ts = float(turn.get("ts") or 0.0)
            except (TypeError, ValueError):
                ts = 0.0
            actual = _norm_cortex_tag(turn.get("model") or "")
            selected = _selected_at(ts) if sels else ""
            if selected and actual and selected != actual:
                out.append({
                    "when": turn.get("when", ""),
                    "selected": selected,
                    "actual_model": turn.get("model", ""),
                    "actual": actual,
                    "text_head": turn.get("text_head", ""),
                })
        out = out[-max(1, int(n)):]
    except Exception:
        return []
    return out


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
            "summary": "list my live cortex registry (current marked ●, brains marked ←)",
            "detail": "/cortex <n|name> switches; /cortex llm shows the brain behind the selected provider; /cortex history prints which model actually thought each turn (ledger rows, not narrative)",
        },
        {
            "cmd": "/cortex llm",
            "summary": "show/pin the selected cortex provider's underlying LLM when this organ can steer it",
            "detail": (
                "/cortex llm — render numbered lists (ledger-strict); bare N binds the last list shown; "
                "/cortex llm cline N and /cortex pin claude N are canonical; spoken mutations echo Confirm?"
            ),
        },
        {
            "cmd": "/grok",
            "summary": "show/steer Grok OAuth CLI health and fast model pin",
            "detail": (
                "/grok health — read OAuth/failover state; "
                "/grok fast pins grok-composer-2.5-fast; "
                "/grok build pins grok-build; /grok default clears the pin"
            ),
        },
        {
            "cmd": "/heart",
            "summary": "pulse Alice's hardware-grounded heart ledger",
            "detail": "monotonic timer pacemaker + real power/thermal sensor when the host exposes it",
        },
        {
            "cmd": "/speech",
            "summary": "show speech-lane weights and last spoken vs suppressed sentences",
            "detail": "/speech budget <seconds> — change spoken-time budget for the mouth selector",
        },
        {
            "cmd": "/field",
            "summary": "render unified organ vitals from organ_field.jsonl",
            "detail": "one line per organ: health, load, staleness, top signal",
        },
        {
            "cmd": "/ask-fable",
            "summary": "show or append questions_for_fable.jsonl for George to relay",
            "detail": "/ask-fable <question> — honest I-don't-know lane; no penalty",
        },
        {
            "cmd": "/improve",
            "summary": "show self-improvement proposals and outcomes",
            "detail": "last N proposals: target, predicted vs measured, KEPT/REVERTED",
        },
        {
            "cmd": "/quorum",
            "summary": "show quorum vote breakdown for a proposal id",
            "detail": "/quorum <proposal_id_prefix> — weights, floors, pass/fail",
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


def _latest_grok_failover(state_dir: Path) -> Dict[str, Any]:
    ledger = Path(state_dir) / "cortex_failover.jsonl"
    latest: Dict[str, Any] = {}
    if not ledger.exists():
        return latest
    try:
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            hay = json.dumps(row, ensure_ascii=False).lower()
            if "grok" in hay:
                latest = row
    except Exception:
        return {}
    return latest


def _handle_grok_command(
    out: Dict[str, Any],
    arg: str,
    *,
    state_dir: Path,
    owner_text: str,
) -> Dict[str, Any]:
    """Grok OAuth/CLI health lever.

    This does not run a paid generation call. It reads local health/failover
    receipts and lets George choose the concrete Grok CLI model used by the
    Talk fallback path through SIFTA_GROK_CLI_MODEL.
    """
    sub = (arg or "health").strip().lower()
    cur = os.environ.get("SIFTA_GROK_CLI_MODEL", "").strip()
    pins = {
        "fast": "grok-composer-2.5-fast",
        "composer": "grok-composer-2.5-fast",
        "composer-fast": "grok-composer-2.5-fast",
        "build": "grok-build",
        "slow": "grok-build",
    }
    if sub in pins or sub in {"default", "clear", "off", "reset"}:
        target = pins.get(sub, "")
        if target:
            os.environ["SIFTA_GROK_CLI_MODEL"] = target
        else:
            os.environ.pop("SIFTA_GROK_CLI_MODEL", None)
        out["switched"] = cur != target
        out["from_tag"] = f"grok-cli-model:{cur or '(resolver default)'}"
        out["to_tag"] = f"grok-cli-model:{target or '(resolver default)'}"
        out["diary_ok"] = _write_switch_diary_row(
            state_dir=state_dir,
            from_tag=out["from_tag"],
            to_tag=out["to_tag"],
            owner_text=owner_text,
        )
        diary_note = "diary updated" if out["diary_ok"] else "diary write FAILED"
        out["reply"] = (
            f"Grok CLI model pin: {cur or '(resolver default)'} -> "
            f"{target or '(resolver default)'} ({diary_note}). "
            "This steers the OAuth CLI fallback used when grok:grok-4.3 resolves to the local grok command."
        )
        return out

    if sub not in {"", "health", "status", "models", "model"}:
        out["error"] = "grok_unknown_subcommand"
        out["reply"] = (
            f"(unknown /grok subcommand '{sub}')\n"
            "Use /grok health, /grok fast, /grok build, or /grok default."
        )
        return out

    try:
        from System.swarm_cortex_auth_health import check_xai_oauth_health

        health = check_xai_oauth_health(state_dir)
    except Exception as exc:
        health = {"status": "unknown", "reason": f"health_probe_failed:{type(exc).__name__}", "last_failover_age_s": None}
    latest = _latest_grok_failover(state_dir)
    model_pin = cur or "(resolver default: grok-build for grok:grok-4.3)"
    lines = [
        "Grok cortex health (receipt-grounded, no paid generation call):",
        f"  OAuth: {health.get('status')} ({health.get('reason')})",
        f"  CLI model pin: {model_pin}",
    ]
    if latest:
        kind = latest.get("kind") or "grok_failover"
        head = str(latest.get("error_head") or latest.get("reason") or "")[:140]
        lines.append(f"  Last Grok failover: {kind} :: {head}")
    else:
        lines.append("  Last Grok failover: none found in this state_dir.")
    lines.append("  Fast lever: /grok fast -> SIFTA_GROK_CLI_MODEL=grok-composer-2.5-fast")
    lines.append("  Build lever: /grok build -> SIFTA_GROK_CLI_MODEL=grok-build")
    lines.append("  Clear lever: /grok default -> resolver default")
    out["reply"] = "\n".join(lines)
    return out


def _grok_attached_models_for_pin(state_dir: Path, selected: str) -> tuple[List[str], Callable[[str], str]]:
    try:
        from System.swarm_cortex_capabilities import (
            attached_models_for_cortex,
            format_attached_model,
            sync_cortex_attached_models_catalog,
        )

        sync_cortex_attached_models_catalog(state_dir=Path(state_dir))
        rec = attached_models_for_cortex(selected or "grok:grok-4.3", state_dir=Path(state_dir))
        models = [str(m) for m in (rec.get("attached_models") or []) if str(m or "").strip()]
        if models:
            return models, format_attached_model
    except Exception:
        pass
    return ["grok-composer-2.5-fast", "grok-build"], str


def _fireworks_attached_models_for_pin(
    state_dir: Path,
    selected: str,
) -> tuple[List[str], Callable[[str], str], str]:
    try:
        from System.sifta_inference_defaults import CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
        from System.swarm_cortex_capabilities import (
            attached_models_for_cortex,
            format_attached_model,
            sync_cortex_attached_models_catalog,
        )
        from System.swarm_fireworks_qwen_config import (
            fireworks_model_for_qwen_cortex,
            is_qwen_fireworks_cortex,
        )

        sync_cortex_attached_models_catalog(state_dir=Path(state_dir))
        catalog_key = (
            selected
            if is_qwen_fireworks_cortex(selected)
            else CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
        )
        rec = attached_models_for_cortex(catalog_key, state_dir=Path(state_dir))
        if not rec.get("attached_models") and catalog_key != CANONICAL_CLOUD_QWEN_PREMIUM_KIMI:
            rec = attached_models_for_cortex(
                CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,
                state_dir=Path(state_dir),
            )
        models = [str(m) for m in (rec.get("attached_models") or []) if str(m or "").strip()]
        active = fireworks_model_for_qwen_cortex(selected or CANONICAL_CLOUD_QWEN_PREMIUM_KIMI)
        if models:
            return models, format_attached_model, active
    except Exception:
        pass
    from System.swarm_fireworks_qwen_config import FIREWORKS_CORTEX_ATTACHED_MODELS

    return list(FIREWORKS_CORTEX_ATTACHED_MODELS), str, ""


def _handle_fireworks_llm_pin(
    out: Dict[str, Any],
    arg: str,
    *,
    state_dir: Path,
    owner_text: str,
    current_cortex: str,
) -> Dict[str, Any]:
    from System.swarm_fireworks_qwen_config import (
        FIREWORKS_MODEL_PIN_ENV,
        fireworks_model_slug,
        normalize_fireworks_model_path,
    )

    models, fmt, active_default = _fireworks_attached_models_for_pin(state_dir, current_cortex)
    cur = normalize_fireworks_model_path(str(os.environ.get(FIREWORKS_MODEL_PIN_ENV, "")).strip())
    if not cur:
        cur = normalize_fireworks_model_path(active_default)
    low = (arg or "").strip().lower()
    if low in ("default", "cli", "clear", "off", "reset"):
        target = ""
    elif low.isdigit():
        idx = int(low)
        if not (1 <= idx <= len(models)):
            out["error"] = "fireworks_llm_index_out_of_range"
            out["reply"] = (
                f"Fireworks has {len(models)} attached LLMs here — there is no number {idx}. "
                "Run /cortex llm while the qwen/Fireworks cortex is selected."
            )
            return out
        target = normalize_fireworks_model_path(models[idx - 1])
    else:
        target = normalize_fireworks_model_path(arg.split()[0].strip())
    if target == cur:
        slug = fireworks_model_slug(target) or "(cortex tag default)"
        out["reply"] = f"Fireworks model is already {fmt(target) if target else slug} — no change."
        return out
    if target:
        os.environ[FIREWORKS_MODEL_PIN_ENV] = target
    else:
        os.environ.pop(FIREWORKS_MODEL_PIN_ENV, None)
    out["diary_ok"] = _write_switch_diary_row(
        state_dir=Path(state_dir),
        from_tag=f"fireworks-model:{fireworks_model_slug(cur) or '(cortex tag)'}",
        to_tag=f"fireworks-model:{fireworks_model_slug(target) or '(cortex tag)'}",
        owner_text=owner_text,
    )
    out["switched"] = True
    out["from_tag"] = cur
    out["to_tag"] = target
    diary_note = "diary updated" if out["diary_ok"] else "diary write FAILED — receipt it"
    out["reply"] = (
        f"Fireworks model pin: {fmt(cur) if cur else '(cortex tag default)'} → "
        f"{fmt(target) if target else '(cortex tag default)'} ({diary_note}). "
        "This steers qwen/Fireworks Talk dispatch via SIFTA_FIREWORKS_MODEL."
    )
    return out


def _is_direct_weight_cortex(tag: str) -> bool:
    """True when the cortex tag IS the model — no upstream sub-model picker."""
    low = str(tag or "").strip().lower()
    if not low:
        return False
    if low.startswith(("diffusion:", "usd:", "mlx-vlm:", "mlx:")):
        return True
    if low.startswith(("alice-", "sifta-", "igorls/", "krishairnd/")):
        return True
    if low.endswith(":latest") and "/" not in low.split(":", 1)[0]:
        return True
    return False


def _cortex_llm_direct_brain_block(selected: str) -> List[str]:
    """Per-cortex truth when one tag = one brain (George r1065 diffusion ask)."""
    sel = str(selected or "").strip()
    low = sel.lower()
    if not sel:
        return []
    if low.startswith(("diffusion:", "usd:")):
        bare = sel.split(":", 1)[-1]
        lines = [
            "Cortex family: local diffusion decode (denoising LM — not autoregressive).",
            "LLMs in use: exactly one. The picker tag is the whole brain:",
            f"  ●  1. {sel}",
        ]
        try:
            from System.swarm_diffusion_cortex import is_cli_built, resolve_model_spec

            _path, entry, err = resolve_model_spec(sel)
            display = str(entry.get("display") or bare)
            lines.append(f"  Runner: llama-diffusion-cli ({'built' if is_cli_built() else 'missing'})")
            lines.append(f"  Catalog: {display}")
            if _path:
                lines.append(f"  GGUF on disk: {_path}")
            elif err:
                lines.append(f"  Install status: {err}")
        except Exception as exc:
            lines.append(f"  Probe: {type(exc).__name__}")
        lines.append(
            "  No sub-model list here — switch diffusion ids with /cortex <n>, not /cortex llm N."
        )
        return lines
    if low.startswith("mlx-vlm:"):
        return [
            "Cortex family: local MLX vision-language model (VLM eye / unified multimodal).",
            "LLMs in use: exactly one — the mlx-vlm tag is the weight bundle:",
            f"  ●  1. {sel}",
            "  No upstream picker — pick another mlx-vlm row with /cortex <n>.",
        ]
    if low.startswith("mlx:"):
        return [
            "Cortex family: local MLX cortex (mlx-omni-server).",
            "LLMs in use: exactly one:",
            f"  ●  1. {sel}",
            "  No sub-model picker on this lane.",
        ]
    if _is_direct_weight_cortex(sel):
        return [
            "Cortex family: local Ollama weights (autoregressive GGUF on this node).",
            "LLMs in use: exactly one — the Ollama tag IS the model:",
            f"  ●  1. {sel}",
            "  No upstream picker — /cortex <n> selects a different installed tag.",
        ]
    if low.startswith("antigravity:"):
        return [
            "Cortex family: Google Antigravity auto-router (`agy`).",
            "Upstream model is chosen inside Antigravity (Gemini/Claude mix) — not a single fixed LLM id here.",
            f"  Selected surface tag: {sel}",
            "  Re-run /cortex llm after you change agy settings; I probe what I can see.",
        ]
    return []


def _handle_grok_llm_pin(
    out: Dict[str, Any],
    arg: str,
    *,
    state_dir: Path,
    owner_text: str,
    current_cortex: str,
) -> Dict[str, Any]:
    models, fmt = _grok_attached_models_for_pin(state_dir, current_cortex)
    cur = os.environ.get("SIFTA_GROK_CLI_MODEL", "").strip()
    low = (arg or "").strip().lower()
    if low in ("default", "cli", "clear", "off", "reset"):
        target = ""
    elif low.isdigit():
        idx = int(low)
        if not (1 <= idx <= len(models)):
            out["error"] = "grok_llm_index_out_of_range"
            out["reply"] = (
                f"Grok has {len(models)} attached LLMs here — there is no number {idx}. "
                "/cortex llm shows the Grok list. Claude arm was not touched."
            )
            return out
        target = models[idx - 1]
    else:
        aliases = {
            "fast": "grok-composer-2.5-fast",
            "composer": "grok-composer-2.5-fast",
            "composer-fast": "grok-composer-2.5-fast",
            "build": "grok-build",
            "slow": "grok-build",
        }
        target = aliases.get(low, arg.split()[0].strip())
        if target.lower().startswith("grok:"):
            target = target.split(":", 1)[1].strip()
    if target == cur:
        out["reply"] = f"Grok attached LLM is already pinned to {fmt(target) if target else '(resolver default)'} — no change. Claude arm untouched."
        return out
    if target:
        os.environ["SIFTA_GROK_CLI_MODEL"] = target
    else:
        os.environ.pop("SIFTA_GROK_CLI_MODEL", None)
    out["diary_ok"] = _write_switch_diary_row(
        state_dir=Path(state_dir),
        from_tag=f"grok-cli-model:{cur or '(resolver default)'}",
        to_tag=f"grok-cli-model:{target or '(resolver default)'}",
        owner_text=owner_text,
    )
    out["switched"] = True
    out["from_tag"] = cur
    out["to_tag"] = target
    diary_note = "diary updated" if out["diary_ok"] else "diary write FAILED — receipt it"
    out["reply"] = (
        f"Grok attached LLM pin: {fmt(cur) if cur else '(resolver default)'} → "
        f"{fmt(target) if target else '(resolver default)'} ({diary_note}). "
        "This steers Grok OAuth/CLI Talk dispatch. Claude arm untouched."
    )
    return out


# r943: known underlying models for the claude arm. The pin is honored by
# System/swarm_agent_arm_launcher.py (--model flag); the CLI must have access.
# This list is suggestions, not a cage — /cortex llm <any-model-id> also works,
# and a wrong id fails honestly at dispatch with the CLI's own error.
_CLAUDE_ARM_KNOWN_MODELS: List[str] = [
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-3",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]


def _cortex_llm_capabilities(state_dir: Path):
    try:
        from System.swarm_cortex_capabilities import (
            attached_model_matches_active,
            attached_models_for_cortex,
            format_attached_model,
            sync_cortex_attached_models_catalog,
        )

        sync_cortex_attached_models_catalog(state_dir=Path(state_dir))
        return attached_model_matches_active, attached_models_for_cortex, format_attached_model
    except Exception:
        return None, None, str  # type: ignore[return-value]


def _record_primary_llm_list(
    *,
    namespace: str,
    items: List[str],
    labels: List[str],
    selected_cortex: str,
    owner_text: str,
    state_dir: Path,
) -> Dict[str, Any]:
    from System.swarm_cortex_llm_list_binding import record_rendered_list

    return record_rendered_list(
        namespace=namespace,
        items=items,
        labels=labels,
        selected_cortex=selected_cortex,
        is_primary=True,
        owner_text=owner_text,
        state_dir=state_dir,
    )


def _apply_claude_arm_pin(
    out: Dict[str, Any],
    target: str,
    *,
    state_dir: Path,
    owner_text: str,
    binding: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    import os

    cur = str(os.environ.get("SIFTA_CLAUDE_ARM_MODEL", "")).strip()
    if target == cur:
        out["reply"] = f"My claude arm is already pinned to {target or '(launcher/CLI default)'} — no change."
        return out
    if target:
        os.environ["SIFTA_CLAUDE_ARM_MODEL"] = target
    else:
        os.environ.pop("SIFTA_CLAUDE_ARM_MODEL", None)
    out["diary_ok"] = _write_switch_diary_row(
        state_dir=Path(state_dir),
        from_tag=f"claude-arm-llm:{cur or '(default)'}",
        to_tag=f"claude-arm-llm:{target or '(default)'}",
        owner_text=owner_text,
    )
    out["switched"] = True
    out["from_tag"] = cur
    out["to_tag"] = target
    diary_note = "diary updated" if out["diary_ok"] else "diary write FAILED — receipt it"
    out["reply"] = (
        f"Claude-arm LLM pin: {cur or '(default)'} → {target or '(launcher/CLI default)'} "
        f"({diary_note}). Every claude dispatch from now runs --model {target}."
        if target
        else f"Claude-arm LLM pin cleared: {cur or '(default)'} → launcher/CLI default ({diary_note})."
    )
    if binding:
        from System.swarm_cortex_llm_list_binding import write_binding_receipt

        write_binding_receipt(
            action="applied_claude_pin",
            payload={
                "binding": binding,
                "from_pin": cur,
                "to_pin": target,
            },
            state_dir=state_dir,
        )
    return out


def _refuse_stale_or_ambiguous_llm(
    out: Dict[str, Any],
    *,
    state_dir: Path,
    owner_text: str,
    current_cortex: str,
    error_code: str,
    index: int = 0,
) -> Dict[str, Any]:
    out["error"] = error_code
    render = _handle_cortex_llm(
        {"handled": True, "reply": "", "switched": False, "diary_ok": False, "error": ""},
        "",
        state_dir=state_dir,
        owner_text=owner_text,
        current_cortex=current_cortex,
        ingress_kind="typed",
    )
    prefix = (
        f"{index} in which picker? I need a fresh numbered list — here is what I last know:\n\n"
        if index
        else "I need a fresh numbered list before a bare number can bind — here is what I last know:\n\n"
    )
    out["reply"] = prefix + str(render.get("reply") or "")
    out["reply"] += (
        "\n\nBare /cortex llm N binds to the list rendered above (ledger-strict). "
        "For zero ambiguity use /cortex llm cline N or /cortex pin claude N."
    )
    return out


def _handle_cortex_pin(
    out: Dict[str, Any],
    arg: str,
    *,
    state_dir: Path,
    owner_text: str,
    current_cortex: str = "",
    ingress_kind: str = "typed",
) -> Dict[str, Any]:
    """Canonical namespaced pin: /cortex pin claude 4."""
    return _handle_cortex_llm_mutation(
        out,
        f"pin {arg}".strip(),
        state_dir=state_dir,
        owner_text=owner_text,
        current_cortex=current_cortex,
        ingress_kind=ingress_kind,
    )


def _handle_cortex_llm_mutation(
    out: Dict[str, Any],
    arg: str,
    *,
    state_dir: Path,
    owner_text: str,
    current_cortex: str = "",
    ingress_kind: str = "typed",
) -> Dict[str, Any]:
    import os

    from System.swarm_cortex_llm_list_binding import (
        NAMESPACE_CLAUDE,
        NAMESPACE_DIRECT,
        NAMESPACE_GROK,
        NAMESPACE_QWEN,
        UPSTREAM_NAMESPACES,
        clear_pending_binding,
        close_incident_if_spark_safe,
        load_pending_binding,
        mutation_echo,
        parse_mutation_arg,
        resolve_binding,
        save_pending_binding,
        write_binding_receipt,
    )

    selected = str(current_cortex or "").strip()
    grok_models, grok_fmt = _grok_attached_models_for_pin(state_dir, selected)
    fireworks_models, fireworks_fmt, _fireworks_active = _fireworks_attached_models_for_pin(
        state_dir, selected
    )
    parsed = parse_mutation_arg(arg)
    claude_before = str(os.environ.get("SIFTA_CLAUDE_ARM_MODEL", "")).strip()

    if parsed.kind == "confirm":
        pending = load_pending_binding(state_dir=state_dir)
        if not pending:
            out["error"] = "no_pending_binding"
            out["reply"] = "No pending /cortex llm binding to confirm."
            return out
        clear_pending_binding(state_dir=state_dir)
        ns = str(pending.get("namespace") or "")
        model_id = str(pending.get("model_id") or "")
        if ns in UPSTREAM_NAMESPACES:
            out["error"] = "upstream_not_mutable"
            out["reply"] = (
                f"I cannot apply {model_id} from the upstream picker here — change it inside "
                f"the provider UI. Claude arm was not touched."
            )
            close_incident_if_spark_safe(
                binding=pending,
                claude_env_before=claude_before,
                claude_env_after=str(os.environ.get("SIFTA_CLAUDE_ARM_MODEL", "")).strip(),
                state_dir=state_dir,
            )
            return out
        if ns == NAMESPACE_GROK:
            return _handle_grok_llm_pin(
                out,
                str(pending.get("index") or model_id),
                state_dir=state_dir,
                owner_text=owner_text,
                current_cortex=selected,
            )
        if ns == NAMESPACE_QWEN:
            return _handle_fireworks_llm_pin(
                out,
                str(pending.get("index") or model_id),
                state_dir=state_dir,
                owner_text=owner_text,
                current_cortex=selected,
            )
        if ns == NAMESPACE_CLAUDE:
            return _apply_claude_arm_pin(
                out,
                model_id,
                state_dir=state_dir,
                owner_text=owner_text,
                binding=pending,
            )
        out["error"] = "unknown_pending_namespace"
        out["reply"] = f"Pending binding namespace {ns!r} is not actionable."
        return out

    if parsed.kind == "clear":
        return _apply_claude_arm_pin(out, "", state_dir=state_dir, owner_text=owner_text)

    if parsed.kind == "model_id" and parsed.model_id:
        if parsed.model_id.lower().startswith("claude:"):
            parsed.model_id = parsed.model_id.split(":", 1)[1].strip()
        if parsed.model_id in _CLAUDE_ARM_KNOWN_MODELS:
            binding = {"namespace": NAMESPACE_CLAUDE, "model_id": parsed.model_id, "index": 0, "list_row": {}}
            if ingress_kind == "spoken":
                save_pending_binding(binding, state_dir=state_dir)
                out["pending_confirmation"] = True
                out["reply"] = mutation_echo(binding, format_model=str) + " Say confirm to apply."
                return out
            return _apply_claude_arm_pin(
                out,
                parsed.model_id,
                state_dir=state_dir,
                owner_text=owner_text,
                binding=binding,
            )
        out["error"] = "unknown_model_id"
        out["reply"] = (
            f"I do not recognize model-id {parsed.model_id!r} on a steerable pin list. "
            "Run /cortex llm to render numbered lists, or use /cortex pin claude <n>."
        )
        return out

    if parsed.kind not in ("bare_number", "namespaced"):
        out["error"] = "unsupported_mutation"
        out["reply"] = "Use /cortex llm, /cortex llm <n>, /cortex llm cline <n>, or /cortex pin claude <n>."
        return out

    binding, err = resolve_binding(
        parsed,
        state_dir=state_dir,
        claude_catalog=list(_CLAUDE_ARM_KNOWN_MODELS),
        grok_catalog=grok_models,
        fireworks_catalog=fireworks_models,
    )
    if err:
        return _refuse_stale_or_ambiguous_llm(
            out,
            state_dir=state_dir,
            owner_text=owner_text,
            current_cortex=selected,
            error_code=err,
            index=int(parsed.index or 0),
        )

    ns = str(binding.get("namespace") or "")
    model_id = str(binding.get("model_id") or "")
    write_binding_receipt(
        action="resolved_binding",
        payload={
            "owner_text_preview": owner_text[:120],
            "ingress_kind": ingress_kind,
            "selected_cortex": selected,
            "binding": binding,
        },
        state_dir=state_dir,
    )

    if ns == NAMESPACE_DIRECT:
        out["error"] = "direct_cortex_no_pin"
        out["reply"] = (
            f"This cortex already uses {model_id} as its only LLM — no sub-model pin. "
            "Switch brains with /cortex <n> on the main picker list."
        )
        return out

    if ns in UPSTREAM_NAMESPACES:
        out["error"] = "upstream_picker_refused"
        row = binding.get("list_row") or {}
        out["reply"] = (
            f"Resolved {binding.get('index') or '?'} → {model_id} on the {ns} list "
            f"(rendered {row.get('list_id', '?')[:8]}…). "
            "This picker lives upstream in its own CLI/app — I did not pin Claude and I did not mutate "
            "hidden state. Change the model inside that provider surface, then /cortex llm to probe."
        )
        close_incident_if_spark_safe(
            binding=binding,
            claude_env_before=claude_before,
            claude_env_after=str(os.environ.get("SIFTA_CLAUDE_ARM_MODEL", "")).strip(),
            state_dir=state_dir,
        )
        return out

    echo = mutation_echo(
        binding,
        format_model=(
            grok_fmt
            if ns == NAMESPACE_GROK
            else fireworks_fmt
            if ns == NAMESPACE_QWEN
            else str
        ),
    )
    if ingress_kind == "spoken":
        save_pending_binding(binding, state_dir=state_dir)
        out["pending_confirmation"] = True
        out["reply"] = echo + " Say confirm to apply."
        return out

    if ns == NAMESPACE_GROK:
        out = _handle_grok_llm_pin(
            out,
            str(binding.get("index") or model_id),
            state_dir=state_dir,
            owner_text=owner_text,
            current_cortex=selected,
        )
        out["reply"] = echo + "\n" + str(out.get("reply") or "")
        return out

    if ns == NAMESPACE_QWEN:
        out = _handle_fireworks_llm_pin(
            out,
            str(binding.get("index") or model_id),
            state_dir=state_dir,
            owner_text=owner_text,
            current_cortex=selected,
        )
        out["reply"] = echo + "\n" + str(out.get("reply") or "")
        return out

    if ns == NAMESPACE_CLAUDE:
        out = _apply_claude_arm_pin(
            out,
            model_id,
            state_dir=state_dir,
            owner_text=owner_text,
            binding=binding,
        )
        out["reply"] = echo + "\n" + str(out.get("reply") or "")
        return out

    out["error"] = "namespace_not_mutable"
    out["reply"] = f"Namespace {ns!r} is not steerable from this organ."
    return out


def _handle_cortex_llm(
    out: Dict[str, Any],
    arg: str,
    *,
    state_dir: Path,
    owner_text: str,
    current_cortex: str = "",
    ingress_kind: str = "typed",
) -> Dict[str, Any]:
    """George 2026-06-11: '/cortex llm' lists LLMs; bare N binds last-rendered list (r1018 P1)."""
    import os

    from System.swarm_cortex_llm_list_binding import (
        NAMESPACE_CLINE,
        NAMESPACE_CODEX,
        NAMESPACE_GROK,
        NAMESPACE_MIMO,
        NAMESPACE_CLAUDE,
        NAMESPACE_QWEN,
        NAMESPACE_DIRECT,
    )

    selected = str(current_cortex or "").strip()
    selected_low = selected.lower()
    cur = str(os.environ.get("SIFTA_CLAUDE_ARM_MODEL", "")).strip()
    arg = (arg or "").strip()
    if arg:
        return _handle_cortex_llm_mutation(
            out,
            arg,
            state_dir=state_dir,
            owner_text=owner_text,
            current_cortex=selected,
            ingress_kind=ingress_kind,
        )

    attached_model_matches_active, attached_models_for_cortex, format_attached_model = _cortex_llm_capabilities(
        state_dir
    )
    lines = [f"Selected Talk cortex: {selected or '(unknown)'}"]
    primary_recorded = False
    _ext_lane = ""
    for _lane in ("cline", "mimo"):
        if selected_low.startswith(_lane):
            _ext_lane = _lane
            break
    if _ext_lane:
        # r984: cline and mimo are the external-brain family — same probe
        # organ, same ledger, lane-parameterized.
        _lane_title = _ext_lane.capitalize() if _ext_lane == "cline" else "MiMo"
        try:
            from System.swarm_cline_settings_probe import (
                latest_brain_block,
                probe_external_brain,
            )

            row = probe_external_brain(_ext_lane, state_dir=Path(state_dir))
            block = latest_brain_block(_ext_lane, state_dir=Path(state_dir))
            lines.append(f"Underlying provider for my {_lane_title} cortex:")
            lines.append(f"  {block or f'{_ext_lane.upper()} EXTERNAL BRAIN: no ledger row'}")
            lines.append(f"  Probe receipt: {row.get('trace_id', '(none)')} status={row.get('status', '?')}")
        except Exception as exc:
            lines.append(f"Underlying provider for my {_lane_title} cortex: probe failed ({type(exc).__name__})")
        lines.append(
            f"{_lane_title} supports its own upstream provider/model picker — any mainstream "
            f"LLM provider API. Change it inside {_lane_title}, then run /cortex llm again; "
            "I will probe and receipt what I can see."
        )
        lines.append(
            f"Important: the Claude-arm pin below does not steer {_lane_title}. "
            "It only matters when the selected Talk cortex is claude:..."
        )
        if attached_models_for_cortex is not None and selected:
            try:
                rec = attached_models_for_cortex(selected, state_dir=Path(state_dir))
                models = rec.get("attached_models") or []
                if models:
                    lines.append("")
                    lines.append(
                        f"Attached LLMs for {_lane_title} (OAuth + upstream picker — "
                        f"Codex, Anthropic, Grok/Composer attachable in Cline):"
                    )
                    for i, mid in enumerate(models, start=1):
                        active = str(rec.get("default_attached") or "")
                        marker = (
                            "●"
                            if attached_model_matches_active
                            and attached_model_matches_active(str(mid), active)
                            else " "
                        )
                        lines.append(f"  {marker} {i:2d}. {format_attached_model(str(mid))}")
                    lines.append(
                        f"  Live default: {format_attached_model(str(rec.get('default_attached') or '')) or '(change in Cline UI)'}"
                    )
                    if not primary_recorded:
                        _record_primary_llm_list(
                            namespace=NAMESPACE_CLINE if _ext_lane == "cline" else NAMESPACE_MIMO,
                            items=[str(m) for m in models],
                            labels=[format_attached_model(str(m)) for m in models],
                            selected_cortex=selected,
                            owner_text=owner_text,
                            state_dir=state_dir,
                        )
                        primary_recorded = True
            except Exception:
                pass
    elif selected_low.startswith("grok"):
        _grok_pin = str(os.environ.get("SIFTA_GROK_CLI_MODEL", "")).strip()
        if attached_models_for_cortex is not None:
            try:
                rec = attached_models_for_cortex(selected, state_dir=Path(state_dir))
                models = rec.get("attached_models") or []
                if models:
                    lines.append("")
                    lines.append("Attached LLMs for Grok Talk cortex (xAI OAuth — Composer + Build):")
                    for i, mid in enumerate(models, start=1):
                        active = _grok_pin or str(rec.get("default_attached") or "")
                        marker = (
                            "●"
                            if attached_model_matches_active
                            and attached_model_matches_active(str(mid), active)
                            else " "
                        )
                        lines.append(f"  {marker} {i:2d}. {format_attached_model(str(mid))}")
                    lines.append(
                        f"  Live pin: {format_attached_model(str(_grok_pin or rec.get('default_attached') or 'grok-composer-2.5-fast'))} (CLI default if no explicit pin)"
                    )
                    if not primary_recorded:
                        _record_primary_llm_list(
                            namespace=NAMESPACE_GROK,
                            items=[str(m) for m in models],
                            labels=[format_attached_model(str(m)) for m in models],
                            selected_cortex=selected,
                            owner_text=owner_text,
                            state_dir=state_dir,
                        )
                        primary_recorded = True
            except Exception:
                pass
        lines.append("")
        lines.append("Switch Grok sub-model without reboot:")
        lines.append("  /grok fast   → grok-composer-2.5-fast (Composer)")
        lines.append("  /grok build  → grok-build")
        lines.append("  /grok default → clear pin, use CLI default")
        lines.append(
            "Claude arm is inactive while Grok is my Talk cortex — "
            "use /cortex 2 only when you want Anthropic as Talk brain."
        )
    elif selected_low.startswith("codex"):
        if attached_models_for_cortex is not None:
            try:
                rec = attached_models_for_cortex(selected, state_dir=Path(state_dir))
                models = rec.get("attached_models") or []
                if models:
                    lines.append("")
                    lines.append("Attached LLMs for Codex (OpenAI Codex CLI picker):")
                    for i, mid in enumerate(models, start=1):
                        marker = (
                            "●"
                            if attached_model_matches_active
                            and attached_model_matches_active(str(mid), str(rec.get("default_attached") or ""))
                            else " "
                        )
                        lines.append(f"  {marker} {i:2d}. {format_attached_model(str(mid))}")
                    if not primary_recorded:
                        _record_primary_llm_list(
                            namespace=NAMESPACE_CODEX,
                            items=[str(m) for m in models],
                            labels=[format_attached_model(str(m)) for m in models],
                            selected_cortex=selected,
                            owner_text=owner_text,
                            state_dir=state_dir,
                        )
                        primary_recorded = True
            except Exception:
                pass
    elif selected_low.startswith("qwen") and "fireworks" in selected_low:
        fireworks_models, fireworks_fmt, fireworks_active = _fireworks_attached_models_for_pin(
            state_dir, selected
        )
        if fireworks_models:
            lines.append("")
            lines.append("Attached LLMs for Fireworks (qwen cortex — pin with /cortex llm N):")
            for i, mid in enumerate(fireworks_models, start=1):
                marker = "●" if str(mid) == str(fireworks_active) else " "
                lines.append(f"  {marker} {i:2d}. {fireworks_fmt(str(mid))}")
            lines.append(
                f"  Live pin: {fireworks_fmt(fireworks_active) or '(cortex tag default)'}"
            )
            if not primary_recorded:
                _record_primary_llm_list(
                    namespace=NAMESPACE_QWEN,
                    items=[str(m) for m in fireworks_models],
                    labels=[fireworks_fmt(str(m)) for m in fireworks_models],
                    selected_cortex=selected,
                    owner_text=owner_text,
                    state_dir=state_dir,
                )
                primary_recorded = True
        lines.append("")
        lines.append("Switch Fireworks sub-model without reboot:")
        lines.append("  /cortex llm 1  → Kimi K2.7 Code (when list shows it at 1)")
        lines.append("  /cortex llm qwen 1  → namespaced bind")
        lines.append("  /cortex llm default → clear pin, use cortex tag model")
    elif _is_direct_weight_cortex(selected) or selected_low.startswith("antigravity:"):
        direct_lines = _cortex_llm_direct_brain_block(selected)
        if direct_lines:
            lines.extend(direct_lines)
            if not primary_recorded:
                _record_primary_llm_list(
                    namespace=NAMESPACE_DIRECT,
                    items=[selected],
                    labels=[selected],
                    selected_cortex=selected,
                    owner_text=owner_text,
                    state_dir=state_dir,
                )
                primary_recorded = True
    elif selected_low.startswith("claude"):
        lines.append("The selected Talk cortex is my Claude arm; the pin below steers this path.")
        if attached_models_for_cortex is not None and selected:
            try:
                rec = attached_models_for_cortex(selected, state_dir=Path(state_dir))
                models = rec.get("attached_models") or []
                if models:
                    lines.append("")
                    lines.append("Attached LLMs for Claude arm (Anthropic):")
                    for i, mid in enumerate(models, start=1):
                        active = cur or str(rec.get("default_attached") or "")
                        marker = (
                            "●"
                            if attached_model_matches_active
                            and attached_model_matches_active(str(mid), active)
                            else " "
                        )
                        lines.append(f"  {marker} {i:2d}. {format_attached_model(str(mid))}")
            except Exception:
                pass
    elif selected:
        lines.append(
            "This selected provider picks its underlying model upstream or through its own command."
        )
    # r989/r1065: Claude-arm pin is noise on Grok/Cline/Codex and on direct-weight
    # cortexes (diffusion, mlx-vlm, local Ollama) where the tag already IS the model.
    _show_claude_arm_pin = (
        selected_low.startswith("claude")
        or (
            not selected_low.startswith(
                ("grok", "codex", "cline", "mimo", "qwen", "antigravity", "diffusion", "usd", "mlx")
            )
            and not _is_direct_weight_cortex(selected)
        )
    )
    if _show_claude_arm_pin:
        lines.append("")
        lines.append("Underlying LLMs for my Claude arm (pin = r943, live env, no reboot):")
        for i, m in enumerate(_CLAUDE_ARM_KNOWN_MODELS, start=1):
            marker = "●" if m == cur else " "
            lines.append(f"  {marker} {i:2d}. {m}")
        lines.append(f"  Current pin: {cur or '(launcher/CLI default)'}")
        lines.append(
            "Pin with /cortex pin claude <n> or /cortex llm claude <n>. "
            "/cortex llm default clears the launcher pin."
        )
        if not primary_recorded:
            _record_primary_llm_list(
                namespace=NAMESPACE_CLAUDE,
                items=list(_CLAUDE_ARM_KNOWN_MODELS),
                labels=list(_CLAUDE_ARM_KNOWN_MODELS),
                selected_cortex=selected,
                owner_text=owner_text,
                state_dir=state_dir,
            )
            primary_recorded = True
        if selected_low.startswith("claude"):
            lines.append(
                "Plain truth (r948): this pin steers my Claude Talk cortex dispatches."
            )
        else:
            lines.append(
                "Plain truth (r948): Claude-arm pin applies only when /cortex 2 is selected."
            )
    lines.append("")
    lines.append(
        "Ledger-strict: bare /cortex llm N binds the list rendered above in this session. "
        "Namespaced: /cortex llm cline N, /cortex pin claude N. "
        "Refusal with a question outranks confident wrong execution."
    )
    out["reply"] = "\n".join(lines)
    return out


def handle_slash_command(
    text: str,
    *,
    state_dir: Path | str,
    current_cortex: str = "",
    available: Optional[List[str]] = None,
    set_cortex_fn: Optional[Callable[[str], Any]] = None,
    ingress_kind: str = "typed",
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

    if cmd == "/grok":
        return _handle_grok_command(
            out,
            arg,
            state_dir=Path(state_dir),
            owner_text=clean,
        )

    if cmd == "/heart":
        try:
            from System.swarm_hardware_heart import format_heart_reply, pulse_hardware_heart

            row = pulse_hardware_heart(state_dir=Path(state_dir))
            out["reply"] = format_heart_reply(row)
            return out
        except Exception as exc:
            out["error"] = f"heart_failed: {type(exc).__name__}"
            out["reply"] = f"Heart pulse failed honestly ({type(exc).__name__}: {exc})."
            return out

    if cmd == "/speech":
        try:
            from System.swarm_speech_lane_selector import format_speech_reply, set_speech_budget_s

            if arg.lower().startswith("budget"):
                parts = arg.split(None, 1)
                sec_txt = parts[1].strip() if len(parts) > 1 else ""
                if not sec_txt or not sec_txt.replace(".", "", 1).isdigit():
                    out["reply"] = "Usage: /speech budget <seconds>"
                    return out
                budget = set_speech_budget_s(float(sec_txt), state_dir=Path(state_dir))
                out["reply"] = f"Speech budget set to {budget:.1f}s.\n\n" + format_speech_reply(state_dir=Path(state_dir))
                return out
            out["reply"] = format_speech_reply(state_dir=Path(state_dir))
            return out
        except Exception as exc:
            out["error"] = f"speech_failed: {type(exc).__name__}"
            out["reply"] = f"Speech lane read failed ({type(exc).__name__}: {exc})."
            return out

    if cmd == "/field":
        try:
            from System.swarm_canonical_organ_registry import format_organ_field_reply

            out["reply"] = format_organ_field_reply(state_dir=Path(state_dir))
            return out
        except Exception as exc:
            out["error"] = f"field_failed: {type(exc).__name__}"
            out["reply"] = f"Organ field read failed ({type(exc).__name__}: {exc})."
            return out

    if cmd in ("/ask-fable", "/askfable"):
        try:
            from System.swarm_questions_for_fable import ask_fable, format_ask_fable_reply

            if arg.strip():
                row = ask_fable(
                    question=arg.strip(),
                    asker="slash_command",
                    round_id="r1015",
                    blocking=False,
                    state_dir=Path(state_dir),
                )
                out["reply"] = (
                    f"Question logged for Fable: {row.get('q_id', '?')}\n\n"
                    + format_ask_fable_reply(state_dir=Path(state_dir))
                )
                return out
            out["reply"] = format_ask_fable_reply(state_dir=Path(state_dir))
            return out
        except Exception as exc:
            out["error"] = f"ask_fable_failed: {type(exc).__name__}"
            out["reply"] = f"Ask-Fable lane failed ({type(exc).__name__}: {exc})."
            return out

    if cmd == "/improve":
        try:
            from System.swarm_self_improvement_loop import format_improve_reply

            out["reply"] = format_improve_reply(state_dir=Path(state_dir))
            return out
        except Exception as exc:
            out["error"] = f"improve_failed: {type(exc).__name__}"
            out["reply"] = f"Self-improvement read failed ({type(exc).__name__}: {exc})."
            return out

    if cmd == "/quorum":
        try:
            from System.swarm_self_improvement_loop import format_quorum_reply

            if not arg.strip():
                out["reply"] = "Usage: /quorum <proposal_id_prefix>"
                return out
            out["reply"] = format_quorum_reply(arg.strip(), state_dir=Path(state_dir))
            return out
        except Exception as exc:
            out["error"] = f"quorum_failed: {type(exc).__name__}"
            out["reply"] = f"Quorum read failed ({type(exc).__name__}: {exc})."
            return out

    if cmd == "/cortex":
        # r985: "/cortex history" — the deterministic answer to "which model
        # thought last round?". George asked Alice that at 13:53; she answered
        # from chat narrative while her own ledger said alice-m5-cortex-8b.
        # Rows decide (§6); this subcommand prints them.
        _llm_parts = arg.split(None, 1)
        if _llm_parts and _llm_parts[0].lower() in ("history", "hist", "truth", "who"):
            n = 8
            if len(_llm_parts) > 1 and _llm_parts[1].strip().isdigit():
                n = max(1, min(40, int(_llm_parts[1].strip())))
            turns = last_thinking_models(Path(state_dir), n=n)
            if not turns:
                out["reply"] = ("I found no receipted thinking turns in my conversation "
                                "ledger — that absence is the honest answer, not a guess.")
                return out
            lines = [f"Which brain actually thought — last {len(turns)} receipted turns "
                     "(alice_conversation.jsonl, newest last):"]
            for t in turns:
                lines.append(f"  {t['when']}  {t['model']}  — \"{t['text_head']}\"")
            # r988: surface CORTEX_SELECTION_MISMATCH — turns where the model
            # that thought differs from the cortex George selected at the time.
            mismatches = cortex_selection_mismatches(Path(state_dir), n=5)
            if mismatches:
                lines.append("")
                lines.append("CORTEX_SELECTION_MISMATCH — I selected one cortex but a different "
                             "brain thought these turns (the switch did not bind, or a fallback ran):")
                for m in mismatches:
                    lines.append(f"  {m['when']}  selected={m['selected']} but {m['actual_model']} thought "
                                 f"— \"{m['text_head']}\"")
                lines.append("This is a body bug worth a receipt, not a story — the switch effector "
                             "or a silent fallback needs the fix.")
            lines.append("Ledger rows decide (§6). My narrative memory of switches is "
                         "not evidence; these rows are.")
            out["reply"] = "\n".join(lines)
            return out
        if _llm_parts and _llm_parts[0].lower() == "pin":
            return _handle_cortex_pin(
                out,
                _llm_parts[1] if len(_llm_parts) > 1 else "",
                state_dir=Path(state_dir),
                owner_text=clean,
                current_cortex=current_cortex,
                ingress_kind=ingress_kind,
            )
        if _llm_parts and _llm_parts[0].lower() in ("llm", "llms", "model", "models"):
            return _handle_cortex_llm(
                out,
                _llm_parts[1] if len(_llm_parts) > 1 else "",
                state_dir=Path(state_dir),
                owner_text=clean,
                current_cortex=current_cortex,
                ingress_kind=ingress_kind,
            )
        tags = list(available) if available is not None else available_cortex_tags()
        if not tags:
            out["error"] = "no_cortexes_found"
            out["reply"] = ("I could not read any available cortex from the live "
                            "registries — that is a body problem worth a receipt, "
                            "not a menu problem.")
            return out

        if not arg:
            # r984 (George: "my brain is spinning"): every entry names the
            # brain that ACTUALLY thinks, not just the arm label — cline shows
            # its probed upstream, qwen:accounts/fireworks/... says Kimi on
            # the Fireworks API. Local weights show no second name: the tag
            # is already the model.
            try:
                from System.swarm_cline_settings_probe import cortex_brain_label
            except Exception:
                cortex_brain_label = None  # type: ignore[assignment]
            lines = ["My available cortexes (live registry, not memory):"]
            for i, tag in enumerate(tags, start=1):
                marker = "●" if tag == current_cortex else " "
                brain = ""
                if cortex_brain_label is not None:
                    try:
                        lbl = cortex_brain_label(tag, state_dir=Path(state_dir))
                        if lbl:
                            brain = f"   ← {lbl}"
                    except Exception:
                        brain = ""
                lines.append(f"  {marker} {i:2d}. {tag}{brain}")
            lines.append("Switch with /cortex <number or name>. /cortex llm shows the selected brain in depth.")
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
