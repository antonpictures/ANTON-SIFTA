#!/usr/bin/env python3
"""Build a readable 24-hour Alice prediction-history report in HTML and PDF."""

from __future__ import annotations

import html
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
SETTLED = STATE / "alice_15m_settled.jsonl"
OPEN_BOOK = STATE / "alice_15m_open_book.json"
OUTPUT = ROOT / "output"
PDF_OUTPUT = OUTPUT / "pdf"
LOCAL_TZ = ZoneInfo("America/Los_Angeles")

NAVY = "#0b1628"
INK = "#162033"
MUTED = "#667085"
TEAL = "#0b9f9a"
GREEN = "#0b7a53"
RED = "#b42318"
PAPER = "#f6f8fb"
LINE = "#d9e0ea"


def load_rows(now: float) -> tuple[list[dict], float, float]:
    start = now - 24 * 60 * 60
    rows: list[dict] = []
    for line in SETTLED.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = float(row.get("ts") or row.get("entry_ts") or 0)
        result = str(row.get("result") or "").lower()
        if start <= ts <= now and result in {"yes", "no"}:
            row["_ts"] = ts
            rows.append(row)
    rows.sort(key=lambda row: row["_ts"], reverse=True)
    return rows, start, now


def local_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(LOCAL_TZ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def compact_ticker(ticker: str) -> str:
    return ticker.replace("KX", "", 1) if ticker.startswith("KX") else ticker


def strategy(row: dict) -> str:
    return str(row.get("strategy_variant") or row.get("strategy") or "-" )


def pnl_stgm(row: dict) -> float:
    settle = row.get("body_stgm_settle") or {}
    return float(settle.get("pnl_stgm") or 0.0)


def pnl_usd(row: dict) -> float:
    return float(row.get("if_real_usd") or 0.0)


def build_stats(rows: list[dict]) -> dict:
    wins = sum(1 for row in rows if row.get("win"))
    losses = len(rows) - wins
    by_asset: dict[str, dict] = defaultdict(lambda: {"n": 0, "w": 0, "usd": 0.0, "stgm": 0.0})
    by_strategy: dict[str, dict] = defaultdict(lambda: {"n": 0, "w": 0, "usd": 0.0, "stgm": 0.0})
    for row in rows:
        asset = str(row.get("asset") or "?")
        variant = strategy(row)
        for group, key in ((by_asset, asset), (by_strategy, variant)):
            group[key]["n"] += 1
            group[key]["w"] += int(bool(row.get("win")))
            group[key]["usd"] += pnl_usd(row)
            group[key]["stgm"] += pnl_stgm(row)
    return {
        "n": len(rows),
        "wins": wins,
        "losses": losses,
        "wr": wins / len(rows) if rows else 0.0,
        "usd": sum(pnl_usd(row) for row in rows),
        "stgm": sum(pnl_stgm(row) for row in rows),
        "by_asset": dict(sorted(by_asset.items())),
        "by_strategy": dict(sorted(by_strategy.items())),
    }


def fmt_money(value: float) -> str:
    return f"${value:+.2f}"


def fmt_stgm(value: float) -> str:
    return f"{value:+.6f}"


def html_report(rows: list[dict], start: float, now: float, stats: dict, open_rows: list[dict]) -> str:
    generated = local_time(now)
    start_text = local_time(start)

    def esc(value: object) -> str:
        return html.escape(str(value))

    asset_rows = []
    for asset, values in stats["by_asset"].items():
        asset_rows.append(
            f"<tr><td>{esc(asset)}</td><td>{values['n']}</td><td>{values['w']}</td>"
            f"<td>{values['n'] - values['w']}</td><td>{values['w'] / values['n']:.1%}</td>"
            f"<td class=\"{'positive' if values['usd'] >= 0 else 'negative'}\">{fmt_money(values['usd'])}</td>"
            f"<td>{fmt_stgm(values['stgm'])}</td></tr>"
        )
    strategy_rows = []
    for name, values in stats["by_strategy"].items():
        strategy_rows.append(
            f"<tr><td>{esc(name)}</td><td>{values['n']}</td><td>{values['w']}</td>"
            f"<td>{values['n'] - values['w']}</td><td>{values['w'] / values['n']:.1%}</td>"
            f"<td class=\"{'positive' if values['usd'] >= 0 else 'negative'}\">{fmt_money(values['usd'])}</td></tr>"
        )

    detail_rows = []
    for index, row in enumerate(rows, 1):
        win = bool(row.get("win"))
        result = "WIN" if win else "LOSS"
        result_class = "win" if win else "loss"
        detail_rows.append(
            f"<tr><td>{index}</td><td>{local_time(row['_ts'])}</td>"
            f"<td>{esc(row.get('asset') or '?')} {esc(row.get('label') or '')}</td>"
            f"<td>{float(row.get('price') or 0):.0%}</td><td class=\"{result_class}\">{result}</td>"
            f"<td class=\"{'positive' if pnl_usd(row) >= 0 else 'negative'}\">{fmt_money(pnl_usd(row))}</td>"
            f"<td>{fmt_stgm(pnl_stgm(row))}</td><td>{esc(strategy(row))}</td>"
            f"<td class=\"ticker\">{esc(compact_ticker(str(row.get('ticker') or '-')))}</td></tr>"
        )

    open_html = ""
    if open_rows:
        open_items = []
        for row in open_rows:
            open_items.append(
                f"<tr><td>{esc(row.get('asset') or '?')} {esc(row.get('label') or '')}</td>"
                f"<td>{float(row.get('price') or 0):.0%}</td><td>{esc(row.get('ticker') or '-')}</td>"
                f"<td>{esc(row.get('entry_clock') or row.get('entered') or '-')}</td></tr>"
            )
        open_html = (
            "<h2>Still Open At Report Time</h2><table><thead><tr>"
            "<th>Ticket</th><th>Entry</th><th>Ticker</th><th>Clock</th></tr></thead>"
            f"<tbody>{''.join(open_items)}</tbody></table>"
        )
    else:
        open_html = "<h2>Still Open At Report Time</h2><p class=\"empty\">No open paper tickets.</p>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alice 15m History - Last 24 Hours</title>
<style>
:root {{ color-scheme: light; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color: {INK}; background: {PAPER}; }}
body {{ margin: 0; background: {PAPER}; }}
.page {{ max-width: 1360px; margin: 0 auto; padding: 42px 34px 60px; }}
.hero {{ color: white; padding: 34px 38px; border-radius: 20px; background: linear-gradient(132deg,{NAVY},#153e5c 65%,#087f7b); box-shadow: 0 12px 34px #0b16282b; }}
.eyebrow {{ letter-spacing: .14em; text-transform: uppercase; font-size: 12px; opacity: .72; }}
h1 {{ margin: 8px 0 10px; font-size: 38px; letter-spacing: -.03em; }}
.subtitle {{ color: #d9f4f0; margin: 0; font-size: 15px; }}
.grid {{ display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 13px; margin: 22px 0 30px; }}
.card {{ background: white; border: 1px solid {LINE}; border-radius: 14px; padding: 17px 18px; box-shadow: 0 4px 16px #0b16280b; }}
.label {{ color: {MUTED}; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
.value {{ font-size: 25px; font-weight: 750; margin-top: 6px; }}
.positive,.win {{ color: {GREEN}; }} .negative,.loss {{ color: {RED}; }}
h2 {{ margin: 32px 0 11px; font-size: 21px; letter-spacing: -.02em; }}
.note {{ color: {MUTED}; font-size: 13px; line-height: 1.55; }}
table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid {LINE}; border-radius: 12px; overflow: hidden; font-size: 12px; }}
th {{ color: white; background: {NAVY}; text-align: left; padding: 10px 9px; font-weight: 650; white-space: nowrap; }}
td {{ padding: 8px 9px; border-bottom: 1px solid #e8edf3; white-space: nowrap; }}
tr:nth-child(even) td {{ background: #fbfcfe; }}
tr:last-child td {{ border-bottom: 0; }}
.ticker {{ color: {MUTED}; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size: 11px; }}
.empty {{ border: 1px dashed {LINE}; border-radius: 12px; background: white; padding: 18px; color: {MUTED}; }}
.footer {{ color: {MUTED}; margin-top: 30px; font-size: 12px; line-height: 1.6; }}
@media (max-width: 850px) {{ .page {{ padding: 22px 14px 40px; }} .grid {{ grid-template-columns: repeat(2,1fr); }} h1 {{ font-size: 30px; }} table {{ display: block; overflow-x: auto; }} }}
</style></head><body><main class="page">
<section class="hero"><div class="eyebrow">Alice / STGM learning ledger</div><h1>15-minute prediction history</h1>
<p class="subtitle">Last 24 hours ending {esc(generated)} PDT</p></section>
<section class="grid">
<div class="card"><div class="label">Settled tickets</div><div class="value">{stats['n']}</div></div>
<div class="card"><div class="label">Wins / losses</div><div class="value"><span class="positive">{stats['wins']}</span> / <span class="negative">{stats['losses']}</span></div></div>
<div class="card"><div class="label">Win rate</div><div class="value">{stats['wr']:.1%}</div></div>
<div class="card"><div class="label">Hypothetical USD PnL</div><div class="value {'positive' if stats['usd'] >= 0 else 'negative'}">{fmt_money(stats['usd'])}</div></div>
<div class="card"><div class="label">STGM PnL</div><div class="value {'positive' if stats['stgm'] >= 0 else 'negative'}">{fmt_stgm(stats['stgm'])}</div></div>
</section>
<p class="note">Window: {esc(start_text)} PDT through {esc(generated)} PDT. Source: <code>.sifta_state/alice_15m_settled.jsonl</code>. Hypothetical USD PnL is the ledger's <code>if_real_usd</code> field; it is not exchange cash. STGM PnL is the settled body-ledger value. Live USD was off for these paper/STGM rows.</p>
<h2>By Asset</h2><table><thead><tr><th>Asset</th><th>Tickets</th><th>Wins</th><th>Losses</th><th>Win rate</th><th>Hyp USD PnL</th><th>STGM PnL</th></tr></thead><tbody>{''.join(asset_rows)}</tbody></table>
<h2>By Strategy</h2><table><thead><tr><th>Strategy</th><th>Tickets</th><th>Wins</th><th>Losses</th><th>Win rate</th><th>Hyp USD PnL</th></tr></thead><tbody>{''.join(strategy_rows)}</tbody></table>
{open_html}
<h2>Complete Settled History</h2><table><thead><tr><th>#</th><th>Time PDT</th><th>Ticket</th><th>Entry</th><th>Result</th><th>Hyp USD PnL</th><th>STGM PnL</th><th>Strategy</th><th>Ticker</th></tr></thead><tbody>{''.join(detail_rows)}</tbody></table>
<div class="footer">Generated {esc(generated)} PDT. This is a paper/STGM learning report, not a claim of live-money edge or a trading recommendation.</div>
</main></body></html>"""


def pdf_report(rows: list[dict], start: float, now: float, stats: dict, open_rows: list[dict], path: Path) -> None:
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=colors.HexColor(NAVY), spaceAfter=4)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=9.5, leading=12, textColor=colors.HexColor(MUTED), spaceAfter=12)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor(NAVY), spaceBefore=13, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor(INK))
    small = ParagraphStyle("Small", parent=body, fontSize=7.3, leading=8.6)
    small_right = ParagraphStyle("SmallRight", parent=small, alignment=TA_RIGHT)
    small_center = ParagraphStyle("SmallCenter", parent=small, alignment=TA_CENTER)
    table_header = ParagraphStyle("TableHeader", parent=small, textColor=colors.white, fontName="Helvetica-Bold")

    def P(text: object, style=body) -> Paragraph:
        return Paragraph(str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)

    doc = SimpleDocTemplate(str(path), pagesize=landscape(letter), rightMargin=0.34 * inch, leftMargin=0.34 * inch, topMargin=0.34 * inch, bottomMargin=0.38 * inch, title="Alice 15-minute prediction history - last 24 hours", author="SIFTA")
    story = [P("15-minute prediction history", title), P(f"Last 24 hours: {local_time(start)} PDT through {local_time(now)} PDT", subtitle)]
    summary = [
        [P("SETTLED", small), P("WINS", small), P("LOSSES", small), P("WIN RATE", small), P("HYP USD PNL", small), P("STGM PNL", small)],
        [P(stats["n"], ParagraphStyle("sum", parent=body, fontSize=15, leading=17, textColor=colors.HexColor(NAVY))), P(stats["wins"], ParagraphStyle("sumg", parent=body, fontSize=15, leading=17, textColor=colors.HexColor(GREEN))), P(stats["losses"], ParagraphStyle("sumr", parent=body, fontSize=15, leading=17, textColor=colors.HexColor(RED))), P(f"{stats['wr']:.1%}", ParagraphStyle("sum2", parent=body, fontSize=15, leading=17, textColor=colors.HexColor(NAVY))), P(fmt_money(stats["usd"]), ParagraphStyle("sum3", parent=body, fontSize=15, leading=17, textColor=colors.HexColor(RED if stats["usd"] < 0 else GREEN))), P(fmt_stgm(stats["stgm"]), ParagraphStyle("sum4", parent=body, fontSize=15, leading=17, textColor=colors.HexColor(RED if stats["stgm"] < 0 else GREEN)))],
    ]
    summary_table = Table(summary, colWidths=[1.26 * inch] * 6, repeatRows=1)
    summary_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef4f8")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor(LINE)), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [summary_table, Spacer(1, 8), P("Source: .sifta_state/alice_15m_settled.jsonl. Hypothetical USD PnL is the ledger if_real_usd field, not exchange cash. STGM PnL is the settled body-ledger value. Live USD was off for these rows.", small)]

    def section_table(headers: list[str], data: list[list[object]], widths: list[float], repeat=1) -> Table:
        converted = [[P(h, table_header) for h in headers]]
        converted.extend(data)
        table = Table(converted, colWidths=widths, repeatRows=repeat)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(LINE)), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return table

    story.append(Paragraph("By asset", section))
    asset_data = []
    for asset, values in stats["by_asset"].items():
        asset_data.append([P(asset, small), P(values["n"], small_right), P(values["w"], small_right), P(values["n"] - values["w"], small_right), P(f"{values['w'] / values['n']:.1%}", small_right), P(fmt_money(values["usd"]), small_right), P(fmt_stgm(values["stgm"]), small_right)])
    story.append(section_table(["Asset", "Tickets", "Wins", "Losses", "Win rate", "Hyp USD PnL", "STGM PnL"], asset_data, [0.83 * inch, 0.72 * inch, 0.62 * inch, 0.7 * inch, 0.76 * inch, 1.08 * inch, 0.92 * inch]))
    story.append(Paragraph("By strategy", section))
    strategy_data = []
    for name, values in stats["by_strategy"].items():
        strategy_data.append([P(name, small), P(values["n"], small_right), P(values["w"], small_right), P(values["n"] - values["w"], small_right), P(f"{values['w'] / values['n']:.1%}", small_right), P(fmt_money(values["usd"]), small_right)])
    story.append(section_table(["Strategy", "Tickets", "Wins", "Losses", "Win rate", "Hyp USD PnL"], strategy_data, [2.0 * inch, 0.72 * inch, 0.62 * inch, 0.7 * inch, 0.76 * inch, 1.08 * inch]))
    if open_rows:
        story.append(Paragraph("Still open at report time", section))
        open_data = [[P(f"{row.get('asset') or '?'} {row.get('label') or ''}", small), P(f"{float(row.get('price') or 0):.0%}", small_right), P(row.get("ticker") or "-", small), P(row.get("entry_clock") or "-", small)] for row in open_rows]
        story.append(section_table(["Ticket", "Entry", "Ticker", "Clock"], open_data, [1.35 * inch, 0.7 * inch, 3.4 * inch, 1.8 * inch]))

    story.append(Paragraph("Complete settled history", section))
    detail = []
    for index, row in enumerate(rows, 1):
        result = "WIN" if row.get("win") else "LOSS"
        result_style = ParagraphStyle("rowresult", parent=small_center, textColor=colors.HexColor(GREEN if row.get("win") else RED), fontName="Helvetica-Bold")
        detail.append([P(index, small_right), P(local_time(row["_ts"]), small), P(f"{row.get('asset') or '?'} {row.get('label') or ''}", small), P(f"{float(row.get('price') or 0):.0%}", small_right), P(result, result_style), P(fmt_money(pnl_usd(row)), small_right), P(fmt_stgm(pnl_stgm(row)), small_right), P(strategy(row), small), P(compact_ticker(str(row.get("ticker") or "-")), small)])
    story.append(section_table(["#", "Time PDT", "Ticket", "Entry", "Result", "Hyp USD", "STGM", "Strategy", "Ticker"], detail, [0.28 * inch, 1.14 * inch, 0.75 * inch, 0.48 * inch, 0.53 * inch, 0.7 * inch, 0.72 * inch, 1.3 * inch, 2.15 * inch]))
    story.append(Spacer(1, 8))
    story.append(P("Paper/STGM learning report only. It does not establish a live-money edge or represent a trading recommendation.", small))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(document.leftMargin, 0.2 * inch, "Alice 15-minute history | paper/STGM ledger | live USD off")
        canvas.drawRightString(landscape(letter)[0] - document.rightMargin, 0.2 * inch, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    now = time.time()
    rows, start, now = load_rows(now)
    stats = build_stats(rows)
    open_rows = []
    if OPEN_BOOK.exists():
        try:
            open_rows = list(json.loads(OPEN_BOOK.read_text(encoding="utf-8")).get("open") or [])
        except (json.JSONDecodeError, OSError):
            open_rows = []
    OUTPUT.mkdir(exist_ok=True)
    PDF_OUTPUT.mkdir(exist_ok=True)
    stamp = datetime.fromtimestamp(now, timezone.utc).astimezone(LOCAL_TZ).strftime("%Y%m%d_%H%M%S_PDT")
    html_path = OUTPUT / f"alice_15m_history_24h_{stamp}.html"
    pdf_path = PDF_OUTPUT / f"alice_15m_history_24h_{stamp}.pdf"
    html_path.write_text(html_report(rows, start, now, stats, open_rows), encoding="utf-8")
    pdf_report(rows, start, now, stats, open_rows, pdf_path)
    print(json.dumps({"html": str(html_path), "pdf": str(pdf_path), "stats": stats}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
