#!/usr/bin/env python3
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _route_url_to_alice_browser(url: str) -> bool:
    try:
        state = _REPO / ".sifta_state"
        state.mkdir(parents=True, exist_ok=True)
        (state / "alice_browser_open_url.txt").write_text(str(url), encoding="utf-8")
        (state / "alice_browser_open_url_new_tab.flag").write_text("1\n", encoding="utf-8")
        (state / "alice_browser_alice_only.flag").write_text(
            f"{time.time()}\n{url}\n",
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def launch():
    print("═" * 60)
    print(" SIFTA SIMULATIONS: Vector 11 Threshold Topology ")
    print("═" * 60)
    print("\n[+] Initializing Lagrangian stress models...")
    time.sleep(0.5)
    print("[+] Binding constraint compression states...")
    time.sleep(0.5)
    print("[+] Rendering topological mesh...")
    
    file_path = Path(__file__).resolve().parent.parent / "Simulations" / "gatekeeper_vector11_topology.html"
    
    url = f"file://{file_path}"
    print(f"\n[!] Sending deep visualization to Alice Browser...")
    print(f"    {url}\n")
    
    if _route_url_to_alice_browser(url):
        print("✅ Simulation successfully deployed.")
        print("   Alice Browser will consume the URL drop inside SIFTA.")
        print("\n   [ You may close this window. Swarm control returning to OS. ]")
    else:
        print("❌ Failed to write Alice Browser URL drop.")
        
    # Keep the window open for a bit so the user can read it
    time.sleep(10)

if __name__ == "__main__":
    launch()
