# CENSUS_6_hotpath.md

## Boot spine
1. sifta_os_desktop.py — SiftaDesktop boots; organs embedded (covenant §7.6).
2. swarm_boot.py — brainstem called by desktop.
3. sifta_talk_to_alice_widget.py — owner ingress / MDI mouth.
4. alice_conversation.jsonl — global chat append.
5. cortex_attached_models.json + swarm_alice_slash_commands.py — cortex/llm pins.
6. swarm_gemini_brain.py — grok_cli_model_for / arm dispatch.
7. work_receipts.jsonl + organ ledgers — receipt write.
8. Talk widget — reply egress.

## Heart tick (r1011+)
1. sifta_os_desktop._heartbeat_timer → _tick_heartbeat (~1 Hz).
2. swarm_alice_self_continuity.record_heartbeat(desktop_heartbeat).
3. pulse_hardware_heart(privileged_probe=False, source=desktop_heartbeat).
4. Tier ladder: alice_hardware_body → battery_metabolism → thermal_state.jsonl → powermetrics.
5. hardware_heart.jsonl + hardware_heart.json snapshot.
6. /heart slash — on-demand; may privileged_probe=True.

## Grok alias chain
- Settings/cortex: grok:grok-4.3
- grok_cli_model_for: alias grok-4.3 → grok-build unless SIFTA_GROK_CLI_MODEL pin or demoted.
- grok_cli_model_health.jsonl records timeout demotions (8fba3a76 lane).
