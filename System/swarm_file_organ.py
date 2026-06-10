#!/usr/bin/env python3
"""
swarm_file_organ.py
File read/write/edit/list organ for Alice.
Denies dangerous paths.
Writes SHA-256 chained receipts.
Bills STGM.
"""

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
import difflib

_TRACE = Path(".sifta_state/tool_router_trace.jsonl")
_DENY_PATHS = ["/etc/", "/System/", "/private/etc/", "/usr/bin/", "/bin/", "/sbin/"]

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
    row["organ"] = "file"
    row["prev_hash"] = _previous_hash()
    row["hash"] = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]
    with _TRACE.open("a") as f:
        f.write(json.dumps(row) + "\n")

def _is_denied(path: str) -> bool:
    p = str(path)
    for d in _DENY_PATHS:
        if p.startswith(d):
            return True
    return False

def _read_pdf_text(path: str):
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return None, "pdftotext_not_available"
    try:
        proc = subprocess.run(
            [pdftotext, "-layout", "-enc", "UTF-8", path, "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:
        return None, str(e)[:200]
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or f"pdftotext exit {proc.returncode}")[:200]
    return proc.stdout, ""

def read_file(path: str):
    if _is_denied(path):
        receipt = {"type": "FILE_REFUSED", "path": path, "reason": "denied_path"}
        _append_receipt(receipt)
        return receipt
    try:
        if Path(path).suffix.lower() == ".pdf":
            content, error = _read_pdf_text(path)
            if content is None:
                raise RuntimeError(error or "pdf_text_extract_failed")
        else:
            content = Path(path).read_text()
        receipt = {"type": "FILE_READ", "path": path, "size_bytes": len(content), "content_preview": content[:500]}
        _append_receipt(receipt)
        return {"content": content, "receipt_hash": receipt["hash"]}
    except Exception as e:
        receipt = {"type": "FILE_ERROR", "path": path, "error": str(e)[:200]}
        _append_receipt(receipt)
        return receipt

def write_file(path: str, content: str):
    if _is_denied(path):
        receipt = {"type": "FILE_REFUSED", "path": path, "reason": "denied_path"}
        _append_receipt(receipt)
        return receipt
    try:
        Path(path).write_text(content)
        h = hashlib.sha256(content.encode()).hexdigest()
        receipt = {"type": "FILE_WRITE", "path": path, "size_bytes": len(content), "content_hash": h}
        _append_receipt(receipt)
        return {"wrote_ok": True, "content_hash": h, "receipt_hash": receipt["hash"]}
    except Exception as e:
        receipt = {"type": "FILE_ERROR", "path": path, "error": str(e)[:200]}
        _append_receipt(receipt)
        return receipt

def edit_file(path: str, old_text: str, new_text: str):
    if _is_denied(path):
        receipt = {"type": "FILE_REFUSED", "path": path, "reason": "denied_path"}
        _append_receipt(receipt)
        return receipt
    try:
        content = Path(path).read_text()
        if old_text not in content:
            receipt = {"type": "FILE_ERROR", "path": path, "error": "old_text not found"}
            _append_receipt(receipt)
            return receipt
        new_content = content.replace(old_text, new_text, 1)
        Path(path).write_text(new_content)
        diff = list(difflib.unified_diff(content.splitlines(keepends=True), new_content.splitlines(keepends=True), fromfile='old', tofile='new'))
        h = hashlib.sha256(new_content.encode()).hexdigest()
        receipt = {"type": "FILE_EDIT", "path": path, "diff": ''.join(diff)[:2000], "content_hash": h}
        _append_receipt(receipt)
        return {"edited_ok": True, "content_hash": h, "receipt_hash": receipt["hash"]}
    except Exception as e:
        receipt = {"type": "FILE_ERROR", "path": path, "error": str(e)[:200]}
        _append_receipt(receipt)
        return receipt

def list_dir(path: str):
    if _is_denied(path):
        receipt = {"type": "FILE_REFUSED", "path": path, "reason": "denied_path"}
        _append_receipt(receipt)
        return receipt
    try:
        items = [str(p) for p in Path(path).iterdir()]
        receipt = {"type": "DIR_LIST", "path": path, "items": items[:50]}
        _append_receipt(receipt)
        return {"items": items, "receipt_hash": receipt["hash"]}
    except Exception as e:
        receipt = {"type": "FILE_ERROR", "path": path, "error": str(e)[:200]}
        _append_receipt(receipt)
        return receipt
