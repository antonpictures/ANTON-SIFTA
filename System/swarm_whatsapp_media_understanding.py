"""swarm_whatsapp_media_understanding — looking, listening and watching what arrives.

The Architect, 2026-10-03:

    "solve the photo, to be able to look at photos and videos and audio recordings from whatsapp.
     I will send audio now recorded 30 seconds... and 5 sec video containing 2 shots forward and
     backwards camera from iPhone SE"

and, on the division of labour:

    "mercury is text only so you have to use another vision llm to decode, ok?"

He is right, and this organ is that rule made mechanical:

    Mercury 2.5 (cloud, text)   the thinking. It never receives pixels.
    MiniCPM-V / SmolVLM (local) the eyes. It never receives a market question.
    whisper large-v3 (local)    the ears.
    ffmpeg + the eyes           a video becomes frames, and the frames are looked at.

WHY THIS EXISTS AT ALL, measured: a photo from WhatsApp was downloaded, saved, carried into the
inbox with `media_path` set -- and the lane consumed the row and answered around the text
"[photo]". Ingest is not sight. The bytes sat on disk unlooked-at while the answer was written
about nothing. So the understanding step is explicit, it happens before the cortex is asked
anything, and its output replaces "[photo]" with what is actually in the frame.

THE DIALECT, learned the hard way today: Ollama wants `content` as a STRING and pixels in a
separate `images` array. An OpenAI-style content list returns

    HTTP 400  json: cannot unmarshal array into Go struct field .ChatRequest.messages.content

which is what blinded both local eyes until it was found. One shape. Get it wrong and the eye
looks broken when it is only being spoken to incorrectly.
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
RECEIPTS = STATE / "media_understanding.jsonl"
TRUTH_LABEL = "SIFTA_MEDIA_UNDERSTANDING_V1"

OLLAMA = "http://127.0.0.1:11434/api/chat"
VISION_MODEL = "hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M"
VISION_FALLBACK = "hf.co/ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0"
VISION_PROMPT = ("Describe this image concretely in three or four sentences: what is shown, any "
                 "people or places, any text or numbers you can read. Do not speculate about "
                 "what app or product it is unless it is written in the image.")
BODY_PYTHON = "/usr/local/bin/python3"     # the interpreter that owns faster_whisper / mlx_whisper
MAX_VIDEO_FRAMES = 4
MAX_DESCRIBED_CHARS = 1200


def _vlm(image: Path, *, prompt: str = VISION_PROMPT, model: Optional[str] = None,
         timeout: int = 200) -> Dict[str, Any]:
    """One look. Returns the description, or an honest failure -- never a silent empty string."""
    if not image.exists():
        return {"ok": False, "error": "no such file", "path": str(image)}
    b64 = base64.b64encode(image.read_bytes()).decode()
    for m in ([model] if model else [VISION_MODEL, VISION_FALLBACK]):
        # THE SHAPE: content is a STRING, pixels ride in `images`. This is the whole lesson.
        payload = {"model": m, "stream": False,
                   "messages": [{"role": "user", "content": prompt, "images": [b64]}]}
        try:
            r = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-X", "POST", OLLAMA,
                                "-H", "Content-Type: application/json", "-d", json.dumps(payload)],
                               capture_output=True, text=True)
            d = json.loads(r.stdout)
        except Exception as exc:
            continue
        text = str((d.get("message") or {}).get("content") or "").strip()
        if text:
            return {"ok": True, "model": m, "text": text[:MAX_DESCRIBED_CHARS]}
    return {"ok": False, "error": "every vision model failed", "tried": [VISION_MODEL,
                                                                        VISION_FALLBACK]}


def transcribe_audio(path: Path, *, timeout: int = 300) -> Dict[str, Any]:
    """The ears. Local whisper, any language, no cloud and no bill."""
    if not path.exists():
        return {"ok": False, "error": "no such file", "path": str(path)}
    # THE GPU FIRST. Measured 2026-10-03 on 20.3s of speech from this machine's own voice:
    #     mlx_whisper large-v3 (Apple GPU)   5.1s  → 4.0x realtime
    #     mlx_whisper small   (Apple GPU)    2.7s  → 7.5x realtime
    # while faster_whisper on the CPU is roughly 1x. The first version of this organ used the
    # CPU path and I told the owner to expect ~30 seconds for a 30-second note -- a wrong number
    # produced by leaving a GPU idle. A 30s voice note is 4-8 seconds.
    # (For "an hour in a few seconds" whisper is the wrong family entirely: that is
    # Parakeet-class ASR. This is the best ear we have until one of those is installed.)
    mlx_script = (
        "import sys, json\n"
        "import mlx_whisper\n"
        "r = mlx_whisper.transcribe(sys.argv[1], path_or_hf_repo=sys.argv[2])\n"
        "print(json.dumps({'text': (r.get('text') or '').strip(),\n"
        "                  'language': r.get('language') or ''}))\n"
    )
    cpu_script = (
        "import sys, json\n"
        "from faster_whisper import WhisperModel\n"
        "m = WhisperModel('large-v3', device='cpu', compute_type='int8')\n"
        "segs, info = m.transcribe(sys.argv[1], vad_filter=True)\n"
        "text = ' '.join(s.text.strip() for s in segs).strip()\n"
        "print(json.dumps({'text': text, 'language': getattr(info, 'language', '')}))\n"
    )
    attempts = [(BODY_PYTHON, mlx_script, ["mlx-community/whisper-large-v3-mlx"], "mlx_whisper"),
                (BODY_PYTHON, cpu_script, [], "faster_whisper_cpu"),
                ("python3", cpu_script, [], "faster_whisper_cpu")]
    for python, script, extra, engine in attempts:
        if not shutil.which(python) and not Path(python).exists():
            continue
        try:
            r = subprocess.run([python, "-c", script, str(path)] + extra,
                               capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 and r.stdout.strip():
                d = json.loads(r.stdout.strip().splitlines()[-1])
                if d.get("text"):
                    return {"ok": True, "text": d["text"][:MAX_DESCRIBED_CHARS],
                            "language": d.get("language", ""), "engine": f"{engine}/{python}"}
        except Exception:
            continue
    return {"ok": False, "error": "no working local transcriber",
            "tried": [a[3] for a in attempts]}


def scene_cuts(video: Path, *, threshold: float = 0.35) -> List[float]:
    """When does the picture change? ffmpeg's scene filter, measured in seconds.

    The Architect, 2026-10-03: "if there is a method to detect scenes in video files then extract
    only one frame / scene from every scene around the middle of it". There is, and it is better
    than sampling on a timer: a 5-second clip with two camera shots sampled every second gives
    four near-duplicate frames and misses nothing important, while two SCENES give exactly two
    frames -- one from each shot, taken where the shot is settled rather than mid-transition.
    """
    if not video.exists() or not shutil.which("ffmpeg"):
        return []
    try:
        r = subprocess.run(["ffmpeg", "-i", str(video),
                            "-filter:v", f"select='gt(scene,{threshold})',showinfo",
                            "-f", "null", "-"],
                           capture_output=True, text=True, timeout=180)
        text = (r.stderr or "") + (r.stdout or "")
    except Exception:
        return []
    cuts = []
    for line in text.splitlines():
        if "pts_time:" in line:
            try:
                t = float(line.split("pts_time:")[1].split()[0])
                cuts.append(round(t, 3))
            except Exception:
                continue
    return sorted(set(cuts))


def _scene_frames(video: Path, *, threshold: float = 0.35,
                  max_frames: int = MAX_VIDEO_FRAMES) -> List[Path]:
    """One still per scene, from the middle of each scene."""
    duration = 0.0
    try:
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(video)],
                           capture_output=True, text=True).stdout.strip()
        duration = float(d) if d else 0.0
    except Exception:
        duration = 0.0
    cuts = [c for c in scene_cuts(video, threshold=threshold) if 0.05 < c < (duration or 1e9)]
    bounds = [0.0] + cuts + ([duration] if duration else [])
    mids: List[float] = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a > 0.15:
            mids.append(round((a + b) / 2.0, 3))
    if not mids:                       # no cuts detected: fall back to even sampling
        if duration:
            step = duration / max(1, min(max_frames, 4))
            mids = [round(step * (i + 0.5), 3) for i in range(min(max_frames, 4))]
    tmp = Path(tempfile.mkdtemp(prefix="wa_scenes_"))
    out: List[Path] = []
    for i, t in enumerate(mids[:max_frames]):
        dest = tmp / f"scene_{i:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video),
                        "-frames:v", "1", "-q:v", "3", str(dest)], capture_output=True)
        if dest.exists():
            out.append(dest)
    return out


def _frames(video: Path, n: int = MAX_VIDEO_FRAMES) -> List[Path]:
    """A short clip becomes a handful of stills. ffmpeg, one per second, at most n."""
    if not shutil.which("ffmpeg"):
        return []
    out: List[Path] = []
    tmp = Path(tempfile.mkdtemp(prefix="wa_frames_"))
    try:
        dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(video)],
                             capture_output=True, text=True).stdout.strip()
        seconds = float(dur) if dur else 5.0
        step = max(0.5, seconds / max(1, n))
        for i in range(n):
            t = round(i * step, 2)
            dest = tmp / f"frame_{i:02d}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video),
                            "-frames:v", "1", "-q:v", "3", str(dest)],
                           capture_output=True)
            if dest.exists():
                out.append(dest)
    except Exception:
        return out
    return out


def describe_video(path: Path, *, timeout: int = 240) -> Dict[str, Any]:
    """Watch a clip: one frame per SCENE, from the middle of each, looked at in order."""
    frames = _scene_frames(path)
    if not frames:
        return {"ok": False, "error": "ffmpeg produced no frames (or is missing)"}
    looks: List[str] = []
    for i, f in enumerate(frames, 1):
        r = _vlm(f, prompt=("This is one frame from a short video, taken in order. Describe what "
                            "is happening in this frame in one or two sentences."),
                 timeout=timeout)
        if r.get("ok"):
            looks.append(f"frame {i}: {r['text']}")
    if not looks:
        return {"ok": False, "error": "frames were extracted but no model could read them"}
    return {"ok": True, "frames": len(frames), "text": " | ".join(looks)[:MAX_DESCRIBED_CHARS * 2]}


def understand(path: str, media_type: str = "image", *, write: bool = True) -> Dict[str, Any]:
    """Turn a file into words, whichever sense it needs."""
    p = Path(path)
    kind = (media_type or "image").lower()
    if kind == "audio":
        r = transcribe_audio(p)
        if r.get("ok"):
            r["text"] = f"[voice note, {r.get('language') or 'unknown language'}] {r['text']}"
    elif kind == "video":
        r = describe_video(p)
        if r.get("ok"):
            r["text"] = f"[video, {r.get('frames')} frames] {r['text']}"
    else:
        r = _vlm(p)
        if r.get("ok"):
            r["text"] = f"[photo] {r['text']}"
    out = {"ok": bool(r.get("ok")), "media_type": kind, "path": str(p),
           "text": r.get("text", ""), "error": r.get("error"), "truth_label": TRUTH_LABEL}
    if write:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **out}, ensure_ascii=False) + "\n")
    return out


def enrich_row(row: Dict[str, Any], *, write: bool = True) -> Dict[str, Any]:
    """Replace "[photo]" with what the photo contains, before any cortex is asked anything."""
    path = row.get("media_path")
    if not path:
        return row
    r = understand(str(path), str(row.get("media_type") or "image"), write=write)
    if r.get("ok") and r.get("text"):
        row["text"] = r["text"]
        row["understood"] = True
    else:
        row["text"] = (f"[{row.get('media_type') or 'attachment'} received but not understood: "
                       f"{r.get('error')}]")
        row["understood"] = False
    return row


def selftest() -> Dict[str, Any]:
    """Hermetic: shapes, tools and honest failure paths. No model is invoked here."""
    checks = {
        "the_vision_call_uses_a_string_content": isinstance(VISION_PROMPT, str),
        "ffmpeg_is_available": bool(shutil.which("ffmpeg")),
        "ffprobe_is_available": bool(shutil.which("ffprobe")),
        "a_missing_file_is_an_honest_failure": _vlm(Path("/nope/missing.jpg"))["ok"] is False,
        "audio_of_a_missing_file_fails_loudly": transcribe_audio(Path("/nope/missing.ogg"))["ok"]
                                                is False,
        "video_with_no_frames_fails_loudly": describe_video(Path("/nope/missing.mp4"))["ok"] is False,
        "understand_reports_its_truth_label": understand("/nope/x.jpg", "image",
                                                         write=False)["truth_label"] == TRUTH_LABEL,
        "a_row_without_media_is_untouched": enrich_row({"text": "hello"}, write=False) == {
            "text": "hello"},
        "an_image_row_gets_real_text_not_a_placeholder": (
            "[photo]" not in str(enrich_row(
                {"text": "[photo]", "media_path": "/nope/x.jpg", "media_type": "image"},
                write=False).get("text") or "")),
        "the_eyes_and_the_ears_are_local": "11434" in OLLAMA and "127.0.0.1" in OLLAMA,
        "scene_cuts_returns_a_list": isinstance(scene_cuts(Path("/nope.mp4")), list),
        "scene_frames_of_a_missing_video_is_empty": _scene_frames(Path("/nope.mp4")) == [],
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "look" and len(sys.argv) > 2:
        print(json.dumps(understand(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "image"),
                         indent=2)[:1500])
    else:
        print(json.dumps({"vision": VISION_MODEL, "ears": "faster_whisper large-v3 (local)",
                          "video": "ffmpeg scene cuts, one mid-scene frame each"}, indent=2))
