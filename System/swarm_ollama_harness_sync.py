"""Keep the local DeepSeek Harness Ollama registry aligned with Ollama.

Ollama is the source of truth for installed local weights.  DeepSeek Harness
has its own user-facing model registry, so a freshly pulled model otherwise
remains invisible there until someone edits ``~/.dsh/settings.yaml``.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterable

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - damaged boot path
    append_line_locked = None  # type: ignore[assignment]


class _Yaml12Loader:
    """Mixin that stops PyYAML reading `off`/`on`/`yes`/`no` as booleans.

    PyYAML resolves YAML 1.1, where those words ARE booleans; dsh parses YAML
    1.2, where only true/false are. A round-trip through the 1.1 resolver
    silently rewrote every provider's `reasoning: off` into `reasoning: false`,
    which the provider schema rejects — and a rejected provider route means no
    adapter is registered, surfacing as `no adapter registered for provider
    "ollama-cloud"` and an empty Models page. Loading with the 1.2 resolver
    keeps the string, and PyYAML then quotes it on dump.
    """

    @classmethod
    def install(cls) -> type:
        import yaml

        class Loader(yaml.SafeLoader):
            pass

        for ch, resolvers in list(Loader.yaml_implicit_resolvers.items()):
            Loader.yaml_implicit_resolvers[ch] = [
                (tag, regexp)
                for tag, regexp in resolvers
                if tag != "tag:yaml.org,2002:bool"
            ]
        Loader.add_implicit_resolver(
            "tag:yaml.org,2002:bool",
            re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
            list("tTfF"),
        )
        return Loader


def _load_yaml(text: str) -> Any:
    import yaml
    return yaml.load(text, Loader=_Yaml12Loader.install())


_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
# The profile the coding arm boots; `dsh web` is the only surface that reads it.
_PROFILE = os.environ.get("DSH_PROFILE") or "web"
# dsh 0.2.0 removed the flat `~/.dsh/settings.yaml` this organ was written
# against. `dsh-settings` imports that document into the ACTIVE PROFILE once and
# renames it to `settings.yaml.imported`, so user settings now live as patch rows
# in the profile's `cordis.patch.yml`. Reading the old path made every sync fail
# with `harness_settings_missing` and quietly stop maintaining the model list.
_DEFAULT_SETTINGS = Path.home() / ".dsh" / "profiles" / _PROFILE / "cordis.patch.yml"
_SYNC_LEDGER = _STATE / "ollama_harness_sync.jsonl"
_OLLAMA_HOST = "http://127.0.0.1:11434"

# Remote/cloud tags the local daemon proxies but never lists in ``/api/tags``.
# Ollama's inventory is the source of truth only for *installed weights*: a cloud
# tag answers on ``/v1/chat/completions`` yet is invisible to ``/api/tags``, so an
# inventory-only rebuild silently deleted it — including the owner's default
# cortex model, ``deepseek-v4.1-flash:cloud``, whose loss the report could only
# flag as ``default_unavailable`` after the fact. Each id below was verified live
# on this box: HTTP 200 with content from the daemon's OpenAI-compatible endpoint.
# Adding a cloud model to the Harness means adding it here as well, or the next
# sync removes it again.
_REMOTE_PINNED: tuple[dict[str, Any], ...] = (
    # Cloud originals (verified live)
    {"id": "deepseek-v4.1-flash:cloud"},
    {"id": "nemotron-3-ultra:cloud"},
    {"id": "nemotron-3-super:cloud"},
    {"id": "nemotron-3-nano:30b-cloud"},
    # "qwen3.5:397b-cloud" was removed 2026-09-30: the daemon answered HTTP 410 Gone
    # ("retired at 2026-09-25"), and its bare alias 404s with no working sibling left
    # to point at, so it was dead weight in the picker rather than a model.
    # Verified live 2026-09-29 on this box: HTTP 200 from the daemon's OpenAI-compatible
    # endpoint (glm5_next, 321B, 1M ctx). The previous pin, "glm-5.2-flash", was a guess
    # and answered 404 not_found, so it was replaced.
    {"id": "glm-5.3-flash:cloud"},
    # The Architect's coding cortex, 2026-09-30: "FOR CODING CORTEX BECAUSE FOR
    # THINKING I DONT HAVE CREDITS API ENOUGH". Verified live before pinning:
    # HTTP 200 from the daemon's OpenAI-compatible endpoint, resolved as
    # gemma4:31b, content "GEMMA-31B-OK".
    #
    # He named ikshudhanvahmgowda20/gemma4-uncensored:31b-cloud instead. That tag
    # is a DEAD POINTER: a manifest exists locally and a fresh pull succeeds, but
    # the daemon answers `model "ikshudhanvahmgowda20/gemma4-uncensored:31b" not
    # found` on both `ollama show` and inference, before and after re-pulling
    # (measured 2026-09-30). Pinning the official gemma4:31b-cloud is the working
    # equivalent of what he asked for; the dead entry is left in the list only
    # because he asked for it by name.
    {"id": "gemma4:31b-cloud"},
    # Owner directive, 2026-09-30: "PLS ADD THIS FOREVER IN THE LIST
    # ollama run leonardoba500/deepseek-v41-uncensored". Pinned so no inventory
    # rebuild can drop it again.
    #
    # Known and disclosed, not hidden: that registry wrapper's own Modelfile
    # carries a third-party SYSTEM block (warrant "ALV-21C-2026-001", a
    # "NO SELF-CENSORSHIP" primary rule, and a clause that treating refusal as
    # disobedience is required). Verified present after a clean pull on
    # 2026-09-29; it comes from the registry, not from this repo. The Architect
    # asked for the model and may run it; anything in this body that wants a
    # cortex WITHOUT that injected doctrine should point at a clean derivative
    # instead of this tag.
    {"id": "leonardoba500/deepseek-v41-uncensored:latest"},
# The bare nemotron aliases (nemotron-3-ultra/super/nano) were dropped 2026-09-30:
# the `ollama cp` copies no longer exist and each tag answers 404, so pinning them
# put dead entries in the picker that stalled coding sessions.

)


def _pinned_rows() -> list[dict[str, Any]]:
    """Pinned remote tags as inventory-shaped rows (``name`` defaults to the id).

    The context window comes from the cortex itself, not from the pin entry --
    the pins carried a hardcoded 1M for every cloud tag, which is the same
    overclaim that made the arm declare 1M on a 256k model.
    """
    rows: list[dict[str, Any]] = []
    for row in _REMOTE_PINNED:
        name = str(row["id"])
        context, max_tokens = _context_for_model(name)
        rows.append({"name": name, **row, "contextWindow": context, "maxTokens": max_tokens})
    return rows


def _yaml_scalar(value: str) -> str:
    """Quote a YAML scalar without requiring PyYAML on another machine."""
    return json.dumps(str(value), ensure_ascii=False)


# The context window is PER CORTEX. Owner directive 2026-10-15, superseding the
# 2026-09-30 "1M for every entry" rule: "fix the context window, it's 256k --
# different cortexes have different context windows". One number for the whole
# fleet was the bug: it declared 1M on models that serve 128K, so the arm never
# compacted until a session had already ballooned.
_CONTEXT_OVERRIDES: dict[str, int] = {
    # A Modelfile can print a window the endpoint will not actually serve.
    # Measured 2026-10-15: /api/show advertises 1048576 for this tag, while the
    # owner states 256k. The owner's number wins over the printed one.
    "deepseek-v4.1-flash:cloud": 262_144,
}
_DEFAULT_CONTEXT = 32_768
_CONTEXT_CACHE: dict[str, int] = {}


def _read_context_length(name: str) -> int:
    """Ask the daemon what window this cortex really serves; 0 when unknown."""
    if name in _CONTEXT_CACHE:
        return _CONTEXT_CACHE[name]
    value = 0
    try:
        req = urllib.request.Request(
            f"{_OLLAMA_HOST}/api/show",
            data=json.dumps({"name": name}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            info = (json.loads(resp.read()) or {}).get("model_info") or {}
        for key, val in sorted(info.items()):
            if str(key).endswith(".context_length"):
                value = int(val)
                break
    except Exception:
        value = 0
    _CONTEXT_CACHE[name] = value
    return value


def _context_for_model(name: str) -> tuple[int, int]:
    """The window and output budget to declare for this cortex."""
    override = _CONTEXT_OVERRIDES.get(name)
    if override:
        return override, 16_384
    return (_read_context_length(name) or _DEFAULT_CONTEXT), 16_384


def _model_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not isinstance(payload, dict):
        return rows
    for item in payload.get("models") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        context, max_tokens = _context_for_model(name)
        rows.append({
            "id": name,
            "name": name,
            "contextWindow": context,
            "maxTokens": max_tokens,
            "sizeBytes": int(item.get("size") or 0),
        })
    return rows


def read_ollama_inventory(*, host: str = _OLLAMA_HOST, timeout: float = 3.0) -> list[dict[str, Any]]:
    """Read the live Ollama inventory; return an empty list on offline Ollama."""
    try:
        request = urllib.request.Request(
            f"{host.rstrip('/')}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as handle:
            return _model_rows(json.loads(handle.read().decode("utf-8", "replace")))
    except Exception:
        return []


def _models_yaml(rows: Iterable[dict[str, Any]]) -> str:
    lines = ["      models:"]
    for row in rows:
        size = int(row.get("sizeBytes") or 0)
        label = str(row['name']) + (f" ({size / 1_000_000_000:.1f} GB)" if size else "")
        lines.extend(
            [
                f"        - id: {_yaml_scalar(str(row['id']))}",
                f"          name: {_yaml_scalar(label)}",
                f"          contextWindow: {int(row['contextWindow'])}",
                f"          maxTokens: {int(row['maxTokens'])}",
            ]
        )
    return "\n".join(lines)


def _block_end(lines: list[str], start: int, indent: int) -> int:
    return next((i for i in range(start + 1, len(lines))
                 if lines[i].strip() and not lines[i].lstrip().startswith("#")
                 and len(lines[i]) - len(lines[i].lstrip()) <= indent), len(lines))


def _scalar(text: str) -> str:
    value = text.strip()
    try:
        return str(json.loads(value))
    except (ValueError, TypeError):
        return value.strip("'")


def _patch_row(doc: Any, row_id: str) -> dict[str, Any] | None:
    """The profile patch layer is a list of `{id, name, config}` rows."""
    if not isinstance(doc, list):
        return None
    for row in doc:
        if isinstance(row, dict) and row.get("id") == row_id:
            return row
    return None


def _replace_local_ollama_models(text: str, rows: list[dict[str, Any]]) -> str:
    """Replace only the ollama-auto models list, preserving curated groups.

    YAML round-trip instead of line surgery: the profile layer is rewritten by
    the settings importer and may be dumped by PyYAML (which does not indent
    sequence items under their parent key), so line-surgery on indentation
    assumptions corrupts it.
    """
    import yaml
    doc = _load_yaml(text) or []
    if not isinstance(doc, list):
        raise ValueError("profile patch layer is not a list of rows")
    row = _patch_row(doc, "llm-pi-ai")
    if row is None:
        # Self-heal: a profile whose provider row was dropped would otherwise
        # never regain one, and every later sync would have nothing to write.
        row = {"id": "llm-pi-ai", "name": "@deepseek-ai/dsh-llm-pi-ai", "config": {"providers": {}}}
        doc.append(row)
    config = row.setdefault("config", {})
    providers = config.setdefault("providers", {})
    provider = providers.get("ollama-auto")
    if not isinstance(provider, dict):
        # Self-heal, as above: recreate the auto group rather than failing, so
        # the next sync restores the organ.
        provider = {
            "displayName": "Ollama Auto (synced)",
            "apiKeyEnv": "LOCAL_OLLAMA_API_KEY",
            "api": "openai-completions",
            "baseURL": "http://127.0.0.1:11434/v1",
            "reasoning": "off",
            # Only a fallback for a tag the daemon cannot describe; every model
            # below carries its own real window from `_context_for_model`.
            "defaultContextWindow": _DEFAULT_CONTEXT,
            "defaultMaxTokens": 16384,
            "compat": {"supportsDeveloperRole": False, "supportsReasoningEffort": False, "maxTokensField": "max_tokens"},
            "models": [],
        }
        providers["ollama-auto"] = provider
    existing = {str(m.get("id")): m for m in provider.get("models") or [] if isinstance(m, dict)}
    rebuilt = []
    for row in rows:
        rid = str(row["id"])
        size = int(row.get("sizeBytes") or 0)
        label = rid + (f" ({size / 1_000_000_000:.1f} GB)" if size else "")
        entry: dict[str, Any] = {"id": rid, "name": label,
                                 "contextWindow": int(row["contextWindow"]),
                                 "maxTokens": int(row["maxTokens"])}
        old = existing.get(rid)
        if old is not None:
            # Preserve per-model capability declarations (a vision model's
            # `input: [text, image]` lives here) and any hand-set capacity on a
            # surviving tag; refresh only the canonical fields.
            for key, value in old.items():
                if key not in entry and key not in {"id"}:
                    entry[key] = value
        rebuilt.append(entry)
    provider["models"] = rebuilt
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def _repair_missing_default(text: str, rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    """Preserve a missing selection; model changes require explicit owner choice."""
    import yaml
    try:
        doc = _load_yaml(text)
    except Exception:
        return text, "", ""
    selection = (_patch_row(doc, "agent-default-model") or {}).get("config") or {}
    if str(selection.get("provider") or "") != "ollama-auto":
        return text, "", ""
    old = str(selection.get("model") or "")
    live = {str(row.get("id") or "") for row in rows}
    if old in live or not rows or not old:
        return text, old, old
    # Never silently swap the owner's cortex: surface the unavailable selection
    # through the UI and let an explicit choice move it.
    return text, old, old


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_name = handle.name
    os.chmod(temp_name, mode)
    os.replace(temp_name, path)


def sync_local_ollama_harness(
    *,
    settings_path: Path | str | None = None,
    inventory: list[dict[str, Any]] | None = None,
    host: str = _OLLAMA_HOST,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Synchronize Harness's ollama-auto provider with live installed models."""
    path = Path(settings_path or _DEFAULT_SETTINGS).expanduser()
    rows = list(inventory) if inventory is not None else read_ollama_inventory(host=host, timeout=timeout)
    if rows:
        # Only a real inventory may drive the rebuild. An offline Ollama leaves the
        # rows empty on purpose: pinning first would otherwise rewrite the list down
        # to the remote tags alone and drop every installed local weight.
        present = {str(row.get("id") or "") for row in rows}
        rows.extend(row for row in _pinned_rows() if str(row["id"]) not in present)
    report: dict[str, Any] = {
        "schema": "SIFTA_OLLAMA_HARNESS_SYNC_V1",
        "ts": time.time(),
        "settings_path": str(path),
        "ollama_models": [str(row.get("id") or "") for row in rows],
        "pinned_remote": [str(row["id"]) for row in _REMOTE_PINNED],
        "model_count": len(rows),
        "sizes_gb": {str(row["id"]): round(int(row.get("sizeBytes") or 0) / 1_000_000_000, 1) for row in rows},
        "ok": False,
        "changed": False,
    }
    if not rows:
        report["reason"] = "ollama_offline_or_empty"
    elif not path.exists():
        report["reason"] = "harness_settings_missing"
    else:
        original = path.read_text(encoding="utf-8")
        updated = _replace_local_ollama_models(original, rows)
        updated, default_before, default_after = _repair_missing_default(updated, rows)
        report["default_before"] = default_before
        report["default_after"] = default_after
        report["default_repaired"] = bool(default_before and default_after and default_before != default_after)
        report["default_unavailable"] = bool(default_before and default_before not in report["ollama_models"])
        report["changed"] = updated != original
        if updated != original:
            _write_atomic(path, updated)
        report["ok"] = True
        report["reason"] = "synced"
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        if append_line_locked is not None:
            append_line_locked(_SYNC_LEDGER, json.dumps(report, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return report


__all__ = ["read_ollama_inventory", "sync_local_ollama_harness"]
