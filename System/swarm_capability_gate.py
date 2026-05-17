#!/usr/bin/env python3
"""
System/swarm_capability_gate.py — DEPRECATED SHIM (Cowork CW47 2026-05-16)
══════════════════════════════════════════════════════════════════════════

This module was renamed to ``swarm_mutation_guard.py`` to free the word
"capability" for the unified Capability Registry
(``System/swarm_capability_registry.py``) that Alice reasons over.

This file is now a thin re-export shim so any caller still importing
``swarm_capability_gate`` (or ``SwarmCapabilityGate``) keeps working
during the consolidation window. New code MUST import directly from
``swarm_mutation_guard``.

The shim prints a one-time deprecation notice on import, gated by the
``SIFTA_QUIET_DEPRECATIONS`` env var so it doesn't pollute pytest logs.

§7.6 alignment: one word, one meaning. "Capability" is what Alice can
do (tools + skills + apps unified). The OS-mutation guard is something
else and now wears its own name.
"""

import os as _os

from System.swarm_mutation_guard import (  # noqa: F401 — re-export
    SwarmCapabilityGate,
    SwarmMutationGuard,
)

if _os.environ.get("SIFTA_QUIET_DEPRECATIONS", "0") != "1":
    import sys as _sys
    print(
        "[swarm_capability_gate] DEPRECATED: use System.swarm_mutation_guard. "
        "Cowork CW47 2026-05-16.",
        file=_sys.stderr,
    )
