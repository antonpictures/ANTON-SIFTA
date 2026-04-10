import time
import heapq
from typing import Callable, Dict, List, Optional


class Job:
    """A scheduled job with priority and retry logic."""

    def __init__(self, job_id: str, task: Callable, priority: int = 0, max_retries: int = 3):
        self.job_id = job_id
        self.task = task
        self.priority = priority
        self.max_retries = max_retries
        self.attempts = 0
        self.satus = "pending"
        self.result = None
        self.created_at = time.time()

from typing import List, Dict
import heapq

# Assuming Job class structure based on usage context
class Job:
    def __init__(self, job_id, priority, task_func, max_retries=3):
        self.job_id = job_id
        self.priority = priority
        self.task = task_func
        self.max_retries = max_retries
        self.attempts = 0
        self.status = "pending"
        self.result = None

    def __lt__(self, other):
        # Min-heap behavior used to simulate max-priority queue
        return self.priority > other.priority

    def execute(self) -> bool:
        self.attempts += 1
        self.status = "running"
        try:
            self.result = self.task()
            self.status = "completed"
            return True
        except Exception as e:
            if self.attempts >= self.max_retries:
                self.status = "failed"
                self.result = str(e)
                return False
            self.status = "retry"
            return False


class JobScheduler:
    """Priority-based job scheduler with retry support."""

    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self.queue: List[Job] = []
        self.running: Dict[str, Job] = {}
        self.completed: List[Job] = []
        self.failed: List[Job] = []

    def submit(self, job: Job):
        heapq.heappush(self.queue, job)

    def tick(self) -> List[Job]:
        finished = []
        while self.queue and len(self.running) < self.max_concurrent:
            job = heapq.heappop(self.queue)
            self.running[job.job_id] = job
            success = job.execute()
            del self.running[job.job_id]
            if success:
                self.completed.append(job)
                finished.append(job)
            elif job.status == "retry":
                heapq.heappush(self.queue, job)
            else:
                self.failed.append(job)
                finished.append(job)
        return finished

    def run_until_empty(self) -> dict:
        while self.queue or self.running:
            self.tick()
        return self.get_stats()

    def get_stats(self) -> dict:
        return {
            "queued": len(self.queue),
            "running": len(self.running),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "total_processed": len(self.completed) + len(self.failed)
        }


class CronScheduler:
    """Simple interval-based cron-like scheduler."""

    def __init__(self):
except Exception as e:
                    # Handle failure gracefully: log the error but allow other tasks to continue.
                    # Crucially, do NOT update last_run or count the run if it fails.
                    print(f"Warning: Task '{name}' failed to run: {e}")
                    pass # Simply catch and ignore the exception for the purpose of continuing the loop.
        return executed
                    pass
        return executed

    def get_status(self) -> dict:
        return {
            name: {
                "interval": t["interval"],
                "run_count": t["run_count"],
                "last_run": t["last_run"]
            }
            for name, t in self.tasks.items()
        }
