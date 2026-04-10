#!/usr/bin/env python3
"""
sifta_consigliere.py — The LLM Advisory Layer

The Consigliere is NOT a queen. It is NOT a controller.
It is a strategic advisor that:
  1. READS global colony state (scars, ledger, logs, reputation)
  2. SYNTHESIZES patterns using an LLM
  3. WRITES proposals/ — never executes directly
  4. Is ALWAYS audited in the task_ledger.db

Biology says: there is no central intelligence in a swarm.
Engineering agrees. The LLM is the advisor. The human is the authority.

Architecture:
    Swarm → produces logs/scars
            ↓
    Consigliere → analyzes patterns (LLM)
            ↓
    Consigliere → writes proposals/
            ↓
    Human → approves/rejects (dashboard)
            ↓
    System → executes deterministically

Usage:
    python sifta_consigliere.py --advise            # Full advisory sweep
    python sifta_consigliere.py --watch              # Continuous advisory loop
    python sifta_consigliere.py --digest             # Text summary only (no proposals)
    python sifta_consigliere.py --model gemma4:latest
"""
import json
import os
import sqlite3
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).parent
STATE_DIR = ROOT_DIR / ".sifta_state"
LEDGER_DB = STATE_DIR / "task_ledger.db"
LOG_PATH = ROOT_DIR / "sifta_log.jsonl"
CONSIGLIERE_LOG = STATE_DIR / "consigliere_log.jsonl"


# ─── 1. COLONY STATE READER ──────────────────────────────────────────────────
# Reads ALL available signals. Never modifies anything.

def read_colony_state() -> dict:
    """
    Comprehensive read of the entire colony state.
    Returns a structured digest suitable for LLM consumption.
    """
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scars": _read_scars(),
        "agents": _read_agents(),
        "reputation": _read_reputation(),
        "recent_logs": _read_recent_logs(limit=30),
        "proposals": _read_proposal_stats(),
        "audit_events": _read_recent_audit(limit=15),
    }
    return state


def _read_scars() -> dict:
    """Scan all territories for scar data."""
    result = {
        "bleeding_count": 0,
        "clean_count": 0,
        "suppressed_count": 0,
        "total_scars": 0,
        "bleeding_details": [],
        "territories": [],
    }

    for sifta_dir in ROOT_DIR.rglob(".sifta"):
        if not sifta_dir.is_dir():
            continue
        rel_path = str(sifta_dir.parent.relative_to(ROOT_DIR))
        if "CEMETERY" in rel_path or "proposals" in rel_path:
            continue

        territory_scars = []
        for scar_file in sifta_dir.glob("*.scar"):
            try:
                data = json.loads(scar_file.read_text(encoding="utf-8"))
                status = data.get("stigmergy", {}).get("status", "UNKNOWN")
                result["total_scars"] += 1

                if status == "BLEEDING":
                    result["bleeding_count"] += 1
                    line = data.get("stigmergy", {}).get("unresolved_fault_line", -1)
                    reason = data.get("stigmergy", {}).get("reason", {})
                    result["bleeding_details"].append({
                        "territory": rel_path,
                        "agent": data.get("agent_id", "UNKNOWN"),
                        "line": line,
                        "error_type": reason.get("type", "?"),
                        "message": reason.get("message", "")[:150],
                        "mark": data.get("mark", "")[:100],
                    })
                elif status in ("CLEAN", "RESOLVED"):
                    result["clean_count"] += 1
                elif status == "SUPPRESSED":
                    result["suppressed_count"] += 1

                territory_scars.append(status)
            except Exception:
                continue

        if territory_scars:
            result["territories"].append({
                "path": rel_path,
                "scars": len(territory_scars),
                "bleeding": territory_scars.count("BLEEDING"),
            })

    return result


def _read_agents() -> list:
    """Read all live agent state files."""
    agents = []
    for p in STATE_DIR.glob("*.json"):
        if p.name in ("hivemind.json",):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if "id" not in data:
                continue
            agents.append({
                "id": data["id"],
                "energy": data.get("energy", 0),
                "style": data.get("style", "UNKNOWN"),
                "history_count": len(data.get("history", [])),
                "last_event": data.get("history", [{}])[-1].get("event", "") if data.get("history") else "",
            })
        except Exception:
            continue
    return agents


def _read_reputation() -> list:
    """Read reputation scores for all agents."""
    rep_dir = ROOT_DIR / ".sifta_reputation"
    reps = []
    if not rep_dir.exists():
        return reps
    for p in rep_dir.glob("*.rep.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            reps.append({
                "agent_id": data.get("agent_id", "?"),
                "score": data.get("score", 0.5),
                "confidence": data.get("confidence", 0.1),
                "successes": data.get("events", {}).get("successful_repairs", 0),
                "failures": data.get("events", {}).get("failed_repairs", 0),
                "false_signals": data.get("events", {}).get("false_signals", 0),
            })
        except Exception:
            continue
    return reps


def _read_recent_logs(limit: int = 30) -> list:
    """Read the most recent swim log events."""
    events = []
    if not LOG_PATH.exists():
        return events
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return events


def _read_proposal_stats() -> dict:
    """Read proposal counts."""
    try:
        import proposal_engine
        return proposal_engine.proposal_stats()
    except Exception:
        return {"pending": 0, "approved": 0, "rejected": 0}


def _read_recent_audit(limit: int = 15) -> list:
    """Read recent audit log entries."""
    events = []
    if not LEDGER_DB.exists():
        return events
    try:
        conn = sqlite3.connect(LEDGER_DB)
        rows = conn.execute(
            "SELECT timestamp, event_type, component, details FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        for row in rows:
            events.append({
                "timestamp": row[0],
                "event_type": row[1],
                "component": row[2],
                "details": row[3],
            })
    except Exception:
        pass
    return events


# ─── 2. LLM ADVISORY SYNTHESIS ───────────────────────────────────────────────
# Sends the colony state to an LLM for pattern analysis.
# The LLM never receives file contents — only structured metadata.

ADVISORY_PROMPT = """[SIFTA CONSIGLIERE — STRATEGIC ADVISORY PROTOCOL]

You are the Consigliere: a strategic advisor for a self-healing code swarm.
You are NOT a controller. You do NOT execute. You ADVISE.

Your role:
1. Analyze the colony state below
2. Identify patterns, risks, and opportunities
3. Generate specific, actionable recommendations
4. Prioritize by urgency (CRITICAL → HIGH → MEDIUM → LOW)

Colony State:
{colony_state}

Output a structured advisory report in this EXACT JSON format:
{{
    "summary": "1-2 sentence colony health assessment",
    "risk_level": "CRITICAL|HIGH|MEDIUM|LOW|NOMINAL",
    "observations": [
        {{
            "type": "PATTERN|RISK|OPPORTUNITY|ANOMALY",
            "priority": "CRITICAL|HIGH|MEDIUM|LOW",
            "description": "What you observed",
            "recommendation": "What should be done",
            "affected": ["list of affected files or agents"]
        }}
    ],
    "strategic_recommendations": [
        "Top-level strategic action items"
    ]
}}

Rules:
- Base analysis ONLY on the data provided. Do not hallucinate files or errors.
- Be specific about line numbers, agents, and territories when available.
- If the colony is healthy, say so. Do not invent problems.
- Output ONLY the JSON. No preamble, no explanation.
"""


def request_advisory(model: str = "gemma4:latest", ollama_base: str = "") -> dict:
    """
    Full advisory cycle:
    1. Read colony state
    2. Send to LLM
    3. Parse response
    4. Audit the advisory event
    5. Return structured advice
    """
    import urllib.request

    colony_state = read_colony_state()

    # Compact the state for token efficiency
    state_str = json.dumps(colony_state, indent=2, default=str)

    # Cap the state to avoid blowing context (~8k tokens)
    if len(state_str) > 12000:
        state_str = state_str[:12000] + "\n... [TRUNCATED — colony state too large for context]"

    prompt = ADVISORY_PROMPT.format(colony_state=state_str)

    base = (ollama_base or "http://localhost:11434").rstrip("/")
    url = f"{base}/api/generate"

    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3,   # Slightly creative for pattern recognition
        "num_predict": 2048,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    print(f"[🧠 CONSIGLIERE] Consulting {model}...")
    print(f"[🧠 CONSIGLIERE] Colony state: {colony_state['scars']['total_scars']} scars, "
          f"{colony_state['scars']['bleeding_count']} bleeding, "
          f"{len(colony_state['agents'])} agents")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            raw_text = result.get("response", "")
    except Exception as e:
        print(f"[🧠 CONSIGLIERE] LLM unreachable: {e}")
        return {"error": str(e), "raw": ""}

    # Parse the LLM response
    advisory = _parse_advisory(raw_text)

    # Audit the event
    _audit_advisory(advisory, model, colony_state)

    return advisory


def _parse_advisory(raw_text: str) -> dict:
    """Extract structured advisory from LLM response."""
    # Try direct JSON parse
    try:
        # Find JSON block in response
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        pass

    # Try to find JSON embedded in text
    try:
        start = raw_text.index("{")
        end = raw_text.rindex("}") + 1
        return json.loads(raw_text[start:end])
    except Exception:
        pass

    # Fallback: return raw text as unstructured advisory
    return {
        "summary": "Advisory returned unstructured response.",
        "risk_level": "UNKNOWN",
        "observations": [],
        "strategic_recommendations": [],
        "raw": raw_text[:2000],
    }


def _audit_advisory(advisory: dict, model: str, colony_state: dict):
    """Log the advisory event for full auditability."""
    # Audit to sifta_audit.py ledger
    try:
        from sifta_audit import record_event
        record_event(
            "CONSIGLIERE_ADVISORY",
            "sifta_consigliere",
            f"Model: {model} | Risk: {advisory.get('risk_level', '?')} | "
            f"Observations: {len(advisory.get('observations', []))} | "
            f"Summary: {advisory.get('summary', '')[:100]}"
        )
    except Exception:
        pass

    # Also append to our own log file
    try:
        entry = {
            "ts": time.time(),
            "model": model,
            "risk_level": advisory.get("risk_level", "?"),
            "observation_count": len(advisory.get("observations", [])),
            "summary": advisory.get("summary", ""),
            "scars_at_time": colony_state.get("scars", {}).get("total_scars", 0),
            "bleeding_at_time": colony_state.get("scars", {}).get("bleeding_count", 0),
        }
        with open(CONSIGLIERE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ─── 3. DISPLAY ──────────────────────────────────────────────────────────────

def display_advisory(advisory: dict):
    """Pretty-print the advisory to the terminal."""
    risk = advisory.get("risk_level", "UNKNOWN")
    risk_colors = {
        "CRITICAL": "\033[91m",  # red
        "HIGH": "\033[93m",      # yellow
        "MEDIUM": "\033[96m",    # cyan
        "LOW": "\033[92m",       # green
        "NOMINAL": "\033[92m",   # green
    }
    color = risk_colors.get(risk, "\033[0m")
    reset = "\033[0m"

    print("\n" + "═" * 70)
    print(f"  🧠 CONSIGLIERE ADVISORY REPORT")
    print("═" * 70)
    print(f"  Risk Level:  {color}{risk}{reset}")
    print(f"  Summary:     {advisory.get('summary', '—')}")
    print("─" * 70)

    observations = advisory.get("observations", [])
    if observations:
        print(f"\n  📋 OBSERVATIONS ({len(observations)}):")
        for i, obs in enumerate(observations, 1):
            priority = obs.get("priority", "?")
            obs_type = obs.get("type", "?")
            p_color = risk_colors.get(priority, "")
            print(f"\n    [{i}] {p_color}{priority}{reset} — {obs_type}")
            print(f"        {obs.get('description', '')}")
            if obs.get("recommendation"):
                print(f"        → {obs['recommendation']}")
            if obs.get("affected"):
                print(f"        ⚡ Affected: {', '.join(obs['affected'])}")
    else:
        print("\n  No observations generated.")

    recs = advisory.get("strategic_recommendations", [])
    if recs:
        print(f"\n  🎯 STRATEGIC RECOMMENDATIONS:")
        for r in recs:
            print(f"    • {r}")

    if advisory.get("raw"):
        print(f"\n  ⚠ RAW (unstructured):\n    {advisory['raw'][:300]}")

    print("\n" + "═" * 70)


def display_digest(colony_state: dict):
    """Print a human-readable colony digest without LLM involvement."""
    scars = colony_state["scars"]
    agents = colony_state["agents"]
    reps = colony_state["reputation"]
    proposals = colony_state["proposals"]

    print("\n" + "═" * 70)
    print("  🐝 COLONY DIGEST — RAW STATE")
    print("═" * 70)

    print(f"\n  SCARS:      {scars['total_scars']} total | "
          f"🩸 {scars['bleeding_count']} bleeding | "
          f"✅ {scars['clean_count']} clean | "
          f"🔇 {scars['suppressed_count']} suppressed")

    print(f"  AGENTS:     {len(agents)} active")
    for a in agents:
        print(f"    • {a['id']} — ⚡{a['energy']} [{a['style']}] "
              f"({a['history_count']} events)")

    print(f"  REPUTATION:")
    for r in reps:
        bar = "█" * int(r["score"] * 20) + "░" * (20 - int(r["score"] * 20))
        print(f"    • {r['agent_id']}: [{bar}] {r['score']:.2f} "
              f"(✓{r['successes']} ✗{r['failures']})")

    print(f"  PROPOSALS:  📋 {proposals.get('pending', 0)} pending | "
          f"✅ {proposals.get('approved', 0)} approved | "
          f"❌ {proposals.get('rejected', 0)} rejected")

    if scars["bleeding_details"]:
        print(f"\n  🩸 ACTIVE WOUNDS:")
        for b in scars["bleeding_details"][:5]:
            print(f"    • {b['territory']} line {b['line']} — "
                  f"{b['error_type']}: {b['message'][:80]}")

    print("\n" + "═" * 70)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SIFTA Consigliere — LLM Advisory Layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The Consigliere reads colony state, synthesizes patterns via LLM,
and generates advisory reports. It NEVER executes. It NEVER modifies files.
It writes to proposals/ and the audit log.

Examples:
    python sifta_consigliere.py --advise
    python sifta_consigliere.py --digest
    python sifta_consigliere.py --watch --interval 60
    python sifta_consigliere.py --advise --model gemma4:latest
        """
    )
    parser.add_argument("--advise", action="store_true",
                        help="Run a full LLM advisory sweep")
    parser.add_argument("--digest", action="store_true",
                        help="Print colony state digest (no LLM)")
    parser.add_argument("--watch", action="store_true",
                        help="Continuous advisory loop")
    parser.add_argument("--interval", type=int, default=120,
                        help="Seconds between watch cycles (default: 120)")
    parser.add_argument("--model", default="gemma4:latest",
                        help="LLM model to use")
    parser.add_argument("--ollama-base", default="",
                        help="Ollama base URL")

    args = parser.parse_args()

    if args.digest:
        state = read_colony_state()
        display_digest(state)

    elif args.advise:
        advisory = request_advisory(model=args.model, ollama_base=args.ollama_base)
        display_advisory(advisory)

    elif args.watch:
        print("[🧠 CONSIGLIERE] Watch mode activated.")
        print(f"[🧠 CONSIGLIERE] Advisory interval: {args.interval}s")
        print("[🧠 CONSIGLIERE] Press Ctrl+C to stop.\n")

        while True:
            try:
                advisory = request_advisory(model=args.model, ollama_base=args.ollama_base)
                display_advisory(advisory)
                print(f"\n[🧠 CONSIGLIERE] Next advisory in {args.interval}s...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n[🧠 CONSIGLIERE] Watch mode terminated.")
                break

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
