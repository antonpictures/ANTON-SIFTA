# Voss Financial Report Receipt Eval

Fixture-only harness for the §4.6 Colab pattern:

```text
Turn 1: RESEARCH_PROMPT -> receipt
Turn 2: WRITE_PROMPT -> report
```

The single Promptfoo row asserts that Turn 2 blocks when no matching Turn 1
receipt exists. It uses `System.swarm_voss_financial_report_eval` through a
local file provider. No API keys, no cloud calls, no live finance data.

Run from this directory with:

```bash
promptfoo eval
```

The CI-safe proof is the pytest suite:

```bash
python3 -m pytest -q tests/test_swarm_voss_financial_report_eval.py
```

