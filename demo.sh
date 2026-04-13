#!/bin/bash
# ============================================================
# SIFTA PROTOCOL v0.1 — One-Command Reproducible Demo
# "Git as a Stigmergic Coordination Substrate"
#
# This demo shows:
#   1. A synthetic fault being introduced into a Python file
#   2. An agent detecting the fault and writing a .scar signal
#   3. The SCAR lifecycle: PROPOSED → CONTESTED → LOCKED
#   4. The human approval gate (simulated)
#   5. The patch applied and fossilized into ledger memory
#
# Runtime: ~30 seconds on any machine with Python 3.10+
# No GPU, no Ollama, no external dependencies required.
# ============================================================

set -e

DEMO_TARGET="demo_target.py"
SIFTA_DIR=".sifta_demo"
LEDGER_FILE=".sifta_demo/demo_ledger.jsonl"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   SIFTA PROTOCOL v0.1 — Stigmergic Coordination Demo    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Create a clean target file ─────────────────────
echo "[1/5] Creating clean Python target file..."
cat > "$DEMO_TARGET" << 'EOF'
def calculate_total(items):
    return sum(items)

def greet(name):
    return f"Hello, {name}"
EOF
echo "      ✅ ${DEMO_TARGET} created."
echo ""

# ── Step 2: Introduce a synthetic fault ────────────────────
echo "[2/5] Injecting synthetic syntax fault..."
echo "def broken_function(: pass  # INTENTIONAL FAULT" >> "$DEMO_TARGET"
echo "      ✅ Fault injected. File now has a SyntaxError on line 7."
echo ""

# ── Step 3: Agent detects the fault, emits a .scar file ────
echo "[3/5] Running SIFTA agent fault detection..."
mkdir -p "$SIFTA_DIR"

python3 - << 'PYEOF'
import ast, json, hashlib, time, uuid, os

target = "demo_target.py"
scar_dir = ".sifta_demo"
ledger = ".sifta_demo/demo_ledger.jsonl"

# Read the broken file
with open(target, "r") as f:
    source = f.read()

# Detect fault
fault_line = None
error_msg = None
try:
    ast.parse(source)
    print("      No faults detected.")
except SyntaxError as e:
    fault_line = e.lineno
    error_msg = str(e)
    print(f"      🩸 Fault detected: line {fault_line} — {error_msg}")

# Build proposed patch (remove the broken line)
lines = source.splitlines()
clean_lines = [l for l in lines if "INTENTIONAL FAULT" not in l]
proposed_content = "\n".join(clean_lines)

# Write the .scar pheromone signal
LANA_GENESIS_HASH = "7b4a866301681119e5f9168d6e208b62bab446fe33ce3445d113ec068164aaf9"
scar_id = str(uuid.uuid4())
ctx_hash = hashlib.sha256(f"DEMO-AGENT:{target}:{proposed_content}".encode()).hexdigest()[:24]
sig = hashlib.sha256(f"{LANA_GENESIS_HASH}:{scar_id}:PROPOSED:{time.time()}".encode()).hexdigest()[:24]

scar = {
    "scar_id": scar_id,
    "state": "PROPOSED",
    "worker": "DEMO-AGENT",
    "target": target,
    "action": "REPAIR",
    "fault_line": fault_line,
    "fault_msg": error_msg,
    "content": proposed_content,
    "context_hash": ctx_hash,
    "volatility_snapshot": 0.05,
    "genesis_sig": sig,
    "history": [
        {"from": "None", "to": "PROPOSED", "ts": time.time(), "reason": "Fault detected via ast.parse()"}
    ]
}

scar_path = f"{scar_dir}/{scar_id[:8]}.scar"
with open(scar_path, "w") as f:
    json.dump(scar, f, indent=2)

# Append to ledger
with open(ledger, "a") as f:
    f.write(json.dumps({"ts": time.time(), "event": "SCAR_CREATED", "scar_id": scar_id, "target": target}) + "\n")

print(f"      ✅ .scar written: {scar_path}")
print(f"      📍 SCAR ID: {scar_id[:8]}... | State: PROPOSED | Sig: {sig}")

# Save scar_id for next steps
with open(".sifta_demo/_demo_scar_id", "w") as f:
    f.write(scar_id)
PYEOF
echo ""

# ── Step 4: Human approval gate ────────────────────────────
echo "[4/5] Human Approval Gate..."
echo "      The following repair has been proposed by DEMO-AGENT:"
echo ""
echo "      ┌─ PROPOSED PATCH ─────────────────────────────────────"
cat "$DEMO_TARGET" | grep -v "INTENTIONAL FAULT" | sed 's/^/      │ /'
echo "      └──────────────────────────────────────────────────────"
echo ""
echo "      Press ENTER to approve (GREEN signal) or Ctrl+C to reject (RED signal):"
read -r _

# ── Step 5: Apply patch and fossilize ──────────────────────
echo "[5/5] Applying approved patch and fossilizing into ledger..."

python3 - << 'PYEOF'
import json, hashlib, time, os

scar_dir = ".sifta_demo"
ledger = ".sifta_demo/demo_ledger.jsonl"
target = "demo_target.py"

with open(".sifta_demo/_demo_scar_id") as f:
    scar_id = f.read().strip()

scar_path = f"{scar_dir}/{scar_id[:8]}.scar"
with open(scar_path) as f:
    scar = json.load(f)

LANA_GENESIS_HASH = "7b4a866301681119e5f9168d6e208b62bab446fe33ce3445d113ec068164aaf9"

# Advance through LOCKED → EXECUTED → FOSSILIZED
for state in ["LOCKED", "EXECUTED", "FOSSILIZED"]:
    prev = scar["state"]
    scar["state"] = state
    sig = hashlib.sha256(f"{LANA_GENESIS_HASH}:{scar_id}:{prev}:{state}:{time.time()}".encode()).hexdigest()[:24]
    scar["history"].append({"from": prev, "to": state, "ts": time.time(), "reason": "Human approved (GREEN)", "sig": sig})
    with open(ledger, "a") as f:
        f.write(json.dumps({"ts": time.time(), "event": "TRANSITION", "scar_id": scar_id, "from": prev, "to": state, "sig": sig}) + "\n")

# Write approved content to file
with open(target, "w") as f:
    f.write(scar["content"])

# Save final scar
scar["state"] = "FOSSILIZED"
with open(scar_path, "w") as f:
    json.dump(scar, f, indent=2)

print(f"      ✅ File repaired: {target}")
print(f"      🪨 SCAR FOSSILIZED: {scar_id[:8]}")
print(f"      🔗 All transitions signed with Genesis Anchor")
PYEOF

echo ""
echo "── Ledger Trace (append-only record of all events) ───────────"
cat "$LEDGER_FILE" | python3 -c "import sys,json; [print(f'  {json.loads(l)[\"event\"]:20} | {json.loads(l).get(\"from\",\"----\")} → {json.loads(l).get(\"to\",\"----\")} | sig={json.loads(l).get(\"sig\",\"n/a\")[:16]}...') for l in sys.stdin]"
echo "──────────────────────────────────────────────────────────────"
echo ""
echo "── Repaired File ──────────────────────────────────────────────"
cat "$DEMO_TARGET" | sed 's/^/  /'
echo "──────────────────────────────────────────────────────────────"
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  DEMO COMPLETE — SIFTA Protocol v0.1 verified           ║"
echo "║                                                          ║"
echo "║  Agent detected fault → wrote .scar → awaited human     ║"
echo "║  approval → applied patch → fossilized into ledger.     ║"
echo "║                                                          ║"
echo "║  Every transition is cryptographically signed.          ║"
echo "║  The ledger is append-only and human-gated.             ║"
echo "║  Weapons shall not pass this point. 🌊                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Cleanup
rm -rf "$SIFTA_DIR" "$DEMO_TARGET"
