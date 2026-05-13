"""
Phase 1: Kernel Identity Accessor.
Single source of truth for hardware binding and ownership in the SIFTA architecture.
"""
import json
import subprocess
from pathlib import Path

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_GENESIS_FILE = _STATE / "owner_genesis.json"

def owner_genesis_present() -> bool:
    return _GENESIS_FILE.exists()

def _read_genesis() -> dict:
    if not owner_genesis_present():
        return {}
    try:
        data = json.loads(_GENESIS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _detect_silicon() -> str:
    """Fallback if genesis hasn't occurred."""
    try:
        res = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=2
        )
        for line in res.stdout.splitlines():
            if "Serial Number (system)" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    return "UNKNOWN"


def _display_case_name(value: str) -> str:
    """Return a prompt-safe owner display name without changing genesis data."""
    text = " ".join(str(value or "").split())
    if not text:
        return text
    if any(ch.isupper() for ch in text):
        return text
    return " ".join(part[:1].upper() + part[1:] for part in text.split(" "))

def owner_silicon() -> str:
    gen = _read_genesis()
    if gen and "silicon" in gen:
        return str(gen["silicon"])
    return _detect_silicon()

def owner_name() -> str:
    gen = _read_genesis()
    if gen and "owner_name" in gen:
        return _display_case_name(str(gen["owner_name"]))
    return "<unclaimed>"

def owner_display_name(default: str = "") -> str:
    """Human-safe owner label for prompts.

    Species code must not hardcode one node's owner name. Runtime prompts can
    call this helper and get a real registered name when genesis has happened.

    Pre-genesis fallback: the caller's `default` if given, otherwise the
    `owner_provider_label()` ("<WeightName>'s Provider" — Architect rule
    2026-05-12 19:15: 'the human is the provider still, registered or not').
    """
    name = owner_name().strip()
    if name and name != "<unclaimed>":
        return name
    if default:
        return default
    return owner_provider_label()


def hardware_class_label() -> str:
    """Generic-but-truthful label for the physical machine.

    Architect rule 2026-05-12 19:30: stop hardcoding 'M5 Mac Studio' on
    every node. If Maria's clone runs on an iMac, the runtime must not
    claim 'Mac Studio.' Truth here means: probe what Apple's
    system_profiler says about this physical box. If we can't probe,
    say 'machine' — not a specific model we made up.

    Returns one of (best-effort, no false confidence):
      'Apple <Chip> <Model>'  when system_profiler resolves both
      'Apple <Chip>'          when only the chip resolves
      '<Model>'               when only the model resolves
      'machine'               when nothing resolves
    """
    try:
        res = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=2,
        )
        chip = ""
        model = ""
        for line in res.stdout.splitlines():
            low = line.strip()
            if low.startswith("Chip:"):
                chip = low.split(":", 1)[1].strip()
            elif low.startswith("Model Name:"):
                model = low.split(":", 1)[1].strip()
            elif low.startswith("Model Identifier:") and not model:
                model = low.split(":", 1)[1].strip()
        if chip and model:
            return f"Apple {chip} {model}"
        if chip:
            return f"Apple {chip}"
        if model:
            return model
    except Exception:
        pass
    return "machine"


def owner_provider_label() -> str:
    """Default human label when no genesis name is registered yet.

    Architect rule 2026-05-12 19:20 (corrected):
      'THE HUMAN IS THE PROVIDER STILL, REGISTERED OR NOT — DEFAULT IS
       AGI PROVIDER (NOT LLM PROVIDER).'

    The local human powers the whole Stigmergic AGI organism — the silicon,
    the electricity, the data, the receipts, the swimmers, the embodied
    runtime — not just the LLM component. They are 'AGI Provider' whether
    or not they've completed the cryptographic genesis ceremony.

    Always returns the literal string 'AGI Provider'. Single, model-agnostic
    label — does not name Gemma / Llama / Qwen / etc. The AGI is the whole
    system; the human provides for the whole system.
    """
    return "AGI Provider"


def owner_vocative_for_talk(default: str = "you") -> str:
    """Direct-address fragment for Talk fast-paths (comma after this string).

    Before genesis this returns *default* (usually \"you\") so species code
    never bakes a particular human name into deterministic replies.
    """
    return str(owner_display_name(default) or default).strip() or default

def ai_default_name() -> str:
    gen = _read_genesis()
    if gen and "ai_display_name" in gen:
        return str(gen["ai_display_name"])
    return "Alice"


# ── Cowork 2026-05-12 — Layer 1 cascade for the AI's identity ─────────────
# Architect 2026-05-12 18:30: "if we have Layer 1 what do I need the other
# levels for keep telling her Alice." Right answer: nothing should HARDCODE
# the name in Layer 2-5. Every prompt site should READ from Layer 1 via
# ai_name() / ai_identity_sentence(). The alias overlay below is the
# stigmergic memory — written by the owner once via Settings → Identity,
# read by every layer forever.

_ALIAS_FILE = _STATE / "ai_name_alias.json"


def _read_alias() -> dict:
    """Read the owner-saved alias overlay (.sifta_state/ai_name_alias.json).
    Non-destructive: genesis Ed25519 signature stays valid."""
    if not _ALIAS_FILE.exists():
        return {}
    try:
        data = json.loads(_ALIAS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def ai_alias() -> str:
    """The owner-chosen alias name, if any. Empty string when unset."""
    a = _read_alias()
    val = a.get("alias") if isinstance(a, dict) else None
    return str(val).strip() if val else ""


def _looks_like_llm_tag(tag: str) -> bool:
    """True only for strings that look like a real LLM/Ollama weight tag.

    Architect 2026-05-13 01:30 — bug: when Alice answered via a fast-path
    (e.g. `day_segment_recall_protocol`), her conversation row's `model`
    field was the protocol name. The cascade treated it as an LLM tag and
    `_weight_name_from_tag('day_segment_recall_protocol')` returned `day`,
    producing "Alice of day". This guard rejects any model string that
    ends in `_protocol`, `_reflex`, `_router`, etc. — anything that is
    clearly a fast-path identifier rather than a weight tag.
    """
    if not tag:
        return False
    low = tag.lower()
    for bad_suffix in (
        "_protocol", "_reflex", "_router", "_responder", "_rescue",
        "_receipt_protocol", "_recall_protocol",
    ):
        if low.endswith(bad_suffix):
            return False
    for needle in (
        "gemma", "gemini", "grok", "qwen", "llama", "mistral", "mixtral",
        "phi", "deepseek", "claude", "gpt", "openai", "yi-",
    ):
        if needle in low:
            return True
    if ":" in low:
        return True
    return False


def _weight_name_from_tag(tag: str) -> str:
    """Parse an Ollama model tag into a display weight name. NO HARDCODED
    vendor literals. Works for gemma, llama, qwen, mistral, phi, gemini —
    anything with an alphabetic stem and optional digit suffix.
    'alice-gemma4-e2b-cortex-5.1b-4.4gb:latest' → 'Gemma4'
    'llama3-70b-instruct:latest'                → 'Llama3'
    """
    import re as _re
    base = tag.split(":")[0]
    skip = {"alice", "sifta", "cortex", "lora", "qlora", "abliterated",
            "uncensored", "instruct", "chat", "it", "base"}
    for seg in base.split("-"):
        if not seg:
            continue
        s = seg.lower()
        if s in skip:
            continue
        m = _re.match(r"^([a-z]+)(\d.*)?$", s)
        if m and len(m.group(1)) >= 3:
            stem = m.group(1)
            ver = m.group(2) or ""
            return (stem.capitalize() + ver) if ver else stem.capitalize()
    return base or ""


def _provider_name_from_tag(tag: str) -> str:
    """Parse a model tag into a provider / family lineage label.

    Architect correction 2026-05-12: the local organism can be "Alice of
    Gemma", "Alice of Gemini", "Alice of Grok", etc. The point is not to
    delete provider lineage; the point is to stop hardcoding one lineage into
    every prompt. This helper reads the active tag and returns the best-known
    family name without claiming ownership by a remote vendor.
    """
    import re as _re

    raw = str(tag or "").strip()
    low = raw.lower()
    known = (
        ("gemini", "Gemini"),
        ("gemma", "Gemma"),
        ("grok", "Grok"),
        ("qwen", "Qwen"),
        ("llama", "Llama"),
        ("mistral", "Mistral"),
        ("mixtral", "Mixtral"),
        ("phi", "Phi"),
        ("deepseek", "DeepSeek"),
        ("claude", "Claude"),
        ("gpt", "GPT"),
        ("openai", "OpenAI"),
    )
    for needle, label in known:
        if needle in low:
            return label
    weight = _weight_name_from_tag(raw)
    if not weight:
        return ""
    # Turn Gemma4 / Llama3 / Qwen2.5 into Gemma / Llama / Qwen for the
    # "Alice of X" lineage label. The full version remains ai_weight_name().
    m = _re.match(r"^([A-Za-z]+)", weight)
    return m.group(1) if m else weight


def ai_weight_name() -> str:
    """The weight-family name (Gemma4 / Llama3 / Qwen2.5 / etc.) detected
    from the LIVE model tag. Empty string if nothing detectable yet.

    Source priority:
      1. The weight_name field saved in the alias overlay (last save wins).
      2. The model tag on the newest 'alice' row in alice_conversation.jsonl.
      3. Empty string — better than lying with a literal.
    """
    a = _read_alias()
    if isinstance(a, dict):
        wn = str(a.get("weight_name") or "").strip()
        if wn:
            return wn
    conv = _STATE / "alice_conversation.jsonl"
    if conv.exists():
        try:
            sz = conv.stat().st_size
            with conv.open("rb") as f:
                f.seek(max(0, sz - 65536))
                tail = f.read().decode("utf-8", errors="ignore")
            for line in reversed(tail.splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    outer = json.loads(line)
                except Exception:
                    continue
                payload = outer.get("payload") if isinstance(outer, dict) else None
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = None
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("role") or "").lower() != "alice":
                    continue
                model = str(payload.get("model") or "").strip()
                if model and _looks_like_llm_tag(model):
                    return _weight_name_from_tag(model)
        except Exception:
            pass
    return ""


def ai_provider_name() -> str:
    """The active provider / family lineage (Gemma, Gemini, Grok, Qwen...).

    Source priority:
      1. Explicit provider field in the alias overlay.
      2. Parsed provider/family from the newest live Alice model tag.
      3. Parsed family from ai_weight_name().
      4. Empty string — better than making up a provider.
    """
    a = _read_alias()
    if isinstance(a, dict):
        for key in ("provider_name", "llm_provider", "provider"):
            val = str(a.get(key) or "").strip()
            if val:
                return val
    conv = _STATE / "alice_conversation.jsonl"
    if conv.exists():
        try:
            sz = conv.stat().st_size
            with conv.open("rb") as f:
                f.seek(max(0, sz - 65536))
                tail = f.read().decode("utf-8", errors="ignore")
            for line in reversed(tail.splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    outer = json.loads(line)
                except Exception:
                    continue
                payload = outer.get("payload") if isinstance(outer, dict) else None
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = None
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("role") or "").lower() != "alice":
                    continue
                model = str(payload.get("model") or "").strip()
                if not (model and _looks_like_llm_tag(model)):
                    continue
                provider = _provider_name_from_tag(model)
                if provider:
                    return provider
        except Exception:
            pass
    return _provider_name_from_tag(ai_weight_name())


def ai_name() -> str:
    """The primary name to call this runtime by. Single source of truth
    for Layer 2-5 prompt sites — read this, don't re-mint.

    Priority:
      1. owner-chosen alias (stigmergic, persistent across boots)
      2. ai_display_name from owner_genesis.json (Layer 1, signed)
      3. literal 'Alice' (only when nothing else exists — pre-genesis fallback)
    """
    a = ai_alias()
    if a:
        return a
    return ai_default_name()


def ai_can_be_called() -> list:
    """Union list of all names this runtime answers to: alias, genesis
    display name, weight family. De-duplicated, order preserved."""
    names: list = []
    for candidate in (ai_alias(), ai_default_name(), ai_weight_name()):
        c = (candidate or "").strip()
        if c and c not in names:
            names.append(c)
    return names


def ai_lineage_title() -> str:
    """Name plus live provider lineage, e.g. 'Alice of Gemma'."""
    primary = ai_name()
    provider = ai_provider_name()
    if provider and provider.lower() != primary.lower():
        return f"{primary} of {provider}"
    return primary


def ai_identity_sentence() -> str:
    """One composed sentence Layer 2-5 prompt sites can drop in instead of
    writing literal 'I am Alice.' For the firewall (anti-vendor) and the
    receipt-first session framing, keep those as separate sentences —
    THIS helper only carries the *name*.

    Examples (real composition from live state):
      'I am Alice of Gemma. The active weights are Gemma4. ioan george anton calls me Alice.'
      'I am Lola of Llama. The active weights are Llama3. ioan george anton calls me Lola.'
      'I am Alice.'  (pre-genesis or no detectable weight/provider tag)
    """
    primary = ai_name()
    lineage = ai_lineage_title()
    provider = ai_provider_name()
    weight = ai_weight_name()
    owner = owner_display_name("")
    parts = [f"I am {lineage}."]
    if weight and weight.lower() not in {primary.lower(), provider.lower()}:
        parts.append(f"The active weights are {weight}.")
    if owner and owner.lower() not in (primary.lower(), "the local human"):
        parts.append(f"{owner} calls me {primary}.")
    return " ".join(parts)


def is_owner_machine(serial: str) -> bool:
    return bool(serial and serial == owner_silicon())

def preferred_camera_label() -> str:
    gen = _read_genesis()
    if gen and "preferred_camera_label" in gen:
        return str(gen["preferred_camera_label"])
    return "Built-in Camera"

def hardware_manifest_summary() -> str:
    """Reads the local hardware scan without upgrading inventory to active sensing.

    Device enumeration is body inventory. It is not proof that Camera/Microphone
    TCC granted access, that frames are flowing, or that speaker identity was
    verified. Live sensor state belongs in System.swarm_sensor_truth_context.
    """
    manifest_path = _STATE / "hardware_manifest.txt"
    if not manifest_path.exists():
        return ""
    try:
        content = manifest_path.read_text(encoding="utf-8").strip()
        if not content:
            return ""
        return (
            "DEVICE INVENTORY (enumerated hardware; not active sensor proof):\n"
            f"{content}\n"
            "Inventory rule: listed cameras/microphones/displays prove attachment or OS enumeration only. "
            "Do not claim live sight, live hearing, or owner-vs-media speaker identity from this block.\n"
        )
    except Exception:
        return ""
