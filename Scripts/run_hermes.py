import subprocess
import time
from pathlib import Path
import sys

# Try to import SwarmBody, fallback to just running
try:
    from body_state import SwarmBody
    agent = SwarmBody("HERMES")
    # V4 uses the compressed pheromones feature but technically the body string works fine
    body_string = agent.generate_body("BENCHMARK_100", "MAC_MINI_8GB", "WORMHOLE_SYNC", style="NOMINAL", action_type="BORN", energy=100)
    body_args = ["--body", body_string]
except Exception as e:
    body_args = []

BENCHMARK_DIR = Path("benchmark_fresh_100")

def run_swarm():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(" SIFTA V4: 100-FILE WORMHOLE PROTOCOL BENCHMARK")
    print(" Agent: HERMES | Tether: M5 NPU (192.168.1.100:11434)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    start_time = time.time()
    
    # We use localhost if 192 doesn't respond quickly, but the user explicitly demanded 192.168.1.100
    cmd = ["python3", "repair.py", str(BENCHMARK_DIR), "--write", "--remote-ollama", "http://192.168.1.100:11434"] + body_args
    
    # Wait, the prompt says M5 is currently listening. We are running on it or near it.
    # Stream the output directly so the user sees the STGM flow!
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    for line in iter(process.stdout.readline, ''):
        sys.stdout.write(line)
        sys.stdout.flush()
        
    process.wait()
    
    elapsed = time.time() - start_time
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f" BENCHMARK COMPLETE (Time: {elapsed:.2f}s)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    run_swarm()
