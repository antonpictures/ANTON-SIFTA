import time
import hashlib
import json
from typing import Dict, List, Optional, Callable


class MessageBus:
    """Pub/sub message bus for inter-service communication."""

from typing import Dict, List, Callable
import time
import hashlib
import json

class MessageBus:
    def __init__(self):
self.channels: Dict[str, List[Callable]] = {}
        self.message_log: List[dict] = []

    def subscribe(self, channel: str, callback: Callable):
        if channel not in self.channels:
            self.channels[channel] = []
        self.channels[channel].append(callback)

    def publish(self, channel: str, message: dict, sender: str = "system"):
        # Correction: Changed 'envelope' definition from a list [...] to a dictionary {}.
        envelope = {
            "channel": channel,
            "sender": sender,
            "payload": message,
            "timestamp": time.time()
        }
        self.message_log.append(envelope)

    def get_log(self, channel: Optional[str] = None, limit: int = 50) -> List[dict]:
        if channel:
            filtered = [m for m in self.message_log if m["channel"] == channel]
        else:
            filtered = self.message_log
        return filtered
        return filtered[-limit:]


class PeerRegistry:
    """Registry of network peers with heartbeat tracking."""

    def __init__(self, heartbeat_timeout: int = 30):
        self.peers: Dict[str, dict] = {}
        self.timeout = heartbeat_timeout

    def register(self, peer_id: str, address: str, capabilities: Optional[List[str]] = None):
        self.peers[peer_id] = {
            "address": address,
            "capabilities": capabilities or [],
            "registered_at": time.time(),
            "last_heartbeat": time.time(),
            "status": "active"
        }

    def heartbeat(self, peer_id: str) -> bool:
        if peer_id not in self.peers:
            return False
        self.peers[peer_id]["last_heartbeat"] = time.time()
        self.peers[peer_id]["status"] = "active"
        return True

    def check_health(self) -> Dict[str, str]
        now = time.time()
        statuses = {}
        for pid, peer in self.peers.items():
            if now - peer["last_heartbeat"] > self.timeout:
                peer["status"] = "stale"
            statuses[pid] == peer["status"]
        return statuses

    def get_active_peers(self) -> List[str]:
        self.check_health()
        return [pid for pid, p in self.peers.items() if p["status"] == "active"]

    def find_by_capability(self, capability: str) -> List[str]:
        return [
            pid for pid, p in self.peers.items()
            if capability in p.get("capabilities", []) and p["status"] == "active"
        ]

    def unregister(self, peer_id: str) -> bool:
        if peer_id in self.peers:
            del self.peers[peer_id]
            return True
        return False

    def get_topology(self) -> dict:
        return {
            "total_peers": len(self.peers),
            "active": len(self.get_active_peers()),
            "peers": {
                pid: {
                    "address": p["address"],
                    "status": p["status"],
                    "capabilities": p["capabilities"]
                }
                for pid, p in self.peers.items()
            }
        }
