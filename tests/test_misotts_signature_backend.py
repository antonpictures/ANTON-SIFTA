"""tests/test_misotts_signature_backend.py

Verifier test (cowork_claude) for the offline signature-voice limb Grok landed in
r572. It pins the HONEST contract so Alice never silently claims the SOTA MisoTTS
voice before the real model has actually generated her clips:

  1. the misotts_signature backend registers + is available when signature clips exist;
  2. it does NOT overclaim — its reason names the macOS-say foundation, not "MisoTTS"
     alone, so a lawyer/demo can't mistake macOS Samantha for SOTA MisoTTS;
  3. the live fallback (macos_say) is never removed for arbitrary text.

Today the clips are macOS Samantha (receipts: method=macos_say). The real upgrade is
the documented `--misotts --reference <clip>` path on a host with MisoTTS installed.
This is the §3.5 verifier closing the chain on a brother's organ, not a rival build.
"""
from System.swarm_local_voice_pipeline import build_voice_pipeline_report


def _backends(report):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "id" in node and ("available" in node or "reason" in node):
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(report)
    return {b["id"]: b for b in found}


def _report_macos_with_clips():
    # Deterministic: a macOS host where signature clips exist; no piper/sherpa modules.
    return _backends(
        build_voice_pipeline_report(
            path_exists=lambda p: True,
            command_available=lambda c: c == "say",
            module_available=lambda m: False,
            platform_name="Darwin",
        )
    )


def test_signature_backend_registers_when_clips_present():
    backends = _report_macos_with_clips()
    assert "misotts_signature" in backends, "signature backend should register when clips are present"
    assert backends["misotts_signature"].get("available") is True


def test_signature_backend_does_not_overclaim_misotts():
    reason = str(_report_macos_with_clips()["misotts_signature"].get("reason", "")).lower()
    # Honest contract: the macOS-say foundation must be named so nobody mistakes the
    # current clips for SOTA MisoTTS before the real --misotts path has been run.
    assert ("macos say" in reason) or ("foundation" in reason), f"overclaim risk in reason: {reason!r}"


def test_live_fallback_macos_say_never_removed():
    assert "macos_say" in _report_macos_with_clips(), "the always-on live fallback must remain for arbitrary text"
