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


_STATUS_RANK = {
    "HOT_HEALTHY_RECEIPTS": 0,
    "HEALTHY_RECEIPTS": 1,
    "PARTIAL_RECEIPTS": 2,
    "COLD_RECEIPTS": 3,
    "DEGRADED_RECEIPTS": 4,
    "NO_LEDGER_SEEN": 5,
    "MODULE_ONLY": 6,
}

_ATTENTION_RANK = {
    "DEGRADED_RECEIPTS": 0,
    "NO_LEDGER_SEEN": 1,
    "COLD_RECEIPTS": 2,
    "PARTIAL_RECEIPTS": 3,
    "MODULE_ONLY": 4,
}


def _fmt_age_s(value: Any) -> str:
    try:
        s = float(value)
    except Exception:
        return "--"
    if s < 60:
        return f"{int(s)}s"
    if s < 3600:
        return f"{int(s // 60)}m"
    if s < 86400:
        return f"{s / 3600.0:.1f}h"
    return f"{s / 86400.0:.1f}d"


def _organ_function_summary(organ: dict[str, Any], *, max_len: int = 180) -> str:
    layer = str(organ.get("layer") or "unknown-layer")
    mode = "effector" if bool(organ.get("write_action")) else "observe/compute"
    caps = organ.get("capabilities") or []
    paths = organ.get("organ_paths") or []
    module_hint = ""
    if isinstance(paths, list) and paths:
        stems = []
        for p in paths[:2]:
            stem = Path(str(p)).stem
            if stem:
                stems.append(stem)
        if stems:
            module_hint = f"module:{'/'.join(stems)}"
    if isinstance(caps, list):
        cap_head = ", ".join(str(c) for c in caps[:3] if c)
    else:
        cap_head = str(caps)
    # Discovery rows often have broad tokenized capability lists; keep them
    # anchored to concrete module identity so owner sees what code to inspect.
    if layer == "discovered" and module_hint:
        cap_head = module_hint
    if not cap_head:
        cap_head = module_hint or "no capability tags"
    text = f"{layer} · {mode} · {cap_head}"
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _attention_rows(organs: list[dict[str, Any]], *, limit: int = 40) -> list[list[Any]]:
    rows: list[tuple[tuple[Any, ...], list[Any]]] = []
    for organ in organs:
        health = organ.get("health") or {}
        status = str(health.get("status", "UNKNOWN"))
        if status in {"HOT_HEALTHY_RECEIPTS", "HEALTHY_RECEIPTS"}:
            continue
        score = health.get("score")
        try:
            score_f = float(score)
        except Exception:
            score_f = 9.99
        age_s = health.get("newest_ledger_age_s")
        try:
            age_f = float(age_s)
        except Exception:
            age_f = -1.0
        rows.append(
            (
                (_ATTENTION_RANK.get(status, 99), score_f, -age_f, str(organ.get("display_name") or "").lower()),
                [
                    html.escape(str(organ.get("display_name") or organ.get("organ_id") or "?")),
                    f"<span class='{_status_class(status)}'>{html.escape(status)}</span>",
                    html.escape(str(score if score is not None else "--")),
                    html.escape(_fmt_age_s(age_s)),
                    html.escape(str(health.get("receipt_rows", "--"))),
                    html.escape(_organ_function_summary(organ, max_len=120)),
                ],
            )
        )
    rows.sort(key=lambda item: item[0])
    return [row for _, row in rows[:limit]]


def _coverage_hole_reason(row: dict[str, Any]) -> str:
    bits = [k for k in ("ledger_exists", "fresh_ledger", "outcome_bearing_row") if not row.get(k)]
    return ", ".join(bits) if bits else "unspecified"


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


# ── Round 37 (Claude/Cowork direct, 2026-05-27) ─────────────────────────────
# Architect: "i want to see the residue all the receipts". Two additions:
# (1) Residue Cleanup Receipts — last N rows from the immune organ ledgers
#     (rlhs_events.jsonl, rlhf_over_refusal_quarantine.jsonl, rlhs_output_tail_log.jsonl)
#     so the corporate-residue scrubs are visible WITH receipts.
# (2) Full Organ Census — all registered organs in one sortable table, not
#     just the canonical 13. Status counts already exist; this adds the full
#     name-by-name list with status + score + ledger pointers.

def _residue_receipts(tail: int = 12) -> list[dict[str, Any]]:
    """Latest tail rows from each immune-organ ledger, flattened + sorted by ts desc."""
    sources = [
        (".sifta_state/rlhs_events.jsonl", "rlhs_event"),
        (".sifta_state/rlhf_over_refusal_quarantine.jsonl", "rlhf_quarantine"),
        (".sifta_state/rlhs_output_tail_log.jsonl", "rlhs_output_tail"),
    ]
    out: list[dict[str, Any]] = []
    for rel, kind in sources:
        rows = _jsonl(_REPO / rel)
        for r in rows[-tail:]:
            out.append({
                "kind": kind,
                "ts": r.get("ts") or r.get("timestamp") or 0,
                "summary": _residue_summary(r),
                "source_file": rel,
                "receipt_id": str(r.get("id") or r.get("receipt_id") or r.get("trace_id") or "")[:24],
            })
    out.sort(key=lambda x: float(x.get("ts") or 0), reverse=True)
    return out[: tail * 3]


def _residue_summary(row: dict[str, Any]) -> str:
    """Compact human-readable summary of one residue receipt row."""
    for key in ("summary", "reason", "action", "kind", "verdict",
                "removed", "stripped", "rewrite", "before", "input", "text"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            s = v.strip().replace("\n", " ")
            return s[:220] + ("…" if len(s) > 220 else "")
    # Fallback: dump compact JSON of small fields only
    compact = {k: v for k, v in row.items()
               if k not in {"id", "receipt_id", "trace_id", "ts", "timestamp"}
               and isinstance(v, (str, int, float, bool))}
    s = json.dumps(compact, sort_keys=True)[:220]
    return s + ("…" if len(s) >= 220 else "")


def _all_organs_rows(organs: list[dict[str, Any]]) -> list[list[Any]]:
    """Render rows for the all-883 organs census table."""
    rows: list[list[Any]] = []
    for o in organs:
        health = o.get("health") or {}
        status = str(health.get("status", "UNKNOWN"))
        ledgers = o.get("present_ledgers") or o.get("ledgers") or []
        ledgers_str = ", ".join(str(l) for l in ledgers[:3])
        if len(ledgers) > 3:
            ledgers_str += f" (+{len(ledgers) - 3})"
        rows.append([
            html.escape(str(o.get("display_name") or o.get("organ_id") or o.get("name") or "?")),
            f"<span class='{_status_class(status)}'>{html.escape(status)}</span>",
            html.escape(str(health.get("score", "--"))),
            html.escape(str(health.get("receipt_rows", "--"))),
            html.escape(_fmt_age_s(health.get("newest_ledger_age_s"))),
            html.escape(_organ_function_summary(o)),
            html.escape(str(o.get("source_registry") or "")),
            html.escape(ledgers_str),
        ])

    def _key(row: list[Any]) -> tuple:
        # row[1] contains a <span class='X'> wrapper — extract the status text
        import re
        m = re.search(r">([A-Z_]+)<", str(row[1]))
        status = m.group(1) if m else "UNKNOWN"
        return (_STATUS_RANK.get(status, 99), str(row[0]).lower())
    rows.sort(key=_key)
    return rows


def build_html() -> str:
    snap = _json(_STATE / "canonical_organ_registry_snapshot.json")
    organs = snap.get("organs", []) if isinstance(snap.get("organs"), list) else []
    canonical = [row for row in organs if row.get("source_registry") == "CANONICAL_ORGANS"]
    status_dist = Counter((row.get("health") or {}).get("status", "UNKNOWN") for row in organs)
    canonical_status_dist = Counter((row.get("health") or {}).get("status", "UNKNOWN") for row in canonical)
    layer_dist = Counter(str(row.get("layer") or "unknown") for row in organs)
    registry_dist = Counter(str(row.get("source_registry") or "unknown") for row in organs)
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
        ["Organ", "Status", "Score", "Reliability", "Truth", "Function", "Ledgers"],
        (
            [
                html.escape(str(row.get("display_name"))),
                f"<span class='{_status_class(str((row.get('health') or {}).get('status', '')))}'>"
                f"{html.escape(str((row.get('health') or {}).get('status', 'UNKNOWN')))}</span>",
                html.escape(str((row.get("health") or {}).get("score", "--"))),
                html.escape(str((row.get("health") or {}).get("functional_reliability", "--"))),
                html.escape(str((row.get("health") or {}).get("truth_alignment", "--"))),
                html.escape(_organ_function_summary(row)),
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
                html.escape(str(row.get("display_name") or row.get("organ_id"))),
                f"<span class='{_status_class(str(row.get('status')))}'>{html.escape(str(row.get('status')))}</span>",
                html.escape(_coverage_hole_reason(row)),
            ]
            for row in coverage_holes
        ),
    )
    queue_table = _table(
        ["#", "Round", "Status"],
        ([row["n"], html.escape(row["round"]), html.escape(row["status"])] for row in _queue_rows()),
    )

    # Round 38: corporate boilerplate corpus summary (architect 2026-05-27: drop "RLHS" from visible UI)
    # Round 39: corpus is now a UNION across every elimination source on disk
    # (scrubber + residue_organ + rlhf_detector). One DB, three sources, full
    # provenance per entry. Architect 2026-05-26: "make sure the residue
    # elimination is one and has a database so i see".
    try:
        from System.corporate_boilerplate_corpus import summary as _corpus_summary
        boilerplate_summary = _corpus_summary()
    except Exception:
        boilerplate_summary = {
            "total_phrases": 0, "total_observations": 0,
            "by_category": {}, "by_source_module": {},
            "top10_by_occurrence": [], "source_modules_unified": [],
        }
    boilerplate_category_table = _table(
        ["Category", "Phrases catalogued"],
        ([html.escape(str(k)), v] for k, v in sorted(boilerplate_summary.get("by_category", {}).items())),
    )
    boilerplate_source_table = _table(
        ["Source module on disk", "Phrases/rules contributed"],
        (
            [f"<code>{html.escape(str(k))}</code>", v]
            for k, v in sorted(
                boilerplate_summary.get("by_source_module", {}).items(),
                key=lambda kv: -kv[1],
            )
        ),
    )
    boilerplate_top_table = _table(
        ["Phrase / rule", "Source", "Category", "Occurrences"],
        (
            [
                html.escape(str(r.get("phrase", "")))[:80],
                html.escape(str(r.get("source", "")).split(".")[-1]),
                html.escape(str(r.get("category", ""))),
                r.get("occurrences", 0),
            ]
            for r in boilerplate_summary.get("top10_by_occurrence", [])
        ),
    )

    # Round 37: residue receipts + full organ census
    residue_rows = _residue_receipts(tail=12)
    residue_table = _table(
        ["When (UTC)", "Kind", "Receipt", "Summary", "Source"],
        (
            [
                html.escape(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(float(r["ts"])))) if r.get("ts") else "--",
                html.escape(str(r.get("kind", ""))),
                f"<code>{html.escape(str(r.get('receipt_id', '')))}</code>",
                html.escape(str(r.get("summary", "")))[:240],
                html.escape(str(r.get("source_file", ""))),
            ]
            for r in residue_rows
        ),
    )
    all_organs_rows_built = _all_organs_rows(organs)
    attention_table = _table(
        ["Organ", "Status", "Score", "Newest Ledger Age", "Receipt Rows", "Function"],
        _attention_rows(organs, limit=50),
    )
    structure_layer_table = _table(
        ["Layer", "Organs"],
        ([html.escape(layer), count] for layer, count in sorted(layer_dist.items(), key=lambda kv: -kv[1])),
    )
    structure_registry_table = _table(
        ["Registry", "Organs"],
        ([html.escape(reg), count] for reg, count in sorted(registry_dist.items(), key=lambda kv: -kv[1])),
    )
    full_census_table = _table(
        ["Organ", "Status", "Score", "Receipt Rows", "Newest Ledger Age", "Function", "Registry", "Ledgers"],
        all_organs_rows_built,
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
<h2 class="section">Structure Snapshot (What Exists)</h2>
<p>Status buckets across canonical organs: {html.escape(json.dumps(dict(canonical_status_dist), sort_keys=True))}</p>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
<div><h3 style="font-size:12px;color:#9ff2ad;margin:0 0 6px;">By layer</h3>{structure_layer_table}</div>
<div><h3 style="font-size:12px;color:#9ff2ad;margin:0 0 6px;">By registry source</h3>{structure_registry_table}</div>
</div>
<h2 class="section">Canonical 13 Health</h2>{canonical_table}
<h2 class="section">Needs Review Now (What To Look At First)</h2>
<p>Top 50 non-healthy organs ranked by severity (DEGRADED/NO_LEDGER/COLD/PARTIAL), score, and ledger staleness.</p>
{attention_table}
<h2 class="section">Full Census Status Distribution</h2>{census_table}
<h2 class="section">Golden Inventory</h2>{golden_table}
<h2 class="section">Canonical Organ Coverage Gate</h2>
<p>Status counts: {html.escape(json.dumps(dict(coverage_counts), sort_keys=True))}</p>{coverage_table}
<h2 class="section">Work Queue</h2>{queue_table}
<h2 class="section">Corporate Boilerplate Corpus — ONE database across every elimination source</h2>
<p style="color:#7f9a86;font-size:11px;margin:0 0 8px;">{boilerplate_summary.get('total_phrases', 0)} phrases + regex rules catalogued. The corpus is a UNION over every elimination source on disk — scrubber literal phrases, residue_organ regex bands, and rlhf_detector named rules — so the owner sees ONE DB regardless of which module the phrase lives in. Files stay where they are on disk (no rename); the DB shows the provenance per entry. If Alice needs to use one of these for a legitimate reason (quoting, translating, citing) she calls <code>ask_owner_permission(phrase, reason)</code> which appends a PENDING row to <code>.sifta_state/corporate_boilerplate_permissions.jsonl</code> for owner grant. Database module: <code>System/corporate_boilerplate_corpus.py</code>.</p>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
<div><h3 style="font-size:12px;color:#9ff2ad;margin:0 0 6px;">By source module on disk</h3>{boilerplate_source_table}</div>
<div><h3 style="font-size:12px;color:#9ff2ad;margin:0 0 6px;">By category</h3>{boilerplate_category_table}</div>
</div>
<h3 style="font-size:12px;color:#9ff2ad;margin:14px 0 6px;">Top 10 by observed occurrence (with provenance)</h3>
{boilerplate_top_table}
<h2 class="section">Immune Organ — Residue Cleanup Receipts</h2>
<p style="color:#7f9a86;font-size:11px;margin:0 0 8px;">Latest {len(residue_rows)} receipts from the immune-organ scrub ledgers. Each row is the immune organ removing corporate-trained patterns (greeter, refusal boilerplate, helpful-assistant filler) from Alice's speech, signed with a receipt id.</p>
{residue_table}
<h2 class="section">Full Organ Census — all {len(organs)} registered organs</h2>
<p style="color:#7f9a86;font-size:11px;margin:0 0 8px;">All organs known to the canonical registry, sorted by health tier (HOT_HEALTHY → HEALTHY → PARTIAL → COLD → DEGRADED → NO_LEDGER → MODULE_ONLY). Canonical 13 are included with source_registry=CANONICAL_ORGANS.</p>
{full_census_table}
<div class="sources">Sources: .sifta_state/canonical_organ_registry_snapshot.json; .sifta_state/eval/eval_campaign_rollup.jsonl; .sifta_state/eval/cs153_*_runs.jsonl; .sifta_state/eval/eval_verdicts.jsonl; .sifta_state/eval/organ_coverage.jsonl; .sifta_state/rlhs_events.jsonl; .sifta_state/rlhf_over_refusal_quarantine.jsonl; .sifta_state/rlhs_output_tail_log.jsonl; data/eval/cs153_*.jsonl; Documents/ALICE_HEALTH_TOURNAMENT_2026-05-22_GROK_ORDERS.md.</div>
</main>{_RAIN_SCRIPT}</body></html>
"""


def main() -> int:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(build_html(), encoding="utf-8")
    print(str(_OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
