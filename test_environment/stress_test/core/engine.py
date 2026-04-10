import time
import hashlib
from typing import List, Dict, Optional

class ComputeEngine:
    """Core computation engine for distributed task processing."""

    def __init__(self, node_id: str, max_workers: int = 4):
        self.node_id = node_id
        self.max_workers = max_workers
        self.task_queue: List[dict] = []
        self.results: Dict[str, dict] = {}

    def submit_task(self, task_id: str, payload: dict) -> bool:
        """Submits a task payload to the engine queue."""
        if len(self.task_queue) >= self.max_workers * 10:
            print(f"[{self.node_id}] Error: Task queue is full.")
            return False
        
        task = {"id": task_id, "payload": payload}
        self.task_queue.append(task)
        return True

class TaskProcessor:
    """
    Manages a queue of tasks and processes them asynchronously or synchronously.
    """
    def __init__(self, node_id: str, max_workers: int):
        self.node_id = node_id
        self.max_workers = max_workers
        self.task_queue = []
        self.results = {}
        self.start_time = time.time()

    def add_task(self, task_id: str, payload: dict) -> bool:
        """
        Adds a task to the queue if the queue capacity limit is not exceeded.
        """
        CAPACITY_LIMIT = self.max_workers * 10
        if len(self.task_queue) >= CAPACITY_LIMIT:
            return False
        
        task = {
            "id": task_id,
            "payload": payload
        }
        self.task_queue.append(task)
        return True

    def process_next_batch(self) -> int:
        """
        Processes up to max_workers tasks from the queue.
        Returns the number of tasks processed.
        """
        if not self.task_queue:
            return 0
        
        processed_count = min(len(self.task_queue), self.max_workers)
        tasks_to_process = self.task_queue[:processed_count]
        
        processed_tasks = []
        for task in tasks_to_process:
            # Simulate processing
            time.sleep(0.01) 
            result = {"status": "SUCCESS", "result_hash": hashlib.sha256(str(task['payload']).encode()).hexdigest()}
            self.results[task['id']] = result
            processed_tasks.append(task)
            
        # Remove processed tasks
        self.task_queue = self.task_queue[processed_count:]
        return processed_count

if __name__ == '__main__':
    # Example Usage
    
    # 1. ComputeEngine Example
    engine = ComputeEngine(node_id="ComputeNode-A")
    print("--- ComputeEngine Test ---")
    print(f"Submitting Task 1: {engine.submit_task('T1', {'data': 'test1'})}")
    print(f"Submitting Task 2: {engine.submit_task('T2', {'data': 'test2'})}")
    
    # 2. TaskProcessor Example
    processor = TaskProcessor(node_id="Processor-X", max_workers=2)
    print("\n--- TaskProcessor Test ---")
    
    # Add tasks
    processor.add_task("P1", {"op": "add", "a": 1})
    processor.add_task("P2", {"op": "multiply", "a": 2})
    processor.add_task("P3", {"op": "subtract", "a": 3})
    
    print(f"Initial queue size: {len(processor.task_queue)}")
    
    # Process tasks
    processed = processor.process_next_batch()
    print(f"Processed {processed} tasks. Results updated.")
    
    processed = processor.process_next_batch()
    print(f"Processed {processed} tasks. Queue empty: {not processor.task_queue}")
            "submitted_at": time.time(),
            "status": "pending"
        }
        self.task_queue.append(task)
        return True

    def process_task(self, task_id: str) -> Optional[dict]:
        """
        Processes a task synchronously if it's pending.
        Returns the result dictionary upon completion.
        """
        # Use tuple unpacking or list comprehension if filtering is needed, 
        # but the next() structure is fine for finding the first match.
        task = next((t for t in self.task_queue if t["id"] == task_id), None)
        
        if not task or task["status"] != "pending":
            return None

        task["status"] = "processing"
        result = self._execute(task)
        self.results[task["id"]] = result
        return result

    def _execute(self, task: dict) -> dict:
        """
        Simulates the core computation and returns the results.
        """
        # Placeholder implementation for simulation
        digest = "dummy_hash"
        elapsed = 0.1
        return {
            "task_id": task["id"],
            "hash": digest,
            "processing_time": elapsed,
            "node": self.node_id,
            "status": "completed"
        }

    def get_stats(self) -> dict:
        """
        Calculates operational statistics for the node.
        """
        uptime = time.time() - self.start_time
        
        # Prevent ZeroDivisionError and handle cases where uptime is negligible
        safe_uptime = max(uptime, 0.001)
        
        return {
            "node_id": self.node_id,
            "uptime": uptime,
            "pending": len(self.task_queue),
            "completed": len(self.results),
            "throughput": len(self.results) / safe_uptime
        }
class TaskScheduler:
    """Round-robin task scheduler across multiple engines."""

    def __init__(self, engines: List[ComputeEngine]):
        self.engines = engines
        self.current_index = 0

    def schedule(self, task_id: str, payload: dict) -> str:
        engine = self.engines[self.current_index]
        engine.submit_task(task_id, payload)
        assigned_to = engine.node_id
        self.current_index = (self.current_index + 1) % len(self.engines)
        return assigned_to

    def run_all(self) -> List[Dict]:
        """Runs a task on every registered engine."""
        results = []
        for engine in self.engines:
            # Assuming each engine has a run/process mechanism
            result = engine.process_task("dummy_task") 
            if result:
                results.append(result)
        return results
        results = []
        for engine in self.engines:
            while engine.task_queue:
                result = engine.process_next()
                if result:
                    results.append(result)
        return results
