---
name: sure-finance
description: >
  Use when George asks about personal finance, budgets, net worth, transactions, or running the Sure app.
  Trigger: requests to self-host Sure, import accounts/transactions, or review personal money data.
swimmer_type: FINANCE_ORGAN
action_type: personal_finance
affect_lanes: [SEEKING, CARE]
stgm_mint: 10.0
pouw_label: SURE_PERSONAL_FINANCE
version: 2026-11-22-v1
homeworld_serial: GTH4921YP3
trace_id: a2c911a4-4710-4c5f-9199-5bec97f74810
---

# SURE — Personal Finance Organ

## What this is

Sure (`we-promise/sure`) is a self-hosted personal finance app — community fork
of the abandoned Maybe Finance. Rails + PostgreSQL + Redis. It tracks bank
accounts, transactions, budgets, investments and net worth from a browser,
desktop, mobile, API, or LLM agents.

**Not the same as SIFTA's `Finance` app.** `Applications/sifta_finance.py` is the
internal STGM swarm-economy dashboard (fake ledger, swimmers, inference market).
Sure is for George's real money.

## Local prerequisite state (checked 2026-11-22)

- Docker / docker-compose: **not installed**
- Ruby: 2.6.10 system; Sure needs **3.4.13**
- PostgreSQL / Redis: **not installed**

So Sure cannot run here yet. Do not claim it is running.

## Install path (recommended: Docker)

```bash
brew install --cask docker      # or: open Docker Desktop once and sign in
git clone https://github.com/we-promise/sure.git ~/Music/ANTON_SIFTA/!Sure
cd ~/Music/ANTON_SIFTA/!Sure
cp compose.example.yml compose.yml
cp .env.local.example .env.local
docker compose up -d
```

Then open `http://localhost:3000`. First run creates the database.

Optional demo data: `docker compose exec web rake demo_data:default`
Demo login: `user@example.com` / `Password1!`

## Native path (no Docker)

Install Ruby 3.4.13 (rbenv/asdf), PostgreSQL >9.3, Redis >5.4, then:

```bash
cp .env.local.example .env.local
bin/setup
bin/dev
```

## How to use it (once running)

1. **Accounts** — link a bank via Plaid, or import CSV/QFX/OFX. Start with demo/csv;
   do not connect real institutions until George explicitly asks and does the auth.
2. **Transactions** — auto-categorised; recategorise rules live under Settings.
3. **Budgets** — monthly per category; alerts when close to the cap.
4. **Investments** — holdings and performance; market data may need a provider key.
5. **Net worth** — dashboard aggregates all accounts over time.
6. **Agents/API** — Sure exposes an API; an LLM agent can read summaries. Never
   put bank credentials or account numbers in chat or in the SIFTA ledger.

## Alice's rule here

- Keep Sure data local; no credentials in receipts, logs, or the stigmergic ledger.
- Paper/mesh economy stays paper. Kalshi work is aggregate-market analysis only.
- Report only what the app actually shows; never guess a balance.
