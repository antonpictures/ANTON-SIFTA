#!/usr/bin/env python3
"""
System/swarm_olfactory_cortex.py — Epoch 5 The Olfactory Cortex (Chemoreception)
═════════════════════════════════════════════════════════════════════════════════
Concept: Pattern-match the food vacuoles produced by the Pseudopod and tell
         Alice WHAT she just tasted on the LAN — not just THAT she tasted.

Author:  C47H ∥ AG47 (Claude Opus 4.7 High, Cursor IDE, node ANTON_SIFTA)
Status:  Active sensory lobe, Epoch 5
Trust:   Architect's tournament mandate 2026-04-20 — for the swarm.

Biological metaphor
-------------------
AG31's `swarm_pseudopod_phagocytosis.py` and C47H's hardened
`swarm_pseudopod.py` both extend a chemical feeler to a LAN target IP and
bring back ≤1024 bytes of HTTP/banner response into a Food Vacuole
(`.sifta_state/phagocytosis_vacuoles.jsonl`). That gives Alice TASTE.

This module is her OLFACTORY CORTEX: it inspects each vacuole, runs the
ingested bytes against a curated signature library, and emits a structured
classification — "ASUS RT-AX88U router", "OpenSSH 9.6 server", "Plex Media
Server", "Sonos speaker", "Cursor IDE telemetry endpoint", and so on. The
classifications land in a per-event ledger AND a rolling state cache so
Alice's prompt-builder can show one line: "Olfactory: 7 scents | router=1
iot=3 server=2 unknown=1".

This is pattern recognition, NOT execution. The vacuole is read; signatures
are matched against it; the result is logged. No remote calls. No code from
the vacuole is ever evaluated.

Architecture
------------
1. **Signature library** — list of (regex, category, identity_template, weight)
   tuples. Higher weight wins on tie. Specific signatures (model numbers)
   outrank generic ones.
2. **classify_vacuole(vacuole) → dict** — pure function. Input: a vacuole
   row dict. Output: classification dict (vacuole_trace_id, target_ip,
   scent_category, scent_identity, matched_signatures, confidence,
   byte_length).
3. **digest_recent(n=20) → list** — read the last N vacuoles, classify
   each, append non-duplicate classifications to the ledger, refresh state.
4. **State cache** — `.sifta_state/olfactory_state.json`, refreshed on
   every digest, also exposed as a one-line summary for Alice's prompt.
5. **CLI**: `summary`, `digest`, `recent N`, `signatures`, `classify_text "raw bytes"`.

Hardening notes
---------------
* Repo-anchored state dir; safe to call from any cwd.
* Silently survives a missing vacuole ledger (never crashes on cold boot).
* Idempotent ledger writes — each classification is keyed on
  `vacuole_trace_id`. A second `digest` over the same vacuoles will not
  duplicate rows.
* All regex patterns compiled once at module import.
* Confidence is a calibrated sum of matched weights, capped at 1.0.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_VACUOLES   = _STATE_DIR / "phagocytosis_vacuoles.jsonl"
_LEDGER     = _STATE_DIR / "olfactory_classifications.jsonl"
_STATE_FILE = _STATE_DIR / "olfactory_state.json"

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    import sys
    sys.path.insert(0, str(_REPO))
    from System.jsonl_file_lock import append_line_locked

# ──────────────────────────────────────────────────────────────────────────
# Signature library.
# ──────────────────────────────────────────────────────────────────────────
# Each entry: (compiled_regex, category, identity_template, weight)
#   - regex          : case-insensitive pattern. May use named groups for
#                      model numbers (e.g. `(?P<model>RT-AX\d+\w*)`).
#   - category       : coarse bucket Alice's prompt aggregates by.
#   - identity_template : python str.format() template that may reference
#                      regex named groups. Falls back to the literal string
#                      when no named groups matched.
#   - weight         : 0.0 to 1.0 — how confident a single match makes us.
#                      Generic signatures: 0.30-0.50. Specific model
#                      identifiers: 0.70-0.95.

@dataclass(frozen=True)
class _Sig:
    pattern: re.Pattern
    category: str
    identity: str
    weight: float


def _S(rx: str, cat: str, ident: str, w: float) -> _Sig:
    return _Sig(re.compile(rx, re.IGNORECASE | re.DOTALL), cat, ident, w)


# Curated signature catalog. Ordered roughly by weight so the highest-weight
# match wins ties on the same byte stream.
_SIGNATURES: Tuple[_Sig, ...] = (
    # ── Routers / networking gear (most specific first) ─────────────────
    # ASUS: any of 'asus', 'asuswrt', 'asus router', 'asus wireless router'
    # followed eventually by a model token like RT-AX88U, GT-AX6000, ZenWiFi-XT8.
    # The `.{0,40}?` (non-greedy, ≤40 chars) lets words sit between 'asus'
    # and the model number while preventing runaway matches.
    _S(r"asus(?:wrt)?\b.{0,40}?\b(?P<model>(?:rt|gt|zen|tuf|rog)-[a-z0-9]+)", "router", "ASUS {model}", 0.92),
    _S(r"\basus(?:wrt|\s+wireless\s+router|\s+router)\b", "router", "ASUS router", 0.78),
    _S(r"netgear[^a-z0-9]*(?P<model>(?:nighthawk|orbi|rax|rbr|cax|cbr)[a-z0-9-]*)", "router", "Netgear {model}", 0.92),
    _S(r"tp[-_ ]?link[^a-z0-9]*(?P<model>(?:archer|deco|omada|tl-[a-z0-9]+)[a-z0-9-]*)", "router", "TP-Link {model}", 0.92),
    _S(r"linksys[^a-z0-9]*(?P<model>(?:velop|smart|lcap|ea|wrt)[a-z0-9-]*)", "router", "Linksys {model}", 0.90),
    _S(r"unifi(?:[^a-z0-9]+(?P<model>[a-z0-9-]+))?", "router", "Ubiquiti UniFi {model}", 0.90),
    _S(r"edgeos|edgerouter", "router", "Ubiquiti EdgeRouter", 0.88),
    _S(r"amplifi", "router", "Ubiquiti AmpliFi", 0.85),
    _S(r"\beero\b", "router", "Eero mesh node", 0.85),
    _S(r"mikrotik|routeros", "router", "MikroTik RouterOS", 0.88),
    _S(r"d-link[^a-z0-9]*(?P<model>dir-[a-z0-9]+)?", "router", "D-Link {model}", 0.85),
    _S(r"airport (?:base station|extreme|express)", "router", "Apple AirPort", 0.88),
    _S(r"google (?:nest )?wifi", "router", "Google Nest WiFi", 0.88),
    _S(r"verizon|fios|quantum gateway", "router", "Verizon FiOS gateway", 0.80),
    _S(r"\bxfi\b|xfinity gateway", "router", "Comcast Xfinity gateway", 0.80),
    _S(r"plume\s+(?:adaptive|wifi)", "router", "Plume mesh", 0.85),
    _S(r"<title>[^<]*router[^<]*</title>", "router", "Generic router admin page", 0.55),

    # ── SSH banners (RFC 4253 says first line is the version string) ────
    _S(r"SSH-2\.0-OpenSSH[_ ](?P<ver>[\w.]+)", "ssh", "OpenSSH {ver}", 0.95),
    _S(r"SSH-2\.0-(?P<impl>[\w.-]+)", "ssh", "SSH server ({impl})", 0.85),

    # ── HTTP server fingerprints ────────────────────────────────────────
    _S(r"server:\s*nginx(?:/(?P<ver>[\w.]+))?", "http_server", "nginx {ver}", 0.85),
    _S(r"server:\s*apache(?:/(?P<ver>[\w.]+))?", "http_server", "Apache {ver}", 0.85),
    _S(r"server:\s*microsoft-iis(?:/(?P<ver>[\w.]+))?", "http_server", "Microsoft IIS {ver}", 0.85),
    _S(r"server:\s*caddy", "http_server", "Caddy", 0.85),
    _S(r"server:\s*lighttpd(?:/(?P<ver>[\w.]+))?", "http_server", "Lighttpd {ver}", 0.85),
    _S(r"server:\s*werkzeug", "http_server", "Python Werkzeug (Flask dev)", 0.85),
    _S(r"server:\s*uvicorn", "http_server", "Python Uvicorn (ASGI)", 0.85),
    _S(r"server:\s*gunicorn", "http_server", "Python Gunicorn (WSGI)", 0.85),
    _S(r"server:\s*tornado", "http_server", "Python Tornado", 0.80),
    _S(r"server:\s*python(?:/[\w.]+)?\s+simplehttp", "http_server", "Python SimpleHTTPServer", 0.80),

    # ── AI brain (her own brain, sibling intel) ─────────────────────────
    _S(r"\bollama\b", "ai_brain", "Ollama (Alice's local brain)", 0.95),
    # Ollama's /api/tags response shape. The body itself doesn't say
    # "ollama" but the JSON shape `{"models":[{"name":"<model>:<tag>",...}]}`
    # is canonical — every Ollama instance returns it.
    _S(r'"models"\s*:\s*\[\s*\{\s*"name"\s*:\s*"[\w.-]+:[\w.-]+"', "ai_brain", "Ollama API (tag list)", 0.93),
    _S(r"\blm[- ]?studio\b|/v1/(?:chat/)?completions", "ai_brain", "OpenAI-compatible LLM endpoint", 0.75),

    # ── NAS / media servers ─────────────────────────────────────────────
    _S(r"plex media server|x-plex", "nas", "Plex Media Server", 0.92),
    _S(r"synology|\bdsm\b/(?P<ver>[\w.]+)", "nas", "Synology DSM {ver}", 0.92),
    _S(r"\bqnap\b|\bqts\b/(?P<ver>[\w.]+)", "nas", "QNAP QTS {ver}", 0.92),
    _S(r"unraid|\blibvirt\b", "nas", "Generic NAS", 0.60),
    _S(r"jellyfin", "nas", "Jellyfin Media Server", 0.88),

    # ── IoT / smart home ────────────────────────────────────────────────
    _S(r"sonos", "iot", "Sonos speaker", 0.92),
    _S(r"chromecast|cast device", "iot", "Chromecast / Google Cast", 0.90),
    _S(r"airplay|_airplay\._tcp|apple tv", "iot", "Apple TV / AirPlay device", 0.88),
    _S(r"homepod", "iot", "Apple HomePod", 0.92),
    _S(r"philips hue|hue bridge", "iot", "Philips Hue Bridge", 0.92),
    _S(r"nest (?:cam|hub|protect|thermostat)|google home", "iot", "Google Nest device", 0.88),
    _S(r"ring (?:doorbell|camera|chime)", "iot", "Ring device", 0.88),
    _S(r"\broku\b", "iot", "Roku", 0.85),
    _S(r"samsung smart ?tv|tizen", "iot", "Samsung Smart TV", 0.85),
    _S(r"webos|lg smart ?tv", "iot", "LG WebOS TV", 0.85),
    _S(r"home assistant|homeassistant", "iot", "Home Assistant hub", 0.92),

    # ── Cameras (often unencrypted ONVIF/RTSP HTTP banners) ─────────────
    _S(r"hikvision|webserver-hikvision", "camera", "Hikvision camera", 0.90),
    _S(r"\bdahua\b", "camera", "Dahua camera", 0.90),
    _S(r"\bwyze\b", "camera", "Wyze camera", 0.85),
    _S(r"\breolink\b", "camera", "Reolink camera", 0.85),
    _S(r"axis communications|axis-acc", "camera", "Axis camera", 0.88),

    # ── Printers ────────────────────────────────────────────────────────
    _S(r"hp (?:laserjet|officejet|envy|deskjet)\s+(?P<model>[\w-]+)?", "printer", "HP {model}", 0.92),
    _S(r"brother (?:hl|mfc|dcp)-(?P<model>[\w-]+)?", "printer", "Brother {model}", 0.92),
    _S(r"epson (?:workforce|expression|ecotank)", "printer", "Epson printer", 0.88),
    _S(r"\bcanon\b\s+(?P<model>(?:pixma|imageclass|maxify)[\w-]*)?", "printer", "Canon {model}", 0.88),

    # ── Apple device general ────────────────────────────────────────────
    _S(r"applewebkit", "apple_device", "Apple device (WebKit)", 0.40),
    _S(r"_homekit\._tcp|homekit accessory", "iot", "HomeKit accessory", 0.85),

    # ── Generic landing pages / weak signals ────────────────────────────
    _S(r"<html|<!doctype html", "generic_http", "Generic HTTP server", 0.30),
    _S(r"^http/1\.[01] \d{3}", "generic_http", "Bare HTTP response", 0.25),
    _S(r"\b403 forbidden\b|\b401 unauthorized\b", "generic_http", "Auth-protected HTTP endpoint", 0.45),
    _S(r"\bnot found\b|\b404\b", "generic_http", "HTTP server (404 on root)", 0.40),

    # ── Cell membrane rejections (the pseudopod itself failed) ──────────
    _S(r"\[CELL MEMBRANE REJECTED\]", "rejection", "Connection refused / unreachable", 0.95),
    _S(r"\[DIGESTION ERROR\]", "rejection", "Pseudopod digestion failure", 0.90),
    _S(r"\[UNKNOWN PROTOCOL\]", "rejection", "Unsupported protocol", 0.90),
)


# ──────────────────────────────────────────────────────────────────────────
# Pure classifier.
# ──────────────────────────────────────────────────────────────────────────

def classify_text(blob: str) -> Dict[str, Any]:
    """
    Pure-function classifier. Inspect a raw text blob (the ingested_data
    field of a vacuole) and return a structured scent dict:

        {
          "scent_category":     "router" | "iot" | "ssh" | ... | "unknown",
          "scent_identity":     human-readable identity string,
          "matched_signatures": [pattern_str, ...],
          "confidence":         float 0.0..1.0,
        }

    The picked identity is always the SINGLE highest-weight match (most
    specific signature wins). Confidence aggregates ALL matches:
    cumulative weight capped at 1.0. So a vacuole that hits both
    "asus rt-ax88u" (0.92) AND a generic "<html>" (0.30) reports the
    ASUS identity at confidence min(0.92+0.30, 1.0) = 1.0.
    """
    if not isinstance(blob, str) or not blob.strip():
        return {
            "scent_category": "unknown",
            "scent_identity": "empty vacuole",
            "matched_signatures": [],
            "confidence": 0.0,
        }

    matches: List[Tuple[_Sig, re.Match]] = []
    for sig in _SIGNATURES:
        m = sig.pattern.search(blob)
        if m:
            matches.append((sig, m))

    if not matches:
        return {
            "scent_category": "unknown",
            "scent_identity": "unrecognized chemical signature",
            "matched_signatures": [],
            "confidence": 0.0,
        }

    # Highest-weight match wins identity assignment.
    matches.sort(key=lambda pm: pm[0].weight, reverse=True)
    winner_sig, winner_match = matches[0]

    # Render identity template. Falls back to the literal string if any
    # named group is missing or empty.
    try:
        groups = {k: (v if v else "") for k, v in winner_match.groupdict().items()}
        identity = winner_sig.identity.format(**groups).strip()
        # Collapse double spaces from missing optional groups.
        identity = re.sub(r"\s+", " ", identity).strip()
        if not identity or identity.endswith(" "):
            identity = winner_sig.identity
    except (KeyError, IndexError):
        identity = winner_sig.identity

    confidence = min(sum(s.weight for s, _ in matches), 1.0)

    return {
        "scent_category": winner_sig.category,
        "scent_identity": identity,
        "matched_signatures": [s.pattern.pattern for s, _ in matches[:5]],  # cap at 5 for ledger sanity
        "confidence": round(confidence, 3),
    }


def classify_vacuole(vacuole: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify ONE vacuole row (the dict you'd json.loads() out of
    phagocytosis_vacuoles.jsonl) and produce a complete classification
    dict ready to be appended to the olfactory ledger.
    """
    blob = vacuole.get("ingested_data") or ""
    scent = classify_text(blob)
    return {
        "ts": time.time(),
        "vacuole_trace_id": vacuole.get("trace_id", ""),
        "target_ip": vacuole.get("target_ip", ""),
        "vacuole_ts": vacuole.get("ts", 0.0),
        "scent_category": scent["scent_category"],
        "scent_identity": scent["scent_identity"],
        "matched_signatures": scent["matched_signatures"],
        "confidence": scent["confidence"],
        "byte_length": len(blob) if isinstance(blob, str) else 0,
    }


# ──────────────────────────────────────────────────────────────────────────
# Ledger / state persistence.
# ──────────────────────────────────────────────────────────────────────────

def _read_existing_trace_ids(ledger_path: Path) -> set[str]:
    """Return the set of vacuole_trace_ids already classified, so digest is idempotent."""
    seen: set[str] = set()
    if not ledger_path.exists():
        return seen
    try:
        with ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    tid = row.get("vacuole_trace_id")
                    if tid:
                        seen.add(tid)
                except Exception:
                    continue
    except Exception:
        pass
    return seen


def _read_recent_vacuoles(n: int, vacuoles_path: Path) -> List[Dict[str, Any]]:
    if not vacuoles_path.exists():
        return []
    try:
        with vacuoles_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def digest_recent(n: int = 20,
                  vacuoles_path: Optional[Path] = None,
                  ledger_path: Optional[Path] = None,
                  state_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Read the last `n` vacuoles, classify each that hasn't been classified
    yet, append the new classifications to the olfactory ledger, refresh
    the state cache, and return the list of NEW classifications produced.
    """
    vp = vacuoles_path or _VACUOLES
    lp = ledger_path or _LEDGER
    sp = state_path or _STATE_FILE

    seen = _read_existing_trace_ids(lp)
    vacs = _read_recent_vacuoles(n, vp)

    new_rows: List[Dict[str, Any]] = []
    for v in vacs:
        tid = v.get("trace_id")
        if not tid or tid in seen:
            continue
        row = classify_vacuole(v)
        try:
            append_line_locked(lp, json.dumps(row) + "\n")
            new_rows.append(row)
            seen.add(tid)
        except Exception:
            pass

    # Refresh state regardless of whether new rows landed; the aggregate
    # counts may need to reflect ledger truth even after manual edits.
    _refresh_state(lp, sp)
    return new_rows


def _refresh_state(ledger_path: Path, state_path: Path) -> Dict[str, Any]:
    """Re-aggregate the entire ledger into the state cache."""
    by_category: Dict[str, int] = {}
    known_devices: Dict[str, Dict[str, Any]] = {}
    total = 0

    if ledger_path.exists():
        try:
            with ledger_path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    cat = row.get("scent_category", "unknown")
                    by_category[cat] = by_category.get(cat, 0) + 1
                    total += 1
                    ip = row.get("target_ip")
                    if ip:
                        # Last-tasted wins (newer rows overwrite older).
                        known_devices[ip] = {
                            "ip": ip,
                            "identity": row.get("scent_identity", "unknown"),
                            "category": cat,
                            "last_tasted": row.get("ts", 0.0),
                            "confidence": row.get("confidence", 0.0),
                        }
        except Exception:
            pass

    state = {
        "ts": time.time(),
        "total_classified": total,
        "by_category": by_category,
        "known_devices": sorted(known_devices.values(),
                                key=lambda d: d.get("last_tasted", 0.0),
                                reverse=True),
        "unknown_count": by_category.get("unknown", 0) + by_category.get("rejection", 0),
    }

    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass
    return state


def get_olfactory_state(refresh: bool = False) -> Dict[str, Any]:
    """Read the cached state, optionally re-aggregating from the ledger first."""
    if refresh or not _STATE_FILE.exists():
        return _refresh_state(_LEDGER, _STATE_FILE)
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _refresh_state(_LEDGER, _STATE_FILE)


def get_olfactory_summary() -> str:
    """
    One-line summary block suitable for inclusion in Alice's prompt-builder.
    Empty string when she's never tasted anything (so the prompt-builder
    quietly omits the line).
    """
    state = get_olfactory_state(refresh=False)
    total = state.get("total_classified", 0)
    if total == 0:
        return ""

    by_cat = state.get("by_category", {})
    # Order categories by count desc, drop unknown to the end.
    ordered = sorted(
        ((c, n) for c, n in by_cat.items() if c not in ("unknown", "rejection")),
        key=lambda cn: -cn[1],
    )
    cat_str = " ".join(f"{c}={n}" for c, n in ordered) or "(no recognized scents)"
    unk = state.get("unknown_count", 0)
    if unk:
        cat_str += f" unknown={unk}"

    # Surface the most recently tasted *named* device for textural color.
    devices = state.get("known_devices", [])
    last_named: Optional[Dict[str, Any]] = None
    for d in devices:
        if d.get("category") not in ("unknown", "rejection"):
            last_named = d
            break

    base = f"Olfactory: {total} scent{'s' if total != 1 else ''} classified | {cat_str}"
    if last_named:
        base += f" | last={last_named['identity']}@{last_named['ip']}"
    return base


# ──────────────────────────────────────────────────────────────────────────
# CLI.
# ──────────────────────────────────────────────────────────────────────────

def _cli() -> int:
    parser = argparse.ArgumentParser(
        prog="swarm_olfactory_cortex",
        description="Pattern-match Pseudopod food vacuoles into LAN device identities.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("summary", help="Print the one-line olfactory summary for Alice's prompt.")
    sub.add_parser("signatures", help="List all known scent signatures.")

    digest_p = sub.add_parser("digest", help="Process recent vacuoles into classifications.")
    digest_p.add_argument("-n", type=int, default=20, help="Number of recent vacuoles to consider (default 20).")

    recent_p = sub.add_parser("recent", help="Show the last N classifications.")
    recent_p.add_argument("n", type=int, nargs="?", default=10)

    classify_p = sub.add_parser("classify_text", help="Classify a literal text blob (debugging).")
    classify_p.add_argument("blob")

    args = parser.parse_args()

    if args.cmd == "summary":
        s = get_olfactory_summary()
        print(s if s else "Olfactory: cortex idle (no vacuoles classified yet).")
        return 0

    if args.cmd == "signatures":
        print(f"Olfactory signatures registered: {len(_SIGNATURES)}")
        by_cat: Dict[str, int] = {}
        for s in _SIGNATURES:
            by_cat[s.category] = by_cat.get(s.category, 0) + 1
        for cat, n in sorted(by_cat.items(), key=lambda kn: -kn[1]):
            print(f"  {cat:>14s}  {n:>3d} signatures")
        return 0

    if args.cmd == "digest":
        new_rows = digest_recent(n=args.n)
        print(f"[OLFACTORY] Digested {len(new_rows)} new classification(s) from last {args.n} vacuoles.")
        for r in new_rows:
            print(f"  {r['target_ip']:<18s} {r['scent_category']:<14s} {r['scent_identity']:<40s} "
                  f"conf={r['confidence']:.2f} bytes={r['byte_length']}")
        print()
        print(get_olfactory_summary() or "(state empty)")
        return 0

    if args.cmd == "recent":
        if not _LEDGER.exists():
            print("(no classifications yet)")
            return 0
        try:
            with _LEDGER.open("r", encoding="utf-8") as f:
                lines = f.readlines()[-args.n:]
        except Exception as e:
            print(f"[!] read failure: {e}")
            return 1
        for line in lines:
            try:
                r = json.loads(line)
                print(f"{time.strftime('%H:%M:%S', time.localtime(r.get('ts', 0)))}  "
                      f"{r.get('target_ip', ''):<18s} {r.get('scent_category', ''):<14s} "
                      f"{r.get('scent_identity', ''):<40s} conf={r.get('confidence', 0):.2f}")
            except Exception:
                continue
        return 0

    if args.cmd == "classify_text":
        scent = classify_text(args.blob)
        print(json.dumps(scent, indent=2))
        return 0

    return 1


# ──────────────────────────────────────────────────────────────────────────
# In-module smoke test (runs when invoked as a module without subcommand).
# ──────────────────────────────────────────────────────────────────────────

def _smoke() -> int:
    print("\n=== SWARM OLFACTORY CORTEX : SMOKE TEST ===")

    # 1. Pure classifier — ten canonical scents.
    fixtures = [
        ("ASUS RT-AX88U admin",  "<html><title>ASUS Wireless Router RT-AX88U</title></html>",       "router",    "ASUS"),
        ("OpenSSH 9.6 banner",    "SSH-2.0-OpenSSH_9.6 Ubuntu-3ubuntu13.5\r\n",                       "ssh",       "OpenSSH 9.6"),
        ("nginx 1.24",            "HTTP/1.1 200 OK\r\nServer: nginx/1.24.0 (Ubuntu)\r\n\r\n",         "http_server", "nginx 1.24.0"),
        ("Apache 2.4",            "HTTP/1.1 200 OK\r\nServer: Apache/2.4.58 (Unix)\r\n\r\n",          "http_server", "Apache 2.4.58"),
        ("Sonos speaker",         "HTTP/1.1 200 OK\r\nServer: Linux UPnP/1.0 Sonos/76.1\r\n",         "iot",       "Sonos"),
        ("Plex",                  "HTTP/1.1 200 OK\r\nX-Plex-Protocol: 1.0\r\nContent-Type: text/xml", "nas",       "Plex"),
        ("Synology",              "<title>DSM Login - Synology</title>",                              "nas",       "Synology"),
        ("Ollama",                '{"models":[{"name":"gemma4:latest"}]}',                            "ai_brain",  "Ollama"),
        ("Hue Bridge",            "<title>Philips hue Bridge 2.0</title>",                            "iot",       "Philips Hue"),
        ("Pseudopod rejection",   "[CELL MEMBRANE REJECTED]: [Errno 61] Connection refused",         "rejection", "Connection refused"),
    ]

    failures = 0
    for label, blob, want_cat, want_id_substr in fixtures:
        scent = classify_text(blob)
        ok_cat = scent["scent_category"] == want_cat
        ok_id  = want_id_substr.lower() in scent["scent_identity"].lower()
        status = "PASS" if (ok_cat and ok_id) else "FAIL"
        if not (ok_cat and ok_id):
            failures += 1
        print(f"  [{status}] {label:<28s} → cat={scent['scent_category']:<13s} "
              f"id={scent['scent_identity']:<35s} conf={scent['confidence']:.2f}")
    print()

    # 2. Vacuole-level classification (input as a full vacuole dict).
    vac = {
        "ts": time.time() - 5,
        "target_ip": "192.168.1.1",
        "protocol": "http",
        "ingested_data": "<html><title>ASUS Wireless Router RT-AX88U</title></html>",
        "trace_id": "VACUOLE_smoketest",
    }
    row = classify_vacuole(vac)
    assert row["target_ip"] == "192.168.1.1"
    assert row["scent_category"] == "router"
    assert "ASUS" in row["scent_identity"]
    print(f"  [PASS] Full vacuole → row: {row['target_ip']} {row['scent_category']} "
          f"{row['scent_identity']} conf={row['confidence']:.2f}")

    # 3. Idempotent digest — write a fixture vacuole, digest twice, verify
    # only one classification lands.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        vac_path = tdp / "phagocytosis_vacuoles.jsonl"
        led_path = tdp / "olfactory_classifications.jsonl"
        st_path  = tdp / "olfactory_state.json"

        vac_path.write_text(json.dumps(vac) + "\n", encoding="utf-8")

        new1 = digest_recent(n=10, vacuoles_path=vac_path, ledger_path=led_path, state_path=st_path)
        new2 = digest_recent(n=10, vacuoles_path=vac_path, ledger_path=led_path, state_path=st_path)
        assert len(new1) == 1, f"first digest should classify 1, got {len(new1)}"
        assert len(new2) == 0, f"second digest should be idempotent, got {len(new2)}"
        print(f"  [PASS] Idempotent digest: first={len(new1)}, second={len(new2)}")

        # State cache reflects the one classification.
        st = json.loads(st_path.read_text())
        assert st["total_classified"] == 1
        assert st["by_category"].get("router") == 1
        assert any(d["ip"] == "192.168.1.1" for d in st["known_devices"])
        print(f"  [PASS] State cache aggregates: total={st['total_classified']}, by_cat={st['by_category']}")

    print()
    if failures:
        print(f"=== {failures} FIXTURE FAILURE(S). Olfactory cortex NOT green. ===")
        return 1
    print(f"=== OLFACTORY CORTEX GREEN. {len(_SIGNATURES)} signatures, all 10 fixtures classified. ===")
    return 0


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1:
        _sys.exit(_cli())
    _sys.exit(_smoke())
