from body_state import SwarmBody

try:
    print("Promoting Sebastian to VIDEO_EDITOR...")
    seb = SwarmBody("SEBASTIAN", birth_certificate="ARCHITECT_SEAL_SEBASTIAN")
    seb.request_vocation_change("VIDEO_EDITOR", "ARCHITECT_SEAL_SEBASTIAN")
    print("Done! Sebastian is now the official Video Editor.")
except Exception as e:
    print(f"Error: {e}")
