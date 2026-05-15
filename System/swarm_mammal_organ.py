#!/usr/bin/env python3
"""swarm_mammal_organ.py — MAMMAL as a SIFTA tool organ.

Architect 2026-05-13 23:55: "DID WE DOWNLOAD THE MAMMAL WEIGHTS I
WANT THE LLM AS ONE OF OUR ORGANS / TOOLS"

Answer was NO. This module is the wrapper that makes pulling the
weights into Alice's body a single command — no integration work
needed afterward.

MAMMAL = ibm-research/biomed.omics.bl.sm.ma-ted-458m (458M-param
multi-modal biomedical foundation model from the IBM Research paper
the architect dropped earlier today). It is NOT a chat LLM. It is a
specialized scoring / classification / regression tool over typed
biomedical tokens (Protein / Small Molecule / Gene Expression /
Antibody) plus scalar attributes.

Right framing for SIFTA: a TOOL ORGAN, similar to the wallpaper
effector or the dream organ. The cortex-gated router decides when
to invoke it (biomedical query intent), it runs, returns a structured
result, signed receipt back to the architect or downstream organ.

Pipeline:
    cortex sees biomedical query intent
      ↓
    router fires effector='mammal_query', audience=architect
      ↓
    MammalOrgan.query(structured_prompt) → result dict
      ↓
    sha256-signed receipt to .sifta_state/mammal_organ_receipts.jsonl
      ↓
    minimal grounded reply to the architect

This file is the SCAFFOLD. The model is loaded lazily — if weights
are not present on disk, `query()` returns a clear error explaining
exactly how to pull them. No silent fakes, no fabricated outputs.
Per §7.12 Probe-Before-Claim: we don't pretend results when the
model isn't there.

Truth class: OPERATIONAL for the wrapper, but HYPOTHESIS for any
biomedical output once the model IS loaded (because biomedical
predictions are HYPOTHESIS until validated wet-lab).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Canonical model identifier per IBM Research paper figure.
DEFAULT_MODEL_ID = "ibm-research/biomed.omics.bl.sm.ma-ted-458m"
DEFAULT_REVISION = "main"

TRUTH_LABEL_ORGAN = "MAMMAL_ORGAN_V1"
TRUTH_LABEL_QUERY = "MAMMAL_QUERY_RESULT_V1"
LEDGER_NAME = "mammal_organ_receipts.jsonl"

TRUTH_BOUNDARY = (
    "MAMMAL (IBM biomed.omics.bl.sm.ma-ted-458m) is a multi-modal "
    "biomedical foundation model — NOT a chat LLM and NOT a finished "
    "medical authority. Its outputs are HYPOTHESIS until validated "
    "by wet-lab or independent receipts. This wrapper is OPERATIONAL "
    "scaffolding; the model's predictions inherit HYPOTHESIS class. "
    "No claim about reproducing ATLAS/CMS or beating CERN (§20.F)."
)


# ──────────────────────────────────────────────────────────────────────
# Weight discovery — honest answer to "do we have the model?"
# ──────────────────────────────────────────────────────────────────────

def _hf_cache_root() -> Path:
    """Honor HF_HOME / TRANSFORMERS_CACHE / default ~/.cache/huggingface."""
    if "HF_HOME" in os.environ:
        return Path(os.environ["HF_HOME"])
    if "TRANSFORMERS_CACHE" in os.environ:
        return Path(os.environ["TRANSFORMERS_CACHE"]).parent
    return Path.home() / ".cache" / "huggingface"


def find_mammal_weights(
    *,
    model_id: str = DEFAULT_MODEL_ID,
    extra_paths: Optional[list[str | Path]] = None,
) -> dict[str, Any]:
    """Probe the filesystem for MAMMAL weights. Returns a dict with
    `present` (bool), `location` (path or None), and `evidence`
    (list of file paths found).

    Probes:
      1. HuggingFace hub cache (`~/.cache/huggingface/hub/models--ibm-research--...`)
      2. _REPO/models/<model_id>
      3. _REPO/weights/<model_id>
      4. Any extra_paths passed in
    """
    org, _, name = model_id.partition("/")
    if not name:
        name, org = org, ""
    hf_name_dir = f"models--{org}--{name}".replace("/", "--")
    candidates: list[Path] = []
    # SIFTA-local body storage. Codex's weight manager downloads/proves here.
    candidates.append(_STATE / "mammal_weights" / name)
    # HF cache
    candidates.append(_hf_cache_root() / "hub" / hf_name_dir)
    # Local repo conventions
    candidates.append(_REPO / "models" / model_id)
    candidates.append(_REPO / "models" / name)
    candidates.append(_REPO / "weights" / model_id)
    candidates.append(_REPO / "weights" / name)
    if extra_paths:
        candidates.extend(Path(p) for p in extra_paths)
    evidence: list[str] = []
    located: Optional[Path] = None
    for cand in candidates:
        if not cand.exists():
            continue
        # Real weights look like *.safetensors / *.bin / *.gguf / config.json
        files = list(cand.rglob("*.safetensors")) + list(cand.rglob("*.bin")) + \
                list(cand.rglob("config.json"))
        if files:
            located = cand
            evidence = [str(f) for f in files[:5]]
            break
    return {
        "model_id": model_id,
        "present": located is not None,
        "location": str(located) if located else None,
        "candidate_paths_probed": [str(c) for c in candidates],
        "evidence_files": evidence,
        "hf_cache_root": str(_hf_cache_root()),
    }


def pull_instructions(model_id: str = DEFAULT_MODEL_ID) -> str:
    """Return the exact commands the architect should run on his Mac
    to pull MAMMAL into a local cache the wrapper can find."""
    return (
        f"# Run these on YOUR Mac terminal (NOT inside this sandbox).\n"
        f"# 1. Ensure transformers + huggingface_hub are installed:\n"
        f"#    pip3 install --upgrade transformers huggingface_hub\n"
        f"# 2. Pull the weights to the default HF cache (~/.cache/huggingface/hub):\n"
        f"#    huggingface-cli download {model_id}\n"
        f"#    (If huggingface-cli is unavailable: python3 -c \""
        f"from huggingface_hub import snapshot_download; "
        f"snapshot_download('{model_id}')\")\n"
        f"# 3. Verify with: python3 -m System.swarm_mammal_organ --probe\n"
        f"#\n"
        f"# Disk: ~1-2 GB for fp16. You have 129 GB free.\n"
        f"# Note: this model is gated on Hugging Face. If you get a 403, run:\n"
        f"#    huggingface-cli login\n"
        f"# and accept the model license at:\n"
        f"#    https://huggingface.co/{model_id}\n"
    )


# ──────────────────────────────────────────────────────────────────────
# MammalOrgan — lazy-loading wrapper
# ──────────────────────────────────────────────────────────────────────

@dataclass
class MammalQueryResult:
    """Result of one MAMMAL query, with truth-class qualifiers."""
    ok: bool
    truth_label: str
    truth_class: str  # HYPOTHESIS by default for biomedical outputs
    prompt_summary: str
    output: Any  # raw model output — type depends on task
    sha256: str
    receipt_id: str
    error: Optional[str] = None
    weights_present: Optional[bool] = None
    pull_instructions: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MammalOrgan:
    """SIFTA organ wrapping the IBM MAMMAL biomedical foundation model.

    Lazy-loads on first `query()` call. Returns a clean error if
    weights are not present; no silent fakes.

    Usage:
        organ = MammalOrgan()
        result = organ.query({"protein": "MKTAYIA...", "task": "tcr_bind"})
        # result.ok == True if model loaded and ran
        # result.truth_class == "HYPOTHESIS"
        # result.sha256 / receipt_id for ledger
    """

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_MODEL_ID,
        revision: str = DEFAULT_REVISION,
        device: str = "cpu",
        state_root: str | Path | None = None,
    ) -> None:
        self.model_id = model_id
        self.revision = revision
        self.device = device
        self.state_root = Path(state_root) if state_root else _STATE
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._load_error: Optional[str] = None
        # Statistics
        self.queries_served = 0
        self.queries_failed = 0
        self.first_query_ts: Optional[float] = None
        self.last_query_ts: Optional[float] = None

    # ── State ──────────────────────────────────────────────────

    def weights_present(self) -> bool:
        """Cheap check — does the filesystem have the weights?"""
        return find_mammal_weights(model_id=self.model_id)["present"]

    def status(self) -> dict[str, Any]:
        """Receipt-friendly status snapshot."""
        probe = find_mammal_weights(model_id=self.model_id)
        return {
            "truth_label": TRUTH_LABEL_ORGAN,
            "model_id": self.model_id,
            "weights_present": probe["present"],
            "weights_location": probe["location"],
            "loaded": self._loaded,
            "load_error": self._load_error,
            "queries_served": self.queries_served,
            "queries_failed": self.queries_failed,
            "first_query_ts": self.first_query_ts,
            "last_query_ts": self.last_query_ts,
            "device": self.device,
            "pull_instructions": (
                None if probe["present"] else pull_instructions(self.model_id)
            ),
        }

    # ── Load ───────────────────────────────────────────────────

    def load(self) -> bool:
        """Attempt to load the model. Returns True on success."""
        if self._loaded:
            return True
        probe = find_mammal_weights(model_id=self.model_id)
        if not probe["present"]:
            self._load_error = (
                f"MAMMAL weights not found at {probe['hf_cache_root']} "
                f"or repo models/. Pull instructions:\n{pull_instructions(self.model_id)}"
            )
            return False
        try:
            from transformers import AutoModel, AutoTokenizer  # type: ignore
        except ImportError:
            self._load_error = (
                "transformers library not installed. Run "
                "`pip3 install transformers` on your Mac terminal."
            )
            return False
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, revision=self.revision, trust_remote_code=False,
            )
            self._model = AutoModel.from_pretrained(
                self.model_id, revision=self.revision, trust_remote_code=False,
            )
            if hasattr(self._model, "to"):
                self._model = self._model.to(self.device)
            self._loaded = True
            self._load_error = None
            return True
        except Exception as e:  # noqa: BLE001
            self._load_error = f"{type(e).__name__}: {e}"
            return False

    # ── Query ──────────────────────────────────────────────────

    def query(self, prompt: Any) -> MammalQueryResult:
        """Run one query through MAMMAL. Returns MammalQueryResult.

        `prompt` is whatever the task needs — for a tokenized
        biomedical prompt, pass a dict {protein, small_molecule, ...}
        per the paper's Structured Universal Prompt convention.
        """
        now = time.time()
        if self.first_query_ts is None:
            self.first_query_ts = now
        self.last_query_ts = now
        prompt_summary = self._summarize_prompt(prompt)

        if not self._loaded:
            ok = self.load()
            if not ok:
                self.queries_failed += 1
                payload = {
                    "prompt_summary": prompt_summary,
                    "error": self._load_error,
                    "weights_present": self.weights_present(),
                }
                return self._make_result(
                    ok=False,
                    output=None,
                    prompt_summary=prompt_summary,
                    error=self._load_error,
                    payload=payload,
                )

        # Model is loaded — run the forward pass.
        try:
            output = self._run_forward(prompt)
            self.queries_served += 1
            payload = {
                "prompt_summary": prompt_summary,
                "output": output,
            }
            return self._make_result(
                ok=True,
                output=output,
                prompt_summary=prompt_summary,
                payload=payload,
            )
        except Exception as e:  # noqa: BLE001
            self.queries_failed += 1
            err = f"{type(e).__name__}: {e}"
            payload = {"prompt_summary": prompt_summary, "error": err}
            return self._make_result(
                ok=False, output=None,
                prompt_summary=prompt_summary, error=err, payload=payload,
            )

    # ── Internals ─────────────────────────────────────────────

    def _run_forward(self, prompt: Any) -> Any:
        """Subclass / monkeypatch point. Default: tokenize text and
        return the last-hidden-state mean as a numpy array."""
        if isinstance(prompt, str):
            text = prompt
        elif isinstance(prompt, dict):
            # Concatenate the prompt dict's text-valued fields.
            text = " | ".join(f"{k}={v}" for k, v in prompt.items()
                              if isinstance(v, str))
        else:
            text = str(prompt)
        if not text:
            text = "[empty]"
        tokens = self._tokenizer(text, return_tensors="pt", truncation=True)
        if hasattr(tokens, "to"):
            tokens = tokens.to(self.device)
        out = self._model(**tokens)
        # Try last_hidden_state first; fall back to pooler_output or logits
        if hasattr(out, "last_hidden_state"):
            v = out.last_hidden_state.mean(dim=1).detach().cpu().numpy()
        elif hasattr(out, "pooler_output"):
            v = out.pooler_output.detach().cpu().numpy()
        elif hasattr(out, "logits"):
            v = out.logits.detach().cpu().numpy()
        else:
            v = [str(out)[:200]]
        return {
            "kind": "EMBEDDING",
            "shape": list(getattr(v, "shape", [len(v)])),
            "first_8_dims": [float(x) for x in (v.flatten()[:8] if hasattr(v, "flatten") else v[:8])],
        }

    def _summarize_prompt(self, prompt: Any) -> str:
        if isinstance(prompt, str):
            return prompt[:120]
        if isinstance(prompt, dict):
            keys = ",".join(sorted(prompt.keys()))
            return f"dict({keys})"
        return f"{type(prompt).__name__}({str(prompt)[:60]})"

    def _make_result(
        self, *, ok: bool, output: Any, prompt_summary: str,
        error: Optional[str] = None, payload: Optional[dict] = None,
    ) -> MammalQueryResult:
        body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"),
                          default=str)
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        rid = uuid.uuid4().hex[:16]
        result = MammalQueryResult(
            ok=ok,
            truth_label=TRUTH_LABEL_QUERY,
            truth_class="HYPOTHESIS",
            prompt_summary=prompt_summary,
            output=output,
            sha256=sha,
            receipt_id=rid,
            error=error,
            weights_present=self.weights_present(),
            pull_instructions=(None if ok else pull_instructions(self.model_id)),
        )
        # Write receipt unconditionally — both successes and failures
        # leave evidence in the ledger.
        self._write_receipt(result)
        return result

    def _write_receipt(self, result: MammalQueryResult) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "kind": "MAMMAL_QUERY",
            "trace_id": str(uuid.uuid4()),
            "truth_label": TRUTH_LABEL_QUERY,
            "truth_class": "HYPOTHESIS",
            "truth_boundary": TRUTH_BOUNDARY,
            "sha256": result.sha256,
            "receipt_id": result.receipt_id,
            "ok": result.ok,
            "model_id": self.model_id,
            "prompt_summary": result.prompt_summary,
            "error": result.error,
            "weights_present": result.weights_present,
        }
        with (self.state_root / LEDGER_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probe", action="store_true",
                   help="Check whether MAMMAL weights are on disk")
    p.add_argument("--query", type=str, default="",
                   help="Run a single query string through MAMMAL")
    p.add_argument("--model-id", type=str, default=DEFAULT_MODEL_ID)
    args = p.parse_args()
    if args.probe or not args.query:
        probe = find_mammal_weights(model_id=args.model_id)
        print(json.dumps(probe, indent=2))
        if not probe["present"]:
            print()
            print(pull_instructions(args.model_id))
    if args.query:
        organ = MammalOrgan(model_id=args.model_id)
        result = organ.query(args.query)
        print(json.dumps(result.to_dict(), indent=2, default=str))
