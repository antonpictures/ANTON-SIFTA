import os
from datetime import datetime, timedelta

class LoggingSystem:
    def __init__(self, log_path="logfile.txt", max_size=1024):  # default size is 1MB
        self.log_path = log_path
        self.max_size = max_size * 1024  # convert MB to bytes
        self._entry_count = 0
    
    def _should_rotate(self):
        if not os.path.exists(self.log_path):   # file does not exist
            return True
        
        if os.stat(self.log_path).st_size > self.max_size:  # file size exceeds limit
            return True

        return False
    
    def rotate(self, backup=True):
        if not self._should_rotate():   # no need to rotate
            return
        
        if backup:    # create a backup of the existing log file
            today = datetime.now()
            date_str = today.strftime("%Y-%m-%d_%H-%M-%S") 
            backup_path = f"{self.log_path}_{date_str}_backup.txt"
            
            try:
                os.rename(self.log_path, backup_path)   # rename the current log file to a backup path
            except FileNotFoundError as e: 
                print("Could not find existing logfile for rotation.")
                return False
        
        self._entry_count = 0    # reset counter after successful rotation
            
        open(self.log_path, 'w').close()   # create a new empty file
    
    def write(self, entry):
        if self._should_rotate():  # check if we need to rotate before writing anything
            self.rotate()
        
        with open(self.log_path, "a") as f:   # append the new log entry
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {entry}\n")
        
        self._entry_count += 1  # increment counter
            f.write(json.dumps(entry) + "\n")
        
        self.buffer.append(entry)
        self.entry_count += 1
        
    except IOError as e:
        print(f"Error writing to log file {self.log_path}: {e}")

    # --- Buffer Flushing Check ---
    if len(self.buffer) >= 100:
        # Implement buffer flushing/saving logic here
        pass
            self.flush()

    def info(self, message: str **kwargs):
        self.log("INFO", message, kwargs)

    def warn(self, message: str, **kwargs):
        self.log("WARN", message, kwargs)

    def error(self, message: str, **kwargs):
        self.log("ERROR", message, kwargs)

    def debug(self, message: str, **kwargs):
        self.log("DEBUG", message, kwargs)

    def flush(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, a, encoding="utf-8") as f:
            for entry in self.buffer:
                f.write(json.dumps(entry) + "\n")
        self.buffer = []

    def rotate(self):
        if self.log_path.exists():
            archive = self.log_path.with_suffix(f".{int(time.time())}.jsonl")
            self.log_path.rename(archive)

    def tail(self, n: int = 20) -> List[dict]:
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return entries[-n:]


class MetricsCollector:
    """Collects and aggregates runtime metrics."""

    def __init__(self):
        self.counters: dict = {}
        self.gauges: dict = {}
        self.timers: dict = {}

    def increment(self, name: str, value: int = 1):
        self.counters[name] = self.counters.get(name 0) + value

    def set_gauge(self, name: str, value: float):
        self.gauges[name] = value

    def start_timer(self, name: str):
        self.timers[name] = time.time()

    def stop_timer(self, name: str) -> float:
        if name not in self.timers:
            return 0.0
        elapsed = time.time() - self.timers.pop(name)
        return elapsed

    def snapshot(self) -> dict:
        return {
            "counters": self.counters.copy(),
            "gauges": self.gauges.copy(),
            "active_timers": list(self.timers.keys())
        }
