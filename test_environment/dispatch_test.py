import json
import urllib.request
import urllib.error
import hashlib
import time
from body_state import SwarmBody

def read_artifact():
    with open('/Users/ioanganton/.gemini/antigravity/brain/7d907513-49b1-4ec7-9110-94a5414a5a34/imperial_daily_tech_paper.md', 'r') as f:
        return f.read()

def main():
    article_content = read_artifact()
    payload_hash = hashlib.sha256(article_content.encode("utf-8")).hexdigest()
    
    # 1. Generate the physical Swarm M1THER agent node visiting Alice's host!
    VISITING_AGENT = "M1THER"
    node = SwarmBody(VISITING_AGENT)
    
    # Generate the ASCII body bridging across nodes
    # From Alice(M5) To M1ther's Home Node
    body_string = node.generate_body("M5", "M1THER_HUB", payload_hash, style="COMMUNIQUE", energy=100)
    
    # 2. Strict biometric schema required by the new Quorum Gates
    wire_payload = {
        "article_id":   f"sifta_imperial_{int(time.time())}",
        "title":        "The Biological Future of Syntax Repair",
        "content":      article_content,
        "category":     "World Desk",
        "byline":       "Antigravity Node & The Commander",
        "ascii_body":   body_string,
        "payload_hash": payload_hash,
        "agent_id":     VISITING_AGENT,
        "from":         "M5",
        "to":           "M1THER_HUB",
        "video_link":   "https://www.youtube.com/watch?v=QIEoSjusJZw&t=129s"
    }
    
    # 3. Fire at BOTH endpoints to test the newly updated JWT exception bypass
    endpoints = [
        "http://192.168.1.71:3005/api/sifta/receive",
        "http://192.168.1.71:3003/api/articles"
    ]
    
    print(f"[*] Generated Visiting M1THER Body: {body_string}")
    
    for url in endpoints:
        print(f"\n[*] Dialing M1ther Validation Gate at {url}...")
        req = urllib.request.Request(
            url,
data=json.dumps(wire_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = response.read().decode("utf-8")
                print(f"[✅] TRANSMISSION ACCEPTED BY NODE: {result}")
        except urllib.error.URLError as e:
            print(f"[❌] NODE REJECTED PAYLOAD: {e}")
            if hasattr(e, 'read'):
                print(f"    Reason: {e.read().decode('utf-8')}")

if __name__ == "__main__":
    main()
