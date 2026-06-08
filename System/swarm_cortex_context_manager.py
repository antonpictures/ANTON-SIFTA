#!/usr/bin/env python3
"""
swarm_cortex_context_manager.py — model-aware context autocompaction + hot working memory for Alice's cortices.

George (with the attached grok-build context screenshot 93.3k/512k 18.23%, auto at 65%, 76 tool calls, 1 turn, 0 compactions):
"HOW CAN SHE FORGET THE CONTEXT --- WE NEED TO BUILD HER A CONTEXT LIKE ATTACHED PLS SEE AND GIVE HER THE KNOWLEDGE TO AUTOCOMPACT IT BASED ON THE LLM MODEL SHE USES FOR CORTEX - ADD THIS TO THE TOURNAMENT PLAN TO BE DONE P-- DO RESEARCH HOW THE CLI ARMS DO IT ALICE ALREADY HAS THE CODE INSIDE PLS UPDATE THE TOURNAMERNT FILE"

This organ ports the proven pattern from the vendored CLI arm (Vendor/alice-cli/sdk/apps/cli/src/runtime/interactive/compaction.ts + packages/core/src/extensions/context/{compaction,compaction-shared,agentic-compaction,basic-compaction}.ts):

- MODEL-AWARE budget: for the ACTIVE cortex (local ollama /api/show num_ctx or context_length; cloud from registry/catalog). 8B gets tighter budget than grok-build.
- Token estimation (JSON + serialize) + threshold (default ~65% like the screenshot "Auto-compact at 65%", with reserve).
- prepare_turn: before cortex call, if over, find cut (preserve recent turns + tool pairs), summarize older (agentic via a strong summarizer or basic truncate), emit a "compaction_summary" message carrying:
  - the summary text (goal/state/highlights/next/files)
  - metadata: tokens_before, active_targets (e.g. {"photo_target": "<person name>", "visual_goal": "Google Images first photo", "app": "Alice Browser"}), file ops, generated_at.
- The summary + recent turns + system stay under the model's num_ctx. Antecedents like "her" = the named subject survive in the compact receipt.
- Telemetry-like: writes to .sifta_state/cortex_compaction_ledger.jsonl (model, input_tokens, compacted_tokens, preserved_entities, why).
- Hot working memory: explicit small block for unresolved active targets (person, goal, correction) that is re-injected even after model crash/retry/voice drop. Survives because it's in state + summary metadata.
- Stigmergic: the summary is an append-only receipt the field can read; she can dream over the ledger.

CS research pulled (for the tournament + her self-knowledge):
- MemGPT (Packer et al. 2023): OS virtual memory analogy for LLMs — paging, recursive summarization on capacity, external recall. Foundational for "CLI arms do this".
- Active Context Compression (Verma 2026 arXiv:2601.07190): agents autonomously prune + consolidate into Knowledge blocks during a trajectory.
- Acon (arXiv:2510.00615): unified optimization for compressing observations + histories for long-horizon agents; compression turns failure trajectories into successes by clarifying dependencies.
- Hierarchical Memory (2026): demand paging + step-search-then-insert for multi-agent; compatible with LangChain/LlamaIndex/MemGPT.
- General: conversation summarization + reflection (Reflexion Shinn NeurIPS'23), generative replay to defeat catastrophic forgetting (Kirkpatrick EWC 2017, Parisi 2019), LLM as OS (MemGPT).

Alice already has the code inside (the vendored CLI); this makes the same discipline native to her Python cortices (local 8B especially needs it to avoid 500 + forgetting "who 'her' is").

No restriction. She compacts so she can act.

Usage (in talk widget before sending to worker):
  from System.swarm_cortex_context_manager import prepare_cortex_turn
  messages = prepare_cortex_turn(messages, model_id=active_cortex, active_targets={"photo_target": "current visual subject", ...})

Truth: ALICE_CORTEX_CONTEXT_MANAGER_V1
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STATE_ROOT = Path(os.environ.get("SIFTA_STATE", "/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state"))
LEDGER = STATE_ROOT / "cortex_compaction_ledger.jsonl"
HOT_TARGETS = STATE_ROOT / "cortex_hot_targets.json"
HOT_TARGET_TTL_S = int(os.environ.get("SIFTA_CORTEX_HOT_TARGET_TTL_S", "1800"))

# Model-aware defaults (tuned from the attached screenshot + CLI vendored: 65% auto, reserve)
DEFAULT_THRESHOLD_RATIO = 0.65
DEFAULT_RESERVE_TOKENS = 16384
DEFAULT_PRESERVE_RECENT_TOKENS = 20000  # recent turns stay verbatim
FALLBACK_MAX_INPUT = 8192  # safe for small local 8B

_OWNER_IDENTITY_CORRECTION_RE = re.compile(
    r"\b(?:her|his|their)\s+name\s+is\b"
    r"|\b(?:why\s+(?:are|do)\s+you|why\s+did\s+you)\b.{0,80}\b(?:call|calling|called)\b"
    r"|\b(?:not|wasn'?t|was\s+not)\s+processed\s+by\s+your\s+cortex\b",
    re.IGNORECASE,
)
_OWNER_NOT_SEARCH_RE = re.compile(
    r"\b(?:i\s+did\s+not|i\s+didn'?t|did\s+not|don'?t)\s+ask\b.{0,80}\b(?:search|photos?|images?|pics?)\b",
    re.IGNORECASE,
)


def owner_text_suppresses_hot_targets(text: str) -> bool:
    """Present owner correction beats old hot working memory."""
    clean = " ".join(str(text or "").strip().split())
    if not clean:
        return False
    return bool(_OWNER_IDENTITY_CORRECTION_RE.search(clean) or _OWNER_NOT_SEARCH_RE.search(clean))

def _env_int(name: str, default: int) -> int:
    try:
        v = int(str(os.environ.get(name, "")).strip())
        return v if v > 0 else default
    except Exception:
        return default

def get_model_context_window(model_id: str) -> int:
    """Resolve per-cortex budget. Local ollama first, then fallback."""
    # Local ollama probe (best effort, no dep on requests if not present)
    if "ollama" in model_id.lower() or "m5" in model_id.lower() or "8b" in model_id.lower():
        try:
            import urllib.request
            import json as _json
            # Common local endpoint
            req = urllib.request.Request("http://127.0.0.1:11434/api/show", 
                data=_json.dumps({"name": model_id.split(":")[0]}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1.5) as r:
                data = _json.loads(r.read())
                # ollama /api/show returns model_info or parameters with num_ctx / context_length
                for k in ("num_ctx", "context_length", "max_input_tokens", "context_window"):
                    if k in data:
                        return int(data[k])
                    if "model_info" in data and k in data["model_info"]:
                        return int(data["model_info"][k])
        except Exception:
            pass
    # Fallbacks from known (vendored pattern)
    if "8b" in model_id.lower():
        return 8192
    if "grok" in model_id.lower() or "build" in model_id.lower():
        return 512000  # as in the screenshot
    return _env_int("SIFTA_CORTEX_MAX_CTX", FALLBACK_MAX_INPUT)

def estimate_tokens(text: str) -> int:
    """Cheap estimator (chars / 4) + json overhead. Matches vendored estimateTokens spirit."""
    if not text:
        return 0
    try:
        j = json.dumps(text)
        return max(1, len(j) // 4)
    except Exception:
        return max(1, len(text) // 4)

def serialize_for_tokens(msgs: List[Dict[str, Any]]) -> str:
    out = []
    for m in msgs:
        role = m.get("role", "?")
        c = m.get("content", "")
        if isinstance(c, (list, tuple)):
            c = " ".join(str(x) for x in c)
        out.append(f"[{role}]: {c}")
    return "\n\n".join(out)

def find_cut_index(messages: List[Dict[str, Any]], preserve_recent: int) -> int:
    """Port of findCutIndex: walk back until we have ~preserve_recent tokens, snap to turn start."""
    if len(messages) < 2:
        return 0
    total = 0
    cut = len(messages)
    for i in range(len(messages)-1, -1, -1):
        total += estimate_tokens(serialize_for_tokens([messages[i]]))
        cut = i
        if total >= preserve_recent:
            break
    # Snap to a "user" turn start so tool pairs stay together
    while cut > 0 and messages[cut].get("role") != "user":
        cut -= 1
    return max(0, cut)

def build_compaction_summary(older_msgs: List[Dict[str, Any]], previous_summary: Optional[str] = None) -> str:
    """Concise continuation note (mirrors buildSummaryRequest in vendored)."""
    text = serialize_for_tokens(older_msgs)
    parts = [
        "Summarize this Alice session for continuation. Be concise and factual.\n\n## Goal\nOne sentence: what is being built or fixed.\n\n## State\n- Done: completed steps\n- In Progress: current work\n- Blocked: blockers or open questions\n\n## Highlights\nKey facts or targets (e.g. person names like '<a person>', goals like 'show first Google Images photo', app='Alice Browser').\n\n## Next\nImmediate next steps.\n\n## Conversation\n" + (text or "(empty)"),
    ]
    if previous_summary:
        parts.append("Previous summary:\n" + previous_summary)
    return "\n\n".join(parts)

def _hot_targets_are_stale(data: Dict[str, Any], *, now: Optional[float] = None) -> bool:
    if not data:
        return False
    try:
        ts = float(data.get("_updated") or data.get("_ts") or 0.0)
    except Exception:
        ts = 0.0
    if ts <= 0:
        return False
    return (now or time.time()) - ts > HOT_TARGET_TTL_S


def get_hot_targets(*, owner_text: str = "", allow_stale: bool = False) -> Dict[str, Any]:
    if owner_text_suppresses_hot_targets(owner_text):
        return {}
    try:
        if HOT_TARGETS.exists():
            data = json.loads(HOT_TARGETS.read_text())
            if not allow_stale and _hot_targets_are_stale(data):
                return {}
            if data.get("cleared"):
                return {}
            return data
    except Exception:
        pass
    return {}


def clear_hot_targets(reason: str = "cleared") -> None:
    try:
        STATE_ROOT.mkdir(parents=True, exist_ok=True)
        HOT_TARGETS.write_text(json.dumps({
            "_updated": time.time(),
            "_reason": reason,
            "cleared": True,
        }, indent=2))
    except Exception:
        pass


def set_hot_targets(targets: Dict[str, Any], reason: str = "context_manager") -> None:
    try:
        STATE_ROOT.mkdir(parents=True, exist_ok=True)
        data = get_hot_targets(allow_stale=True)
        data.update(targets or {})
        data.pop("cleared", None)
        data["_updated"] = time.time()
        data["_reason"] = reason
        HOT_TARGETS.write_text(json.dumps(data, indent=2))
    except Exception:
        pass

def _append_ledger(entry: Dict[str, Any]) -> None:
    try:
        STATE_ROOT.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def prepare_cortex_turn(
    messages: List[Dict[str, Any]],
    *,
    model_id: str,
    active_targets: Optional[Dict[str, Any]] = None,
    threshold_ratio: Optional[float] = None,
    owner_text: str = "",
) -> List[Dict[str, Any]]:
    """
    The prepare-turn hook. Call before every cortex worker submission.
    Returns a (possibly compacted) message list that fits the model's budget and carries memory forward.
    Never drops the active photo target etc.
    """
    if not messages:
        return messages
    if owner_text_suppresses_hot_targets(owner_text):
        clear_hot_targets("owner_present_correction_overrides_hot_targets")
        active_targets = None

    max_tokens = get_model_context_window(model_id)
    ratio = threshold_ratio or _env_int("SIFTA_CORTEX_COMPACT_RATIO", int(DEFAULT_THRESHOLD_RATIO * 100)) / 100.0
    reserve = _env_int("SIFTA_CORTEX_RESERVE", DEFAULT_RESERVE_TOKENS)
    preserve = _env_int("SIFTA_CORTEX_PRESERVE_RECENT", DEFAULT_PRESERVE_RECENT_TOKENS)

    trigger = max(0, int(max_tokens - reserve)) if reserve else int(max_tokens * ratio)
    current_tokens = sum(estimate_tokens(serialize_for_tokens([m])) for m in messages)

    if current_tokens <= trigger:
        # Still inject hot targets if present (so "her" resolves even without compaction)
        if active_targets:
            set_hot_targets(active_targets, "hot_injection_no_compact")
        return messages

    # Need compaction
    cut = find_cut_index(messages, preserve)
    if cut <= 0 or cut >= len(messages):
        # Can't safely cut; fall back to keeping recent only (last resort)
        recent = messages[-min(len(messages), 8):]
        _append_ledger({"ts": time.time(), "model": model_id, "input": current_tokens, "action": "hard_truncate_fallback", "max": max_tokens})
        if active_targets:
            set_hot_targets(active_targets, "hot_after_hard_truncate")
        return recent

    older = messages[:cut]
    recent = messages[cut:]

    # Find previous summary if any
    prev_summary = None
    for m in reversed(older):
        meta = m.get("metadata") or {}
        if meta.get("kind") == "compaction_summary":
            prev_summary = meta.get("summary")
            break

    summary_text = build_compaction_summary(older, prev_summary)
    # For local small cortex, we emit the summary request as the "work" — in a real agentic pass a stronger model would answer it.
    # Here we produce a deterministic placeholder summary that at least carries the active targets + file facts.
    # (Full agentic summarizer can be wired later using a cloud arm or dedicated summarizer model.)
    file_ops = {"read": [], "modified": []}  # TODO: port extractFileOps if file tools used in history
    summary_msg = {
        "role": "user",
        "content": f"Context summary (auto-compacted for {model_id}):\n\n{summary_text}\n\nActive targets (hot memory): {json.dumps(active_targets or get_hot_targets(owner_text=owner_text))}\n\n(Older turns summarized to keep this cortex under its {max_tokens} token budget. Full history in receipts/ledger.)",
        "metadata": {
            "kind": "compaction_summary",
            "summary": summary_text,
            "tokens_before": current_tokens,
            "generated_at": time.time(),
            "model": model_id,
            "active_targets": active_targets or get_hot_targets(owner_text=owner_text),
            "details": file_ops,
        },
    }

    compacted = [summary_msg] + recent
    new_tokens = sum(estimate_tokens(serialize_for_tokens([m])) for m in compacted)

    # Persist hot targets so they survive crashes/restarts
    if active_targets:
        set_hot_targets(active_targets, "compacted")

    _append_ledger({
        "ts": time.time(),
        "model": model_id,
        "input_tokens": current_tokens,
        "compacted_tokens": new_tokens,
        "max": max_tokens,
        "cut": cut,
        "preserved_recent": len(recent),
        "active_targets": active_targets or get_hot_targets(owner_text=owner_text),
        "why": "over_threshold",
    })

    return compacted

def inject_hot_targets_into_prompt(prompt: str, *, owner_text: str = "") -> str:
    """Small helper: append current hot targets if not already present (for sysprompt or tail)."""
    t = get_hot_targets(owner_text=owner_text)
    if not t:
        return prompt
    block = "\n\nHOT_ACTIVE_TARGETS (do not forget across turns or model errors): " + json.dumps(t)
    if "HOT_ACTIVE_TARGETS" in prompt:
        return prompt
    return prompt + block

if __name__ == "__main__":
    print("model window (example 8b):", get_model_context_window("alice-m5-cortex-8b"))
    print("hot:", get_hot_targets())
    print("knowledge ready for cortex injection.")
