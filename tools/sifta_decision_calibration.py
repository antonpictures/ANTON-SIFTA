#!/usr/bin/env python3
"""J2 — calibrate and evaluate Alice's local visitor-message decision against held-out data.

Pipeline (fit -> freeze -> held out, in that order, once):

1. Split the labelled corpus into fit / validation / test by text hash, stratified per class.
2. Serve the real local GGUF through llama-server with the efficient KV profile
   (``-ctk q8_0 -ctv q8_0 -fa on``) under a loopback-only egress guard and on the smallest
   installed artifact that fits the RAM budget at the required context.
3. Read the option logits for every declared label on the **fit** split and fit one
   temperature there. Nothing else may see the test split before the freeze.
4. Freeze the abstention threshold on the **validation** split, subject to a coverage floor.
5. Read the **test** split exactly once and report per-class precision/recall, the confusion
   matrix, Brier / NLL, calibration error, abstention and coverage, and latency p50/p95.

Every measured row is also written to a pheromone trail in ``.sifta_state/`` keyed by
(model digest, prompt template, labels, message) so a later run reuses a real measurement
instead of paying prefill again. A trail row is written only after a fully finite measurement.

Exit code is 0 only when every message produced finite logits for every declared label,
the temperature was fitted on the fit split, the threshold frozen on validation, and the
held-out split was evaluated. A partial reading exits 1 and says which options were missing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from System import swarm_decision_metrics as METRICS  # noqa: E402
from System import swarm_local_serving as SERVING  # noqa: E402
from System import swarm_visitor_message_corpus as CORPUS  # noqa: E402
from System.jsonl_file_lock import append_line_locked  # noqa: E402

SCHEMA = "SIFTA_DECISION_CALIBRATION_V1"
TRAIL_PATH = REPO / ".sifta_state" / "swarm_calibration_trails.jsonl"
LLAMA_SERVER = os.environ.get("SIFTA_LLAMA_SERVER", "/opt/homebrew/bin/llama-server")

CAVEATS = [
    "The corpus is authored evaluation templates, not harvested visitor traffic; it bounds "
    "behaviour on those templates and says nothing about the production traffic distribution.",
    "Raw softmax over declared option logits is not calibrated; only the fitted temperature "
    "produces the number called calibrated, and it was fitted on the fit split only.",
    "Option probabilities are relative to the supplied label set; adding or removing a label "
    "changes every number in the row.",
    "Scoring reads the first continuation token of each label, so a multi-token label is "
    "approximated by its first token.",
    "A label whose token falls below the top-K window is reported missing and fails the run "
    "rather than being silently imputed.",
    "Logits come from a Q4_K_M quantized checkpoint, not full precision weights.",
    "llama-server may reuse a prompt prefix across requests, so later requests can be faster; "
    "the latency percentiles mix cold and warm conditions.",
    "No cloud model was consulted; there is no automatic failover, by local-first law.",
]


def _load_probe():
    path = Path(__file__).resolve().parent / "sifta_local_logits_probe.py"
    spec = importlib.util.spec_from_file_location("sifta_local_logits_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROBE = _load_probe()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def logits_vector(option_logits: dict, labels: list[str]) -> list[float] | None:
    """Turn the probe's option dict into a label-ordered logit vector, or None if incomplete."""
    vector: list[float] = []
    for label in labels:
        cell = (option_logits or {}).get(label)
        if not isinstance(cell, dict) or not isinstance(cell.get("logprob"), (int, float)):
            return None
        value = float(cell["logprob"])
        if value != value or value in (float("inf"), float("-inf")):
            return None
        vector.append(value)
    return vector


def trail_key(model_digest: str, template_hash: str, labels: list[str], message: str) -> str:
    return SERVING.sha256_json({"model_digest": model_digest, "template_hash": template_hash,
                                "labels": list(labels), "message": message})


def load_trails(path: Path = TRAIL_PATH) -> dict[str, dict]:
    """Read the pheromone trail; an unreadable trail is treated as empty, never as data."""
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            key = row.get("trail_key")
            if isinstance(key, str) and isinstance(row.get("option_logits_raw"), dict):
                out[key] = row
    except Exception:
        return {}
    return out


def _inventory_rows() -> list[dict]:
    try:
        from System.swarm_inference_model_inventory import list_inference_model_inventory
        return list(list_inference_model_inventory())
    except Exception:
        return []


def model_matches(row_id: str | None, requested: str) -> bool:
    """Loose but explicit match between an inventory row id and the requested tag."""
    if not row_id:
        return False
    left, right = str(row_id).strip().lower(), str(requested).strip().lower()
    for suffix in (":latest", ":main"):
        if left.endswith(suffix):
            left = left[: -len(suffix)]
        if right.endswith(suffix):
            right = right[: -len(suffix)]
    return left == right or left.endswith("/" + right) or right.endswith("/" + left)


def find_model_row(rows: list[dict], requested: str) -> dict | None:
    for row in rows:
        for field in ("id", "name", "selectable_value"):
            if model_matches(row.get(field), requested):
                return row
    return None


def append_jsonl_locked(path: Path, obj: dict) -> None:
    """Append one JSON object as exactly one newline-terminated line.

    ``jsonl_file_lock.append_line_locked`` writes the caller's string verbatim, so
    a missing newline silently glues rows into a single unparseable blob. This
    wrapper is the only place the tool writes JSONL, and it always terminates.
    """
    append_line_locked(path, json.dumps(obj, ensure_ascii=False) + "\n")


def _label_ordered_summary(rows: list[dict], labels: list[str], split: str) -> dict:
    counts = {label: 0 for label in labels}
    for row in rows:
        name = row.get("label", row.get("gold_label"))
        if name is None:
            continue
        counts[str(name)] = counts.get(str(name), 0) + 1
    return {"split": split, "n": len(rows), "per_label": counts}


def _answered_summary(measured_rows: list[dict], labels: list[str], split: str) -> dict:
    """Per-split counts over the rows actually usable, plus how many were dropped."""
    answered = [m["row"] for m in measured_rows if m["vector"]]
    summary = _label_ordered_summary(answered, labels, split)
    summary["measured"] = len(measured_rows)
    summary["excluded"] = len(measured_rows) - len(answered)
    return summary


RANK_LADDER = (2048, 4096)


def probe_with_rank_ladder(port: int, labels: list[str], first_tokens: dict, message: str,
                           base_n_probs: int, timeout: float,
                           ladder: tuple[int, ...] = RANK_LADDER) -> dict:
    """Read option logits, escalating top-K depth when an option sits below the cut.

    The reused J0 probe escalates only up to ``n_probs=1024``; an option ranked deeper
    than that came back missing. A deeper read returns the *true* logprob at a deeper
    rank, so this is measurement, not imputation: nothing is invented for an option the
    server still does not report, and ``missing_options`` survives to fail the run.
    """
    tried: list[dict] = []
    probed = PROBE.probe_once(port, labels, first_tokens, message, base_n_probs, timeout)
    tried.append({"n_probs": base_n_probs, "missing": list(probed.get("missing_options") or [])})
    for depth in ladder:
        if not probed.get("missing_options"):
            break
        if depth <= int(probed.get("n_probs_requested") or 0):
            continue
        probed = PROBE.probe_once(port, labels, first_tokens, message, depth, timeout)
        tried.append({"n_probs": depth, "missing": list(probed.get("missing_options") or [])})
    probed = dict(probed)
    probed["rank_ladder"] = tried
    return probed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="atervin2011/Aries:latest")
    parser.add_argument("--ctx", type=int, default=2048)
    parser.add_argument("--n-probs", type=int, default=512)
    parser.add_argument("--ngl", type=int, default=0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--profile", choices=["efficient", "baseline"], default="efficient")
    parser.add_argument("--min-coverage", type=float, default=0.6)
    parser.add_argument("--ram-fraction", type=float, default=0.6)
    parser.add_argument("--reuse-trails", type=int, default=1)
    parser.add_argument("--out-root", default=str(REPO / "outputs" / "sifta_decision_calibration"))
    parser.add_argument("--artifact-root", default=str(REPO / "outputs" / "sifta_calibration"))
    args = parser.parse_args()

    labels = list(CORPUS.LABELS)
    splits = CORPUS.split_corpus()
    corpus_info = CORPUS.corpus_summary()
    template_hash = _sha256_text(str(PROBE.TEMPLATE))
    run_id = f"cal-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    out_dir = Path(args.out_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = (SERVING.EFFICIENT_SERVING_PROFILE if args.profile == "efficient"
               else SERVING.BASELINE_SERVING_PROFILE)
    egress_rows: list[dict] = []
    trail_rows = load_trails() if args.reuse_trails else {}
    trail_new: list[dict] = []
    measured: dict[str, list[dict]] = {"fit": [], "validation": [], "test": []}
    latencies: dict[str, list[float]] = {"fit": [], "validation": [], "test": []}
    trail_hits = 0
    missing_any: list[dict] = []
    server_note = None
    report: dict = {}

    try:
        with SERVING.loopback_only_egress(egress_rows):
            total_ram = SERVING.machine_ram_mb()
            budget = None if total_ram is None else round(total_ram * float(args.ram_fraction), 1)
            inventory = _inventory_rows()
            fit_choice = SERVING.choose_local_backend(
                inventory, required_ctx=args.ctx, ram_budget_mb=budget, kv_dtype="q8_0")
            # The harness serves the requested model; the recommendation is context, so the
            # report must state whether the two agree instead of implying they are the same.
            requested_row = find_model_row(inventory, args.model)
            if requested_row is None:
                requested_fit = None
                fit_note = "requested model not found in the local inventory; budget check skipped"
            else:
                check = SERVING.choose_local_backend([requested_row], required_ctx=args.ctx,
                                                     ram_budget_mb=budget, kv_dtype="q8_0")
                requested_fit = check["ok"]
                fit_note = check["reason"]
            hardware_fit = {
                "machine_ram_mb": total_ram,
                "budget_mb": budget,
                "budget_fraction": float(args.ram_fraction),
                "kv_dtype": "q8_0",
                "recommended_smallest_fitting": fit_choice,
                "requested_model": args.model,
                "requested_model_row_id": (requested_row or {}).get("id"),
                "requested_model_in_inventory": requested_row is not None,
                "requested_model_fits_budget": requested_fit,
                "requested_model_is_recommended": bool(
                    requested_row and fit_choice.get("chosen") and model_matches(
                        fit_choice.get("chosen"), str(requested_row.get("id") or args.model))),
                "note": fit_note,
            }

            artifact = PROBE.resolve_model_blob(args.model)
            artifact.update(PROBE.ollama_tag_details(args.model))
            model_digest = artifact.get("digest_sha256") or artifact.get("blob") or args.model

            port = PROBE._free_port()
            log_path = out_dir / "server.log"
            command = [LLAMA_SERVER, "-m", artifact["blob"], "--host", "127.0.0.1",
                       "--port", str(port), "-c", str(args.ctx), "-ngl", str(args.ngl),
                       "--threads", str(args.threads)] + SERVING.serving_flags(profile)
            with open(log_path, "wb") as log_handle:
                proc = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)
            try:
                if not PROBE.wait_health(port, args.timeout_s):
                    report = {"ok": False, "schema": SCHEMA, "run_id": run_id,
                              "error": "llama-server health timeout",
                              "command": command, "artifact": artifact,
                              "server_log_tail": log_path.read_text(errors="replace")[-2000:]}
                    (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
                    print(json.dumps({"ok": False, "error": report["error"]}))
                    return 1
                token_rows = PROBE.tokenize_labels(port, labels, args.timeout_s)
                collision_row = [r for r in token_rows if r.get("kind") == "collision_check"]
                collision = collision_row[0] if collision_row else {"collision": None}
                if collision.get("collision"):
                    report = {"ok": False, "schema": SCHEMA, "run_id": run_id,
                              "error": "first-token collision between declared labels",
                              "collisions": collision, "artifact": artifact}
                    (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
                    print(json.dumps({"ok": False, "error": report["error"]}))
                    return 1
                first_tokens = {r["label"]: r["first_token_id"] for r in token_rows if "label" in r}

                rows_path = out_dir / "rows.jsonl"
                for split in ("fit", "validation", "test"):
                    for entry in splits[split]:
                        message = str(entry["text"])
                        gold = labels.index(str(entry["label"]))
                        key = trail_key(str(model_digest), template_hash, labels, message)
                        cached = trail_rows.get(key)
                        rank_ladder = None
                        if cached is not None:
                            option_logits = cached["option_logits_raw"]
                            elapsed_ms = cached.get("elapsed_ms")
                            deep_used = cached.get("deep_probe_used")
                            source = "trail_reuse"
                            trail_hits += 1
                        else:
                            probed = probe_with_rank_ladder(port, labels, first_tokens, message,
                                                            args.n_probs, args.timeout_s)
                            option_logits = probed.get("option_logits_raw") or {}
                            elapsed_ms = probed.get("elapsed_ms")
                            deep_used = probed.get("deep_probe_used")
                            rank_ladder = probed.get("rank_ladder")
                            source = "measured_now"
                            if probed.get("all_options_finite"):
                                trail_new.append({"trail_key": key, "model_digest": str(model_digest),
                                                  "template_hash": template_hash, "labels": labels,
                                                  "message": message, "message_sha256": _sha256_text(message),
                                                  "option_logits_raw": option_logits,
                                                  "elapsed_ms": elapsed_ms,
                                                  "deep_probe_used": deep_used,
                                                  "rank_ladder": rank_ladder,
                                                  "truth_label": "MEASURED_LOCAL_MODEL",
                                                  "writer": "glm_harness", "written_at": time.time()})
                        vector = logits_vector(option_logits, labels)
                        if vector is None:
                            missing_any.append({"split": split, "message_sha256": _sha256_text(message),
                                                "label": entry["label"],
                                                "present": sorted(option_logits.keys())})
                        if isinstance(elapsed_ms, (int, float)):
                            latencies[split].append(float(elapsed_ms))
                        probs = METRICS.softmax(vector, 1.0) if vector else None
                        row_out = {
                            "schema": SCHEMA, "split": split, "gold_label": entry["label"],
                            "gold_index": gold, "tag": entry["tag"],
                            "message_sha256": _sha256_text(message), "message": message,
                            "logits": vector, "raw_probabilities": probs,
                            "raw_choice": labels[METRICS.argmax(probs)] if probs else None,
                            "option_logits_raw": option_logits, "elapsed_ms": elapsed_ms,
                            "deep_probe_used": deep_used, "source": source,
                            "rank_ladder": rank_ladder,
                            "truth_label": "MEASURED_LOCAL_MODEL_ON_AUTHORED_TEMPLATE",
                        }
                        measured[split].append({"row": row_out, "vector": vector, "gold": gold})
                        append_jsonl_locked(rows_path, row_out)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
    except SERVING.EgressViolation as exc:
        report = {"ok": False, "schema": SCHEMA, "run_id": run_id,
                  "error": f"local-first guard blocked a non-loopback connection: {exc}",
                  "egress": SERVING.egress_block(egress_rows)}
        (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(json.dumps({"ok": False, "error": report["error"]}))
        return 1

    for item in trail_new:
        append_jsonl_locked(TRAIL_PATH, item)

    fit_rows = [(m["vector"], m["gold"]) for m in measured["fit"] if m["vector"]]
    val_rows = [(m["vector"], m["gold"]) for m in measured["validation"] if m["vector"]]
    test_rows = [(m["vector"], m["gold"]) for m in measured["test"] if m["vector"]]

    if not fit_rows or not val_rows or not test_rows:
        report = {"ok": False, "schema": SCHEMA, "run_id": run_id,
                  "error": "a split produced no finite measurement; refusing to calibrate",
                  "sizes": {k: len(v) for k, v in measured.items()},
                  "missing_options": missing_any[:20]}
        (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(json.dumps({"ok": False, "error": report["error"]}))
        return 1

    # ---- fit on the fit split only -------------------------------------------------------
    temperature_fit = METRICS.fit_temperature(fit_rows)
    temperature = float(temperature_fit["temperature"])
    choice_preserved = METRICS.assert_choice_preserved([v for v, _ in fit_rows], temperature)

    # ---- freeze the threshold on validation ---------------------------------------------
    val_probs = [METRICS.softmax(v, temperature) for v, _ in val_rows]
    val_gold = [g for _, g in val_rows]
    frozen = METRICS.choose_threshold(val_probs, val_gold, min_coverage=args.min_coverage)
    threshold = float(frozen["threshold"])

    identity = {"schema": SCHEMA, "model_digest": str(model_digest), "template_hash": template_hash,
                "labels": labels, "corpus_sha256": corpus_info["corpus_sha256"],
                "policy_id": CORPUS.POLICY_ID, "profile": profile["name"],
                "temperature": temperature, "threshold": threshold,
                "min_coverage": float(args.min_coverage)}
    artifact_id = "cal-" + SERVING.sha256_json(identity)[:16]
    calibration_artifact = {**identity, "artifact_id": artifact_id, "run_id": run_id,
                            "created_at": time.time(), "frozen_before_held_out": True,
                            "fitted_on": {"temperature": "fit split only",
                                          "threshold": "validation split only"},
                            "truth_label": "MEASURED_LOCAL_MODEL_ON_AUTHORED_TEMPLATE"}

    # ---- held out: read the test split once with the frozen artifact ---------------------
    test_report = METRICS.evaluate_split(test_rows, labels, temperature=temperature,
                                        threshold=threshold, latencies_ms=latencies["test"])
    validation_report = METRICS.evaluate_split(val_rows, labels, temperature=temperature,
                                              threshold=threshold,
                                              latencies_ms=latencies["validation"])
    fit_report = METRICS.evaluate_split(fit_rows, labels, temperature=temperature,
                                       threshold=threshold, latencies_ms=latencies["fit"])

    artifact_root = Path(args.artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / f"{artifact_id}.json").write_text(
        json.dumps(calibration_artifact, indent=1), encoding="utf-8")

    report = {
        "ok": not missing_any,
        "status": "complete" if not missing_any else "some_options_below_rank_ladder",
        "schema": SCHEMA,
        "run_id": run_id,
        "artifact_id": artifact_id,
        "truth_label": "MEASURED_LOCAL_MODEL_ON_AUTHORED_TEMPLATE",
        "model": {"model_id": args.model, "digest_sha256": artifact.get("digest_sha256"),
                  "size_bytes": artifact.get("size_bytes"), "blob": artifact.get("blob"),
                  "details": artifact.get("details")},
        "serving": {"profile": SERVING.serving_profile_block(profile), "ctx": args.ctx,
                    "ngl": args.ngl, "threads": args.threads,
                    "kv_estimate_mb_at_ctx": round(SERVING.estimate_kv_bytes(
                        n_layer=28, n_kv_head=8, head_dim=64, n_ctx=args.ctx,
                        dtype="q8_0") / 1024 / 1024, 1) if args.profile == "efficient" else None,
                    "command": command},
        "hardware_fit": hardware_fit,
        "corpus": corpus_info,
        "prompt_template_sha256": template_hash,
        "first_tokens": first_tokens,
        "collision_check": collision,
        "split_sizes": {k: len(v) for k, v in measured.items()},
        "split_label_counts": {k: _label_ordered_summary([m["row"] for m in v], labels, k)
                               for k, v in measured.items()},
        "calibration": {"temperature_fit_on_fit_split": temperature_fit,
                        "threshold_frozen_on_validation": frozen,
                        "frozen_artifact": calibration_artifact,
                        "choice_unchanged_by_temperature": choice_preserved},
        "fit": fit_report,
        "validation": validation_report,
        "held_out_test": test_report,
        "latency_ms": {k: METRICS.latency_summary(v) for k, v in latencies.items()},
        "trails": {"path": str(TRAIL_PATH.relative_to(REPO)), "reuse_enabled": bool(args.reuse_trails),
                   "reused_rows": trail_hits, "new_rows_written": len(trail_new),
                   "identity_fields": ["model_digest", "template_hash", "labels", "message"]},
        "egress": SERVING.egress_block(egress_rows),
        "missing_options": missing_any,
        "all_options_finite_for_every_message": not missing_any,
        "metrics_scope": ("every metric below is computed only on rows where every option was "
                          "finite; rows listed in missing_options are excluded from fit, "
                          "validation and held-out test"),
        "split_answered_counts": {k: _answered_summary(v, labels, k) for k, v in measured.items()},
        "rank_ladder": [args.n_probs, *RANK_LADDER],
        "n_probs_requested": args.n_probs,
        "caveats": CAVEATS,
        "finished_at": time.time(),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

    summary = {
        "ok": not missing_any,
        "run_id": run_id, "artifact_id": artifact_id,
        "split_sizes": report["split_sizes"],
        "temperature": temperature,
        "temperature_nll_before_after": [temperature_fit["nll_before"], temperature_fit["nll_after"]],
        "threshold": threshold, "coverage_floor_met": frozen["floor_met"],
        "held_out_calibrated": {k: test_report["calibrated"].get(k) for k in
                                ("coverage", "accuracy_on_answered", "macro_f1", "brier", "nll")},
        "held_out_raw_full_coverage_accuracy": test_report["raw_full_coverage"]["accuracy"],
        "held_out_ece_calibrated": (test_report["calibrated"].get("calibration_error") or {}).get("ece"),
        "held_out_ece_raw": (test_report["raw_full_coverage"].get("calibration_error") or {}).get("ece"),
        "trail_reuse": {"reused": trail_hits, "written": len(trail_new)},
        "hardware_fit": {"requested_model_fits_budget": hardware_fit["requested_model_fits_budget"],
                         "requested_model_is_recommended": hardware_fit["requested_model_is_recommended"],
                         "recommended_smallest_fitting": hardware_fit["recommended_smallest_fitting"].get("chosen")},
        "egress": report["egress"],
        "missing_options": len(missing_any),
        "report": str((out_dir / "report.json").relative_to(REPO)),
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if not missing_any else 1


if __name__ == "__main__":
    raise SystemExit(main())
