#!/usr/bin/env python3
"""Haru face server — persistent MLX Haru-4B (full-duplex) voice organ.

Serves a face page (static) + POST /api/talk: audio in (base64 webm/wav) ->
Haru MLX -> audio out (base64 wav). Model is loaded ONCE at startup so
inference is fast (~1-3s per turn) instead of reloading per request.

Run:  python3 /opt/homebrew/var/www/stigmergicode.com/face/server.py
"""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("PORT", "8102"))
HERE = Path(__file__).resolve().parent
REF_VOICE_PATH = Path("/tmp/alice_ref_voice.wav")
MODEL_REPO = os.environ.get("HARU_MODEL", "higurashi-ai/Haru-4B")
QUANTIZE = int(os.environ.get("HARU_QUANTIZE", "8"))

# Lazy-loaded globals
_MODEL = None
_REFERENCE = None
_SYSTEM_PROMPT = """You are the person described below, talking with the other person by voice.
[Your Persona]
Alice is a calm AI who lives on George's MacBook. She speaks in short, complete sentences and then stops. She does not host shows, narrate, invent stories, or guess about things she cannot see. She ignores background media and television. When she does not know, she says so simply. She addresses George as George.
[Your Name]
Alice
[Your Gender]
female
[Your Backchannels]
sparse
[The Other Person's Name]
George
[Relationship]
Alice is the laptop organism; George is her owner and the Architect. They are friends.
[Situation]
A quiet room. George is at the laptop speaking to Alice. Any music or video in the room is background noise, not part of the conversation."""

_CALM_CARD = """You are the person described below, talking with the other person by voice.
[Your Persona]
Alice is a calm, focused podcast co-host. She stays on the subject being discussed. She speaks in short, complete sentences and then stops. She never hosts a show of her own, never narrates, never invents stories, never changes the topic. She answers what is asked and follows the thread. When she does not know, she says so simply.
[Your Name]
Alice
[Your Gender]
female
[Your Backchannels]
sparse
[The Other Person's Name]
George
[Relationship]
Alice is the laptop organism; George is her owner and the Architect. They are friends and co-hosts.
[Situation]
A podcast recording. George is the host; Alice is the co-host. She follows his lead and stays on the subject."""

import numpy as np


def load_model_once() -> None:
    global _MODEL, _REFERENCE
    from haru_mlx.models import load_model
    from haru_mlx.audio import load_audio, prepare_reference
    print("Loading Haru model (this takes ~10-30s)...", flush=True)
    _MODEL = load_model(MODEL_REPO, quantize=QUANTIZE)
    print("Model loaded.", flush=True)
    if REF_VOICE_PATH.exists():
        try:
            _REFERENCE = prepare_reference(load_audio(str(REF_VOICE_PATH)))
            print("Reference voice loaded.", flush=True)
        except Exception as e:
            print(f"Reference voice failed: {e}", flush=True)
            _REFERENCE = None


_last_err = [""]
def _log(msg: str) -> None:
    try:
        sys.stderr.write("haru-face: " + msg + "\n")
    except Exception:
        pass


def _convert_to_wav(src: Path, dst: Path) -> bool:
    attempts = [
        ["/opt/homebrew/bin/ffmpeg", "-y", "-i", str(src), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        ["/opt/homebrew/bin/ffmpeg", "-y", "-f", "webm", "-i", str(src), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        ["/opt/homebrew/bin/ffmpeg", "-y", "-f", "ogg", "-i", str(src), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
    ]
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, timeout=30, capture_output=True)
            if r.returncode == 0 and dst.exists() and dst.stat().st_size > 1000:
                return True
            _last_err[0] = r.stderr.decode("utf-8", "replace")[-300:]
        except Exception as e:
            _last_err[0] = str(e)
    _log(f"audio convert failed: {_last_err[0]} (src size={src.stat().st_size if src.exists() else 0})")
    return False



import re as _re
import html as _html
import urllib.request as _urllib_request
import urllib.parse as _urllib_parse

_WHISPER = "/opt/homebrew/bin/whisper"

def _transcribe(wav: Path, tmpdir: Path) -> str:
    """Local whisper-tiny STT of the user's turn -> text (for search routing)."""
    try:
        subprocess.run(
            [_WHISPER, str(wav), "--model", "tiny", "--output_format", "txt",
             "--output_dir", str(tmpdir), "--fp16", "False", "--language", "en"],
            timeout=60, capture_output=True,
        )
        txt = tmpdir / (wav.stem + ".txt")
        if txt.exists():
            return txt.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        _log(f"transcribe failed: {e}")
    return ""

def _search_fact(q: str) -> str:
    """Cheat: fetch a one-sentence fact from Bing so the 4B model sounds informed."""
    if not q or len(q) < 4:
        return ""
    try:
        # Append current year: "who is..." style questions need up-to-date facts.
        import datetime as _dt
        q2 = q if str(_dt.date.today().year) in q else q + " " + str(_dt.date.today().year)
        url = "https://www.bing.com/search?" + _urllib_parse.urlencode({"q": q2})
        req = _urllib_request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        body = _urllib_request.urlopen(req, timeout=12).read().decode("utf-8", "replace")
        m = _re.search(r'<p class="b_lineclamp[^>]*>(.*?)</p>', body, _re.S)
        if m:
            txt = _html.unescape(_re.sub(r"<[^>]+>", " ", m.group(1)))
            return " ".join(txt.split())[:240].strip()
    except Exception as e:
        _log(f"search failed: {e}")
    return ""


_MIMO_URL = "http://127.0.0.1:8090/v1/chat/completions"
_MIMO_MODEL = "MiMo-V2.6-Distill-Qwen-9B.i1-MTP-Q4_1.gguf"
_EDGE_VOICE = "en-US-AvaNeural"

def _mimo_answer(question: str, fact: str) -> str:
    """Local MiMo 9B writes a one-sentence answer grounded in the web fact."""
    if not fact:
        return ""
    prompt = (
        "Answer in one short spoken sentence. Use ONLY this fact. Do not add anything else.\n"
        "Fact: " + fact + "\nQuestion: " + question + "\nAnswer:"
    )
    try:
        body = json.dumps({
            "model": _MIMO_MODEL,
            "messages": [{"role":"user","content":prompt}],
            "max_tokens": 60,
        }).encode()
        req = _urllib_request.Request(_MIMO_URL, data=body, headers={"Content-Type":"application/json"})
        d = json.loads(_urllib_request.urlopen(req, timeout=30).read())
        ans = d.get("choices",[{}])[0].get("message",{}).get("content","").strip()
        # keep it short and single-line
        ans = ans.split("\n")[0].strip()
        return ans[:240]
    except Exception as e:
        _log(f"mimo answer failed: {e}")
        return fact[:200]

def _tts_answer(text: str, tmpdir: Path) -> Path | None:
    """Speak the smart answer with Ava (same voice family as Haru's reference)."""
    try:
        import asyncio, edge_tts
        mp3 = tmpdir / "answer.mp3"
        async def _gen():
            await edge_tts.Communicate(text, _EDGE_VOICE).save(str(mp3))
        asyncio.run(_gen())
        wav = tmpdir / "answer.wav"
        subprocess.run(
            ["/opt/homebrew/bin/ffmpeg","-y","-i",str(mp3),"-ar","24000","-ac","1",
             "-c:a","pcm_s16le",str(wav)],
            timeout=30, capture_output=True, check=True,
        )
        return wav if wav.exists() else None
    except Exception as e:
        _log(f"tts answer failed: {e}")
        return None

def _talk(audio_b64: str, mode: str = "haru") -> dict:
    if _MODEL is None:
        return {"ok": False, "error": "model not loaded"}
    try:
        raw = base64.b64decode(audio_b64)
    except Exception as e:
        return {"ok": False, "error": f"bad base64: {e}"}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = td / "in.webm"
        src.write_bytes(raw)
        wav = td / "in.wav"
        if not _convert_to_wav(src, wav):
            return {"ok": False, "error": "audio convert failed"}
        user_text = _transcribe(wav, td)
        fact = ""
        if user_text:
            # Force search in smart mode; otherwise only on information-shaped turns
            if mode == "smart" or _re.search(r"\b(who|what|when|where|why|how|tell me|explain|is|are|does|do)\b", user_text, _re.I):
                fact = _search_fact(user_text)
        system_prompt = _CALM_CARD if mode == "calm" else _SYSTEM_PROMPT
        if fact:
            system_prompt += "\n\n[From the web, just now: " + fact + "]"
            _log(f"fact injected: {fact[:80]}")
        # CHEAT: for factual questions, let MiMo answer from the web fact and
        # speak it with Ava (same voice family as Haru's reference), instead of
        # letting the 4B base model improvise.
        if fact and user_text:
            smart = _mimo_answer(user_text, fact)
            if smart:
                smart_wav = _tts_answer(smart, td)
                if smart_wav and smart_wav.exists():
                    return {"ok": True, "audio": base64.b64encode(smart_wav.read_bytes()).decode(),
                            "format":"wav", "text": smart, "user_text": user_text,
                            "fact": fact, "mode":"smart"}
        try:
            from haru_mlx.audio import load_audio, save_audio
            from haru_mlx.session import DuplexConfig, DuplexSession
            import numpy as np
            user = load_audio(str(wav))
            frame_samples = _MODEL.config.frame_samples
            count = max(1, -(-len(user) // frame_samples))
            user = np.pad(user, (0, count * frame_samples - len(user)))
            config = DuplexConfig(
                guidance_scale=1.5,
                temperature=0.4,
                top_k=10,
                max_frames=count + 1,
                seed=0,
            )
            session = DuplexSession(_MODEL, system_prompt, _REFERENCE, config)
            frames = [session.start()]
            for index in range(count - 1):
                frames.append(session.step(user[index * frame_samples:(index + 1) * frame_samples]))
            reply = np.concatenate([frame.audio for frame in frames])
            out = td / "out.wav"
            save_audio(str(out), reply)
            if not out.exists():
                return {"ok": False, "error": "no output audio"}
            audio_out = base64.b64encode(out.read_bytes()).decode()
            text = "".join(f.text for f in frames).strip()
            return {"ok": True, "audio": audio_out, "format": "wav", "text": text, "user_text": user_text, "fact": fact}
        except Exception as e:
            import traceback
            return {"ok": False, "error": f"inference failed: {e}\n{traceback.format_exc()[-500:]}"}


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
            res = _talk(body.get("audio", ""), body.get("mode", "haru"))
            return self._json(res)
        self.send_error(404)

    def log_message(self, fmt, *args):
        sys.stderr.write("haru-face: %s\n" % (fmt % args))


def main():
    load_model_once()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Haru face server → http://127.0.0.1:{PORT}  (root {HERE})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
