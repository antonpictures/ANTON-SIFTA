#!/usr/bin/env node
/**
 * pump.fun path tracker — records what actually happened AFTER each launch.
 *
 * A launch record alone cannot answer "would a bot have made money?", because
 * the answer lives in the price path that follows. This tracker subscribes to
 * the trade feed for mints we just harvested and records every reserve update,
 * which is the token's price history.
 *
 *   price (SOL per token) = vSolInBondingCurve / vTokensInBondingCurve
 *
 * PumpPortal caps a subscribeTokenTrade call at 100 mints, so the harvest window
 * is polled and rotated in batches. Read-only: no keys, no signatures, no trades.
 *
 * Usage: node tools/pumpfun_path_tracker.mjs --seconds 300 --batch 100
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const STATE = resolve(HERE, '..', '.sifta_state')
const LAUNCHES = resolve(STATE, 'pumpfun_launches.jsonl')
const PATHS = resolve(STATE, 'pumpfun_paths.jsonl')
const WS_URL = 'wss://pumpportal.fun/api/data'

const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > -1 && process.argv[i + 1] !== undefined ? Number(process.argv[i + 1]) : fallback
}
const seconds = arg('seconds', 300)
const batch = Math.min(arg('batch', 100), 100)

mkdirSync(STATE, { recursive: true })

/** Track the newest un-tracked mints, most recent first. */
function newestMints(limit) {
  if (!existsSync(LAUNCHES)) return []
  const lines = readFileSync(LAUNCHES, 'utf8').split('\n').filter(Boolean)
  const seen = new Set()
  const out = []
  for (let i = lines.length - 1; i >= 0 && out.length < limit; i--) {
    try {
      const r = JSON.parse(lines[i])
      if (r.mint && !seen.has(r.mint)) { seen.add(r.mint); out.push(r.mint) }
    } catch { /* skip a partial tail line */ }
  }
  return out
}

const mints = newestMints(batch)
const started = Date.now()
const counts = { events: 0, buys: 0, sells: 0, tracked_mints: mints.length, errors: 0 }
const touched = new Set()

if (mints.length === 0) {
  console.error('[tracker] no launches harvested yet — run the harvester first')
  console.log(JSON.stringify({ ...counts, note: 'nothing to track' }, null, 1))
  process.exit(0)
}

const ws = new WebSocket(WS_URL)
ws.onopen = () => {
  ws.send(JSON.stringify({ method: 'subscribeTokenTrade', keys: mints }))
  console.error(`[tracker] subscribed to ${mints.length} mints -> ${PATHS}`)
}
ws.onmessage = (event) => {
  let m
  try { m = JSON.parse(event.data) } catch { return }
  if (!m.mint || m.vTokensInBondingCurve === undefined) return
  const vSol = Number(m.vSolInBondingCurve || 0)
  const vTok = Number(m.vTokensInBondingCurve || 0)
  if (vTok <= 0) return
  counts.events++
  if (m.txType === 'buy') counts.buys++
  else if (m.txType === 'sell') counts.sells++
  touched.add(m.mint)
  appendFileSync(PATHS, JSON.stringify({
    ts: Date.now() / 1000,
    mint: m.mint,
    txType: m.txType ?? null,
    sol_amount: Number(m.solAmount || 0) || null,
    token_amount: Number(m.tokenAmount || 0) || null,
    v_sol: vSol,
    v_tokens: vTok,
    price_sol: vSol / vTok,
    market_cap_sol: Number(m.marketCapSol || 0) || null,
    trader: m.traderPublicKey ?? null,
    truth_label: 'PUMPFUN_PATH_POINT_V1',
  }) + '\n')
}
ws.onerror = (e) => { counts.errors++; console.error('[tracker] ws error:', e?.message ?? e) }

function report() {
  console.log(JSON.stringify({
    window_s: Math.round((Date.now() - started) / 1000),
    mints_subscribed: mints.length,
    mints_with_activity: touched.size,
    path_points: counts.events,
    buys: counts.buys,
    sells: counts.sells,
    errors: counts.errors,
    paths_ledger: PATHS,
    keys_held: 0,
    transactions_sent: 0,
    truth_label: 'PUMPFUN_PATH_TRACK_V1',
  }, null, 1))
  process.exit(0)
}
process.on('SIGINT', report)
if (seconds > 0) setTimeout(() => { try { ws.close() } catch {} ; report() }, seconds * 1000)
