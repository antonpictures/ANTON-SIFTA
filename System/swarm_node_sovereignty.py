#!/usr/bin/env python3
"""Node sovereignty and hardware-molded model policy.

SIFTA species code can be shared by many machines. Local Alice identity cannot.
This module keeps those boundaries executable:

* hardware facts shape model choice;
* local roles such as ``web_host`` reserve memory for public services;
* private organism paths are flagged before they leak into git;
* serial numbers are hashed for federation summaries unless an explicit
  Covenant hardware receipt requires raw disclosure.

The module is intentionally deterministic and side-effect free unless callers
ask for ``probe_hardware_profile()`` / ``probe_ollama_models()``.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_NODE_ROLE = _STATE / "node_role.json"

TINY_LOCAL_MODELS: tuple[str, ...] = (
    "qwen3.5:0.8b",
    "alice-phc-0.8b-cure:latest",
    "qwen2.5:1.5b",
)

SMALL_LOCAL_MODELS: tuple[str, ...] = (
    "qwen3.5:2b",
    "qwen2.5:3b",
    "huihui_ai/qwen3.5-abliterated:2b",
    "alice-qwen-phc:latest",
)

HEAVY_LOCAL_MODELS: tuple[str, ...] = (
    "huihui_ai/gemma-4-abliterated:latest",
    "gemma4:latest",
    "gemma-4:latest",
)

PRIVATE_PATH_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(^|/)\.sifta_state(/|$)"), "local organism state"),
    (re.compile(r"(^|/)owner_genesis\.json$"), "hardware-bound owner genesis"),
    (re.compile(r"(^|/)long_term_engrams\.jsonl$"), "private memory"),
    (re.compile(r"(^|/)work_receipts\.jsonl$"), "live local work ledger"),
    (re.compile(r"(^|/)ide_stigmergic_trace\.jsonl$"), "live local IDE trace"),
    (re.compile(r"(^|/)wormhole_cache(/|$)"), "session-local wormhole cache"),
    (re.compile(r"\.(key|pem|seed)$", re.IGNORECASE), "cryptographic secret"),
)

PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)")
LOCAL_IP_RE = re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[0-1]))\.\d{1,3}\.\d{1,3}\b")


@dataclass(frozen=True)
class HardwareProfile:
    """Local machine capabilities, safe to summarize after serial hashing."""

    node_serial_hash: str = "UNKNOWN"
    raw_serial_present: bool = False
    chip: str = "UNKNOWN"
    ram_gb: float = 0.0
    role: str = "desktop_alice"
    public_services: int = 0
    installed_models: tuple[str, ...] = ()
    thermal_state: str = "unknown"

    @property
    def safe_model_tier(self) -> str:
        role = self.role.lower()
        if self.ram_gb <= 8.5 or "web_host" in role or self.public_services >= 2:
            return "tiny_local"
        if self.ram_gb < 24:
            return "small_local"
        return "heavy_local"

    def as_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["installed_models"] = list(self.installed_models)
        data["safe_model_tier"] = self.safe_model_tier
        return data


@dataclass(frozen=True)
class ModelDecision:
    app_context: str
    selected_model: str
    fallback_chain: tuple[str, ...]
    safe_model_tier: str
    allowed_to_autopull: bool
    reason: str
    forbidden_models: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fallback_chain"] = list(self.fallback_chain)
        data["forbidden_models"] = list(self.forbidden_models)
        return data


@dataclass(frozen=True)
class SovereigntyFinding:
    path: str
    severity: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def serial_hash(serial: str) -> str:
    clean = str(serial or "").strip()
    if not clean or clean.upper() == "UNKNOWN":
        return "UNKNOWN"
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]


def _parse_ram_gb(memory_line: str) -> float:
    text = str(memory_line or "").strip().lower()
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(tb|gb|mb)?", text)
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = (m.group(2) or "gb").lower()
    if unit == "tb":
        return value * 1024.0
    if unit == "mb":
        return value / 1024.0
    return value


def parse_system_profiler_hardware(output: str) -> dict[str, Any]:
    """Parse ``system_profiler SPHardwareDataType`` text into coarse facts."""
    facts: dict[str, str] = {}
    for raw in str(output or "").splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        facts[key.strip().lower()] = value.strip()
    serial = facts.get("serial number (system)") or facts.get("serial number") or "UNKNOWN"
    return {
        "serial": serial,
        "serial_hash": serial_hash(serial),
        "chip": facts.get("chip") or facts.get("processor name") or "UNKNOWN",
        "ram_gb": _parse_ram_gb(facts.get("memory", "")),
    }


def parse_ollama_tags(output: str) -> tuple[str, ...]:
    """Parse ``ollama list`` output; ignores headers and empty lines."""
    tags: list[str] = []
    for raw in str(output or "").splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("name"):
            continue
        tag = line.split()[0]
        if ":" in tag:
            tags.append(tag)
    return tuple(dict.fromkeys(tags))


def load_node_role(path: Path = _NODE_ROLE) -> dict[str, Any]:
    if not path.exists():
        return {"role": "desktop_alice", "public_services": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"role": "desktop_alice", "public_services": 0}
    return data if isinstance(data, dict) else {"role": "desktop_alice", "public_services": 0}


def build_hardware_profile(
    *,
    system_profiler_output: str = "",
    installed_models: Sequence[str] = (),
    node_role: Mapping[str, Any] | None = None,
    thermal_state: str = "unknown",
) -> HardwareProfile:
    facts = parse_system_profiler_hardware(system_profiler_output)
    role_data = dict(node_role or {})
    return HardwareProfile(
        node_serial_hash=str(facts.get("serial_hash") or "UNKNOWN"),
        raw_serial_present=bool(facts.get("serial") and facts.get("serial") != "UNKNOWN"),
        chip=str(facts.get("chip") or "UNKNOWN"),
        ram_gb=float(facts.get("ram_gb") or 0.0),
        role=str(role_data.get("role") or "desktop_alice"),
        public_services=int(role_data.get("public_services") or 0),
        installed_models=tuple(dict.fromkeys(str(m) for m in installed_models if m)),
        thermal_state=str(thermal_state or "unknown"),
    )


def _preferred_models_for(profile: HardwareProfile, app_context: str) -> tuple[str, ...]:
    tier = profile.safe_model_tier
    if tier == "tiny_local":
        return TINY_LOCAL_MODELS + SMALL_LOCAL_MODELS
    if tier == "small_local":
        return SMALL_LOCAL_MODELS + TINY_LOCAL_MODELS
    if app_context in {"long_reasoning", "tournament", "cortex_probe"}:
        return HEAVY_LOCAL_MODELS + SMALL_LOCAL_MODELS + TINY_LOCAL_MODELS
    return SMALL_LOCAL_MODELS + HEAVY_LOCAL_MODELS + TINY_LOCAL_MODELS


def resolve_node_model(
    profile: HardwareProfile,
    *,
    app_context: str = "talk_to_alice",
    owner_override: str | None = None,
) -> ModelDecision:
    """Select a local model without confusing node identity with repo identity."""
    installed = set(profile.installed_models)
    forbidden = HEAVY_LOCAL_MODELS if profile.safe_model_tier == "tiny_local" else ()

    if owner_override:
        if owner_override in forbidden:
            return ModelDecision(
                app_context=app_context,
                selected_model="",
                fallback_chain=tuple(m for m in _preferred_models_for(profile, app_context) if m in installed),
                safe_model_tier=profile.safe_model_tier,
                allowed_to_autopull=False,
                reason=f"owner_override_rejected_for_{profile.safe_model_tier}: {owner_override}",
                forbidden_models=tuple(forbidden),
            )
        if owner_override in installed:
            return ModelDecision(
                app_context=app_context,
                selected_model=owner_override,
                fallback_chain=(owner_override,),
                safe_model_tier=profile.safe_model_tier,
                allowed_to_autopull=False,
                reason="owner_override_installed",
                forbidden_models=tuple(forbidden),
            )

    preferred = _preferred_models_for(profile, app_context)
    fallback = tuple(m for m in preferred if m in installed and m not in forbidden)
    selected = fallback[0] if fallback else ""
    if selected:
        reason = f"{profile.safe_model_tier}_installed_match"
    else:
        reason = f"no_installed_model_in_{profile.safe_model_tier}_policy"
    return ModelDecision(
        app_context=app_context,
        selected_model=selected,
        fallback_chain=fallback,
        safe_model_tier=profile.safe_model_tier,
        allowed_to_autopull=False,
        reason=reason,
        forbidden_models=tuple(forbidden),
    )


def scan_sovereignty_paths(paths: Iterable[str]) -> list[SovereigntyFinding]:
    """Flag paths that must not enter public species DNA commits."""
    findings: list[SovereigntyFinding] = []
    for raw in paths:
        path = str(raw).strip()
        normalized = path.replace("\\", "/")
        for pattern, reason in PRIVATE_PATH_PATTERNS:
            if pattern.search(normalized):
                findings.append(SovereigntyFinding(path=path, severity="block", reason=reason))
                break
    return findings


def scan_text_for_node_leaks(text: str) -> list[SovereigntyFinding]:
    findings: list[SovereigntyFinding] = []
    if PHONE_RE.search(text or ""):
        findings.append(SovereigntyFinding(path="<text>", severity="review", reason="possible phone number"))
    if LOCAL_IP_RE.search(text or ""):
        findings.append(SovereigntyFinding(path="<text>", severity="review", reason="local/private IP address"))
    return findings


def probe_hardware_profile() -> HardwareProfile:
    hw = subprocess.run(
        ["system_profiler", "SPHardwareDataType"],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    ).stdout
    try:
        ollama = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        ollama = ""
    return build_hardware_profile(
        system_profiler_output=hw,
        installed_models=parse_ollama_tags(ollama),
        node_role=load_node_role(),
    )


def node_policy_summary(profile: HardwareProfile, *, app_context: str = "talk_to_alice") -> dict[str, Any]:
    decision = resolve_node_model(profile, app_context=app_context)
    return {
        "schema": "SIFTA_NODE_SOVEREIGNTY_V1",
        "profile": profile.as_public_dict(),
        "model_decision": decision.as_dict(),
        "species_identity_rule": "repo_is_species_dna_not_local_alice_selfhood",
        "federation_rule": "exchange_receipts_hashes_summaries_never_raw_sifta_state",
    }


__all__ = [
    "HEAVY_LOCAL_MODELS",
    "HardwareProfile",
    "ModelDecision",
    "SovereigntyFinding",
    "build_hardware_profile",
    "load_node_role",
    "node_policy_summary",
    "parse_ollama_tags",
    "parse_system_profiler_hardware",
    "probe_hardware_profile",
    "resolve_node_model",
    "scan_sovereignty_paths",
    "scan_text_for_node_leaks",
    "serial_hash",
]


if __name__ == "__main__":
    print(json.dumps(node_policy_summary(probe_hardware_profile()), indent=2))
