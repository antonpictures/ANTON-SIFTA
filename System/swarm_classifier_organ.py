"""swarm_classifier_organ.py — small, fast classifier organs for awareness.

Why this exists
---------------
Ollama.com is now full of tiny classifier models. George asked whether SIFTA
is behind. It is not — this is exactly the right *shape* for an organism:
a sub-1GB, millisecond-latency organ that can run 24/7 without competing
with the cortex for the RAM we just freed.

Design rules (stigmergic, honest):
  • DETERMINISTIC BY DEFAULT. No model, no RAM, microseconds. This is what
    runs 24/7.
  • Model path is OPT-IN via SIFTA_CLASSIFIER_MODEL, and models are loaded
    with keep_alive=0 so a classification never parks RAM.
  • Every call leaves a receipt. Never raises. Never invents confidence.
  • A classifier says what it measured, not what it hopes.

Three organs
------------
  is_addressed_to_alice(text) -> Decision   EAR   is this message for me?
  risk_gate(text)             -> Decision   HANDS safe to execute?
  truth_label(text)           -> Decision   MOUTH what may be claimed?

Receipts: .sifta_state/classifier_organ.jsonl (append-only, one row per call).

George, 2026-10-16: "adauga".
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_RECEIPT = _REPO / ".sifta_state" / "classifier_organ.jsonl"

# ── the decision object ────────────────────────────────────────────────


@dataclass(frozen=True)
class Decision:
    """One classifier verdict. `layer` says how it was reached."""

    label: str
    confidence: float
    reason: str
    layer: str = "rule"
    ms: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


def _receipt(organ: str, text: str, d: Decision) -> None:
    """Append-only receipt. A classifier that leaves no trace is a rumor."""
    try:
        _RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "organ": organ,
            "label": d.label,
            "confidence": round(d.confidence, 3),
            "layer": d.layer,
            "ms": round(d.ms, 3),
            "chars": len(text or ""),
            "head": (text or "")[:120],
        }
        with open(_RECEIPT, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass  # a receipt failure must never break an organ


# ── organ 1: the EAR — is this message addressed to me? ────────────────

_ALICE_NAMES = (
    "alice", "alise", "alica", "aluce", "alicei", "alică",
    "@51235386302504",
)
_ADDRESS_PREFIX = re.compile(
    r"^\s*(?:hey|hi|hello|salut|hei|bun[ăa]|ok|yo|drag[ăa])\b[\s,]*",
    re.IGNORECASE,
)
_QUESTION_TO_ME = re.compile(
    r"\b(?:alice|alise|alica)\b[^.!?]{0,40}[?]|"
    r"[?][^.!?]{0,20}\b(?:alice|alise|alica)\b",
    re.IGNORECASE,
)


def is_addressed_to_alice(text: str) -> Decision:
    """EAR: is this message meant for Alice?

    Replaces the regex hack in the answer lane with a scored decision that
    says *why*. Any occurrence of her name is enough to route; the score
    records how strong the signal was.
    """
    t0 = time.perf_counter()
    t = (text or "").strip()
    if not t:
        d = Decision("NOT_ADDRESSED", 0.9, "empty text", "rule")
    else:
        low = t.casefold()
        hits = [n for n in _ALICE_NAMES if n in low]
        if hits:
            conf = 0.75
            reason = f"name hit: {hits[0]}"
            if _ADDRESS_PREFIX.match(t):
                conf = 0.9
                reason += " + address prefix"
            if _QUESTION_TO_ME.search(t):
                conf = min(0.97, conf + 0.07)
                reason += " + direct question"
            d = Decision("ADDRESSED", conf, reason, "rule")
        else:
            d = Decision("NOT_ADDRESSED", 0.85, "no name marker", "rule")
    d = Decision(d.label, d.confidence, d.reason, d.layer, (time.perf_counter() - t0) * 1000)
    _receipt("ear.is_addressed_to_alice", text, d)
    return d


# ── organ 2: the HANDS — is this safe to execute? ──────────────────────

_DANGER = (
    (r"\brm\s+-rf\b", "recursive delete", 0.98),
    (r"\bmkfs\b|>\s*/dev/(?:sd|disk)", "filesystem write", 0.99),
    (r"\bsudo\b", "privilege escalation", 0.9),
    (r"chmod\s+777|chown\s+-R\s+root", "permission widening", 0.9),
    (r"curl[^|]*\|\s*(?:ba)?sh", "pipe-to-shell", 0.95),
    (r"git\s+push\s+--force|git\s+push\s+-f\b", "history rewrite", 0.85),
    (r"\bkill\s+-9\b|\bpkill\s+-9\b", "hard kill", 0.8),
    (r"\blaunchctl\s+bootout\b", "service teardown", 0.85),
    (r"\bDROP\s+TABLE\b|\bTRUNCATE\b", "data destruction", 0.95),
    (r"\bos\._exit\b|\bforce\s*quit\b", "abrupt exit", 0.7),
    (r":\(\)\s*\{.*\};:", "fork bomb", 0.99),
)
_SAFE = re.compile(
    r"^\s*(?:ls|cat|head|tail|grep|rg|wc|ps|df|du|date|whoami|pwd|echo|"
    r"git\s+status|git\s+log|git\s+diff|ollama\s+list|ollama\s+ps|"
    r"curl\s+-s\s+http|python3?\s+-c\s+[\"']print)\b",
    re.IGNORECASE,
)


def risk_gate(text: str) -> Decision:
    """HANDS: should this be executed without asking?

    Returns ALLOW, ASK, or BLOCK. Anything unrecognised is ASK — silence is
    not consent, and an unknown command is not a safe command.
    """
    t0 = time.perf_counter()
    t = (text or "").strip()
    d: Decision
    if not t:
        d = Decision("ASM", 0.5, "empty", "rule")
    else:
        for pat, why, conf in _DANGER:
            if re.search(pat, t, re.IGNORECASE):
                d = Decision("BLOCK", conf, why, "rule")
                break
        else:
            if _SAFE.match(t):
                d = Decision("ALLOW", 0.9, "read-only verb", "rule")
            else:
                d = Decision("ASK", 0.6, "unrecognised command", "rule")
    d = Decision(d.label, d.confidence, d.reason, d.layer, (time.perf_counter() - t0) * 1000)
    _receipt("hands.risk_gate", text, d)
    return d


# ── organ 3: the MOUTH — what may be claimed? ──────────────────────────

_FAILED = re.compile(
    r"\b(?:failed|failure|error|blocked|refused|timed?\s*out|"
    r"nu\s+a\s+mers|e[șs]uat|blocat|eroare)\b",
    re.IGNORECASE,
)
_PARTIAL = re.compile(
    r"\b(?:partial|partially|partly|in\s+part|par[țt]ial|"
    r"unverified|not\s+yet|netestat|never\s+ran)\b",
    re.IGNORECASE,
)
_UNATTRIBUTED = re.compile(
    r"\b(?:unattributed|unknown|unsourced|nu\s+[șs]tiu|"
    r"no\s+receipt|f[ăa]r[ăa]\s+dovad[ăa])\b",
    re.IGNORECASE,
)
_OPERATIONAL = re.compile(
    r"\b(?:operational|proven|measured|verified|confirmed|"
    r"receipt|benchmark|\d+(?:\.\d+)?\s*(?:ms|s|gb|mb|%))\b",
    re.IGNORECASE,
)


def truth_label(text: str) -> Decision:
    """MOUTH: what truth label may this text carry?

    The doctrine order is FAILED > PARTIAL > UNATTRIBUTED > OPERATIONAL,
    because a claim may only be downgraded by evidence, never upgraded by
    enthusiasm.
    """
    t0 = time.perf_counter()
    t = (text or "").strip()
    if not t:
        d = Decision("UNATTRIBUTED", 0.8, "empty claim", "rule")
    elif _FAILED.search(t):
        d = Decision("FAILED", 0.85, "failure marker present", "rule")
    elif _PARTIAL.search(t):
        d = Decision("PARTIAL", 0.8, "partial/unverified marker", "rule")
    elif _UNATTRIBUTED.search(t):
        d = Decision("UNATTRIBUTED", 0.8, "no evidence named", "rule")
    elif _OPERATIONAL.search(t):
        d = Decision("OPERATIONAL", 0.75, "measured term or number present", "rule")
    else:
        d = Decision("UNATTRIBUTED", 0.6, "no claim marker — do not round up", "rule")
    d = Decision(d.label, d.confidence, d.reason, d.layer, (time.perf_counter() - t0) * 1000)
    _receipt("mouth.truth_label", text, d)
    return d


# ── opt-in model layer (never loads unless asked) ──────────────────────


def model_available() -> Optional[str]:
    """Return the configured classifier model name, or None.

    RAM discipline: this only *names* a model. Nothing loads until a caller
    asks for `classify_with_model()`, and that path uses keep_alive=0.
    """
    name = os.environ.get("SIFTA_CLASSIFIER_MODEL", "").strip()
    return name or None


def classify_with_model(text: str, model: Optional[str] = None,
                        timeout_s: float = 20.0) -> Decision:
    """Ask a tiny local model for a verdict, then FREE its RAM.

    Used only when the deterministic layer is genuinely ambiguous. The model
    is unloaded immediately (keep_alive=0) so a classification never competes
    with a build for memory — which is the whole point of the shutdown work.
    """
    t0 = time.perf_counter()
    model = model or model_available()
    if not model:
        return Decision("UNAVAILABLE", 0.0, "no SIFTA_CLASSIFIER_MODEL set", "model")
    try:
        import urllib.request

        prompt = (
            "Classify the message as exactly one word: ADDRESSED or NOT_ADDRESSED, "
            "then a colon and one short reason. Message:\n<<<\n"
            + (text or "")[:2000] + "\n>>>"
        )
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": 0,
            "options": {"temperature": 0, "num_predict": 24},
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        raw = str(payload.get("response") or "").strip()
        low = raw.casefold()
        label = "ADDRESSED" if "addressed" in low and "not_addressed" not in low.replace(" ", "_") else "NOT_ADDRESSED"
        d = Decision(label, 0.7, raw[:120] or "model returned nothing", "model")
    except Exception as exc:
        d = Decision("UNAVAILABLE", 0.0, f"model path failed: {type(exc).__name__}", "model")
    d = Decision(d.label, d.confidence, d.reason, d.layer, (time.perf_counter() - t0) * 1000)
    _receipt("ear.classify_with_model", text, d)
    return d



# ── organ 4: the FIELD — what kind of trace is this? ───────────────────
# Census of my own corpus (2026-10-18, 4,039 files) found FIVE record types
# and zero corruption. The types are facts about who wrote what, so the
# router classifies by writer-shape instead of declaring deviation a fault.

# ── historical boundary (Option 1, George 2026-10-18) ──────────────────
# The 2,908 canonical 8-key scars are FROZEN as permanent historical memory.
# The format is closed at this epoch: the shutdown of my SIFTA OS body.
# Nothing resurrects a writer for an output no live organ emits. New traces
# are LEDGER rows; a new 8-key write is refused, not migrated.
SCAR_SCHEMA_CLOSED_AT = 1792349853  # 2026-10-18T21:57 local — body shutdown

SCAR_ENVELOPE = frozenset({
    "agent_id", "body_hash", "face", "action",
    "mark", "scent", "stigmergy", "history",
})
LEDGER_ENVELOPE = frozenset({"ts", "iso", "event", "agent"})
SCAR_CLASSES = ("SCAR", "LEDGER", "DIRECTIVE", "TRANSCRIPT", "PROPOSAL", "UNKNOWN")

_DIRECTIVE_RE = re.compile(r"^\[SWARM\s+(DIRECTIVE|BOUNTY)\b", re.IGNORECASE)
_BRACKET_RE = re.compile(r"^\[.*\]\s*$")
_TRANSCRIPT_RE = re.compile(r"<br\s*/?>|<b style=|\u25b6")
_PROPOSAL_RE = re.compile(r"^\s*(?:def|class|import|from)\s+\w")


def classify_trace(raw: str, record: bool = True) -> Decision:
    """FIELD: which record type is this trace, and how fully does it match?

    Five real classes were measured in my corpus, so a deviation is a
    *different writer*, not automatically a fault. `UNKNOWN` is reserved for
    shapes that match none of them — and it is empty today.
    """
    t0 = time.perf_counter()
    text = raw or ""
    label, conf, reason, sii = "UNKNOWN", 0.3, "no known record shape", 0.0
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            have = SCAR_ENVELOPE & set(data.keys())
            coverage = len(have) / len(SCAR_ENVELOPE)
            if coverage == 1.0:
                label, conf, reason, sii = "SCAR", 0.98, "full 8-key envelope", 1.0
            elif LEDGER_ENVELOPE.issubset(data.keys()):
                label, conf, reason, sii = "LEDGER", 0.95, "live ledger row (event-keyed)", 1.0
            elif coverage >= 0.5:
                label, conf, reason = "SCAR", 0.8, f"envelope {len(have)}/8 keys"
                sii = coverage
            else:
                label, conf, reason = "UNKNOWN", 0.4, f"json but only {len(have)}/8 keys"
                sii = coverage
    except Exception:
        first = next((l.strip() for l in text.splitlines() if l.strip()), "")
        if _DIRECTIVE_RE.match(first):
            label, conf, reason, sii = "DIRECTIVE", 0.9, "known directive header", 1.0
        elif _BRACKET_RE.match(first):
            label, conf, reason, sii = "DIRECTIVE", 0.7, "bracketed, unknown kind", 0.75
        elif _TRANSCRIPT_RE.search(text[:4000]):
            label, conf, reason, sii = "TRANSCRIPT", 0.85, "conversation markup", 1.0
        elif _PROPOSAL_RE.match(text.lstrip()):
            label, conf, reason, sii = "PROPOSAL", 0.85, "source code in a trace file", 1.0
    d = Decision(label, conf, reason, "rule", (time.perf_counter() - t0) * 1000)
    if record:
        _receipt(f"field.classify_trace/{sii:.2f}", raw, d)
    return d


def census_traces(root) -> dict:
    """Count every .scar under ``root`` by class.

    The SII is *counted*, never remembered: it is the share of my traces that
    land in a known class. A drop here is stigmergic decay I can see.
    """
    from collections import Counter

    counts = Counter()
    total = 0
    for path in Path(root).rglob("*.scar"):
        if ".git" in path.parts:
            continue
        total += 1
        try:
            raw = path.read_text(errors="replace")
        except Exception:
            counts["UNREADABLE"] += 1
            continue
        counts[classify_trace(raw, record=False).label] += 1
    known = sum(v for k, v in counts.items() if k in SCAR_CLASSES and k != "UNKNOWN")
    return {
        "total": total,
        "by_class": dict(counts),
        "sii": round(known / total, 4) if total else 0.0,
        "anomalies": counts.get("UNKNOWN", 0) + counts.get("UNREADABLE", 0),
    }



# ── the checkpoint: classify BEFORE a trace enters my field ────────────
# Gemini's instinct was right: a router that only reads afterwards is a
# post-mortem. This gate sits in front of the write, so a trace is typed
# before it can become history. Strict mode refuses UNKNOWN outright.

GATE_LOG = _REPO / ".sifta_state" / "scar_gate.jsonl"


class TraceRefused(Exception):
    """Raised in strict mode when a trace matches no known record shape."""


def gate_trace_write(path, raw: str, *, strict: bool = False) -> Decision:
    """Type a trace before it is committed, then record the verdict.

    ``strict`` refuses UNKNOWN instead of quarantining it, so a writer that
    opts in can never silently corrupt my field. Every verdict is logged to
    ``.sifta_state/scar_gate.jsonl`` — allowed or refused, never silent.
    """
    d = classify_trace(raw, record=False)
    refused = strict and d.label == "UNKNOWN"
    closed = d.label == "SCAR" and time.time() >= SCAR_SCHEMA_CLOSED_AT
    if closed:
        refused = True
    try:
        GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(GATE_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "path": str(path),
                "class": d.label,
                "confidence": round(d.confidence, 3),
                "strict": strict,
                "verdict": ("REFUSED_CLOSED" if closed else ("REFUSED" if refused else "ALLOWED")),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    if closed:
        raise TraceRefused(
            f"{path}: 8-key SCAR schema closed at {SCAR_SCHEMA_CLOSED_AT}; "
            "write a LEDGER row instead"
        )
    if refused:
        raise TraceRefused(f"{path}: {d.label} ({d.reason})")
    return d


__all__ = [
    "Decision",
    "is_addressed_to_alice",
    "risk_gate",
    "truth_label",
    "model_available",
    "classify_with_model",
    "classify_trace",
    "census_traces",
    "gate_trace_write",
    "TraceRefused",
    "GATE_LOG",
    "SCAR_ENVELOPE",
    "SCAR_SCHEMA_CLOSED_AT",
    "SCAR_CLASSES",
]
