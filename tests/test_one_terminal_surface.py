"""Covenant invariant: Alice's global chat is the ONLY terminal surface in SIFTA OS.

Owner decision 2026-05-25 ("Alice global chat is the only terminal"). Point 7 of the
collapse spec: prove no separate terminal surface can launch.

claude-opus-4-7 — auditor lane, co-coded in parallel with Codex's collapse: Codex owns
the source collapse (sifta_matrix_terminal.py -> internal service, routing, receipts,
render); this file is the gate that proves the invariant holds. The vestigial
standalone terminal file must not exist, no terminal app may be launchable, and every
terminal receipt must carry source=alice_global_chat_terminal.
"""
from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_MANIFEST = _REPO / "Applications" / "apps_manifest.json"
_STANDALONE_TERMINAL = _REPO / "Applications" / "sifta_terminal.py"

# Widget classes that ARE standalone terminal surfaces — never launchable apps.
_TERMINAL_WIDGET_CLASSES = {"MatrixTerminalApp", "SiftaTerminalApp"}


def _load_manifest() -> dict:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def _is_launchable(spec: dict) -> bool:
    """Launchable unless explicitly hidden / retired / disabled."""
    if not isinstance(spec, dict):
        return False
    if spec.get("hidden") or spec.get("_retired") or spec.get("retired"):
        return False
    if spec.get("enabled") is False:
        return False
    return True


def _launchable_terminal_offenders() -> list[str]:
    manifest = _load_manifest()
    offenders: list[str] = []
    for name, spec in manifest.items():
        if not isinstance(spec, dict):
            continue
        wc = str(spec.get("widget_class") or "")
        ep = str(spec.get("entry_point") or "").lower()
        looks_terminal = (
            wc in _TERMINAL_WIDGET_CLASSES
            or "terminal" in name.lower()
            or "terminal" in ep
        )
        if looks_terminal and _is_launchable(spec):
            offenders.append(name)
    return offenders


def test_no_launchable_terminal_surface_in_manifest():
    """No manifest entry may be a launchable standalone terminal surface."""
    offenders = _launchable_terminal_offenders()
    assert not offenders, (
        f"Separate terminal surface(s) launchable in manifest: {offenders}. "
        "Alice global chat is the only terminal surface (owner decision 2026-05-25)."
    )


def test_standalone_terminal_file_removed():
    assert not _STANDALONE_TERMINAL.exists(), (
        "Applications/sifta_terminal.py is the deleted vestigial standalone PTY surface."
    )


def test_terminal_receipts_use_global_chat_source():
    """Terminal/internal-PTY receipts must name Alice global chat as source."""
    sources = [
        _REPO / "Applications" / "sifta_matrix_terminal.py",
        _REPO / "System" / "swarm_terminal_organ.py",
        _REPO / "System" / "swarm_tool_router.py",
    ]
    code = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources)
    assert "alice_global_chat_terminal" in code
    assert '"source": "matrix_terminal"' not in code
    assert '"source": "macos_terminal_front_tab"' not in code
    assert "source=macos_terminal_front_tab" not in code


import re as _re

_TALK = _REPO / "Applications" / "sifta_talk_to_alice_widget.py"
_MATRIX = _REPO / "Applications" / "sifta_matrix_terminal.py"
_SERVICE = _REPO / "System" / "grok_pty_service.py"


def _names_imported_from_matrix() -> set[str]:
    """Every name the talk widget imports from sifta_matrix_terminal (the grok route)."""
    talk = _TALK.read_text(encoding="utf-8", errors="replace")
    names: set[str] = set()
    # multi-line:  from Applications.sifta_matrix_terminal import ( a, b, c )
    for m in _re.finditer(
        r"from Applications\.sifta_matrix_terminal import \(([^)]*)\)", talk
    ):
        for nm in m.group(1).replace("\n", ",").split(","):
            nm = nm.strip()
            if nm:
                names.add(nm)
    # single-line: from Applications.sifta_matrix_terminal import a, b
    for m in _re.finditer(
        r"from Applications\.sifta_matrix_terminal import ([^\n(]+)", talk
    ):
        for nm in m.group(1).split(","):
            nm = nm.strip()
            if nm:
                names.add(nm)
    return names


def _missing_grok_route_imports() -> list[str]:
    imported = _names_imported_from_matrix()
    defined = set(_re.findall(r"^(?:def|class)\s+(\w+)", _MATRIX.read_text(encoding="utf-8", errors="replace"), _re.M))
    if _SERVICE.exists():
        defined |= set(_re.findall(r"^(?:def|class)\s+(\w+)", _SERVICE.read_text(encoding="utf-8", errors="replace"), _re.M))
    return sorted(n for n in imported if n not in defined)


def test_ask_grok_route_has_no_dangling_imports():
    """'ask grok' must work: every function the talk widget imports from
    sifta_matrix_terminal (or the collapse service) must still be DEFINED — so a
    collapse cut can't silently break the grok route with a dangling import."""
    missing = _missing_grok_route_imports()
    assert not missing, (
        f"talk widget imports {missing} from sifta_matrix_terminal but they are no longer "
        "defined there (or in grok_pty_service) — the 'ask grok' route is broken."
    )


if __name__ == "__main__":
    # Runnable without pytest — proves the invariants right now.
    offenders = _launchable_terminal_offenders()
    print(
        "PASS — no launchable terminal surface; global chat is the only one."
        if not offenders
        else f"FAIL — launchable terminal surfaces still in manifest: {offenders}"
    )
    missing = _missing_grok_route_imports()
    print(
        "PASS — ask-grok route imports all resolve (no dangling)."
        if not missing
        else f"FAIL — ask-grok route broken; talk widget imports gone: {missing}"
    )
    print(
        "source=alice_global_chat_terminal gate:",
        "ready to check",
    )
