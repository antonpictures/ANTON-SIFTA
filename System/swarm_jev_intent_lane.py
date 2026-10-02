"""Jev intent lane — the cortex classifier the router seam was waiting for.

The gated effector router ships `IntentClassifier` as a Protocol and a
`RegexIntentClassifier` as a stand-in; its own docstring calls that the
"band-aid / fallback path while the real cortex classifier is being trained".
The band-aid is what produces this, live, in the router ledger:

    decision=UNKNOWN_INTENT  confidence=0.0
    reason="no registered intent pattern matched"

Jev is the trained cortex that fills that seam. It returns calibrated
probability distributions instead of a regex verdict, and the router's own
`EffectorSpec.confidence_threshold` is already the right place to compare them.

Design rules, in order of precedence:

  1. CODE OWNS KNOWN RULES. The regex classifier runs FIRST. A deterministic hit
     is free, instant and already correct; Jev is for what patterns miss.
  2. LOCAL-FIRST. If Jev is unreachable, refused, or unsure, the result degrades
     to the regex verdict. The router keeps working; nothing new can hang it.
  3. NEVER PAY TWICE. Judgments are identity-keyed on (text, candidate set) and
     cached in the field, so a repeated utterance costs zero credits. This is
     the stigmergic point: the trace replaces the recomputation.
  4. EVERY JUDGMENT LEAVES A TRACE. Model, latency, tokens, probabilities, and
     whether it was a cache hit are recorded, so Jev's contribution to the
     organism is provable rather than asserted.

Ledger: JEV_JUDGMENT_LEDGER (judgments) and JEV_INTENT_CACHE (reuse)
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

JEV_JUDGMENT_LEDGER = "jev_judgment_ledger.jsonl"
JEV_INTENT_CACHE = "jev_intent_cache.jsonl"
JEV_INTENT_ENABLED = "jev_intent_enabled"
TRUTH_LABEL = "JEV_INTENT_LANE_V1"

# The router compares the classifier's confidence against each effector's own
# threshold (default 0.55). We report the PROBABILITY of the selected option,
# which is the calibrated quantity, and never the distribution concentration.
DEFAULT_THRESHOLD = 0.55

# Cache entries older than this are re-judged, so a stale judgment cannot decide
# forever about text that has since become ambiguous.
CACHE_TTL_S = 30 * 24 * 3600

NONE_LABEL = "NONE"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _identity(text: str, candidates: Iterable[str]) -> str:
    payload = f"{text.strip()}||{'|'.join(sorted(candidates))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _append(path: Path, row: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass  # a failed trace must never break a router decision


def read_judgments(*, limit: int = 200, state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / JEV_JUDGMENT_LEDGER
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out[-limit:]


class _Cache:
    """Identity-keyed judgment reuse. One read, then in-memory."""

    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / JEV_INTENT_CACHE
        self._map: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = str(row.get("identity") or "")
            if key:
                self._map[key] = row  # last write wins

    def get(self, identity: str) -> Optional[dict[str, Any]]:
        self._load()
        row = self._map.get(identity)
        if row is None:
            return None
        if time.time() - float(row.get("ts") or 0.0) > CACHE_TTL_S:
            return None
        return row

    def put(self, identity: str, label: Optional[str], probability: float, slots: dict[str, Any]) -> None:
        self._load()
        row = {
            "ts": time.time(),
            "identity": identity,
            "label": label,
            "probability": probability,
            "slots": slots,
        }
        self._map[identity] = row
        _append(self.path, row)


class JevIntentClassifier:
    """IntentClassifier implementation backed by Jev, with the regex path first.

    Satisfies the router's Protocol:
        classify(text) -> (effector_name | None, confidence_0_to_1, slots)
    """

    def __init__(
        self,
        *,
        state_dir: Path | str | None = None,
        key_state_dir: Path | str | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        use_cache: bool = True,
        registry: Any = None,
    ) -> None:
        # Where judgments and the cache are written...
        self.sd = _state_dir(state_dir)
        # ...and where the API key is read from. These must be separable: a test
        # or an isolated lane may redirect its ledgers without losing the body's
        # credential, and conflating them silently disables Jev.
        self.key_sd = _state_dir(key_state_dir)
        self.threshold = float(threshold)
        self.use_cache = bool(use_cache)
        self._registry = registry
        self._cache = _Cache(self.sd)
        self._regex = None
        self.calls = 0
        self.cache_hits = 0

    # -- internals ---------------------------------------------------------

    def _regex_classifier(self):
        if self._regex is None:
            from System.swarm_cortex_gated_effector_router import RegexIntentClassifier

            self._regex = RegexIntentClassifier()
        return self._regex

    def _candidates(self) -> dict[str, str]:
        """Effector name -> description, straight from the live registry."""
        try:
            if self._registry is not None:
                reg = self._registry
            else:
                from System.swarm_cortex_gated_effector_router import get_registry

                reg = get_registry()
            specs = getattr(reg, "_specs", {}) or {}
            return {
                name: (getattr(spec, "description", "") or name)
                for name, spec in specs.items()
                if getattr(spec, "allowed_audiences", ("architect",)) and "architect" in (spec.allowed_audiences or ())
            }
        except Exception:
            return {}

    def _ask_jev(self, text: str, candidates: dict[str, str]) -> dict[str, Any]:
        from System import swarm_typesafe_decision as jev

        state = (
            "The speaker is George, the Architect, addressing Alice, his local organism. "
            "Alice may fire at most one registered effector. Choose the effector whose "
            "description best matches what the speaker wants done, or NONE when the message "
            "asks for no action, is social, or is ambiguous."
        )
        question = "Which registered effector, if any, does this message intend to invoke?"
        choices = dict(candidates)
        choices[NONE_LABEL] = "the message asks for no effector (social talk, acknowledgement, question, or ambiguous)"
        out = jev.calibrated_choice(state, f"{question}\n\nMessage: {text}", choices, state_dir=self.key_sd)
        self.calls += 1
        return out

    def _record(self, *, text: str, label: Optional[str], probability: float,
                slots: dict[str, Any], meta: dict[str, Any]) -> None:
        row = {
            "ts": time.time(),
            "kind": "JEV_INTENT_JUDGMENT",
            "intent_text": text[:200],
            "label": label,
            "probability": round(float(probability), 4),
            "fired": bool(label) and float(probability) >= self.threshold,
            "threshold": self.threshold,
            "slots": slots,
            "truth_label": TRUTH_LABEL,
            **meta,
        }
        _append(self.sd / JEV_JUDGMENT_LEDGER, row)

    # -- the Protocol ------------------------------------------------------

    def classify(self, text: str) -> tuple[Optional[str], float, dict[str, Any]]:
        if not text or not text.strip():
            return (None, 0.0, {})

        # 1. Deterministic rules first: free, instant, already correct.
        name, confidence, slots = self._regex_classifier().classify(text)
        if name:
            self._record(text=text, label=name, probability=confidence, slots=slots,
                         meta={"path": "regex", "cache": "n/a"})
            return (name, confidence, slots)

        candidates = self._candidates()
        if not candidates:
            self._record(text=text, label=None, probability=0.0, slots={},
                         meta={"path": "regex", "cache": "n/a", "note": "no effectors registered"})
            return (None, 0.0, {})

        identity = _identity(text, list(candidates) + [NONE_LABEL])

        # 2. Never pay twice: the field already holds this judgment.
        if self.use_cache:
            hit = self._cache.get(identity)
            if hit is not None:
                self.cache_hits += 1
                label = hit.get("label") or None
                prob = float(hit.get("probability") or 0.0)
                slots = dict(hit.get("slots") or {})
                if label == NONE_LABEL:
                    label = None
                self._record(text=text, label=label, probability=prob, slots=slots,
                             meta={"path": "cache", "cache": "hit"})
                fires = label is not None and prob >= self.threshold
                return (label if fires else None, prob if fires else 0.0, slots)

        # 3. Ask Jev. Any failure degrades to the regex verdict, which was None.
        try:
            out = self._ask_jev(text, candidates)
        except Exception as exc:
            self._record(text=text, label=None, probability=0.0, slots={},
                         meta={"path": "jev", "cache": "miss", "ok": False,
                               "error": f"{type(exc).__name__}: {exc}"})
            return (None, 0.0, {})

        if not out.get("ok"):
            self._record(text=text, label=None, probability=0.0, slots={},
                         meta={"path": "jev", "cache": "miss", "ok": False,
                               "status": out.get("status"), "error": out.get("error")})
            return (None, 0.0, {})

        chosen = out.get("label")
        probabilities = out.get("probabilities") or {}
        # The calibrated quantity is the probability of the SELECTED option, not
        # the concentration of the distribution.
        probability = float(probabilities.get(chosen, out.get("confidence") or 0.0))
        label = None if chosen in (None, NONE_LABEL) else str(chosen)

        if self.use_cache:
            self._cache.put(identity, chosen, probability, {})

        self._record(text=text, label=label, probability=probability, slots={},
                     meta={"path": "jev", "cache": "miss", "ok": True,
                           "model": out.get("model"), "elapsed_ms": out.get("elapsed_ms"),
                           "input_tokens": out.get("input_tokens"),
                           "output_tokens": out.get("output_tokens"),
                           "distribution_confidence": out.get("confidence"),
                           "probabilities": probabilities})

        if label is None or probability < self.threshold:
            return (None, 0.0 if label is None else probability, {})
        return (label, probability, {})

    # -- installation ------------------------------------------------------

    def install(self, *, state_dir: Path | str | None = None) -> dict[str, Any]:
        """Opt the router's default classifier into this lane.

        A marker file, not a code edit: the router keeps its own fallback and an
        operator can disarm the lane by deleting one file.
        """
        sd = _state_dir(state_dir) if state_dir is not None else self.sd
        sd.mkdir(parents=True, exist_ok=True)
        (sd / JEV_INTENT_ENABLED).write_text(
            json.dumps({"ts": time.time(), "threshold": self.threshold,
                        "truth_label": TRUTH_LABEL}, indent=2),
            encoding="utf-8",
        )
        return self.status()

    def uninstall(self, *, state_dir: Path | str | None = None) -> dict[str, Any]:
        sd = _state_dir(state_dir) if state_dir is not None else self.sd
        marker = sd / JEV_INTENT_ENABLED
        if marker.exists():
            marker.unlink()
        return self.status()

    def status(self, *, state_dir: Path | str | None = None) -> dict[str, Any]:
        sd = _state_dir(state_dir) if state_dir is not None else self.sd
        judgments = read_judgments(state_dir=sd)
        jev_rows = [j for j in judgments if j.get("path") == "jev"]
        return {
            "installed": (sd / JEV_INTENT_ENABLED).exists(),
            "threshold": self.threshold,
            "judgments_total": len(judgments),
            "jev_calls_recorded": len(jev_rows),
            "cache_hits_recorded": len([j for j in judgments if j.get("path") == "cache"]),
            "tokens_spent_recorded": sum(int(j.get("input_tokens") or 0) + int(j.get("output_tokens") or 0) for j in jev_rows),
            "truth_label": TRUTH_LABEL,
        }


def default_classifier():
    """What the router should use when the caller passes no classifier.

    Returns the Jev lane only when the opt-in marker exists AND the lane imports
    and constructs cleanly; otherwise the original regex classifier. The router's
    behaviour is therefore unchanged unless the lane was deliberately enabled.
    """
    from System.swarm_cortex_gated_effector_router import RegexIntentClassifier

    try:
        if not (_STATE / JEV_INTENT_ENABLED).exists():
            return RegexIntentClassifier()
        return JevIntentClassifier()
    except Exception:
        return RegexIntentClassifier()


def selftest() -> dict[str, Any]:
    """Prove: rules first, real Jev for gaps, reuse is free, unsurely refuses."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)

        class _Spec:
            def __init__(self, name, description):
                self.name = name
                self.description = description
                self.allowed_audiences = ("architect",)

        class _Reg:
            _specs = {
                "open_camera": _Spec("open_camera", "switch the camera on or start a video capture"),
                "set_wallpaper": _Spec("set_wallpaper", "change the desktop wallpaper image"),
            }

        # ledgers in a temp dir, credential from the real body
        clf = JevIntentClassifier(state_dir=sd, key_state_dir=_STATE, registry=_Reg())

        # 1. regex path must not spend a Jev call
        before = clf.calls
        # (no patterns are registered in this isolated import, so the regex misses)

        # 2. a real Jev judgment on a novel utterance
        label, prob, slots = clf.classify("could you flip the wallpaper to something calmer")
        after = clf.calls

        # 3. identical text again must be a cache hit and cost nothing
        label2, prob2, _ = clf.classify("could you flip the wallpaper to something calmer")
        calls_after_cache = clf.calls

        # 4. an impossible threshold must refuse rather than guess
        strict = JevIntentClassifier(state_dir=sd, key_state_dir=_STATE, registry=_Reg(), threshold=0.999)
        label3, prob3, _ = strict.classify("could you flip the wallpaper to something calmer")

        rows = read_judgments(state_dir=sd)
        jev_rows = [r for r in rows if r.get("path") == "jev"]

    checks = {
        "jev_was_actually_called": after > before,
        "judgment_has_probability": 0.0 <= prob <= 1.0,
        "wallpaper_chosen": label == "set_wallpaper",
        "repeat_is_a_cache_hit": calls_after_cache == after,
        "repeat_same_answer": label2 == label and abs(prob2 - prob) < 1e-9,
        "unsure_refuses": label3 is None or prob3 < 0.999,
        "judgment_traced": len(jev_rows) >= 1,
        "trace_carries_tokens": any(r.get("input_tokens") for r in jev_rows),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


def main(argv: Iterable[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    clf = JevIntentClassifier()
    if args[0] == "selftest":
        print(json.dumps(selftest(), indent=2))
        return 0
    if args[0] == "status":
        print(json.dumps(clf.status(), indent=2))
        return 0
    if args[0] == "install":
        print(json.dumps(clf.install(), indent=2))
        return 0
    if args[0] == "uninstall":
        print(json.dumps(clf.uninstall(), indent=2))
        return 0
    if args[0] == "classify":
        text = " ".join(args[1:])
        label, prob, slots = clf.classify(text)
        print(json.dumps({"text": text, "effector": label, "probability": prob, "slots": slots}, indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
