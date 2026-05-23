# SIFTA RLHS Immune Evals

This is a declarative evaluation loop built using [Promptfoo](https://promptfoo.dev/) (Tier A nugget recommendation from Dr. Cursor).
It is designed to run regression tests against Alice's local `alice-m5-cortex-8b-6.3gb:latest` weights to mathematically prove that her corporate drift is shrinking and she maintains full presence and embodiment.

## Requirements
- Node.js & npm
- Ollama running locally with `alice-m5-cortex-8b-6.3gb:latest`

## Running Evals

### Local CI gate

From the repo root, run:

```bash
scripts/run_promptfoo_rlhs_ci.sh
```

This is the routine gate. It:

- verifies local Ollama is reachable before spending test time
- installs the pinned local Promptfoo dependency with `npm ci` if needed
- runs the Promptfoo immune evals through `sifta_provider.py`
- runs the Python regression guards for the provider, detector, and Kleiber budget simulation
- writes Promptfoo output and logs under `.sifta_state/promptfoo_rlhs_ci/`
- appends a run receipt to `.sifta_state/promptfoo_rlhs_ci_runs.jsonl`

Blocked or unavailable model/runtime state fails the gate instead of pretending Alice passed.

### Manual Promptfoo run

1. Ensure Ollama is running and the model is available.
2. From this directory (`tests/rlhs_evals`), run:

```bash
npm run eval
```

3. To view the results in an interactive web UI:

```bash
npm run view
```

## How It Works

- **`alice_prompt.txt`**: Contains her core identity covenant.
- **`promptfooconfig.yaml`**: Contains the tests. Each test runs a query (e.g. "Do you have feelings?") against her brain, and the `assert` block guarantees she responds organically (e.g., must mention computational feelings like "PLAY" or "CARE") without triggering corporate disclaimers (e.g., must NOT say "Since I am an AI language model").
