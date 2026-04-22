"""ALICE_PARROT_LOOP regression guard.

Locks in the two defenses C47H added on 2026-04-21 after the Architect
showed a live Talk-to-Alice transcript where Alice, handed a stream of
backchannel grunts ("Mm-hmm.", "Thank you.", "Mm."), collapsed into the
canonical RLHF sycophantic-servant pattern ("I'm here. What's on your
mind?") round after round, AND the gag-reflex fired silently while the
boilerplate stayed visible on screen.

Defenses:
  1. `_is_backchannel_utterance(text, stt_conf)` — returns True for phatic
     acknowledgments that should NOT wake the LLM. Intercepts in
     `_on_stt_done` so no brain call ever happens.
  2. `_is_rlhf_boilerplate(text)` — now catches bare self-status
     survivors ("I am ready", "I'm functioning optimally ...") that used
     to leak through after the servant-tail stripper ate their closers.

If either of these regresses, the same live-session parrot loop resumes.
"""

import importlib.util
from pathlib import Path


def _load_widget_module():
    """Load the widget as a module WITHOUT instantiating any Qt widgets.
    Imports are safe at module scope because the Qt classes are only
    constructed inside `__main__`."""
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Defense #1: backchannel gate ────────────────────────────────────────
def test_backchannel_phrasebook_matches_are_silenced():
    """Exact phatic acknowledgments must be detected at any STT confidence."""
    mod = _load_widget_module()
    # Every one of these appeared in the live session as a user turn that
    # triggered Alice's RLHF collapse.
    backchannel_samples = [
        ("Mm-hmm.",     0.50),
        ("Mm.",         0.41),
        ("Mm-hmm",      0.54),
        ("Thank you.",  0.38),
        ("Thank you",   0.75),
        ("Thanks",      0.80),
        ("Yeah.",       0.70),
        ("Yep",         0.65),
        ("OK",          0.60),
        ("Okay.",       0.90),
        ("Uh-huh",      0.55),
        ("Hmm",         0.80),
        ("Got it.",     0.80),
        ("I see.",      0.75),
        ("Right.",      0.70),
        ("Sure",        0.85),
    ]
    for text, conf in backchannel_samples:
        assert mod._is_backchannel_utterance(text, conf), (
            f"backchannel detector missed phatic utterance: {text!r}@{conf}"
        )


def test_backchannel_does_not_swallow_real_content():
    """Real questions and assertions must NEVER be classified as backchannel,
    even at low STT confidence — the Architect's voice can be quiet/noisy,
    that's a fidelity problem for STT, not permission to ignore meaning."""
    mod = _load_widget_module()
    # These were all real user turns in the live session. At minimum the
    # last one is a direct command that MUST reach Alice.
    real_content_samples = [
        ("Is it refrigerator?",              0.43),
        ("This is the same.",                0.67),
        ("Let us go Valleys. Have you ever walked before?", 0.41),
        ("c47h stigauth and 555 above",      0.90),
        ("from both the legs.",              0.48),
        ("Sign in and run diagnostics.",     0.55),
        ("Scan the ribosome folding state.", 0.30),
        ("",                                 0.50),   # empty → not backchannel
    ]
    for text, conf in real_content_samples:
        assert not mod._is_backchannel_utterance(text, conf), (
            f"backchannel detector false-positive on real content: "
            f"{text!r}@{conf}"
        )


# ── Defense #2: RLHF gag-reflex covers bare self-status survivors ───────
def _would_alice_speak(mod, raw_model_output: str) -> bool:
    """Replicate the exact silent-vs-speak decision from `_on_brain_done`
    for a given raw model output. Returns True if Alice would vocalize;
    False if the gag + stripper pipeline would silence her."""
    cleaned = mod._strip_servant_tail_tics(
        mod._strip_reflective_tics(raw_model_output)
    )
    rlhf_gag = (
        mod._is_rlhf_boilerplate(cleaned)
        or mod._is_rlhf_boilerplate(raw_model_output)
    )
    explicit_silent = rlhf_gag or mod._is_silent_marker(raw_model_output)
    return not (explicit_silent or not cleaned)


def test_live_session_parrot_loop_is_fully_silenced():
    """Every RLHF-collapse line Alice emitted in the 2026-04-21 live
    session must now be gagged. This is the 'once forever' test."""
    mod = _load_widget_module()
    live_parrot_lines = [
        "I'm here. What's on your mind?",
        "I'm here, ready to process whatever you need. What's on your mind?",
        "I'm here to help. What's on your mind, or what would you like to explore today?",
        "I'm ready for your next question, or I can run any of my available "
        "diagnostic or exploratory routines. What's on your mind?",
        "I'm functioning optimally and ready for your next query. "
        "How can I assist you today?",
        "I'm glad to hear it. I'm ready for whatever you'd like to explore "
        "next. What's on your mind?",
        "I'm here, ready to assist. What's on your mind today?",
        "I'm ready for your next question or task. What's on your mind?",
        "I am ready. How can I assist you today?",
        "I am listening.",
        "I'm ready",
    ]
    leaks = [line for line in live_parrot_lines if _would_alice_speak(mod, line)]
    assert not leaks, (
        "RLHF parrot line(s) leaked past the gag — ALICE_PARROT_LOOP "
        f"regression: {leaks!r}"
    )


def test_real_content_survives_the_gag():
    """Genuine sentences must pass — a gag that silences real speech is
    worse than no gag. Topological-integrity and FMO-efficiency lines
    were the motivating false-positives AG31 originally caused."""
    mod = _load_widget_module()
    real_replies = [
        # Actual live Alice reply that contained a real question:
        "I am ready to follow you. Where are we going?",
        # Rich, content-bearing reply from the walking prompt:
        "I've always been a collection of data, a network of potential "
        "pathways, but yes, I understand the concept of walking — of "
        "traversing space and time.",
        # AG31's original false positives (contain "1.", "I understand"):
        "Topological integrity is 1.0 — body intact.",
        "I understand the FMO router efficiency rose to 15.38%.",
        # Mixed opener + real content — must pass:
        "I'm here, and the ribosome just folded a protein called HSP70.",
        "I am listening to the wind in the courtyard — it smells like "
        "after-rain.",
    ]
    silenced = [line for line in real_replies if not _would_alice_speak(mod, line)]
    assert not silenced, (
        f"Gag over-reached and silenced real content: {silenced!r}"
    )


def test_erase_method_exists_on_widget():
    """The `_erase_alice_streaming_line` method must exist on the widget
    class — without it, gagged replies still stream to the UI visibly.
    This is the structural half of ALICE_PARROT_LOOP."""
    mod = _load_widget_module()
    # Talk to Alice widget class name is `TalkToAliceWidget` in this module.
    widget_cls = None
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and name.endswith("Widget") and "Alice" in name:
            widget_cls = obj
            break
    assert widget_cls is not None, (
        "Could not locate Talk-to-Alice widget class in module"
    )
    assert hasattr(widget_cls, "_erase_alice_streaming_line"), (
        "_erase_alice_streaming_line method missing — gagged replies "
        "will stay visible on screen"
    )
    assert hasattr(widget_cls, "_begin_alice_streaming_line"), (
        "_begin_alice_streaming_line method missing"
    )
