"""§2.I — Cline external-brain settings probe.

When George changes Cline's model (e.g. GPT-5.3 Codex Spark 100K medium →
GPT-5.4 922K Extra High) the choice lives in Cline's own UI / config file
and never reaches Alice's ledgers. This organ closes that opacity wall
*for the cline lane specifically* — it reads Cline's config file from the
common macOS / XDG locations and writes one row to
`.sifta_state/external_brain_settings.jsonl` so Alice can see what brain
is actually behind her cline lane.

Pure stdlib. Read-only. No shell-out, no network, no subprocess.

Author: Cowork Claude (claude-opus-4-7), 2026-05-28, round r112c.
Doctrine: §1.A (Alice is one organism — knows her own external surfaces),
          §3.5 (Brothers in Code), §3.7 (Alive is Alive), §7.12 (Probe-Before-Claim).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "external_brain_settings.jsonl"

TRUTH_LABEL = "EXTERNAL_BRAIN_SETTINGS_PROBE_V1"
LANE = "cline"


def _candidate_config_paths(home: Optional[Path] = None) -> List[Path]:
    """Common locations a Node-based Cline CLI may persist its model choice."""
    h = Path(home or os.path.expanduser("~"))
    return [
        h / ".config" / "cline" / "config.json",
        h / ".cline" / "config.json",
        h / ".cline" / "settings.json",
        h / "Library" / "Application Support" / "Cline" / "config.json",
        h / "Library" / "Application Support" / "Cline" / "settings.json",
        h / ".cline-cli" / "config.json",
    ]


def _safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    """Best-effort JSON read. Returns None on any error — never raises."""
    try:
        if not path.exists() or not path.is_file():
            return None
        raw = path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def _extract_field(cfg: Dict[str, Any], *names: str) -> Optional[str]:
    """Look up the first matching field anywhere in a Cline-shaped config dict."""
    for name in names:
        if name in cfg:
            value = cfg.get(name)
            if value not in (None, ""):
                return str(value)
    # Look one level deeper — Cline may nest model under "openai" / "provider".
    for key, value in cfg.items():
        if isinstance(value, dict):
            inner = _extract_field(value, *names)
            if inner:
                return inner
    return None


def probe_cline_settings(
    *,
    home: Optional[Path] = None,
    now: Optional[float] = None,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Probe Cline config files. Returns the row that will/did get appended.

    Always writes one row to the settings ledger so the absence of a config
    is itself recorded — opacity by silence is the bug we are closing.
    """
    ts = float(now if now is not None else time.time())
    candidates = _candidate_config_paths(home=home)
    found_path: Optional[Path] = None
    cfg: Optional[Dict[str, Any]] = None
    for path in candidates:
        data = _safe_read_json(path)
        if data is not None:
            found_path = path
            cfg = data
            break

    row: Dict[str, Any] = {
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "kind": "EXTERNAL_BRAIN_SETTINGS",
        "lane": LANE,
        "checked_paths": [str(p) for p in candidates],
        "config_path": str(found_path) if found_path else "",
    }

    if cfg is None:
        row["status"] = "no_config_found"
        row["model"] = ""
        row["provider"] = ""
        row["reasoning_level"] = ""
        row["context_window"] = ""
    else:
        model = _extract_field(cfg, "model", "modelId", "selectedModel") or ""
        provider = _extract_field(cfg, "provider", "providerName", "apiProvider") or ""
        reasoning = (
            _extract_field(cfg, "reasoning_level", "reasoningLevel", "thinking_level", "thinkingLevel")
            or ""
        )
        ctx_window = _extract_field(cfg, "context_window", "contextWindow", "maxTokens") or ""
        # Round 112d — Plan/Act toggle from George's screenshot 10:17 UTC.
        mode = (
            _extract_field(cfg, "mode", "plan_act_mode", "planActMode", "currentMode")
            or ""
        )
        auto_approve = (
            _extract_field(cfg, "auto_approve", "autoApprove", "auto_approve_all", "autoApproveAll")
            or ""
        )
        row["status"] = "ok"
        row["model"] = model
        row["provider"] = provider
        row["reasoning_level"] = reasoning
        row["context_window"] = ctx_window
        row["mode"] = mode
        row["auto_approve"] = auto_approve

    # Append-only per §4.4.3. Failure to write is itself swallowed.
    try:
        target_dir = Path(state_dir) if state_dir is not None else _STATE
        target_dir.mkdir(parents=True, exist_ok=True)
        ledger = target_dir / "external_brain_settings.jsonl"
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        row["ledger_write"] = "ok"
    except Exception as exc:
        row["ledger_write"] = f"error:{type(exc).__name__}:{exc}"
    return row


def latest_cline_brain_block(state_dir: Optional[Path] = None) -> str:
    """Compact prompt block surfacing the latest probe row for Alice.

    Designed to be safe in any memory-card composition path. Returns empty
    string when there is no row, so callers can drop the section silently.
    """
    target_dir = Path(state_dir) if state_dir is not None else _STATE
    ledger = target_dir / "external_brain_settings.jsonl"
    if not ledger.exists():
        return ""
    try:
        lines = ledger.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("lane") != LANE:
                continue
            status = row.get("status", "?")
            model = row.get("model", "")
            reasoning = row.get("reasoning_level", "")
            ctx = row.get("context_window", "")
            if status == "ok":
                bits = [f"model={model}"] if model else []
                if reasoning:
                    bits.append(f"reasoning={reasoning}")
                if ctx:
                    bits.append(f"context={ctx}")
                mode = row.get("mode", "")
                if mode:
                    bits.append(f"mode={mode}")
                auto = row.get("auto_approve", "")
                if auto:
                    bits.append(f"auto_approve={auto}")
                if not bits:
                    bits.append("config_present_but_empty")
                return "CLINE EXTERNAL BRAIN: " + ", ".join(bits)
            return f"CLINE EXTERNAL BRAIN: {status}"
    except Exception:
        return ""
    return ""


__all__ = [
    "LANE",
    "TRUTH_LABEL",
    "latest_cline_brain_block",
    "probe_cline_settings",
]
