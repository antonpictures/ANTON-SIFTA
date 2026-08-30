"""Process-local causal attribution and activation epochs for SIFTA."""
from __future__ import annotations

import contextvars
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Mapping


_initiator_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "sifta_initiator_id", default=None
)
_activation_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "sifta_activation_id", default=None
)


def set_initiator(agent_id: str | None) -> contextvars.Token[str | None]:
    return _initiator_var.set(agent_id)


def reset_initiator(token: contextvars.Token[str | None]) -> None:
    _initiator_var.reset(token)


def get_initiator() -> str | None:
    return _initiator_var.get()


@contextmanager
def initiator_scope(agent_id: str | None) -> Iterator[str | None]:
    """Temporarily attribute all nested work to one causal initiator."""
    token = set_initiator(agent_id)
    try:
        yield agent_id
    finally:
        reset_initiator(token)


def new_activation_id() -> str:
    return str(uuid.uuid4())


def get_activation_id() -> str | None:
    return _activation_var.get()


@contextmanager
def activation_scope(activation_id: str | None = None) -> Iterator[str]:
    """Create or propagate one epoch across nested work and async tasks."""
    epoch = activation_id or new_activation_id()
    token = _activation_var.set(epoch)
    try:
        yield epoch
    finally:
        _activation_var.reset(token)


def stamp_context(row: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a receipt and add current causal fields without overwriting them."""
    stamped = dict(row)
    initiator_id = get_initiator()
    activation_id = get_activation_id()
    if initiator_id:
        stamped.setdefault("initiator_id", initiator_id)
    if activation_id:
        stamped.setdefault("activation_id", activation_id)
    return stamped
