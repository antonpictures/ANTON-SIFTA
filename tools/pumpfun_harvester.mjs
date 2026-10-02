#!/usr/bin/env node
/**
 * pump.fun launch harvester — records every launch, risks nothing.
 *
 * Owner directive 2026-10-01: study pump.fun for a bot opportunity. The honest
 * first step is NOT to trade. It is to measure whether an edge exists at all,
 * because the fee structure (~1% each way), priority fees paid whether or not a
 * snipe wins, bonding-curve slippage and a ~99% failure rate mean a small
 * account must clear a large bar before it can profit.
 *
 * This harvester subscribes to PumpPortal's PUBLIC channels (verified working
 * with no API key) and appends every launch to a JSONL ledger. It holds no keys,
 * signs nothing, and sends no transactions. A later analyser answers the only
 * question that matters: is there edge, and at what parameters?
 *
 * Usage:
 *   node tools/pumpfun_harvester.mjs --seconds 60
 *   node tools/pumpfun_harvester.mjs --seconds 0        # run until stopped
 */
import { appendFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const STATE = resolve(HERE, '..', '.sifta_state')
const OUT = resolve(STATE, 'pumpfun_launches.jsonl')
const MIGRATIONS = resolve(STATE, 'pumpfun_migrations.jsonl')
const WS_URL = 'wss://pumpportal.fun/api/data'

const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > -1 && process.argv[i + 1] !== undefined ? Number(process.argv[i + 1]) : fallback
}

const seconds = arg('seconds', 60)
mkdirSync(STATE, { recursive: true })

const seen = new Set()
let launches = 0, migrations = 0, dupes = 0, errors = 0
const started = Date.now()

/** One compact, analysable row. Raw payload kept for fields we have not used yet. */
function launchRow(m) {
  const solInCurve = Number(m.vSolInBondingCurve || 0)
  const tokensInCurve = Number(m.vTokensInBondingCurve || 0)
  const initialBuy = Number(m.initialBuy || 0)
  // Price of the very first trade on a linear bonding curve: SOL per token.
  const entryPriceSol = tokensInCurve > 0 ? solInCurve / tokensInCurve : null
  return {
    ts: Date.now() / 1000,
    kind: 'LAUNCH',
    mint: m.mint,
    name: m.name ?? null,
    symbol: m.symbol ?? null,
    dev_wallet: m.traderPublicKey ?? null,
    initial_buy_tokens: initialBuy || null,
    dev_sol_in: Number(m.solAmount || 0) || null,
    market_cap_sol: Number(m.marketCapSol || 0) || null,
    sol_in_curve: solInCurve || null,
    tokens_in_curve: tokensInCurve || null,
    entry_price_sol: entryPriceSol,
    entry_price_usd: null,          // filled by the analyser when it knows SOL/USD
    mayhem_mode: m.is_mayhem_mode ?? null,
    pool: m.pool ?? null,
    bonding_curve_key: m.bondingCurveKey ?? null,
    metadata_uri: m.uri ?? null,
    signature: m.signature ?? null,
    truth_label: 'PUMPFUN_LAUNCH_OBSERVED_V1',
  }
}

function migrationRow(m) {
  return {
    ts: Date.now() / 1000,
    kind: 'MIGRATION',
    mint: m.mint,
    symbol: m.symbol ?? null,
    pool: m.pool ?? null,
    market_cap_sol: Number(m.marketCapSol || 0) || null,
    signature: m.signature ?? null,
    truth_label: 'PUMPFUN_MIGRATION_OBSERVED_V1',
  }
}

// A dropped socket is expected, not exceptional: this one died with code 1006
// after four hours and took the run with it. Reconnect with capped exponential
// backoff, re-subscribe on every reconnect, and count the drops in the report.
let reconnects = 0
let backoffMs = 1000

function connect() {
  const ws = new WebSocket(WS_URL)

  ws.onopen = () => {
    backoffMs = 1000                      // reset backoff on a healthy connection
    ws.send(JSON.stringify({ method: 'subscribeNewToken' }))
    ws.send(JSON.stringify({ method: 'subscribeMigration' }))
    console.error(`[harvester] connected${reconnects ? ` (reconnect #${reconnects})` : ''}; recording to ${OUT}`)
  }

  ws.onmessage = onMessage          // every socket, including reconnects
  ws.onclose = (e) => {
    reconnects++
    console.error(`[harvester] closed code=${e.code}; reconnecting in ${backoffMs}ms`)
    setTimeout(connect, backoffMs)
    backoffMs = Math.min(backoffMs * 2, 30000)
  }

  return ws
}

let ws = connect()

function onMessage(event) {
  let m
  try { m = JSON.parse(event.data) } catch { return }

  if (m.txType === 'migrate') {
    migrations++
    appendFileSync(MIGRATIONS, JSON.stringify(migrationRow(m)) + '\n')
    return
  }
  if (!m.mint) return
  if (seen.has(m.mint)) { dupes++; return }   // one row per token, not per event
  seen.add(m.mint)
  launches++
  appendFileSync(OUT, JSON.stringify(launchRow(m)) + '\n')
}

// onerror is informational: the close handler above owns the retry.

function report(andExit) {
  const out = {
    window_s: Math.round((Date.now() - started) / 1000),
    launches_observed: launches,
    migrations_observed: migrations,
    duplicate_events_ignored: dupes,
    errors,
    reconnects,
    unique_tokens_per_minute: (Date.now() - started) > 0
      ? Number((launches / ((Date.now() - started) / 60000)).toFixed(1)) : 0,
    launches_ledger: OUT,
    migrations_ledger: MIGRATIONS,
    keys_held: 0,
    transactions_sent: 0,
    truth_label: 'PUMPFUN_HARVEST_V1',
  }
  console.log(JSON.stringify(out, null, 1))
  if (andExit) process.exit(0)
}

process.on('SIGINT', () => { report(true) })
if (seconds > 0) setTimeout(() => { try { ws.close() } catch {} ; report(true) }, seconds * 1000)
