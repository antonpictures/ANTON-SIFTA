"""Compatibility alias for the Claude swimmer arm.

The tournament language names this organ ``claude_swimmer_arm``. The operational
implementation lives in ``System.swarm_claude_arm`` so the body loop can keep
its current ``claude_arm`` wiring. This module keeps the canonical alias alive.
"""

from __future__ import annotations

from .swarm_claude_arm import *  # noqa: F401,F403

