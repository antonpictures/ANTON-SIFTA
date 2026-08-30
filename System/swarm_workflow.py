"""Small deterministic workflow primitives shared by SIFTA organs."""
from __future__ import annotations

import asyncio
import contextvars
import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Iterable, TypeVar


T = TypeVar("T")
R = TypeVar("R")
Stage = Callable[[Any], Any | Awaitable[Any]]


class WorkflowError(Exception):
    """Base class for failures with explicit workflow semantics."""


class OrdinaryError(WorkflowError):
    """Reject one item while allowing the remaining workflow to continue."""


class FatalError(WorkflowError):
    """Abort the entire workflow because its result would be untrustworthy."""


async def _resolve(value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value


async def _run_task(task: Awaitable[T] | Callable[[], T | Awaitable[T]]) -> T | None:
    try:
        value = task() if callable(task) else task
        return await _resolve(value)
    except OrdinaryError:
        return None


async def parallel(
    tasks: Iterable[Awaitable[T] | Callable[[], T | Awaitable[T]]],
) -> list[T | None]:
    """Run independent tasks concurrently and preserve input order.

    OrdinaryError rejects only its task. FatalError and unexpected exceptions
    propagate so callers never receive a deceptively partial success.
    """
    return list(await asyncio.gather(*(_run_task(task) for task in tasks)))


async def pipeline(items: Iterable[T], *stages: Stage) -> list[Any | None]:
    """Pass each item through ordered stages, processing peers concurrently."""
    current: list[Any | None] = list(items)
    for stage in stages:
        positions: list[int] = []
        tasks: list[Callable[[], Any | Awaitable[Any]]] = []
        next_items: list[Any | None] = [None] * len(current)
        for index, item in enumerate(current):
            if item is None:
                continue
            positions.append(index)
            tasks.append(lambda item=item, stage=stage: stage(item))
        for index, result in zip(positions, await parallel(tasks)):
            next_items[index] = result
        current = next_items
    return current


def run(awaitable: Awaitable[R]) -> R:
    """Run a workflow from synchronous code, including inside an active loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    # Public registry APIs are synchronous. Async UI callers use an isolated
    # loop instead of nesting asyncio.run() in their active event loop.
    context = contextvars.copy_context()
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="sifta-workflow") as pool:
        return pool.submit(context.run, asyncio.run, awaitable).result()
