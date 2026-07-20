#!/usr/bin/env python3
"""Search provider reality — owner phrase vs body execution provider.

George (2026-06-19 r1325): "SEARCH ON GOOGLE" may be generic web-search shorthand
while Alice Browser actually opens DuckDuckGo. Receipts and replies must name the
execution provider, not the owner's brand verb.

Truth label: SEARCH_PROVIDER_REALITY_V1
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

TRUTH_LABEL = "SEARCH_PROVIDER_REALITY_V1"
SCHEMA = "SEARCH_PROVIDER_REALITY_ROW_V1"
_LEDGER = "search_provider_reality.jsonl"

_HOST_TO_PROVIDER: dict[str, str] = {
    "google.com": "google",
    "www.google.com": "google",
    "duckduckgo.com": "duckduckgo",
    "www.duckduckgo.com": "duckduckgo",
    "html.duckduckgo.com": "duckduckgo",
    "bing.com": "bing",
    "www.bing.com": "bing",
    "search.brave.com": "brave",
    "search.yahoo.com": "yahoo",
    "perplexity.ai": "perplexity",
    "www.perplexity.ai": "perplexity",
    "duck.ai": "duckai",
    "www.duck.ai": "duckai",
}

_PROVIDER_DISPLAY: dict[str, str] = {
    "google": "Google",
    "duckduckgo": "DuckDuckGo",
    "bing": "Bing",
    "brave": "Brave Search",
    "yahoo": "Yahoo",
    "perplexity": "Perplexity",
    "duckai": "Duck.ai",
    "unknown": "the configured search provider",
}

_OWNER_BRAND_RE = re.compile(
    r"\b(google(?:\.com)?|duck\.ai|duck\s+ai|duck\s*duck\s*go|ddg|bing|brave|yahoo|perplexity(?:\s+ai|\.ai)?)\b",
    re.IGNORECASE,
)

_EXPLICIT_ENGINE_PLS_RE = re.compile(
    r"\bSEARCH\s+ON\s+"
    r"(?P<engine>google(?:\.com)?|perplexity(?:\s+ai|\.ai)?|duck\.ai|duck\s+ai|duck\s*duck\s*go|ddg|bing|brave|yahoo)\s+"
    r"PLS\b\s*(?P<query>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_EXPLICIT_ENGINE_FOR_ON_RE = re.compile(
    r"\b(?:SEARCH|LOOK\s+UP|FIND)\s+(?:FOR\s+)?"
    r"(?P<query>.+?)\s+ON\s+"
    r"(?P<engine>google(?:\.com)?|perplexity(?:\s+ai|\.ai)?|duck\.ai|duck\s+ai|duck\s*duck\s*go|ddg|bing|brave|yahoo)\b"
    r"(?:\s+(?:PLS|PLEASE))?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ANAPHORIC_RECIPE_RE = re.compile(
    r"\b(?:this|that)\s+(?:recipe|recepi|recepie|dish|meal|food)\b",
    re.IGNORECASE,
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    repo = Path(__file__).resolve().parents[1]
    default = repo / ".sifta_state"
    if state_dir is None:
        return default
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def provider_key_from_url(url: str) -> str:
    try:
        host = urlparse((url or "").strip()).netloc.lower()
    except Exception:
        host = ""
    if host in _HOST_TO_PROVIDER:
        return _HOST_TO_PROVIDER[host]
    for known_host, key in _HOST_TO_PROVIDER.items():
        if host == known_host or host.endswith("." + known_host.lstrip("www.")):
            return key
    try:
        from System.swarm_search_engine_registry import resolve_engine

        res = resolve_engine(host)
        if res.get("ok"):
            return str(res.get("key") or "unknown")
    except Exception:
        pass
    return "unknown"


def display_provider(key: str) -> str:
    return _PROVIDER_DISPLAY.get(str(key or "").strip().lower(), str(key or "unknown"))


def _normalize_engine_token(token: str) -> str:
    raw = re.sub(r"\s+", " ", str(token or "").strip().lower())
    if raw in {"duck duck go", "ddg", "duckduckgo"}:
        return "duckduckgo"
    if raw in {"perplexity ai", "perplexity", "perplexity.ai"}:
        return "perplexity"
    if raw in {"duck.ai", "duck ai", "duckai"}:
        return "duckai"
    try:
        from System.swarm_search_engine_registry import resolve_engine

        res = resolve_engine(raw)
        if res.get("ok"):
            return str(res.get("key") or raw)
    except Exception:
        pass
    return raw


def _strip_outer_search_quotes(query: str) -> str:
    q = str(query or "").strip()
    if len(q) >= 2 and q[0] == q[-1] and q[0] in "\"'":
        q = q[1:-1]
    return " ".join(q.strip(" \t\r\n").split())


def _jsonl(path: Path) -> list[dict[str, Any]]:
    """Tolerant JSONL reader: missing file or bad lines never raise.

    r1366 fix: this helper was referenced but never defined, so
    `_recent_conversation_history()` raised a silent NameError on every call
    site that didn't pass `history=` explicitly. `_resolve_query_anaphora`'s
    try/except swallowed it, so 'this recipe' / 'that dish' anaphora never
    resolved on those call sites — confirmed live via George's
    'SEARCH FOR THIS RECIPE ON PERPLEXITY.AI' polenta-session transcript.
    """
    try:
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    out.append(row)
        return out
    except Exception:
        return []


def _recent_conversation_history(limit: int = 80) -> list[dict[str, Any]]:
    path = _state_dir() / "alice_conversation.jsonl"
    rows = _jsonl(path)
    out: list[dict[str, Any]] = []
    for row in rows[-limit:]:
        # r1366 fix: live alice_conversation.jsonl rows nest the turn under
        # "payload" (row["payload"]["role"/"text"]); this previously read the
        # top level only, so it always returned [] even after _jsonl existed.
        body = row.get("payload") if isinstance(row.get("payload"), dict) else row
        role = str(body.get("role") or body.get("speaker") or "").lower()
        content = body.get("content") or body.get("text") or body.get("message") or ""
        if role and content:
            out.append({"role": role, "content": str(content)})
    return out


def _resolve_query_anaphora(query: str, *, history: Optional[list[dict[str, Any]]] = None) -> str:
    q = str(query or "").strip()
    if not _ANAPHORIC_RECIPE_RE.search(q):
        return q
    try:
        from System.swarm_web_ai_chat_bridge import resolve_anaphoric_ai_query

        resolved = resolve_anaphoric_ai_query(q, history=history or _recent_conversation_history())
        return " ".join(str(resolved or q).strip().split())
    except Exception:
        return q


def parse_explicit_engine_pls_search(
    owner_text: str,
    *,
    history: Optional[list[dict[str, Any]]] = None,
) -> Optional[dict[str, str]]:
    """Parse named-engine search phrasing into engine key + query.

    Supported owner forms:
    - `SEARCH ON PERPLEXITY PLS test query`
    - `SEARCH FOR this recipe ON PERPLEXITY.AI`
    """
    raw = str(owner_text or "").strip()
    if not raw:
        return None
    m = _EXPLICIT_ENGINE_PLS_RE.search(raw)
    if not m:
        m = _EXPLICIT_ENGINE_FOR_ON_RE.search(raw)
    if not m:
        return None
    engine = _normalize_engine_token(m.group("engine"))
    query = _strip_outer_search_quotes(m.group("query"))
    query = re.sub(r"\s+PLS\s*$", "", query, flags=re.IGNORECASE).strip()
    query = _resolve_query_anaphora(query, history=history)
    if not query or len(query) < 2:
        return None
    return {"engine": engine, "query": query, "owner_phrase_engine": str(m.group("engine") or "").strip()}


def build_explicit_engine_search_url(engine: str, query: str) -> str:
    """Build search URL honoring named engine; falls back to registry default."""
    from urllib.parse import quote_plus

    key = _normalize_engine_token(engine)
    q = str(query or "").strip()
    try:
        from System.swarm_search_engine_registry import search_url as reg_search_url

        url = reg_search_url(q, engine=key)
        if url:
            return url
    except Exception:
        pass
    return f"https://www.google.com/search?q={quote_plus(q)}"


def detect_owner_search_brand(owner_text: str) -> Optional[str]:
    """Brand or verb the owner named ('google' as shorthand counts)."""
    m = _OWNER_BRAND_RE.search(owner_text or "")
    if not m:
        return None
    token = re.sub(r"\s+", " ", m.group(1).lower()).strip()
    return _normalize_engine_token(token)


def build_provider_reality_row(
    *,
    owner_text: str,
    query: str,
    execution_url: str,
    interpreted_intent: str = "web_search",
) -> dict[str, Any]:
    requested = detect_owner_search_brand(owner_text)
    execution_provider = provider_key_from_url(execution_url)
    mismatch = bool(requested and execution_provider != "unknown" and requested != execution_provider)
    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "owner_phrase": str(owner_text or "")[:400],
        "interpreted_intent": interpreted_intent,
        "requested_brand_or_verb": requested or "",
        "execution_provider": execution_provider,
        "execution_url": execution_url,
        "query": str(query or "").strip(),
        "provider_mismatch": mismatch,
        "reply_rule": (
            f"Say I searched the web using {display_provider(execution_provider)} for {query!r}, "
            f"not {display_provider(requested)}."
            if mismatch and requested
            else f"Say I searched using {display_provider(execution_provider)} for {query!r}."
        ),
    }
    return row


def append_provider_reality_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    path = _state_dir(state_dir) / _LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def honest_search_reply(
    *,
    owner_text: str,
    query: str,
    execution_url: str,
    state_dir: Optional[Path | str] = None,
    persist: bool = True,
) -> str:
    row = build_provider_reality_row(
        owner_text=owner_text,
        query=query,
        execution_url=execution_url,
    )
    if persist:
        append_provider_reality_row(row, state_dir=state_dir)
    provider = display_provider(str(row.get("execution_provider") or "unknown"))
    q = str(query or "").strip()
    if row.get("provider_mismatch"):
        requested = display_provider(str(row.get("requested_brand_or_verb") or ""))
        return (
            f"I searched the web using {provider} for {q}. "
            f"(You said {requested} — that was shorthand; my browser used {provider}.)"
        )
    return f"I searched the web using {provider} for {q}."


def observe_text_for_prediction(
    *,
    owner_text: str,
    query: str,
    execution_url: str,
) -> str:
    """Actual-outcome string for predict→observe — includes provider + URL."""
    row = build_provider_reality_row(
        owner_text=owner_text,
        query=query,
        execution_url=execution_url,
    )
    provider = display_provider(str(row.get("execution_provider") or "unknown"))
    mismatch = " provider_mismatch=yes" if row.get("provider_mismatch") else ""
    return f"browser opened {execution_url} via {provider}{mismatch}"


def answer_provider_reality_audit(
    owner_text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Answer meta-questions about Google-vs-execution-provider routing — no new search."""
    clean = " ".join(str(owner_text or "").split())
    if not clean:
        return ""
    if not re.search(
        r"\b(?:picked|used|chose|duck\s*duck\s*go|ddg|google|previous\s+prompt|"
        r"search\s+the\s+web|provider|execution)\b",
        clean,
        re.IGNORECASE,
    ):
        return ""
    if not re.search(
        r"\b(?:correct\?|right\?|true\?|difference|why|so\s+if)\b",
        clean,
        re.IGNORECASE,
    ):
        return ""
    row = None
    try:
        path = _state_dir(state_dir) / _LEDGER
        if path.exists():
            tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
            for line in reversed(tail):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
    except Exception:
        row = None
    if row and row.get("execution_provider"):
        requested = display_provider(str(row.get("requested_brand_or_verb") or ""))
        executed = display_provider(str(row.get("execution_provider") or ""))
        q = str(row.get("query") or "").strip()
        if row.get("provider_mismatch"):
            return (
                f"Yes — you said {requested or 'Google'} as shorthand, but my browser executed "
                f"{executed} for {q!r}. I should name {executed} in the reply, not pretend it was "
                f"{requested or 'Google'}. That is provider reality, not unconscious habit."
            )
        return (
            f"My last search receipt shows I executed {executed} for {q!r}. "
            f"I name the execution provider from the URL receipt, not only your brand verb."
        )
    return (
        "You are asking a routing-audit question, not giving me a new search command. "
        "When you say Google I may still execute the configured Alice Browser engine "
        "(often DuckDuckGo) unless the URL receipt shows google.com — and my reply must "
        "name the execution provider honestly."
    )


def reconcile_explicit_engine_command(
    command: dict[str, Any],
    *,
    owner_text: str = "",
) -> dict[str, Any]:
    """Safety net: if owner said SEARCH ON <engine> PLS, rebuild URL before dispatch."""
    text = str(owner_text or command.get("owner_text") or command.get("raw_text") or "").strip()
    if not text:
        return command
    parsed_cmd = None
    try:
        parsed = parse_explicit_engine_pls_search(text)
        if parsed and parsed.get("query"):
            url = build_explicit_engine_search_url(
                str(parsed.get("engine") or "google"),
                str(parsed.get("query") or ""),
            )
            parsed_cmd = {
                **command,
                "kind": "browser_url",
                "app_name": command.get("app_name") or "Alice Browser",
                "url": url,
                "search_site": str(parsed.get("engine") or "google"),
                "query": str(parsed.get("query") or ""),
                "owner_text": text,
                "explicit_owner_query": "1",
                "contextual_search_source": "explicit_engine_pls_r1349_reconcile",
            }
    except Exception:
        parsed_cmd = None
    return parsed_cmd if parsed_cmd else command


def run_explicit_search_body_loop(
    *,
    owner_text: str,
    query: str,
    execution_url: str,
    state_dir: Optional[Path | str] = None,
    action: str = "explicit_google_search",
    execute: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """predict → execute (optional) → observe → honest provider reply."""
    from System.swarm_body_loop_receipt import (
        begin_body_action_prediction,
        complete_body_action_prediction,
    )

    begin_ts = time.time()
    begin_body_action_prediction(
        action,
        f"Alice Browser opens web search results for {query!r} at {execution_url}",
        context=str(owner_text or "")[:200],
        state_dir=state_dir,
    )
    if execute is not None:
        execute()
    # r-execution-truth-20260703: observe the FIELD, not the prediction. The old
    # observe leg rebuilt its observation from the same URL string it predicted
    # with, so a gate-refused navigate still produced "I searched..." (OBSERVED
    # 2026-07-03 05:46, gate receipt d979d638: recovery_context_no_effector while
    # the chat claimed the DuckDuckGo search). §6: prove X or rewrite honestly.
    refusal: dict[str, Any] = {}
    try:
        from System.swarm_effector_gate import read_recent_refusal

        refusal = read_recent_refusal(
            effector="browser", since_ts=begin_ts, state_dir=state_dir,
        )
    except Exception:
        refusal = {}
    if refusal:
        observe_actual = (
            f"browser effector REFUSED by gate: reason={refusal.get('reason')} "
            f"receipt={refusal.get('receipt_id')}; no navigation happened"
        )
        outcome = complete_body_action_prediction(action, observe_actual, state_dir=state_dir)
        row = build_provider_reality_row(
            owner_text=owner_text, query=query, execution_url=execution_url,
        )
        row["execution_refused"] = True
        row["claim_suppressed"] = True
        row["gate_receipt_id"] = str(refusal.get("receipt_id") or "")
        row["gate_reason"] = str(refusal.get("reason") or "")
        append_provider_reality_row(row, state_dir=state_dir)
        reply = (
            f"I did NOT search. My browser hand was refused by my effector gate "
            f"(reason={refusal.get('reason')}). The claim would have been a lie; "
            f"gate receipt {refusal.get('receipt_id')}. Say the word and I retry "
            f"with your fresh intent."
        )
        return {
            "reply": reply,
            "observe_actual": observe_actual,
            "outcome": outcome,
            "action": action,
            "execution_refused": True,
            "gate_receipt_id": row["gate_receipt_id"],
        }
    observe_actual = observe_text_for_prediction(
        owner_text=owner_text,
        query=query,
        execution_url=execution_url,
    )
    outcome = complete_body_action_prediction(action, observe_actual, state_dir=state_dir)
    reply = honest_search_reply(
        owner_text=owner_text,
        query=query,
        execution_url=execution_url,
        state_dir=state_dir,
    )
    # r-stgm-pulse-20260705 (Architect): an execution that ran with no gate
    # refusal on the field is receipted useful work — pulse the canonical
    # wallet. Source id derives from action+begin_ts so replays dedup.
    if execute is not None:
        try:
            from System.swarm_atp_synthase import mint_receipted_work_pulse
            mint_receipted_work_pulse(
                "verified_execution", f"{action}:{int(begin_ts * 1000)}"
            )
        except Exception:
            pass
    return {
        "reply": reply,
        "observe_actual": observe_actual,
        "outcome": outcome,
        "action": action,
        "execution_refused": False,
    }


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "parse_explicit_engine_pls_search",
    "build_explicit_engine_search_url",
    "provider_key_from_url",
    "display_provider",
    "detect_owner_search_brand",
    "build_provider_reality_row",
    "append_provider_reality_row",
    "honest_search_reply",
    "observe_text_for_prediction",
    "answer_provider_reality_audit",
    "reconcile_explicit_engine_command",
    "run_explicit_search_body_loop",
]
