#!/usr/bin/env python3
# System/swarm_architect_day_segments.py
# Event 117 — Persistent Day Segments (Calendar-Scale Memory with Receipts)

import json
import time
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

STATE_DIR = Path(".sifta_state")
SEGMENTS_LOG = STATE_DIR / "architect_day_segments.jsonl"

class ArchitectDaySegments:
    """
    Bounded interval persistence with source hash.
    Fixes "vanished" 4-hour blocks. Receipts only.
    """

    @staticmethod
    def parse_segment(text: str) -> Optional[Dict]:
        """Extract time windows like 11am–3pm, bedroom, nap, YouTube"""
        # Time range patterns
        time_pat = re.search(r'(\d{1,2})(?::\d{2})?\s*(am|pm)?\s*[-–to ]+\s*(\d{1,2})(?::\d{2})?\s*(am|pm)?', text, re.I)
        if not time_pat:
            return None

        start_str = time_pat.group(1) + (time_pat.group(2) or "")
        end_str = time_pat.group(3) + (time_pat.group(4) or "")
        context = re.findall(r'(bedroom|bedrook|nap|sleep|youtube|media|loud|quiet)', text, re.I)

        segment = {
            "segment_id": hashlib.sha256(text.encode()).hexdigest()[:16],
            "timestamp": time.time(),
            "raw_text": text[:500],
            "start_time": start_str,
            "end_time": end_str,
            "context_tags": list(set([c.lower() for c in context])),
            "source_hash": hashlib.sha256(text.encode()).hexdigest()[:12],
            "status": "observed"
        }
        return segment

    @staticmethod
    def ingest_segment(text: str):
        seg = ArchitectDaySegments.parse_segment(text)
        if not seg:
            return None
        
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SEGMENTS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(seg) + "\n")
        return seg

    @staticmethod
    def get_today_segments() -> List[Dict]:
        """Return today's persisted segments for prompt/context"""
        if not SEGMENTS_LOG.exists():
            return []
        today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        segments = []
        with open(SEGMENTS_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    s = json.loads(line.strip())
                    if s.get("timestamp", 0) > today_start:
                        segments.append(s)
                except:
                    continue
        return segments

    @staticmethod
    def format_for_prompt() -> str:
        segments = ArchitectDaySegments.get_today_segments()
        if not segments:
            return ""
        lines = ["DAY SEGMENTS DIARY (Observed Episodic Blocks):"]
        for s in segments[-6:]:  # last 6 for context
            tags = ", ".join(s["context_tags"]) if s["context_tags"] else "unknown"
            lines.append(f"- {s['start_time']} to {s['end_time']} : {tags} (receipt {s['segment_id']})")
        return "\n".join(lines)

# Integration test
def test_day_segment_persistence():
    text = "11am to 3pm bedroom loud YouTube"
    seg = ArchitectDaySegments.ingest_segment(text)
    assert seg is not None
    assert "bedroom" in seg["context_tags"]
    print("Day segment persistence test passed.")
    print("Prompt format:", ArchitectDaySegments.format_for_prompt())

if __name__ == "__main__":
    test_day_segment_persistence()


def try_ingest_architect_day_segment(text: str):
    return ArchitectDaySegments.ingest_segment(text)

def format_segments_for_prompt() -> str:
    return ArchitectDaySegments.format_for_prompt()

def answer_recent_activity_query(text: str) -> str:
    import re
    if re.search(r"\b(what was i doing|where was i|my recent activity)\b", text, re.I):
        prompt = ArchitectDaySegments.format_for_prompt()
        if not prompt or "No persisted" in prompt:
            return ""
        return "George, looking at my local day segments ledger: \n" + prompt
    return ""

if __name__ == "__main__":
    pass
