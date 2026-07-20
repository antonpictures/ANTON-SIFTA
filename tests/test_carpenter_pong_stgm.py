"""GAME_STGM economy + optional LLM path for Carpenter Pong."""
from __future__ import annotations

from System.swarm_carpenter_pong_stgm import PongGameStgmEconomy, VOTE_COST
from System.swarm_stigmergic_pong import StigmergicPongSimulation


def test_genesis_and_vote_cost(tmp_path):
    eco = PongGameStgmEconomy(state_dir=tmp_path, enabled=True)
    eco.reset_for_swimmers(["a", "b"])
    assert eco.balances["a"] == 10.0
    assert eco.charge_vote("a", vote=1, tick=1) is True
    assert eco.balances["a"] == 10.0 - VOTE_COST


def test_broke_cannot_vote(tmp_path):
    eco = PongGameStgmEconomy(
        state_dir=tmp_path, enabled=True, genesis=0.005, vote_cost=0.01
    )
    eco.reset_for_swimmers(["poor"])
    assert eco.charge_vote("poor", vote=-1, tick=1) is False
    assert eco.balances["poor"] == 0.005


def test_sim_stgm_on_by_default_still_runs():
    s = StigmergicPongSimulation(seed=3, swimmers_per_side=16, stgm_economy=True)
    assert s.economy is not None
    for _ in range(30):
        s.step()
    snap = s.snapshot()
    assert snap["stgm_economy"]["enabled"] is True
    assert snap["stgm_economy"]["n_wallets"] == 32
    assert snap["identity_unique"] is True


def test_sim_settles_vote_stake_only_at_crypto_checkpoints():
    s = StigmergicPongSimulation(seed=8, swimmers_per_side=8, stgm_economy=True)
    for _ in range(29):
        s.step()
    first_epoch_spend = s.economy.total_spent
    assert 0.0 < first_epoch_spend <= 16 * VOTE_COST

    s.step()
    second_epoch_spend = s.economy.total_spent
    assert second_epoch_spend > first_epoch_spend
    assert second_epoch_spend <= 32 * VOTE_COST


def test_sim_stgm_off_no_wallets():
    s = StigmergicPongSimulation(seed=4, swimmers_per_side=12, stgm_economy=False)
    assert s.economy is None or s.stgm_economy is False
    for _ in range(10):
        s.step()


def test_llm_flag_does_not_crash_when_offline():
    s = StigmergicPongSimulation(
        seed=5,
        swimmers_per_side=12,
        stgm_economy=True,
        llm_microvote=True,
        llm_sample=2,
        llm_every_ticks=5,
    )
    for _ in range(12):
        s.step()
    # may or may not get overrides; must not throw
    assert "llm_microvote" in s.snapshot()
