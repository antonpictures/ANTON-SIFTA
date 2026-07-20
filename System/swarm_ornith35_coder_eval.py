#!/usr/bin/env python3
"""swarm_ornith35_coder_eval.py — r1623-06: Ornith 35B vs 9B vs Krishna eval scaffold.

Does not download models. Probes live ollama tags and picks best coder for SELF_CODE.

Truth label: ORNITH35_CODER_EVAL_V1
"""

from __future__ import annotations

from typing import Any

TRUTH_LABEL = "ORNITH35_CODER_EVAL_V1"

# (match_fn_needles, score) — higher = prefer for coder phase
_CODER_RANK: tuple[tuple[tuple[str, ...], int], ...] = (
    (("ornith", "35b"), 90),
    (("nightshift",), 80),
    (("qwenpaw",), 75),
    (("north-mini-code", "north-mini"), 72),
    (("ultragemma",), 70),
    (("ornith:latest",), 65),
    (("ornith",), 60),
    (("krishairnd", "gemma-4-uncensored"), 55),
)


def probe_coder_candidates() -> dict[str, Any]:
    tags: list[str] = []
    try:
        from System.sifta_inference_defaults import probe_installed_ollama_tags

        tags = [str(t) for t in (probe_installed_ollama_tags() or [])]
    except Exception as exc:
        return {
            "truth_label": TRUTH_LABEL,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "installed": [],
            "pick": "",
            "ornith_35b_present": False,
        }

    scored: list[dict[str, Any]] = []
    for tag in tags:
        low = tag.lower()
        best = 0
        for needles, score in _CODER_RANK:
            if all(n in low for n in needles):
                best = max(best, score)
            elif len(needles) == 1 and needles[0] in low:
                best = max(best, score)
        if best:
            scored.append({"tag": tag, "score": best})

    scored.sort(key=lambda r: (-int(r["score"]), r["tag"]))
    # dedupe keep first
    seen: set[str] = set()
    ranked: list[dict[str, Any]] = []
    for row in scored:
        if row["tag"] in seen:
            continue
        seen.add(row["tag"])
        ranked.append(row)

    has_35 = any("35b" in r["tag"].lower() and "ornith" in r["tag"].lower() for r in ranked)
    pick = ranked[0]["tag"] if ranked else ""
    return {
        "truth_label": TRUTH_LABEL,
        "ok": True,
        "installed": ranked,
        "pick": pick,
        "ornith_35b_present": has_35,
        "note": (
            "ornith 35B available — prefer for coder phase"
            if has_35
            else "ornith 35B not on desk — use pick for SELF_CODE"
        ),
    }


def recommended_coder_cortex() -> str:
    p = probe_coder_candidates()
    return str(p.get("pick") or "ornith:latest")


__all__ = [
    "TRUTH_LABEL",
    "probe_coder_candidates",
    "recommended_coder_cortex",
]
