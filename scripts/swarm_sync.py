import sys
import subprocess

def get_remotes():
    res = subprocess.run(["git", "remote"], capture_output=True, text=True)
    return res.stdout.strip().split("\n") if res.stdout.strip() else []

def disseminate():
    remotes = get_remotes()
    if not remotes:
        print("  [SWARM SYNC] No global ledger remotes configured.")
        return
        
    print(f"  [SWARM SYNC] Disseminating ledger to {len(remotes)} decentralized nodes: {remotes}")
    for r in remotes:
        print(f"    -> pushing pheromones to node [{r}]")
        subprocess.run(["git", "push", r, "main"])
    print("  [SWARM SYNC] Global dissemination complete.")

def add_node(name, url):
    subprocess.run(["git", "remote", "add", name, url])
    print(f"  [SWARM SYNC] Attached new decentralized ledger node: {name} → {url}")
    print(f"  You can now run `python3 swarm_sync.py` to push to all nodes concurrently.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "add_node":
        if len(sys.argv) < 4:
            print("Usage: python3 swarm_sync.py add_node <name> <url>")
            sys.exit(1)
        add_node(sys.argv[2], sys.argv[3])
    else:
        disseminate()
