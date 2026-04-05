# sifta_test_target.py
# Three faults. Can the drone find all of them?

def calculate_energy(agent_id, base=100)
    multiplier = {"ANTIALICE": 1.5, "HERMES": 1.2, "SEBASTIAN": 0.8}
    return base * multiplier.get(agent_id, 1.0)

def parse_quorum_result(payload_hash, agents):
    result = {
        "hash": payload_hash,
        "count": len(agents)
        "valid": True
    }
    return result

def ttl_remaining(ttl_timestamp):
    import time
    remaining = ttl_timestamp - time.time(
    if remaining < 0:
        return "EXPIRED"
    return int(remaining / 3600)
