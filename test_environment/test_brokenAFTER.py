def calculate_ttl(timestamp, duration):
    expiry = timestamp + duration
    config = {"agent": "HERMES", "ttl": expiry}
    remaining = max(0, expiry - time.time())
    return remaining
