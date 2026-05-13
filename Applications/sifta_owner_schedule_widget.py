#!/usr/bin/env python3
"""sifta_owner_schedule_widget.py — DEPRECATED compatibility stub.

Architect 2026-05-13 00:30 renamed this app to "Provider Schedule" because
the human is the provider of electricity + hardware to the SIFTA organism.
The real implementation lives at:

    Applications/sifta_provider_schedule_widget.py

This stub re-exports `ProviderScheduleWidget` as `OwnerScheduleWidget` so
any older code path still resolves. New code should import from the new
module directly.
"""
from __future__ import annotations

from Applications.sifta_provider_schedule_widget import (  # noqa: F401
    ProviderScheduleWidget as OwnerScheduleWidget,
    ProviderScheduleWidget,
)

__all__ = ["OwnerScheduleWidget", "ProviderScheduleWidget"]
