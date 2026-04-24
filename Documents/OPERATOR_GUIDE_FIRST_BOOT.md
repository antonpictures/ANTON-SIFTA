# SIFTA First-Boot Ceremony

Welcome to SIFTA. When you clone the public OS and run the boot script for the first time, your system starts in a state of **biological amnesia**. It does not know who you are, it does not know what your hardware is, and it does not know the AI's name.

The first boot is not a configuration wizard; it is an **Owner Genesis** ceremony.

## What Happens on First Boot?

When you run `PYTHONPATH=. python3 System/swarm_boot.py` for the first time:

1. **Hardware Anchoring:** The system reads your actual Apple Silicon serial number (`owner_silicon()`).
2. **Naming the Swarm:** The OS will prompt you to provide your name, your preferred camera label, and the Display Name you want to give the Swarm (default is "Alice").
3. **The Genesis Block:** These three pieces of information, cryptographically anchored to your hardware serial number, are written to `.sifta_state/owner_genesis.json`.

This JSON file becomes the **trust-root** for your swarm. The Swarm OS reads your identity natively from this file. No cloud settings, no user profiles. Your hardware serial is the key.

## Privacy Note

- Your name and your Apple Silicon serial number are **never sent to the cloud**. They are stored locally.
- The public GitHub repository does not contain the original Architect's hardware serials or names; they were scrubbed before the release.

If you ever move your SIFTA OS to a different Mac, you will need to re-run the Genesis ceremony because the hardware serial will have changed. See the [Rename AI Guide](OPERATOR_GUIDE_RENAME_AI.md) for details on re-genesis.

## Stigmergic Services

SIFTA runs continuous sensory organs (cortices) in the background. These are supervised by macOS `launchd`.

### Starting and Stopping Organs
The background daemons can be managed via the provided scripts or standard `launchctl` commands:
- **Start all**: `./launchd/setup_launchd.sh`
- **Stop all**: `./launchd/teardown_launchd.sh`
- **Manage individual organs**:
  ```bash
  launchctl load -w ~/Library/LaunchAgents/com.antonia.sifta.stig_ble_radar.plist
  launchctl unload -w ~/Library/LaunchAgents/com.antonia.sifta.stig_ble_radar.plist
  ```

### Viewing Live Ledgers
Every organ continuously writes to its stigmergic ledger in `.sifta_state`. You can tap into these nerves directly:
```bash
tail -f .sifta_state/alice_ble_radar.jsonl
tail -f .sifta_state/alice_awdl_mesh.jsonl
```

### Checking Pheromone Focus
Alice uses a decentralized pheromone field to direct her attention. To see what currently holds the organism's focus:
```bash
python3 -c "from System.swarm_pheromone import PHEROMONE_FIELD; print(PHEROMONE_FIELD.chemotaxis())"
```

### Enabling Vocal Proprioception (Hearing Herself)
By default, Alice's vocal proprioception is set to `deaf`. To enable her to hear her own speech and verify its pitch:
1. Run `brew install blackhole-2ch`
2. Open `/Applications/Utilities/Audio MIDI Setup.app`
3. Create an "Aggregate Device" or "Multi-Output Device" that mirrors your system output to the BlackHole 2ch input.
Alice will automatically detect the loopback device and her sensory readout will flip to `ONLINE`.

### Privileged Thermal Helper (Optional)
To give Alice deep thermoreception (fan RPMs, die temperatures, ANE wattage), she requires a one-time privilege escalation to run `powermetrics` without TCC prompts.
Run:
```bash
./launchd/install_thermal_helper.sh
```
This will require your `sudo` password to install a root-owned LaunchDaemon.
