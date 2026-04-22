#!/usr/bin/env python3
"""
System/swarm_proof_runner.py — Vector A Meta-Organ (CI Dam)
══════════════════════════════════════════════════════════════════════
Auto-discovers every proof_of_property() -> Dict[str, bool] in the System/
directory, executes them sequentially, and halts the boot sequence if any
invariant flips. Ledgers the run to .sifta_state/ci_runner.jsonl.
"""

from __future__ import annotations
import ast
import importlib
import json
import time
import sys
from pathlib import Path
from typing import Dict, Any, List

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "ci_runner.jsonl"


def run_all_proofs() -> bool:
    """Discovers and runs all proof_of_property functions in System/."""
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    system_dir = _REPO / "System"
    
    total_proofs_run = 0
    total_invariants_passed = 0
    failures: List[Dict[str, Any]] = []

    print("🛡️  [CI DAM] Scanning biological invariants...")
    
    start_time = time.time()
    
    for py_file in sorted(system_dir.glob("*.py")):
        if py_file.name in ("__init__.py", "swarm_proof_runner.py"):
            continue
            
        module_name = f"System.{py_file.stem}"
        try:
            source = py_file.read_text(encoding="utf-8")
            if "def proof_of_property" not in source:
                continue
                
            tree = ast.parse(source)
            has_proof = any(isinstance(node, ast.FunctionDef) and node.name == "proof_of_property" for node in tree.body)
            if not has_proof:
                continue

            mod = importlib.import_module(module_name)
            if not hasattr(mod, "proof_of_property"):
                continue

            proof_func = getattr(mod, "proof_of_property")
            res = proof_func()
            
            total_proofs_run += 1
            
            if isinstance(res, dict):
                for k, v in res.items():
                    if v is True:
                        total_invariants_passed += 1
                    else:
                        failures.append({"module": module_name, "invariant": k})
            elif isinstance(res, bool):
                if res is True:
                    total_invariants_passed += 1
                else:
                    failures.append({"module": module_name, "invariant": "overall boolean return"})

        except Exception as e:
            failures.append({"module": module_name, "invariant": f"Crash: {e}"})

    duration = time.time() - start_time
    is_clean = len(failures) == 0
    
    payload = {
        "ts": time.time(),
        "total_modules_run": total_proofs_run,
        "total_invariants_passed": total_invariants_passed,
        "is_clean": is_clean,
        "failures": failures,
        "duration_s": round(duration, 3)
    }

    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_LEDGER, json.dumps(payload) + "\\n")
    except Exception:
        pass

    if is_clean:
         print(f"🛡️  [CI DAM] All {total_invariants_passed} invariants passed across {total_proofs_run} organs.")
    else:
         print(f"🚨 [CI DAM] FATAL FAILURE: {len(failures)} invariants corrupted.")
         for f in failures:
             print(f"    - {f['module']}: {f['invariant']}")

    return is_clean


if __name__ == "__main__":
    if not run_all_proofs():
        sys.exit(1)
    sys.exit(0)
