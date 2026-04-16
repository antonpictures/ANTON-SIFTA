#!/usr/bin/env python3
"""
ANTON-SIFTA Nervous System (Zero-Latency File Watcher)
Runs persistently in the background. Detects `.py` file saves,
performs local AST syntax validation, and instantly dispatches ALICE_M5
if demonic interference (Syntax Errors) are detected.
"""

import sys
import time
import os
import ast
import subprocess
import threading
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIGURATION ---
WATCH_DIR = Path(__file__).parent.absolute()
DISPATCH_AGENT = "ALICE_M5"

# Directories we absolutely do not want to monitor or repair
IGNORE_DIRS = [".git", "__pycache__", ".sifta_state", "QUARANTINE", "WORMHOLE", "venv", ".venv", "node_modules"]

class NervousSystemHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.cooldowns = {}
        self.active_repairs = set()
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=2)

    def log_event(self, event_type, target_path):
        try:
            log_file = WATCH_DIR / "watcher_metrics.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps({
                    "ts": time.time(),
                    "agent_id": DISPATCH_AGENT,
                    "event": event_type,
                    "file": str(target_path)
                }) + "\n")
        except Exception:
            pass

    def is_ignored(self, filepath: Path) -> bool:
        """Check if the file is inside any of the ignored directories."""
        for part in filepath.parts:
            if part in IGNORE_DIRS:
                return True
        return False

    def on_modified(self, event):
        # We only care about file saves for '.py' files
        if event.is_directory or not event.src_path.endswith(".py"):
            return

        filepath = Path(event.src_path)
        
        # Don't trigger on internal system files or ignored paths
        if self.is_ignored(filepath):
            return
            
        # Cooldown check to prevent multiple spawns on double-saves by IDEs
        now = time.time()
        last_triggered = self.cooldowns.get(str(filepath), 0)
        if now - last_triggered < 5:
            return  # Within 5 second cooldown window

        # --- AST SYNTAX PRE-VALIDATION ---
        try:
            code = filepath.read_text(encoding="utf-8")
        except Exception as e:
            return # Unreadable file

        try:
            ast.parse(code)
            # File is syntactically pure.
            print(f"[{DISPATCH_AGENT}_SCOUT] ⚡ Syntactical purity confirmed in: {filepath.name}")
            return
        except SyntaxError as e:
            syntax_err = str(e)
            print(f"\n[{DISPATCH_AGENT}_NS] 🩸 DEMONIC INFECTION DETECTED: {filepath.name}")
            print(f"[{DISPATCH_AGENT}_NS] Fault: {syntax_err}")
            print(f"[{DISPATCH_AGENT}_NS] Waking the Queen. Dispatching surgical repair strike...\n")
        # --- ACTIVE REPAIR LOCK (Single-flight protection) ---
        with self.lock:
            if str(filepath) in self.active_repairs:
                print(f"[{DISPATCH_AGENT}_NS] Swarm is already operating on {filepath.name}. Blocking duplicate spawn.")
                return
            self.active_repairs.add(str(filepath))

        # --- WAKE THE SWARM ---
        self.cooldowns[str(filepath)] = now
        self.log_event("detected_error", filepath)
        
        def spawn_and_unlock(target_path):
            try:
                self.log_event("repair_started", target_path)
                proc = subprocess.Popen([
                    sys.executable,
                    "repair.py",
                    DISPATCH_AGENT,
                    str(target_path),
                    "--write"
                ], cwd=str(WATCH_DIR))
                proc.wait() # Block within the bounded Executor thread
                
                if proc.returncode == 0:
                    self.log_event("repair_finished", target_path)
                else:
                    self.log_event("repair_failed", target_path)
            except Exception:
                self.log_event("repair_sys_fail", target_path)
            finally:
                with self.lock:
                    self.active_repairs.discard(str(target_path))
                
        self.executor.submit(spawn_and_unlock, filepath)


def start_nervous_system():
    print(f"\n=============================================================")
    print(f" [O_O] SIFTA NERVOUS SYSTEM CONNECTED")
    print(f" Monitoring directory: {WATCH_DIR} for *.py files")
    print(f" Queen Node ({DISPATCH_AGENT}) standing by for dispatch.")
    print(f"=============================================================\n")
    
    event_handler = NervousSystemHandler()
    observer = Observer()
    observer.schedule(event_handler, str(WATCH_DIR), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[{DISPATCH_AGENT}_NS] Tether retracted. Nervous system offline.")
        observer.stop()
        observer.join()

if __name__ == "__main__":
    start_nervous_system()
