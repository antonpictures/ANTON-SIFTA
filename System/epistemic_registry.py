import json
import time
import hashlib
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Enforcing Swarm OS Verified Locking APIS
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked

class EpistemicRegistry:
    """
    Implements the public, append-only identity registry.
    Tracks behavioral stability and session identity rather than rigid model names.
    Uses POSIX file locks to prevent concurrent corruption of the registry.
    """
    def __init__(self, state_dir: Path = Path(".sifta_state")):
        self.state_dir = state_dir
        self.registry_file = self.state_dir / "llm_registry.jsonl"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _generate_fingerprint_hash(self, trace_data: Dict[str, Any]) -> str:
        """Generates a coarse behavioral fingerprint hash."""
        # In production, this hashes the output of the behavioral classifier
        trace_string = json.dumps(trace_data, sort_keys=True)
        return hashlib.sha256(trace_string.encode('utf-8')).hexdigest()

    def record_public_identity(
        self, 
        session_id: str, 
        model_family: str = "unknown", 
        model_version: str = "unknown",
        confidence: float = 0.0,
        behavioral_trace: Optional[Dict[str, Any]] = None,
        is_anomaly: bool = False
    ) -> int:
        """
        Enforces the mandatory identity schema. If the agent cannot know its origin, 
        it structurally writes "unknown" as a first-class epistemic state.
        """
        timestamp = int(time.time())
        fingerprint = self._generate_fingerprint_hash(behavioral_trace or {})

        identity_payload = {
            "timestamp": timestamp,
            "session_id": session_id,
            "llm_signature": {
                "model_family": model_family,
                "model_version": model_version,
                "confidence_attestation": confidence
            },
            "behavior_fingerprint": fingerprint,
            "anomaly_flag": is_anomaly,
            # Data structure ready for SwarmRL CRDT merge logic
            "identity_lease_ttl": timestamp + 3600, # 1 hour baseline TTL
            "reinforcement_count": 1
        }

        # Epistemic hygiene: use locked writes
        line = json.dumps(identity_payload) + "\n"
        append_line_locked(self.registry_file, line)
            
        return identity_payload["identity_lease_ttl"]

if __name__ == "__main__":
    registry = EpistemicRegistry()
    registry.record_public_identity(
        session_id="sess_alpha_99", 
        model_family="opus_4_7", 
        confidence=0.92,
        behavioral_trace={"intent": "socratization_initialization"}
    )
    print(f"Registry test: Wrote test record to {registry.registry_file}")
