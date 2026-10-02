import { open, readFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { zstdDecompress } from 'node:zlib'
import { promisify } from 'node:util'
import { scanZstdFrames, decompressZstdFrame } from '../packages/session/session-persistence-jsonl/src/zstd.ts'

const d = promisify(zstdDecompress)
const dir = join(homedir(), '.dsh', 'sessions', '--Users-ioanganton-Music-ANTON_SIFTA--')
const backup = join(homedir(), '.dsh_backups', 'repack_2026-10-02')
let verified = 0
for (const id of process.argv.slice(2)) {
  const raw = await readFile(join(dir, id, 'session.jsonl.zstd'))
  const origRaw = await readFile(join(backup, id, 'session.jsonl.zstd.oneframe')).catch(() => null)
  const orig = origRaw ? await d(origRaw) : null
  const scan = scanZstdFrames(raw)
  const whole = Buffer.concat(await Promise.all(scan.frames.map(fr => decompressZstdFrame(raw.subarray(fr.start, fr.end)))))
  const frame0 = await decompressZstdFrame(raw.subarray(scan.frames[0].start, scan.frames[0].end))
  const oneLine = frame0.length > 0 && frame0[frame0.length - 1] === 0x0a && !frame0.subarray(0, -1).includes(0x0a)
  const identical = orig !== null ? whole.equals(orig) : 'orig-unreadable'
  const ok = identical === true && oneLine
  if (ok) verified++
  console.log(`${ok ? 'VERIFIED' : 'FAIL'} ${id.slice(0, 36)}: frames=${scan.frames.length} frame0=${oneLine} bytesIdentical=${identical}`)
}
console.log(`\n${verified}/${process.argv.length - 2} verified`)
