#!/usr/bin/env python3
"""Named r440 alias for Alice's stigmergic self-evaluation surface.

The implementation lives in ``Applications.sifta_self_evaluation``. This file
exists so app manifests and launchers can use the explicit r440 name without
creating a rival self-eval system.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from Applications import sifta_self_evaluation as _impl

alice_self_evaluate_and_dispatch = _impl.alice_self_evaluate_and_dispatch
dispatch_swimmer = _impl.dispatch_swimmer
load_self_eval = _impl.load_self_eval
main = _impl.main
what_alice_does_not_know = _impl.what_alice_does_not_know
write_snapshot = _impl.write_snapshot
SelfEvaluationApp = getattr(_impl, "SelfEvaluationApp", object)
load_owner_physical_reality = _impl.load_owner_physical_reality
generate_self_code_plans = _impl.generate_self_code_plans
assess_fiction_reality = _impl.assess_fiction_reality
try:
    from System.swarm_residue_fact_fiction_eval import residue_fact_fiction_snapshot
except Exception:  # pragma: no cover
    residue_fact_fiction_snapshot = None


class StigmergicSelfEvaluationApp(SelfEvaluationApp):
    """Alias widget class for the unified self-evaluation app."""


if __name__ == "__main__":
    raise SystemExit(main())
