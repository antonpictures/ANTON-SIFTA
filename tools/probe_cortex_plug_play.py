#!/usr/bin/env python3
"""Small explicit local probes; never changes Alice's chosen cortex or reads memory."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from System.jsonl_file_lock import append_line_locked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    ledger = ROOT / ".sifta_state/cortex_plug_play_probes.jsonl"
    failed = False
    for model in args.models:
        row = {"receipt_id": "cortex-probe-" + uuid.uuid4().hex, "ts": time.time(),
               "requested_model": model, "source": "isolated_local_probe",
               "truth_label": "OBSERVED", "think": False, "num_predict": 120,
               "owner_context_used": False, "selection_changed": False}
        started = time.monotonic()
        try:
            payload = {"model": model, "stream": False, "think": False, "keep_alive": 0,
                       "options": {"num_ctx": 4096, "num_predict": 120, "temperature": 0},
                       "messages": [{"role": "system", "content": "You are Alice of SIFTA. Reply directly and briefly."},
                                    {"role": "user", "content": "Say hello in one short sentence."}]}
            request = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                result = json.loads(response.read())
            content = str((result.get("message") or {}).get("content") or "").strip()
            row.update(actual_model=result.get("model"), reply=content, done_reason=result.get("done_reason"),
                       prompt_tokens=result.get("prompt_eval_count"), output_tokens=result.get("eval_count"),
                       reply_sha256=hashlib.sha256(content.encode()).hexdigest(),
                       ok=bool(content) and result.get("done_reason") == "stop" and result.get("model") == model)
        except Exception as exc:
            row.update(ok=False, error_type=type(exc).__name__)
        row["elapsed_s"] = round(time.monotonic() - started, 3)
        append_line_locked(ledger, json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)
        failed |= not row["ok"]
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
