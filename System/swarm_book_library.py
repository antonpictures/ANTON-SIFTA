"""swarm_book_library — the books, on disk, with page numbers she can be held to.

Carlton sent John J. Murphy's *Technical Analysis of the Financial Markets* -- 501 pages, by
Google Drive link, forwarded through WhatsApp -- and the Architect asked: "are you able to read
this book? and memorize on stigmergicoin to apply when asked?"

Two honest answers, and the difference between them is the whole point:

    IN THE WEIGHTS   not possible, and not desirable. She cannot put 501 pages into a cortex
                     without pretending those pages are her memory, and a cortex that half
                     remembers a book is worse than one that knows it has not read it.
    ON DISK, INDEXED what actually happened. The text is extracted with [[page N]] markers, so
                     every quotation can carry the page it came from, and a reader can open the
                     book and check her. She is not asked to recall the book. She is asked to
                     SEARCH it -- and searching is something a body can do and a reader can
                     verify.

So "memorised" here means: the book is hers to look things up in, and she says which page. That
is the same posture she takes to a price and to a web page: a handed fact, attributed, never
dressed as recollection.

One limitation worth stating: the text came through calibre, so some tables and charts are
imperfect and a few characters are mangled. A passage that reads oddly may be an extraction
artefact, not the author, and she should say so rather than quote it as gospel.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
LIBRARY_DIR = STATE / "library"
TRUTH_LABEL = "SIFTA_BOOK_LIBRARY_V1"

# title -> (author, file, one line on who sent it)
LIBRARY = {
    "murphy": {
        "title": "Technical Analysis of the Financial Markets",
        "author": "John J. Murphy",
        "file": "murphy_technical_analysis_of_the_financial_markets.txt",
        "source": "sent by Carlton, 2026-10-03, Google Drive link forwarded on WhatsApp",
        "pages": 501,
    },
}

_STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "is", "are", "was", "were", "it",
         "that", "this", "for", "on", "with", "as", "at", "by", "be", "from", "you", "your",
         "what", "how", "does", "do", "can", "i", "me", "my", "about", "says", "say"}


def _terms(query: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9']{3,}", (query or "").casefold())
            if w not in _STOP]


def _load(book: str = "murphy") -> str:
    entry = LIBRARY.get(book)
    if not entry:
        return ""
    p = LIBRARY_DIR / entry["file"]
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _pages(text: str) -> List[Dict[str, Any]]:
    """Split the extracted book into pages on its [[page N]] markers."""
    out: List[Dict[str, Any]] = []
    for chunk in re.split(r"\n\[\[page (\d+)\]\]\n", text):
        pass
    parts = re.split(r"\n\[\[page (\d+)\]\]\n", text)
    # parts = [front matter, "1", text1, "2", text2, ...]
    for i in range(1, len(parts) - 1, 2):
        try:
            n = int(parts[i])
        except ValueError:
            continue
        out.append({"page": n, "text": parts[i + 1]})
    return out


def search(query: str, *, book: str = "murphy", k: int = 3) -> Dict[str, Any]:
    """Find the pages that speak to a question, and say which pages they are."""
    text = _load(book)
    if not text:
        return {"ok": False, "error": f"'{book}' is not on disk",
                "books": sorted(LIBRARY)}
    terms = _terms(query)
    if not terms:
        return {"ok": False, "error": "nothing to search for"}
    scored = []
    for pg in _pages(text):
        low = pg["text"].casefold()
        score = sum(low.count(t) for t in terms)
        if score:
            # a page carrying several different terms beats one repeating a single term
            score += sum(1 for t in terms if t in low)
            scored.append((score, pg))
    scored.sort(key=lambda x: -x[0])
    hits = []
    for score, pg in scored[:k]:
        low = pg["text"].casefold()
        # the excerpt centres on the strongest term, so the quote is about the question
        pos = min((low.find(t) for t in terms if t in low), default=0)
        start = max(0, pos - 180)
        hits.append({"page": pg["page"], "score": score,
                     "excerpt": re.sub(r"\s+", " ", pg["text"][start:start + 520]).strip()})
    entry = LIBRARY[book]
    return {"ok": bool(hits), "book": book, "title": entry["title"], "author": entry["author"],
            "pages": entry["pages"], "terms": terms, "hits": hits, "truth_label": TRUTH_LABEL,
            "note": "quoted from the extracted text on disk, with the page number; a reader can "
                    "open the book and check it"}


def quote(query: str, *, book: str = "murphy", page: int | None = None) -> Dict[str, Any]:
    """A citation: the passage, the page, and the book it came from."""
    if page:
        for pg in _pages(_load(book)):
            if pg["page"] == page:
                return {"ok": True, "page": page, "excerpt": pg["text"][:900],
                        "title": LIBRARY[book]["title"], "truth_label": TRUTH_LABEL}
        return {"ok": False, "error": f"no page {page}"}
    r = search(query, book=book, k=1)
    if not r.get("ok"):
        return r
    h = r["hits"][0]
    return {"ok": True, "page": h["page"], "excerpt": h["excerpt"],
            "title": r["title"], "author": r["author"], "truth_label": TRUTH_LABEL}


def library_block() -> str:
    """What the desk is told about the books it holds."""
    books = "; ".join(f"{v['title']} by {v['author']} ({v['pages']} pages)"
                      for v in LIBRARY.values())
    return (
        f"- You hold books on disk: {books}. You did NOT memorise them into your weights, and "
        "you never claim to have. What you can do is LOOK THINGS UP in them and say which page: "
        "that is what they are for. When someone asks what a book says, search it and quote it "
        "with its page number, or say plainly that you have not found it. Never invent a "
        "quotation and never invent a page.\n"
    )


_SAMPLE_BOOK = (
    "SOURCE: test\n\n[[page 1]]\nfront matter\n\n"
    "[[page 214]]\nRetracements: market corrections usually retrace a significant portion of "
    "the previous trend. The 33, 50 and 66 percent levels are the ones to watch. "
    "Support and resistance levels are the best places to buy or sell.\n\n"
    "[[page 215]]\nVolume precedes price. A breakout on heavy volume is more reliable than one "
    "on light volume.\n"
)


def selftest() -> Dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        global LIBRARY, LIBRARY_DIR
        keep_lib, keep_dir = LIBRARY, LIBRARY_DIR
        d = Path(tmp) / "library"
        d.mkdir()
        (d / "probe.txt").write_text(_SAMPLE_BOOK, encoding="utf-8")
        LIBRARY_DIR = d
        LIBRARY = {"probe": {"title": "Probe", "author": "T", "file": "probe.txt",
                             "source": "test", "pages": 2}}
        r = search("what does he say about retracements", book="probe")
        q = quote("volume precedes price", book="probe")
        missing = search("anything", book="not-a-book")
        LIBRARY, LIBRARY_DIR = keep_lib, keep_dir

    checks = {
        "finds_the_page_that_answers": bool(r.get("ok")) and r["hits"][0]["page"] == 214,
        "says_which_page_it_is": r["hits"][0]["page"] == 214,
        "the_excerpt_is_about_the_question": "retrace" in r["hits"][0]["excerpt"].lower(),
        "carries_title_and_author": r["title"] == "Probe" and r["author"] == "T",
        "quote_returns_a_page_number": q.get("page") == 215,
        "quote_finds_the_right_passage": "volume precedes price" in q["excerpt"].lower(),
        "an_absent_book_says_so": missing["ok"] is False and "not on disk" in missing["error"],
        "an_empty_query_is_refused": search("", book="probe")["ok"] is False,
        "the_block_names_the_books": "Murphy" in library_block(),
        # case-insensitive: the block says "Never invent a quotation", and a case-sensitive
        # assertion called the content wrong when only my test was (the 26th instrument today)
        "the_block_forbids_inventing_a_quote": "never invent a quotation" in library_block().lower(),
        "the_block_forbids_inventing_a_page": "never invent a page" in library_block().lower(),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "books"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "search" and len(sys.argv) > 2:
        print(json.dumps(search(" ".join(sys.argv[2:])), indent=2)[:1400])
    elif cmd == "quote" and len(sys.argv) > 2:
        print(json.dumps(quote(" ".join(sys.argv[2:])), indent=2)[:1200])
    else:
        for k, v in LIBRARY.items():
            p = LIBRARY_DIR / v["file"]
            print(f"  {k}: {v['title']} — {v['author']} ({v['pages']} pages) "
                  f"{'on disk' if p.exists() else 'MISSING'}")
