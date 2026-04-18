# state_bus.py
"""
SHARED STATE BUS
Creates a unified memory layer across SIFTA modules so the system 
survives restarts without amnesia.
"""

import json
from pathlib import Path
import threading

STATE_FILE = Path(".sifta_state/state_bus.json")
_lock = threading.Lock()

def get_state(key: str, default_value=None):
    """Safely retrieves a specific key from the shared state bus."""
    if not STATE_FILE.exists():
        return default_value
        
    with _lock:
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(key, default_value)
        except json.JSONDecodeError:
            # If the file is corrupted during write, return default
            return default_value

def set_state(key: str, value):
    """Safely writes a specific key to the shared state bus."""
    STATE_FILE.parent.mkdir(exist_ok=True)
    
    with _lock:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
            
        data[key] = value
        
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
