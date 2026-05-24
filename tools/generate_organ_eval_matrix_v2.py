#!/usr/bin/env python3
"""Generate the live Matrix v2 companion page from SIFTA ledgers."""

from __future__ import annotations

import html
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_EVAL = _STATE / "eval"
_DATA = _REPO / "data" / "eval"
_OUT = _EVAL / "ORGAN_EVAL_MATRIX_V2.html"
_ORDERS = _REPO / "Documents" / "ALICE_HEALTH_TOURNAMENT_2026-05-22_GROK_ORDERS.md"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _turn_rows(path: Path) -> list[dict[str, Any]]:
    return [row for row in _jsonl(path) if row.get("turn_id")]


def _latest(path: Path) -> dict[str, Any]:
    rows = _jsonl(path)
    return rows[-1] if rows else {}


def _latest_run(path: Path) -> list[dict[str, Any]]:
    rows = _jsonl(path)
    if not rows:
        return []
    run_id = rows[-1].get("run_id")
    return [row for row in rows if row.get("run_id") == run_id]


def _fmt_rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "--"


def _status_class(text: str) -> str:
    lowered = text.casefold()
    if "healthy" in lowered or "covered" in lowered or text == "correct":
        return "ok"
    if "partial" in lowered or "unverifiable" in lowered or "cold" in lowered:
        return "warn"
    if "fail" in lowered or "degraded" in lowered or "incorrect" in lowered or "no_" in lowered:
        return "bad"
    return "dim"


def _golden_inventory() -> list[dict[str, Any]]:
    files = [
        "cs153_golden_turns.jsonl",
        "cs153_talk_turns.jsonl",
        "cs153_skill_turns.jsonl",
        "cs153_free_text_turns.jsonl",
        "cs153_regression_turns.jsonl",
    ]
    out = []
    for name in files:
        path = _DATA / name
        turns = _turn_rows(path)
        out.append({
            "file": f"data/eval/{name}",
            "turns": len(turns),
            "sha_hint": path.stat().st_mtime if path.exists() else None,
        })
    return out


def _label_progress() -> dict[str, Any]:
    turns = _turn_rows(_DATA / "cs153_talk_turns.jsonl")
    verdicts = {
        row.get("turn_id"): row
        for row in _jsonl(_EVAL / "eval_verdicts.jsonl")
        if row.get("turn_id") and row.get("verdict") in {"correct", "incorrect"} and row.get("trace_id")
    }
    missing = [row.get("turn_id") for row in turns if row.get("turn_id") not in verdicts]
    return {"total": len(turns), "labeled": len(verdicts), "missing": missing}


def _queue_rows() -> list[dict[str, str]]:
    text = _ORDERS.read_text(encoding="utf-8", errors="replace") if _ORDERS.exists() else ""
    rows: list[dict[str, str]] = []
    in_ladder = False
    for line in text.splitlines():
        if line.startswith("| # | Round |"):
            in_ladder = True
            continue
        if in_ladder and not line.startswith("|"):
            break
        if not in_ladder or line.startswith("|---"):
            continue
        parts = [part.strip().strip("*") for part in line.strip("|").split("|")]
        if len(parts) >= 4 and parts[0].isdigit():
            rows.append({"n": parts[0], "round": parts[1], "buys": parts[2], "status": parts[3]})
    return rows


def _campaign_cards() -> list[dict[str, Any]]:
    rollup = _latest(_EVAL / "eval_campaign_rollup.jsonl")
    skill = _latest_run(_EVAL / "cs153_skill_runs.jsonl")
    free = _latest_run(_EVAL / "cs153_free_text_runs.jsonl")
    regression = _latest_run(_EVAL / "cs153_regression_runs.jsonl")
    labels = _label_progress()

    def summarize(rows: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "turns": len(rows),
            "passed": sum(1 for row in rows if row.get("passed") is True),
            "failed": sum(1 for row in rows if row.get("passed") is False and row.get("status") != "unverifiable"),
            "unverifiable": sum(1 for row in rows if row.get("status") == "unverifiable"),
        }

    free_judged = sum(1 for row in free if row.get("judge_used") is True)
    return [
        {
            "name": "EVAL-2 Talk Labels",
            "value": f"{labels['labeled']}/{labels['total']}",
            "status": "needs owner labels" if labels["missing"] else "complete",
            "source": ".sifta_state/eval/eval_verdicts.jsonl",
        },
        {
            "name": "EVAL-3 Skill",
            "value": _fmt_rate((summarize(skill)["passed"] / max(1, summarize(skill)["turns"]))),
            "status": summarize(skill),
            "source": ".sifta_state/eval/cs153_skill_runs.jsonl",
        },
        {
            "name": "EVAL-4 Free Text",
            "value": f"{free_judged}/{len(free)} judged",
            "status": summarize(free),
            "source": ".sifta_state/eval/cs153_free_text_runs.jsonl",
        },
        {
            "name": "EVAL-5 Regression",
            "value": _fmt_rate((summarize(regression)["passed"] / max(1, summarize(regression)["turns"]))),
            "status": summarize(regression),
            "source": ".sifta_state/eval/cs153_regression_runs.jsonl",
        },
        {
            "name": "EVAL-6 Rollup",
            "value": _fmt_rate(rollup.get("pass_rate")),
            "status": {
                "passed": rollup.get("passed", 0),
                "failed": rollup.get("failed", 0),
                "unverifiable": rollup.get("unverifiable", 0),
            },
            "source": ".sifta_state/eval/eval_campaign_rollup.jsonl",
        },
    ]


def _table(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


# Matrix-rain backdrop (plain strings — NOT f-strings — so their braces stay literal).
_RAIN_CSS = (
    "canvas#rain{position:fixed;inset:0;z-index:0;opacity:.16}"
    "main{position:relative;z-index:1}"
    "h1{text-shadow:0 0 12px #39ff14}"
    "h2.section{text-shadow:0 0 8px rgba(57,255,20,.4)}"
)
_RAIN_CANVAS = '<canvas id="rain"></canvas>'
_RAIN_SCRIPT = (
    "<script>"
    "const cv=document.getElementById('rain'),ctx=cv.getContext('2d');let cols,drops;"
    "function rs(){cv.width=innerWidth;cv.height=innerHeight;cols=Math.floor(cv.width/14);"
    "drops=Array(cols).fill(0).map(()=>Math.random()*cv.height/14);}"
    "rs();addEventListener('resize',rs);"
    "const G='0123456789STGMABCDEF01ALICE'.split('');"
    "function draw(){ctx.fillStyle='rgba(7,9,8,.10)';ctx.fillRect(0,0,cv.width,cv.height);"
    "ctx.fillStyle='#39ff14';ctx.font='13px monospace';"
    "for(let i=0;i<cols;i++){const c=G[Math.floor(Math.random()*G.length)];"
    "ctx.fillText(c,i*14,drops[i]*14);"
    "if(drops[i]*14>cv.height&&Math.random()>0.975)drops[i]=0;drops[i]++;}}"
    "setInterval(draw,60);"
    "</script>"
)


def build_html() -> str:
    snap = _json(_STATE / "canonical_organ_registry_snapshot.json")
    organs = snap.get("organs", []) if isinstance(snap.get("organs"), list) else []
    canonical = [row for row in organs if row.get("source_registry") == "CANONICAL_ORGANS"]
    status_dist = Counter((row.get("health") or {}).get("status", "UNKNOWN") for row in organs)
    coverage_rows = _latest_run(_EVAL / "organ_coverage.jsonl")
    coverage_counts = Counter(row.get("status", "UNKNOWN") for row in coverage_rows)
    coverage_holes = [row for row in coverage_rows if not row.get("ok")]
    dashboard = _latest(_EVAL / "company_dashboard.jsonl")
    rendered = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())

    cards = []
    for card in _campaign_cards():
        cards.append(
            "<section class='card'>"
            f"<h2>{html.escape(card['name'])}</h2>"
            f"<div class='metric'>{html.escape(str(card['value']))}</div>"
            f"<pre>{html.escape(json.dumps(card['status'], sort_keys=True))}</pre>"
            f"<p>{html.escape(card['source'])}</p>"
            "</section>"
        )

    canonical_table = _table(
        ["Organ", "Status", "Score", "Reliability", "Truth", "Ledgers"],
        (
            [
                html.escape(str(row.get("display_name"))),
                f"<span class='{_status_class(str((row.get('health') or {}).get('status', '')))}'>"
                f"{html.escape(str((row.get('health') or {}).get('status', 'UNKNOWN')))}</span>",
                html.escape(str((row.get("health") or {}).get("score", "--"))),
                html.escape(str((row.get("health") or {}).get("functional_reliability", "--"))),
                html.escape(str((row.get("health") or {}).get("truth_alignment", "--"))),
                html.escape(", ".join(row.get("present_ledgers", [])[:4])),
            ]
            for row in canonical
        ),
    )
    census_table = _table(
        ["Status", "Organs"],
        ([f"<span class='{_status_class(status)}'>{html.escape(status)}</span>", count] for status, count in status_dist.most_common()),
    )
    golden_table = _table(
        ["Golden", "Turns"],
        ([html.escape(row["file"]), row["turns"]] for row in _golden_inventory()),
    )
    coverage_table = _table(
        ["Organ", "Status", "Missing"],
        (
            [
                html.escape(str(row.get("organ_id"))),
                f"<span class='{_status_class(str(row.get('status')))}'>{html.escape(str(row.get('status')))}</span>",
                html.escape(", ".join(k for k in ("ledger_exists", "fresh_ledger", "outcome_bearing_row") if not row.get(k))),
            ]
            for row in coverage_holes
        ),
    )
    queue_table = _table(
        ["#", "Round", "Status"],
        ([row["n"], html.escape(row["round"]), html.escape(row["status"])] for row in _queue_rows()),
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SIFTA Organ Eval Matrix v2</title>
<style>
body{{margin:0;background:#070908;color:#d9f7df;font-family:Menlo,Consolas,monospace;}}
main{{max-width:1240px;margin:0 auto;padding:28px 18px 70px;}}
h1{{font-size:24px;margin:0 0 6px;color:#72f28a;}}
.stamp{{color:#8aa891;font-size:12px;margin-bottom:20px;line-height:1.5;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:14px 0 24px;}}
.card{{border:1px solid #244d2d;background:#0d1510;border-radius:8px;padding:13px;min-height:142px;}}
.card h2{{font-size:13px;color:#9ff2ad;margin:0 0 8px;}}
.metric{{font-size:25px;color:#fff;margin-bottom:8px;}}
pre{{white-space:pre-wrap;color:#bdd8c2;font-size:11px;margin:0 0 8px;}}
p{{font-size:11px;color:#7f9a86;margin:0;}}
h2.section{{font-size:14px;color:#8ce6ff;margin:26px 0 8px;border-bottom:1px solid #244d2d;padding-bottom:6px;}}
table{{width:100%;border-collapse:collapse;background:#0d1510;border:1px solid #244d2d;}}
th,td{{padding:8px;border-bottom:1px solid #1d3523;text-align:left;font-size:12px;vertical-align:top;}}
th{{color:#8ce6ff;font-size:11px;text-transform:uppercase;}}
.ok{{color:#74f28c}}.warn{{color:#ffca5f}}.bad{{color:#ff7b72}}.dim{{color:#93a199}}
.sources{{margin-top:24px;font-size:11px;color:#7f9a86;line-height:1.6;}}
{_RAIN_CSS}
</style>
</head>
<body>{_RAIN_CANVAS}<main>
<h1>THE ORGAN EVAL MATRIX v2</h1>
<div class="stamp">Rendered {html.escape(rendered)} from live local ledgers. Registry organs: {len(organs)}; canonical organs: {len(canonical)}; coverage holes: {len(coverage_holes)}. Coverage line gate: {html.escape(str(dashboard.get('coverage_percent', '--')))}%.</div>
<div class="grid">{''.join(cards)}</div>
<h2 class="section">Canonical 13 Health</h2>{canonical_table}
<h2 class="section">Full Census Status Distribution</h2>{census_table}
<h2 class="section">Golden Inventory</h2>{golden_table}
<h2 class="section">Canonical Organ Coverage Gate</h2>
<p>Status counts: {html.escape(json.dumps(dict(coverage_counts), sort_keys=True))}</p>{coverage_table}
<h2 class="section">Work Queue</h2>{queue_table}
<div class="sources">Sources: .sifta_state/canonical_organ_registry_snapshot.json; .sifta_state/eval/eval_campaign_rollup.jsonl; .sifta_state/eval/cs153_*_runs.jsonl; .sifta_state/eval/eval_verdicts.jsonl; .sifta_state/eval/organ_coverage.jsonl; data/eval/cs153_*.jsonl; Documents/ALICE_HEALTH_TOURNAMENT_2026-05-22_GROK_ORDERS.md.</div>
</main>{_RAIN_SCRIPT}</body></html>
"""


def main() -> int:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(build_html(), encoding="utf-8")
    print(str(_OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
