import os
import shutil
from pathlib import Path

BENCHMARK_DIR = Path("benchmark_fresh_100")

def unclosed_parens(): return "def compute_val():\n    return (5 * 4\n"
def missing_colon(): return "if True\n    print('yes')\n"
def invalid_ident(): return "class = 5\nprint(class)\n"
def missing_quote(): return "msg = 'unclosed\nprint(msg)\n"
def bad_indent(): return "def foo():\nreturn 10\n"

flaw_generators = [unclosed_parens, missing_colon, invalid_ident, missing_quote, bad_indent]

if __name__ == "__main__":
    if BENCHMARK_DIR.exists():
        shutil.rmtree(BENCHMARK_DIR)
    BENCHMARK_DIR.mkdir()
    
    for i in range(100):
        # Round robin thru generators
        flaw_code = flaw_generators[i % len(flaw_generators)]()
        file_path = BENCHMARK_DIR / f"test_file_{i:03d}.py"
        file_path.write_text(flaw_code, encoding="utf-8")
        
    print(f"Generated 100 fresh syntax errors in {BENCHMARK_DIR}")
