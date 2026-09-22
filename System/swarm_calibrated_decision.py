#!/usr/bin/env python3
"""J1 — a local, typed decision organ over the J0 logits interface.

This module turns a local forward pass into a reusable Choice-shaped result.
It deliberately does not call Jev or any other cloud service.  A raw softmax
over the supplied alternatives is marked ``raw_uncalibrated_option_relative``;
only an explicitly supplied, versioned calibration artifact can change that
status.  The result is a ranking/reflex signal, never physical authority.

The backend protocol is intentionally small.  J0's llama.cpp server can be
used through :class:`LlamaServerBackend`, while tests and future local runtimes
can provide ``score(message, labels)`` without importing a model runtime.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - bare System/ execution
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)


RAW_STATUS = "raw_uncalibrated_option_relative"
CALIBRATED_STATUS = "calibrated_option_relative"
SCHEMA = "SIFTA_CALIBRATED_DECISION_V1"
DEFAULT_RECEIPT_PATH = Path(__file__).resolve().parent.parent / ".sifta_state" / "swarm_calibrated_decisions.jsonl"


class DecisionError(RuntimeError):
    """A typed local decision could not be produced."""

    def __init__(self, code: str, detail: str, *, metadata: Mapping[str, Any] | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.metadata = dict(metadata or {})
        super().__init__(f"[{self.code}] {self.detail}")


class LogitBackend(Protocol):
    """Local backend contract; it must never return generated JSON confidence."""

    model_id: str
    model_artifact_digest: str
    prompt_template: str

    def score(self, message: str, labels: Sequence[str]) -> Mapping[str, Any]:
        """Return ``logits`` and optionally ``token_ids``/backend metadata."""


def _sha256(value: Any) -> str:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _softmax(logits: Mapping[str, float], temperature: float = 1.0) -> dict[str, float]:
    if not _finite_number(temperature) or float(temperature) <= 0:
        raise DecisionError("INVALID_CALIBRATION", "temperature must be a finite positive number")
    scaled = {label: float(value) / float(temperature) for label, value in logits.items()}
    maximum = max(scaled.values())
    denominator = sum(math.exp(value - maximum) for value in scaled.values())
    if not _finite_number(denominator) or denominator <= 0:
        raise DecisionError("NONFINITE_DISTRIBUTION", "softmax denominator is not finite and positive")
    return {label: math.exp(value - maximum) / denominator for label, value in scaled.items()}


@dataclass(frozen=True)
class CalibrationArtifact:
    """A measured J2 artifact, never a self-rated model confidence value."""

    artifact_id: str
    temperature: float = 1.0
    fitted_on: str = ""

    def __post_init__(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("calibration artifact_id is required")
        if not _finite_number(self.temperature) or float(self.temperature) <= 0:
            raise ValueError("calibration temperature must be finite and positive")


@dataclass(frozen=True)
class Decision:
    """Serializable Choice-shaped output with explicit uncertainty semantics."""

    schema: str
    receipt_id: str
    choice: str | None
    probabilities: dict[str, float]
    confidence: float | None
    status: str
    abstained: bool
    reason_code: str | None
    model_id: str
    model_artifact_digest: str
    prompt_template_sha256: str
    label_order_sha256: str
    calibration_artifact_id: str | None
    latency_ms: int
    cache_hit: bool
    backend: str
    message_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "receipt_id": self.receipt_id,
            "choice": self.choice,
            "probabilities": dict(self.probabilities),
            "confidence": self.confidence,
            "status": self.status,
            "abstained": self.abstained,
            "reason_code": self.reason_code,
            "model_id": self.model_id,
            "model_artifact_digest": self.model_artifact_digest,
            "prompt_template_sha256": self.prompt_template_sha256,
            "label_order_sha256": self.label_order_sha256,
            "calibration_artifact_id": self.calibration_artifact_id,
            "latency_ms": self.latency_ms,
            "cache_hit": self.cache_hit,
            "backend": self.backend,
            "message_sha256": self.message_sha256,
        }


class LlamaServerBackend:
    """Read next-token logits from a running J0-compatible llama.cpp server.

    The server is deliberately supplied by the caller.  Starting a model
    process belongs to the J0 runner and lifecycle supervisor; this class never
    downloads a model, starts a cloud fallback, or fabricates a score.
    """

    def __init__(
        self,
        *,
        port: int,
        model_id: str,
        model_artifact_digest: str,
        prompt_template: str,
        n_probs: int = 512,
        max_n_probs: int = 1024,
        timeout_s: float = 30.0,
        host: str = "127.0.0.1",
    ) -> None:
        if int(n_probs) < 1 or int(max_n_probs) < int(n_probs):
            raise ValueError("max_n_probs must be >= n_probs >= 1")
        self.base_url = f"http://{host}:{int(port)}"
        self.model_id = str(model_id)
        self.model_artifact_digest = str(model_artifact_digest)
        self.prompt_template = str(prompt_template)
        self.n_probs = int(n_probs)
        self.max_n_probs = int(max_n_probs)
        self.timeout_s = float(timeout_s)
        self._token_ids: dict[str, int] = {}

    def _post(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(dict(payload)).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8", "replace"))
        except Exception as exc:
            raise DecisionError("BACKEND_UNAVAILABLE", f"local logits endpoint {self.base_url} failed: {exc}") from exc
        if not isinstance(body, dict):
            raise DecisionError("INVALID_BACKEND_RESPONSE", "local logits endpoint returned a non-object")
        return body

    def _ensure_tokens(self, labels: Sequence[str]) -> dict[str, int]:
        missing = [label for label in labels if label not in self._token_ids]
        for label in missing:
            body = self._post("/tokenize", {"content": " " + label})
            ids = body.get("tokens")
            if not isinstance(ids, list) or not ids or not isinstance(ids[0], int):
                raise DecisionError("TOKENIZATION_FAILED", f"no continuation token for label {label!r}")
            self._token_ids[label] = int(ids[0])
        reverse: dict[int, list[str]] = {}
        for label in labels:
            reverse.setdefault(self._token_ids[label], []).append(label)
        collisions = {token: names for token, names in reverse.items() if len(names) > 1}
        if collisions:
            raise DecisionError("TOKEN_COLLISION", f"declared options share first tokens: {collisions}")
        return {label: self._token_ids[label] for label in labels}

    def score(self, message: str, labels: Sequence[str]) -> Mapping[str, Any]:
        tokens = self._ensure_tokens(labels)
        prompt = self.prompt_template.format(labels_block=", ".join(labels), message=message)
        def read(n_probs: int) -> dict[int, float]:
            body = self._post("/completion", {"prompt": prompt, "n_predict": 0, "n_probs": n_probs, "temperature": 0.0})
            top = (body.get("completion_probabilities") or [{}])[0].get("top_logprobs") or []
            out: dict[int, float] = {}
            for entry in top:
                token, value = entry.get("id"), entry.get("logprob")
                if isinstance(token, int) and _finite_number(value):
                    out[token] = float(value)
            return out
        by_token = read(self.n_probs)
        ladder_used = False
        missing = [label for label, token in tokens.items() if token not in by_token]
        if missing and self.max_n_probs > self.n_probs:
            ladder_used = True
            by_token.update(read(self.max_n_probs))
            missing = [label for label, token in tokens.items() if token not in by_token]
        if missing:
            raise DecisionError("MISSING_OPTIONS", f"top-K response did not expose declared labels: {missing}", metadata={"n_probs": self.max_n_probs})
        return {
            "logits": {label: by_token[token] for label, token in tokens.items()},
            "token_ids": tokens,
            "prompt": prompt,
            "backend": "llama.cpp",
            "top_k_ladder_used": ladder_used,
        }


class CalibratedDecisionEngine:
    """Cacheable typed decision engine; no implicit remote or generated fallback."""

    def __init__(
        self,
        backend: LogitBackend,
        *,
        calibration: CalibrationArtifact | None = None,
        abstain_below: float = 0.0,
        min_margin: float = 0.0,
        receipt_path: Path | str | None = DEFAULT_RECEIPT_PATH,
    ) -> None:
        self.backend = backend
        self.calibration = calibration
        self.abstain_below = float(abstain_below)
        self.min_margin = float(min_margin)
        if not 0 <= self.abstain_below <= 1 or not 0 <= self.min_margin <= 1:
            raise ValueError("abstention thresholds must be in [0, 1]")
        self.receipt_path = Path(receipt_path) if receipt_path is not None else None
        self._cache: dict[str, Decision] = {}

    def _cache_key(self, message: str, labels: Sequence[str]) -> str:
        return _sha256({
            "message": message,
            "labels": list(labels),
            "model_id": self.backend.model_id,
            "model_artifact_digest": self.backend.model_artifact_digest,
            "prompt_template": self.backend.prompt_template,
            "calibration_artifact_id": self.calibration.artifact_id if self.calibration else None,
            "calibration_temperature": self.calibration.temperature if self.calibration else None,
        })

    def _receipt(self, decision: Decision) -> None:
        if self.receipt_path is None:
            return
        row = {**decision.to_dict(), "ts": time.time(), "truth_label": "OBSERVED_LOCAL_DECISION"}
        append_line_locked(self.receipt_path, json.dumps(row, sort_keys=True) + "\n")

    def _error_receipt(self, *, message: str, labels: Sequence[str], error: DecisionError) -> None:
        """Persist an explicit refusal without turning an error into a verdict."""
        if self.receipt_path is None:
            return
        row = {
            "schema": SCHEMA,
            "receipt_id": str(uuid.uuid4()),
            "ts": time.time(),
            "status": "decision_error",
            "reason_code": error.code,
            "detail": error.detail,
            "message_sha256": _sha256(message),
            "label_order_sha256": _sha256(list(labels)),
            "model_id": str(self.backend.model_id),
            "model_artifact_digest": str(self.backend.model_artifact_digest),
            "prompt_template_sha256": _sha256(self.backend.prompt_template),
            "truth_label": "OBSERVED_LOCAL_DECISION_REFUSAL",
        }
        append_line_locked(self.receipt_path, json.dumps(row, sort_keys=True) + "\n")

    def decide(self, message: str, labels: Sequence[str]) -> Decision:
        message = str(message)
        ordered = tuple(str(label).strip() for label in labels)
        if not message.strip():
            raise DecisionError("INVALID_MESSAGE", "message must not be empty")
        if len(ordered) < 2 or any(not label for label in ordered) or len(set(ordered)) != len(ordered):
            raise DecisionError("INVALID_LABELS", "labels must contain at least two distinct non-empty options")
        key = self._cache_key(message, ordered)
        cached = self._cache.get(key)
        if cached is not None:
            result = Decision(**{
                **cached.__dict__,
                "receipt_id": str(uuid.uuid4()),
                "latency_ms": 0,
                "cache_hit": True,
            })
            self._receipt(result)
            return result
        started = time.monotonic()
        try:
            raw = self.backend.score(message, ordered)
        except DecisionError as exc:
            self._error_receipt(message=message, labels=ordered, error=exc)
            raise
        logits_raw = raw.get("logits") if isinstance(raw, Mapping) else None
        if not isinstance(logits_raw, Mapping) or set(logits_raw) != set(ordered):
            raise DecisionError("INVALID_LOGITS", "backend must return one finite logit for every declared option")
        logits: dict[str, float] = {}
        for label in ordered:
            value = logits_raw[label]
            if not _finite_number(value):
                raise DecisionError("NONFINITE_LOGIT", f"backend returned a non-finite logit for {label!r}")
            logits[label] = float(value)
        probabilities = _softmax(logits, self.calibration.temperature if self.calibration else 1.0)
        ranked = sorted(probabilities.items(), key=lambda item: (-item[1], ordered.index(item[0])))
        best_label, best_prob = ranked[0]
        second_prob = ranked[1][1]
        margin = best_prob - second_prob
        abstained = best_prob < self.abstain_below or margin < self.min_margin
        reason = None
        choice: str | None = best_label
        if abstained:
            choice = None
            reason = "LOW_CONFIDENCE" if best_prob < self.abstain_below else "SMALL_MARGIN"
        result = Decision(
            schema=SCHEMA,
            receipt_id=str(uuid.uuid4()),
            choice=choice,
            probabilities={label: round(probabilities[label], 12) for label in ordered},
            confidence=round(best_prob, 12),
            status=CALIBRATED_STATUS if self.calibration else RAW_STATUS,
            abstained=abstained,
            reason_code=reason,
            model_id=str(self.backend.model_id),
            model_artifact_digest=str(self.backend.model_artifact_digest),
            prompt_template_sha256=_sha256(self.backend.prompt_template),
            label_order_sha256=_sha256(list(ordered)),
            calibration_artifact_id=self.calibration.artifact_id if self.calibration else None,
            latency_ms=max(0, round((time.monotonic() - started) * 1000)),
            cache_hit=False,
            backend=str(raw.get("backend") or type(self.backend).__name__),
            message_sha256=_sha256(message),
        )
        self._cache[key] = result
        self._receipt(result)
        return result


__all__ = [
    "CALIBRATED_STATUS", "RAW_STATUS", "CalibrationArtifact", "CalibratedDecisionEngine",
    "Decision", "DecisionError", "LlamaServerBackend", "SCHEMA",
]
