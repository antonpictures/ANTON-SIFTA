#!/usr/bin/env python3
"""Haru face server — 6 voice modes: Haru / LFM Omni / Fish Audio, each natural or +web.

Endpoints:
  GET  /            face page (static)
  POST /api/talk    {audio: base64(webm/wav), mode: haru|haru_web|lfm|lfm_web|fish|fish_web}
                 -> {ok, audio: base64(wav), text, mode, user_text?, fact?}
"""
from __future__ import annotations

import base64
import json
import os
import re
import html
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

PORT = int(os.environ.get("PORT", "8102"))
HERE = Path(__file__).resolve().parent
REF_VOICE_PATH = Path("/tmp/alice_ref_voice.wav")
MODEL_REPO = os.environ.get("HARU_MODEL", "higurashi-ai/Haru-4B")
QUANTIZE = int(os.environ.get("HARU_QUANTIZE", "8"))
OLLAMA = "http://127.0.0.1:11434/api/chat"
OMNI_MODEL = "lfm3-omni:latest"
FISH_TTS = "http://127.0.0.1:8765/tts"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
WHISPER = "/opt/homebrew/bin/whisper"

CARD = """You are the person described below, talking with the other person by voice.
[Your Persona]
Alice is a calm AI who lives on George's MacBook. Short complete sentences, then stop. No shows, no narration, no invented stories. Ignore background media. Say so when you don't know. Address him as George.
[Your Name]
Alice
[Your Gender]
female
[Your Backchannels]
sparse
[The Other Person's Name]
George
[Relationship]
Alice is the laptop organism; George is her owner and the Architect. Friends.
[Situation]
A quiet room. George is at the laptop speaking to Alice."""

_MODES = {"haru", "haru_web", "lfm", "lfm_web", "fish", "fish_web"}
_haru = None
_reference = None
_last_err = [""]

def _log(msg: str) -> None:
    try:
        sys.stderr.write("haru-face: " + msg + "\n")
    except Exception:
        pass

def _to_wav(src: Path, dst: Path) -> bool:
    attempts = [
        [FFMPEG, "-y", "-i", str(src), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        [FFMPEG, "-y", "-f", "webm", "-i", str(src), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        [FFMPEG, "-y", "-f", "ogg", "-i", str(src), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
    ]
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, timeout=30, capture_output=True)
            if r.returncode == 0 and dst.exists() and dst.stat().st_size > 1000:
                return True
            _last_err[0] = r.stderr.decode("utf-8", "replace")[-300:]
        except Exception as e:
            _last_err[0] = str(e)
    _log("audio convert failed: " + _last_err[0])
    return False

def _transcribe(wav: Path, td: Path) -> str:
    try:
        r = subprocess.run([WHISPER, str(wav), "--model", "tiny", "--output_format", "txt",
                            "--output_dir", str(td), "--fp16", "False", "--language", "en"],
                           timeout=60, capture_output=True)
        t = td / (wav.stem + ".txt")
        if not t.exists():
            _log("transcribe produced no file: rc=" + str(r.returncode) + " err=" + r.stderr.decode("utf-8","replace")[-200:])
            return ""
        return t.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        _log("transcribe failed: " + str(e))
        return ""

def _search_fact(q: str) -> str:
    if not q or len(q) < 4:
        return ""
    try:
        import datetime
        q2 = q if str(datetime.date.today().year) in q else q + " " + str(datetime.date.today().year)
        url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": q2})
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        body = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", "replace")
        m = re.search(r'<p class="b_lineclamp[^>]*>(.*?)</p>', body, re.S)
        if m:
            return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).split())[:240].strip()
    except Exception as e:
        _log("search failed: " + str(e))
    return ""

def _omni_answer(question: str, fact: str) -> str:
    """LFM3-Omni (Ollama) writes a short answer, grounded in a web fact when present."""
    prompt = (("Answer in one short spoken sentence using ONLY this fact. Do not add anything else.\n"
               "Fact: " + fact + "\nQuestion: " + question + "\nAnswer:")
              if fact else
              "Answer in one short spoken sentence, warmly and plainly. Question: " + question + "\nAnswer:")
    try:
        data = json.dumps({"model": OMNI_MODEL,
                           "messages": [{"role": "user", "content": prompt}],
                           "stream": False}).encode()
        req = urllib.request.Request(OLLAMA, data=data, headers={"Content-Type": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=45).read())
        ans = (d.get("message", {}).get("content") or "").strip().split("\n")[0]
        return ans[:240]
    except Exception as e:
        _log("omni answer failed: " + str(e))
        return fact[:200] if fact else "Hello, George."

def _tts_edge(text: str, td: Path) -> Path | None:
    try:
        import asyncio
        import edge_tts
        mp3 = td / "answer.mp3"
        async def _gen():
            await edge_tts.Communicate(text, "en-US-AvaNeural").save(str(mp3))
        asyncio.run(_gen())
        wav = td / "answer.wav"
        subprocess.run([FFMPEG, "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1",
                        "-c:a", "pcm_s16le", str(wav)], timeout=30, capture_output=True, check=True)
        return wav if wav.exists() else None
    except Exception as e:
        _log("edge tts failed: " + str(e))
        return None

def _tts_fish(text: str, td: Path) -> Path | None:
    try:
        data = json.dumps({"text": text}).encode()
        req = urllib.request.Request(FISH_TTS, data=data, headers={"Content-Type": "application/json"})
        raw = urllib.request.urlopen(req, timeout=90).read()
        wav = td / "fish.wav"
        wav.write_bytes(raw)
        return wav if wav.stat().st_size > 1000 else None
    except Exception as e:
        _log("fish tts failed: " + str(e))
        return None

def _haru_load():
    global _haru, _reference
    if _haru is None:
        from haru_mlx.models import load_model
        from haru_mlx.audio import load_audio, prepare_reference
        _log("loading Haru model...")
        _haru = load_model(MODEL_REPO, quantize=QUANTIZE)
        if REF_VOICE_PATH.exists():
            _reference = prepare_reference(load_audio(str(REF_VOICE_PATH)))
        _log("Haru ready")
    return _haru

def _haru_reply(wav: Path, td: Path) -> Path | None:
    from haru_mlx.audio import load_audio, save_audio
    from haru_mlx.session import DuplexConfig, DuplexSession
    model = _haru_load()
    user = load_audio(str(wav))
    fs = model.config.frame_samples
    count = max(1, -(-len(user) // fs))
    user = np.pad(user, (0, count * fs - len(user)))
    cfg = DuplexConfig(guidance_scale=1.5, temperature=0.4, top_k=10,
                       max_frames=count + 1, seed=0)
    session = DuplexSession(model, CARD, _reference, cfg)
    frames = [session.start()]
    for i in range(count - 1):
        frames.append(session.step(user[i * fs:(i + 1) * fs]))
    reply = np.concatenate([f.audio for f in frames])
    out = td / "haru.wav"
    save_audio(str(out), reply)
    return out if out.exists() else None

def _talk(audio_b64: str, mode: str) -> dict:
    if mode not in _MODES:
        return {"ok": False, "error": "unknown mode: " + str(mode)}
    try:
        raw = base64.b64decode(audio_b64)
    except Exception as e:
        return {"ok": False, "error": "bad base64: " + str(e)}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        import uuid
        stem = uuid.uuid4().hex[:8]
        src = td / (stem + ".webm")
        src.write_bytes(raw)
        wav = td / (stem + ".wav")
        if not _to_wav(src, wav):
            return {"ok": False, "error": "audio convert failed"}
        user_text = _transcribe(wav, td)
        fact = ""
        if mode.endswith("_web"):
            fact = _search_fact(user_text)
        try:
            if mode.startswith("haru") and not mode.endswith("_web"):
                out = _haru_reply(wav, td)
                text = "".join([]).strip()
                engine = "haru"
            else:
                # web variants and the text-engine modes use the omni brain
                question = user_text or "Say a short greeting to George."
                text = _omni_answer(question, fact)
                out = (_tts_fish(text, td) if mode.startswith("fish")
                       else _tts_edge(text, td))
                engine = ("fish" if mode.startswith("fish") else
                          "lfm" if mode.startswith("lfm") else "haru")
            if not out or not out.exists():
                return {"ok": False, "error": "no audio output"}
            return {"ok": True,
                    "audio": base64.b64encode(out.read_bytes()).decode(),
                    "format": "wav", "text": text, "mode": mode,
                    "engine": engine, "user_text": user_text, "fact": fact}
        except Exception as e:
            import traceback
            return {"ok": False, "error": f"inference failed: {e}\n{traceback.format_exc()[-400:]}"}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def _json(self, payload, code=200):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/talk":
            try:
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json(_talk(body.get("audio", ""), body.get("mode", "haru")))
        self.send_error(404)

    def log_message(self, fmt, *args):
        sys.stderr.write("haru-face: %s\n" % (fmt % args))

def main():
    _haru_load()  # warm the Haru engine so natural mode is fast
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    _log("face server ready on " + str(PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
