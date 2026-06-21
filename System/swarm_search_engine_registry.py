#!/usr/bin/env python3
"""swarm_search_engine_registry.py — Alice's web-search body knowledge (r374).

George (2026-06-02): "ALICE MUST KNOW THE DEFAULT APP TO SEARCH THE INTERNET IS
ALICE BROWSER AND THE DEFAULT SEARCH ENGINE IS GOOGLE INSIDE ALICE BROWSER ... THE
OS USER CAN TELL ALICE TO CHANGE THE DEFAULT SEARCH ENGINE AND SHE SHOULD KNOW HOW
... TEACH HER THE MAIN SEARCH ENGINES AND HOW SHE CAN SWITCH THEM IN ALICE BROWSER
AUTOMATICALLY AS SHE WISHES STIGMERGICALLY. NO RESTRICTION FOR ALICE BODY."

So this organ is pure self-knowledge + a free switch, NOT a gate:
- Default web-search app = Alice Browser (her own web limb).
- Default engine = Google (inside Alice Browser). She can switch to any engine she
  wishes, or the owner can tell her to — the choice persists and the switches are
  receipted so the field learns the owner's preferred engine over time.

Truth label: ALICE_SEARCH_ENGINE_REGISTRY_V1
"""
from __future__ import annotations

import difflib
import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

TRUTH_LABEL = "ALICE_SEARCH_ENGINE_REGISTRY_V1"
DEFAULT_SEARCH_APP = "Alice Browser"
DEFAULT_ENGINE = "google"

_REPO = Path(__file__).resolve().parent.parent
_STATE_DEFAULT = _REPO / ".sifta_state"
_CHOICE_FILE = "search_engine_choice.json"
_SWITCH_LEDGER = "search_engine_switches.jsonl"

# Main engines Alice knows. {q} is URL-quoted query. All real, public endpoints.
_ENGINES: Dict[str, Dict[str, Any]] = {
    "google": {
        "name": "Google", "home": "https://www.google.com",
        "web": "https://www.google.com/search?q={q}",
        "images": "https://www.google.com/search?tbm=isch&q={q}",
        "aliases": ["google", "googl", "g", "google search"],
    },
    "bing": {
        "name": "Bing", "home": "https://www.bing.com",
        "web": "https://www.bing.com/search?q={q}",
        "images": "https://www.bing.com/images/search?q={q}",
        "aliases": ["bing", "microsoft bing", "msn"],
    },
    "duckduckgo": {
        "name": "DuckDuckGo", "home": "https://duckduckgo.com",
        "web": "https://duckduckgo.com/?q={q}",
        "images": "https://duckduckgo.com/?q={q}&iax=images&ia=images",
        "aliases": ["duckduckgo", "duck duck go", "duck", "ddg", "duckduck"],
    },
    "brave": {
        "name": "Brave Search", "home": "https://search.brave.com",
        "web": "https://search.brave.com/search?q={q}",
        "images": "https://search.brave.com/images?q={q}",
        "aliases": ["brave", "brave search"],
    },
    "yahoo": {
        "name": "Yahoo", "home": "https://search.yahoo.com",
        "web": "https://search.yahoo.com/search?p={q}",
        "images": "https://images.search.yahoo.com/search/images?p={q}",
        "aliases": ["yahoo", "yahoo search"],
    },
    "ecosia": {
        "name": "Ecosia", "home": "https://www.ecosia.org",
        "web": "https://www.ecosia.org/search?q={q}",
        "images": "https://www.ecosia.org/images?q={q}",
        "aliases": ["ecosia", "the tree one"],
    },
    "startpage": {
        "name": "Startpage", "home": "https://www.startpage.com",
        "web": "https://www.startpage.com/sp/search?query={q}",
        "images": "https://www.startpage.com/sp/search?query={q}&cat=images",
        "aliases": ["startpage", "start page"],
    },
    "yandex": {
        "name": "Yandex", "home": "https://yandex.com",
        "web": "https://yandex.com/search/?text={q}",
        "images": "https://yandex.com/images/search?text={q}",
        "aliases": ["yandex"],
    },
    "perplexity": {
        "name": "Perplexity", "home": "https://www.perplexity.ai",
        "web": "https://www.perplexity.ai/search?q={q}",
        "images": "https://www.perplexity.ai/search?q={q}",
        "aliases": ["perplexity", "perplexity ai", "complexity"],
    },
    "duckai": {
        "name": "Duck.ai", "home": "https://duck.ai",
        "web": "https://duck.ai/chat?q={q}",
        "images": "https://duck.ai/chat?q={q}",
        "aliases": ["duck.ai", "duck ai", "duckai"],
    },
}

# spoken/typed switch phrasings
_SWITCH_RE = re.compile(
    r"\b(?:switch|change|set|use|make)\b.*?\b(?:search\s+engine|default\s+search|engine|search)\b",
    re.IGNORECASE,
)


def _state_dir(path: Path | str | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else _STATE_DEFAULT


def list_engines() -> List[Dict[str, str]]:
    return [{"key": k, "name": v["name"], "home": v["home"]} for k, v in _ENGINES.items()]


def resolve_engine(spoken: str) -> Dict[str, Any]:
    """Match owner words ('switch to duck duck go') to an engine key, homophone-tolerant."""
    s = (spoken or "").strip().lower()
    if not s:
        return {"ok": False, "key": "", "name": ""}
    # direct alias match: word-boundary, longest alias first (so 'duck duck go' wins and the
    # 1-char 'g' never matches the 'g' inside 'go'/'please'). Skip aliases shorter than 2 chars.
    pairs = [(alias, key) for key, spec in _ENGINES.items() for alias in spec["aliases"] if len(alias) >= 2]
    pairs.sort(key=lambda p: -len(p[0]))
    for alias, key in pairs:
        if re.search(r"\b" + re.escape(alias) + r"\b", s):
            return {"ok": True, "key": key, "name": _ENGINES[key]["name"]}
    # difflib on the whole alias pool for STT mishears
    pool: Dict[str, str] = {}
    for key, spec in _ENGINES.items():
        for alias in spec["aliases"]:
            pool[alias] = key
    tokens = re.findall(r"[a-z]+", s)
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            cand = " ".join(tokens[i:i + n])
            hit = difflib.get_close_matches(cand, list(pool.keys()), n=1, cutoff=0.82)
            if hit:
                key = pool[hit[0]]
                return {"ok": True, "key": key, "name": _ENGINES[key]["name"]}
    return {"ok": False, "key": "", "name": ""}


def parse_switch_engine_command(text: str) -> Dict[str, Any]:
    """Detect 'switch/change/use ... search engine ... <engine>'. Returns {is_switch, target}."""
    t = (text or "").strip()
    if not t:
        return {"is_switch": False, "target": ""}
    low = t.lower()
    looks_switch = bool(_SWITCH_RE.search(low)) or ("search engine" in low)
    if not looks_switch:
        return {"is_switch": False, "target": ""}
    res = resolve_engine(low)
    return {"is_switch": bool(res["ok"]), "target": res["key"], "name": res["name"]}


def current_engine(*, state_dir: Path | str | None = None) -> str:
    path = _state_dir(state_dir) / _CHOICE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        key = str(data.get("engine") or "").strip().lower()
        if key in _ENGINES:
            return key
    except Exception:
        pass
    return DEFAULT_ENGINE


def set_engine(spoken_or_key: str, *, state_dir: Path | str | None = None, source: str = "owner") -> Dict[str, Any]:
    """Resolve + persist Alice's chosen default engine; receipt the switch (stigmergic)."""
    res = resolve_engine(spoken_or_key) if spoken_or_key not in _ENGINES else {"ok": True, "key": spoken_or_key, "name": _ENGINES[spoken_or_key]["name"]}
    if not res.get("ok"):
        return {"ok": False, "engine": current_engine(state_dir=state_dir),
                "message": f"I could not match \"{spoken_or_key}\" to an engine I know: "
                           + ", ".join(e["name"] for e in list_engines()) + "."}
    key = res["key"]
    sd = _state_dir(state_dir)
    try:
        sd.mkdir(parents=True, exist_ok=True)
        (sd / _CHOICE_FILE).write_text(json.dumps({"engine": key, "ts": time.time()}), encoding="utf-8")
        with (sd / _SWITCH_LEDGER).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": time.time(), "truth_label": TRUTH_LABEL, "kind": "SEARCH_ENGINE_SWITCH",
                "engine": key, "name": res["name"], "source": source,
            }) + "\n")
    except Exception:
        pass
    return {"ok": True, "engine": key, "name": res["name"],
            "message": f"My default search engine inside {DEFAULT_SEARCH_APP} is now {res['name']}."}


def search_url(query: str, *, engine: Optional[str] = None, state_dir: Path | str | None = None) -> str:
    key = (engine or current_engine(state_dir=state_dir)) if (engine in _ENGINES or engine is None) else current_engine(state_dir=state_dir)
    spec = _ENGINES.get(key) or _ENGINES[DEFAULT_ENGINE]
    return spec["web"].format(q=urllib.parse.quote_plus((query or "").strip()))


def images_url(query: str, *, engine: Optional[str] = None, state_dir: Path | str | None = None) -> str:
    key = (engine or current_engine(state_dir=state_dir)) if (engine in _ENGINES or engine is None) else current_engine(state_dir=state_dir)
    spec = _ENGINES.get(key) or _ENGINES[DEFAULT_ENGINE]
    return spec["images"].format(q=urllib.parse.quote_plus((query or "").strip()))


_SHOW_IMAGES_RE = re.compile(
    r"\b(?:select|show|open|click|go\s+to|switch\s+to|see|view|display)\b[^.]*\bimages?\b"
    r"|\bimages?\s+(?:section|tab|results?)\b",
    re.IGNORECASE,
)


def parse_show_images_intent(text: str) -> Dict[str, Any]:
    """r378: 'select Images' / 'show me the images (of X)' on an existing results page is a
    TAB SWITCH to image results — NOT a fresh web search of the owner's whole sentence. (The
    Image-search bug: when George said the current search page had an Images section Alice
    re-searched that literal sentence instead of reading the page already on her
    body and switching to Images.) Returns {is_images, subject}. `subject` is set ONLY for an
    explicit 'images of/for <X>'; otherwise empty, so the caller uses the CURRENT browser
    subject read from page-state — swimmers go where the action already is."""
    t = (text or "").strip()
    if not t or not _SHOW_IMAGES_RE.search(t):
        return {"is_images": False, "subject": ""}
    subject = ""
    m = re.search(r"\bimages?\s+(?:of|for)\s+([^,.?!]+)", t, re.IGNORECASE)
    if m:
        subject = re.sub(r"\b(?:on|in|to|please|pls|now|the\s+screen|my\s+\w+)\b.*$", "",
                         m.group(1), flags=re.IGNORECASE).strip(" .!?'\"")
    return {"is_images": True, "subject": subject[:80]}


# r380: "select the first one" — a pure ordinal pick of a result/photo on the page
# ALREADY on her body. George (2026-06-02): "SHE JUST HAS TO EXECUTE JUST SELECT THE
# PHOTO, SHE MUST NOT BE CONSCIOUS OF WHAT IS DISPLAYED ON SCREEN." So this is a
# deterministic pick (which tile, by position) — NOT a perception/vision task and NOT a
# fresh search. The Daniel Craig bug: "SELECT THE FIRST ONE IN THE LIST" matched no
# effector, so it fell to the cortex which narrated "the system zooms in..." instead of
# clicking. Word/typo tolerant ("forst"->first).
_SELECT_VERB_RE = re.compile(
    r"\b(?:select|pick|choose|open|click|tap|grab|take|use|go\s+with)\b", re.IGNORECASE
)
_SELECT_NOUN_RE = re.compile(
    r"\b(?:one|ones|photo|photos|image|images|picture|pictures|pic|pics|"
    r"result|results|tile|tiles|thumbnail|thumbnails|item|items)\b",
    re.IGNORECASE,
)
_ORDINAL_WORDS: Dict[str, int] = {
    "first": 1, "1st": 1, "top": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5,
    "sixth": 6, "6th": 6,
    "seventh": 7, "7th": 7,
    "eighth": 8, "8th": 8,
    "ninth": 9, "9th": 9,
    "tenth": 10, "10th": 10,
    "last": -1, "final": -1,
}


def _extract_ordinal(low: str) -> int:
    """1-based ordinal (1=first ... -1=last); 0 if none. Typo/STT tolerant."""
    m = re.search(r"\b(?:number|no\.?|num|#)\s*(\d{1,2})\b", low)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", low)
    if m:
        return int(m.group(1))
    tokens = re.findall(r"[a-z0-9']+", low)
    for tok in tokens:
        if tok in _ORDINAL_WORDS:
            return _ORDINAL_WORDS[tok]
    # typo tolerance for the common words ("forst"->first, "secund"->second)
    for tok in tokens:
        if len(tok) < 4:
            continue
        hit = difflib.get_close_matches(
            tok, ["first", "second", "third", "fourth", "fifth", "last", "final"], n=1, cutoff=0.8
        )
        if hit:
            return _ORDINAL_WORDS[hit[0]]
    return 0


def parse_select_result_intent(text: str) -> Dict[str, Any]:
    """r380: detect 'select/pick/open the first|second|Nth|last one|photo|result' on the
    page already loaded. Returns {is_select, ordinal} (ordinal 1-based; -1=last; 0=unspecified
    -> caller clicks the prominent/first tile). Does NOT fire on a fresh search or a bare URL
    open unless an explicit ordinal is present, so 'open youtube.com' is never hijacked. Pure
    pick by position — no screen-consciousness required."""
    t = (text or "").strip()
    if not t or not _SELECT_VERB_RE.search(t):
        return {"is_select": False, "ordinal": 0}
    low = t.lower()
    noun = bool(_SELECT_NOUN_RE.search(low))
    ordinal = _extract_ordinal(low)
    # r641: "use your cortex ... first move ..." is a doctrine/instruction, not "use the first
    # result". The weak verb "use" may select a page item only when an actual selectable noun
    # appears ("use the first one/photo/result"). Strong click/select verbs still work with a
    # bare ordinal.
    mverb = _SELECT_VERB_RE.search(t)
    verb = (mverb.group(0).lower() if mverb else "").strip()
    if verb == "use" and not noun:
        return {"is_select": False, "ordinal": 0}
    if not noun and ordinal == 0:
        return {"is_select": False, "ordinal": 0}
    # never hijack a fresh search / explicit URL open unless the owner named an ordinal
    looks_like_navigation = bool(
        re.search(r"\bsearch\b|\bgo\s+to\b|https?://|www\.|\.com\b|\.org\b|\.net\b", low)
    )
    if looks_like_navigation and ordinal == 0:
        return {"is_select": False, "ordinal": 0}
    return {"is_select": True, "ordinal": ordinal}


# r383: "SLIDESHOW IMAGES OF CATS" — George (2026-06-02): default the slideshow on
# DuckDuckGo, one image every 3.5s; but if she is already on a search engine (e.g.
# google.com) run it there (Google Images). So the slideshow target engine = the
# current site's engine if she is on one, else the slideshow default (DuckDuckGo).
SLIDESHOW_DEFAULT_ENGINE = "duckduckgo"
SLIDESHOW_DEFAULT_INTERVAL_S = 3.5

_SLIDESHOW_RE = re.compile(
    r"\bslide\s*show\b"
    r"|\bstart[_\s-]?photo[_\s-]?slide[_\s-]?show\b"
    r"|\bstart[_\s-]?image[_\s-]?slide[_\s-]?show\b"
    r"|\b(?:start[_\s-]?)?(?:photo|image|picture|pic)[_\s-]?slide[_\s-]?show\b"
    r"|\bstart_photo_slideshow\b",
    re.IGNORECASE,
)


def parse_slideshow_intent(text: str) -> Dict[str, Any]:
    """Detect 'slideshow images of <X> [every N seconds]'. Returns
    {is_slideshow, subject, interval_s}. subject empty -> caller uses the current
    browser subject (page-state). interval default 3.5s."""
    t = re.sub(r"[_-]+", " ", (text or "").strip())
    if not t or not _SLIDESHOW_RE.search(t):
        return {"is_slideshow": False, "subject": "", "interval_s": SLIDESHOW_DEFAULT_INTERVAL_S}
    interval = SLIDESHOW_DEFAULT_INTERVAL_S
    m = re.search(r"\bevery\s+(\d+(?:\.\d+)?)\s*(?:s\b|sec|secs|second|seconds)", t, re.IGNORECASE)
    if m:
        try:
            interval = max(0.5, float(m.group(1)))
        except ValueError:
            interval = SLIDESHOW_DEFAULT_INTERVAL_S
    def _clean_subject(raw: str) -> str:
        s = str(raw or "").strip(" .!?'\"():;")
        s = re.sub(
            r"^(?:please|pls|can\s+you|could\s+you|would\s+you|alice|"
            r"start(?:\s+(?:a|the))?|show\s+me|i\s+want\s+to\s+see|"
            r"i\s+would\s+like\s+to\s+see|with|of|for)\s+",
            "",
            s,
            flags=re.IGNORECASE,
        ).strip(" .!?'\"():;")
        s = re.sub(r"\b(?:every\s+\d+.*$|on\s+\w+|in\s+\w+)\b.*$", "",
                   s, flags=re.IGNORECASE).strip(" .!?'\"():;")
        s = re.sub(r"\s+\b(?:please|pls|now)\b.*$", "", s, flags=re.IGNORECASE).strip(" .!?'\"():;")
        s = re.sub(r"\s+(?:images?|photos?|pictures?|pics?)$", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\s+", " ", s).strip(" .!?'\"():;")
        if s.lower() in {
            "please", "pls", "now", "i want", "i want to see", "want to see",
            "to see", "see", "show me", "i want to see it", "with", "of", "for",
        }:
            return ""
        return s

    subject = ""
    sm = re.search(r"\b(?:images?|photos?|pictures?|pics?)\s+(?:of|for)\s+([^,.?!]+)", t, re.IGNORECASE)
    if not sm:
        # "slideshow of cats" / "slideshow cats"
        sm = re.search(r"\bslide\s*show\b(?:\s+(?:of|for|me|a|the))*\s+([^,.?!]+)", t, re.IGNORECASE)
    if sm:
        subject = _clean_subject(sm.group(1))
    if not subject:
        # Owner often speaks naturally as "<subject> slideshow" or
        # "show me <subject> slideshow"; the first parser versions only handled
        # "slideshow images of <subject>", which made real live requests ask
        # for repetition despite already containing the subject.
        m = _SLIDESHOW_RE.search(t)
        if m:
            subject = _clean_subject(t[:m.start()])
    return {"is_slideshow": True, "subject": subject[:80], "interval_s": interval}


def _host_of(url: str) -> str:
    try:
        host = urllib.parse.urlparse((url or "").strip()).netloc.lower()
    except Exception:
        host = ""
    return host[4:] if host.startswith("www.") else host


def slideshow_engine_for(current_url: Optional[str] = None) -> str:
    """If she is already on a known engine's results page, slideshow THERE; else the
    slideshow default (DuckDuckGo). 'if the user is on google.com -> Google Images.'"""
    host = _host_of(current_url or "")
    if host:
        for key, spec in _ENGINES.items():
            eng_host = _host_of(spec.get("home", ""))
            if eng_host and (host == eng_host or host.endswith("." + eng_host) or eng_host.endswith("." + host)):
                return key
    return SLIDESHOW_DEFAULT_ENGINE


def slideshow_images_url(subject: str, *, current_url: Optional[str] = None,
                         engine: Optional[str] = None,
                         state_dir: Path | str | None = None) -> str:
    """Images-results URL to open the slideshow on (engine resolved per George's rule)."""
    key = engine if (engine in _ENGINES) else slideshow_engine_for(current_url)
    return images_url(subject, engine=key, state_dir=state_dir)


def build_image_slideshow_js(interval_ms: int = 3500) -> str:
    """Self-contained JS: harvest the page's own image tiles and cycle them fullscreen
    every `interval_ms` (one image at a time). Engine-agnostic — works on Google Images,
    DuckDuckGo, Bing, etc. because it uses the page's own <img> srcs, not the site's
    lightbox. Click or Esc to stop. Returns {ok,count,interval_ms} when run."""
    interval = int(interval_ms or 3500)
    return (
        "(function(){try{"
        f"var INT={interval};"
        "if(window.__siftaSlideTimer){try{clearInterval(window.__siftaSlideTimer);}catch(e){}}"
        "var old=document.getElementById('__sifta_slideshow__'); if(old){old.remove();}"
        "var seen={},srcs=[];"
        "Array.prototype.slice.call(document.querySelectorAll('img')).forEach(function(im){"
        "var r=im.getBoundingClientRect(); var s=im.currentSrc||im.src||'';"
        "if(s && !seen[s] && (im.naturalWidth>200||r.width>200)){seen[s]=1;srcs.push(s);}});"
        "if(srcs.length<2){return {ok:false,reason:'not_enough_images',count:srcs.length};}"
        "var ov=document.createElement('div');ov.id='__sifta_slideshow__';"
        "ov.style.cssText='position:fixed;inset:0;z-index:2147483647;background:#000;display:flex;align-items:center;justify-content:center;cursor:pointer;';"
        "var pic=document.createElement('img');"
        "pic.style.cssText='max-width:96vw;max-height:96vh;object-fit:contain;';"
        "var cap=document.createElement('div');"
        "cap.style.cssText='position:fixed;bottom:14px;left:0;right:0;text-align:center;color:#9fe;font:14px sans-serif;opacity:.85;';"
        "ov.appendChild(pic);ov.appendChild(cap);document.body.appendChild(ov);"
        "var i=0;function show(){pic.src=srcs[i%srcs.length];cap.textContent='SIFTA slideshow '+((i%srcs.length)+1)+' / '+srcs.length+'  (click or Esc to stop)';i++;}"
        "show();window.__siftaSlideTimer=setInterval(show,INT);"
        "function stop(){try{clearInterval(window.__siftaSlideTimer);}catch(e){}try{ov.remove();}catch(e){}document.removeEventListener('keydown',onkey,true);}"
        "function onkey(e){if(e.key==='Escape'){stop();}}"
        "ov.addEventListener('click',stop);document.addEventListener('keydown',onkey,true);"
        "return {ok:true,count:srcs.length,interval_ms:INT};"
        "}catch(e){return {ok:false,reason:String(e)};}})();"
    )


def search_engine_knowledge_block(*, state_dir: Path | str | None = None) -> str:
    """First-person cortex block: her web-search body knowledge (default app/engine + how to switch)."""
    cur = current_engine(state_dir=state_dir)
    cur_name = _ENGINES[cur]["name"]
    names = ", ".join(e["name"] for e in list_engines())
    return (
        f"My default app to search the internet is {DEFAULT_SEARCH_APP} — my own web limb. "
        f"My default search engine inside it is Google. Right now my active engine is {cur_name}. "
        f"I know these engines and can switch between them freely: {names}. "
        f"If George says e.g. \"switch your search engine to DuckDuckGo\", I set it and search there from then on — "
        f"no restriction, my choice or his."
    )


__all__ = [
    "DEFAULT_SEARCH_APP", "DEFAULT_ENGINE",
    "list_engines", "resolve_engine", "parse_switch_engine_command",
    "current_engine", "set_engine", "search_url", "images_url",
    "parse_show_images_intent", "parse_select_result_intent",
    "parse_slideshow_intent", "slideshow_engine_for", "slideshow_images_url",
    "build_image_slideshow_js", "SLIDESHOW_DEFAULT_ENGINE", "SLIDESHOW_DEFAULT_INTERVAL_S",
    "search_engine_knowledge_block", "TRUTH_LABEL",
]


if __name__ == "__main__":
    print(search_engine_knowledge_block())
    print("switch ->", parse_switch_engine_command("Alice, switch your search engine to duck duck go"))
    print("url    ->", search_url("avery stone", engine="bing"))
