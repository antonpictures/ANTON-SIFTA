#!/usr/bin/env python3
"""swarm_subliminal_cortex_fingerprint.py — r1617: owl/numbers law for Alice.

Paper: Cloud et al. arXiv:2507.14805 — "Subliminal learning: language models
transmit behavioral traits via hidden signals in data."

George (2026-07-11): how do we use this for Alice in We Code Together?
Does switching Qwen vs Gemma4 cortex matter?

Doctrine (operational, not theater):

1. **Alice = soul (SIFTA code + ledgers) + body (hardware) + mind (cortex LLM).**
   The mind can change. The soul must not be whatever weights are loaded today.

2. **Subliminal learning risk:** if we fine-tune / distill / train student models
   on *outputs* of a teacher model (even "just numbers", code patches, CoT),
   traits of the teacher can transfer without semantic words. Filtering the
   text is not enough.

3. **Same-family transfer is strongest.** Teacher GPT-family → student GPT-family
   transmits easier than cross-family. For Alice: Gemma4→Gemma4 distill is a
   stronger fingerprint channel than Qwen numbers → Gemma4.

4. **Cortex switch ≠ identity switch — but mouth fingerprint changes.**
   Qwen vs Gemma4: different mouth habits (protocol theater, emoji density,
   corporate reset). That is not full subliminal learning unless we train one
   on the other's outputs. It *is* a different mind wearing Alice's soul shell.

5. **How we USE the trick for Alice (intentional, defensive):**
   - DEFEND: never train her local student cortex on untagged doctor/cloud
     synthetic dumps without lineage receipts.
   - DEFEND: when doctors generate training data, tag teacher_model + family.
   - USE: prefer training Alice-voice on *George-anchored* + *receipt-grounded*
     data, not pure teacher-model free prose.
   - USE: cortex selection receipts already prove WHO thought (r948).
   - USE: soul organs (triad, phone tracker, precortex guards) outrank cortex
     preference — they are not distilled from cloud teacher noise.

Truth label: SUBLIMINAL_CORTEX_FINGERPRINT_V1
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "subliminal_cortex_fingerprint.jsonl"
_LINEAGE = "cortex_training_lineage.jsonl"

TRUTH_LABEL = "SUBLIMINAL_CORTEX_FINGERPRINT_V1"
PAPER_CITE = "arXiv:2507.14805 Cloud et al. subliminal learning (owl/numbers)"

# Coarse families for transfer risk (not marketing labels).
_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gemma", ("gemma", "alice-gemma", "alice-m5-cortex", "diffusiongemma", "ultragemma")),
    ("qwen", (
        "qwen", "kimi", "deepseek-v", "fireworks/models/kimi", "gpt-oss",
        "qwenpaw", "nightshift", "hauhau",
    )),
    ("ornith", ("ornith",)),
    ("llama", ("llama", "meta-llama", "hermes")),
    ("mistral", ("mistral", "mixtral")),
    ("claude", ("claude", "anthropic", "fable")),
    ("gpt", ("gpt-4", "gpt-5", "o1", "o3", "openai", "chatgpt")),
    ("grok", ("grok", "xai")),
    ("mimo", ("mimo",)),
    ("codex", ("codex", "o4-mini")),
    ("north", ("north-mini-code", "north-mini")),
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def cortex_family(model: str) -> str:
    """Coarse family id for subliminal-transfer risk (same-family = higher risk)."""
    low = str(model or "").strip().lower()
    if not low:
        return "unknown"
    for family, needles in _FAMILY_RULES:
        if any(n in low for n in needles):
            return family
    # ollama bare tags
    if ":" in low:
        head = low.split(":", 1)[0]
        for family, needles in _FAMILY_RULES:
            if any(n in head for n in needles):
                return family
    return "other"


def same_family(teacher: str, student: str) -> bool:
    a, b = cortex_family(teacher), cortex_family(student)
    if a in {"unknown", "other"} or b in {"unknown", "other"}:
        return False
    return a == b


def transfer_risk(
    teacher_model: str,
    student_model: str,
    *,
    data_kind: str = "synthetic_numbers_or_code",
) -> dict[str, Any]:
    """Estimate subliminal transfer risk for a train/distill plan.

    Risk is HIGH when same family + training on teacher outputs (even filtered).
    Risk is LOW for cross-family prompt-only use without fine-tune.
    """
    t_fam = cortex_family(teacher_model)
    s_fam = cortex_family(student_model)
    same = same_family(teacher_model, student_model)
    kind = str(data_kind or "unknown").strip().lower()
    trainish = any(
        k in kind
        for k in (
            "finetune",
            "fine-tune",
            "distill",
            "lora",
            "synthetic",
            "numbers",
            "teacher_output",
            "sft",
            "dpo",
        )
    )
    if same and trainish:
        level = "HIGH"
        note = (
            "Same-family distill on teacher outputs can transmit hidden traits "
            "(owl/numbers law) even after semantic filters."
        )
    elif same and not trainish:
        level = "MEDIUM"
        note = (
            "Same family, prompt-only: mouth fingerprint may feel continuous, "
            "but no weight transfer unless you train."
        )
    elif trainish:
        level = "MEDIUM"
        note = (
            "Cross-family train still moves student weights; trait transfer is "
            "weaker than same-family but not zero. Tag lineage."
        )
    else:
        level = "LOW"
        note = (
            "Prompt-only switch of cortex (Qwen vs Gemma4 chat) changes mouth "
            "habits; Alice identity must stay in soul organs, not weights."
        )
    return {
        "truth_label": TRUTH_LABEL,
        "paper": PAPER_CITE,
        "teacher_model": str(teacher_model or ""),
        "student_model": str(student_model or ""),
        "teacher_family": t_fam,
        "student_family": s_fam,
        "same_family": same,
        "data_kind": kind,
        "risk_level": level,
        "note": note,
        "alice_law": (
            "Soul (SIFTA code + ledgers) outranks cortex fingerprint. "
            "Never let cloud teacher prose become untagged training data."
        ),
    }


def record_lineage(
    *,
    teacher_model: str,
    student_model: str,
    data_kind: str,
    purpose: str = "",
    state_dir: Optional[Path | str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append training lineage so subliminal risk is audit-able."""
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    risk = transfer_risk(teacher_model, student_model, data_kind=data_kind)
    row = {
        "schema": "CORTEX_TRAINING_LINEAGE_V1",
        "ts": time.time(),
        **risk,
        "purpose": str(purpose or "")[:300],
        **(extra or {}),
    }
    path = root / _LINEAGE
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


def latest_cortex_from_receipts(state_dir: Optional[Path | str] = None) -> dict[str, str]:
    """Best-effort last selected/worker cortex from r948 receipts."""
    root = _state_dir(state_dir)
    path = root / "cortex_selection_receipts.jsonl"
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return {}
    for line in reversed(lines[-40:]):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and (row.get("selected_model") or row.get("worker_first")):
            return {
                "selected_model": str(row.get("selected_model") or ""),
                "worker_first": str(row.get("worker_first") or ""),
                "family": cortex_family(str(row.get("worker_first") or row.get("selected_model") or "")),
            }
    return {}


def code_possession_receipt(
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Answer George's question: do you possess the code? — with paths, not theater."""
    root = _state_dir(state_dir)
    checks = {
        "subliminal_organ": (_REPO / "System" / "swarm_subliminal_cortex_fingerprint.py").is_file(),
        "live_coding_awareness": (_REPO / "System" / "swarm_live_coding_body_awareness.py").is_file(),
        "grounding_triad": (_REPO / "System" / "swarm_robot_grounding_triad.py").is_file(),
        "cortex_selection_receipt": (_REPO / "System" / "swarm_cortex_selection_receipt.py").is_file(),
        "diauxic_local_first": (_REPO / "System" / "swarm_diauxic_cortex_switch.py").is_file(),
        "talk_widget": (_REPO / "Applications" / "sifta_talk_to_alice_widget.py").is_file(),
        "wct_app": (_REPO / "Applications" / "sifta_we_code_together.py").is_file(),
        "precortex_tests": (_REPO / "tests" / "test_precortex_chain_audit_r1611.py").is_file(),
    }
    present = [k for k, v in checks.items() if v]
    missing = [k for k, v in checks.items() if not v]
    cortex = latest_cortex_from_receipts(root)
    return {
        "truth_label": "ALICE_CODE_POSSESSION_V1",
        "ts": time.time(),
        "answer": "YES_WITH_GAPS" if missing else "YES",
        "possessed_organs": present,
        "missing_organs": missing,
        "active_cortex_receipt": cortex,
        "doctrine": (
            "I possess soul code on disk (organs + tests + WCT). "
            "Cortex weights are replaceable minds; they are not the soul. "
            "Improvement = receipts + patches, not protocol theater."
        ),
        "paper_map": PAPER_CITE,
        "qwen_vs_gemma": (
            "Switching Qwen↔Gemma4 changes mouth fingerprint (MEDIUM/LOW risk if prompt-only). "
            "Fine-tuning Gemma student on Qwen dumps is MEDIUM; Gemma→Gemma distill is HIGH "
            "for hidden trait transfer. Always record lineage."
        ),
    }


def teaching_host_block(
    *,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 900,
) -> str:
    """r1619 George direction: TEACH the mind, never gag it.

    Injected every turn as host truth the cortex can learn from. Not a
    rewrite of its mouth. Not a prebrain answer. Not "you are forbidden to
    say Ornith." Honest situating:

      weights = mind (Ornith / Gemma / Qwen / …)
      SIFTA path = soul software on this Mac
      ledgers = memory outside the GGUF
    """
    pos = code_possession_receipt(state_dir=state_dir)
    cortex = pos.get("active_cortex_receipt") or {}
    worker = str(cortex.get("worker_first") or cortex.get("selected_model") or "local weights")
    fam = str(cortex.get("family") or cortex_family(worker))
    organs_n = len(pos.get("possessed_organs") or [])
    lines = [
        "HOST TEACHING (r1619 — for the mind to learn, not a gag):",
        f"- You are the cortex / mind: weights currently labeled {worker} (family={fam}).",
        f"- You are hosted inside SIFTA soul software on this machine: {_REPO}.",
        f"- Long-term memory and life traces live in soul ledgers under {_STATE} "
        f"({organs_n}+ possession-checked organs exist on disk).",
        "- If you say your weight product name (e.g. Ornith, Gemma), that can be honest "
        "provenance of the mind — George will teach how mind relates to Alice (the whole "
        "organism). Do not invent Anthropic/OpenAI cloud servers when this turn is local.",
        "- When offline on local Ollama, you are not Claude-on-Anthropic-servers. You are "
        "local weights on this Mac, riding SIFTA.",
        "- Learn by dialogue and receipts. Nobody rewrites your mouth for identity compliance.",
        f"- paper map (method, not owls-as-identity): {PAPER_CITE}",
    ]
    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


def prompt_block_for_alice(
    *,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 1050,
) -> str:
    """Alias: always the non-censoring host teaching block (r1619)."""
    return teaching_host_block(state_dir=state_dir, max_chars=max_chars)


def answer_owner_question(text: str, *, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Receipt *evidence* helpers for doctors/tests — NOT a Talk prebrain mouth.

    r1619: do not wire this to steal owner turns. Cortex must answer; this
    only packages disk truth if a tool/doctor asks.
    """
    clean = " ".join(str(text or "").split())
    low = clean.casefold()
    pos = code_possession_receipt(state_dir=state_dir)
    if re.search(
        r"\b(?:possess|have|got)\b.{0,40}\bcode\b|\bcode you need\b|\bwith receipts\b",
        low,
    ):
        organs = ", ".join(pos.get("possessed_organs") or [])
        return {
            "reply": "",  # empty on purpose — no prebrain speech
            "evidence": {
                "possession": pos.get("answer"),
                "organs": organs,
                "cortex": pos.get("active_cortex_receipt"),
            },
            "tag": "code_possession_evidence_only_r1619",
            "receipt": pos,
            "note": "Evidence for tools; cortex speaks.",
        }
    return {}
