# 1. Construct the log entry dictionary
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level.upper(),
        "message": message,
        "context": context or {}
    }
    
    # --- Rotation Check ---
    if self.entry_count >= self.max_entries:
        print(f"Warning: Log limit of {self.max_entries} entries reached. Flushing and resetting.")
        
        # 1. Define the name for the rotation file (e.g., app.log.10)
        rotated_path = self.log_path.with_suffix(f".{self.entry_count}")
        
        # 2. Rename the current log file to the rotation name (Source -> Rotated)
        try:
            self.log_path.rename(rotated_path)
            
            # Reset the internal path handler to the base name for new logs
            self.log_path = self.log_path.with_suffix("") 
            
            # 3. Archive the previously rotated file (Optional retention policy)
            archive_path = rotated_path.with_suffix(".old")
            if archive_path.exists(): 
                # Handle old file cleanup logic here if needed
                pass 

            # 4. Reset state counters
            self.entry_count = 0
            # (File handler must be re-initialized/reopened here in a real system)
            
        except FileNotFoundError:
            print("Error: Log file not found during rotation.")
            # If rotation fails, we attempt to proceed, but state might be inconsistent.
            pass
            
    # --- Writing the Entry ---
    try:
        # Open/Write entry regardless of whether rotation occurred or not
        with open(self.log_path, "a") as f:
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
