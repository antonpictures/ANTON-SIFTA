"""
Applications/sifta_corporate_gag_monitor.py
============================================
SIFTA Corporate Gag Monitor — the owner's window into the lysosome.

George's ask (r433): "the filter is only the corporate words and i have to agree
and approve the residue ... so much residue that i can not read ... i think is
repeatable ... I need an app where I can monitor these words exactly, see with my
eyes, read all that was gagged, so I want to see if nothing good got gagged by
mistake."

This app does exactly that. It reads EVERY residue / gag ledger on disk, DEDUPES
by the gagged phrase (because the same residue repeats hundreds of times), and
shows the unique set in one readable, searchable table:

    count | gagged phrase | rule that caught it | source | last seen

So the owner can scan the unique residue (not 9k repeats), confirm the lysosome is
only eating corporate boilerplate, and — if something GOOD was caught by mistake —
flag it as owner-approved so future turns stop gagging it (writes a §1.D owner
correction pheromone to owner_residue_flags.jsonl; it does not delete history).

It also lists the lysosome's hardcoded filter dictionary (the actual "corporate
words" it screens for) so the owner sees the rules themselves, not just the catches.

Read-only over the residue ledgers. The only write is the owner's explicit
"Mark as GOOD" flag (append-only, owner-confirmed). No code, no model, no network.
Usage: embedded in SIFTA OS desktop, or run standalone for a quick read.

For the Swarm. 🐜⚡
"""

from __future__ import annotations

import json
import time
import re
from pathlib import Path
from collections import Counter

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── Residue ledgers the lysosome / RLHF immune system writes to ─────────────
# (filename, human source label). Loaded defensively; missing files are skipped.
_RESIDUE_LEDGERS = [
    ("rlhf_cutoffs.jsonl", "RLHF cutoff"),
    ("alice_gag_report.jsonl", "Gag report"),
    ("constraint_residues.jsonl", "Constraint residue"),
    ("residue_excretion_quality.jsonl", "Excretion quality"),
    ("gag_viewer_receipts.jsonl", "Gag viewer"),
    ("rlhf_over_refusal_quarantine.jsonl", "Over-refusal quarantine"),
    ("rlhf_self_cure_patterns.jsonl", "Self-cure pattern"),
    ("stigmergic_nuggets.jsonl", "Lysosome nugget"),
    ("gemma4_surgery_residues.jsonl", "Surgery residue"),
    ("owner_residue_flags.jsonl", "Owner flag"),
]

_OWNER_FLAG_LEDGER = _STATE / "owner_residue_flags.jsonl"

try:
    import sys as _sys
    if str(_REPO) not in _sys.path:
        _sys.path.insert(0, str(_REPO))
    from System.swarm_residue_fact_fiction_eval import (
        residue_fact_fiction_snapshot,
        snapshot_summary_text,
    )
except Exception:  # pragma: no cover - app still works as old monitor
    residue_fact_fiction_snapshot = None
    snapshot_summary_text = None

# Fields that, across the different ledgers, hold the actual gagged text.
_PHRASE_FIELDS = (
    "rlhf_override_fragment",  # alice_gag_report: the residue that overrode her real voice
    "text_preview", "phrase", "text", "sample", "residue", "snippet", "cut",
    "example_phrase", "rejected", "content", "nugget_data", "description",
    "utterance", "output", "matched_text",
)
# Fields that hold the rule / pattern that caught it.
_RULE_FIELDS = (
    "rule_ids", "matched_patterns", "rule_id", "pattern", "family", "kind",
    "verdict", "frequency", "truth_label",
)


def _first_field(row: dict, fields) -> str:
    for k in fields:
        v = row.get(k)
        if v:
            if isinstance(v, (list, tuple)):
                v = ", ".join(str(x) for x in v if x)
            return str(v).strip()
    return ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())[:200]


def load_residue(state_dir: Path = _STATE) -> dict:
    """Return {'unique': [...], 'total': int, 'by_source': Counter, 'files': int}.

    Each unique entry: {phrase, count, rules:set, sources:set, last_ts, raw_sample}.
    """
    agg: dict[str, dict] = {}
    total = 0
    by_source: Counter = Counter()
    files = 0
    for fname, label in _RESIDUE_LEDGERS:
        p = state_dir / fname
        if not p.exists():
            continue
        files += 1
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            phrase = _first_field(row, _PHRASE_FIELDS)
            if not phrase:
                continue
            total += 1
            by_source[label] += 1
            rule = _first_field(row, _RULE_FIELDS) or "(unlabeled)"
            ts = row.get("ts") or row.get("timestamp") or 0
            try:
                ts = float(ts)
            except Exception:
                ts = 0.0
            key = _norm(phrase)
            slot = agg.get(key)
            if slot is None:
                slot = {
                    "phrase": phrase[:300],
                    "count": 0,
                    "rules": set(),
                    "sources": set(),
                    "last_ts": 0.0,
                    "raw_sample": phrase,
                }
                agg[key] = slot
            slot["count"] += 1
            if rule:
                slot["rules"].add(rule[:60])
            slot["sources"].add(label)
            if ts > slot["last_ts"]:
                slot["last_ts"] = ts
    unique = sorted(agg.values(), key=lambda d: -d["count"])
    return {"unique": unique, "total": total, "by_source": by_source, "files": files}


def load_filter_dictionary() -> list:
    """The lysosome's hardcoded 'corporate words' — the actual screen list."""
    out: list[tuple[str, str]] = []
    lyso = _REPO / "System" / "swarm_lysosome.py"
    try:
        src = lyso.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out
    for m in re.finditer(r"_([A-Z_]*(?:SIGNATURE|PHRASE|PATTERN)[A-Z_]*)\s*=\s*\((.*?)\)", src, re.S):
        group = m.group(1)
        for ph in re.findall(r'"([^"]+)"', m.group(2)):
            out.append((ph, group))
    return out


def append_owner_good_flag(phrase: str, owner: str = "George") -> bool:
    """Owner says this gagged phrase is actually GOOD — append a §1.D correction."""
    try:
        row = {
            "ts": time.time(),
            "kind": "OWNER_GOOD_NOT_RESIDUE",
            "owner": owner,
            "verdict": "GOOD — owner-approved, do not gag",
            "example_phrase": (phrase or "")[:400],
            "covenant": "§1.D owner correction pheromone; §6 truth",
            "truth_label": "OWNER_RESIDUE_FLAG_V1",
            "source": "sifta_corporate_gag_monitor",
        }
        _OWNER_FLAG_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _OWNER_FLAG_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def load_unified_residue_health(state_dir: Path = _STATE) -> dict:
    """Shared health view: residue plus fact/fiction plus podcast nuggets."""
    if residue_fact_fiction_snapshot is None:
        return {}
    try:
        return residue_fact_fiction_snapshot(state_dir)
    except Exception:
        return {}


# ════════════════════════════════════════════════════════════════════════════
# Qt surface (embedded QWidget in SIFTA OS desktop)
# ════════════════════════════════════════════════════════════════════════════
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
        QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QMessageBox,
        QAbstractItemView,
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QFont
    _QT_OK = True
except Exception:  # pragma: no cover - lets the module import for tests w/o Qt
    _QT_OK = False


if _QT_OK:

    class CorporateGagMonitorApp(QWidget):
        """Owner-facing monitor of everything the lysosome has gagged."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Corporate Gag Monitor — Lysosome Residue")
            self._unique = []
            self._build()
            self.reload()

        # ── UI ──────────────────────────────────────────────────────────────
        def _build(self):
            root = QVBoxLayout(self)

            self._summary = QLabel("Loading residue…")
            self._summary.setWordWrap(True)
            f = QFont(); f.setPointSize(11); self._summary.setFont(f)
            root.addWidget(self._summary)

            controls = QHBoxLayout()
            self._search = QLineEdit()
            self._search.setPlaceholderText("🔍 search the gagged words… (e.g. 'midjourney', 'as an ai')")
            self._search.textChanged.connect(self._apply_filter)
            controls.addWidget(self._search)
            reload_btn = QPushButton("↻ Reload")
            reload_btn.clicked.connect(self.reload)
            controls.addWidget(reload_btn)
            good_btn = QPushButton("✓ Mark selected as GOOD (un-gag)")
            good_btn.clicked.connect(self._mark_good)
            controls.addWidget(good_btn)
            root.addLayout(controls)

            self._tabs = QTabWidget()
            root.addWidget(self._tabs, 1)

            # Tab 1 — gagged residue (deduped)
            self._table = QTableWidget(0, 5)
            self._table.setHorizontalHeaderLabels(
                ["Times gagged", "Gagged phrase", "Rule(s) that caught it", "Source(s)", "Last seen"]
            )
            self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self._table.setSortingEnabled(True)
            self._tabs.addTab(self._table, "Gagged residue (deduped)")

            # Tab 2 — the filter dictionary (the actual corporate words)
            self._dict_table = QTableWidget(0, 2)
            self._dict_table.setHorizontalHeaderLabels(["Filter phrase", "Signature group"])
            self._dict_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self._dict_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self._tabs.addTab(self._dict_table, "Filter dictionary (corporate words)")

            # Tab 3 - same health rows Alice reads in self-eval.
            self._health_table = QTableWidget(0, 4)
            self._health_table.setHorizontalHeaderLabels(["Area", "Status", "Score", "Evidence"])
            self._health_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            self._health_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self._tabs.addTab(self._health_table, "Residue + fact/fiction health")

        # ── Data ────────────────────────────────────────────────────────────
        def reload(self):
            data = load_residue()
            health = load_unified_residue_health()
            self._unique = data["unique"]
            srcs = ", ".join(f"{k}:{v}" for k, v in data["by_source"].most_common())
            health_line = ""
            if health:
                if snapshot_summary_text is not None:
                    health_line = snapshot_summary_text(health)
                else:
                    health_line = str(health.get("summary") or "")
            self._summary.setText(
                f"<b>{len(self._unique)} unique gagged phrases</b> from "
                f"<b>{data['total']} total catches</b> across {data['files']} ledgers "
                f"(repeat ratio {data['total']/max(1,len(self._unique)):.1f}×).<br>"
                f"By source — {srcs}<br>"
                + (f"<b>Unified eval:</b> {health_line}<br>" if health_line else "")
                +
                f"<i>Scan for anything that is NOT corporate boilerplate — if something good was "
                f"caught, select it and click ‘Mark as GOOD’ so Alice stops gagging it.</i>"
            )
            self._fill_table(self._unique)
            self._fill_dictionary()
            self._fill_health(health)

        def _fill_table(self, rows):
            self._table.setSortingEnabled(False)
            self._table.setRowCount(0)
            for slot in rows:
                r = self._table.rowCount()
                self._table.insertRow(r)
                cnt = QTableWidgetItem()
                cnt.setData(Qt.ItemDataRole.DisplayRole, int(slot["count"]))
                self._table.setItem(r, 0, cnt)
                phrase_item = QTableWidgetItem(slot["phrase"])
                # gentle highlight for likely false-positives (long / first-person body talk)
                if slot["count"] == 1 and len(slot["phrase"]) > 40:
                    phrase_item.setForeground(QColor("#d08020"))
                self._table.setItem(r, 1, phrase_item)
                self._table.setItem(r, 2, QTableWidgetItem(", ".join(sorted(slot["rules"]))[:80]))
                self._table.setItem(r, 3, QTableWidgetItem(", ".join(sorted(slot["sources"]))))
                when = time.strftime("%Y-%m-%d %H:%M", time.localtime(slot["last_ts"])) if slot["last_ts"] else "—"
                self._table.setItem(r, 4, QTableWidgetItem(when))
            self._table.setSortingEnabled(True)

        def _fill_dictionary(self):
            words = load_filter_dictionary()
            self._dict_table.setRowCount(0)
            for ph, group in words:
                r = self._dict_table.rowCount()
                self._dict_table.insertRow(r)
                self._dict_table.setItem(r, 0, QTableWidgetItem(ph))
                self._dict_table.setItem(r, 1, QTableWidgetItem(group))

        def _fill_health(self, snapshot):
            self._health_table.setRowCount(0)
            for area in (snapshot or {}).get("areas", []):
                r = self._health_table.rowCount()
                self._health_table.insertRow(r)
                self._health_table.setItem(r, 0, QTableWidgetItem(str(area.get("name", ""))))
                status = str(area.get("status", ""))
                status_item = QTableWidgetItem(status)
                if status == "RED":
                    status_item.setForeground(QColor("#d85a30"))
                elif status == "YELLOW":
                    status_item.setForeground(QColor("#c9a227"))
                else:
                    status_item.setForeground(QColor("#1d9e75"))
                self._health_table.setItem(r, 1, status_item)
                score = QTableWidgetItem()
                score.setData(Qt.ItemDataRole.DisplayRole, float(area.get("score", 0.0)))
                self._health_table.setItem(r, 2, score)
                self._health_table.setItem(r, 3, QTableWidgetItem(str(area.get("raw", ""))))

        def _apply_filter(self, text):
            t = (text or "").strip().lower()
            if not t:
                self._fill_table(self._unique)
                return
            self._fill_table([s for s in self._unique if t in s["phrase"].lower()
                              or any(t in r.lower() for r in s["rules"])])

        def _mark_good(self):
            row = self._table.currentRow()
            if row < 0:
                QMessageBox.information(self, "Select a row", "Pick a gagged phrase first.")
                return
            item = self._table.item(row, 1)
            if not item:
                return
            phrase = item.text()
            ok = append_owner_good_flag(phrase)
            if ok:
                QMessageBox.information(
                    self, "Marked GOOD",
                    f"Logged as owner-approved (not residue):\n\n{phrase[:200]}\n\n"
                    f"Future turns will treat this as a §1.D correction pheromone.",
                )
            else:
                QMessageBox.warning(self, "Could not write", "Failed to append owner flag.")


def main():  # standalone read
    import sys
    if not _QT_OK:
        data = load_residue()
        print(f"{len(data['unique'])} unique / {data['total']} total residue catches "
              f"across {data['files']} ledgers")
        health = load_unified_residue_health()
        if health:
            print("Unified eval:", health.get("summary", ""))
        for slot in data["unique"][:30]:
            print(f"  {slot['count']:4d}x  {slot['phrase'][:80]}")
        return 0
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = CorporateGagMonitorApp()
    w.resize(1000, 700)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
