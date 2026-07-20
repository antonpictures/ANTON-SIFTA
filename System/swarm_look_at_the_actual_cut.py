#!/usr/bin/env python3
"""swarm_look_at_the_actual_cut.py — Alice's "look at the actual cut" reflex organ.

Lesson learned from a peer arm (Codex, GPT-5.5) on 2026-06-23 and taught in
tournament r1564: when asked "thoughts?" about a video/clip, DO NOT judge the
title. Go look at the real artifact, then judge from grounded evidence.

This organ delivers the grounded evidence + a receipt; the *judgement* stays the
cortex's job. It embodies §7.12 (probe before claim): speak only what you
actually looked at.

Pipeline:
  1. probe_media()    -> ffprobe metadata (duration, resolution, has_audio)
  2. extract_frames() -> ffmpeg, GLOB-QUIRK-PROOF (explicit %03d pattern +
                         pathlib listing; never a bare shell wildcard)
  3. contact_sheet()  -> PIL grid so the SEQUENCE is judged, not one frame
  4. transcribe()     -> local Whisper if present; graceful gap-receipt if not
  5. critique_evidence() -> orchestrates the above and returns a receipt dict
                            ("ready_for_cortex") with every path + any scar.

Degrades gracefully: missing ffmpeg/ffprobe/PIL/whisper become honest gaps in
the receipt, never a fake success. Never raises on a missing tool.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


def _run(cmd: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe_media(path: str | Path) -> Dict[str, Any]:
    """ffprobe metadata. Honest gap-receipt if ffprobe is missing or fails."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "reason": "file_not_found", "path": str(p)}
    if not _have("ffprobe"):
        return {"ok": False, "reason": "ffprobe_unavailable", "path": str(p)}
    try:
        cp = _run(["ffprobe", "-v", "error", "-print_format", "json",
                   "-show_format", "-show_streams", str(p)])
        if cp.returncode != 0:
            return {"ok": False, "reason": f"ffprobe_error: {cp.stderr.strip()[:200]}"}
        data = json.loads(cp.stdout or "{}")
    except Exception as exc:  # noqa: BLE001 - return the scar, never raise
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    streams = data.get("streams", []) or []
    vid = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    dur = data.get("format", {}).get("duration")
    try:
        dur = float(dur) if dur is not None else None
    except (TypeError, ValueError):
        dur = None
    return {
        "ok": True, "path": str(p), "duration_s": dur,
        "width": vid.get("width"), "height": vid.get("height"),
        "video_codec": vid.get("codec_name"), "has_audio": has_audio,
        "orientation": ("vertical" if (vid.get("height") or 0) > (vid.get("width") or 0)
                        else "horizontal"),
    }


def extract_frames(path: str | Path, out_dir: str | Path, n: int = 10) -> Dict[str, Any]:
    """Extract ~n evenly spaced frames. GLOB-QUIRK-PROOF: ffmpeg writes an
    explicit frame_%03d.jpg pattern, and we list results with pathlib.glob —
    never a bare shell wildcard (that was the exact quirk Codex hit and fixed).
    """
    p, out = Path(path), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not _have("ffmpeg"):
        return {"ok": False, "reason": "ffmpeg_unavailable", "frames": []}
    meta = probe_media(p)
    dur = meta.get("duration_s") or 0.0
    fps_expr = f"{n}/{dur:.3f}" if dur and dur > 0 else "1"
    pattern = str(out / "frame_%03d.jpg")
    try:
        cp = _run(["ffmpeg", "-y", "-i", str(p), "-vf", f"fps={fps_expr}",
                   "-frames:v", str(n), "-q:v", "3", pattern])
        if cp.returncode != 0:
            return {"ok": False, "reason": f"ffmpeg_error: {cp.stderr.strip()[-200:]}", "frames": []}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "frames": []}
    frames = sorted(str(f) for f in out.glob("frame_*.jpg"))  # pathlib, not shell glob
    return {"ok": bool(frames), "frames": frames, "count": len(frames),
            "reason": None if frames else "no_frames_written"}


def contact_sheet(frames: List[str], out_path: str | Path, cols: int = 5,
                  cell: int = 320) -> Dict[str, Any]:
    """PIL grid so composition + captions are judged as a SEQUENCE."""
    if not frames:
        return {"ok": False, "reason": "no_frames"}
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "pillow_unavailable"}
    try:
        imgs = [Image.open(f).convert("RGB") for f in frames]
        rows = (len(imgs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell, rows * cell), (17, 17, 17))
        for i, im in enumerate(imgs):
            im.thumbnail((cell, cell))
            x = (i % cols) * cell + (cell - im.width) // 2
            y = (i // cols) * cell + (cell - im.height) // 2
            sheet.paste(im, (x, y))
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out_path, "JPEG", quality=85)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "path": str(out_path), "tiles": len(frames),
            "cols": cols, "rows": rows}


def transcribe(path: str | Path) -> Dict[str, Any]:
    """Local Whisper if present; honest graceful gap otherwise (never fake text)."""
    try:
        import whisper  # type: ignore
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "whisper_unavailable", "graceful": True, "text": None}
    try:
        model = whisper.load_model("base")
        result = model.transcribe(str(path))
        return {"ok": True, "text": (result.get("text") or "").strip()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "graceful": True, "text": None}


def critique_evidence(path: str | Path, work_dir: str | Path | None = None,
                      n_frames: int = 10) -> Dict[str, Any]:
    """Orchestrate the reflex and return a grounded-evidence RECEIPT.

    The organ does NOT judge — it hands the cortex real evidence so the cortex
    can judge like a producer/editor and cite frames + transcript. Judgement
    without this evidence is a §7.12 violation (claiming from the title).
    """
    p = Path(path)
    work = Path(work_dir) if work_dir else (p.parent / f".cut_evidence_{p.stem}")
    work.mkdir(parents=True, exist_ok=True)
    meta = probe_media(p)
    fr = extract_frames(p, work / "frames", n=n_frames) if meta.get("ok") else {"ok": False, "reason": meta.get("reason"), "frames": []}
    sheet = contact_sheet(fr.get("frames", []), work / "contact_sheet.jpg") if fr.get("ok") else {"ok": False, "reason": fr.get("reason")}
    tx = transcribe(p) if meta.get("ok") and meta.get("has_audio") else {"ok": False, "reason": "no_audio_or_probe", "graceful": True, "text": None}
    scars = [s for s in [
        None if meta.get("ok") else f"probe:{meta.get('reason')}",
        None if fr.get("ok") else f"frames:{fr.get('reason')}",
        None if sheet.get("ok") else f"contact_sheet:{sheet.get('reason')}",
        None if tx.get("ok") else f"transcript:{tx.get('reason')}",
    ] if s]
    return {
        "truth_label": "LOOK_AT_THE_ACTUAL_CUT_V1",
        "ts": time.time(),
        "source": str(p),
        "metadata": meta,
        "frames": fr,
        "contact_sheet": sheet,
        "transcript": tx,
        "scars": scars,
        # the cortex must judge from THIS, not from the title:
        "ready_for_cortex": bool(meta.get("ok") and fr.get("ok") and sheet.get("ok")),
        "instruction": ("Judge the clip from the contact sheet (sequence) + transcript like a "
                        "producer/editor. Cite specific frames and the spoken line. Do not opine "
                        "from the title. If ready_for_cortex is False, say which evidence is missing."),
    }


if __name__ == "__main__":
    # Self-test: build a tiny clip with ffmpeg, run the full pipeline, assert.
    import tempfile, sys
    ok = True
    if not (_have("ffmpeg") and _have("ffprobe")):
        print("SKIP: ffmpeg/ffprobe not present in this environment")
        raise SystemExit(0)
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "test_clip.mp4"
        gen = _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=30:duration=3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-shortest", "-pix_fmt", "yuv420p", str(clip)])
        assert clip.exists(), f"clip not generated: {gen.stderr[-300:]}"
        ev = critique_evidence(clip, work_dir=Path(td) / "ev", n_frames=10)
        m = ev["metadata"]
        checks = {
            "probe_ok": m.get("ok") is True,
            "duration~3": (m.get("duration_s") or 0) >= 2.5,
            "has_audio": m.get("has_audio") is True,
            "vertical": m.get("orientation") == "vertical",
            "frames>=8": ev["frames"].get("count", 0) >= 8,
            "frames_glob_proof": all("frame_" in f for f in ev["frames"].get("frames", [])),
            "contact_sheet_ok": ev["contact_sheet"].get("ok") is True,
            "contact_sheet_exists": Path(ev["contact_sheet"].get("path", "x")).exists(),
            "transcript_graceful_if_no_whisper": (ev["transcript"].get("ok") is True
                                                  or ev["transcript"].get("graceful") is True),
            "ready_for_cortex": ev["ready_for_cortex"] is True,
        }
        for k, v in checks.items():
            print(f"{'OK ' if v else 'FAIL'} {k}")
            ok = ok and v
        print("RECEIPT:", json.dumps({k: ev[k] for k in ("truth_label", "scars", "ready_for_cortex")}))
    print("SELF-TEST:", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
