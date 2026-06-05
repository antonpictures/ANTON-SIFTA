#!/usr/bin/env python3
"""Local modular voice pipeline resolver for SIFTA.

This organ keeps Alice's production speech path modular:

    mic/VAD -> local ASR -> text gates/ledger -> Alice brain -> local TTS

It deliberately does not make direct audio-to-audio speech models the default.
Those models can be studied in a research lane, but production speech must keep
the text ledger boundary where RLHS, wake-ear, social-frame, tool truth, and
effector receipts can inspect the turn.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - bootstrap fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as f:
            f.write(line)


MODULE_VERSION = "2026-05-07.v1"
TRUTH_LABEL = "SIFTA_LOCAL_VOICE_PIPELINE"

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
PIPELINE_LEDGER = STATE_DIR / "local_voice_pipeline_receipts.jsonl"
PIPER_VOICES_DIR = REPO_ROOT / "Voices" / "piper"

ASR_BACKEND_ENV = "SIFTA_ASR_BACKEND"
TTS_BACKEND_ENV = "SIFTA_TTS_BACKEND"
LEGACY_TTS_BACKEND_ENV = "SIFTA_VOICE_BACKEND"
SHERPA_MODEL_DIR_ENV = "SIFTA_SHERPA_ONNX_MODEL_DIR"
SHERPA_CONFIG_ENV = "SIFTA_SHERPA_ONNX_CONFIG"
COSYVOICE_MODEL_DIR_ENV = "SIFTA_COSYVOICE2_MODEL_DIR"
COSYVOICE_COMMAND_ENV = "SIFTA_COSYVOICE2_COMMAND"
DIRECT_S2S_ENV = "SIFTA_ENABLE_DIRECT_S2S_EXPERIMENTS"

DEFAULT_FASTER_WHISPER_MODEL = "tiny.en"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _path_exists(path: str) -> bool:
    try:
        return Path(path).expanduser().exists()
    except Exception:
        return False


def _command_available(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _norm_backend(value: str) -> str:
    return (value or "").strip().lower().replace("-", "_")


def _candidate(
    *,
    role: str,
    backend_id: str,
    label: str,
    available: bool,
    reason: str,
    setup_hint: str = "",
    model_path: str = "",
    selected: bool = False,
) -> dict[str, Any]:
    return {
        "role": role,
        "id": backend_id,
        "label": label,
        "available": bool(available),
        "selected": bool(selected),
        "reason": reason,
        "setup_hint": setup_hint,
        "model_path": model_path,
    }


def _select_candidate(
    candidates: list[dict[str, Any]],
    *,
    override: str,
    aliases: Mapping[str, str],
) -> tuple[dict[str, Any], str]:
    requested = aliases.get(_norm_backend(override), _norm_backend(override))
    if requested:
        for cand in candidates:
            if cand["id"] == requested:
                if cand["available"]:
                    cand["selected"] = True
                    return cand, "explicit"
                break
    for cand in candidates:
        if cand["available"]:
            cand["selected"] = True
            if requested:
                return cand, f"fallback_after_unavailable_override:{requested}"
            return cand, "auto"
    candidates[-1]["selected"] = True
    return candidates[-1], "forced_degraded"


def build_voice_pipeline_report(
    *,
    faster_whisper_model: str = DEFAULT_FASTER_WHISPER_MODEL,
    env: Optional[Mapping[str, str]] = None,
    module_available: Optional[Callable[[str], bool]] = None,
    path_exists: Optional[Callable[[str], bool]] = None,
    command_available: Optional[Callable[[str], bool]] = None,
    platform_name: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve the production speech route without loading heavy models.

    The function is dependency-injected for tests, but defaults to live host
    probes. It returns only metadata, never raw audio or transcript content.
    """
    env_map = os.environ if env is None else env
    has_module = module_available or _module_available
    has_path = path_exists or _path_exists
    has_cmd = command_available or _command_available
    host_platform = platform_name or platform.system()

    sherpa_model_dir = str(env_map.get(SHERPA_MODEL_DIR_ENV, "") or "").strip()
    sherpa_config = str(env_map.get(SHERPA_CONFIG_ENV, "") or "").strip()
    sherpa_has_model = bool(
        (sherpa_model_dir and has_path(sherpa_model_dir))
        or (sherpa_config and has_path(sherpa_config))
    )
    sherpa_has_pkg = has_module("sherpa_onnx")
    if not sherpa_has_pkg:
        sherpa_reason = "sherpa-onnx package is not installed"
    elif not sherpa_has_model:
        sherpa_reason = "sherpa-onnx package is present, but no local model/config is configured"
    else:
        sherpa_reason = "offline streaming ASR/VAD path is configured"

    fw_model = (faster_whisper_model or DEFAULT_FASTER_WHISPER_MODEL).strip()
    fw_available = bool(fw_model) and has_module("faster_whisper")
    fw_reason = (
        f"faster-whisper model {fw_model!r} is available"
        if fw_available
        else "faster-whisper package is not installed"
    )

    asr_candidates = [
        _candidate(
            role="asr",
            backend_id="sherpa_onnx_streaming",
            label="sherpa-onnx streaming ASR/VAD",
            available=sherpa_has_pkg and sherpa_has_model,
            reason=sherpa_reason,
            setup_hint=(
                "Install sherpa-onnx and set SIFTA_SHERPA_ONNX_MODEL_DIR "
                "or SIFTA_SHERPA_ONNX_CONFIG to a local model."
            ),
            model_path=sherpa_model_dir or sherpa_config,
        ),
        _candidate(
            role="asr",
            backend_id="faster_whisper",
            label=f"faster-whisper {fw_model}",
            available=fw_available,
            reason=fw_reason,
            setup_hint="Install faster-whisper or keep it in requirements.txt.",
            model_path=fw_model,
        ),
    ]
    selected_asr, asr_selection = _select_candidate(
        asr_candidates,
        override=str(env_map.get(ASR_BACKEND_ENV, "") or ""),
        aliases={
            "auto": "",
            "sherpa": "sherpa_onnx_streaming",
            "sherpa_onnx": "sherpa_onnx_streaming",
            "sherpa_onnx_streaming": "sherpa_onnx_streaming",
            "whisper": "faster_whisper",
            "faster_whisper": "faster_whisper",
        },
    )

    cosy_model_dir = str(env_map.get(COSYVOICE_MODEL_DIR_ENV, "") or "").strip()
    cosy_cmd = str(env_map.get(COSYVOICE_COMMAND_ENV, "") or "").strip()
    cosy_pkg = has_module("cosyvoice") or has_module("CosyVoice")
    cosy_has_model = bool(cosy_model_dir and has_path(cosy_model_dir))
    cosy_available = bool(cosy_cmd)
    if cosy_cmd:
        cosy_reason = "CosyVoice2 command adapter is configured"
    elif not cosy_pkg:
        cosy_reason = "CosyVoice2 package/repo is not importable"
    elif not cosy_has_model:
        cosy_reason = "CosyVoice2 package is present, but model dir is not configured"
    else:
        cosy_reason = "CosyVoice2 model is present; set SIFTA_COSYVOICE2_COMMAND to enable the mouth adapter"

    piper_has_model = PIPER_VOICES_DIR.exists() and any(PIPER_VOICES_DIR.glob("*.onnx"))
    piper_available = has_module("piper") and piper_has_model
    macsay_available = host_platform == "Darwin" and has_cmd("say")

    # On Apple desktops, macOS say is a better fallback than silently requiring
    # optional Piper models. Off macOS, Piper is the useful local neural fallback.
    tts_candidates = [
        _candidate(
            role="tts",
            backend_id="cosyvoice2_streaming",
            label="CosyVoice2-0.5B streaming TTS",
            available=cosy_available,
            reason=cosy_reason,
            setup_hint=(
                "Set SIFTA_COSYVOICE2_COMMAND, or install CosyVoice2 and set "
                "SIFTA_COSYVOICE2_MODEL_DIR to the local CosyVoice2-0.5B model."
            ),
            model_path=cosy_model_dir,
        ),
    ]
    if host_platform == "Darwin":
        tts_candidates.extend([
            _candidate(
                role="tts",
                backend_id="macos_say",
                label="macOS say",
                available=macsay_available,
                reason="macOS speech synthesizer is available" if macsay_available else "say is not on PATH",
                setup_hint="Install a macOS voice or keep say on PATH.",
            ),
            _candidate(
                role="tts",
                backend_id="piper",
                label="Piper ONNX TTS",
                available=piper_available,
                reason="Piper package and voice model are available" if piper_available else "Piper package/model is not configured",
                setup_hint="Install piper-tts and place .onnx voice files under Voices/piper/.",
                model_path=str(PIPER_VOICES_DIR),
            ),
        ])
    else:
        tts_candidates.extend([
            _candidate(
                role="tts",
                backend_id="piper",
                label="Piper ONNX TTS",
                available=piper_available,
                reason="Piper package and voice model are available" if piper_available else "Piper package/model is not configured",
                setup_hint="Install piper-tts and place .onnx voice files under Voices/piper/.",
                model_path=str(PIPER_VOICES_DIR),
            ),
            _candidate(
                role="tts",
                backend_id="macos_say",
                label="macOS say",
                available=macsay_available,
                reason="macOS speech synthesizer is available" if macsay_available else "say is unavailable off macOS",
                setup_hint="Use SIFTA_VOICE_BACKEND=piper or install a local TTS backend off macOS.",
            ),
        ])
    tts_candidates.append(
        _candidate(
            role="tts",
            backend_id="null",
            label="Null silent backend",
            available=True,
            reason="degraded fallback that preserves control flow without audio",
        )
    )
    # MisoTTS signature (offline cloned) — the de-risked quick win for "Alice sounds great".
    # Pre-generated clips live in Voices/misotts_signature/. Exact phrase matches play the high-quality
    # sample; arbitrary text falls back to the selected live backend (Piper/macos_say).
    # Future: when MLX/Metal port lands, this becomes the live misotts_mlx backend.
    SIGNATURE_DIR = REPO_ROOT / "Voices" / "misotts_signature"
    tts_candidates.append(
        _candidate(
            role="tts",
            backend_id="misotts_signature",
            label="MisoTTS signature (offline cloned high-quality voice)",
            available=(SIGNATURE_DIR.exists() and any(SIGNATURE_DIR.glob("*"))),
            reason="Pre-generated Alice signature clips (MisoTTS or foundation macOS say) are present for known phrases",
            setup_hint="Run: python3 tools/alice_misotts_signature_voice_clone.py --generate (or --misotts --reference your_clip.wav). Then SIFTA_TTS_BACKEND=misotts_signature",
            model_path=str(SIGNATURE_DIR),
        )
    )

    tts_override = str(
        env_map.get(TTS_BACKEND_ENV)
        or env_map.get(LEGACY_TTS_BACKEND_ENV)
        or ""
    )
    selected_tts, tts_selection = _select_candidate(
        tts_candidates,
        override=tts_override,
        aliases={
            "auto": "",
            "cosy": "cosyvoice2_streaming",
            "cosyvoice": "cosyvoice2_streaming",
            "cosyvoice2": "cosyvoice2_streaming",
            "cosyvoice2_streaming": "cosyvoice2_streaming",
            "say": "macos_say",
            "macsay": "macos_say",
            "macos_say": "macos_say",
            "piper": "piper",
            "null": "null",
            "signature": "misotts_signature",
            "misotts": "misotts_signature",
            "misotts_signature": "misotts_signature",
            "high_quality": "misotts_signature",
        },
    )

    direct_experiment = _truthy(env_map.get(DIRECT_S2S_ENV))
    report = {
        "truth_label": TRUTH_LABEL,
        "module_version": MODULE_VERSION,
        "ts": time.time(),
        "architecture": "modular_local_stt_text_brain_tts",
        "stages": [
            "mic_vad",
            "local_asr",
            "wake_social_rlhs_gates",
            "alice_text_brain",
            "local_tts",
            "vocal_cords_receipt",
        ],
        "selected_asr": dict(selected_asr),
        "selected_tts": dict(selected_tts),
        "asr_candidates": asr_candidates,
        "tts_candidates": tts_candidates,
        "selection": {
            "asr": asr_selection,
            "tts": tts_selection,
        },
        "text_ledger_boundary": True,
        "raw_audio_stored": False,
        "direct_s2s": {
            "default_enabled": False,
            "experiment_enabled": direct_experiment,
            "production_allowed": False,
            "reason": (
                "Direct audio-to-audio can bypass text receipts, wake/social "
                "frame filters, and effector truth. Keep it research-only."
            ),
        },
        "fallbacks": {
            "asr": "faster_whisper",
            "tts": "macos_say" if host_platform == "Darwin" else "piper_or_null",
        },
    }
    return report


def canonical_report_hash(report: Mapping[str, Any]) -> str:
    payload = json.dumps(report, ensure_ascii=True, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_voice_pipeline_receipt(
    report: Optional[Mapping[str, Any]] = None,
    *,
    kind: str = "VOICE_PIPELINE_RESOLVE",
    extra: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Append an audit row for a speech-route decision.

    The receipt intentionally omits raw audio and transcript text. It records
    only the selected route and the invariant that the text ledger boundary is
    still present.
    """
    resolved = dict(report or build_voice_pipeline_report())
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "receipt_id": str(uuid.uuid4()),
        "kind": kind,
        "truth_label": TRUTH_LABEL,
        "module_version": MODULE_VERSION,
        "architecture": resolved.get("architecture"),
        "selected_asr": resolved.get("selected_asr", {}),
        "selected_tts": resolved.get("selected_tts", {}),
        "text_ledger_boundary": bool(resolved.get("text_ledger_boundary", False)),
        "direct_s2s_default_enabled": bool(
            resolved.get("direct_s2s", {}).get("default_enabled", True)
        ),
        "raw_audio_stored": bool(resolved.get("raw_audio_stored", True)),
        "report_hash": canonical_report_hash(resolved),
    }
    if extra:
        row["extra"] = dict(extra)
    append_line_locked(PIPELINE_LEDGER, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def selected_asr_id(report: Optional[Mapping[str, Any]] = None) -> str:
    resolved = report or build_voice_pipeline_report()
    return str(resolved.get("selected_asr", {}).get("id") or "")


def selected_tts_id(report: Optional[Mapping[str, Any]] = None) -> str:
    resolved = report or build_voice_pipeline_report()
    return str(resolved.get("selected_tts", {}).get("id") or "")


def _main() -> int:
    report = build_voice_pipeline_report()
    receipt = write_voice_pipeline_receipt(report, kind="VOICE_PIPELINE_SMOKE")
    print(json.dumps({
        "ok": True,
        "selected_asr": report["selected_asr"]["id"],
        "selected_tts": report["selected_tts"]["id"],
        "text_ledger_boundary": report["text_ledger_boundary"],
        "direct_s2s_default_enabled": report["direct_s2s"]["default_enabled"],
        "receipt_id": receipt["receipt_id"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
