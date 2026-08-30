from __future__ import annotations

import asyncio

from System import swarm_context


def _deep_context_read() -> tuple[str | None, str | None]:
    return swarm_context.get_initiator(), swarm_context.get_activation_id()


def test_nested_calls_read_and_restore_causal_context() -> None:
    assert _deep_context_read() == (None, None)

    with swarm_context.initiator_scope("research_arm"):
        with swarm_context.activation_scope("activation-1"):
            assert _deep_context_read() == ("research_arm", "activation-1")
            with swarm_context.initiator_scope("maintenance_arm"):
                assert _deep_context_read() == ("maintenance_arm", "activation-1")
            assert _deep_context_read() == ("research_arm", "activation-1")

    assert _deep_context_read() == (None, None)


def test_async_tasks_keep_independent_initiators() -> None:
    async def read_as(agent_id: str) -> tuple[str | None, str | None]:
        with swarm_context.initiator_scope(agent_id), swarm_context.activation_scope(agent_id):
            await asyncio.sleep(0)
            return _deep_context_read()

    async def gather() -> list[tuple[str | None, str | None]]:
        return list(await asyncio.gather(read_as("one"), read_as("two")))

    assert asyncio.run(gather()) == [("one", "one"), ("two", "two")]


def test_stamp_context_does_not_overwrite_explicit_receipt_fields() -> None:
    with swarm_context.initiator_scope("body"), swarm_context.activation_scope("epoch"):
        stamped = swarm_context.stamp_context({"event": "tick"})
        explicit = swarm_context.stamp_context(
            {"initiator_id": "owner", "activation_id": "owner-epoch"}
        )

    assert stamped == {
        "event": "tick",
        "initiator_id": "body",
        "activation_id": "epoch",
    }
    assert explicit == {"initiator_id": "owner", "activation_id": "owner-epoch"}
