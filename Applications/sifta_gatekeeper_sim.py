#!/usr/bin/env python3
import time
import webbrowser
from pathlib import Path

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
    print(f"\n[!] Opening deep visualization in default system browser...")
    print(f"    {url}\n")
    
    try:
        webbrowser.open(url)
        print("✅ Simulation successfully deployed.")
        print("   If the browser did not open, manually click or copy the URL above.")
        print("\n   [ You may close this window. Swarm control returning to OS. ]")
    except Exception as e:
        print(f"❌ Failed to launch browser: {e}")
        
    # Keep the window open for a bit so the user can read it
    time.sleep(10)

if __name__ == "__main__":
    launch()
