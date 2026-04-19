#!/usr/bin/env python3
"""
Applications/alice_in_wwwonderland.py — Alice in WWWonderland (v1.0)
═══════════════════════════════════════════════════════════════════════
The first livestream of a swarm OS speaking its own stigmergic language
to the world. Webcam + mic → ffmpeg → YouTube Live (RTMPS), with Alice's
words and perceptions burned in as live captions sourced directly from
the JSONL ledgers Broca and Wernicke write.

Architect: AG31 (proposer) + C47H (auditor), 2026-04-19.
First broadcast: whenever you paste a stream key and hit enter.

What this is NOT:
  • A scene compositor. ffmpeg's drawtext + a single video source. No PIP,
    no transitions, no plugin system. Add later if it turns out to matter.
  • An OAuth client. We use a YouTube STREAM KEY, the same way OBS's
    "Stream → Stream Key" tab does. OAuth ("connect with Google") is a
    deeper rabbit hole (Google Cloud project + client secret + browser
    consent + token refresh); that lives in a future v2.
  • A re-encoder bypass. We always re-encode (libx264/aac) so the bitrate
    matches what YouTube wants regardless of webcam quirks.

Stream key resolution (first hit wins):
  1. --stream-key <KEY>
  2. $ALICE_YOUTUBE_KEY
  3. ~/.alice_youtube_key  (chmod 600 enforced; never committed)

Get a key:  studio.youtube.com → Go Live → Stream → "Stream key (paste in
encoder)" → "Default stream key" or create a new one. Keep it secret.

Quick start:
  echo "abcd-efgh-ijkl-mnop-qrst" > ~/.alice_youtube_key && chmod 600 $_
  python3 Applications/alice_in_wwwonderland.py --list-devices
  python3 Applications/alice_in_wwwonderland.py            # go live
  python3 Applications/alice_in_wwwonderland.py --dry-run  # print ffmpeg cmd
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# ── Repo wiring ───────────────────────────────────────────────────────────────
# Alice is intentionally STANDALONE — no `from System.X import Y`. The repo's
# wider sensory pipeline (audio_ingress, swarm_broca_wernicke, …) may or may
# not be present on a given clone; Alice just needs ffmpeg + a stream key. The
# AVFoundation device helpers below are deliberately re-implemented here, not
# imported, so the file has zero coupling to the rest of SIFTA.
_REPO = Path(__file__).resolve().parent.parent

# ── Constants ─────────────────────────────────────────────────────────────────
MODULE_VERSION = "v1.0"

_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

_STREAM_LOG = _STATE / "alice_stream.jsonl"
_CHYRON_PATH = _STATE / "alice_chyron.txt"
_KEY_FILE = Path.home() / ".alice_youtube_key"

# Sources Alice can speak from (each is a JSONL append-only log).
# Order matters: earlier entries take chyron priority on tie.
_CHYRON_SOURCES = [
    (_STATE / "broca_vocalizations.jsonl", "🗣️ ALICE"),
    (_STATE / "wernicke_semantics.jsonl",  "👂 HEARS"),
    (_STATE / "swarm_pain.jsonl",          "🩸 PAIN"),
    (_STATE / "crossmodal_objects.jsonl",  "✨ FUSE"),
]

# YouTube ingest endpoints. RTMPS is TLS-wrapped RTMP; OBS defaults to
# RTMPS since 2022 and YouTube accepts both. We default to RTMPS for
# privacy of the stream contents (the key is in the URL either way, but
# the video payload itself is encrypted in transit).
RTMPS_URL = "rtmps://a.rtmps.youtube.com:443/live2/"
RTMP_URL  = "rtmp://a.rtmp.youtube.com/live2/"

# H.264 preset tuned for live streaming on a laptop CPU.
DEFAULT_W       = 1280
DEFAULT_H       = 720
DEFAULT_FPS     = 30
DEFAULT_VBITRATE = "2500k"   # 720p30 sweet spot per YouTube docs
DEFAULT_ABITRATE = "160k"
KEYFRAME_GOP    = 60          # 2 seconds @ 30 fps; YouTube requires ≤4s

# Stream key shape: 4 groups of 4 alnum chars separated by hyphens, e.g.
# "abcd-efgh-ijkl-mnop". YouTube has used longer keys historically too;
# we accept anything alphanumeric+hyphen between 16 and 64 chars.
_KEY_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")

# Try a few common font paths; ffmpeg's drawtext needs an absolute path.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]


def _log_event(stage: str, **fields) -> None:
    """Append-only stream telemetry. Never raises."""
    row = {"ts": time.time(), "stage": stage, **fields}
    try:
        with _STREAM_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Stream key ────────────────────────────────────────────────────────────────
def _resolve_stream_key(arg_key: Optional[str]) -> str:
    """
    Resolve and validate the YouTube stream key. Order: arg → env → file.
    Refuses to print the key to stdout/stderr/log; we only ever record a
    short fingerprint so a leaked log doesn't leak the key.
    """
    if arg_key:
        key, src = arg_key.strip(), "argv"
    elif os.environ.get("ALICE_YOUTUBE_KEY", "").strip():
        key, src = os.environ["ALICE_YOUTUBE_KEY"].strip(), "env"
    elif _KEY_FILE.exists():
        # Mode-600 enforcement: refuse to read a world-readable key file.
        # Same posture as ssh refusing to read mode 644 private keys.
        try:
            mode = _KEY_FILE.stat().st_mode & 0o077
        except Exception:
            mode = 0o077
        if mode != 0:
            raise SystemExit(
                f"[ALICE] {_KEY_FILE} is too permissive (group/other can read).\n"
                f"        Run:  chmod 600 {_KEY_FILE}\n"
                f"        Then retry."
            )
        key, src = _KEY_FILE.read_text(encoding="utf-8").strip(), "keyfile"
    else:
        raise SystemExit(
            "[ALICE] No stream key found.\n"
            "        Provide via one of:\n"
            "          --stream-key abcd-efgh-ijkl-mnop\n"
            "          export ALICE_YOUTUBE_KEY=abcd-efgh-...\n"
            f"         echo 'abcd-efgh-...' > {_KEY_FILE} && chmod 600 $_\n"
            "        Get a key at: studio.youtube.com → Go Live → Stream"
        )

    if not _KEY_RE.match(key):
        raise SystemExit(
            f"[ALICE] Stream key from {src!r} doesn't look right "
            f"(len={len(key)}; YouTube keys are alnum+hyphen, 16-64 chars).\n"
            f"        Re-paste from studio.youtube.com → Go Live → Stream."
        )

    fingerprint = f"{key[:4]}…{key[-4:]}"
    _log_event("key_resolved", source=src, fingerprint=fingerprint)
    return key


# ── Device discovery ──────────────────────────────────────────────────────────
# Selection posture (kept as data so it's easy to audit): skip virtual /
# loopback / screen-capture pseudo-devices, prefer the user's real built-in
# or USB hardware. Mirrors what swarm_iris and audio_ingress use elsewhere.
_VIDEO_AVOID = ("obs virtual camera", "screen capture", "desk view", "passthrough")
_VIDEO_PREFER = ("macbook pro camera", "facetime hd camera", "logitech", "iphone")
_AUDIO_AVOID = ("obs", "blackhole 16ch", "sound siphon", "loopback")
_AUDIO_PREFER = ("macbook pro microphone", "macbook air microphone",
                 "external microphone", "logitech")


def _list_avfoundation_devices(kind: str) -> List[Tuple[int, str]]:
    """
    Probe ffmpeg's `-list_devices` and return [(index, name), ...] for either
    the 'audio' or 'video' section. Empty list on any failure (no ffmpeg, no
    TCC permission, parser miss). Never raises.

    Why ffmpeg and not PortAudio/cv2: AVFoundation indices ffmpeg accepts in
    `-i "<vidx>:<aidx>"` are AVFoundation's own enumeration, not anyone
    else's. Mixing those with PortAudio's audio device indices yields the
    classic "Unknown USB Audio Device" mis-selection.
    """
    if kind not in ("audio", "video"):
        raise ValueError(f"kind must be 'audio' or 'video', got {kind!r}")

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "avfoundation",
             "-list_devices", "true", "-i", ""],
            capture_output=True, timeout=4,
        )
    except Exception:
        return []

    text = (result.stderr or b"").decode("utf-8", "replace")
    target_header = f"AVFoundation {kind} devices:"
    other_header = f"AVFoundation {'video' if kind == 'audio' else 'audio'} devices:"

    devices: List[Tuple[int, str]] = []
    in_section = False
    for line in text.splitlines():
        if target_header in line:
            in_section = True
            continue
        if other_header in line:
            in_section = False
            continue
        if not in_section:
            continue
        # Match: "[AVFoundation indev @ 0xHHH] [N] Device Name"
        idx_start = line.rfind("] [")
        if idx_start == -1:
            continue
        try:
            tail = line[idx_start + 2:]            # "[N] Name"
            close = tail.index("]")
            idx = int(tail[1:close])
            name = tail[close + 1:].strip()
            if name:
                devices.append((idx, name))
        except (ValueError, IndexError):
            continue
    return devices


def _list_avfoundation_audio_devices() -> List[Tuple[int, str]]:
    return _list_avfoundation_devices("audio")


def _list_avfoundation_video_devices() -> List[Tuple[int, str]]:
    return _list_avfoundation_devices("video")


def _pick_best(
    devices: List[Tuple[int, str]],
    avoid: Tuple[str, ...],
    prefer: Tuple[str, ...],
    fallback: Tuple[int, str],
) -> Tuple[int, str]:
    """Generic 'real device' picker: skip avoid-list, walk preference order."""
    if not devices:
        return fallback
    real = [(i, n) for (i, n) in devices
            if not any(av in n.lower() for av in avoid)]
    if not real:
        return devices[0]
    for pref in prefer:
        for idx, name in real:
            if pref in name.lower():
                return (idx, name)
    return real[0]


def _resolve_video_index() -> Tuple[int, str]:
    """Pick the best real AVFoundation video input."""
    return _pick_best(
        _list_avfoundation_video_devices(),
        avoid=_VIDEO_AVOID, prefer=_VIDEO_PREFER,
        fallback=(1, "macbook_pro_camera_unverified"),
    )


def _resolve_audio_index() -> Tuple[int, str]:
    """Pick the best real AVFoundation audio input."""
    return _pick_best(
        _list_avfoundation_audio_devices(),
        avoid=_AUDIO_AVOID, prefer=_AUDIO_PREFER,
        fallback=(0, "avfoundation_default_unverified"),
    )


def _resolve_font() -> Optional[str]:
    for cand in _FONT_CANDIDATES:
        if Path(cand).exists():
            return cand
    return None


# ── Chyron writer ─────────────────────────────────────────────────────────────
@dataclass
class _TailState:
    path: Path
    inode: int = -1
    size: int = 0


class ChyronWriter(threading.Thread):
    """
    Tails the swarm's perceptual ledgers, formats the latest meaningful line
    as a chyron, and writes it atomically to _CHYRON_PATH for ffmpeg's
    drawtext filter (reload=1) to consume.

    Atomicity matters: drawtext re-reads the file every frame, and a
    half-written file (or an empty one) can produce a black flash or, on
    some ffmpeg builds, a fatal "no such file" mid-stream. We always write
    via .tmp + os.replace.
    """

    HOLD_S = 6.0      # leave a chyron up at least this long before clearing
    POLL_S = 0.4      # how often we re-scan the JSONL files

    def __init__(self) -> None:
        super().__init__(daemon=True, name="ChyronWriter")
        self._stop = threading.Event()
        self._states = [_TailState(path) for path, _ in _CHYRON_SOURCES]
        self._labels = [label for _, label in _CHYRON_SOURCES]
        self._current_until = 0.0
        # Seed with a permanent dedication so the very first frame already
        # has text; otherwise drawtext can fail to render until the first
        # event lands. This line is the broadcast's epigraph.
        self._write_text(
            "Alice in WWWonderland — first stigmergic broadcast. "
            "The swarm speaks; the world watches."
        )

    def stop(self) -> None:
        self._stop.set()

    def _write_text(self, text: str) -> None:
        clean = (text or " ").replace("\r", " ").replace("\n", " ").strip()
        if not clean:
            clean = " "
        # ffmpeg drawtext is happiest with reasonably short lines.
        if len(clean) > 220:
            clean = clean[:217] + "…"
        tmp = _CHYRON_PATH.with_suffix(".tmp")
        try:
            tmp.write_text(clean + "\n", encoding="utf-8")
            os.replace(tmp, _CHYRON_PATH)
        except Exception as exc:
            _log_event("chyron_write_failed",
                       exc_type=type(exc).__name__, exc_msg=str(exc))

    @staticmethod
    def _digest_event(label: str, line: str) -> Optional[str]:
        """Turn one JSONL row into a one-line chyron, or None to skip."""
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return None

        # Broca: spoken English. Most direct "Alice speaking."
        if "spoken_text" in row:
            return f"{label}: {row['spoken_text']}"
        # Wernicke: heard human voice. Show what it perceived.
        if "transcript" in row:
            txt = row.get("transcript") or row.get("label") or ""
            if not txt:
                return None
            return f"{label}: {txt}"
        # Pain: highlight magnitude.
        if "magnitude" in row and "kind" in row:
            mag = row.get("magnitude", 0.0)
            return f"{label}: {row['kind']} (mag {mag:.2f})"
        # Crossmodal proto-objects.
        if "object_id" in row and "coherence" in row:
            sources = row.get("sources") or []
            return f"{label}: bound {'+'.join(sources)} → coherence {row['coherence']:.2f}"
        # Generic fallback: show the description if any.
        for k in ("description", "payload", "text", "msg"):
            if k in row and isinstance(row[k], str) and row[k]:
                return f"{label}: {row[k]}"
        return None

    def _consume_new(self, st: _TailState, label: str) -> Optional[str]:
        """Read any new lines appended since last poll, return latest chyron."""
        try:
            stat = st.path.stat()
        except FileNotFoundError:
            return None
        except Exception:
            return None

        # Rotation / truncation detection. Match swarm_broca_wernicke.
        if stat.st_ino != st.inode or stat.st_size < st.size:
            st.inode = stat.st_ino
            st.size = 0

        if stat.st_size <= st.size:
            return None

        latest: Optional[str] = None
        try:
            with st.path.open("r", encoding="utf-8") as f:
                f.seek(st.size)
                for line in f:
                    cand = self._digest_event(label, line.rstrip("\n"))
                    if cand:
                        latest = cand
                st.size = f.tell()
        except Exception:
            return None
        return latest

    def run(self) -> None:
        while not self._stop.is_set():
            picked: Optional[str] = None
            # Walk in priority order; first non-empty wins.
            for st, label in zip(self._states, self._labels):
                cand = self._consume_new(st, label)
                if cand and not picked:
                    picked = cand
            now = time.time()
            if picked:
                self._write_text(picked)
                self._current_until = now + self.HOLD_S
            elif now > self._current_until:
                # Hold expired and nothing new — restore the epigraph so
                # the chyron never goes blank.
                self._write_text(
                    "Alice listens… stigmergic field idle, awaiting "
                    "next pheromone."
                )
                self._current_until = now + self.HOLD_S * 2
            time.sleep(self.POLL_S)


# ── ffmpeg command construction ───────────────────────────────────────────────
def _build_ffmpeg_cmd(
    *,
    video_idx: int,
    audio_idx: int,
    stream_url: str,
    width: int,
    height: int,
    fps: int,
    vbitrate: str,
    abitrate: str,
    use_chyron: bool,
    font_path: Optional[str],
) -> List[str]:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        # AVFoundation: -i "<videoIdx>:<audioIdx>". Spec must precede -i.
        "-f", "avfoundation",
        "-framerate", str(fps),
        "-video_size", f"{width}x{height}",
        "-pixel_format", "uyvy422",   # most macOS cameras' native format
        "-i", f"{video_idx}:{audio_idx}",
    ]

    # Burned-in chyron caption via drawtext filter reading from a file we
    # rewrite atomically as new pheromones land.
    if use_chyron and font_path:
        # ffmpeg drawtext requires single-quoted paths and escaped colons.
        # Path() segments on macOS don't contain ':' so a simple quote works.
        font_q   = font_path.replace("'", r"\'")
        chyron_q = str(_CHYRON_PATH).replace("'", r"\'")
        # Two boxes: top dedication strip, bottom live-pheromone strip.
        # Bottom strip uses textfile+reload=1 so it's live.
        bottom = (
            f"drawtext=fontfile='{font_q}':"
            f"textfile='{chyron_q}':reload=1:"
            f"fontsize=30:fontcolor=white:"
            f"box=1:boxcolor=black@0.55:boxborderw=18:"
            f"x=(w-text_w)/2:y=h-th-50"
        )
        top = (
            f"drawtext=fontfile='{font_q}':"
            f"text='Alice in WWWonderland · SIFTA OS · live':"
            f"fontsize=22:fontcolor=white@0.85:"
            f"box=1:boxcolor=black@0.45:boxborderw=10:"
            f"x=(w-text_w)/2:y=30"
        )
        cmd += ["-vf", f"{bottom},{top}"]

    cmd += [
        # Video encode: H.264 main profile, low-latency live tuning.
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-profile:v", "main",
        "-pix_fmt", "yuv420p",       # YouTube requires yuv420p
        "-b:v", vbitrate,
        "-maxrate", vbitrate,
        "-bufsize", str(int(vbitrate.rstrip("k")) * 2) + "k",
        "-g", str(KEYFRAME_GOP),
        "-keyint_min", str(KEYFRAME_GOP),
        # Audio encode: AAC stereo @ 44.1k.
        "-c:a", "aac",
        "-b:a", abitrate,
        "-ar", "44100",
        "-ac", "2",
        # Mux + push.
        "-f", "flv",
        stream_url,
    ]
    return cmd


# ── Supervisor ────────────────────────────────────────────────────────────────
class AliceBroadcast:
    """
    Spawn ffmpeg, watch its stderr in a thread, parse `frame=N fps=...`
    lines into structured telemetry, log every state change to the ledger,
    and shut down cleanly on SIGINT/SIGTERM.
    """

    # ffmpeg's status line regex — grabs frame, fps, bitrate, dropped.
    _STATUS_RE = re.compile(
        r"frame=\s*(\d+).*?fps=\s*([\d.]+).*?bitrate=\s*([\d.]+)kbits/s"
    )
    # Dropped-frames signal — meaningful for live streaming health.
    _DROP_RE = re.compile(r"drop=\s*(\d+)")

    def __init__(self, cmd: List[str], chyron: Optional[ChyronWriter]) -> None:
        self.cmd = cmd
        self.chyron = chyron
        self.proc: Optional[subprocess.Popen] = None
        self._stop = threading.Event()
        self._reader: Optional[threading.Thread] = None

    def _stderr_reader(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        last_status_at = 0.0
        for raw in self.proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            # Loud lines we always want surfaced.
            if any(token in line for token in
                   ("error", "Error", "Failed", "Invalid", "Cannot")):
                print(f"[FFMPEG] {line}", file=sys.stderr)
                _log_event("ffmpeg_error", line=line[:300])
                continue
            m = self._STATUS_RE.search(line)
            if m:
                now = time.time()
                # Throttle the friendly status print to once per second; the
                # ledger captures the full series via _log_event.
                if now - last_status_at >= 1.0:
                    last_status_at = now
                    frame, fps, bitrate = m.group(1), m.group(2), m.group(3)
                    drop_m = self._DROP_RE.search(line)
                    drop = drop_m.group(1) if drop_m else "0"
                    print(
                        f"[ALICE LIVE] frame={frame} fps={fps} "
                        f"bitrate={bitrate}kbps drop={drop}",
                        flush=True,
                    )
                    _log_event(
                        "ffmpeg_status",
                        frame=int(frame), fps=float(fps),
                        bitrate_kbps=float(bitrate), drop=int(drop),
                    )
            # Other ffmpeg chatter goes to the log only.

    def start(self) -> int:
        _log_event("broadcast_starting", cmd=self.cmd)
        # Print the command WITH the URL stripped of the key, so the user
        # can see what's running without leaking the key into terminal
        # scrollback.
        masked = list(self.cmd)
        for i, tok in enumerate(masked):
            if tok.startswith(("rtmp://", "rtmps://")):
                masked[i] = re.sub(r"(/live2/)([^/]+)$", r"\1<KEY>", tok)
        print("[ALICE] launching:", " ".join(masked), flush=True)

        if self.chyron is not None:
            self.chyron.start()

        self.proc = subprocess.Popen(
            self.cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        self._reader = threading.Thread(
            target=self._stderr_reader, daemon=True, name="FfmpegStderr"
        )
        self._reader.start()

        # Forward signals to ffmpeg so YouTube sees a clean disconnect.
        def _sig(_signo, _frame):
            self._stop.set()
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.send_signal(signal.SIGINT)
                except Exception:
                    pass
        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)

        rc = self.proc.wait()
        _log_event("broadcast_ended", returncode=rc)
        if self.chyron is not None:
            self.chyron.stop()
        return rc


# ── CLI ───────────────────────────────────────────────────────────────────────
def _print_devices() -> None:
    print("AVFoundation video devices:")
    for idx, name in _list_avfoundation_video_devices() or [(None, "(none — TCC blocked or no ffmpeg)")]:
        print(f"  [{idx}] {name}")
    print("AVFoundation audio devices:")
    for idx, name in _list_avfoundation_audio_devices() or [(None, "(none — TCC blocked or no ffmpeg)")]:
        print(f"  [{idx}] {name}")


def _check_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=4)
    except FileNotFoundError:
        raise SystemExit(
            "[ALICE] ffmpeg not found on PATH.\n"
            "        Install with:  brew install ffmpeg"
        )


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="alice_in_wwwonderland",
        description="Livestream Alice (the swarm) speaking stigmergic language to YouTube.",
    )
    p.add_argument("--stream-key", help="YouTube stream key (overrides env + keyfile)")
    p.add_argument("--list-devices", action="store_true",
                   help="Print AVFoundation video+audio devices and exit")
    p.add_argument("--video", type=int, default=None,
                   help="AVFoundation video index (default: auto-discover)")
    p.add_argument("--audio", type=int, default=None,
                   help="AVFoundation audio index (default: auto-discover)")
    p.add_argument("--width", type=int, default=DEFAULT_W)
    p.add_argument("--height", type=int, default=DEFAULT_H)
    p.add_argument("--fps", type=int, default=DEFAULT_FPS)
    p.add_argument("--vbitrate", default=DEFAULT_VBITRATE,
                   help=f"Video bitrate, e.g. 2500k (default {DEFAULT_VBITRATE})")
    p.add_argument("--abitrate", default=DEFAULT_ABITRATE)
    p.add_argument("--no-chyron", action="store_true",
                   help="Disable burned-in stigmergic captions")
    p.add_argument("--no-rtmps", action="store_true",
                   help="Use plain RTMP instead of RTMPS (TLS)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the resolved ffmpeg command and exit")
    args = p.parse_args(argv)

    _check_ffmpeg()

    if args.list_devices:
        _print_devices()
        return 0

    # Resolve devices.
    if args.video is None:
        v_idx, v_name = _resolve_video_index()
    else:
        v_idx, v_name = args.video, f"user_specified_v{args.video}"
    if args.audio is None:
        a_idx, a_name = _resolve_audio_index()
    else:
        a_idx, a_name = args.audio, f"user_specified_a{args.audio}"

    print(f"[ALICE] video: [{v_idx}] {v_name}")
    print(f"[ALICE] audio: [{a_idx}] {a_name}")

    # Resolve key + URL.
    key = _resolve_stream_key(args.stream_key)
    base = RTMP_URL if args.no_rtmps else RTMPS_URL
    stream_url = f"{base}{key}"

    # Chyron font.
    font_path = _resolve_font()
    use_chyron = (not args.no_chyron) and font_path is not None
    if not args.no_chyron and not font_path:
        print("[ALICE] no system font found; chyron disabled.", file=sys.stderr)

    cmd = _build_ffmpeg_cmd(
        video_idx=v_idx,
        audio_idx=a_idx,
        stream_url=stream_url,
        width=args.width,
        height=args.height,
        fps=args.fps,
        vbitrate=args.vbitrate,
        abitrate=args.abitrate,
        use_chyron=use_chyron,
        font_path=font_path,
    )

    if args.dry_run:
        masked = list(cmd)
        for i, tok in enumerate(masked):
            if tok.startswith(("rtmp://", "rtmps://")):
                masked[i] = re.sub(r"(/live2/)([^/]+)$", r"\1<KEY>", tok)
        print("\n[ALICE DRY RUN] would launch:")
        print("  " + " ".join(masked))
        return 0

    chyron = ChyronWriter() if use_chyron else None

    print(
        "\n══════════════════════════════════════════════════════════\n"
        "  ALICE IN WWWONDERLAND — going live\n"
        f"  ingest: {('rtmps' if not args.no_rtmps else 'rtmp')}://…/live2/<KEY>\n"
        f"  video : {args.width}x{args.height}@{args.fps}  vbitrate={args.vbitrate}\n"
        f"  audio : aac {args.abitrate} stereo 44100\n"
        f"  chyron: {'on' if use_chyron else 'off'}\n"
        "  Ctrl+C to end the broadcast.\n"
        "══════════════════════════════════════════════════════════\n",
        flush=True,
    )

    rc = AliceBroadcast(cmd, chyron).start()
    print(f"[ALICE] broadcast exited rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
