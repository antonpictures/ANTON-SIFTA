"""Explicit principal scope for ingress and memory decisions.

Names, aliases, device fingerprints and camera observations are descriptive
signals only.  They are never authentication or authorization evidence.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrincipalScope:
    principal_id: str
    session_id: str
    role: str = "visitor"
    authenticated: bool = False

    @property
    def owner_authority(self) -> bool:
        return self.authenticated and self.role == "owner" and bool(self.principal_id)

    def can_read(self, owner_only: bool = False) -> bool:
        return not owner_only or self.owner_authority

    def can_act(self) -> bool:
        return self.owner_authority


def public_visitor_scope(session_id: str) -> PrincipalScope:
    """Return the non-authoritative scope used by public web chat."""
    return PrincipalScope(
        principal_id=f"visitor:{str(session_id or '').strip()}",
        session_id=str(session_id or ""),
    )


__all__ = ["PrincipalScope", "public_visitor_scope"]
