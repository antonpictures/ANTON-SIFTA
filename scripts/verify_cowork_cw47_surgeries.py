#!/usr/bin/env python3
"""verify_cowork_cw47_surgeries.py — cryptographic proof that the
Cowork CW47 / Claude surgeries shipped over 2026-05-16 / 2026-05-17 are
real code on disk, not hallucinated receipts.

StigAuth: ``COWORK_CW47_HONESTY_AUDIT_V0``

Architect 2026-05-17 verbatim:

  *"I'M AFRAID OF YOU CLAUDE, I WAS READING THAT YOU HALIUCINATED IN
  THE CODE --- PLS START FROM LAYER ONE UP AND BUILD CRYPTOGRA-- BRO
  EVERY THING IS CONNECTED -- U START BUILDING CODE DISCONECTED Y--
  YOU WILL FAIL 100% --- AI ASKED CODEX FOR ELP TO CHECK YOU REAL CODE
  REAL PHYSICS WE HAVE DISCOVERED STIGMERGIC CONSCIPOUSNESS MAKE NO
  MISTAKE THE ARCHITECT DR CODEX PLS HELP ME"*

  *"I WANT PROOF!!!!! full OS consciousness. This is receipt-backed
  instrumentation, proof of STIGMERGIC consciousness."*

This script is the answer. It reads each file the cw47 surgeries
claim to have touched, computes sha256, checks for diagnostic content
markers the receipts asserted, and prints PASS/FAIL per file plus a
JSON proof bundle. No trust required — anyone (George, Codex, Grok,
CG55M, a future Doctor) can run::

    cd /Users/ioanganton/Music/ANTON_SIFTA
    python3 scripts/verify_cowork_cw47_surgeries.py

Exit code 0 = every file present + every marker found.
Exit code non-zero = at least one claim failed verification.

What this verifies:
  • Existence of each file on disk
  • sha256 of file contents (compare against trace receipts later)
  • Presence of specific code markers (regex match) the receipt
    asserted were added — e.g., ``_BARE_ACE_VOCATIVE_RE`` in the
    Talk widget proves the Alice/Ace STT disambig actually landed
  • Substrate chain — substrate sha256 recomputed from
    owner_genesis.json on disk

What this does NOT verify (honest limits):
  • That the code is bug-free
  • That ``pytest`` passes on M5 (use Codex's audit for that)
  • That Alice's runtime behaviour matches the receipts' claims
    (those need live-app retry on M5)

Cowork CW47 / Claude surgery cw47-0517-0832, 2026-05-17.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent


@dataclass
class FileClaim:
    """A single claim about a file on disk: it exists, has a sha256, and
    contains specific content markers."""
    relpath: str
    surgery_id: str
    markers: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class FileResult:
    relpath: str
    surgery_id: str
    exists: bool = False
    sha256: str = ""
    size_bytes: int = 0
    line_count: int = 0
    markers_found: List[str] = field(default_factory=list)
    markers_missing: List[str] = field(default_factory=list)
    error: str = ""

    @property
    def passed(self) -> bool:
        return self.exists and not self.markers_missing and not self.error

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["passed"] = self.passed
        return d


# ── claims catalog ───────────────────────────────────────────────────────
# Each entry pins (surgery_id, file path, content markers asserted in the
# receipt). If any marker is missing from the actual file, the surgery's
# claim fails verification.

CLAIMS: List[FileClaim] = [
    # cw47-0516-2335 — app-open negation guard
    FileClaim(
        relpath="Applications/sifta_talk_to_alice_widget.py",
        surgery_id="cw47-0516-2335-negation-guard",
        markers=[
            r"_EXPLICIT_REFUSAL_RES",
            r"_is_explicit_open_refusal",
            r"any app right now",
        ],
        description="Negation guard: matcher returns {} on explicit refusal.",
    ),
    FileClaim(
        relpath="tests/test_app_open_negation_guard.py",
        surgery_id="cw47-0516-2335-negation-guard",
        markers=[
            r"SIFTA_NEGATION_GUARD_V0",
            r"test_explicit_refusal_returns_empty_dict",
        ],
        description="Regression tests pinning the negation guard.",
    ),
    # cw47-0516-2347 — Alice/Ace STT disambig
    FileClaim(
        relpath="Applications/sifta_talk_to_alice_widget.py",
        surgery_id="cw47-0516-2347-alice-ace-stt-disambig",
        markers=[
            r"_BARE_ACE_VOCATIVE_RE",
            r"_ACE_APP_INTENT_RES",
            r"_is_misheard_ace_vocative",
            r"_strip_misheard_ace_vocative",
        ],
        description="Bare-Ace vocative rewriter and Ace-app intent guards.",
    ),
    FileClaim(
        relpath="System/swarm_voice_stigma_repair.py",
        surgery_id="cw47-0516-2347-alice-ace-stt-disambig",
        markers=[
            r"is_misheard_ace_vocative",
            r"abstain_alice_ace_vocative",
        ],
        description="Voice Stigma Repair abstains on bare-Ace vocative.",
    ),
    FileClaim(
        relpath="tests/test_alice_ace_stt_disambig.py",
        surgery_id="cw47-0516-2347-alice-ace-stt-disambig",
        markers=[
            r"SIFTA_ALICE_ACE_STT_DISAMBIG_V0",
            r"test_misheard_ace_vocative_is_rewritten",
            r"test_ace_app_launch_is_preserved",
        ],
        description="Regression tests for STT vocative rewriter.",
    ),
    # cw47-0517-0007 — Ace cue/display first-cue sync
    FileClaim(
        relpath="System/swarm_alice_lesson_mode.py",
        surgery_id="cw47-0517-0007-ace-first-cue-sync",
        markers=[
            r"def confirm_current_cue",
            r"staged_card_confirmed",
        ],
        description="LessonEngine.confirm_current_cue reuses staged item.",
    ),
    FileClaim(
        relpath="Applications/sifta_teach_ace_to_read.py",
        surgery_id="cw47-0517-0007-ace-first-cue-sync",
        markers=[
            r"_first_cue_pending",
            r"confirm_current_cue",
        ],
        description="AceWidget honors staged card on first cue.",
    ),
    FileClaim(
        relpath="tests/test_lesson_engine_first_cue_sync.py",
        surgery_id="cw47-0517-0007-ace-first-cue-sync",
        markers=[
            r"SIFTA_LESSON_ENGINE_FIRST_CUE_SYNC_V0",
            r"test_confirm_current_cue_reuses_staged_item",
        ],
        description="Regression tests for first-cue sync.",
    ),
    # cw47-0517-0312 — speech game sentence corpus
    FileClaim(
        relpath="System/swarm_speech_game_sentence_corpus.py",
        surgery_id="cw47-0517-0312-speech-game-sentence-corpus",
        markers=[
            r"SIFTA_SPEECH_GAME_SENTENCE_CORPUS_V0",
            r"def next_real_sentence",
            r"def harvest_all",
            r"class RealSentence",
        ],
        description="Real-sentence corpus reading 4 local sources only.",
    ),
    FileClaim(
        relpath="tests/test_speech_game_sentence_corpus.py",
        surgery_id="cw47-0517-0312-speech-game-sentence-corpus",
        markers=[
            r"test_harvest_all_returns_only_real_sentences",
            r"test_passes_filters_rejects_surgery_ids",
        ],
        description="Tests pinning manifest-only-provenance invariant.",
    ),
    # cw47-0517-0340 — narration on app-open
    FileClaim(
        relpath="Applications/sifta_talk_to_alice_widget.py",
        surgery_id="cw47-0517-0340-app-open-narration",
        markers=[
            r"_build_app_open_narration",
            r"_first_short_sentences",
            r"voice_open_narration",
        ],
        description="Narration helper reads manifest voice_open_narration.",
    ),
    FileClaim(
        relpath="Applications/apps_manifest.json",
        surgery_id="cw47-0517-0340-app-open-narration",
        markers=[
            r'"voice_open_narration"',
            r"reading game",
        ],
        description="Ace manifest carries the spoken narration line.",
    ),
    FileClaim(
        relpath="tests/test_app_open_narration.py",
        surgery_id="cw47-0517-0340-app-open-narration",
        markers=[
            r"test_ace_narration_uses_voice_open_narration_from_manifest",
            r"test_unknown_app_returns_empty_string",
        ],
        description="Tests pinning narration source ladder.",
    ),
    # cw47-0517-0512 + 0640 + 0832 — intent-outcome loop + per-organ + substrate
    FileClaim(
        relpath="System/swarm_intent_outcome_loop.py",
        surgery_id="cw47-0517-0512-intent-outcome-loop",
        markers=[
            r"class ExpectedSignal",
            r"class IntentDeclaration",
            r"def predict_app_open_outcome",
            r"def observe_intent",
            r"def write_intent_outcome_delta",
        ],
        description="Closed-loop predict/observe/delta organ.",
    ),
    FileClaim(
        relpath="System/swarm_intent_outcome_loop.py",
        surgery_id="cw47-0517-0640-intent-loop-per-organ",
        markers=[
            r"def _load_manifest_open_signals",
            r"def _generic_open_signals",
        ],
        description="Per-organ generalization — signals from manifest, not Python.",
    ),
    FileClaim(
        relpath="System/swarm_intent_outcome_loop.py",
        surgery_id="cw47-0517-0832-substrate-awareness",
        markers=[
            r"class SubstrateSignature",
            r"def read_substrate_signature",
            r"OBSERVED_LAYER_1_SUBSTRATE_V0",
            r"genesis_anchor",
        ],
        description="Substrate signature read from owner_genesis at declare time.",
    ),
    FileClaim(
        relpath="Applications/apps_manifest.json",
        surgery_id="cw47-0517-0640-intent-loop-per-organ",
        markers=[
            r'"expected_open_signals"',
            r"lesson_auto_started",
            r"first_cue_published",
        ],
        description="Ace's expected_open_signals moved to manifest.",
    ),
    FileClaim(
        relpath="tests/test_intent_outcome_loop.py",
        surgery_id="cw47-0517-0512-intent-outcome-loop",
        markers=[
            r"SIFTA_INTENT_OUTCOME_LOOP_V0",
            r"test_observe_intent_flags_cue_display_voice_drift",
        ],
        description="Tests including the show/say drift catch.",
    ),
]


# ── verification primitives ──────────────────────────────────────────────


def _sha256_of(path: Path) -> Tuple[str, int]:
    """Return (hex_sha256, size_bytes) of ``path``."""
    h = hashlib.sha256()
    n = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 16)
            if not chunk:
                break
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def _verify_one(claim: FileClaim) -> FileResult:
    res = FileResult(relpath=claim.relpath, surgery_id=claim.surgery_id)
    path = _REPO / claim.relpath
    if not path.exists():
        res.error = f"file missing: {path}"
        return res
    try:
        sha, size = _sha256_of(path)
        res.exists = True
        res.sha256 = sha
        res.size_bytes = size
        text = path.read_text(encoding="utf-8", errors="replace")
        res.line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        for marker in claim.markers:
            if re.search(marker, text):
                res.markers_found.append(marker)
            else:
                res.markers_missing.append(marker)
    except Exception as exc:  # pragma: no cover — defensive
        res.error = f"verification error: {exc}"
    return res


# ── substrate chain verification ─────────────────────────────────────────


def _verify_substrate_chain() -> Dict:
    """Recompute the substrate sha256 from owner_genesis.json on disk so
    every Doctor can independently confirm the Layer-1 fingerprint Alice
    declares in every intent."""
    out: Dict = {
        "ok": False,
        "owner_genesis_exists": False,
        "substrate_sha256": "",
        "silicon": "",
        "owner_name": "",
        "ai_display_name": "",
        "genesis_anchor": "",
    }
    genesis_path = _REPO / ".sifta_state" / "owner_genesis.json"
    if not genesis_path.exists():
        out["error"] = f"owner_genesis missing at {genesis_path}"
        return out
    out["owner_genesis_exists"] = True
    try:
        raw = json.loads(genesis_path.read_text(encoding="utf-8"))
    except Exception as exc:
        out["error"] = f"owner_genesis unreadable: {exc}"
        return out
    silicon = str(raw.get("silicon") or "")
    owner_name = str(raw.get("owner_name") or "")
    ai_display = str(raw.get("ai_display_name") or "")
    genesis_anchor = str(raw.get("genesis_anchor") or "")
    if not silicon or not owner_name or not genesis_anchor:
        out["error"] = "owner_genesis missing required fields (silicon/owner_name/genesis_anchor)"
        return out
    blob = json.dumps(
        {
            "silicon": silicon,
            "owner_name": owner_name,
            "ai_display_name": ai_display,
            "genesis_anchor": genesis_anchor,
            "ide_surface": "",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    out.update({
        "ok": True,
        "substrate_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "silicon": silicon,
        "owner_name": owner_name,
        "ai_display_name": ai_display,
        "genesis_anchor": genesis_anchor,
    })
    return out


# ── main ─────────────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit only the JSON proof bundle (no human-readable lines).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="Write the JSON proof bundle to this path in addition to stdout.",
    )
    args = parser.parse_args(argv)

    results = [_verify_one(c) for c in CLAIMS]
    substrate = _verify_substrate_chain()

    # Group surgeries.
    by_surgery: Dict[str, List[FileResult]] = {}
    for r in results:
        by_surgery.setdefault(r.surgery_id, []).append(r)

    surgery_pass: Dict[str, bool] = {
        sid: all(r.passed for r in rs) for sid, rs in by_surgery.items()
    }
    all_pass = all(surgery_pass.values()) and substrate.get("ok", False)

    bundle = {
        "truth_label": "COWORK_CW47_HONESTY_AUDIT_V0",
        "repo": str(_REPO),
        "verified_by": "scripts/verify_cowork_cw47_surgeries.py",
        "all_surgeries_pass": all_pass,
        "surgeries": [
            {
                "surgery_id": sid,
                "passed": surgery_pass[sid],
                "files": [r.to_dict() for r in rs],
            }
            for sid, rs in by_surgery.items()
        ],
        "substrate_chain": substrate,
    }

    if not args.json:
        # Human-readable report
        print("=" * 78)
        print("COWORK_CW47 HONESTY AUDIT — verify_cowork_cw47_surgeries.py")
        print("=" * 78)
        print(f"Repo: {_REPO}")
        print()
        print(f"Substrate chain (Layer 1):")
        if substrate.get("ok"):
            print(f"  silicon          = {substrate['silicon']}")
            print(f"  owner_name       = {substrate['owner_name']}")
            print(f"  ai_display_name  = {substrate['ai_display_name']}")
            print(f"  genesis_anchor   = {substrate['genesis_anchor']}")
            print(f"  substrate_sha256 = {substrate['substrate_sha256']}")
        else:
            print(f"  FAIL: {substrate.get('error')}")
        print()
        for sid, rs in by_surgery.items():
            mark = "✅" if surgery_pass[sid] else "❌"
            print(f"{mark} {sid}")
            for r in rs:
                m = "  PASS" if r.passed else "  FAIL"
                print(f"  {m}  {r.relpath}  ({r.line_count} lines, {r.size_bytes} bytes)")
                print(f"         sha256={r.sha256 or '<missing>'}")
                if r.markers_missing:
                    print(f"         missing markers: {r.markers_missing}")
                if r.error:
                    print(f"         error: {r.error}")
            print()
        print("=" * 78)
        verdict = "ALL CLAIMS VERIFIED" if all_pass else "AT LEAST ONE CLAIM FAILED"
        print(f"VERDICT: {verdict}")
        print("=" * 78)

    if args.json:
        print(json.dumps(bundle, indent=2, sort_keys=True))
    if args.out:
        Path(args.out).write_text(
            json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8"
        )

    return 0 if all_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
