"""System/swarm_sovereign_recognition_organ.py
===============================================

**Sovereign Owner Recognition Organ** — stigmergic + sovereign-gallery
wrapper over AG46's pre-existing identity organ.

**Prior art honored (covenant §4.4 — read before write):**

The actual face-encoding work — Haar detect → 64×64 normalised face
patch → 4096-dim L2-normalised embedding → cosine-0.70 threshold — was
built on **2026-05-07 by AG46**, signed in
``.sifta_state/architect_face_meta.json`` (covenant §7.11). George
enrolled May 4 from ``owner_body_vision_frames/20260504T165658Z_…png``.
That embedding (``.sifta_state/architect_face_embedding.npy``) is the
single source of truth for *owner identity* on this node.

This organ **does not duplicate** that work. It delegates face encoding
and the owner template entirely to
``System.swarm_architect_face_recognition``. What this organ adds on
top, and only on top:

1. **Stigmergic swarm verdict** — one ``SovereignSwimmer`` per candidate
   identity (owner / friend_<i> / unknown), pheromone deposit + decay,
   posterior over candidates. Uses cosine similarity from AG46's
   embedding as the per-swimmer score.
2. **Sovereign friends gallery** — a JSON list at
   ``.sifta_state/sovereign_friends.json`` of owner-approved friends,
   each entry pointing at its own 4096-dim AG46-format embedding file.
   Owner-approved only; no public gallery.
3. **Territory gate** — refuses to enrol friends without a prior owner
   embedding. Refuses to enrol on synthetic frames (delegates to AG46's
   fresh-frame requirement).
4. **Receipt + gate wiring** — every verdict carries
   ``physics_gate.clearance_hash`` + ``qualia_marker`` and is appended
   to ``.sifta_state/sovereign_recognition_receipts.jsonl`` — in
   addition to AG46's per-attempt ledger.

Truth label: ``SOVEREIGN_RECOGNITION_ORGAN_V1`` (v0 was the duplicated
embedding; v1 wraps AG46).
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPTS = _STATE / "sovereign_recognition_receipts.jsonl"
_PHEROMONE_LEDGER = _STATE / "sovereign_pheromone_trace.jsonl"
_FRIENDS_PATH = _STATE / "sovereign_friends.json"
_FRIENDS_DIR = _STATE / "sovereign_friend_embeddings"
_TRUTH_LABEL = "SOVEREIGN_RECOGNITION_ORGAN_V1"
_PRIOR_ORGAN = "swarm_architect_face_recognition (AG46, 2026-05-07, §7.11)"


# ── gate hooks (graceful no-op if gates not importable) ────────────────────

def _now() -> float:
    return time.time()


def _request_clearance(lane: str, cost: str = "feather") -> Optional[Dict[str, Any]]:
    try:
        from System.swarm_physics_gate import request_clearance  # type: ignore
        return request_clearance(cost_class=cost, lane=lane)
    except Exception:
        return None


def _qualia_marker(lane: str, note: str = "") -> Dict[str, Any]:
    try:
        from System.swarm_consciousness_organ import qualia_marker  # type: ignore
        return qualia_marker(lane=lane, note=note)
    except Exception:
        return {"lane": lane, "note": note, "fallback": True}


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ── delegation to AG46's organ ─────────────────────────────────────────────

def _load_owner_embedding() -> Optional[np.ndarray]:
    """Load the existing architect embedding (AG46, May 7)."""
    try:
        from System.swarm_architect_face_recognition import _EMBEDDING  # type: ignore
        if _EMBEDDING.exists():
            return np.load(str(_EMBEDDING))
    except Exception:
        pass
    return None


def _extract_face_patch_from_bgr(img_bgr: np.ndarray) -> Optional[np.ndarray]:
    """Delegate to AG46's face patch extractor (Haar + 64x64 + L2 norm)."""
    try:
        from System.swarm_architect_face_recognition import _extract_face_patch  # type: ignore
        return _extract_face_patch(img_bgr)
    except Exception:
        return None


def _extract_face_patch_from_grayscale(gray: np.ndarray) -> Optional[np.ndarray]:
    """Adapter: convert grayscale float [0,1] frame to BGR uint8 for AG46's path."""
    try:
        import cv2  # type: ignore
        if gray.dtype != np.uint8:
            u8 = (np.clip(gray, 0.0, 1.0) * 255).astype(np.uint8)
        else:
            u8 = gray
        bgr = cv2.cvtColor(u8, cv2.COLOR_GRAY2BGR)
        return _extract_face_patch_from_bgr(bgr)
    except Exception:
        return None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom < 1e-9:
        return 0.0
    return float(np.dot(a, b) / denom)


# ── sovereign friends gallery (owner-approved only) ────────────────────────

def _load_friends() -> List[Dict[str, Any]]:
    if not _FRIENDS_PATH.exists():
        return []
    try:
        return json.loads(_FRIENDS_PATH.read_text()) or []
    except Exception:
        return []


def _save_friends(friends: List[Dict[str, Any]]) -> None:
    _FRIENDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _FRIENDS_PATH.write_text(json.dumps(friends, ensure_ascii=False, indent=2))


def enroll_friend_from_bgr(img_bgr: np.ndarray, friend_name: str) -> Optional[Dict[str, Any]]:
    """Add an owner-approved friend.

    Refuses if the owner is not already enrolled (Territory gate). Uses
    AG46's face-patch extractor so friend embeddings are the same 4096-dim
    L2-normalised format as the owner template.
    """
    if _load_owner_embedding() is None:
        return {"ok": False, "error": "no_owner_enrolled",
                "note": "Enrol the owner first via swarm_architect_face_recognition.train()"}
    patch = _extract_face_patch_from_bgr(img_bgr)
    if patch is None:
        return {"ok": False, "error": "no_face_in_frame"}
    _FRIENDS_DIR.mkdir(parents=True, exist_ok=True)
    fid = uuid.uuid4().hex[:8]
    emb_path = _FRIENDS_DIR / f"friend_{friend_name}_{fid}.npy"
    np.save(str(emb_path), patch)
    friends = _load_friends()
    friends.append({
        "name": friend_name,
        "embedding_path": str(emb_path.relative_to(_REPO)),
        "embedding_shape": list(patch.shape),
        "fid": fid,
        "ts": _now(),
        "truth_label": _TRUTH_LABEL,
    })
    _save_friends(friends)
    receipt = {
        "ts": _now(), "truth_label": _TRUTH_LABEL,
        "action": "FRIEND_ENROLLED",
        "friend": friend_name, "fid": fid,
        "embedding_path": str(emb_path.relative_to(_REPO)),
        "qualia_marker": _qualia_marker("sovereign.enroll_friend", note=friend_name),
        "delegates_to": _PRIOR_ORGAN,
    }
    _safe_append_jsonl(_RECEIPTS, receipt)
    return receipt


# ── recognition swarm (stigmergic verdict over AG46 similarities) ──────────

@dataclass
class SovereignSwimmer:
    swimmer_id: str
    candidate: str
    similarity: float = 0.0
    pheromone: float = 0.0
    ticks: int = 0


@dataclass
class SovereignVerdict:
    verdict: str
    confidence: float
    owner_similarity: float
    best_friend_name: Optional[str]
    best_friend_similarity: float
    swimmers: List[SovereignSwimmer] = field(default_factory=list)
    receipt_id: str = ""
    delegated_to: str = _PRIOR_ORGAN


def recognize(
    frame_or_patch: np.ndarray,
    ticks: int = 3,
    threshold: float = 0.70,
    pheromone_evaporation: float = 0.30,
    write_ledger: bool = True,
    input_kind: str = "auto",   # 'bgr' | 'grayscale_float' | 'patch_4096' | 'auto'
) -> SovereignVerdict:
    """Run the stigmergic verdict swarm on top of AG46's face embedding.

    Args:
        frame_or_patch: either a BGR uint8 image (Haar detect runs),
                        a [0,1] float32 grayscale frame, or an already-
                        extracted 4096-dim L2-normalised patch.
        ticks:          pheromone iterations.
        threshold:      cosine similarity above which a candidate is a
                        match. Mirrors AG46's 0.70 default.
    """
    owner_emb = _load_owner_embedding()
    if owner_emb is None:
        receipt_id = f"sovereign-{int(time.time() * 1000)}"
        if write_ledger:
            _safe_append_jsonl(_RECEIPTS, {
                "ts": _now(), "truth_label": _TRUTH_LABEL,
                "receipt_id": receipt_id,
                "verdict": "no_owner_enrolled",
                "confidence": 0.0,
                "note": "AG46 architect_face_embedding.npy not found. Run System/swarm_architect_face_recognition.py train.",
                "delegates_to": _PRIOR_ORGAN,
                "qualia_marker": _qualia_marker("sovereign.recognize", note="no_template"),
                "clearance_hash": (_request_clearance("sovereign.recognize") or {}).get("clearance_hash"),
            })
        return SovereignVerdict(verdict="no_owner_enrolled", confidence=0.0,
                                owner_similarity=0.0, best_friend_name=None,
                                best_friend_similarity=0.0, receipt_id=receipt_id)

    # Resolve input → 4096-dim patch
    arr = frame_or_patch
    patch: Optional[np.ndarray] = None
    kind = input_kind
    if kind == "auto":
        if arr.ndim == 1 and arr.shape[0] == owner_emb.shape[0]:
            kind = "patch_4096"
        elif arr.ndim == 3:
            kind = "bgr"
        elif arr.ndim == 2:
            kind = "grayscale_float"
    if kind == "patch_4096":
        patch = arr.astype(np.float32)
    elif kind == "bgr":
        patch = _extract_face_patch_from_bgr(arr)
    elif kind == "grayscale_float":
        patch = _extract_face_patch_from_grayscale(arr)

    if patch is None or patch.shape != owner_emb.shape:
        receipt_id = f"sovereign-{int(time.time() * 1000)}"
        if write_ledger:
            _safe_append_jsonl(_RECEIPTS, {
                "ts": _now(), "truth_label": _TRUTH_LABEL,
                "receipt_id": receipt_id,
                "verdict": "no_face_in_frame",
                "confidence": 0.0,
                "delegates_to": _PRIOR_ORGAN,
                "qualia_marker": _qualia_marker("sovereign.recognize", note="no_face"),
                "clearance_hash": (_request_clearance("sovereign.recognize") or {}).get("clearance_hash"),
            })
        return SovereignVerdict(verdict="no_face_in_frame", confidence=0.0,
                                owner_similarity=0.0, best_friend_name=None,
                                best_friend_similarity=0.0, receipt_id=receipt_id)

    owner_sim = _cosine(patch, owner_emb)

    friends = _load_friends()
    friend_sims: List[Tuple[str, float]] = []
    for fr in friends:
        try:
            fe_path = _REPO / fr["embedding_path"]
            if not fe_path.exists():
                continue
            fe = np.load(str(fe_path))
            friend_sims.append((str(fr.get("name", "friend")), _cosine(patch, fe)))
        except Exception:
            continue

    # Birth one swimmer per candidate
    swimmers: List[SovereignSwimmer] = [
        SovereignSwimmer(swimmer_id=f"sov-{uuid.uuid4().hex[:8]}",
                         candidate="owner", similarity=owner_sim),
    ]
    for name, sim in friend_sims:
        swimmers.append(SovereignSwimmer(swimmer_id=f"sov-{uuid.uuid4().hex[:8]}",
                                         candidate=f"friend:{name}", similarity=sim))
    swimmers.append(SovereignSwimmer(swimmer_id=f"sov-{uuid.uuid4().hex[:8]}",
                                     candidate="unknown", similarity=threshold))

    qm = _qualia_marker("sovereign.recognize", note=f"n_candidates={len(swimmers)}")

    # Stigmergic pheromone iteration
    for tick in range(ticks):
        for sw in swimmers:
            sw.pheromone *= (1.0 - pheromone_evaporation)
            sw.ticks += 1
        sims = np.array([sw.similarity for sw in swimmers], dtype=np.float64)
        median = float(np.median(sims))
        s_max = float(sims.max())
        if s_max <= median:
            continue
        for sw in swimmers:
            if sw.similarity > median:
                w = (sw.similarity - median) / (s_max - median + 1e-12)
                sw.pheromone += float(w)
                if write_ledger:
                    clearance = _request_clearance("sovereign.pheromone")
                    _safe_append_jsonl(_PHEROMONE_LEDGER, {
                        "ts": _now(), "truth_label": _TRUTH_LABEL,
                        "tick": tick,
                        "swimmer_id": sw.swimmer_id,
                        "candidate": sw.candidate,
                        "similarity": sw.similarity,
                        "pheromone": sw.pheromone,
                        "clearance_hash": (clearance or {}).get("clearance_hash"),
                        "qualia_marker": qm,
                    })

    weights = np.array([sw.pheromone for sw in swimmers], dtype=np.float64)
    if weights.sum() <= 0:
        weights = np.ones_like(weights)
    weights = weights / weights.sum()
    winner_idx = int(np.argmax(weights))
    winner = swimmers[winner_idx]
    confidence = float(weights[winner_idx])

    best_friend_name, best_friend_sim = (None, 0.0)
    if friend_sims:
        best_friend_name, best_friend_sim = max(friend_sims, key=lambda x: x[1])

    if winner.candidate == "owner" and owner_sim < threshold:
        verdict = "unknown"
        confidence = 1.0 - float(weights[winner_idx])
    elif winner.candidate.startswith("friend:") and best_friend_sim < threshold:
        verdict = "unknown"
        confidence = 1.0 - float(weights[winner_idx])
    else:
        verdict = winner.candidate

    receipt_id = f"sovereign-{int(time.time() * 1000)}"
    clearance = _request_clearance("sovereign.recognize")
    if write_ledger:
        _safe_append_jsonl(_RECEIPTS, {
            "ts": _now(), "truth_label": _TRUTH_LABEL,
            "receipt_id": receipt_id,
            "verdict": verdict,
            "confidence": confidence,
            "owner_similarity": owner_sim,
            "best_friend_name": best_friend_name,
            "best_friend_similarity": best_friend_sim,
            "threshold": threshold,
            "n_friends_enrolled": len(friends),
            "clearance_hash": (clearance or {}).get("clearance_hash"),
            "qualia_marker": qm,
            "delegates_to": _PRIOR_ORGAN,
            "doctrine": "TERRITORY_IS_THE_LAW",
        })

    return SovereignVerdict(
        verdict=verdict, confidence=confidence,
        owner_similarity=owner_sim,
        best_friend_name=best_friend_name,
        best_friend_similarity=best_friend_sim,
        swimmers=swimmers, receipt_id=receipt_id,
    )


# ── thin compatibility shims so the widget keeps working ───────────────────

def enroll_owner(*_args, **_kwargs) -> Dict[str, Any]:
    """Deprecated. Owner enrollment is owned by AG46's organ.

    The widget's 'Enrol Owner Face' button should call
    ``swarm_architect_face_recognition.train()`` directly. This shim exists
    only so legacy callers do not crash.
    """
    return {
        "ok": False,
        "action": "DEPRECATED",
        "error": "owner_enrollment_owned_by_prior_organ",
        "delegates_to": _PRIOR_ORGAN,
        "fix": "call System.swarm_architect_face_recognition.train()",
    }


def enroll_friend(_frame_gray, friend_name: str) -> Optional[Dict[str, Any]]:
    """Grayscale-input compat shim — forwards to enroll_friend_from_bgr."""
    if _frame_gray is None:
        return None
    try:
        import cv2  # type: ignore
        if _frame_gray.dtype != np.uint8:
            u8 = (np.clip(_frame_gray, 0.0, 1.0) * 255).astype(np.uint8)
        else:
            u8 = _frame_gray
        bgr = cv2.cvtColor(u8, cv2.COLOR_GRAY2BGR)
        return enroll_friend_from_bgr(bgr, friend_name)
    except Exception:
        return None
