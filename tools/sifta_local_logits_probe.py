#!/usr/bin/env python3
"""sifta_local_logits_probe.py — J0: prove finite local logits for every declared option.

Local-first law (09-19): decisions come from a local model's REAL forward pass,
never from generated JSON self-rated confidence. This tool is the J0 evidence
producer: it loads an installed GGUF via llama-server, tokenizes the declared
option labels, and for each probe message reads the next-token distribution at
the decision position (n_predict=0 -> prompt processing only). Every declared
option's first token must appear with a FINITE logprob, or the run fails.

The output is explicitly RAW / option-relative / UNCALIBRATED:
  * probabilities are relative to the supplied alternatives only;
  * a raw softmax over next-token logits is NOT a calibrated probability;
  * single-first-token scoring is an approximation for multi-token labels
    (recorded in the evidence, not hidden).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OLLAMA_ROOT = Path(os.path.expanduser("~/.ollama/models"))
MODEL_LAYER = "application/vnd.ollama.image.model"
TEMPLATE = (
    "You classify visitor messages for a small business. "
    "Reply with exactly one label from this set: {labels_block}.\n"
    "Message: {message}\nLabel:"
)
DEMO_MESSAGES = [
    "my order 4471 arrived broken, the box was crushed",
    "what are your opening hours this weekend?",
    "BUY 5000 followers cheap!!! link in bio",
]
DEMO_LABELS = ["complaint", "question", "spam", "other"]


def _http_json(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as handle:
        return json.loads(handle.read().decode("utf-8", "replace"))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def resolve_model_blob(model_id: str) -> dict:
    """Resolve an ollama model id (namespace/name:tag) to its GGUF blob + digest."""
    stem = model_id.split(":", 1)[0]
    tag = model_id.split(":", 1)[1] if ":" in model_id else "latest"
    parts = stem.split("/")
    manifest = OLLAMA_ROOT.joinpath("manifests", "registry.ollama.ai", *parts, tag)
    if not manifest.exists():  # bare library names live directly under manifests/
        manifest = OLLAMA_ROOT.joinpath("manifests", *parts, tag)
    if not manifest.exists():
        raise FileNotFoundError(f"ollama manifest not found for {model_id} at {manifest}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    layers = [layer for layer in data.get("layers", []) if layer.get("mediaType") == MODEL_LAYER]
    if not layers:
        raise ValueError(f"no model layer in manifest {manifest}")
    layer = max(layers, key=lambda item: int(item.get("size", 0)))
    blob = OLLAMA_ROOT / "blobs" / ("sha256-" + layer["digest"].split(":", 1)[1])
    if not blob.exists():
        raise FileNotFoundError(f"blob missing: {blob}")
    return {"model_id": model_id, "manifest": str(manifest), "blob": str(blob),
            "digest_sha256": layer["digest"], "size_bytes": int(layer["size"])}


def ollama_tag_details(model_id: str) -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as handle:
            tags = json.loads(handle.read().decode("utf-8", "replace"))
        for row in tags.get("models", []):
            if row.get("name") == model_id:
                det = row.get("details", {})
                return {"family": det.get("family"), "parameter_size": det.get("parameter_size"),
                        "quantization_level": det.get("quantization_level")}
    except Exception:
        pass
    return {}


def wait_health(port: int, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as handle:
                if json.loads(handle.read().decode("utf-8", "replace")).get("status") == "ok":
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def tokenize_labels(port: int, labels: list[str], timeout: float) -> list[dict]:
    rows = []
    for label in labels:
        cont = _http_json(f"http://127.0.0.1:{port}/tokenize", {"content": " " + label}, timeout)
        bare = _http_json(f"http://127.0.0.1:{port}/tokenize", {"content": label}, timeout)
        cont_ids = list(cont.get("tokens", []))
        bare_ids = list(bare.get("tokens", []))
        rows.append({"label": label, "continuation_token_ids": cont_ids,
                     "continuation_token_count": len(cont_ids),
                     "bare_token_ids": bare_ids, "first_token_id": cont_ids[0] if cont_ids else None})
    collisions = {}
    for row in rows:
        key = row.get("first_token_id")
        collisions.setdefault(key, []).append(row["label"])
    dupes = {key: names for key, names in collisions.items() if len(names) > 1}
    return rows + [{"kind": "collision_check", "first_token_id_collisions": dupes,
                    "collision": bool(dupes)}]


def probe_once(port: int, labels: list[str], first_tokens: dict, message: str,
               n_probs: int, timeout: float) -> dict:
    prompt = TEMPLATE.format(labels_block=", ".join(labels), message=message)
    started = time.time()
    body = _http_json(f"http://127.0.0.1:{port}/completion",
                      {"prompt": prompt, "n_predict": 0, "n_probs": n_probs, "temperature": 0.0}, timeout)
    top = (body.get("completion_probabilities") or [{}])[0].get("top_logprobs") or []
    by_id = {}
    for entry in top:
        key = entry.get("id")
        val = entry.get("logprob")
        if key is not None and isinstance(val, (int, float)):
            by_id[key] = float(val)
    options = {}
    missing = []
    for label in labels:
        tok = first_tokens.get(label)
        if tok is None:
            missing.append(label)
            continue
        if tok in by_id:
            options[label] = {"first_token_id": tok, "logprob": by_id[tok], "finite": math.isfinite(by_id[tok])}
        else:
            missing.append(label)
    deep_used = False
    if missing and n_probs < 1024:
        deep_used = True
        body2 = _http_json(f"http://127.0.0.1:{port}/completion",
                           {"prompt": prompt, "n_predict": 0, "n_probs": 1024, "temperature": 0.0}, timeout)
        for entry in (body2.get("completion_probabilities") or [{}])[0].get("top_logprobs") or []:
            key = entry.get("id")
            val = entry.get("logprob")
            if key is not None and isinstance(val, (int, float)):
                by_id[key] = float(val)
        still = []
        for label in missing:
            tok = first_tokens.get(label)
            if tok in by_id:
                options[label] = {"first_token_id": tok, "logprob": by_id[tok], "finite": math.isfinite(by_id[tok])}
            else:
                still.append(label)
        missing = still
    elapsed_ms = round((time.time() - started) * 1000)
    if options:
        probs = {}
        mx = max(row["logprob"] for row in options.values())
        denom = sum(math.exp(row["logprob"] - mx) for row in options.values())
        for label, row in options.items():
            probs[label] = round(math.exp(row["logprob"] - mx) / denom, 8)
    else:
        probs = {}
    return {"message": message, "prompt": prompt, "elapsed_ms": elapsed_ms,
            "n_probs_requested": n_probs, "n_probs_returned": len(top),
            "option_logits_raw": options, "option_probabilities_raw_relative": probs,
            "deep_probe_used": deep_used,
            "missing_options": missing, "all_options_finite": (not missing) and all(
                row["finite"] for row in options.values())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="atervin2011/Aries:latest")
    parser.add_argument("--labels", default=",".join(DEMO_LABELS))
    parser.add_argument("--messages", default="", help="JSON file with a list of strings (else demo set)")
    parser.add_argument("--n-probs", type=int, default=512)
    parser.add_argument("--ngl", type=int, default=0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--ctx", type=int, default=2048)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--out-root", default=str(REPO / "outputs" / "sifta_local_logits_probe"))
    args = parser.parse_args()

    labels = [chunk.strip() for chunk in args.labels.split(",") if chunk.strip()]
    if len(labels) < 2:
        print("FAIL need >=2 labels", file=sys.stderr)
        return 2
    if args.messages and Path(args.messages).exists():
        messages = json.loads(Path(args.messages).read_text(encoding="utf-8"))
    else:
        messages = DEMO_MESSAGES

    artifact = resolve_model_blob(args.model)
    artifact.update(ollama_tag_details(args.model))
    out_dir = Path(args.out_root) / f"probe-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)

    port = _free_port()
    log_path = out_dir / "server.log"
    with open(log_path, "wb") as log_handle:
        proc = subprocess.Popen(
            ["/opt/homebrew/bin/llama-server", "-m", artifact["blob"],
             "--host", "127.0.0.1", "--port", str(port), "-c", str(args.ctx),
             "-ngl", str(args.ngl), "--threads", str(args.threads)],
            stdout=log_handle, stderr=subprocess.STDOUT)
    ok = False
    try:
        if not wait_health(port, args.timeout_s):
            evidence = {"ok": False, "error": "server health timeout", "artifact": artifact,
                        "server_log_tail": log_path.read_text(errors="replace")[-2000:]}
            (out_dir / "probe.json").write_text(json.dumps(evidence, indent=1), encoding="utf-8")
            print(json.dumps(evidence)[:1200])
            return 1
        token_rows = tokenize_labels(port, labels, args.timeout_s)
        collision_row = [row for row in token_rows if row.get("kind") == "collision_check"][0]
        if collision_row["collision"]:
            evidence = {"ok": False, "error": "first-token collision between declared options; "
                                              "single-token scoring ambiguous", "collisions": collision_row,
                        "artifact": artifact}
            (out_dir / "probe.json").write_text(json.dumps(evidence, indent=1), encoding="utf-8")
            print(json.dumps(evidence)[:1200])
            return 1
        first_tokens = {row["label"]: row["first_token_id"] for row in token_rows if "label" in row}
        probes = [probe_once(port, labels, first_tokens, msg, args.n_probs, args.timeout_s) for msg in messages]
        all_ok = all(p["all_options_finite"] for p in probes)
        ver_run = subprocess.run(["/opt/homebrew/bin/llama-server", "--version"],
                                 capture_output=True, text=True)
        ver_lines = [ln for ln in (ver_run.stdout + ver_run.stderr).splitlines() if ln.strip()]
        server_version = ver_lines[0] if ver_lines else "unknown"
        evidence = {
            "ok": all_ok,
            "law": "real forward pass; generated-JSON self-rated confidence does NOT pass",
            "status": "raw_uncalibrated_option_relative",
            "model_artifact": artifact,
            "server": {"binary": "/opt/homebrew/bin/llama-server", "version": server_version,
                       "port": port, "ngl": args.ngl, "threads": args.threads, "ctx": args.ctx,
                       "n_probs": args.n_probs, "endpoint": "POST /completion n_predict=0"},
            "prompt_template": TEMPLATE,
            "prompt_template_sha256": hashlib.sha256(TEMPLATE.encode("utf-8")).hexdigest(),
            "labels": labels,
            "tokenizer_behavior": token_rows,
            "probes": probes,
            "cautions": [
                "raw softmax over next-token logits is NOT calibrated",
                "probabilities are relative to the supplied alternatives only",
                "single-first-token scoring approximates multi-token labels",
                "no module name or classifier result certifies AGI",
            ],
        }
        (out_dir / "probe.json").write_text(json.dumps(evidence, indent=1), encoding="utf-8")
        print(json.dumps({"ok": all_ok, "out": str(out_dir / "probe.json"),
                          "probes": [{"elapsed_ms": p["elapsed_ms"], "probs": p["option_probabilities_raw_relative"]}
                                     for p in probes]}))
        return 0 if all_ok else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())