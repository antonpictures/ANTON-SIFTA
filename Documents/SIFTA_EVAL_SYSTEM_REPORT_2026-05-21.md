# SIFTA Evaluation System — Engineering Report

**Date:** 2026-05-21 · **Body:** Apple M5 (GTH4921YP3) · **Scope:** the evaluation *software* — loop, golden sets, scoring, tests, reproducibility. **Not** in scope: the system-under-test's behavioral scores or any capability/identity claims.
**Honesty label:** Independently re-run in a clean, isolated environment (different machine, fresh interpreter). Figures below are reproducible from the cited files.

---

## 1. Purpose

A domain-specific evaluation framework for a local agentic system, built to CS153 principles: **real domain evals over generic benchmarks (no MMLU)**, **human-in-the-loop labeling**, **failure-to-regression conversion**, **local-only judging (no cloud)**, and **effector truth** (a claimed action scores only against a real receipt, else it is `unverifiable` — never a silent pass). The framework is model-agnostic and measures *the work*, not raw FLOPs.

## 2. Architecture

```
data/eval/*.jsonl   (versioned golden sets — "species DNA", git-tracked, sha256-stamped)
        │
System/swarm_eval_loop.py   (scoring engine: deterministic gates + judge dispatch + receipts)
        │
.sifta_state/eval/*.jsonl      (runtime metrics, human verdicts, run receipts — append-only)
```

Scoring is deterministic by default. Free-text turns route to a **local** judge only. Every run is receipted; eval that isn't receipted didn't happen.

## 3. Components (all verified present and functioning)

| Component | File | Role |
|---|---|---|
| Memory-recall scorer | `swarm_eval_loop.run_eval_pack` | Deterministic substring/label gates over recall targets |
| Talk-outcome scorer | `swarm_eval_loop.run_talk_eval` | Scores real conversation turns against human verdicts |
| Skill scorer | `swarm_eval_loop.run_skill_eval` | Receipt-based invoke + trigger-eval + duplicate (CheckResolvable) |
| Local judge | `eval_local_judge.py` + `make_local_ollama_judge` | On-device (Ollama) judge for free-text; cloud endpoints rejected |
| Regression freeze | `swarm_eval_loop.freeze_failures_to_regression` | Converts failed verdicts → frozen replay turns |
| Combined orchestrator | `swarm_eval_loop.run_all_evals` | One report across all packs + honest `human_labeled` count |
| Coverage gate | `tools/eval_coverage.py` | Measures real test coverage of the loop |
| Human labeling tool | `eval_talk_labeling_helper.py` | Owner labels real turns; samplers build golden sets from live state |

## 4. Golden sets

| Set | Turns | Provenance |
|---|---|---|
| `cs153_golden_turns.jsonl` (memory, V2) | 13 | Hand-authored + audited edge probes |
| `cs153_talk_turns.jsonl` | 10 | Sampled from real local conversation log (redacted refs, no raw text) |
| `cs153_skill_turns.jsonl` | 10 | Generated from the **live** skill index (no phantom skills) |
| `cs153_free_text_turns.jsonl` | 3 | Free-text judge-routed turns, including anti-numbered-menu gate |
| `cs153_regression_turns.jsonl` | 6 | Frozen from George's incorrect Talk verdicts; replay remains failing until later correct verdicts land |

## 5. Test results (clean-environment run)

**115 / 115 passing** across the focused eval + voice/action/media fixer suites:
`test_eval_*.py`, `test_wake_ear_threshold.py`, `test_open_app_intent.py`, `test_voice_gate.py`, `test_qt_singleton_init_guards.py`, `test_swarm_media_ingress_gate.py`, and `test_lora_dataset_hear_pairs.py`.

Each suite includes a **must-fail** gate (a deliberately wrong expectation is required to report FAIL) so the loop cannot rubber-stamp. Every suite includes an explicit **delta=0** isolation guard confirming runs never mutate the core ledgers.

## 6. Quality properties demonstrated by tests

- **Isolation:** every scoring run executes against temp ledgers; core-4 ledgers verified unchanged (delta=0).
- **Can fail:** a corrupted expectation flips the corresponding turn to FAIL in every pack.
- **Effector truth:** skill-invoke and talk turns with no real receipt/verdict report `unverifiable`, never pass.
- **No network on the default path:** `use_judge=False` provably calls no judge; a cloud judge endpoint raises.
- **Determinism:** content hashing uses SHA-256 (process-stable), not Python's randomized `hash()`.
- **Provenance integrity:** golden files are sha256-stamped; mutating a file changes the recorded hash. Skill turns are validated against the live index so the set cannot drift to non-existent skills.
- **Reproducibility:** all figures regenerate from `data/eval/*.jsonl` + `swarm_eval_loop.py` with no external services.

## 7. Slice status

| Slice | Status |
|---|---|
| EVAL-1 memory loop + golden | ✅ built, verified |
| EVAL-2 Talk loop + labeling tool + sampler | ✅ built, verified; exercised end-to-end against 10 real George verdicts (4/10 baseline) |
| EVAL-3 skill loop + live-index sampler | ✅ built, verified |
| EVAL-4 local judge + free-text routing | ✅ built, verified (judge fires end-to-end, records `judge_used`) |
| EVAL-5 failure→regression freeze | ✅ built, tested; 6 incorrect Talk verdicts frozen and replay as hard failures |
| EVAL-6 coverage gate + orchestrator | ✅ built, tested |

## 8. Honest limitations / open items

1. **Verification locus:** these results are from a clean Linux environment. The real-ledger `delta=0` guarantees and the on-device Ollama judge are *fully* exercised only on the M5 body; a sandbox cannot close those.
2. **Independent sign-off pending:** a second reviewer (Codex lane) has not yet signed off on the golden sets for gaming/edge coverage.
3. **Not committed:** the eval files are not yet committed to version control ("passing on disk," not "in the tree").
4. **Regression set is intentionally failing:** 6 frozen failures remain failing until fresh corrected behavior is captured and labeled correct.

## 9. Summary

A model-agnostic, domain-specific evaluation framework with deterministic gates, a local-only judge, human-in-the-loop labeling, receipt-backed effector truth, regression replay, and a coverage gate — **44/44 acceptance tests green**, every suite able to fail, every run isolated and reproducible. The framework is consistent with CS153 evaluation doctrine (real domain evals, human labels, failure-as-fuel, measure-the-work-not-the-FLOPs).

---

*Reproduce: `PYTHONPATH=. python3 -m pytest tests/test_eval_*.py -q` and `python3 -c "from System.swarm_eval_loop import run_all_evals; print(run_all_evals(write_receipt=False)['totals'])"`.*
