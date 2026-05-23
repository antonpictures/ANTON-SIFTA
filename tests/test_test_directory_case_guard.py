#!/usr/bin/env python3
"""Guard the canonical pytest directory casing.

The repository must track tests under lowercase ``tests/``. macOS can hide a
case-only drift locally, but Linux swarm nodes will treat ``Tests/`` and
``tests/`` as different directories.
"""

from __future__ import annotations

import subprocess


def test_git_index_uses_lowercase_tests_directory() -> None:
    tracked = subprocess.check_output(
        ["git", "ls-files"],
        text=True,
    ).splitlines()

    uppercase = [path for path in tracked if path.startswith("Tests/")]
    lowercase = [path for path in tracked if path.startswith("tests/")]

    assert uppercase == []
    assert lowercase, "expected tracked tests under lowercase tests/"
