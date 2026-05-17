#!/usr/bin/env python3
"""
swarm_dictation_geometry.py — DEPRECATED tombstone.

This module was created during a Cowork session on 2026-05-17 before
discovering that another IDE Doctor had already implemented the
foreground-IDE voice attribution filter in
Applications/sifta_talk_to_alice_widget.py via:

    _foreground_ide_voice_attribution(text, stt_conf, ...)
    _foreground_ide_voice_attribution_from_surface(surface, text, ...)
    _write_external_ide_voice_receipt(text, stt_conf, attribution, ...)
    _external_ide_surface_kind(surface)

That implementation uses NEEDLES-based substring matching against app /
window / bundle-id surface data (not vendor brand strings alone) and
already writes structured receipts to .sifta_state/external_ide_voice.jsonl.

§8.5 (verify-don't-redo) + §4.4 (no duplicated parallel surgery) →
this file is a tombstone. Do NOT import from it.

Note (Architect, 2026-05-17): the entire foreground-IDE filter has no
physical basis. App-name strings are marketing labels, not observables.
A physics-based router would read: macOS accessibility focus (which
text-input field has the cursor), dictation engine state, eye-gaze
direction, recent keyboard activity. That replacement is open work.

Vendor brand strings removed per Architect 2026-05-17:
'remove Claude from all code'.

Stigauth: COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE.
"""
from __future__ import annotations

import warnings


def was_external_ide_foreground(*_args, **_kwargs):
    """Deprecated tombstone. Returns None unconditionally."""
    warnings.warn(
        "swarm_dictation_geometry.was_external_ide_foreground is deprecated. "
        "Use the canonical _foreground_ide_voice_attribution in the Talk "
        "widget, OR build a physics-based router (accessibility focus + "
        "gaze + dictation engine state).",
        DeprecationWarning,
        stacklevel=2,
    )
    return None
