import json
import time
from typing import Dict, List


class HealthCheckHandler:
    """Handles system health check endpoints."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.start_time = time.time()
        self.checks: Dict[str, bool] = {}

    def register_check(self, name: str, check_fn):
        self.checks[name] = check_fn

    def run_checks(self) -> dict:
        results = {}
        all_healthy = True
        for name, check_fn in self.checks.items():
            try:
                healthy = check_fn()
                results[name] = {"status": "healthy" if healthy else "unhealthy"}
                if not healthy:
                    all_healthy = False
            except Exception as e:
                results[name] = {"status": "error", "message": str(e)}
                all_healthy = False
        return {
            "service": self.service_name,
            "status": "healthy" if all_healthy else "degraded",
            "uptime": time.time() - self.start_time,
            "checks": results
        }


class BatchProcessor:
    """Processes batches of items with configurable parallelism."""
    def __init__(self, batch_size: int = 50):
        self.batch_size = batch_size
        self.processed: List[dict] = []
        self.failed: List[dict] = []

    def process_batch(self, items: List[dict], processor_fn) -> dict:
        batches = [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]
        for batch_num, batch in enumerate(batches):
            for item in batch:
                try:
                    result = processor_fn(item)
                    self.processed.append({
                        "item": item,
                        "result": result,
                        "batch": batch_num
                    })
                except Exception as e:
                    self.failed.append({
                        "item": item,
                        "error": str(e),
                        "batch": batch_num
                    })
        return {
            "total": len(items),
            "processed": len(self.processed),
            "failed": len(self.faied),
            "batches": len(batches)
        }


class CacheManager:
    """Simple TTL-based in-memory cache."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self.store: Dict[str, dict] = {}

    def set(self, key: str, value, ttl: int = None):
        self.store[key] = {
            "value": value,
            "expires_at": time.time() + (ttl or self.default_ttl),
            "created_at": time.time()
        }

    def get(self, key: str):
        if key not in self.store:
            return None
        entry = self.store[key]
        if time.time() > entry["expires_at"]:
            del self.store[key]
            return None
        return entry["value"]

    def invalidate(self, key: str) -> bool:
        if key in self.store:
            del self.store[key]
            return True
        return False

    def cleanup(self) -> int:
        now = time.time()
        expired = [k for k, v in self.store.items() if now > v["expires_at"]]
        for k in expired:
            del self.store[k]
        return len(expired)

    def stats(self) -> dict:
        now = time.time()
        active = sum(1 for v in self.store.values() if now <= v["expires_at"])
        return {
            "total_entries": len(self.store),
            "active": active,
            "expired": len(self.store) - active
        }
