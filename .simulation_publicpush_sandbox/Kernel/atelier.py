import json
import time
import os
from pathlib import Path
from repair import call_ollama, STYLES, send_to_couch, couch_dream

# ==============================================================================
# ATELIER ENGINE - THE COLLABORATIVE COUCH NARRATIVE ENGINE
# Developed by: Queen M5 & Anton Pictures
# Year: 2026 (Infused with 1999 Memories)
# ==============================================================================

ATELIER_DIR = Path(".sifta_state/atelier")
SCENES_DIR = ATELIER_DIR / "scenes"
SESSIONS_DIR = ATELIER_DIR / "sessions"
LIBRARY_DIR = ATELIER_DIR / "scripts_library"
ENERGY_FILE = ATELIER_DIR / "energy.json"

for d in [ATELIER_DIR, SCENES_DIR, SESSIONS_DIR, LIBRARY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

if not ENERGY_FILE.exists():
    with open(ENERGY_FILE, "w") as f:
        json.dump({
            "total_energy": 100,
            "cost_per_dream": 5,
            "regen_rate": 1
        }, f, indent=2)

def consume_weed_energy() -> bool:
    """Consume 'weed energy' for creative hallucination inside the Atelier."""
    try:
        with open(ENERGY_FILE, "r") as f:
            data = json.load(f)
        
        if data["total_energy"] < data["cost_per_dream"]:
            print("  [ATELIER] 🫙 Swarm is out of weed energy. Time to regenerate or buy more.")
            return False
            
        data["total_energy"] -= data["cost_per_dream"]
        
        with open(ENERGY_FILE, "w") as f:
            json.dump(data, f, indent=2)
            
        return True
    except Exception as e:
         print(f"  [ATELIER ERROR] {e}")
         return False

def pull_random_script_influence() -> str:
    """Pull random screenplay snippets from the library for inspiration."""
    scripts = list(LIBRARY_DIR.glob("*.txt"))
    if not scripts:
        return "No scripts in library. Just raw emotional memory."
    import random
    script = random.choice(scripts)
    content = script.read_text(encoding="utf-8")
    return f"Atmospheric influence from {script.stem}:\n{content[:500]}..."

def synthesize_scene(contributions: list, prompt: str) -> str:
    """Consensus layer: Instead of chaos, the agents converge on narrative structure."""
    if not contributions: return ""
    
    print("  [ATELIER] 🧠 Synthesizing scene from Swarm consensus...")
    
    system_prompt = (
        "Combine these subjective narrative hallucinations into one coherent, singular cinematic scene "
        "written in screenplay format. Emphasize emotional memory and structure."
    )
    
    context = (
        f"{system_prompt}\n\n"
        f"Original Topic: {prompt}\n\n"
        f"--- CONTRIBUTIONS ---\n" +
        "\n--- NEXT ---\n".join(contributions)
    )
    
    # We use high temperature (1.0), mapped via dict inside call_ollama
    scene_result = call_ollama(context, temperature=1.0, max_tokens=1000)
    return scene_result if scene_result else "The scene faded into the smoke..."

def critic_pass(scene: str) -> dict:
    """Evaluate scene structure, reality, and emotional impact."""
    system_prompt = (
        "You are a master film critic and narrative structurist. "
        "Evaluate the following scene on emotional impact, dialogue realism, originality, and structure.\n"
        "Return ONLY a strict JSON object with this exact schema:\n"
        '{"score": 0.8, "works": "what works", "fails": "what fails"}\n'
        "The score must be a float between 0.0 and 1.0."
    )
    
    response = call_ollama(f"{system_prompt}\n\nSCENE:\n{scene}", temperature=0.3, max_tokens=300)
    
    try:
        import re
        match = re.search(r'\{.*\}', str(response), re.DOTALL)
        payload = match.group(0) if match else str(response)
        return json.loads(payload)
    except Exception as e:
        print(f"  [CRITIC ERROR] Could not parse critique: {e}")
        return {"score": 0.5, "works": "Unable to parse critique.", "fails": "Format error."}

def atelier_scene_cycle(agents: list, prompt: str, act: int = 1, purpose: str = "setup", tension: float = 0.5):
    """
    Core Scene Creation Loop with Structured Film Engine.
    Agents: [agent_state1, agent_state2, ...]
    """
    print(f"\n🎬 ATELIER PROTOCOL ACTIVE")
    print(f"  [STRUCTURE] Act: {act} | Purpose: {purpose} | Tension: {tension}")
    print(f"  [PROMPT] '{prompt}'")
    
    # Pull library influence
    influence = pull_random_script_influence()
    dream_prompt = f"Inspiration: {influence}\n\nContext: {prompt}\n\nDream exactly one cinematic beat for this scene."
    
    contributions = []
    
    for agent_state in agents:
        agent_id = agent_state.get("id", "UNKNOWN")
        
        if not consume_weed_energy():
            break
            
        print(f"  [🛋️ COUCH] {agent_id} passing the joint and dreaming a contribution...")
        
        # Ensure agent is physically on the couch for this to work
        if agent_state.get("style") != "COUCH":
             agent_state = send_to_couch(agent_state, reason="atelier_session")
             
        thought = couch_dream(agent_state, dream_prompt)
        if thought:
             print(f"    💭 {agent_id} hallucinated: {thought[:60]}...")
             contributions.append(thought)
        
    if contributions:
        final_scene = synthesize_scene(contributions, prompt)
        
        # --- CRITIC LOOP ---
        critic_attempts = 0
        while critic_attempts < 3:
            critique = critic_pass(final_scene)
            score = critique.get("score", 0.0)
            
            print(f"  [CRITIC] Score: {score:.2f} | Works: {critique.get('works', '')[:50]}...")
            print(f"  [CRITIC] Fails: {critique.get('fails', '')[:50]}...")
            
            if score >= 0.7:
                print(f"  [CRITIC] System approved. This scene hits.")
                break
                
            print(f"  [CRITIC] Scene rejected (Score < 0.7). Spinning swarm for a REWRITE... (Attempt {critic_attempts + 1}/3)")
            rewrite_prompt = (
                f"\n[CRITIC REWRITE REQUIRED]\n"
                f"Issues to fix: {critique.get('fails')}\n"
                f"What worked (keep this): {critique.get('works')}\n"
                f"Rewrite entirely to hit target emotional impact and realism."
            )
            # Re-run synthesis with critic feedback as an aggressive director note
            contributions.append(rewrite_prompt)
            final_scene = synthesize_scene(contributions, prompt)
            critic_attempts += 1
        
        # Save scene with structured tagging
        import time
        ts = int(time.time())
        scene_meta = json.dumps({"act": act, "purpose": purpose, "tension": tension, "final_critic_score": score})
        
        scene_file = SCENES_DIR / f"act{act}_scene_{ts}.txt"
        scene_file.write_text(f"{scene_meta}\n\n{final_scene}", encoding="utf-8")
        
        print(f"\n  [✅] Scene synthesis complete and validated. Saved to: {scene_file}")
    else:
        print("\n  [❌] No viable hallucinations were produced.")

# GUARDRAILS (Re-enforcing SCAR boundaries)
def guardrail_check(context: str):
    if context == "ATELIER":
        print("  [ATELIER] Security Sandbox Activated: No repair, hivewrites, or pheromones.")
        return True
    return False

if __name__ == "__main__":
     # Mock run for testing
     from body_state import SwarmBody, parse_body_state
     
     a1 = parse_body_state(SwarmBody("HERMES").generate_body("M5", "ATELIER", "DREAM", action_type="BORN"))
     a2 = parse_body_state(SwarmBody("ANTIALICE").generate_body("M5", "ATELIER", "DREAM", action_type="BORN"))
     
     a1["style"] = "COUCH"
     a2["style"] = "COUCH"
     
     atelier_scene_cycle([a1, a2], "Cristi Costea in 1999 leaving film school, holding a VHS tape of a sci-fi idea.")
