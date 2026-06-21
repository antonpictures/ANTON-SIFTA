#!/usr/bin/env python3
"""
System/swarm_camera_hotplug_probe.py — Camera hot-plug ground-truth probe
═══════════════════════════════════════════════════════════════════════════
READ-ONLY. Mutates nothing. Run this on the Mac, in the SIFTA venv, to make
Alice's camera reality visible to both eyes (yours and the IDE Doctor's).

WHY THIS EXISTS
───────────────
Symptom (George, 2026-05-20): unplug the USB-hub camera and Alice keeps
trying the old device; plug it back and she does not pick it up without a
full restart. "It's not plug-and-play."

Diagnosis (Cowork, Probe lane, trace chains off 49105623…): macOS *is*
plug-and-play — the Qt widget `sifta_what_alice_sees_widget.py` already
listens to `QMediaDevices.videoInputsChanged` and re-ranks live devices.
The break is in the **cv2 capture path** (`swarm_physical_capture_daemon.py`
hardcodes `cv2.VideoCapture(0)`, `optical_ingress.py` hardcodes index 1),
and in `swarm_camera_target.index_for_target()` whose live-device resolution
silently degrades to the **frozen `_INDEX_TO_NAME` integer map** whenever it
runs without a QApplication context (i.e. in the background cv2 threads).
cv2/AVFoundation indices *renumber* on hot-plug; the frozen map does not.
So the cv2 world locks a stale integer and never re-enumerates.

This probe prints, side by side:
  1. Live AVFoundation devices (uniqueID + name) — Qt-free, the macOS truth.
  2. Live QMediaDevices.videoInputs() — what the Qt widget sees.
  3. cv2 index probe — which integer indices actually open *right now*.
  4. The canonical target `.sifta_state/active_saccade_target.json`.
  5. The frozen `_INDEX_TO_NAME` map.
  6. A mismatch report: where the frozen index map disagrees with reality.

Run it once with everything plugged in, once after you unplug the USB
camera, once after you plug it back. The three snapshots prove exactly
where the index drifts.

USAGE
─────
    cd /Users/ioanganton/Music/ANTON_SIFTA
    python3 System/swarm_camera_hotplug_probe.py

Optional: append each run to a ledger for the swarm (still read-only on
organs; only writes its own probe ledger):
    python3 System/swarm_camera_hotplug_probe.py --ledger
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TARGET_JSON = _STATE / "active_saccade_target.json"
_TARGET_TXT = _STATE / "active_saccade_target.txt"
_PROBE_LEDGER = _STATE / "camera_hotplug_probe.jsonl"


def _hr(title: str) -> None:
    print("\n" + "═" * 72)
    print(f"  {title}")
    print("═" * 72)


def avfoundation_devices():
    """Qt-free macOS device list via PyObjC AVFoundation.
    Returns [(uniqueID, localizedName)] or None if unavailable.
    uniqueID is STABLE across hot-plug — this is the plug-and-play key."""
    try:
        import AVFoundation  # type: ignore
    except Exception as e:
        return None, f"AVFoundation import failed: {type(e).__name__}: {e}"
    try:
        media_video = AVFoundation.AVMediaTypeVideo
        devs = AVFoundation.AVCaptureDevice.devicesWithMediaType_(media_video)
        out = []
        for d in devs:
            out.append((str(d.uniqueID()), str(d.localizedName())))
        return out, None
    except Exception as e:
        return None, f"AVFoundation query failed: {type(e).__name__}: {e}"


def qmediadevices():
    """What the Qt widget sees. Needs PyQt6; a QGuiApplication is created if
    none exists so the call is safe to run standalone."""
    try:
        from PyQt6.QtMultimedia import QMediaDevices  # type: ignore
        from PyQt6.QtGui import QGuiApplication  # type: ignore
    except Exception as e:
        return None, f"PyQt6 import failed: {type(e).__name__}: {e}"
    try:
        app = QGuiApplication.instance()
        created = False
        if app is None:
            app = QGuiApplication(sys.argv[:1])
            created = True
        out = []
        for d in QMediaDevices.videoInputs():
            did = d.id()
            try:
                did = bytes(did).decode() if not isinstance(did, str) else did
            except Exception:
                did = did.decode() if isinstance(did, (bytes, bytearray)) else str(did)
            out.append((did, d.description()))
        # do not app.exec(); we only needed enumeration
        return out, None
    except Exception as e:
        return None, f"QMediaDevices query failed: {type(e).__name__}: {e}"


def cv2_index_probe(max_index: int = 8):
    """Which integer indices actually open right now. This is the number that
    renumbers on hot-plug."""
    try:
        import cv2  # type: ignore
    except Exception as e:
        return None, f"cv2 import failed: {type(e).__name__}: {e}"
    out = []
    for idx in range(max_index):
        cap = None
        try:
            cap = cv2.VideoCapture(idx)
            opened = bool(cap.isOpened())
            got_frame = False
            if opened:
                ok, _frame = cap.read()
                got_frame = bool(ok)
            out.append((idx, opened, got_frame))
        except Exception as e:
            out.append((idx, False, f"exception: {type(e).__name__}: {e}"))
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
    return out, None


def frozen_index_map():
    """Read _INDEX_TO_NAME without importing Qt (avoids side effects)."""
    try:
        sys.path.insert(0, str(_REPO))
        from System.swarm_camera_target import _INDEX_TO_NAME  # type: ignore
        return dict(_INDEX_TO_NAME), None
    except Exception as e:
        return None, f"could not import _INDEX_TO_NAME: {type(e).__name__}: {e}"


def read_target():
    if _TARGET_JSON.exists():
        try:
            return json.loads(_TARGET_JSON.read_text()), "json"
        except Exception as e:
            return {"_parse_error": str(e)}, "json(broken)"
    if _TARGET_TXT.exists():
        return {"_legacy_txt": _TARGET_TXT.read_text().strip()}, "txt"
    return None, "absent"


def main(write_ledger: bool = False) -> int:
    snapshot = {"ts": time.time(), "ts_human": time.strftime("%Y-%m-%d %H:%M:%S")}

    _hr("1. AVFoundation devices (macOS truth, Qt-free, uniqueID is stable)")
    av, av_err = avfoundation_devices()
    if av is None:
        print(f"  [unavailable] {av_err}")
        print("  → install with:  pip install pyobjc-framework-AVFoundation")
        snapshot["avfoundation_error"] = av_err
    else:
        for i, (uid, name) in enumerate(av):
            print(f"  av[{i}]  uniqueID={uid!r}")
            print(f"         name    ={name!r}")
        snapshot["avfoundation"] = [{"uid": u, "name": n} for u, n in av]

    _hr("2. QMediaDevices.videoInputs() (what the Qt 'What Alice Sees' widget sees)")
    qm, qm_err = qmediadevices()
    if qm is None:
        print(f"  [unavailable] {qm_err}")
        snapshot["qmediadevices_error"] = qm_err
    else:
        for i, (did, desc) in enumerate(qm):
            print(f"  qt[{i}]  id={did!r}")
            print(f"         desc={desc!r}")
        snapshot["qmediadevices"] = [{"id": d, "desc": x} for d, x in qm]

    _hr("3. cv2 index probe (THESE integers renumber on hot-plug)")
    cv, cv_err = cv2_index_probe()
    if cv is None:
        print(f"  [unavailable] {cv_err}")
        snapshot["cv2_error"] = cv_err
    else:
        for idx, opened, frame in cv:
            mark = "OPEN " if opened else "  -  "
            print(f"  cv2[{idx}]  {mark}  isOpened={opened}  read_frame={frame}")
        snapshot["cv2"] = [{"index": i, "opened": o, "frame": f} for i, o, f in cv]

    _hr("4. Canonical target  .sifta_state/active_saccade_target.json")
    tgt, src = read_target()
    print(f"  source: {src}")
    print(f"  {json.dumps(tgt, indent=2) if tgt else '(none)'}")
    snapshot["target"] = tgt
    snapshot["target_source"] = src

    _hr("5. Frozen _INDEX_TO_NAME (the stale map, captured 2026-04-23)")
    fmap, f_err = frozen_index_map()
    if fmap is None:
        print(f"  [unavailable] {f_err}")
    else:
        for idx, name in sorted(fmap.items()):
            print(f"  frozen[{idx}] = {name!r}")
        snapshot["frozen_index_map"] = {str(k): v for k, v in fmap.items()}

    _hr("6. MISMATCH REPORT — does the frozen index still point where it claims?")
    problems = []
    if av and fmap:
        # AVFoundation order is what cv2's AVFoundation backend follows on macOS.
        for idx, claimed_name in sorted(fmap.items()):
            if idx < len(av):
                live_name = av[idx][1]
                same = claimed_name.lower() in live_name.lower() or live_name.lower() in claimed_name.lower()
                flag = "OK  " if same else "DRIFT"
                if not same:
                    problems.append((idx, claimed_name, live_name))
                print(f"  [{flag}] index {idx}: frozen says {claimed_name!r}  |  live AVF says {live_name!r}")
            else:
                problems.append((idx, claimed_name, "(no live device at this index)"))
                print(f"  [DRIFT] index {idx}: frozen says {claimed_name!r}  |  live AVF has no device here")
    else:
        print("  (need both AVFoundation list and frozen map to compare — see sections above)")

    print()
    if problems:
        print(f"  ⚠  {len(problems)} index(es) DRIFTED. The cv2 capture path that resolves")
        print("     by integer index will open the WRONG or a DEAD device until it")
        print("     re-enumerates. This is the plug-and-play break. The fix is to")
        print("     resolve by AVFoundation uniqueID (stable) instead of integer index,")
        print("     and re-enumerate on read failure (§7.1 Sensory Lock-On).")
    else:
        print("  ✓  No index drift detected in this snapshot. If the bug reproduces,")
        print("     capture a snapshot RIGHT AFTER unplugging — that is when drift appears.")

    if write_ledger:
        snapshot["drift_count"] = len(problems)
        _STATE.mkdir(parents=True, exist_ok=True)
        with _PROBE_LEDGER.open("a") as f:
            f.write(json.dumps(snapshot, default=str) + "\n")
        print(f"\n  appended snapshot → {_PROBE_LEDGER}")
        try:
            from System.swarm_eye_registry import refresh_eye_registry

            devices = snapshot.get("avfoundation") or snapshot.get("qmediadevices") or []
            reg = refresh_eye_registry(devices=devices, now=snapshot["ts"], write_receipt=True)
            print(f"  refreshed eye registry → {len(reg.get('eyes', []))} eye row(s)")
        except Exception as exc:
            print(f"  eye registry refresh failed: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    write_ledger = "--ledger" in sys.argv
    raise SystemExit(main(write_ledger=write_ledger))


# r1027 two-eyes extension (extends this existing organ, no rival).
# Eye registry bound by stable uniqueID / VID:PID+name (Fresco adapter safe).
# Roles assigned: owner_eye = built-in; world_eye = first live USB/external (plug-and-play).
EYE_REGISTRY_PATH = _STATE / "eye_registry.json"

def build_and_write_eye_registry() -> dict:
    """Produce .sifta_state/eye_registry.json via the canonical plug-and-play registry."""
    from System.swarm_eye_registry import refresh_eye_registry

    reg = refresh_eye_registry(write_receipt=True)
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        EYE_REGISTRY_PATH.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
        print(f"[EYE_REGISTRY] wrote {EYE_REGISTRY_PATH}")
    except Exception as e:
        print(f"[EYE_REGISTRY] write error: {e}")
    return reg

# Auto on --ledger or direct import call for consumers (switch, blink).
if "--registry" in sys.argv or (len(sys.argv) > 1 and "registry" in sys.argv[1]):
    build_and_write_eye_registry()
