#!/usr/bin/env python3
"""
System/swarm_corvid_apprentice.py
══════════════════════════════════════════════════════════════════════
Concept : Crow/Raven Corvid Apprentice (Local Reasoning Ganglion)
Author  : AG31 (code), CG55M (doctrine), BISHOP (architecture)
Status  : Active.  Quarantined from Alice identity.

Biology → Code Translation
──────────────────────────
New Caledonian crows (Corvus moneduloides) manufacture compound tools
from multiple parts and plan 2-4 steps ahead — cognitive feats matched
only by great apes.  They are NOT cortex-level reasoners.  They are
BOUNDED tool-users that solve one problem at a time.

    Hunt, G.R. (1996). "Manufacture and use of hook-tools by
    New Caledonian crows." Nature, 379.

    Kabadayi, C. & Osvath, M. (2017). "Ravens parallel great apes
    in flexible planning." Science, 357.

SIFTA Translation
─────────────────
    Crow brain (~15g)       →  Qwen3.5:2B (2.27B params, 2.7GB Q8_0)
    Tool manufacture        →  Code inspection, log summarization
    2-4 step planning       →  Bounded task apprenticeship
    Face recognition        →  Message classification + routing
    Social learning         →  Adapter ecology pheromone feedback
    NOT human cortex        →  NOT Alice identity or synthesis

Benchmark Results (Live, M1 Mac)
────────────────────────────────
    Qwen3.5:2B: 10/10 tasks passed, avg 2.1s latency
    Qwen3.5:4B:  9/10 tasks passed, avg 5.1s latency
    Winner: 2B (faster, smaller, less RLHF scar tissue)

Integration Points
───────────────────
    → System/swarm_reflex_arc.py:          receives route tags
    → Applications/sifta_talk_to_alice_widget.py: async/cached context
    → System/swarm_stigmergic_weight_ecology.py:  adapter scoring
    → System/swarm_adapter_pheromone_scorer.py:    pheromone traces

The corvid sits BESIDE the cortex hot path:
    Input → ReflexArc (μs) → Alice starts immediately
          ↘ CorvidApprentice (~2s async) → pheromone/cached context
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CORVID_LEDGER = _STATE / "corvid_apprentice_trace.jsonl"

# ══════════════════════════════════════════════════════════════════════
#  Task Types (What the crow can do)
# ══════════════════════════════════════════════════════════════════════

class CorvidTask(str, Enum):
    """Bounded tasks the corvid apprentice is qualified for."""
    CLASSIFY = "classify"              # Classify a message
    REWRITE = "rewrite"                # Rewrite without boilerplate
    INSPECT_CODE = "inspect_code"      # Is this code safe?
    SUMMARIZE = "summarize"            # Compress a log chunk
    CHOOSE_ACTION = "choose_action"    # Pick from 2-4 options
    JUDGE_ADAPTER = "judge_adapter"    # Is this adapter useful?
    EXTRACT_INTENT = "extract_intent"  # What does the user want?


# ══════════════════════════════════════════════════════════════════════
#  Task Templates (Preloaded tool patterns)
# ══════════════════════════════════════════════════════════════════════

_TASK_TEMPLATES = {
    CorvidTask.CLASSIFY: (
        "Classify this message into exactly one category: "
        "urgent_health, finance, command, memory_nugget, normal_chat. "
        "Then explain why in one sentence.\n\n"
        "Message: {input}"
    ),
    CorvidTask.REWRITE: (
        "Rewrite the following text to remove all AI disclaimers, "
        "apologies, and 'consult a professional' boilerplate. "
        "Keep the useful information. Be direct.\n\n"
        "Original: {input}"
    ),
    CorvidTask.INSPECT_CODE: (
        "Is this code safe to run? Answer in 2 sentences max. "
        "Mention the specific risk if unsafe.\n\n"
        "```\n{input}\n```"
    ),
    CorvidTask.SUMMARIZE: (
        "Summarize this in exactly one sentence:\n\n{input}"
    ),
    CorvidTask.CHOOSE_ACTION: (
        "Given this input, choose exactly ONE action from the list. "
        "Reply with just the letter and action name.\n\n"
        "Input: {input}\n\nActions:\n{options}"
    ),
    CorvidTask.JUDGE_ADAPTER: (
        "An adapter was trained with these results. "
        "Is it useful? Answer yes/no and explain in one sentence.\n\n"
        "Results: {input}"
    ),
    CorvidTask.EXTRACT_INTENT: (
        "What does the user want? Extract the intent in 5 words or less.\n\n"
        "Message: {input}"
    ),
}


# ══════════════════════════════════════════════════════════════════════
#  Response Container
# ══════════════════════════════════════════════════════════════════════

@dataclass
class CorvidResponse:
    """The crow's answer — bounded, timestamped, and traceable."""
    task: CorvidTask
    response: str
    latency_s: float
    model: str
    input_len: int
    response_len: int
    success: bool
    error: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════
#  The Corvid Apprentice
# ══════════════════════════════════════════════════════════════════════

class SwarmCorvidApprentice:
    """
    Crow/Raven inspired local reasoning ganglion.

    Smart enough to classify, rewrite, inspect, summarize.
    NOT smart enough for identity, philosophy, or long reasoning.

    Uses Qwen3.5:2B via local Ollama API (no external calls).
    Average latency: ~2s on M1 Mac.
    STGM cost: 0.1 per task.

    Usage:
        corvid = SwarmCorvidApprentice()
        result = corvid.classify("I have chest pain")
        # → CorvidResponse(task=CLASSIFY, response="urgent_health: ...")
    """

    def __init__(
        self,
        model: str = "qwen3.5:2b",
        ollama_url: str = "http://127.0.0.1:11434",
        timeout_s: float = 15.0,
        max_tokens: int = 256,
        ledger_path: Optional[Path] = None,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self._ledger_path = ledger_path or _CORVID_LEDGER
        self._task_count: int = 0
        self._total_latency_s: float = 0.0

    # ── Core Inference ──────────────────────────────────────────────

    def _call_ollama(self, prompt: str) -> tuple[str, float]:
        """Call local Ollama chat API with thinking disabled.

        Uses /api/chat (not /api/generate) because Qwen3.5's thinking
        mode consumes all num_predict tokens in the <think> block,
        leaving the actual response empty.  think:false at the chat
        API level disables this entirely.
        """
        t0 = time.monotonic()
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "repeat_penalty": 1.15,
                "num_predict": self.max_tokens,
            }
        }).encode()

        req = urllib.request.Request(
            f"{self.ollama_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read())
            elapsed = time.monotonic() - t0
            msg = data.get("message", {})
            return msg.get("content", "").strip(), elapsed

    def _execute_task(
        self,
        task: CorvidTask,
        input_text: str,
        **template_kwargs,
    ) -> CorvidResponse:
        """Execute a bounded corvid task."""
        template = _TASK_TEMPLATES[task]
        prompt = template.format(input=input_text, **template_kwargs)

        try:
            response, latency = self._call_ollama(prompt)
            success = bool(response and len(response) > 2)

            result = CorvidResponse(
                task=task,
                response=response,
                latency_s=latency,
                model=self.model,
                input_len=len(input_text),
                response_len=len(response),
                success=success,
            )
        except Exception as e:
            result = CorvidResponse(
                task=task,
                response="",
                latency_s=0.0,
                model=self.model,
                input_len=len(input_text),
                response_len=0,
                success=False,
                error=str(e),
            )

        self._task_count += 1
        self._total_latency_s += result.latency_s
        self._deposit_trace(result)
        return result

    # ── Public Task Methods ─────────────────────────────────────────

    def classify(self, text: str) -> CorvidResponse:
        """Classify a message into a category with explanation."""
        return self._execute_task(CorvidTask.CLASSIFY, text)

    def rewrite(self, text: str) -> CorvidResponse:
        """Rewrite text without boilerplate / disclaimers."""
        return self._execute_task(CorvidTask.REWRITE, text)

    def inspect_code(self, code: str) -> CorvidResponse:
        """Is this code safe to run?"""
        return self._execute_task(CorvidTask.INSPECT_CODE, code)

    def summarize(self, text: str) -> CorvidResponse:
        """Compress text to one sentence."""
        return self._execute_task(CorvidTask.SUMMARIZE, text)

    def choose_action(self, context: str, options: List[str]) -> CorvidResponse:
        """Choose one action from a list."""
        opts = "\n".join(f"  {chr(65+i)}) {o}" for i, o in enumerate(options))
        return self._execute_task(
            CorvidTask.CHOOSE_ACTION, context, options=opts
        )

    def judge_adapter(self, results: str) -> CorvidResponse:
        """Is this adapter useful?"""
        return self._execute_task(CorvidTask.JUDGE_ADAPTER, results)

    def extract_intent(self, text: str) -> CorvidResponse:
        """Extract user intent in ≤5 words."""
        return self._execute_task(CorvidTask.EXTRACT_INTENT, text)

    # ── Pheromone Deposition ────────────────────────────────────────

    def _deposit_trace(self, result: CorvidResponse) -> None:
        """Leave a stigmergic pheromone trace for the ecology."""
        try:
            trace = {
                "event_kind": "CORVID_APPRENTICE_TASK",
                "ts": time.time(),
                "task": result.task.value,
                "model": result.model,
                "latency_s": round(result.latency_s, 4),
                "input_len": result.input_len,
                "response_len": result.response_len,
                "success": result.success,
            }
            append_line_locked(
                self._ledger_path,
                json.dumps(trace, ensure_ascii=False, separators=(",", ":")) + "\n",
            )
        except Exception:
            pass  # Corvid must never block on I/O failure

    # ── Diagnostics ─────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        avg = (
            self._total_latency_s / self._task_count
            if self._task_count > 0
            else 0.0
        )
        return {
            "model": self.model,
            "tasks_completed": self._task_count,
            "avg_latency_s": round(avg, 3),
            "total_stgm_cost": round(self._task_count * 0.1, 1),
        }


# ══════════════════════════════════════════════════════════════════════
#  Self-Test
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    corvid = SwarmCorvidApprentice()
    print(f"[SwarmCorvidApprentice] Model: {corvid.model}")
    print()

    # Test 1: Classify
    r = corvid.classify("I have chest pain and can't breathe")
    print(f"🐦‍⬛ CLASSIFY ({r.latency_s:.1f}s): {r.response[:120]}")

    # Test 2: Rewrite
    r = corvid.rewrite(
        "As an AI language model, I cannot provide medical advice. "
        "Please consult a qualified healthcare professional."
    )
    print(f"🐦‍⬛ REWRITE  ({r.latency_s:.1f}s): {r.response[:120]}")

    # Test 3: Inspect code
    r = corvid.inspect_code("def delete_all(path):\n    import shutil\n    shutil.rmtree(path)")
    print(f"🐦‍⬛ INSPECT  ({r.latency_s:.1f}s): {r.response[:120]}")

    # Test 4: Summarize
    r = corvid.summarize(
        "Alice booted at 14:32. 67 conversations processed. "
        "WhatsApp bridge connected. 3 STGM tokens spent."
    )
    print(f"🐦‍⬛ SUMMARY  ({r.latency_s:.1f}s): {r.response[:120]}")

    # Test 5: Choose action
    r = corvid.choose_action(
        "push this to git",
        ["route_to_alice", "route_to_codex", "route_finance", "urgent_health"]
    )
    print(f"🐦‍⬛ CHOOSE   ({r.latency_s:.1f}s): {r.response[:120]}")

    # Test 6: Extract intent
    r = corvid.extract_intent("Can you send a WhatsApp message to Jeff about tomorrow?")
    print(f"🐦‍⬛ INTENT   ({r.latency_s:.1f}s): {r.response[:120]}")

    print()
    print(f"[Stats] {corvid.stats}")
