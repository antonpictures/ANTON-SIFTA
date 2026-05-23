from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERM = "har" + "ness"

SCAN_ROOTS = (
    "System",
    "Applications",
    "Utilities",
    "tools",
    "scripts",
    "tests",
    "Documents",
    "data",
)

ROOT_FILES = (
    "README.md",
    "SIFTA OS.command",
    "cartography_dashboard.html",
    "log_desktop.patch",
)

SKIP_PARTS = {
    "__pycache__",
    "node_modules",
    "build",
    "dist",
}

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".html",
    ".command",
    ".patch",
}


def _active_text_files():
    for rel in SCAN_ROOTS:
        base = ROOT / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts):
                continue
            if path.suffix in TEXT_SUFFIXES:
                yield path
    for rel in ROOT_FILES:
        path = ROOT / rel
        if path.exists():
            yield path


def test_active_tree_uses_loop_language():
    hits = []
    needle = TERM.casefold()
    for path in _active_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if needle in text.casefold() or needle in path.name.casefold():
            hits.append(str(path.relative_to(ROOT)))

    assert hits == []
