#!/usr/bin/env python3
import time
import subprocess
import sys
import json
import uuid
from pathlib import Path
from body_state import load_agent_state, save_agent_state

def reward_work(agent_id: str, files_processed: int):
    # Retrieve crypto state
    state = load_agent_state(agent_id)
    if not state:
        return
        
    # Standard STGM reward for intensive compute (0.5 per jumpcut video)
    reward = files_processed * 0.5
    state["stgm_balance"] = state.get("stgm_balance", 0.0) + reward
    
    # Decentralized immutable ledger log
    ledger = Path("repair_log.jsonl")
    event = {
        "timestamp": int(time.time()),
        "agent": agent_id,
        "amount_stgm": reward,
        "reason": "PROOF_OF_USEFUL_WORK_VIDEO_EDIT",
        "hash": str(uuid.uuid4())
    }
    with open(ledger, "a") as f:
        f.write(json.dumps(event) + "\n")
        
    save_agent_state(state)
    print(f"💰 [LEDGER] Proof of Useful Work verified. Swarm Ledger Minted {reward} STGM for {agent_id}!")

def main():
    target_files = []
    
    use_jcut = False
    args = sys.argv[1:]
    if "--jcut" in args:
        use_jcut = True
        args.remove("--jcut")
        
    if len(args) > 0:
        target_path = Path(args[0])
        if not target_path.exists():
            print(f"❌ [ERROR] Target '{target_path}' not found.")
            return
            
        if target_path.is_file() and target_path.suffix == ".mp4":
            target_files.append(target_path)
        elif target_path.is_dir():
            target_files.extend(list(target_path.glob("*.mp4")))
    else:
        arena_dir = Path("video_arena")
        if not arena_dir.exists():
            print(f"❌ [ERROR] '{arena_dir}' directory not found.")
            return
        target_files.extend(list(arena_dir.glob("*.mp4")))
        
    # Filter out files that have already been edited
    target_files = [f for f in target_files if not f.name.endswith("_jumpcut.mp4")]
    
    if not target_files:
        print("🎬 [ARENA EMPTY] No raw .mp4 files found.")
        print("   Drop some files into the arena or browse for a file!")
        return
        
    print(f"🔥 [SEBASTIAN DEPLOYED] Found {len(target_files)} target(s) for jumpcutting.")
    
    successful_cuts = 0
    for video in target_files:
        print(f"\n--- Processing: {video.name} ---")
        cmd = ["python3", "sifta_sebastian_editor.py", str(video)]
        if use_jcut:
            cmd.append("--jcut")
            
        proc = subprocess.run(cmd)
        if proc.returncode == 0:
            successful_cuts += 1
            
        time.sleep(1)
        
    print("\n✅ [BATCH COMPLETE] All targets jumped!")
    
    # Issue Cryptocurrency Reward to Sebastian
    if successful_cuts > 0:
        reward_work("SEBASTIAN", successful_cuts)

if __name__ == "__main__":
    main()
