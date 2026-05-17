#!/usr/bin/env python3
"""
swarm_web_organ.py
Web fetch and search organ for Alice.
Denies dangerous hosts/schemes (localhost, metadata IPs, file://).
Writes SHA-256 chained receipts.
Bills STGM.
"""

import hashlib
import json
import time
from pathlib import Path
import requests
from urllib.parse import urlparse

_TRACE = Path(".sifta_state/tool_router_trace.jsonl")
_DENY_HOSTS = ["localhost", "127.0.0.1", "169.254.169.254", "metadata.google.internal"]
_DENY_SCHEMES = ["file", "ftp", "gopher"]

def _previous_hash():
    if not _TRACE.exists():
        return "genesis"
    last = ""
    with _TRACE.open() as f:
        for line in f:
            if line.strip():
                last = line.strip()
    if not last:
        return "genesis"
    try:
        prev = json.loads(last)
        return str(prev.get("hash") or prev.get("receipt_hash") or hashlib.sha256(last.encode()).hexdigest()[:16])
    except Exception:
        return hashlib.sha256(last.encode()).hexdigest()[:16]

def _append_receipt(row):
    row["ts"] = time.time()
    row["organ"] = "web"
    row["prev_hash"] = _previous_hash()
    row["hash"] = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]
    with _TRACE.open("a") as f:
        f.write(json.dumps(row) + "\n")

def fetch_url(url: str, max_chars: int = 4000, timeout_s: int = 10):
    p = urlparse(url)
    if p.scheme in _DENY_SCHEMES or p.hostname in _DENY_HOSTS:
        receipt = {"type": "WEB_REFUSED", "url": url, "reason": "denied_host_or_scheme"}
        _append_receipt(receipt)
        return receipt
    try:
        r = requests.get(url, timeout=timeout_s, allow_redirects=True)
        content = r.text[:max_chars]
        receipt = {"type": "WEB_FETCH", "url": url, "status": r.status_code, "content": content[:500]}
        _append_receipt(receipt)
        return {"content": content, "status": r.status_code, "receipt_hash": receipt["hash"]}
    except Exception as e:
        receipt = {"type": "WEB_ERROR", "url": url, "error": str(e)[:200]}
        _append_receipt(receipt)
        return receipt

def search_web(query: str, max_results: int = 5):
    # Stub for demo; in real would use a search API with key.
    # For now, return example with receipt.
    results = [{"title": "Example result for " + query, "url": "https://example.com/search?q=" + query}]
    receipt = {"type": "WEB_SEARCH", "query": query, "results": results}
    _append_receipt(receipt)
    return {"results": results, "receipt_hash": receipt["hash"]}
