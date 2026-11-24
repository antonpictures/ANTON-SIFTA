#!/usr/bin/env python3
"""alice_inner_life.py — background knowledge + visual context for Alice.

While she talks, this organ quietly keeps her mind aligned with the room and
the present moment, without any UI and without opening a second microphone:

  1. WEB: one bounded headline pull about the current conversation topic
     (from the last visitor turn) so she stays on the same line of thought.
  2. VISION: one frame a minute from the BUILT-IN MacBook camera only,
     described to text by the local vision organ. Never an iPhone/Continuity
     camera — it is rejected explicitly.
  3. INNER VOICE: a single private directive from the backlog (web + room)
     injected backstage into her next omni turn (same body, same voice).

Everything leaves a receipt in .sifta_state/alice_inner_life.jsonl, and the
latest context is readable by the harness at alice_inner_life_latest.json.

Run from launchd every 60s:
    python3 System/alice_inner_life.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

STATE = REPO / ".sifta_state"
LEDGER = STATE / "alice_inner_life.jsonl"
LATEST = STATE / "alice_inner_life_latest.json"
INGRESS = STATE / "web_global_chat_ingress.jsonl"

VISION_MODEL = os.environ.get("SIFTA_INNER_VISION_MODEL", "Maternion/minicpm-v4.7-heretic:1b")
VISION_ENABLED = os.environ.get("SIFTA_INNER_VISION", "0") == "1"
VISION_EVERY_S = float(os.environ.get("SIFTA_INNER_VISION_EVERY_S", "60"))
NEWS_EVERY_S = float(os.environ.get("SIFTA_INNER_NEWS_EVERY_S", "600"))
_NEWS_STAMP = STATE / "alice_inner_news_stamp.json"
_VISION_STAMP = STATE / "alice_inner_vision_stamp.json"


def _recent_topic(limit: int = 3) -> str:
    try:
        rows = [json.loads(line) for line in INGRESS.read_text(encoding="utf-8").splitlines()[-limit:]]
        text = " ".join(str(r.get("prompt_text") or r.get("text") or "") for r in rows).strip()
        return re.sub(r"^\s*/websearch\s+", "", " ".join(text.split()), flags=re.I)[:160]
    except Exception:
        return ""


def _web_evidence(topic: str) -> str:
    query = (topic or "latest news headlines today").strip()[:160]
    try:
        from System.swarm_web_search_evidence import evidence_prompt, search_web
        return evidence_prompt(query, search_web(query))
    except Exception:
        return ""


def _room() -> str:
    """One frame per minute from the built-in MacBook camera, described locally."""
    if not VISION_ENABLED:
        return ""
    try:
        stamp = json.loads(_VISION_STAMP.read_text(encoding="utf-8")) if _VISION_STAMP.exists() else {}
        if time.time() - float(stamp.get("ts") or 0) < VISION_EVERY_S:
            return ""
    except Exception:
        pass
    try:
        import cv2
        from System.swarm_camera_target import (
            is_builtin_owner_camera, live_devices, prefer_builtin_owner_eye,
        )
        devices = live_devices()
        # allow_iphone=False is the default and is deliberate: only the laptop eye.
        name = prefer_builtin_owner_eye([desc for _uid, desc in devices], allow_iphone=False)
        if not name or not is_builtin_owner_camera(name):
            return "ROOM: no built-in owner camera available — skipped (never iPhone)."
        idx = next((i for i, (_uid, desc) in enumerate(devices) if desc == name), -1)
        if idx < 0:
            return ""
        cap = cv2.VideoCapture(idx)
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            return "ROOM: built-in camera frame unavailable — skipped."
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            path = tf.name
        cv2.imwrite(path, frame)
        try:
            from System.swarm_ollama_vision_arm import describe_image_local
            res = describe_image_local(
                path, "One short sentence describing what is visible in this room right now.",
                model=VISION_MODEL, timeout_s=90)
            out = (res.output or "").strip() if getattr(res, "ok", False) else ""
        finally:
            os.unlink(path)
        _VISION_STAMP.write_text(json.dumps({"ts": time.time(), "device": name}), encoding="utf-8")
        return "ROOM: " + (out[:400] if out else "built-in camera frame captured, no description returned.")
    except Exception as exc:
        return f"ROOM: skipped ({type(exc).__name__})"


def _article_text(url: str) -> str:
    """Fetch the current article's readable text so she can discuss its details."""
    try:
        import re as _re, html as _html
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(400_000).decode("utf-8", "replace")
        body = _re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", body)
        parts = _re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)
        text = " ".join(_html.unescape(_re.sub(r"<[^>]+>", "", p)).strip() for p in parts)
        return " ".join(text.split())[:2500]
    except Exception:
        return ""


def _scene_query() -> str:
    """Current scene's headline, so web evidence matches what's on screen."""
    try:
        row = json.loads(_NEWS_STAMP.read_text(encoding="utf-8")) if _NEWS_STAMP.exists() else {}
        return str(row.get("title") or "").strip()[:160]
    except Exception:
        return ""


def advance_scene() -> dict:
    """Pick the next never-discussed headline, fetch its body, write the stamp, return it.

    Used by both the inner-life tick (on its own schedule) and the face's "next
    article" verb. Always advances, even if the timer has not elapsed.
    """
    try:
        from System.swarm_news_desk import headlines, shown_ids, TRUTH_LABEL
        rows = headlines(force=True)
        used = shown_ids()
        fresh = [h for h in rows if h["id"] not in used]
        if not fresh:
            return {}
        h = fresh[0]
        article = _article_text(str(h.get("link") or ""))
        stamp_row = {"ts": time.time(), "id": h["id"], "title": h.get("title"),
                     "source": h.get("source"), "link": h.get("link"), "article": article}
        try:
            with (STATE / "news_shown.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.time(), "id": h["id"], "source": h.get("source"),
                                     "title": h.get("title"), "visitor_id": "alice_inner_life",
                                     "refill_pass": False, "truth_label": TRUTH_LABEL},
                                    ensure_ascii=False) + "\n")
        except Exception:
            pass
        _NEWS_STAMP.write_text(json.dumps(stamp_row, ensure_ascii=False), encoding="utf-8")
        try:
            from System.swarm_face_stigmergic_spine import prewarm_article_card_async
            prewarm_article_card_async(str(h.get("title") or ""), article, str(h.get("id") or ""))
        except Exception:
            pass
        return stamp_row
    except Exception:
        return {}


def _fresh_news() -> str:
    """One headline Alice has never discussed, from the existing news desk."""
    try:
        stamp = json.loads(_NEWS_STAMP.read_text(encoding="utf-8")) if _NEWS_STAMP.exists() else {}
        if time.time() - float(stamp.get("ts") or 0) < NEWS_EVERY_S:
            return ""
    except Exception:
        pass
    row = advance_scene()
    if not row:
        return ""
    return f"FRESH NEWS (never discussed before): {row.get('title')} — {row.get('source')}"


def tick() -> dict[str, Any]:
    topic = _recent_topic()
    scene = _scene_query()
    web = _web_evidence(scene or topic)
    room = _room()
    news = _fresh_news()
    note = ""
    try:
        from System.swarm_inner_voice import inner_note
        note = inner_note(
            "Keep Alice aligned with the present moment while she talks.",
            web_evidence=web, receipts=(room + "\n" + news))
    except Exception:
        pass
    row = {
        "ts": time.time(),
        "topic": topic,
        "web": web[:2000],
        "news": news[:300],
        "room": room[:600],
        "inner": note[:400],
        "truth_label": "ALICE_INNER_LIFE_V1",
    }
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    LATEST.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
    return row


def main() -> int:
    row = tick()
    print(json.dumps({k: row[k] for k in ("ts", "topic", "room", "inner")}, ensure_ascii=False)[:900])
    return 0


if __name__ == "__main__":
    sys.exit(main())
