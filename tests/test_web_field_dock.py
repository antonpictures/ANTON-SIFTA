"""W3 regression test: web field dock block + repair_stale_claims are single, correct defs.

Verifies:
- exactly one definition of web_field_dock_block (the returning one, no no-return stub)
- exactly one definition of repair_stale_claims (the float-epoch version, no NameError variant)
- web_field_dock_block actually returns a dock string
- repair_stale_claims is importable with the max_age_s contract
"""
from pathlib import Path
import inspect
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def _gate():
    from System import swarm_web_global_chat_gate as gate
    return gate


def test_single_definitions():
    src = inspect.getsource(_gate())
    assert src.count("def web_field_dock_block(") == 1, "web_field_dock_block must be defined exactly once"
    assert src.count("def repair_stale_claims(") == 1, "repair_stale_claims must be defined exactly once"
    # the kept repair version must use float-epoch time, not the broken datetime/timedelta path
    repair_src = inspect.getsource(_gate().repair_stale_claims)
    assert "time.time()" in repair_src, "repair_stale_claims must use float-epoch now"
    assert "timedelta" not in repair_src, "repair_stale_claims must not reference timedelta without import"


def test_web_field_dock_block_returns_string():
    gate = _gate()
    out = gate.web_field_dock_block("test-session-that-does-not-exist")
    assert isinstance(out, str), "dock block must return a string (the old stub returned None)"
    assert "WEB FIELD DOCKING" in out, "dock block must carry its header"


def test_repair_stale_claims_contract():
    gate = _gate()
    sig = inspect.signature(gate.repair_stale_claims)
    assert "max_age_s" in sig.parameters, "repair_stale_claims must accept max_age_s"
    assert sig.parameters["max_age_s"].default == 900, "default stale window is 900s"


def test_dock_block_in_all_exports():
    gate = _gate()
    assert "web_field_dock_block" in getattr(gate, "__all__", []), "dock block must be exported"
    assert "repair_stale_claims" in getattr(gate, "__all__", []), "repair must be exported"


if __name__ == "__main__":
    test_single_definitions()
    test_web_field_dock_block_returns_string()
    test_repair_stale_claims_contract()
    test_dock_block_in_all_exports()
    print("W3 dock-block + repair checks: OK")