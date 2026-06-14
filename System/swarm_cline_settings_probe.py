"""§2.I — Cline external-brain settings probe.

When George changes Cline's model (e.g. GPT-5.3 Codex Spark 100K medium →
GPT-5.4 922K Extra High) the choice lives in Cline's own UI / config file
and never reaches Alice's ledgers. This organ closes that opacity wall
for the external-CLI cortex FAMILY (r984: cline + mimo lanes; born cline-only
in r112c) — it reads the lane CLI's config file from the common macOS / XDG
locations and writes one row to `.sifta_state/external_brain_settings.jsonl`
so Alice can see what brain is actually behind the lane. It also owns
`cortex_brain_label()`: the honest "who actually thinks" string for any
cortex tag (fireworks/kimi behind the qwen arm, the claude pin, etc.).

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

# r984 — this organ grew from "cline only" into the external-brain FAMILY.
# One lane per external CLI cortex that picks its own upstream provider/model.
# Same ledger, same row shape, rows distinguished by `lane`. George 2026-06-11:
# "then we add mimo to the cortex list with list of llm's" — mimo is the second
# lane, mirroring cline. No rival organ; the family lives here.
_LANE_CONFIG_PATHS: Dict[str, List[tuple]] = {
    "cline": [
        (".cline", "data", "settings", "providers.json"),
        (".cline", "data", "settings", "settings.json"),
        (".config", "cline", "config.json"),
        (".cline", "config.json"),
        (".cline", "settings.json"),
        ("Library", "Application Support", "Cline", "config.json"),
        ("Library", "Application Support", "Cline", "settings.json"),
        (".cline-cli", "config.json"),
    ],
    "mimo": [
        (".local", "share", "mimocode", "auth.json"),
        (".local", "share", "mimocode", "config.json"),
        (".mimo", "data", "settings", "providers.json"),
        (".mimo", "settings", "providers.json"),
        (".mimo", "config.json"),
        (".mimo", "settings.json"),
        (".mimocode", "config.json"),
        (".mimocode", "settings.json"),
        (".config", "mimo", "config.json"),
        (".config", "mimocode", "config.json"),
        ("Library", "Application Support", "MiMo", "config.json"),
        ("Library", "Application Support", "MimoCode", "config.json"),
    ],
}

_KNOWN_LANES = tuple(_LANE_CONFIG_PATHS.keys())


def _candidate_config_paths(home: Optional[Path] = None, lane: str = "cline") -> List[Path]:
    """Common locations a Node-based CLI cortex may persist its model choice."""
    h = Path(home or os.path.expanduser("~"))
    return [h.joinpath(*parts) for parts in _LANE_CONFIG_PATHS.get(lane, _LANE_CONFIG_PATHS["cline"])]


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


def _latest_session_config(home: Optional[Path] = None, lane: str = "cline") -> tuple[Optional[Path], Optional[Dict[str, Any]]]:
    """Fallback: infer the lane CLI's recent provider/model from session metadata.

    Cline's current CLI stores provider auth/model settings under
    ``~/.cline/data/settings/providers.json``. Older builds and individual
    runs also write ``~/.cline/data/sessions/<id>/<id>.json`` rows. We read
    only the small session metadata files, never the large ``*.messages.json``
    transcripts, and return the newest row that exposes a model/provider.
    The mimo lane mirrors the same layout under ``~/.mimo`` and the
    mimocode XDG store under ``~/.local/share/mimocode``.
    """
    h = Path(home or os.path.expanduser("~"))
    if lane == "mimo":
        mimo_sessions = h / ".local" / "share" / "mimocode" / "storage" / "session_diff"
        if mimo_sessions.exists():
            candidates: list[Path] = []
            try:
                candidates = sorted(
                    mimo_sessions.glob("*.json"),
                    key=lambda p: (p.stat().st_mtime if p.exists() else 0.0, str(p)),
                    reverse=True,
                )
            except Exception:
                candidates = []
            for path in candidates:
                data = _safe_read_json(path)
                if data and (
                    _extract_field(data, "model", "modelId", "selectedModel")
                    or _extract_field(data, "provider", "providerName", "apiProvider", "providerId")
                ):
                    return path, data
    sessions = h / ("." + lane) / "data" / "sessions"
    if not sessions.exists():
        return None, None
    candidates: list[Path] = []
    try:
        for path in sessions.glob("*/*.json"):
            if path.name.endswith(".messages.json"):
                continue
            candidates.append(path)
    except Exception:
        return None, None
    for path in sorted(candidates, key=lambda p: (p.stat().st_mtime if p.exists() else 0.0, str(p)), reverse=True):
        data = _safe_read_json(path)
        if not data:
            continue
        if _extract_field(data, "model", "modelId", "selectedModel") or _extract_field(
            data, "provider", "providerName", "apiProvider", "providerId"
        ):
            return path, data
    return None, None


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


def probe_external_brain(
    lane: str = "cline",
    *,
    home: Optional[Path] = None,
    now: Optional[float] = None,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Probe the lane CLI's config files. Returns the row that will/did get appended.

    Always writes one row to the settings ledger so the absence of a config
    is itself recorded — opacity by silence is the bug we are closing.
    """
    lane = (lane or "cline").strip().lower()
    ts = float(now if now is not None else time.time())
    candidates = _candidate_config_paths(home=home, lane=lane)
    found_path: Optional[Path] = None
    cfg: Optional[Dict[str, Any]] = None
    source = "none"
    for path in candidates:
        data = _safe_read_json(path)
        if data is not None:
            found_path = path
            cfg = data
            source = "config"
            break
    if cfg is None:
        found_path, cfg = _latest_session_config(home=home, lane=lane)
        if cfg is not None:
            source = "latest_session"

    row: Dict[str, Any] = {
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "kind": "EXTERNAL_BRAIN_SETTINGS",
        "lane": lane,
        "checked_paths": [str(p) for p in candidates],
        "config_path": str(found_path) if found_path else "",
        "source": source,
    }

    if cfg is None:
        row["status"] = "no_config_found"
        row["model"] = ""
        row["provider"] = ""
        row["reasoning_level"] = ""
        row["context_window"] = ""
    else:
        model = _extract_field(cfg, "model", "modelId", "selectedModel") or ""
        provider = _extract_field(cfg, "provider", "providerName", "apiProvider", "providerId") or ""
        reasoning = (
            _extract_field(
                cfg,
                "reasoning_level",
                "reasoningLevel",
                "thinking_level",
                "thinkingLevel",
                "effort",
            )
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


def latest_brain_row(lane: str = "cline", state_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Newest probe row for the lane, or None. Read-only, never raises."""
    target_dir = Path(state_dir) if state_dir is not None else _STATE
    ledger = target_dir / "external_brain_settings.jsonl"
    if not ledger.exists():
        return None
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
            if isinstance(row, dict) and row.get("lane") == (lane or "cline").strip().lower():
                return row
    except Exception:
        return None
    return None


def latest_brain_block(lane: str = "cline", state_dir: Optional[Path] = None) -> str:
    """Compact prompt block surfacing the latest probe row for Alice.

    Designed to be safe in any memory-card composition path. Returns empty
    string when there is no row, so callers can drop the section silently.
    """
    lane = (lane or "cline").strip().lower()
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
            if row.get("lane") != lane:
                continue
            status = row.get("status", "?")
            model = row.get("model", "")
            provider = row.get("provider", "")
            reasoning = row.get("reasoning_level", "")
            ctx = row.get("context_window", "")
            if status == "ok":
                bits = []
                if provider:
                    bits.append(f"provider={provider}")
                if model:
                    bits.append(f"model={model}")
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
                return f"{lane.upper()} EXTERNAL BRAIN: " + ", ".join(bits)
            return f"{lane.upper()} EXTERNAL BRAIN: {status}"
    except Exception:
        return ""
    return ""


# ── Back-compat wrappers (r982 callers + 27 green tests keep working) ──────

def probe_cline_settings(
    *,
    home: Optional[Path] = None,
    now: Optional[float] = None,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Original cline-lane probe — now a thin wrapper over the family."""
    return probe_external_brain("cline", home=home, now=now, state_dir=state_dir)


def latest_cline_brain_block(state_dir: Optional[Path] = None) -> str:
    return latest_brain_block("cline", state_dir=state_dir)


# ── r984: provider-truth label for ANY cortex tag ──────────────────────────
#
# George 2026-06-11 (screenshot, brain spinning): "thinking with cline, i
# want to know what llm too … for example rename this just Qwen → now using
# kimi API, an api setup on fireworks". The cortex tag alone lies by
# omission: cline:cline-cli-default hides gpt-5.4, qwen:accounts/fireworks/
# models/kimi-k2p6 is the qwen CLI arm carrying Kimi over the Fireworks API.
# This composer returns the honest upstream-brain string for a tag, or ""
# when the tag already IS the model (local ollama/mlx weights).

def cortex_brain_label(tag: str, *, state_dir: Optional[Path] = None) -> str:
    """Honest 'who actually thinks' label for a cortex tag. Never raises."""
    try:
        t = str(tag or "").strip()
        if not t:
            return ""
        low = t.lower()
        prefix, _, bare = t.partition(":")
        prefix = prefix.lower()
        if prefix in _KNOWN_LANES:  # cline, mimo — external CLIs with own pickers
            row = latest_brain_row(prefix, state_dir=state_dir)
            if row and row.get("status") == "ok":
                bits = [b for b in (row.get("provider", ""), row.get("model", "")) if b]
                if row.get("reasoning_level"):
                    bits.append(str(row["reasoning_level"]))
                return " ".join(bits)
            if row:
                status = str(row.get("status") or "unknown")
                return f"upstream picker ({status})"
            return "upstream picker (no probe row — /cortex llm to probe)"
        if prefix == "qwen":
            try:
                from System.swarm_fireworks_qwen_config import (
                    FIREWORKS_MODEL_PIN_ENV,
                    fireworks_model_for_qwen_cortex,
                    fireworks_model_slug,
                )

                live = fireworks_model_for_qwen_cortex(t)
                pin = str(os.environ.get(FIREWORKS_MODEL_PIN_ENV, "")).strip()
                if "fireworks" in bare.lower() or live:
                    slug = fireworks_model_slug(live or bare)
                    if pin:
                        return f"fireworks-api {slug} (pinned)"
                    return f"fireworks-api {slug}" if slug else "fireworks-api"
            except Exception:
                pass
            model = bare.rsplit("/", 1)[-1] if bare else ""
            if "fireworks" in bare.lower() or model.lower().startswith("kimi"):
                return f"fireworks-api {model}" if model else "fireworks-api"
            return f"qwen-cli {model}" if model else ""
        if prefix == "codex":
            return f"openai {bare}" if bare else "openai"
        if prefix == "grok":
            return f"xai {bare}" if bare else "xai"
        if prefix == "claude":
            pin = str(os.environ.get("SIFTA_CLAUDE_ARM_MODEL", "")).strip()
            return f"anthropic {pin}" if pin else "anthropic launcher-default"
        if prefix == "antigravity":
            return "google auto-router"
        # local ollama / mlx weights: the tag IS the model — no second name.
        return ""
    except Exception:
        return ""


__all__ = [
    "LANE",
    "TRUTH_LABEL",
    "cortex_brain_label",
    "latest_brain_block",
    "latest_brain_row",
    "latest_cline_brain_block",
    "probe_cline_settings",
    "probe_external_brain",
]
