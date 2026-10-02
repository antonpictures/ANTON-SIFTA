#!/usr/bin/env python3
"""Pump Sentinel (Rug Radar) — watch Alice screen launches, with your own eyes.

Owner directive: "I want to see with my eyes what you do, how you test."

This app is the visible surface for the pump.fun screening pipeline. It does not
invent anything: it reads the same ledgers the headless tools write, and it runs
the same detectors, so what you see on screen is what the body actually did.

Screen shows:
  * live counts from the harvest and curve ledgers
  * a table of screened tokens: risk score, verdict, the flags that fired, and
    the token's known outcome when we have one
  * whether the detector is separating real winners from real losers
  * an activity log of each screening pass

Honest by construction: the separation line is printed even when it is bad, and
the caveats panel states which detector actually carried the result. A dashboard
that only shows wins is a sales tool, not an instrument.

Widget class: PumpSentinelApp
Backed by: tools/pumpfun_rugcheck.py, tools/pumpfun_harvester.mjs,
           tools/pumpfun_curve_poller.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

STATE = _REPO / ".sifta_state"
TOOLS = _REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

try:
    from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
    from PyQt6.QtWidgets import (
        QCheckBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QPushButton,
        QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    )
    _QT = True
except Exception:                                    # pragma: no cover - headless
    _QT = False
    QWidget = object                                 # type: ignore


def _count_lines(name: str) -> int:
    p = STATE / name
    if not p.exists():
        return 0
    try:
        return sum(1 for line in p.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
    except OSError:
        return 0


def _load_results() -> list[dict]:
    p = STATE / "rugcheck_results.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _symbol_for(mint: str) -> str:
    p = STATE / "pumpfun_launches.jsonl"
    if not p.exists():
        return mint[:8]
    for line in reversed(p.read_text(encoding="utf-8", errors="ignore").splitlines()):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("mint") == mint:
            return str(r.get("symbol") or mint[:8])
    return mint[:8]


def separation(results: list[dict]) -> str:
    """The line that matters, printed even when it is unflattering."""
    scored = [r for r in results if r.get("known_outcome_pct") is not None]
    if len(scored) < 3:
        return "separation: not enough screened tokens with a known outcome yet"
    flagged = [r for r in scored if r.get("risk_score", 0) >= 25]
    clean = [r for r in scored if r.get("risk_score", 0) < 25]
    bits = []
    if flagged:
        bits.append(f"flagged n={len(flagged)} mean {sum(r['known_outcome_pct'] for r in flagged)/len(flagged):+.2f}%")
    if clean:
        bits.append(f"clean n={len(clean)} mean {sum(r['known_outcome_pct'] for r in clean)/len(clean):+.2f}%")
    return "separation: " + "  |  ".join(bits)


def run_screen(batch: int) -> list[dict]:
    """Screen the newest N tokens. Uses the same detector the CLI uses."""
    import pumpfun_rugcheck as rc

    launches: dict[str, dict] = {}
    p = STATE / "pumpfun_launches.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("mint"):
                launches[r["mint"]] = r
    targets = list(launches)[-batch:]
    out = []
    for mint in targets:
        res = rc.rugcheck(mint, (launches.get(mint) or {}).get("dev_wallet"), [])
        outcome = rc.known_outcome(mint)
        res["symbol"] = (launches.get(mint) or {}).get("symbol")
        res["known_outcome_pct"] = None if outcome is None else round(outcome, 2)
        out.append(res)
    existing = _load_results()
    merged = {r.get("mint"): r for r in existing}
    for r in out:
        merged[r["mint"]] = r
    (STATE / "rugcheck_results.json").write_text(
        json.dumps(list(merged.values()), indent=2), encoding="utf-8")
    return out


if _QT:

    class _ScreenWorker(QThread):
        done = pyqtSignal(list, str)

        def __init__(self, batch: int) -> None:
            super().__init__()
            self.batch = batch

        def run(self) -> None:                       # pragma: no cover - thread
            try:
                rows = run_screen(self.batch)
                self.done.emit(rows, "")
            except Exception as exc:
                self.done.emit([], f"{type(exc).__name__}: {exc}")

    class _PaperWorker(QThread):
        done = pyqtSignal(str)

        def run(self) -> None:                            # pragma: no cover - thread
            try:
                import pumpfun_paper_bot as pb
                state = pb.load_state(pb.DEFAULT_CAPITAL)
                state = pb.cycle(state)
                self.done.emit(
                    f"paper cycle: equity ${state['equity']:.2f} cash ${state['cash']:.2f} "
                    f"open {len(state['positions'])} opened {state['opened']} "
                    f"closed {state['closed']} busts {state['busts']}"
                )
            except Exception as exc:
                self.done.emit(f"paper cycle error: {type(exc).__name__}: {exc}")

    class PumpSentinelApp(QWidget):
        """The visible surface for pump.fun launch screening."""

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Pump Sentinel — Rug Radar")
            self.resize(1000, 700)
            self._worker: _ScreenWorker | None = None
            self._timer = QTimer(self)
            self._timer.setInterval(5 * 60 * 1000)      # 5 minutes
            self._timer.timeout.connect(self.screen_now)
            self._paper_timer = QTimer(self)
            self._paper_timer.setInterval(60 * 1000)    # one paper cycle per minute
            self._paper_timer.timeout.connect(self._paper_cycle)
            self._paper_worker = None
            self._build()
            self._panel_timer = QTimer(self)
            self._panel_timer.setInterval(5000)
            self._panel_timer.timeout.connect(self._refresh_panels)
            self._panel_timer.start()

        def _build(self) -> None:
            root = QVBoxLayout(self)

            title = QLabel("Pump Sentinel — Rug Radar")
            title.setStyleSheet("font-size: 18px; font-weight: 600;")
            root.addWidget(title)

            self.status = QLabel()
            self.status.setStyleSheet("color: #666;")
            root.addWidget(self.status)

            # ── THE BIG SWITCH ────────────────────────────────────────────
            self.power = QPushButton("OFF")
            self.power.setCheckable(True)
            self.power.setMinimumHeight(76)
            self.power.setStyleSheet(
                "QPushButton{font-size:26px;font-weight:800;border-radius:12px;"
                "background:#b3261e;color:white;border:none;}"
                "QPushButton:checked{background:#1e8e3e;}"
            )
            self.power.toggled.connect(self._toggle_power)
            root.addWidget(self.power)

            # ── FAKE vs REAL ──────────────────────────────────────────────
            panel = QFrame()
            grid = QGridLayout(panel)
            hdr = QLabel("portfolio")
            hdr.setStyleSheet("font-weight:600;")
            grid.addWidget(hdr, 0, 0)
            fake_hdr = QLabel("FAKE (paper, refills on bust)")
            fake_hdr.setStyleSheet("font-weight:600;color:#1e8e3e;")
            real_hdr = QLabel("REAL (untouched)")
            real_hdr.setStyleSheet("font-weight:600;color:#8a6d3b;")
            grid.addWidget(fake_hdr, 0, 1)
            grid.addWidget(real_hdr, 0, 2)
            self.fake_lbl = QLabel("—"); self.real_lbl = QLabel("—")
            self.fake_lbl.setWordWrap(True); self.real_lbl.setWordWrap(True)
            grid.addWidget(self.fake_lbl, 1, 1)
            grid.addWidget(self.real_lbl, 1, 2)
            grid.setColumnStretch(1, 1); grid.setColumnStretch(2, 1)
            root.addWidget(panel)

            row = QHBoxLayout()
            self.btn = QPushButton("Screen newest 6 launches")
            self.btn.clicked.connect(self.screen_now)
            row.addWidget(self.btn)
            self.only_flagged = QCheckBox("show only flagged")
            self.only_flagged.stateChanged.connect(self._fill_table)
            row.addWidget(self.only_flagged)
            self.auto = QCheckBox("auto-screen every 5 min")
            self.auto.stateChanged.connect(self._toggle_auto)
            row.addWidget(self.auto)
            row.addStretch(1)
            self.sep = QLabel()
            row.addWidget(self.sep)
            root.addLayout(row)

            self.table = QTableWidget(0, 5)
            self.table.setHorizontalHeaderLabels(["token", "risk", "verdict", "flags", "known outcome"])
            self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            root.addWidget(self.table, 3)

            self.log = QTextEdit()
            self.log.setReadOnly(True)
            self.log.setPlaceholderText("activity log — each screening pass appears here")
            root.addWidget(self.log, 1)

            caveat = QLabel(
                "Reads the same ledgers and detectors as the headless tools. "
                "In the test run, the DEV-HISTORY check carried the separation; "
                "the bundle check fired on none and the wash check was not measured. "
                "Samples are small and were partly selected by outcome, so this is "
                "an instrument, not a profit claim."
            )
            caveat.setWordWrap(True)
            caveat.setStyleSheet("color: #8a6d3b;")
            root.addWidget(caveat)

            self.refresh()

        def refresh(self) -> None:
            launches = _count_lines("pumpfun_launches.jsonl")
            curve = _count_lines("pumpfun_curve_paths.jsonl")
            copye = _count_lines("pumpfun_copy_entries.jsonl")
            results = _load_results()
            self.status.setText(
                f"launches harvested: {launches:,}   ·   curve price points: {curve:,}   ·   "
                f"copy entries: {copye:,}   ·   tokens screened: {len(results)}"
            )
            self.sep.setText(separation(results))
            self._fill_table()

        def _fill_table(self) -> None:
            results = _load_results()
            if self.only_flagged.isChecked():
                results = [r for r in results if r.get("risk_score", 0) >= 25]
            results.sort(key=lambda r: -int(r.get("risk_score") or 0))
            self.table.setRowCount(len(results))
            for i, r in enumerate(results):
                sym = str(r.get("symbol") or _symbol_for(str(r.get("mint", ""))))
                outcome = r.get("known_outcome_pct")
                cells = [
                    sym,
                    str(r.get("risk_score", 0)),
                    str(r.get("verdict", "")),
                    "; ".join(r.get("flags") or []) or "none",
                    "unknown" if outcome is None else f"{outcome:+.1f}%",
                ]
                for j, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    if j == 0:
                        item.setData(Qt.ItemDataRole.ToolTipRole, str(r.get("mint")))
                    self.table.setItem(i, j, item)

        def _toggle_power(self, on: bool) -> None:
            """THE SWITCH. Green = the body is testing continuously. Red = idle."""
            self.power.setText("ON — testing continuously" if on else "OFF")
            if on:
                self._paper_timer.start()
                self.log.append("POWER ON — paper portfolio trading against live launches every minute")
                self._paper_cycle()
            else:
                self._paper_timer.stop()
                self.log.append("POWER OFF — paper trader idle")

        def _paper_cycle(self) -> None:
            if self._paper_worker and self._paper_worker.isRunning():
                return
            self._paper_worker = _PaperWorker()
            self._paper_worker.done.connect(self._paper_done)
            self._paper_worker.start()

        def _paper_done(self, summary: str) -> None:      # pragma: no cover - thread
            self.log.append(summary)
            self._refresh_panels()

        def _refresh_panels(self) -> None:
            try:
                import pumpfun_paper_bot as pb
                st = json.loads(pb.PAPER_STATE.read_text()) if pb.PAPER_STATE.exists() else None
                real = json.loads(pb.REAL_STATE.read_text()) if pb.REAL_STATE.exists() else None
            except Exception:
                st = real = None
            if st:
                self.fake_lbl.setText(
                    f"equity ${st.get('equity', 0):.2f}\n"
                    f"cash ${st.get('cash', 0):.2f}   open {len(st.get('positions') or [])}\n"
                    f"opened {st.get('opened', 0)}  closed {st.get('closed', 0)}  "
                    f"busts {st.get('busts', 0)}\n"
                    f"peak ${st.get('peak_equity', 0):.2f}  worst ${st.get('worst_equity', 0):.2f}\n"
                    f"started at ${st.get('initial_capital', 0):.2f}"
                )
            else:
                self.fake_lbl.setText("no paper state yet — switch ON")
            if real:
                self.real_lbl.setText(
                    f"{real.get('sol', 0):.4f} SOL  ≈ ${real.get('usd_estimate', 0):.2f}\n"
                    f"wallet {str(real.get('wallet'))[:10]}…\n"
                    f"platform UI figure ${real.get('observed_ui_usd', 0):.2f}\n"
                    f"no key held · nothing signed · nothing sent"
                )
            else:
                self.real_lbl.setText("real balance not read yet")

        def _toggle_auto(self) -> None:
            """Continuous screening while the window is open."""
            if self.auto.isChecked():
                self._timer.start()
                self.log.append("auto-screen ON — screening the newest launches every 5 minutes")
                self.screen_now()
            else:
                self._timer.stop()
                self.log.append("auto-screen OFF")

        def screen_now(self) -> None:
            if self._worker and self._worker.isRunning():
                return
            self.btn.setEnabled(False)
            self.log.append("screening newest launches — reading the chain…")
            self._worker = _ScreenWorker(6)
            self._worker.done.connect(self._screened)
            self._worker.start()

        def _screened(self, rows: list, err: str) -> None:   # pragma: no cover - thread
            self.btn.setEnabled(True)
            if err:
                self.log.append(f"error: {err}")
            for r in rows:
                flags = "; ".join(r.get("flags") or []) or "no red flag"
                oc = r.get("known_outcome_pct")
                self.log.append(
                    f"  {str(r.get('symbol'))[:12]:13s} risk={r.get('risk_score', 0):3d} "
                    f"{r.get('verdict','')}  outcome={'?' if oc is None else f'{oc:+.1f}%'}  [{flags}]"
                )
            self.refresh()

else:                                                # pragma: no cover - headless

    class PumpSentinelApp:                           # type: ignore[no-redef]
        """Placeholder when Qt is unavailable; the CLI path still works."""

        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyQt6 is required for the Pump Sentinel window")


def watch(minutes: float, every_s: float = 300.0, batch: int = 6) -> int:
    """Screen the newest launches continuously, forever, and log each pass.

    This is the version that keeps working with the window closed: the same
    detector, the same ledger, driven by a loop instead of a button.
    """
    import time
    deadline = time.time() + minutes * 60 if minutes > 0 else None
    passes = 0
    while deadline is None or time.time() < deadline:
        passes += 1
        started = time.time()
        try:
            rows = run_screen(batch)
            flagged = [r for r in rows if r.get("risk_score", 0) >= 25]
            print(f"[pass {passes}] screened {len(rows)} · flagged {len(flagged)} · "
                  f"{separation(_load_results())}")
            for r in rows:
                if r.get("risk_score", 0) >= 25:
                    print(f"    ! {str(r.get('symbol'))[:14]:15s} risk={r['risk_score']:3d} "
                          f"{'; '.join(r.get('flags') or [])}")
        except Exception as exc:
            print(f"[pass {passes}] error: {type(exc).__name__}: {exc}")
        elapsed = time.time() - started
        time.sleep(max(5.0, every_s - elapsed))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if args and args[0] == "watch":
        mins = float(args[1]) if len(args) > 1 else 0.0
        every = float(args[2]) if len(args) > 2 else 300.0
        return watch(mins, every)
    if args and args[0] == "screen":
        n = int(args[1]) if len(args) > 1 else 6
        rows = run_screen(n)
        for r in rows:
            oc = r.get("known_outcome_pct")
            print(f"{str(r.get('symbol'))[:12]:13s} risk={r.get('risk_score',0):3d} "
                  f"{r.get('verdict',''):16s} outcome={'?' if oc is None else f'{oc:+.1f}%'} "
                  f"[{'; '.join(r.get('flags') or []) or 'no red flag'}]")
        print("\n" + separation(_load_results()))
        return 0
    if not _QT:
        print("PyQt6 unavailable in this interpreter. Run with the venv, or use: screen")
        return 1
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = PumpSentinelApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
