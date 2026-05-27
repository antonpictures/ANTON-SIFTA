from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STANDALONE_TERMINAL = _REPO / "Applications" / "sifta_terminal.py"
_MANIFEST = _REPO / "Applications" / "apps_manifest.json"


def test_sifta_terminal_file_is_removed():
    assert not _STANDALONE_TERMINAL.exists(), (
        "Applications/sifta_terminal.py must stay deleted; Alice global chat is "
        "the only terminal surface."
    )


def test_manifest_has_no_sifta_terminal_reference():
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for name, spec in manifest.items():
        if not isinstance(spec, dict):
            continue
        entry_point = str(spec.get("entry_point") or "")
        widget_class = str(spec.get("widget_class") or "")
        if "sifta_terminal.py" in entry_point or widget_class == "SiftaTerminalApp":
            offenders.append(name)

    assert not offenders, (
        "Manifest still references the removed standalone terminal surface: "
        f"{offenders}"
    )
