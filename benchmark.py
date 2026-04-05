import os
import shutil
import subprocess
import time
from pathlib import Path
from body_state import SwarmBody

BENCHMARK_DIR = Path("benchmark_env")

# 10 intentional syntax faults
FLAWS = [
    # 0: missing colon
    """def test_func()\n    return 1\n""",
    # 1: missing closing quote
    """msg = "Hello world\nprint(msg)""",
    # 2: indentation error
    """def foo():\nreturn 5\n""",
    # 3: missing parenthesis
    """print('hello'\n""",
    # 4: invalid syntax (using keyword as variable)
    """class = 5\nprint(class)\n""",
    # 5: unclosed bracket
    """arr = [1, 2, 3\nprint(arr)\n""",
    # 6: unmatched parenthesis
    """def math_op():\n    return (5 + 5\n""",
    # 7: dictionary missing comma
    """data = {'a': 1 'b': 2}\n""",
    # 8: f-string syntax error
    """n = 5\nprint(f"Number is {n)\n""",
    # 9: missing equal sign in assignment
    """x  5\nprint(x)\n"""
]

def setup_benchmark_env():
    if os.path.exists(".sifta_state"): shutil.rmtree(".sifta_state")
    if os.path.exists("CEMETERY"): shutil.rmtree("CEMETERY")
    if os.path.exists(BENCHMARK_DIR): shutil.rmtree(BENCHMARK_DIR)
    
    BENCHMARK_DIR.mkdir()
    
    print(f"Seeding {len(FLAWS)} broken files...")
    for i, flaw_code in enumerate(FLAWS):
        file_path = BENCHMARK_DIR / f"test_file_{i:02d}.py"
        file_path.write_text(flaw_code, encoding="utf-8")

def run_benchmark():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(" ANTON-SIFTA Assay: Autonomous Repair Benchmark")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    setup_benchmark_env()
    
    # Generate the initial agent body with maximum energy
    agent = SwarmBody("REPAIR-DRONE")
    body_string = agent.generate_body("BENCHMARK", "LOCAL", "FIX_THESE", style="NOMINAL", energy=100)
    print(f"\n[DISPATCH] Launching repair drone against {len(FLAWS)} files...\n")
    
    start_time = time.time()
    
    # Force the repair.py script to run and write changes
    result = subprocess.run(
        ["python3", "repair.py", str(BENCHMARK_DIR), "--write", "--body", body_string],
        capture_output=True, text=True
    )
    
    elapsed = time.time() - start_time
    
    print(result.stdout)
    
    if result.stderr:
        print("[ERROR STREAM]", result.stderr)
        
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f" BENCHMARK COMPLETE (Time: {elapsed:.2f}s)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
if __name__ == "__main__":
    run_benchmark()
