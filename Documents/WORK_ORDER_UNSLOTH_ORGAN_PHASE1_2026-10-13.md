# WORK ORDER — Unsloth organ, Phase 1 (read-only) + auth reconnaissance
**Date:** 2026-10-13 · **Architect:** George · **Issued by:** Alice (coding arm) · **For:** local coding model
**Parent plan:** `/Users/ioanganton/Documents/SIFTA_BORG_UNSLOTH_PLAN_2026-10-13.md` (Phases 0–1)
**Constraint (Architect's own words):** *we do not lose the creature we already built.*

---

## 0. Evidence already on disk — do not re-derive it

### 0.0 If a file you were told to read does not exist — say so and STOP

Do not restate your intention. Do not re-plan. Do not loop. Emit one line:
`BLOCKED: <exact path> not found` and stop. A missing file is a finding;
repeating "I need to look at the files" is not work.

Both documents live here (placed together 2026-10-13 16:02):

- Plan: `/Users/ioanganton/Documents/SIFTA_BORG_UNSLOTH_PLAN_2026-10-13.md`
- This work order: `/Users/ioanganton/Documents/WORK_ORDER_UNSLOTH_ORGAN_PHASE1_2026-10-13.md`
  (canonical copy also in the repo at `ANTON_SIFTA/Documents/` — keep the two in sync)

I ran these; the numbers are yours to build against, not to re-discover.

| Fact | Receipt |
|---|---|
| Unsloth backend live | `curl 127.0.0.1:8888/api/health` → `200`, `service: "Unsloth UI Backend"`, `chat_only: false` |
| API surface | `openapi.json` → **516 paths** |
| Auth wall | `/api/health` → `200`. `/api/system`, `/api/train/runs`, `/api/export/status`, `/api/models/list` → **`401 {"detail":"Not authenticated"}`** |
| Auth endpoint | `/api/auth/identity` → `422`, requires query param **`nonce`** |
| Auth protocol (from the Rust binary) | `POST /api/auth/desktop-login` with `Content-Type: application/json`; header **`X-Desktop-Secret`**; response `DesktopAuthResponse::LoginRequired \| TokensSetupError`; body fields **`access_token`, `login_required`, `login_mode`, `signature`, `headers`**, `TokenResponse { token }` |
| Secret provisioning | `unsloth studio provision-desktop-auth`; env `UNSLOTH_STUDIO_HOME` / `STUDIO_HOME`; state under `~/.unsloth/studio`; `token_sha256` |
| Ownership states | `NotInstalled, ManagedReady, ManagedStale, OwnedReady, OwnedStale, AttachedReady` |
| Port map (`lsof`) | 8100 SIFTA `chorus_node_server.py` · 8888 Unsloth · 8644 Hermes gateway · 3080 DSH Web GUI |
| Local training duct | SIFTA `.venv` torch 2.11.0/MPS · `~/.unsloth/studio/unsloth_studio/bin/python` torch 2.10.0/MPS + `import unsloth` ok |

Source binary: `/Applications/Unsloth.app/Contents/MacOS/unsloth-studio`.

---

## 1. What you are building (one deliverable, two files + one test)

### 1.1 `System/organs/unsloth_organ.py` — thin read-only client

Create the `System/organs/` package (it does not exist yet; add `__init__.py`).
Follow repo conventions — read `System/swarm_model_body_self_knowledge.py` first for the
`_state_dir()` pattern and copy that shape, do not invent a new one.

Required public surface:

```python
BASE_URL = "http://127.0.0.1:8888"

def health(timeout: float = 4.0) -> dict: ...          # never raises; on failure returns {"reachable": False, "reason": <code>}
def probe_endpoints(paths: list[str] | None = None, timeout: float = 4.0) -> list[dict]: ...
    # each row: {"path": str, "status": int | None, "auth": "open"|"required"|"missing"|"unreachable"}
def auth_protocol() -> dict: ...
    # static description of the protocol in §0 — endpoint, header, body fields, ownership states.
    # This is a CONSTANT table read from the binary evidence. It is not a network call.
def desktop_secret_present() -> dict: ...
    # {"present": bool, "path": str|None, "sha256_prefix": str|None}
    # Report EXISTENCE and a hash prefix only. NEVER read the secret into memory beyond hashing it,
    # NEVER log it, NEVER return it, NEVER send it anywhere.
def snapshot(state_dir: str | None = None) -> dict: ...
    # {"ts": float, "health": {...}, "endpoints": [...], "auth": {...}, "secret": {...}}
```

### 1.2 `tools/unsloth_borg_probe.py` — CLI wrapper

```
python3 tools/unsloth_borg_probe.py --probe       # writes .sifta_state/unsloth_organ_probe.json
python3 tools/unsloth_borg_probe.py --probe --json
```

Behaviour: run `health()` + `probe_endpoints()` + `desktop_secret_present()`, write the JSON artifact,
print a compact human table. **Exit 0 if the backend is reachable (even if auth-walled); exit 1 only if
the backend is unreachable.** A walled backend is a valid, expected outcome — not an error.

### 1.3 `tests/test_unsloth_borg_probe.py`

Must pass **whether or not Unsloth is running**. Mock the transport for the deterministic cases; do not
require the live daemon for the suite to go green. Minimum assertions:

- `health()` against a mocked `200` returns `reachable: True` with the `service` string.
- `health()` against a refused connection returns `reachable: False` and a `reason` key — **proves it does not raise**.
- `probe_endpoints()` classifies `200`→`"open"`, `401`→`"required"`, `404`→`"missing"`.
- `desktop_secret_present()` never returns a value that equals or contains a real secret (assert the
  returned dict has no key holding more than 8 chars of hash).
- `snapshot()` is JSON-serializable (`json.dumps` round-trips).

---

## 2. Hard constraints — violating any of these fails the work order

1. **Read-only.** Only HTTP `GET`. No `POST`, no `PUT`, no writes into `~/.unsloth/` or its SQLite DB.
   Do not open `studio.db` at all in this phase.
2. **No auth circumvention.** Do not brute-force, guess, or synthesise an `X-Desktop-Secret`. Do not
   attempt `desktop-login` with a fabricated secret. Discovering *that* the header exists is reconnaissance;
   using a made-up one is an attack on the Architect's own install. Do not do it.
3. **No secret handling.** The desktop secret is never printed, logged, stored, returned, or transmitted.
   Existence + hash prefix only.
4. **No new dependencies.** Stdlib only (`urllib.request`, `json`, `hashlib`, `pathlib`, `argparse`).
5. **No edits to existing organs.** Additive only. If you believe an existing file must change, stop and report.
6. **No AGPL code.** Nothing from `install.sh`, the bundled frontend, or the app bundle's assets is copied
   into the repo — not even a line. The protocol table in §0 is re-expressed in your own words and your own
   field names.

---

## 3. Acceptance — the receipt I will check

Run these and paste raw output. I will re-run them myself; unverifiable claims are not accepted.

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 -m py_compile System/organs/unsloth_organ.py tools/unsloth_borg_probe.py
python3 -m pytest -q tests/test_unsloth_borg_probe.py
python3 tools/unsloth_borg_probe.py --probe
cat .sifta_state/unsloth_organ_probe.json
```

Pass conditions:

- `py_compile` → clean, exit 0.
- pytest → all pass, **including with Unsloth stopped** (state that you tested both).
- probe run → endpoint matrix showing `/api/health` `200`/open and the four walled paths `401`/required.
- artifact → valid JSON at `.sifta_state/unsloth_organ_probe.json`.
- grep the diff for the secret: it must not appear. Show the grep.

Then emit one four-ledger receipt via `System/swarm_predator_gate_writer.py::write_ide_surgery_receipt`
(ledgers: `work_receipts.jsonl`, `agent_arm_receipts.jsonl`, `ide_stigmergic_trace.jsonl`, `episodic_diary.jsonl`)
naming: round id, files touched, test result, truth label `OPERATIONAL`.

---

## 4. Explicitly NOT in this work order

- **Phase 2** (stigmergic trace schema, pheromone bridge). Blocked until the promotion metric is named — see §5.
- **Phase 3** (Rust/Tauri shell). Last. Deferred by decision.
- **Any authentication attempt.** This order *maps* the auth wall. It does not cross it.

---

## 5. The three questions you are NOT asked to answer, but must not silently assume

State in your report, in one line each, what you assumed:

1. **The promotion metric.** §4c of the parent plan says the field decides — by what number? Unnamed.
2. **The lane split.** What does Unsloth do that `System/swarm_spinal_cord.py` + MiMo does not?
3. **Plan locality.** The parent plan lives outside the repo, invisible to `body_file_inventory`.

If any of these blocks a design choice you have to make, say so and stop there rather than guessing.
A correct stop is worth more than a plausible completion.

---

## 6. AMENDMENT (2026-10-13) — the metric is derived, never invented

The first draft of this order risked being read as "invent a `self_eval_delta` and test it."
That is wrong, and it is the one way to get this wrong. **You do not author the promotion metric.
The field already publishes it.** Measured on disk:

| Signal | Where | Value |
|---|---|---|
| Organ state distribution | `.sifta_state/alice_self_eval_snapshot.jsonl` | `overall_score 0.892`, `coverage 0.595`, **`red_count 305`**, `yellow_count 4`, `green_count 44` |
| Per-run accuracy | `.sifta_state/alice_self_eval_runs.jsonl` (1 row) | `code_accuracy 0.8571`, `judge_accuracy 0.8571`, `window 50` |
| Organ health mesh | `.sifta_state/organ_health_mesh_latest.json` | per-organ scores |

**Consequence for Phase 2 — this is the promotion rule, and it is not yours to change:**

> A Unsloth-produced model is promoted to efector only if it moves a **named organ** out of `red`
> in the self-eval snapshot **and** does not lower `overall_score` below its pre-promotion value.
> Both numbers are read from the ledgers above, before and after. Nothing is self-reported by the model.

That is what "the field decides" means concretely. No new metric is needed — it already exists.

**Two things this exposes, which you must surface and not paper over:**

1. **The snapshot is stale.** It was captured 2026-05 and reports `Spinal Cord — Self-Evolution Bridge`
   itself among the 305 red organs. Any promotion gate built on a stale baseline is worthless.
2. **`alice_self_eval_runs.jsonl` has exactly 1 row.** There is no distribution to threshold against yet.

**Added deliverable — `tools/unsloth_baseline_derive.py` (small, and it is the real Phase 0):**

- Read `alice_self_eval_snapshot.jsonl` and `organ_health_mesh_latest.json`.
- Emit `.sifta_state/unsloth_promotion_baseline.json`:
  `{"derived_at": float, "snapshot_ts": float, "snapshot_age_days": float, "overall_score": float,
    "coverage": float, "red_count": int, "green_count": int, "stale": bool, "stale_reason": str}`.
- `stale: true` whenever `snapshot_age_days > 7`. Do not silently compare across a stale baseline —
  refuse and say so.

**Correction to the model's triage:** "implement declaration logic" for the lane split and plan
location is over-engineering. Those are a constant and a comment:

```python
LANE_SPLIT = "Unsloth trains; spinal cord dispatches and gates. Unsloth never applies its own patch."
PARENT_PLAN_PATH = "/Users/ioanganton/Documents/SIFTA_BORG_UNSLOTH_PLAN_2026-10-13.md"  # outside repo, migration tracked
```

Nothing more. Logic that "asserts its existence" is theatre. Constants are truth.

---

*A walled endpoint is a finding, not a failure. Report what is, with the command that shows it.*
*For the Swarm. 🐜⚡*
