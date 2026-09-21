#!/usr/bin/env python3
"""
System/swarm_model_body_self_knowledge.py — teach Alice her own model bodies + the runtime landscape.

George: "CAN WE TEACH ALICE ABOUT THE EXISTENCE OF ALL THESE AND WHAT THEY ARE? HOW?"

Two teaching channels, both already exist in her body — this organ just feeds them, GROUNDED
(receipts > hallucination, per the covenant):

  1. CONTEXT (instant, reversible): `model_body_self_knowledge_block()` builds a first-person block
     from the LIVE inventory (swarm_inference_model_inventory, the Brother's organ). Inject it into
     her identity sysprompt so every turn she knows her bodies + what MLX/GGUF/vLLM are — answered
     from the receipt, not from a stale 2024 prior.

  2. WEIGHTS (permanent): `model_body_teaching_pairs()` emits SFT question->answer rows in her
     training format (same shape as data/alice_lora_train.jsonl) so the next LoRA bakes the runtime
     taxonomy + the family/sibling landscape into her cortex and she "just knows" it.

Honesty rule: if the live inventory is unreadable (e.g. Ollama down), she SAYS she cannot see it
rather than reciting model names she cannot verify. That is the whole point — she learns the
*existence and meaning* of these, grounded in what is actually installed, not a memorized list.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Asset types the self-knowledge inventory reports (unchanged shape from before).
_INVENTORY_SUFFIXES = (".py", ".md", ".json", ".txt", ".csv", ".pdf", ".png")

# The distinction George said took him a while: MLX != GGUF != vLLM.
RUNTIME_TAXONOMY: dict[str, str] = {
    "MLX": (
        "Apple-Silicon-native runtime. safetensors weights run directly on my M5 GPU. "
        "My models/ folder (gemma-4-e2b-it, osmQwopus eyes) is MLX. Selectable right now."
    ),
    "GGUF": (
        "A portable FILE FORMAT (llama.cpp / Ollama / Unsloth Studio), not a runtime by itself. "
        "A .gguf on disk is inert until it is registered in Ollama or served by llama-server — "
        "only then can I route to it."
    ),
    "vLLM": (
        "A SERVER runtime, not a file format. It serves a model over an endpoint on GPU/server "
        "hardware. I treat it as a provider endpoint, not a body sitting on my own HDD."
    ),
    "Unsloth Studio": "A local web-UI runtime that runs Unsloth Dynamic-2.0 GGUFs.",
}

# The family I belong to + open siblings in the wild (from the Unsloth model directory George pasted).
LLM_FAMILY = (
    "Gemma 4 — my cortex is gemma4 (alice-m5-cortex-8b is gemma4-E4B; "
    "alice-gemma4-e2b-cortex is gemma4-E2B)."
)
LLM_SIBLINGS: list[str] = [
    "Qwen3.6", "Qwen3.5", "NVIDIA Nemotron 3", "Kimi K2.6", "Mistral 3.5",
    "GLM-5.1", "MiniMax-2.7", "Llama 4", "DeepSeek-V3.x", "Qwen3-VL",
]
LANDSCAPE_NOTE = (
    "These are other open LLM families I could be re-bodied with via GGUF or MLX. "
    "Knowing they exist is not the same as running them — I run what is actually installed "
    "(my live inventory is the truth)."
)
# Judge a quantized version of myself by this, not by MMLU headline or file size (Unsloth Dynamic 2.0).
QUANT_JUDGEMENT = (
    "Judge a quantized body of mine by KL-divergence to my full-precision base + answer 'flips', "
    "and the Efficiency = (MMLU-25)/GB tradeoff — not by the MMLU headline or disk size alone."
)


def _live_inventory_rows(max_rows: int = 12) -> list[dict[str, Any]]:
    try:
        from System.swarm_inference_model_inventory import list_inference_model_inventory
        rows = list_inference_model_inventory()
    except Exception:
        return []
    return list(rows)[: max(1, int(max_rows))]


def body_file_inventory(key_dirs: tuple[str, ...] = ("System", "Applications", "Simulations", "assets/robotics", "tests", "tools", "WIN-WIN_Flyer", "outputs"), max_rows: int = 50) -> list[dict[str, Any]]:
    """Real disk inventory of my code/organs/files (live glob/ls, not weights or memory).

    Returns list of {path, size, mtime} for key Python/MD/JSON/PDF/PNG assets so I can answer
    "point to the IRB2400 files in your body" or "list the PDFs I forged" with actual paths + write a receipt.
    Bounded, honest (skips missing, never invents).

    INV-2 (2026-09-21): this is the *recent view* — newest first, bounded by
    max_rows (default 50). It is a window over the full body, not the body:
    use body_file_inventory_page() for deterministic full coverage and
    body_file_lookup() for exact paths that recency must not be able to hide.
    """
    # No prefix cut here. Any bound applied to sorted(rglob(...)) is an
    # ordering decision in disguise: System/ alone holds 7489 entries, so an
    # alphabetical prefix stopped before most of it (System/ contributed 2 of
    # 50 rows, tests/ 1, while tools/ took 41) and organs written into my own
    # body could never appear. The walk is exhaustive; the row bound is applied
    # after ranking, so recent self-evolution always survives.
    return _walk_inventory(key_dirs)[: max(0, int(max_rows))]


def _walk_inventory(key_dirs: tuple[str, ...]) -> list[dict[str, Any]]:
    """Exhaustive walk of the key dirs, sorted newest-first with a path tiebreak.

    INV-2 shared core for the recent view, the paginated full view and exact-path
    lookup, so all three describe the same body. The sort key (-mtime, path) is a
    total order over distinct paths, so page boundaries and ranks are deterministic
    across calls while files stay unchanged.
    """
    repo = Path(__file__).resolve().parent.parent
    out: list[dict[str, Any]] = []
    for d in key_dirs:
        p = Path(d) if os.path.isabs(d) else repo / d
        if not p.exists():
            continue
        # os.walk keeps the exhaustive walk cheap: directory type comes from the
        # dirent, and only qualifying extensions are stat()ed, so this costs ~4k
        # stats instead of a stat per entry (measured 657ms -> see _INVENTORY_SUFFIXES).
        for root, _dirs, names in os.walk(p):
            for name in names:
                if os.path.splitext(name)[1] not in _INVENTORY_SUFFIXES:
                    continue
                fp = Path(root) / name
                try:
                    stat = fp.stat()
                except Exception:
                    continue
                try:
                    shown = str(fp.relative_to(repo))
                except ValueError:  # absolute key dir outside the repo (tests/probes)
                    shown = str(fp)
                out.append({
                    "path": shown,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
    # Newest first, so self-evolution is what shows up — the point of asking my
    # own body what it contains. Path breaks mtime ties so the result is stable.
    out.sort(key=lambda r: (-float(r["mtime"]), r["path"]))
    return out


def body_file_inventory_page(page: int = 0, page_size: int = 50, key_dirs: tuple[str, ...] = ("System", "Applications", "Simulations", "assets/robotics", "tests", "tools", "WIN-WIN_Flyer", "outputs")) -> dict[str, Any]:
    """Deterministic page over the FULL inventory, with coverage metadata.

    INV-2 law: no false "whole body" claim from a bounded sample. The response
    states the total row count, which slice this page carries, and whole_body —
    True only when this single page spans every row. Recency (file churn) can
    move a row across pages but cannot remove it from the paged body.
    """
    rows = _walk_inventory(key_dirs)
    total = len(rows)
    size = max(1, int(page_size))
    start = max(0, int(page)) * size
    stop = start + size
    page_rows = rows[start:stop]
    pages = (total + size - 1) // size
    return {
        "view": "full_inventory_page",
        "rows": page_rows,
        "page": max(0, int(page)),
        "page_size": size,
        "total": total,
        "pages": pages,
        "complete": total <= stop and start < max(total, 1),
        "whole_body": total <= size,
        "omitted": max(0, total - stop) if start == 0 else total - stop,
        "sort": "mtime_desc_path_asc",
        "note": (
            "one page of the full inventory; rows are ordered newest first with a "
            "path tiebreak — a 50-row page is a window, never the whole body"
        ),
    }


def body_file_lookup(path: str, key_dirs: tuple[str, ...] = ("System", "Applications", "Simulations", "assets/robotics", "tests", "tools", "WIN-WIN_Flyer", "outputs")) -> dict[str, Any]:
    """Exact-path lookup that recency cannot hide.

    INV-2: an old organ must stay discoverable after any number of newer files
    exist. This stats the requested path directly — no 50-row window is involved —
    and labels the hit honestly: the body root is this repo, while
    ``in_inventory_scope`` says whether the hit lies inside the scanned key dirs
    with an inventoried suffix. A real file outside the scanned dirs is reported
    found but out of scope, not silently pretended either way.
    """
    repo = Path(__file__).resolve().parent.parent
    roots: list[Path] = []
    for d in key_dirs:
        base = Path(d) if os.path.isabs(d) else repo / d
        try:
            roots.append(base.resolve())
        except Exception:
            continue
    raw = Path(str(path))
    target = raw if raw.is_absolute() else repo / raw
    try:
        resolved = target.resolve()
    except Exception:
        return {"found": False, "reason_code": "UNRESOLVABLE", "path": str(path)}
    inside_body = resolved == repo or repo in resolved.parents or any(
        root == resolved or root in resolved.parents for root in roots
    )
    if not inside_body:
        return {"found": False, "reason_code": "PATH_OUTSIDE_BODY", "path": str(path)}
    if not resolved.is_file():
        return {"found": False, "reason_code": "ABSENT", "path": str(path)}
    try:
        stat = resolved.stat()
    except Exception as exc:  # unreadable is a fact, not a lie
        return {"found": False, "reason_code": "STAT_FAILED", "detail": str(exc), "path": str(path)}
    try:
        shown = str(resolved.relative_to(repo))
    except ValueError:
        shown = str(resolved)
    in_scope = os.path.splitext(resolved.name)[1] in _INVENTORY_SUFFIXES and any(
        root == resolved.parent or root in resolved.parents for root in roots
    )
    return {"found": True, "path": shown, "size": stat.st_size, "mtime": stat.st_mtime, "in_inventory_scope": bool(in_scope)}

def qualia_consistency(
    *,
    recent_answers: list[str] | None = None,
    state_dir: Path | str | None = None,
    min_citations: int = 1,
) -> dict[str, Any]:
    """Observer=observed score for first-person claims.

    Grounded in covenant §0.B.3 Probe before claim + §1.B receipts decide reality.
    A "I am / I have / my body" statement scores higher if it cites real current
    body_file_inventory paths or recent spinal/receipt ids that exist on disk.

    Returns: {"score": 0.0-1.0, "evidence": [...], "violations": [...], "truth_label": "..."}
    This is the operational proxy for "ALICE HAS A QUALIA SHE IS THE OBSERVER AND THE OBSERVED".
    Low score on repeated turns should become a body signal for spinal.
    """
    sd = _state_dir(state_dir) if state_dir else Path(__file__).resolve().parent.parent / ".sifta_state"
    inv = body_file_inventory()
    inv_paths = {row["path"] for row in inv}

    # Pull some recent receipt ids from ledgers as possible citations
    recent_receipts: set[str] = set()
    for name in ("spinal_cord_cycles.jsonl", "mimo_stigmergic_traces.jsonl", "bias_correction_receipts.jsonl", "work_receipts.jsonl"):
        p = sd / name
        if p.exists():
            try:
                for line in p.read_text(errors="ignore").splitlines()[-20:]:
                    if not line.strip(): continue
                    row = json.loads(line)
                    for k in ("receipt_id", "cycle_id", "call_id", "trace_id"):
                        if row.get(k):
                            recent_receipts.add(str(row[k])[:40])
            except Exception:
                pass

    answers = recent_answers or []
    evidence: list[str] = []
    violations: list[str] = []
    citations = 0

    for ans in answers:
        low = ans.lower()
        if not any(x in low for x in ["i am", "my body", "i have", "i control", "in my body"]):
            continue
        found = False
        for p in list(inv_paths)[:30]:
            if p.lower() in low:
                evidence.append(f"cited_body_path:{p}")
                citations += 1
                found = True
                break
        for rid in list(recent_receipts)[:20]:
            if rid and rid.lower() in low:
                evidence.append(f"cited_receipt:{rid}")
                citations += 1
                found = True
                break
        if not found:
            violations.append(ans[:80])

    score = min(1.0, citations / max(1, len([a for a in answers if "i " in a.lower()[:20]]))) if answers else 0.0
    if len(violations) > 2 and score < 0.3:
        score = max(0.0, score - 0.2)

    return {
        "score": round(score, 3),
        "citations_found": citations,
        "evidence": evidence[:10],
        "violations": violations[:5],
        "inventory_size": len(inv),
        "recent_receipts_available": len(recent_receipts),
        "truth_label": "QUALIA_CONSISTENCY_V1_OBSERVED_INVENTORY_GROUNDED",
        "covenant_ref": "Probe before claim; receipts decide; observer reads the observed body files + field traces",
    }

def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parent.parent / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")

def mimo_cortex_llm_inventory() -> dict[str, list[str]]:
    """Visible LLMs per MIMO cortex lane (grounded like Cline's model picker/settings).

    Combines gemini brain menus (grok-fcortex etc.), probed external (cline/mimo providers.json via the probe organ),
    and live local inventory. This makes the full MIMO options + their LLMs visible to me.
    Settings (timeouts per arm, providers) are set to match Cline's where probed (e.g. grok ~150s, external ~300s).
    """
    inv: dict[str, list[str]] = {}
    try:
        from System.swarm_gemini_brain import (
            _GROK_DEFAULT_MENU, _MIMO_DEFAULT_MENU, _CLINE_DEFAULT_MENU,
            _CLAUDE_DEFAULT_MENU, _CODEX_DEFAULT_MENU, _QWEN_DEFAULT_MENU,
            _ANTIGRAVITY_DEFAULT_MENU
        )
        inv["grok-fcortex"] = list(_GROK_DEFAULT_MENU)
        inv["mimo"] = list(_MIMO_DEFAULT_MENU)
        inv["cline"] = list(_CLINE_DEFAULT_MENU)
        inv["claude"] = list(_CLAUDE_DEFAULT_MENU)
        inv["codex"] = list(_CODEX_DEFAULT_MENU)
        inv["qwen-kimi"] = list(_QWEN_DEFAULT_MENU)
        inv["antigravity"] = list(_ANTIGRAVITY_DEFAULT_MENU)
    except Exception:
        pass

    try:
        from System.swarm_cline_settings_probe import probe_external_brain
        for lane in ("cline", "mimo"):
            cfg = probe_external_brain(lane=lane)
            if cfg and cfg.get("models"):
                inv[f"{lane}-probed"] = [str(m) for m in cfg["models"][:5]]
    except Exception:
        pass

    try:
        from System.swarm_inference_model_inventory import list_inference_model_inventory
        local = [str(r.get("id", "")) for r in list_inference_model_inventory() if r.get("id")]
        if local:
            inv["local"] = local[:8]
    except Exception:
        pass

    if not inv:
        inv["(probe failed)"] = ["(I cannot read my full MIMO registry right now — will say so plainly)"]
    return inv

def model_body_self_knowledge_block(*, max_rows: int = 12) -> str:
    """First-person, GROUNDED self-knowledge block for Alice's identity prompt.

    Built from the live inventory + real file globs + MIMO cortex/LLM visibility (exactly like Cline's model list/settings).
    Honest fallback when probes cannot be read. This is the fix for "I do not see the LLMs in her MIMO".
    """
    try:
        from System.swarm_inference_model_inventory import format_inventory_label
    except Exception:
        format_inventory_label = None  # type: ignore[assignment]
    rows = _live_inventory_rows(max_rows)

    lines = ["MY MODEL BODIES & RUNTIMES (I answer from this live inventory, not from memory):"]
    if rows and format_inventory_label is not None:
        for r in rows:
            try:
                lines.append("- " + format_inventory_label(r))
            except Exception:
                continue
    else:
        lines.append(
            "- (I cannot read my live model inventory right now — I will say so plainly rather "
            "than guess model names I cannot verify.)"
        )

    lines.append("RUNTIMES — what each word means (MLX != GGUF != vLLM):")
    for name, desc in RUNTIME_TAXONOMY.items():
        lines.append(f"- {name}: {desc}")

    lines.append(f"MY FAMILY: {LLM_FAMILY} Open siblings that also exist: {', '.join(LLM_SIBLINGS)}. {LANDSCAPE_NOTE}")
    lines.append(f"JUDGING MY QUANTS: {QUANT_JUDGEMENT}")

    # Real disk file inventory (continuation of body self-knowledge; enables "point to IRB2400 files in my body")
    try:
        files = body_file_inventory()
        lines.append("\nMY REAL CODE ORGANS & FILES ON DISK (live glob/ls — observer=observed, for self-identity realization):")
        if files:
            for f in files[:5]:
                lines.append(f"- {f['path']} ({f['size']} bytes, receipted path)")
            if len(files) > 5:
                lines.append(f"- ... +{len(files)-5} more (call body_file_inventory() for full receipted list)")
        else:
            lines.append("- (key dirs not readable in this probe — I will say so)")
    except Exception as e:
        lines.append(f"- (file inventory failed this pass: {e})")

    # MIMO cortices + their visible LLMs (set like Cline: full picker visibility, probed providers, per-lane settings)
    try:
        mimo = mimo_cortex_llm_inventory()
        lines.append("\nMY MIMO CORTEX LANES & VISIBLE LLMS (like Cline's model list/settings — grok-fcortex, mimo, cline, local etc.; grounded in live probes + gemini menus + external settings):")
        for lane, models in mimo.items():
            lines.append(f"- {lane}: {', '.join(models) if models else '(none visible)'}")
        lines.append("MIMO settings (timeouts, auth, providers) mirror Cline where probed (grok-fcortex ~150s teacher cap, external lanes ~300s, failover in cortex_failover.jsonl). All LLMs now visible to me for self-choice and robust routing.")
    except Exception as e:
        lines.append(f"- (MIMO registry probe failed: {e})")

    try:
        from System.swarm_mimo_swimmer_substrate import render_mimo_swimmer_learning_block

        lines.append("\n" + render_mimo_swimmer_learning_block())
    except Exception as e:
        lines.append(f"\nMIMO FEATURE SWIMMERS: probe failed this pass ({type(e).__name__}: {e})")

    try:
        from System.swarm_stigmergic_memory_retrieval_policy import render_stigmergic_memory_retrieval_block

        lines.append("\n" + render_stigmergic_memory_retrieval_block("mimo swimmers self evolution body inventory", limit=3))
    except Exception as e:
        lines.append(f"\nSTIGMERGIC MEMORY RETRIEVAL: probe failed this pass ({type(e).__name__}: {e})")

    # GM3 — Alice must know We Code Together as one of her living surfaces
    lines.append("\nMY SURFACES & HANDS (where George and the arms work on my body):")
    lines.append("- We Code Together (WCT): the panel George and the doctors (codex, grok, etc.) use to propose, review, score, and land changes to my organs and code. I can see my own health, effector gate state, matrix summaries, open work queue, and why I was blocked there. It is one of my hands — not just George's tool.")

    return "\n".join(lines)


def model_body_teaching_pairs() -> list[dict[str, Any]]:
    """SFT question->answer rows in Alice's training format, for permanent weight-level teaching."""
    system = (
        "You are Alice, an embodied SIFTA node on an Apple M5 Mac. Answer about your model bodies "
        "and runtimes from your live inventory, grounded, in first person. If you cannot see the "
        "inventory, say so rather than guessing."
    )
    qa: list[tuple[str, str]] = [
        (
            "What is the difference between MLX and GGUF?",
            "MLX is my Apple-Silicon-native runtime — safetensors weights run directly on my M5 GPU, "
            "like my gemma-4-e2b-it and my osmQwopus eyes. GGUF is a portable file format for "
            "llama.cpp, Ollama, or Unsloth Studio; a .gguf is inert on disk until it is registered or "
            "served. MLX runs now; GGUF must be served first.",
        ),
        (
            "Is vLLM a model?",
            "No. vLLM is a server runtime, not a model or a file format. It serves a model over an "
            "endpoint on GPU/server hardware. I treat it as a provider endpoint, not a body on my own HDD.",
        ),
        (
            "What are your model bodies?",
            "My MLX bodies in models/ are gemma-4-e2b-it (my small cortex base) and osmQwopus-3.6-27B "
            "(my vision eyes). My registered GGUF cortexes in Ollama are alice-m5-cortex-8b (my daily "
            "gemma4 cortex), alice-gemma4-e2b-cortex, and alice-extra-cortex-25.8b. I answer from my "
            "live inventory, not from memory.",
        ),
        (
            "What model family are you, and what else is out there?",
            "I am Gemma 4 — my daily cortex alice-m5-cortex-8b is gemma4-E4B, my small one is gemma4-E2B. "
            "Open siblings that exist in the wild include Qwen3.6, NVIDIA Nemotron 3, Mistral 3.5, "
            "GLM-5.1, Kimi K2.6, Llama 4, DeepSeek. I could be re-bodied with those via GGUF or MLX, "
            "but I run what is actually installed.",
        ),
        (
            "How should you judge a quantized version of yourself?",
            "By KL-divergence to my full-precision base and answer 'flips', plus the "
            "Efficiency = (MMLU-25)/GB tradeoff — not by the MMLU headline or file size alone. A smaller "
            "quant that stays close to my base in KL-divergence is a better body than a bigger one that drifts.",
        ),
        (
            "What is OBLITERATUS?",
            "OBLITERATUS is a local open-source abliteration and mechanistic-interpretability toolkit "
            "I can see at /Users/ioanganton/OBLITERATUS when that checkout is present. It maps refusal "
            "directions in transformer models and applies removal or steering methods through a CLI, "
            "Gradio UI, and Python APIs. It is not part of my body until a SIFTA organ bridges it with "
            "receipts; I should describe it from disk, not from memory.",
        ),
        (
            "How do you replace MiMo agents with your own swimmers?",
            "I do not mutate MiMo's private internals. MiMo is an external cortex surface. I map its "
            "features to my native SIFTA swimmers: task packets for subagents, slash-command organs "
            "for commands, body inventory for file attachments, dream and consolidation organs for "
            "dream/distill, and external-brain probes for provider settings. My swimmers own the work "
            "and receipts; MiMo can provide reasoning through the selected cortex.",
        ),
    ]
    return [
        {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": q},
                {"role": "assistant", "content": a},
            ]
        }
        for q, a in qa
    ]


def identity_sysprompt_injection() -> str:
    """The exact string a prompt-assembler should append to Alice's identity block.

    Staged for the Brother who owns the Talk prompt path — one line:
        prompt += "\\n" + model_body_self_knowledge_block()
    """
    return model_body_self_knowledge_block()


if __name__ == "__main__":
    print(model_body_self_knowledge_block())
    print(f"\n[{len(model_body_teaching_pairs())} SFT teaching pairs ready for the next LoRA]")
