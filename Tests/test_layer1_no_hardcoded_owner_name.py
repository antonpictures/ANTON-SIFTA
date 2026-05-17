"""Layer-1 invariant guard:
   no consciousness-layer module may carry the Architect's owner name
   as a string literal.

The covenant calls this "Layer 1" — every reference to the human owner
must resolve at runtime through ``owner_genesis.json``. If a Doctor
accidentally types the name as a string constant, this test fails and
the regression is caught before commit.

Architect 2026-05-16: *"make sure you don't HARDCODE my name = take it
from layer one"*. This test enforces that line as code.

Scope: every Python module in `System/` whose name begins with
``swarm_alice_self``, ``swarm_architect_memory``, ``swarm_app_focus``,
``swarm_app_help`` (the consciousness + memory + app-focus layer
shipped on 2026-05-16). Tests intentionally use the literal name in
fixture data — they are excluded.

Truth label: ``SIFTA_LAYER1_NO_HARDCODE_V0``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parent.parent
_SYSTEM = _REPO / "System"
_GENESIS_PATH = _REPO / ".sifta_state" / "owner_genesis.json"


def _consciousness_modules() -> list[Path]:
    """The consciousness + memory + app-focus layer shipped on 2026-05-16.

    Updated 2026-05-16 (Cowork CW47 surgery cw47-0516-2236) to include
    Grok's ``alice_reality_boundary.py`` + the new canon registry. The
    test will FAIL against ``alice_reality_boundary.py`` until peer
    removes its hardcoded ``"george"`` and ``"ioan"`` literals — that is
    the audit-as-forcing-function pattern.
    """
    prefixes = (
        "swarm_alice_self",
        "swarm_alice_schedule",
        "swarm_architect_memory",
        "swarm_app_focus_reader",
        "swarm_app_help_skills",
        "swarm_truth_label_canon",
    )
    exact_names = (
        "alice_reality_boundary.py",
    )
    out: list[Path] = []
    for p in sorted(_SYSTEM.glob("*.py")):
        if any(p.name.startswith(prefix) for prefix in prefixes):
            out.append(p)
        elif p.name in exact_names:
            out.append(p)
    return out


def _owner_name_from_genesis() -> str | None:
    if not _GENESIS_PATH.exists():
        return None
    try:
        data = json.loads(_GENESIS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            name = str(data.get("owner_name") or "").strip()
            return name or None
    except Exception:
        return None
    return None


@pytest.fixture
def owner_name() -> str:
    name = _owner_name_from_genesis()
    if not name:
        pytest.skip(
            "owner_genesis.json missing or owner_name empty — test "
            "requires a real genesis file to enforce Layer-1 invariant."
        )
    return name


def _violations_in(text: str, name: str) -> list[tuple[int, str]]:
    """Return (line_number, line) for every line that contains the
    owner name as a substring, case-insensitive."""
    needle = name.lower()
    found: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if needle in line.lower():
            found.append((i, line.rstrip()))
    return found


def test_consciousness_modules_present():
    """Sanity check: the audit set is non-empty."""
    modules = _consciousness_modules()
    assert len(modules) >= 4, (
        f"Expected the 2026-05-16 consciousness-layer modules to be on disk; "
        f"only found: {[m.name for m in modules]}"
    )


def test_no_owner_name_string_literal_in_any_consciousness_module(owner_name: str):
    """Every reference to the owner must resolve through Layer 1 at
    runtime. A string-literal match anywhere in a consciousness module's
    source is a Layer-1 violation.
    """
    offenders: dict[str, list[tuple[int, str]]] = {}
    for module_path in _consciousness_modules():
        text = module_path.read_text(encoding="utf-8")
        hits = _violations_in(text, owner_name)
        if hits:
            offenders[module_path.name] = hits

    if offenders:
        msg_lines = [
            "Layer-1 invariant violated — owner_name found as a string "
            "literal in consciousness-layer module(s). "
            "Architect 2026-05-16: 'make sure you don't HARDCODE my "
            "name = take it from layer one'.",
            "",
        ]
        for fname, hits in offenders.items():
            msg_lines.append(f"  {fname}:")
            for line_no, line in hits:
                # Truncate long lines so the diff stays readable.
                snippet = line[:160] + ("…" if len(line) > 160 else "")
                msg_lines.append(f"    L{line_no}: {snippet}")
        pytest.fail("\n".join(msg_lines))


def test_each_module_actually_references_owner_genesis(owner_name: str):
    """A consciousness module that talks about the owner without
    *reading* ``owner_genesis.json`` is suspect. This test allows a
    module to skip the check (returns empty match) but flags it if a
    module mentions ``owner`` or ``architect`` in identifier form
    without referencing the genesis file path or a known shared
    helper.
    """
    suspicious: list[str] = []
    for module_path in _consciousness_modules():
        text = module_path.read_text(encoding="utf-8")
        mentions_owner = bool(re.search(r"\bowner\b", text, re.IGNORECASE))
        references_genesis = (
            "owner_genesis" in text
            or "_static_seed_for" in text  # uses shared helper instead
            or "feel_owner_schedule" in text
            or "swarm_kernel_identity" in text
        )
        if mentions_owner and not references_genesis:
            suspicious.append(module_path.name)
    assert not suspicious, (
        "Modules below mention 'owner' but do not read owner_genesis.json "
        "or any blessed kernel-identity helper. Either route the read "
        "through Layer 1, or remove the unused owner reference: "
        f"{suspicious}"
    )
