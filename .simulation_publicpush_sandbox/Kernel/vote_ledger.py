import json
import time
import hashlib
import math
from pathlib import Path

import reputation_engine

VOTES_DIR = Path(__file__).parent / ".sifta_votes"
VOTES_DIR.mkdir(exist_ok=True)

def cast_vote(scar_id: str, voter_id: str, originator_id: str, vote_type: str):
    """
    Appends a behavioral vote to the scar's vote ledger.
    vote_type must be 'CONFIRM' or 'REJECT'
    """
    if not scar_id:
        return
        
    voter_id = voter_id.upper()
    originator_id = originator_id.upper()
    
    if voter_id == originator_id:
        # Agents cannot vote on their own scars
        return
        
    vote_file = VOTES_DIR / f"{scar_id}.votes.log"
    
    # Ensure one vote per agent per scar
    if vote_file.exists():
        try:
            with open(vote_file, "r") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if record.get("voter_id") == voter_id:
                            return # Already voted
                    except Exception:
                        continue
        except Exception:
            pass

    # Record the vote
    voter_rep = reputation_engine.get_reputation(voter_id)
    confidence = voter_rep.get("confidence", 0.1)
    
    # Cryptographic anchor (rudimentary proxy for full Ed25519 signature of payload)
    payload_str = f"{scar_id}:{voter_id}:{vote_type}:{time.time()}"
    signature = hashlib.sha256(payload_str.encode()).hexdigest()
    
    vote_entry = {
        "vote_id": signature,
        "scar_id": scar_id,
        "voter_id": voter_id,
        "vote": vote_type,
        "confidence": confidence,
        "timestamp": int(time.time()),
    }
    
    VOTES_DIR.mkdir(exist_ok=True)
    with open(vote_file, "a") as f:
        f.write(json.dumps(vote_entry) + "\n")
        
    vote_icon = "🟢" if vote_type == "CONFIRM" else "🔴"
    print(f"  [{vote_icon}  VOTE CAST] {voter_id} cast {vote_type} on scar {scar_id[:8]}...")

def get_consensus_metrics(scar_id: str) -> dict:
    """
    Reads the append-only ledger and computes the truth_score multiplier
    using a mathematical damping function (tanh).
    Returns {"multiplier": float, "raw_score": float, "vote_count": int}.
    """
    default_resp = {"multiplier": 1.0, "raw_score": 0.0, "vote_count": 0}
    
    if not scar_id:
        return default_resp
        
    vote_file = VOTES_DIR / f"{scar_id}.votes.log"
    if not vote_file.exists():
        return default_resp
        
    truth_score = 0.0
    vote_count = 0
    vote_timestamps = []
    has_conflict = False
    latest_conflict_ts = 0
    first_vote_ts = None
    vote_types = set()
    
    current_time = time.time()

    try:
        with open(vote_file, "r") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    voter_id = record.get("voter_id", "UNKNOWN")
                    vote = record.get("vote")
                    ts = record.get("timestamp", current_time)
                    
                    vote_timestamps.append(ts)
                    vote_types.add(vote)
                    
                    if first_vote_ts is None:
                        first_vote_ts = ts
                    else:
                        first_vote_ts = min(first_vote_ts, ts)
                        
                    if len(vote_types) > 1:
                        # Swarm disagrees — record latest conflict point
                        latest_conflict_ts = max(latest_conflict_ts, ts)
                        has_conflict = True
                    
                    # Fetch real-time reputation score of the voter
                    voter_score = reputation_engine.get_reputation(voter_id).get("score", 0.5)
                    voter_conf = record.get("confidence", 0.1)
                    
                    vote_val = 1.0 if vote == "CONFIRM" else -1.0
                    
                    truth_score += (vote_val * voter_score * voter_conf)
                    vote_count += 1
                except Exception:
                    continue
    except Exception:
        return default_resp
        
    if vote_count > 0:
        # COLLUSION RESISTANCE (Temporal Clustering Dampener)
        # Group timestamps into 3-second windows. Highly coordinated attacks will land in the same window.
        unique_windows = len(set([int(ts) // 3 for ts in vote_timestamps]))
        diversity_factor = min(1.0, unique_windows / vote_count)
        truth_score *= diversity_factor
        
        # TIME-BASED STABILITY
        # Confidence grows over time if the consensus is unchallenged
        reference_ts = latest_conflict_ts if has_conflict else first_vote_ts
        age_seconds = current_time - reference_ts
        
        # Grow up to 1.5x over the course of 1 hour (3600 seconds) if unchallenged
        stability_bonus = 1.0 + min(0.5, age_seconds / 3600.0)
        truth_score *= stability_bonus
        
    # Scale via tanh for dynamic damping, bounded smoothly.
    multiplier = 1.0 + math.tanh(truth_score)
    final_multiplier = round(max(0.1, min(2.0, multiplier)), 3)
    
    return {
        "multiplier": final_multiplier,
        "raw_score": round(truth_score, 3),
        "vote_count": vote_count
    }
