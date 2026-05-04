from System.dopamine_reward_loop import process_architect_reaction
from System.swarm_multi_gate_replay_policy import current_gate_state
from System.swarm_dopamine_critic_organ import tail_critic_rows

print("Gate state before:", current_gate_state())

# Fire structured feedback (equivalent to clicking thumbs up)
process_architect_reaction("[👍 STRUCTURED FEEDBACK]", alice_preceding_text="Test", structured_score=1.0)

rows = tail_critic_rows(1)
print("Critic log row:")
if rows:
    print(rows[0])
else:
    print("No rows logged!")

print("Gate state after:", current_gate_state())
