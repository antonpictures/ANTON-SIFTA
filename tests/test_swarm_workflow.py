from __future__ import annotations

import asyncio

import pytest

from System import swarm_workflow


def test_pipeline_preserves_order_and_rejects_only_ordinary_errors() -> None:
    async def validate(value: int) -> int:
        await asyncio.sleep(0)
        if value == 2:
            raise swarm_workflow.OrdinaryError("malformed item")
        return value

    def score(value: int) -> int:
        return value * 10

    result = asyncio.run(swarm_workflow.pipeline([1, 2, 3], validate, score))

    assert result == [10, None, 30]


def test_pipeline_propagates_fatal_errors() -> None:
    def fatal(value: int) -> int:
        if value == 2:
            raise swarm_workflow.FatalError("workflow result is untrustworthy")
        return value

    with pytest.raises(swarm_workflow.FatalError):
        asyncio.run(swarm_workflow.pipeline([1, 2, 3], fatal))


def test_parallel_supports_sync_and_async_tasks() -> None:
    async def async_value() -> int:
        await asyncio.sleep(0)
        return 2

    result = asyncio.run(
        swarm_workflow.parallel(
            [
                lambda: 1,
                async_value,
                lambda: (_ for _ in ()).throw(swarm_workflow.OrdinaryError("skip")),
            ]
        )
    )

    assert result == [1, 2, None]


def test_sync_run_works_when_caller_already_has_an_event_loop() -> None:
    async def caller() -> list[int | None]:
        return swarm_workflow.run(swarm_workflow.pipeline([1, 2], lambda value: value + 1))

    assert asyncio.run(caller()) == [2, 3]
