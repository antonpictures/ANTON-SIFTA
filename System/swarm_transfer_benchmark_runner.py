import json
import math
import time
import uuid
import random
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str, **kwargs) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kwargs) as f:
            f.write(line)

class TransferBenchmarkRunner:
    """
    Event 129: Uncertainty / Confidence Organ.
    Computes statistical rigor (Agarwal-level) for transfer learning claims.
    Does not declare victory on single trials (N=1). Requires N>=20 and positive CI95 bounds.
    """
    
    def __init__(self, root: Optional[Path] = None):
        self.root = root or Path(".sifta_state")
        self.log_path = self.root / "transfer_confidence_intervals.jsonl"
        self.min_trials_required = 20

    def generate_task_trials(self, task_family: str, n: int) -> List[float]:
        """
        Mock implementation of generating multiple independent task trials.
        In the real loop, this would run Alice's full inference pipeline.
        Returns a list of raw transfer_gain floats.
        """
        gains = []
        # Simulate baseline vs replay runs
        for _ in range(n):
            # For demonstration, we simulate noisy gain
            # In a real system, this calls the actual PFC Basal Ganglia Arbiter
            base_gain = 0.18 if "research" in task_family else 0.05
            noise = random.uniform(-0.1, 0.15)
            gains.append(base_gain + noise)
        return gains

    def evaluate_confidence(
        self, 
        task_family: str, 
        gains: List[float]
    ) -> Dict[str, Any]:
        """
        Computes 95% CI and determines if generalization claim is statistically safe.
        """
        n = len(gains)
        if n == 0:
            return {}
            
        mean_gain = sum(gains) / n
        
        if n > 1:
            variance = sum((x - mean_gain) ** 2 for x in gains) / (n - 1)
            std_dev = math.sqrt(variance)
            # 95% CI using approx z=1.96
            margin = 1.96 * (std_dev / math.sqrt(n))
            ci95_low = mean_gain - margin
            ci95_high = mean_gain + margin
        else:
            std_dev = 0.0
            ci95_low = mean_gain
            ci95_high = mean_gain

        claim_safe = (n >= self.min_trials_required) and (ci95_low > 0)

        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "kind": "TRANSFER_CONFIDENCE_INTERVAL",
            "task_family": task_family,
            "n": n,
            "mean_transfer_gain": round(mean_gain, 4),
            "std_transfer_gain": round(std_dev, 4),
            "ci95_low": round(ci95_low, 4),
            "ci95_high": round(ci95_high, 4),
            "claim_safe": claim_safe
        }

        append_line_locked(
            self.log_path,
            json.dumps(row) + "\n",
            encoding="utf-8"
        )
        return row

    def run_benchmark(self, task_family: str, n: int = 30) -> Dict[str, Any]:
        """
        High-level orchestrator: runs trials, computes CI, logs result.
        """
        gains = self.generate_task_trials(task_family, n)
        return self.evaluate_confidence(task_family, gains)
